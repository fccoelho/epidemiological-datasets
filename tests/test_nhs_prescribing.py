"""Tests for the NHS England prescribing accessor.

Network-free tests mock the OpenPrescribing REST API and the NHSBSA CKAN
portal using the ``responses`` library.  Live tests are gated behind
``@pytest.mark.external_api``.
"""

import os
from pathlib import Path

import pandas as pd
import pytest
import responses

from epidatasets.sources.nhs_prescribing import (
    BNF_CHAPTERS,
    NHSPrescribingAccessor,
    NHSPrescribingAPIError,
    bnf_level,
    bnf_to_flat,
    filter_bnf,
)

FIXTURES = Path(__file__).parent / "fixtures" / "nhs_prescribing"

API = "https://openprescribing.net/api/1.0"
CKAN = "https://opendata.nhsbsa.net"

EPD_202401_URL = "https://example.com/epd/epd_snomed_202401.csv"
EPD_202402_URL = "https://example.com/epd/epd_snomed_202402.csv"


def ckan_payload():
    return {
        "success": True,
        "result": {
            "resources": [
                {"name": "EPD_SNOMED_202401", "url": EPD_202401_URL},
                {"name": "EPD_SNOMED_202402", "url": EPD_202402_URL},
                {"name": "Release guidance", "url": "https://example.com/guide.pdf"},
            ]
        },
    }


SPENDING_ROWS = [
    {
        "row_id": None,
        "row_name": "england",
        "date": "2024-01-01",
        "items": 1_000_000,
        "quantity": 2_000_000,
        "actual_cost": 123456.78,
    },
    {
        "row_id": None,
        "row_name": "england",
        "date": "2024-02-01",
        "items": 900_000,
        "quantity": 1_800_000,
        "actual_cost": 110000.0,
    },
]

CCG_ROWS = [
    {
        "row_id": "15N",
        "row_name": "NHS NORTH EAST LINCOLNSHIRE",
        "date": "2024-01-01",
        "items": 1200,
        "quantity": 3400,
        "actual_cost": 8100.5,
    },
]

PRACTICE_ROWS = [
    {
        "row_id": "L81001",
        "row_name": "ABBEY MEDICAL PRACTICE",
        "date": "2024-01-01",
        "items": 50,
        "quantity": 120,
        "actual_cost": 210.4,
        "ccg": "15N",
        "setting": 4,
    },
]

MEASURE_NATIONAL = {
    "measures": [
        {
            "id": "ktt9_antibiotics",
            "name": "KTT9 Antibiotic stewardship",
            "title": "Antibiotic stewardship",
            "description": "Items prescribed for selected antibiotics.",
            "why_it_matters": "Overuse of antibiotics drives resistance.",
            "numerator_short": "antibiotic items",
            "denominator_short": "patients",
            "low_is_good": True,
            "tags": ["antibiotics"],
            "data": [
                {
                    "date": "2024-01-01",
                    "numerator": 10,
                    "denominator": 100,
                    "calc_value": 0.1,
                    "percentiles": {},
                    "cost_savings": {},
                }
            ],
        }
    ]
}

MEASURE_BY_PRACTICE = [
    {
        "measure": "ktt9_antibiotics",
        "org_type": "practice",
        "org_id": "L81001",
        "org_name": "Abbey Medical Practice",
        "date": "2024-01-01",
        "numerator": 5,
        "denominator": 50,
        "calc_value": 0.1,
        "percentile": 0.5,
    }
]

ORG_LOCATION_PRACTICE = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-0.142, 51.51]},
            "properties": {
                "code": "L81001",
                "name": "Abbey Medical Practice",
                "setting": 4,
            },
        },
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-1.2, 52.4]},
            "properties": {"code": "M85724", "name": "Another Practice", "setting": 4},
        },
    ],
}

ORG_LOCATION_CCG = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-0.12, 51.55]},
            "properties": {
                "code": "15N",
                "name": "NHS North East Lincolnshire",
                "ons_code": "E38000153",
                "org_type": "CCG",
            },
        }
    ],
}


@pytest.fixture
def accessor(tmp_path):
    return NHSPrescribingAccessor(cache_dir=str(tmp_path / "nhs_prescribing"))


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(
        "epidatasets.sources.nhs_prescribing.time.sleep", lambda seconds: None
    )


