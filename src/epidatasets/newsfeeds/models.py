"""
Data models for the news-feed aggregator.

Defines the normalized :class:`FeedItem` produced by every feed parser and
the :class:`FeedSource` descriptor used by the feed registry.

Author: Flávio Codeço Coelho
License: MIT
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

FeedKind = Literal["rss", "who_don", "google_news"]


@dataclass
class FeedSource:
    """Description of a single news feed endpoint."""

    #: Short identifier used in the ``source`` column of fetched items.
    name: str
    #: Feed URL. For ``google_news`` sources this is a template with a
    #: ``{query}`` placeholder (URL-quoted by the aggregator).
    url: str
    #: Parser kind: ``rss`` (feedparser), ``who_don`` (WHO OData JSON API)
    #: or ``google_news`` (Google News RSS template).
    kind: FeedKind
    #: Human-readable feed name.
    title: str
    #: Primary language of the feed (ISO 639-1).
    language: str = "en"
    #: Publisher homepage (for docs/credits).
    homepage: str = ""
    #: Licensing / terms-of-service note surfaced in the docs.
    notes: str = ""


@dataclass
class FeedItem:
    """A single normalized news item, regardless of the source format."""

    #: Feed source identifier (see :data:`epidatasets.newsfeeds.FEED_SOURCES`).
    source: str
    #: Title/headline.
    title: str
    #: Item URL.
    url: str
    #: Publication timestamp in UTC (naive ``datetime``).
    published_utc: datetime | None
    #: Plain-text summary (HTML stripped), possibly empty.
    summary: str = ""
    #: ISO 639-1 language code of the feed.
    language: str = "en"
    #: Disease tags matched from title/summary (see ``DISEASE_KEYWORDS``).
    disease_tags: list[str] = field(default_factory=list)
    #: URL of the feed the item was fetched from.
    feed_url: str = ""

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "title": self.title,
            "url": self.url,
            "published_utc": self.published_utc,
            "summary": self.summary,
            "language": self.language,
            "disease_tags": list(self.disease_tags),
            "feed_url": self.feed_url,
        }
