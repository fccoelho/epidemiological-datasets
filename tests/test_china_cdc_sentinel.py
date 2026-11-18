"""Tests for the China CDC weekly sentinel respiratory surveillance.

The HTML fixtures are real pages captured from chinacdc.cn:

- ``sentinel_listing.html`` — the listing page (weeks 30–41/2026)
- ``sentinel_2026_W41.html`` — bulletin with the ILI% indicator
- ``sentinel_2025_W01.html`` — older bulletin layout without ILI%

Network calls are mocked with ``responses``; live tests are gated behind
``@pytest.mark.external_api``.
"""

from bs4 import BeautifulSoup
from pathlib import Path

import pandas as pd
import pytest
import responses

from epidatasets.sources.china_cdc import (
    RESPIRATORY_PATHOGEN_MAP,
    ChinaCDCAccessor,
)

FIXTURES = Path(__file__).parent / "fixtures" / "china_cdc"
LISTING = (FIXTURES / "sentinel_listing.html").read_text(encoding="utf-8")
REPORT_2026_W41 = (FIXTURES / "sentinel_2026_W41.html").read_text(encoding="utf-8")
REPORT_2025_W01 = (FIXTURES / "sentinel_2025_W01.html").read_text(encoding="utf-8")

#: Second listing page (empty) so the pagination walk of
#: ``_scrape_chinacdc_listing`` terminates without extra network calls.
LISTING_PAGE_2 = f"{ChinaCDCAccessor.SENTINEL_MIRROR_URL}index_1.html"
ARTICLE_W41_URL = (
    "https://www.chinacdc.cn/jksj/jksj04_14275/202610/t20261015_1842282.html"
)


def _mock_listing():
    """Mock the listing first page and an empty second page."""
    responses.add(
        responses.GET, ChinaCDCAccessor.SENTINEL_MIRROR_URL, body=LISTING
    )
    responses.add(responses.GET, LISTING_PAGE_2, body="<html></html>")


def _mock_w41_article():
    responses.add(responses.GET, ARTICLE_W41_URL, body=REPORT_2026_W41)


@pytest.fixture
def cdc(tmp_path):
    return ChinaCDCAccessor(cache_dir=str(tmp_path / "china_cdc"))


class TestSentinelParsing:
    def test_parses_recent_bulletin(self, cdc):
        report = ChinaCDCAccessor._parse_sentinel_article(
            BeautifulSoup(REPORT_2026_W41, "html.parser")
        )

        assert report["year"] == 2026
        assert report["week"] == 41
        assert report["publish_date"] == "2026-10-15"
        assert report["ili_percent_national"] == 3.8
        assert report["ili_percent_south"] == 4.6
        assert report["ili_percent_north"] == 3.0

        table = report["positivity"]
        assert set(table.columns) == {
            "pathogen_cn",
            "pathogen",
            "ili_positivity_pct",
            "ili_change_vs_previous_week",
            "sari_positivity_pct",
            "sari_change_vs_previous_week",
        }
        assert len(table) == 11  # one row per pathogen, syndromes wide

        influenza = table[
            table["pathogen_cn"] == "流感病毒"
        ].iloc[0]
        assert influenza["pathogen"] == "Influenza"
        assert influenza["ili_positivity_pct"] == 13.6
        assert influenza["ili_change_vs_previous_week"] == 2.4

        top_region = report["top_pathogens_by_region"]
        assert set(top_region.columns) == {
            "region",
            "syndrome",
            "rank",
            "pathogen_cn",
            "pathogen",
        }
        assert set(top_region["region"]) == {"south", "north"}
        assert not report["top_pathogens_by_age"].empty

    def test_parses_older_bulletin_without_ili_indicator(self, cdc):
        report = ChinaCDCAccessor._parse_sentinel_article(
            BeautifulSoup(REPORT_2025_W01, "html.parser")
        )

        assert report["year"] == 2025
        assert report["week"] == 1
        assert report["ili_percent_national"] is None
        assert report["ili_percent_south"] is None
        assert report["ili_percent_north"] is None
        table = report["positivity"]
        assert len(table) == 11
        assert (
            table[table["pathogen"] == "Mycoplasma pneumoniae"].shape[0] == 1
        )

    def test_pathogen_names_are_english(self, cdc):
        table = ChinaCDCAccessor._parse_sentinel_article(
            BeautifulSoup(REPORT_2026_W41, "html.parser")
        )["positivity"]
        assert set(table["pathogen"]) == set(RESPIRATORY_PATHOGEN_MAP.values())

    def test_zero_change_is_parsed(self, cdc):
        table = ChinaCDCAccessor._parse_sentinel_article(
            BeautifulSoup(REPORT_2026_W41, "html.parser")
        )["positivity"]
        adenovirus = table[table["pathogen_cn"] == "腺病毒"].iloc[0]
        assert adenovirus["ili_change_vs_previous_week"] == 0.0