# ---------------------------------------------------------------------------
# BNF helpers (pure functions)
# ---------------------------------------------------------------------------


class TestBNFHelpers:
    def test_bnf_to_flat_dotted(self):
        assert bnf_to_flat("5") == "05"
        assert bnf_to_flat("5.1") == "0501"
        assert bnf_to_flat("5.1.1") == "050101"
        assert bnf_to_flat("5.1.1.3") == "0501013"

    def test_bnf_to_flat_passthrough(self):
        assert bnf_to_flat("0501013B0AAAAAA") == "0501013B0AAAAAA"
        assert bnf_to_flat(" 0501 ") == "0501"

    def test_bnf_level_dotted(self):
        assert bnf_level("5") == "chapter"
        assert bnf_level("5.1") == "section"
        assert bnf_level("5.1.1") == "paragraph"
        assert bnf_level("5.1.1.3") == "subparagraph"

    def test_bnf_level_flat(self):
        assert bnf_level("05") == "chapter"
        assert bnf_level("0501") == "section"
        assert bnf_level("050101") == "paragraph"
        assert bnf_level("0501013") == "subparagraph"
        assert bnf_level("0501013B0") == "chemical"
        assert bnf_level("0501013B0AA") == "product"
        assert bnf_level("0501013B0AAAAAA") == "presentation"

    def test_filter_bnf_all_levels(self):
        df = pd.DataFrame(
            {
                "BNF_CODE": [
                    "0501013B0AAAAAA",  # amoxicillin (5.1.1.3)
                    "0501012H0AAAAAA",  # flucloxacillin (5.1.1.2)
                    "0501055A0AAAAAA",  # clarithromycin, macrolides (5.1.5)
                    "0101021B0BEADAJ",  # GI compound
                ]
            }
        )
        assert len(filter_bnf(df, "5")) == 3
        assert len(filter_bnf(df, "5.1")) == 3
        assert len(filter_bnf(df, "5.1.1")) == 2
        assert len(filter_bnf(df, "5.1.1.3")) == 1
        assert len(filter_bnf(df, "0501013B0")) == 1
        assert len(filter_bnf(df, "01")) == 1
        assert filter_bnf(df, "9").empty
        empty = pd.DataFrame(columns=["BNF_CODE"])
        assert filter_bnf(empty, "5").empty

    def test_list_bnf_chapters(self, accessor):
        chapters = accessor.list_bnf_chapters()
        assert isinstance(chapters, pd.DataFrame)
        assert len(chapters) == len(BNF_CHAPTERS)
        assert "05" in chapters["chapter_code"].values
        assert "Infections" in chapters["chapter_name"].values


# ---------------------------------------------------------------------------
# Accessor basics
# ---------------------------------------------------------------------------


class TestAccessorBasics:
    def test_initialization(self, accessor):
        assert accessor.source_name == "nhs_prescribing"
        assert "OpenPrescribing" in accessor.source_description
        assert accessor.source_url.startswith("https://openprescribing.net")
        assert accessor.cache_dir.exists()

    def test_list_countries(self, accessor):
        countries = accessor.list_countries()
        assert isinstance(countries, pd.DataFrame)
        assert countries.iloc[0]["country_code"] == "GB-ENG"
        assert countries.iloc[0]["country_name"] == "England"

    def test_normalize_date_param(self):
        assert NHSPrescribingAccessor._normalize_date_param("2024-01") == "2024-01-01"
        assert NHSPrescribingAccessor._normalize_date_param("202401") == "2024-01-01"
        assert NHSPrescribingAccessor._normalize_date_param(None) is None
        with pytest.raises(ValueError, match="YYYY-MM"):
            NHSPrescribingAccessor._normalize_date_param("2024/01")


# ---------------------------------------------------------------------------
# OpenPrescribing API: spending
# ---------------------------------------------------------------------------


