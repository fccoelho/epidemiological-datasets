"""
News-feed aggregator: concurrent fetching, normalization, deduplication
and disease tagging of public-health news items.

Feeds are fetched concurrently with polite per-source rate limiting and
JSON-cached on disk (default TTL 6h). Every source fails independently:
one broken feed never prevents the others from being collected.

Author: Flávio Codeço Coelho
License: MIT
"""

from __future__ import annotations

import difflib
import hashlib
import html
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus, urlsplit, urlunsplit

import pandas as pd
import requests

from epidatasets.newsfeeds.geotag import geotag_items
from epidatasets.newsfeeds.models import FeedItem, FeedSource
from epidatasets.newsfeeds.sources import (
    DEFAULT_GOOGLE_NEWS_QUERY,
    FEED_SOURCES,
    GOOGLE_NEWS_TEMPLATE,
    tag_text,
)

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) epidatasets-newsfeeds/1.0 "
    "(Research Purpose)"
)

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_TRACKING_PARAMS = {"fbclid", "gclid", "ref", "ref_src", "cmpid"}


def strip_html(text: str | None) -> str:
    """Strip HTML tags/entities and collapse whitespace."""
    if not text:
        return ""
    text = html.unescape(_HTML_TAG_RE.sub(" ", text))
    return re.sub(r"\s+", " ", text).strip()


def canonical_url(url: str) -> str:
    """
    Canonical form of *url* for deduplication: lowercase scheme/host,
    no fragment, tracking parameters removed, remaining query sorted,
    no trailing slash.
    """
    parts = urlsplit(url.strip())
    query = [
        (k, v)
        for k, v in [tuple(p.split("=", 1)) if "=" in p else (p, "")
                     for p in parts.query.split("&")]
        if k and k.lower() not in _TRACKING_PARAMS
        and not k.lower().startswith("utm_")
    ]
    query = sorted(query)
    qs = "&".join(f"{k}={v}" if v else k for k, v in query)
    path = parts.path or "/"
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), path.rstrip("/"), qs, "")
    )


def _norm_title(title: str) -> str:
    from epidatasets.newsfeeds.geotag import normalize_text

    return normalize_text(title)