class TestSentinelListing:
    @responses.activate
    def test_listing_returns_year_and_week(self, cdc):
        _mock_listing()
        listing = cdc.list_respiratory_sentinel_reports(max_pages=1)

        assert list(listing.columns) == [
            "year",
            "week",
            "title",
            "publish_date",
            "url",
        ]
        # sorted by year/week: the newest report is last
        newest = listing.iloc[-1]
        assert (newest["year"], newest["week"]) == (2026, 41)
        assert newest["publish_date"] == "2026-10-15"
        assert newest["url"].endswith("t20261015_1842282.html")

    @responses.activate
    def test_listing_year_filter(self, cdc):
        _mock_listing()
        listing = cdc.list_respiratory_sentinel_reports(year=2025)
        assert listing.empty

    @responses.activate
    def test_listing_year_filter_keeps_entries(self, cdc):
        _mock_listing()
        listing = cdc.list_respiratory_sentinel_reports(year=2026)
        assert set(listing["year"]) == {2026}
        assert listing["week"].tolist() == list(range(30, 42))


class TestSentinelFetching:
    @responses.activate
    def test_get_report_uses_listing_and_caches(self, cdc):
        _mock_listing()
        _mock_w41_article()

        report = cdc.get_respiratory_sentinel_report(2026, 41)
        assert report["week"] == 41
        assert report["url"] == ARTICLE_W41_URL
        assert len(report["positivity"]) == 11

        # the article is served from the on-disk cache on the second call
        # (only the listing is re-scraped)
        cached = cdc.get_respiratory_sentinel_report(2026, 41)
        assert cached["ili_percent_national"] == 3.8
        article_calls = [
            c for c in responses.calls if c.request.url == ARTICLE_W41_URL
        ]
        assert len(article_calls) == 1

    @responses.activate
    def test_unknown_week_raises(self, cdc):
        _mock_listing()
        with pytest.raises(ValueError, match="No respiratory sentinel"):
            cdc.get_respiratory_sentinel_report(2019, 1)

    @responses.activate
    def test_surveillance_long_frame(self, cdc):
        _mock_listing()
        _mock_w41_article()

        frame = cdc.get_respiratory_sentinel_surveillance(weeks=1)

        assert list(frame.columns) == [
            "year",
            "week",
            "publish_date",
            "syndrome",
            "pathogen",
            "positivity_pct",
            "change_vs_previous_week",
        ]
        assert len(frame) == 22
        assert frame["year"].iloc[0] == 2026
        assert isinstance(frame["positivity_pct"].iloc[0], float)
        assert set(frame["syndrome"]) == {
            "ili_consultation",
            "sari_hospitalised",
        }

    @responses.activate
    def test_ili_series(self, cdc):
        _mock_listing()
        _mock_w41_article()

        ili = cdc.get_respiratory_sentinel_ili(weeks=1)

        assert list(ili.columns) == [
            "year",
            "week",
            "publish_date",
            "ili_percent_national",
            "ili_percent_south",
            "ili_percent_north",
        ]
        assert ili.iloc[0]["ili_percent_national"] == 3.8
        assert ili.iloc[0]["ili_percent_north"] == 3.0


@pytest.mark.external_api
def test_live_sentinel_listing():
    accessor = ChinaCDCAccessor()
    listing = accessor.list_respiratory_sentinel_reports(max_pages=1)
    assert not listing.empty
    assert pd.api.types.is_integer_dtype(listing["week"])


@pytest.mark.external_api
def test_live_sentinel_report():
    accessor = ChinaCDCAccessor()
    report = accessor.get_respiratory_sentinel_report(2026, 41)
    assert len(report["positivity"]) == 11