class TestSpending:
    @responses.activate
    def test_get_spending(self, accessor):
        responses.add(
            responses.GET,
            f"{API}/spending/",
            json=SPENDING_ROWS,
            status=200,
        )
        df = accessor.get_spending(bnf_code="5.1", use_cache=False)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert set(df.columns) >= {
            "row_id",
            "row_name",
            "date",
            "items",
            "quantity",
            "actual_cost",
        }
        assert pd.api.types.is_datetime64_any_dtype(df["date"])
        assert df.iloc[0]["items"] == 1_000_000

    @responses.activate
    def test_get_spending_by_ccg(self, accessor):
        responses.add(
            responses.GET,
            f"{API}/spending_by_sicbl/",
            json=CCG_ROWS,
            status=200,
        )
        df = accessor.get_spending_by_ccg(
            bnf_code="5.1", ccg_code="15N", year_month="2024-01", use_cache=False
        )
        assert len(df) == 1
        assert df.iloc[0]["row_id"] == "15N"
        assert float(df.iloc[0]["actual_cost"]) == 8100.5

    @responses.activate
    def test_get_spending_by_practice(self, accessor):
        responses.add(
            responses.GET,
            f"{API}/spending_by_practice/",
            json=PRACTICE_ROWS,
            status=200,
        )
        df = accessor.get_spending_by_practice(
            bnf_code="5.1",
            ccg_code="15N",
            year_month="202401",
            use_cache=False,
        )
        assert len(df) == 1
        assert df.iloc[0]["row_id"] == "L81001"
        assert df.iloc[0]["ccg"] == "15N"

    def test_get_spending_by_practice_requires_filter(self, accessor):
        with pytest.raises(ValueError, match="ccg_code, practice_code"):
            accessor.get_spending_by_practice(bnf_code="5.1")


# ---------------------------------------------------------------------------
# OpenPrescribing API: measures
# ---------------------------------------------------------------------------


class TestMeasures:
    @responses.activate
    def test_get_measures_national_flattens_nested_payload(self, accessor):
        responses.add(responses.GET, f"{API}/measure/", json=MEASURE_NATIONAL)
        df = accessor.get_measures(measure="ktt9_antibiotics", use_cache=False)
        assert len(df) == 1
        assert df.iloc[0]["id"] == "ktt9_antibiotics"
        assert df.iloc[0]["numerator"] == 10
        assert df.iloc[0]["calc_value"] == 0.1
        assert "data" not in df.columns

    @responses.activate
    def test_get_measures_by_practice(self, accessor):
        responses.add(
            responses.GET,
            f"{API}/measure_by_practice/",
            json=MEASURE_BY_PRACTICE,
        )
        df = accessor.get_measures(
            measure="ktt9_antibiotics",
            org_type="practice",
            org_code="L81001",
            use_cache=False,
        )
        assert len(df) == 1
        assert df.iloc[0]["org_id"] == "L81001"
        assert df.iloc[0]["percentile"] == 0.5

    @responses.activate
    def test_get_measures_by_ccg_maps_to_sicbl(self, accessor):
        responses.add(
            responses.GET,
            f"{API}/measure_by_sicbl/",
            json=[],
        )
        df = accessor.get_measures(
            measure="ktt9_antibiotics", org_type="ccg", org_code="15N", use_cache=False
        )
        assert df.empty

    @responses.activate
    def test_get_measures_aggregate(self, accessor):
        responses.add(
            responses.GET,
            f"{API}/measure_by_practice/",
            json=[],
        )
        accessor.get_measures(
            measure="ktt9_antibiotics", org_type="practice", aggregate=True
        )
        request = responses.calls[0].request
        assert "aggregate=true" in request.url

    def test_get_measures_validates_org_type(self, accessor):
        with pytest.raises(ValueError, match="org_type"):
            accessor.get_measures(org_type="galaxy")

    def test_get_measures_practice_requires_org(self, accessor):
        with pytest.raises(ValueError, match="org_code"):
            accessor.get_measures(org_type="practice", measure="ktt9")

    @responses.activate
    def test_get_measure_definitions(self, accessor):
        responses.add(responses.GET, f"{API}/measure/", json=MEASURE_NATIONAL)
        defs = accessor.get_measure_definitions(use_cache=False)
        assert len(defs) == 1
        assert defs.iloc[0]["id"] == "ktt9_antibiotics"
        assert defs.iloc[0]["why_it_matters"]


# ---------------------------------------------------------------------------
# OpenPrescribing API: codes and locations
# ---------------------------------------------------------------------------