class NewsAggregator:
    """
    Aggregator for public-health news feeds.

    Args:
        cache_dir: Directory for the feed cache (default from
            ``[tool.epidatasets] cache_dir`` / ``~/.cache/epidatasets``).
        cache_ttl_hours: Feed cache time-to-live in hours.
        max_workers: Number of concurrent feed fetches.
        requests_per_source: Polite per-source rate limit (requests/sec).

    Example:
        >>> agg = NewsAggregator()
        >>> items = agg.fetch(days=30)
        >>> locations = agg.geotag(items)
    """

    def __init__(
        self,
        cache_dir: str | None = None,
        cache_ttl_hours: int = 6,
        max_workers: int = 4,
        requests_per_source: float = 1.0,
    ):
        from epidatasets.utils.cache import CacheManager
        from epidatasets.utils.rate_limit import RateLimiter

        if cache_dir is None:
            import os

            cache_dir = os.path.join(
                os.path.expanduser("~"), ".cache", "epidatasets", "newsfeeds"
            )
        self._cache = CacheManager(cache_dir=cache_dir)
        self.cache_ttl_hours = cache_ttl_hours
        self.max_workers = max_workers
        self._rate_limiter = RateLimiter(requests_per_source)
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": _USER_AGENT})
        #: Per-source outcome of the last :meth:`fetch` call:
        #: ``{source: {"items": int, "error": str | None, "cached": bool}}``.
        self.last_fetch_status: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Feed resolution
    # ------------------------------------------------------------------

    def _resolve_sources(
        self,
        sources: list[str] | None,
        queries: list[str] | None,
        google_locale: tuple[str, str, str],
        limit_per_feed: int = 50,
    ) -> list[FeedSource]:
        resolved: list[FeedSource] = []
        if sources:
            unknown = [s for s in sources if s not in FEED_SOURCES]
            if unknown:
                raise KeyError(
                    f"Unknown feeds: {unknown}. "
                    f"Available: {sorted(FEED_SOURCES)}"
                )
            resolved.extend(FEED_SOURCES[s] for s in sources)
        else:
            resolved.extend(FEED_SOURCES.values())

        resolved = [
            FeedSource(
                name=s.name,
                url=s.url.format(limit=limit_per_feed)
                if "{limit}" in s.url
                else s.url,
                kind=s.kind,
                title=s.title,
                language=s.language,
                homepage=s.homepage,
                notes=s.notes,
            )
            for s in resolved
        ]

        for i, query in enumerate(queries or []):
            hl, gl, ceid = google_locale
            url = GOOGLE_NEWS_TEMPLATE.format(
                query=quote_plus(query), hl=hl, gl=gl, ceid=ceid
            )
            slug = re.sub(r"[^a-z0-9]+", "_", query.lower())[:24].strip("_")
            resolved.append(
                FeedSource(
                    name=f"google_news_{slug or i}",
                    url=url,
                    kind="google_news",
                    title=f"Google News: {query}",
                    language=hl,
                    homepage="https://news.google.com/",
                    notes="Dynamic topic feed; low-volume research use.",
                )
            )
        if not queries and not sources:
            # default Google News topic feed for the all-feeds default
            hl, gl, ceid = google_locale
            resolved.append(
                FeedSource(
                    name="google_news",
                    url=GOOGLE_NEWS_TEMPLATE.format(
                        query=quote_plus(DEFAULT_GOOGLE_NEWS_QUERY),
                        hl=hl,
                        gl=gl,
                        ceid=ceid,
                    ),
                    kind="google_news",
                    title="Google News: outbreaks (default query)",
                    language=hl,
                    homepage="https://news.google.com/",
                    notes="Dynamic topic feed; low-volume research use.",
                )
            )
        return resolved

    # ------------------------------------------------------------------
    # Fetching & parsing
    # ------------------------------------------------------------------

    def _fetch_raw(self, url: str) -> bytes:
        resp = self._session.get(url, timeout=20)
        resp.raise_for_status()
        return resp.content

    def _fetch_payload(self, source: FeedSource) -> tuple[dict | None, bool]:
        """Return the parsed payload dict (cached) and cache-hit flag."""
        key = "newsfeed::" + hashlib.sha1(
            f"{source.name}::{source.url}".encode()
        ).hexdigest()[:16]
        cached = self._cache.get(key, max_age_hours=self.cache_ttl_hours)
        if cached is not None and "items" in cached:
            return cached, True
        raw = self._fetch_raw(source.url)
        payload = {
            "items": self._parse_payload(raw, source),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
        self._cache.set(key, payload)
        return payload, False

    def _parse_payload(self, raw: bytes, source: FeedSource) -> list[dict]:
        if source.kind == "who_don":
            return self._parse_who_don(json.loads(raw), source)
        return self._parse_rss(raw, source)

    def _parse_rss(
        self, raw: bytes, source: FeedSource, limit: int = 50
    ) -> list[dict]:
        import feedparser

        parsed = feedparser.parse(raw)
        items: list[dict] = []
        for entry in parsed.entries[:limit]:
            title = strip_html(entry.get("title"))
            if source.kind == "google_news" and " - " in title:
                # Google News appends the source name: "Headline - Outlet"
                title = title.rsplit(" - ", 1)[0].strip()
            link = entry.get("link", "")
            if not title or not link:
                continue
            published = None
            for ts_key in ("published_parsed", "updated_parsed"):
                ts = entry.get(ts_key)
                if ts:
                    # feedparser struct_time is UTC
                    published = datetime(*ts[:6], tzinfo=timezone.utc).replace(
                        tzinfo=None
                    )
                    break
            summary = strip_html(entry.get("summary") or entry.get("description"))
            items.append(
                {
                    "source": source.name,
                    "title": title,
                    "url": link,
                    "published_utc": published.isoformat()
                    if published
                    else None,
                    "summary": summary,
                    "language": source.language,
                    "feed_url": source.url,
                }
            )
        return items

    def _parse_who_don(
        self, payload: dict, source: FeedSource, limit: int = 50
    ) -> list[dict]:
        items: list[dict] = []
        for entry in payload.get("value", [])[:limit]:
            title = strip_html(entry.get("Title"))
            if not title:
                continue
            item_url = entry.get("ItemDefaultUrl") or ""
            if item_url and not item_url.startswith("http"):
                item_url = "https://www.who.int" + item_url
            published = None
            raw_date = entry.get("PublicationDate") or entry.get(
                "PublicationDateAndTime"
            )
            if raw_date:
                try:
                    published = (
                        datetime.fromisoformat(
                            str(raw_date).replace("Z", "+00:00")
                        )
                        .astimezone(timezone.utc)
                        .replace(tzinfo=None)
                    )
                except ValueError:
                    published = None
            summary = strip_html(
                entry.get("Summary") or entry.get("Overview")
            )
            items.append(
                {
                    "source": source.name,
                    "title": title,
                    "url": item_url,
                    "published_utc": published.isoformat()
                    if published
                    else None,
                    "summary": summary,
                    "language": source.language,
                    "feed_url": source.url,
                }
            )
        return items

    # ------------------------------------------------------------------
    # Normalization, dedup, tagging
    # ------------------------------------------------------------------

    @staticmethod
    def _filter_by_days(items: list[FeedItem], days: int | None) -> list[FeedItem]:
        if days is None:
            return items
        cutoff = datetime.utcnow() - timedelta(days=days)
        return [
            it for it in items
            if it.published_utc is None or it.published_utc >= cutoff
        ]

    @staticmethod
    def _dedupe(items: list[FeedItem]) -> list[FeedItem]:
        seen_urls: set[str] = set()
        by_url: list[FeedItem] = []
        # earliest first so duplicates keep the original, not the mirror
        for it in sorted(
            items, key=lambda i: i.published_utc or datetime.min
        ):
            canon = canonical_url(it.url)
            if canon in seen_urls:
                continue
            seen_urls.add(canon)
            by_url.append(it)

        # fuzzy title dedup (near-identical headlines within 1 day,
        # across sources — e.g. Google News mirrors the originals)
        kept: list[FeedItem] = []
        norm_titles: list[tuple[str, datetime | None]] = []
        for it in by_url:
            norm = _norm_title(it.title)
            dup = False
            for other, other_dt in norm_titles:
                dt = it.published_utc
                if (
                    dt is not None
                    and other_dt is not None
                    and abs((dt - other_dt).days) > 1
                ):
                    continue
                if abs(len(norm) - len(other)) > max(len(norm), len(other), 1) * 0.2:
                    continue
                if difflib.SequenceMatcher(None, norm, other).ratio() >= 0.9:
                    dup = True
                    break
            if not dup:
                kept.append(it)
                norm_titles.append((norm, it.published_utc))
        return kept

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch(
        self,
        sources: list[str] | None = None,
        days: int = 30,
        limit_per_feed: int = 50,
        queries: list[str] | None = None,
        google_locale: tuple[str, str, str] = ("en", "US", "en-US"),
    ) -> pd.DataFrame:
        """
        Fetch, normalize, deduplicate and disease-tag all feeds.

        Args:
            sources: Restrict to these registry feed names (default: all).
            days: Only keep items published within this many days
                (items without a date are kept).
            limit_per_feed: Maximum items parsed per feed.
            queries: Optional Google News topic queries, each producing a
                dynamic ``google_news_*`` feed.
            google_locale: ``(hl, gl, ceid)`` locale tuple for Google News.

        Returns:
            DataFrame with columns ``source``, ``title``, ``url``,
            ``published_utc`` (tz-naive UTC), ``summary``, ``language``,
            ``disease_tags`` (pipe-joined) and ``feed_url``, sorted by
            publication date (newest first). Per-source outcomes are
            available in :attr:`last_fetch_status`.
        """
        feed_sources = self._resolve_sources(
            sources, queries, google_locale, limit_per_feed
        )
        self.last_fetch_status = {}

        def worker(src: FeedSource) -> list[FeedItem]:
            payload, cached = self._fetch_payload(src)
            self.last_fetch_status[src.name] = {
                "items": len(payload["items"]),
                "error": None,
                "cached": cached,
            }
            out = []
            for d in payload["items"]:
                d = dict(d)
                if limit_per_feed and len(out) >= limit_per_feed:
                    break
                pub = d.get("published_utc")
                out.append(
                    FeedItem(
                        source=d["source"],
                        title=d["title"],
                        url=d["url"],
                        published_utc=pd.Timestamp(pub).to_pydatetime()
                        if pub
                        else None,
                        summary=d.get("summary", ""),
                        language=d.get("language", "en"),
                        disease_tags=[],
                        feed_url=d.get("feed_url", ""),
                    )
                )
            return out

        all_items: list[FeedItem] = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(worker, s): s for s in feed_sources}
            for fut in as_completed(futures):
                src = futures[fut]
                try:
                    all_items.extend(fut.result())
                except Exception as exc:
                    logger.warning("Feed %s failed: %s", src.name, exc)
                    self.last_fetch_status[src.name] = {
                        "items": 0,
                        "error": str(exc),
                        "cached": False,
                    }

        all_items = self._filter_by_days(all_items, days)
        all_items = self._dedupe(all_items)

        for it in all_items:
            it.disease_tags = tag_text(f"{it.title} {it.summary}")

        records = []
        for it in sorted(
            all_items, key=lambda i: i.published_utc or datetime.min, reverse=True
        ):
            d = it.to_dict()
            d["published_utc"] = pd.Timestamp(d["published_utc"])
            d["disease_tags"] = "|".join(it.disease_tags)
            records.append(d)
        df = pd.DataFrame(
            records,
            columns=[
                "source",
                "title",
                "url",
                "published_utc",
                "summary",
                "language",
                "disease_tags",
                "feed_url",
            ],
        )
        logger.info("Aggregated %d news items", len(df))
        return df

    # ------------------------------------------------------------------
    # Delegates
    # ------------------------------------------------------------------

    def geotag(self, items: pd.DataFrame) -> pd.DataFrame:
        """
        Geo-tag fetched items (see :func:`epidatasets.newsfeeds.geotag.geotag_items`).

        Returns one row per (item, mentioned location) with ``iso3``,
        ``lat`` and ``lon`` columns.
        """
        return geotag_items(items)

    def plot_timeline(
        self,
        items: pd.DataFrame,
        by: str = "disease_tags",
        freq: str = "W",
        out: str | None = None,
    ):
        """Plot a timeline of item counts (see :mod:`epidatasets.newsfeeds.visualize`)."""
        from epidatasets.newsfeeds.visualize import plot_timeline

        return plot_timeline(items, by=by, freq=freq, out=out)

    def plot_map(self, locations: pd.DataFrame, out: str | None = None):
        """Plot an interactive folium map (see :mod:`epidatasets.newsfeeds.visualize`)."""
        from epidatasets.newsfeeds.visualize import plot_map

        return plot_map(locations, out=out)

    def animate_map(
        self,
        locations: pd.DataFrame,
        out: str = "news_map.gif",
        freq: str = "W",
    ):
        """Render a cumulative map animation (see :mod:`epidatasets.newsfeeds.visualize`)."""
        from epidatasets.newsfeeds.visualize import animate_map

        return animate_map(locations, out=out, freq=freq)


def fetch_news(
    days: int = 30,
    sources: list[str] | None = None,
    queries: list[str] | None = None,
    cache_dir: str | None = None,
) -> pd.DataFrame:
    """Convenience one-shot fetch using a default :class:`NewsAggregator`."""
    return NewsAggregator(cache_dir=cache_dir).fetch(
        days=days, sources=sources, queries=queries
    )
