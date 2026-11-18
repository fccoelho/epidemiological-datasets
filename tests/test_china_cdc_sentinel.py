"""Tests for the China CDC weekly sentinel respiratory surveillance.

The HTML fixtures are real pages captured from chinacdc.cn:

- ``sentinel_listing.html`` — the listing page (week 41/2026 on top)
- ``sentinel_2026_W41.html`` — bulletin with the ILI% indicator
- ``sentinel_2025_W01.html`` — older bulletin layout without ILI%

Network calls are mocked with ``responses``; live tests are gated behind
``@pytest.mark.external_api``.
"""

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


@pytest.fixture
def cdc(tmp_path):
    return ChinaCDCAccessor(cache_dir=str(tmp_path / "china_cdc"))


class TestSentinelParsing:
    def test_parses_recent_bulletin(self, cdc):
        report = cdc.parse_respiratory_sentinel_report(REPORT_2026_W41)

        assert report["year"] == 2026
        assert report["week"] == 41
        assert report["published_date"] == "2026-10-15"
        assert report["ili_percent"] == {
            "national": 3.8,
            "south": 4.6,
            "north": 3.0,
        }

        table = report["pathogen_positivity"]
        assert set(table.columns) == {
            "syndrome",
            "pathogen",
            "pathogen_cn",
            "positivity_pct",
            "change_vs_previous_week",
        }
        assert len(table) == 22  # 11 pathogens x 2 syndromes
        assert set(table["syndrome"]) == {"ili_consultation", "sari_hospitalised"}

        influenza = table[
            (table["pathogen"] == "Influenza")
            & (table["syndrome"] == "ili_consultation")
        ].iloc[0]
        assert influenza["positivity_pct"] == 13.6
        assert influenza["change_vs_previous_week"] == 2.4
        assert influenza["pathogen_cn"] == "流感病毒"

    def test_parses_older_bulletin_without_ili_indicator(self, cdc):
        report = cdc.parse_respiratory_sentinel_report(REPORT_2025_W01)

        assert report["year"] == 2025
        assert report["week"] == 1
        assert report["ili_percent"] == {
            "national": None,
            "south": None,
            "north": None,
        }
        table = report["pathogen_positivity"]
        assert len(table) == 22
        assert (
            table[table["pathogen"] == "Mycoplasma pneumoniae"].shape[0] == 2
        )

    def test_pathogen_names_are_english(self, cdc):
        table = cdc.parse_respiratory_sentinel_report(REPORT_2026_W41)[
            "pathogen_positivity"
        ]
        assert set(table["pathogen"]) == set(RESPIRATORY_PATHOGEN_MAP.values())

    def test_zero_change_is_parsed(self, cdc):
        table = cdc.parse_respiratory_sentinel_report(REPORT_2026_W41)[
            "pathogen_positivity"
        ]
        adenovirus = table[
            (table["pathogen_cn"] == "腺病毒")
            & (table["syndrome"] == "ili_consultation")
        ].iloc[0]
        assert adenovirus["change_vs_previous_week"] == 0.0


class TestSentinelListing:
    @responses.activate
    def test_listing_returns_year_and_week(self, cdc):
        responses.add(
            responses.GET, cdc.RESPIRATORY_SENTINEL_URL, body=LISTING
        )
        listing = cdc.list_respiratory_sentinel_reports(pages=1)

        assert list(listing.columns) == [
            "year",
            "week",
            "title",
            "published_date",
            "url",
        ]
        assert (listing.iloc[0]["year"], listing.iloc[0]["week"]) == (2026, 41)
        assert listing.iloc[0]["published_date"] == "2026-10-15"
        assert listing["url"].iloc[0].endswith("t20261015_1842282.html")

    @responses.activate
    def test_listing_year_filter(self, cdc):
        responses.add(
            responses.GET, cdc.RESPIRATORY_SENTINEL_URL, body=LISTING
        )
        listing = cdc.list_respiratory_sentinel_reports(pages=1, year=2025)
        assert listing.empty


class TestSentinelFetching:
    @responses.activate
    def test_get_report_uses_listing_and_caches(self, cdc):
        responses.add(
            responses.GET, cdc.RESPIRATORY_SENTINEL_URL, body=LISTING
        )
        url = (
            "https://www.chinacdc.cn/jksj/jksj04_14275/"
            "202610/t20261015_1842282.html"
        )
        responses.add(responses.GET, url, body=REPORT_2026_W41)

        report = cdc.get_respiratory_sentinel_report(2026, 41)
        assert report["week"] == 41
        assert len(report["pathogen_positivity"]) == 22

        # second call is fully served from the on-disk cache
        cached = cdc.get_respiratory_sentinel_report(2026, 41)
        assert cached["ili_percent"]["national"] == 3.8
        assert len(responses.calls) == 2

    @responses.activate
    def test_unknown_week_raises(self, cdc):
        responses.add(
            responses.GET, cdc.RESPIRATORY_SENTINEL_URL, body=LISTING
        )
        with pytest.raises(ValueError, match="No sentinel report"):
            cdc.get_respiratory_sentinel_report(2019, 1)

    @responses.activate
    def test_surveillance_long_frame(self, cdc):
        responses.add(
            responses.GET, cdc.RESPIRATORY_SENTINEL_URL, body=LISTING
        )
        url = (
            "https://www.chinacdc.cn/jksj/jksj04_14275/"
            "202610/t20261015_1842282.html"
        )
        responses.add(responses.GET, url, body=REPORT_2026_W41)

        frame = cdc.get_respiratory_sentinel_surveillance(weeks=1)

        assert list(frame.columns) == [
            "year",
            "week",
            "published_date",
            "syndrome",
            "pathogen",
            "pathogen_cn",
            "positivity_pct",
            "change_vs_previous_week",
        ]
        assert len(frame) == 22
        assert frame["year"].iloc[0] == 2026
        assert isinstance(frame["positivity_pct"].iloc[0], float)

    @responses.activate
    def test_ili_series(self, cdc):
        responses.add(
            responses.GET, cdc.RESPIRATORY_SENTINEL_URL, body=LISTING
        )
        url = (
            "https://www.chinacdc.cn/jksj/jksj04_14275/"
            "202610/t20261015_1842282.html"
        )
        responses.add(responses.GET, url, body=REPORT_2026_W41)

        ili = cdc.get_respiratory_sentinel_ili(weeks=1)

        assert list(ili.columns) == [
            "year",
            "week",
            "published_date",
            "ili_percent_national",
            "ili_percent_south",
            "ili_percent_north",
        ]
        assert ili.iloc[0]["ili_percent_national"] == 3.8
        assert ili.iloc[0]["ili_percent_north"] == 3.0


@pytest.mark.external_api
def test_live_sentinel_listing():
    accessor = ChinaCDCAccessor()
    listing = accessor.list_respiratory_sentinel_reports(pages=1)
    assert not listing.empty
    assert pd.api.types.is_integer_dtype(listing["week"])


@pytest.mark.external_api
def test_live_sentinel_report():
    accessor = ChinaCDCAccessor()
    report = accessor.get_respiratory_sentinel_report(2026, 41)
    assert len(report["pathogen_positivity"]) == 22