class TestCodesAndLocations:
    @responses.activate
    def test_search_bnf_codes(self, accessor):
        responses.add(
            responses.GET,
            f"{API}/bnf_code/",
            json=[
                {"type": "BNF section", "id": "5.1", "name": "Antibacterial drugs"},
                {"type": "chemical", "id": "0501013B0", "name": "Amoxicillin"},
            ],
        )
        df = accessor.search_bnf_codes("amoxicillin", use_cache=False)
        assert len(df) == 2
        assert "Amoxicillin" in df["name"].values

    @responses.activate
    def test_search_org_codes(self, accessor):
        responses.add(
            responses.GET,
            f"{API}/org_code/",
            json=[
                {"id": "L81001", "code": "L81001", "name": "Abbey", "type": "practice"}
            ],
        )
        df = accessor.search_org_codes("L81001", org_type="practice", use_cache=False)
        assert len(df) == 1
        assert df.iloc[0]["type"] == "practice"

    @responses.activate
    def test_get_practice_locations(self, accessor):
        responses.add(
            responses.GET,
            f"{API}/org_location/",
            json=ORG_LOCATION_PRACTICE,
        )
        df = accessor.get_practice_locations(ccg_code="15N", use_cache=False)
        assert len(df) == 2
        assert {"code", "name", "setting", "lat", "lon"} <= set(df.columns)
        row = df[df["code"] == "L81001"].iloc[0]
        assert row["lat"] == pytest.approx(51.51)
        assert row["lon"] == pytest.approx(-0.142)

    @responses.activate
    def test_get_ccg_locations(self, accessor):
        responses.add(responses.GET, f"{API}/org_location/", json=ORG_LOCATION_CCG)
        df = accessor.get_ccg_locations(use_cache=False)
        assert len(df) == 1
        assert df.iloc[0]["code"] == "15N"
        assert df.iloc[0]["ons_code"] == "E38000153"
        request = responses.calls[0].request
        assert "org_type=ccg" in request.url
        assert "centroids=true" in request.url

    @responses.activate
    def test_geocode_orgs_direct_match(self, accessor):
        responses.add(
            responses.GET,
            f"{API}/org_location/",
            json=ORG_LOCATION_PRACTICE,
        )
        df = accessor.geocode_orgs("L81001")
        assert len(df) == 1
        assert df.iloc[0]["code"] == "L81001"
        assert pd.notna(df.iloc[0]["lat"])

    @responses.activate
    def test_geocode_orgs_parent_ccg_expansion(self, accessor):
        responses.add(
            responses.GET,
            f"{API}/org_location/",
            json=ORG_LOCATION_PRACTICE,
        )
        df = accessor.geocode_orgs(["15N"])
        # no practice has code 15N -> keep the API's CCG expansion rows
        assert len(df) == 2


# ---------------------------------------------------------------------------
# EPD bulk CSV
# ---------------------------------------------------------------------------


