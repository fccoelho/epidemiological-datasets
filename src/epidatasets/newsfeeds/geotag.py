"""
Gazetteer-based geo-tagging for news items.

Extracts location mentions (countries and major cities) from free text
and resolves them to ``iso3 / lat / lon`` using an embedded gazetteer
built from Natural Earth admin-0 data (public domain) plus a curated
list of major cities. No external NLP dependencies required.

Author: Flávio Codeço Coelho
License: MIT
"""

from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Literal

import pandas as pd

LocationType = Literal["country", "city", "admin1"]


@dataclass(frozen=True)
class GazetteerEntry:
    """A gazetteer location resolvable from text."""

    name: str
    iso3: str
    lat: float
    lon: float
    type: LocationType


@dataclass(frozen=True)
class LocationMatch:
    """A single location mention found in text."""

    entry: GazetteerEntry
    #: Alias exactly as matched (normalized form).
    matched: str
    #: Character span of the match in the normalized text.
    start: int
    end: int


#: Curated extra aliases for country short forms not present (or not
#: matched) in the Natural Earth attribute set.
COUNTRY_ALIAS_OVERRIDES: dict[str, str] = {
    "usa": "USA",
    "u s": "USA",
    "united states": "USA",
    "uk": "GBR",
    "britain": "GBR",
    "great britain": "GBR",
    "uae": "ARE",
    "emirates": "ARE",
    "drc": "COD",
    "dr congo": "COD",
    "democratic republic of the congo": "COD",
    "south korea": "KOR",
    "north korea": "PRK",
    "holland": "NLD",
    "the netherlands": "NLD",
    "burma": "MMR",
    "ivory coast": "CIV",
    "cape verde": "CPV",
    "eswatini": "SWZ",
    "swaziland": "SWZ",
    "czechia": "CZE",
    "turkey": "TUR",
    "macedonia": "MKD",
    "vatican": "VAT",
    "palestine": "PSE",
    "west bank": "PSE",
    "gaza": "PSE",
    "gaza strip": "PSE",
    "taiwan": "TWN",
    "laos": "LAO",
    "syria": "SYR",
    "iran": "IRN",
    "bolivia": "BOL",
    "venezuela": "VEN",
    "tanzania": "TZA",
    "moldova": "MDA",
    "brunei": "BRN",
}

#: Alias fragments never matched even if present in the gazetteer
#: (too generic / false-positive prone).
ALIAS_BLOCKLIST = {"man", "mary", "norfolk", "jersey", "guinea bissau"}