class TestEPD:
    @responses.activate
    def test_list_epd_months(self, accessor):
        responses.add(
            responses.GET,
            f"{CKAN}/api/3/action/package_show",
            json=ckan_payload(),
        )
        months = accessor.list_epd_months(use_cache=False)
        assert months == ["202401", "202402"]

    @responses.activate
    def test_get_epd_month(self, accessor):
        responses.add(
            responses.GET,
            f"{CKAN}/api/3/action/package_show",
            json=ckan_payload(),
        )
        responses.add(
            responses.GET,
            EPD_202401_URL,
            body=(FIXTURES / "epd_sample_202401.csv").read_bytes(),
            status=200,
        )
        df = accessor.get_epd_month(2024, 1, use_cache=False)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 5
        # numeric coercion of trailing-dot strings
        assert pd.api.types.is_numeric_dtype(df["ITEMS"])
        assert df["ITEMS"].sum() == 5
        assert df["ACTUAL_COST"].sum() == pytest.approx(150.30, rel=1e-6)
        # SNOMED codes survive
        assert "SNOMED_CODE" in df.columns

    @responses.activate
    def test_get_epd_month_bnf_filter(self, accessor):
        responses.add(
            responses.GET,
            f"{CKAN}/api/3/action/package_show",
            json=ckan_payload(),
        )
        responses.add(
            responses.GET,
            EPD_202401_URL,
            body=(FIXTURES / "epd_sample_202401.csv").read_bytes(),
        )
        df = accessor.get_epd_month(2024, 1, bnf_section="5.1", use_cache=False)
        assert len(df) == 3
        assert df["BNF_CODE"].str.startswith("0501").all()
        amox = accessor.get_epd_month(2024, 1, bnf_section="0501013B0", use_cache=False)
        assert len(amox) == 2

    @responses.activate
    def test_get_epd_month_chunked_lazy(self, accessor):
        responses.add(
            responses.GET,
            f"{CKAN}/api/3/action/package_show",
            json=ckan_payload(),
        )
        responses.add(
            responses.GET,
            EPD_202401_URL,
            body=(FIXTURES / "epd_sample_202401.csv").read_bytes(),
        )
        chunks = accessor.get_epd_month(2024, 1, bnf_section="5.1", chunksize=2)
        collected = list(chunks)
        assert all(len(c) <= 2 for c in collected)
        assert sum(len(c) for c in collected) == 3

    @responses.activate
    def test_get_epd_month_unavailable_month(self, accessor):
        responses.add(
            responses.GET,
            f"{CKAN}/api/3/action/package_show",
            json=ckan_payload(),
        )
        with pytest.raises(ValueError, match="No EPD file"):
            accessor.get_epd_month(2019, 1, use_cache=False)

    @responses.activate
    def test_get_epd_timeseries(self, accessor):
        responses.add(
            responses.GET,
            f"{CKAN}/api/3/action/package_show",
            json=ckan_payload(),
        )
        responses.add(
            responses.GET,
            EPD_202401_URL,
            body=(FIXTURES / "epd_sample_202401.csv").read_bytes(),
        )
        responses.add(
            responses.GET,
            EPD_202402_URL,
            body=(FIXTURES / "epd_sample_202402.csv").read_bytes(),
        )
        ts = accessor.get_epd_timeseries(
            "0501013B0", start_year_month="2024-01", end_year_month="2024-02"
        )
        assert list(ts["YEAR_MONTH"]) == ["202401", "202402"]
        assert list(ts["ITEMS"]) == [2, 3]
        assert ts["ACTUAL_COST"].iloc[0] == pytest.approx(100.30, rel=1e-6)

    def test_get_epd_timeseries_validates_range(self, accessor):
        with pytest.raises(ValueError, match="Invalid range"):
            accessor.get_epd_timeseries("0501013B0", "2024-05", "2024-01")


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------


class TestCaching:
    @responses.activate
    def test_api_response_cached(self, accessor):
        responses.add(responses.GET, f"{API}/spending/", json=SPENDING_ROWS)
        first = accessor.get_spending(bnf_code="5.1")
        second = accessor.get_spending(bnf_code="5.1")
        assert len(responses.calls) == 1
        # compare stable numeric columns (None/NaN round-trip differs in type)
        pd.testing.assert_frame_equal(
            first[["items", "quantity"]], second[["items", "quantity"]]
        )

    @responses.activate
    def test_use_cache_false_bypasses_cache(self, accessor):
        responses.add(responses.GET, f"{API}/spending/", json=SPENDING_ROWS)
        accessor.get_spending(bnf_code="5.1", use_cache=False)
        accessor.get_spending(bnf_code="5.1", use_cache=False)
        assert len(responses.calls) == 2

    @responses.activate
    def test_expired_ttl_refetches(self, tmp_path):
        import os

        accessor = NHSPrescribingAccessor(
            cache_dir=str(tmp_path / "expired"), cache_ttl_days=0
        )
        responses.add(responses.GET, f"{API}/spending/", json=SPENDING_ROWS)
        accessor.get_spending(bnf_code="5.1")
        # age the cache file beyond the (zero) TTL
        for cache_file in tmp_path.joinpath("expired").iterdir():
            os.utime(cache_file, (0, 0))
        accessor.get_spending(bnf_code="5.1")
        assert len(responses.calls) == 2

    @responses.activate
    def test_epd_download_cached(self, accessor):
        responses.add(
            responses.GET,
            f"{CKAN}/api/3/action/package_show",
            json=ckan_payload(),
        )
        responses.add(
            responses.GET,
            EPD_202401_URL,
            body=(FIXTURES / "epd_sample_202401.csv").read_bytes(),
        )
        accessor.get_epd_month(2024, 1)
        accessor.get_epd_month(2024, 1)
        download_calls = [
            c for c in responses.calls if c.request.url.startswith(EPD_202401_URL)
        ]
        assert len(download_calls) == 1

    @responses.activate
    def test_corrupted_cache_refetched(self, accessor):
        responses.add(responses.GET, f"{API}/spending/", json=SPENDING_ROWS)
        accessor.get_spending(bnf_code="5.1")
        # corrupt every cache file
        for cache_file in accessor.cache_dir.iterdir():
            cache_file.write_text("not,a,valid,csv{{{")
        df = accessor.get_spending(bnf_code="5.1")
        assert len(df) == 2
        assert len(responses.calls) == 2


# ---------------------------------------------------------------------------
# Error handling and retries
# ---------------------------------------------------------------------------


class TestErrors:
    @responses.activate
    def test_network_error_wrapped(self, accessor, no_sleep):
        responses.add(
            responses.GET,
            f"{API}/spending/",
            body=responses.ConnectionError("boom"),
        )
        with pytest.raises(NHSPrescribingAPIError, match="failed after 3 attempts"):
            accessor.get_spending(bnf_code="5.1", use_cache=False)

    @responses.activate
    def test_http_error_wrapped(self, accessor):
        responses.add(responses.GET, f"{API}/spending/", json={}, status=404)
        with pytest.raises(NHSPrescribingAPIError, match="404"):
            accessor.get_spending(bnf_code="5.1", use_cache=False)

    @responses.activate
    def test_retries_on_server_error(self, accessor, no_sleep):
        responses.add(responses.GET, f"{API}/spending/", status=500)
        responses.add(responses.GET, f"{API}/spending/", json=SPENDING_ROWS)
        df = accessor.get_spending(bnf_code="5.1", use_cache=False)
        assert len(df) == 2
        assert len(responses.calls) == 2

    @responses.activate
    def test_download_failure_wrapped(self, accessor):
        responses.add(
            responses.GET,
            f"{CKAN}/api/3/action/package_show",
            json=ckan_payload(),
        )
        responses.add(
            responses.GET,
            EPD_202401_URL,
            body=responses.ConnectionError("boom"),
        )
        with pytest.raises(NHSPrescribingAPIError, match="Failed to download"):
            accessor.get_epd_month(2024, 1, use_cache=False)
        # partial files must not linger
        assert not list(accessor.cache_dir.glob("*.part"))

    @responses.activate
    def test_bad_ckan_payload_wrapped(self, accessor):
        responses.add(responses.GET, f"{CKAN}/api/3/action/package_show", json={})
        with pytest.raises(NHSPrescribingAPIError, match="Unexpected CKAN"):
            accessor.list_epd_months(use_cache=False)


# ---------------------------------------------------------------------------
# Live integration smoke tests (network; deselected in CI)
# ---------------------------------------------------------------------------


@pytest.mark.external_api
@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("SKIP_EXTERNAL_TESTS", "false").lower() == "true",
    reason="External API tests disabled",
)
class TestLiveSmoke:
    """Smoke tests against the live OpenPrescribing API and NHSBSA portal."""

    def _skip_if_unavailable(self, func):
        """Skip gracefully when bot protection blocks non-browser clients."""
        try:
            return func()
        except NHSPrescribingAPIError as exc:
            if "403" in str(exc) or "challenge" in str(exc).lower():
                pytest.skip(f"OpenPrescribing API unreachable: {exc}")
            raise

    def test_live_spending(self):
        accessor = NHSPrescribingAccessor()
        df = self._skip_if_unavailable(
            lambda: accessor.get_spending(bnf_code="5.1", use_cache=False)
        )
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert {"date", "items", "quantity", "actual_cost"} <= set(df.columns)

    def test_live_ccg_spending(self):
        accessor = NHSPrescribingAccessor()
        df = self._skip_if_unavailable(
            lambda: accessor.get_spending_by_ccg(
                bnf_code="5.1", year_month="2024-01", use_cache=False
            )
        )
        assert not df.empty
        assert df["row_id"].notna().all()

    def test_live_epd_months(self):
        accessor = NHSPrescribingAccessor()
        months = accessor.list_epd_months(use_cache=False)
        assert "202011" in months

    def test_live_measure_definitions(self):
        accessor = NHSPrescribingAccessor()
        defs = self._skip_if_unavailable(
            lambda: accessor.get_measure_definitions(use_cache=False)
        )
        assert not defs.empty
        assert "ktt9_antibiotics" in defs["id"].values or len(defs) > 10