def normalize_text(text: str) -> str:
    """Lowercase, strip accents (NFKD) and collapse whitespace."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("'", " ").replace("\u2019", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _gazetteer_rows() -> list[dict]:
    rows = []
    for fname in (
        "gazetteer_countries.csv",
        "gazetteer_usstates.csv",
        "gazetteer_cities.csv",
    ):
        resource = resources.files("epidatasets.newsfeeds").joinpath(fname)
        with resource.open(newline="", encoding="utf-8") as fh:
            rows.extend(csv.DictReader(fh))
    return rows


@lru_cache(maxsize=1)
def _alias_lookup() -> dict[str, GazetteerEntry]:
    """Build normalized-alias -> entry lookup (longest aliases last)."""
    from dataclasses import replace

    rows = _gazetteer_rows()
    # canonical display name per ISO3 so that all aliases of a country
    # resolve to the same location_name in results
    canonical: dict[str, str] = {}
    for row in rows:
        if row["type"] == "country" and row["iso3"] not in canonical:
            canonical[row["iso3"]] = row["name"]

    lookup: dict[str, GazetteerEntry] = {}

    def _add(alias: str, entry: GazetteerEntry, min_len: int) -> None:
        norm = normalize_text(alias)
        if len(norm) < min_len or norm in ALIAS_BLOCKLIST:
            return
        if entry.type == "country" and entry.iso3 in canonical:
            entry = replace(entry, name=canonical[entry.iso3])
        # countries win over cities on alias collision (e.g. a city
        # named like a country): keep the first (countries load first)
        lookup.setdefault(norm, entry)

    for row in rows:
        entry = GazetteerEntry(
            name=row["name"],
            iso3=row["iso3"],
            lat=float(row["lat"]),
            lon=float(row["lon"]),
            type=row["type"],  # type: ignore[arg-type]
        )
        if entry.type == "country":
            _add(row["name"], entry, min_len=4)
            for alias in (row.get("aliases") or "").split("|"):
                _add(alias, entry, min_len=4)
    for alias, iso3 in COUNTRY_ALIAS_OVERRIDES.items():
        _add(
            alias,
            GazetteerEntry(alias.title(), iso3, 0.0, 0.0, "country"),
            2,
        )

    for row in rows:
        if row["type"] != "admin1":
            continue
        entry = GazetteerEntry(
            name=row["name"],
            iso3=row["iso3"],
            lat=float(row["lat"]),
            lon=float(row["lon"]),
            type="admin1",
        )
        _add(row["name"], entry, min_len=4)
        for alias in (row.get("aliases") or "").split("|"):
            _add(alias, entry, min_len=4)

    for row in rows:
        if row["type"] != "city":
            continue
        entry = GazetteerEntry(
            name=row["name"],
            iso3=row["iso3"],
            lat=float(row["lat"]),
            lon=float(row["lon"]),
            type="city",
        )
        _add(row["name"], entry, min_len=5)
        for alias in (row.get("aliases") or "").split("|"):
            _add(alias, entry, min_len=5)
    return lookup


def geotag_text(text: str) -> list[LocationMatch]:
    """
    Find location mentions in *text* using the embedded gazetteer.

    Matching is accent-insensitive and case-insensitive with word
    boundaries; longer aliases win over shorter overlapping ones
    (e.g. ``"Mexico City"`` over ``"Mexico"``). The uppercase-only
    abbreviation ``"US"`` is additionally recognized (avoiding false
    matches on the pronoun "us").

    Returns:
        List of non-overlapping :class:`LocationMatch` sorted by position.
    """
    if not text:
        return []
    norm = normalize_text(text)
    candidates: list[LocationMatch] = []
    for alias, entry in _alias_lookup().items():
        for m in re.finditer(rf"\b{re.escape(alias)}\b", norm):
            candidates.append(
                LocationMatch(entry, alias, m.start(), m.end())
            )
    # case-sensitive "US" (uppercase only) -> USA, unless already found
    if any(m.entry.iso3 == "USA" and m.entry.type == "country" for m in candidates):
        us_span = None
    else:
        us_matches = list(re.finditer(r"(?<![A-Za-z])US(?![A-Za-z])", text))
        us_span = (
            (us_matches[0].start(), us_matches[0].end())
            if us_matches
            else None
        )

    # longest match wins on overlap
    candidates.sort(key=lambda c: (c.start - c.end, c.start))
    selected: list[LocationMatch] = []
    taken: list[tuple[int, int]] = []
    for cand in candidates:
        if any(cand.start < e and cand.end > s for s, e in taken):
            continue
        selected.append(cand)
        taken.append((cand.start, cand.end))

    if us_span is not None:
        usa = _alias_lookup()["united states"]
        selected.append(LocationMatch(usa, "US", us_span[0], us_span[1]))
        selected.sort(key=lambda c: c.start)
    return selected


def geotag_items(
    items: pd.DataFrame,
    text_cols: tuple[str, ...] = ("title", "summary"),
) -> pd.DataFrame:
    """
    Geo-tag a DataFrame of news items.

    Args:
        items: DataFrame with at least ``title`` (and optionally the
            columns named in *text_cols*, plus ``url``, ``source`` and
            ``published_utc``).
        text_cols: Columns concatenated to form the text to scan.

    Returns:
        DataFrame with one row per (item, mentioned location) and columns
        ``url``, ``source``, ``published_utc``, ``location_name``,
        ``location_type``, ``iso3``, ``lat``, ``lon``. Items without any
        location mention produce no rows.
    """
    records: list[dict] = []
    meta_cols = [
        c
        for c in ("url", "source", "published_utc", "title")
        if c in items.columns
    ]
    for _, row in items.iterrows():
        text = " ".join(
            str(row[c]) for c in text_cols if c in row and pd.notna(row[c])
        )
        for match in geotag_text(text):
            rec = {c: row[c] for c in meta_cols}
            rec.update(
                {
                    "location_name": match.entry.name,
                    "location_type": match.entry.type,
                    "iso3": match.entry.iso3,
                    "lat": match.entry.lat,
                    "lon": match.entry.lon,
                }
            )
            records.append(rec)
    return pd.DataFrame(
        records,
        columns=[
            *meta_cols,
            "location_name",
            "location_type",
            "iso3",
            "lat",
            "lon",
        ],
    )
