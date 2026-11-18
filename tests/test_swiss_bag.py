"""Tests for the Swiss BAG Infectious Diseases Dashboard (IDD) accessor.

Network-free tests mock the BAG IDD REST API with the ``responses``
library.  Live tests are gated behind ``@pytest.mark.external_api``.
"""

import json

import pandas as pd
import pytest
import responses

from epidatasets.sources.swiss_bag import (
    API_ROOT,
    SwissBAGAccessor,
    SwissBAGAPIError,
    parse_temporal,
)

VERSION_URL = f"{API_ROOT}/version"
DATA_VERSION_URL = f"{API_ROOT}/data/version"
SETS_URL = f"{API_ROOT}/data/sets"
DENGUE_DETAILS_URL = f"{API_ROOT}/data/dengueFever/cases/value/month/details"
DENGUE_QUERY_URL = f"{API_ROOT}/data/dengueFever/cases/value/month"
HEP_A_EXPORT_URL = f"{API_ROOT}/export/20261014/HEPATITIS_A_oblig/csv"

SETS = [
    "dengueFever/cases/value/month",
    "dengueFever/cases/value/year",
    "dengueFever/cases/incValue/month",
    "influenza-like_illness/consultations/incValue/week",
    "covid19/cases/incValue/iso_week",
]

DENGUE_DETAILS = {
    "identifier": "dengueFever/cases/value/month",
    "source": "mandatory_reporting_system",
    "sourceDate": "2026-10-06",
    "version": "20261007",
    "properties": {
        "CHFL": {"allValue": "all", "possibleValues": ["CHFL", "all"]},
        "type": {"allValue": "all", "possibleValues": ["all"]},
    },
    "availableSeriesConfigurations": [
        {"CHFL": "CHFL", "georegion": "CHFL", "type": "all"}
    ],
}

DENGUE_PAYLOAD = {
    "source": "mandatory_reporting_system",
    "sourceDate": "2026-10-06",
    "version": "20261007",
    "values": [
        {"x": 202607, "y": 22, "properties": {"trend": "stagnant"}},
        {"x": 202608, "y": 14, "properties": {"trend": "falling"}},
    ],
}

COVID_DETAILS = {
    "identifier": "covid19/cases/incValue/iso_week",
    "source": "mandatory_reporting_system",
    "sourceDate": "2026-10-13",
    "version": "20261014",
    "properties": {},
    "availableSeriesConfigurations": [
        {"canton": "AG", "georegion": "canton", "sex": "all"},
        {"canton": "ZH", "georegion": "canton", "sex": "all"},
    ],
}

CSV_EXPORT = (
    "valueCategory,temporal,temporal_type,georegion,value,pop,incValue\n"
    "cases,2013-M01,month,CHFL,3,8176760,0.04\n"
    "cases,2013-M02,month,CHFL,NA,8176760,NA\n"
)


@pytest.fixture
def bag(tmp_path):
    return SwissBAGAccessor(cache_dir=tmp_path / "swiss_bag")


class TestCatalogue:
    def test_list_countries(self, bag):
        countries = bag.list_countries()
        assert list(countries["country_code"]) == ["CH", "LI"]

    @responses.activate
    def test_list_versions(self, bag):
        responses.add(
            responses.GET,
            VERSION_URL,
            json=[{"name": "20261014"}, {"name": "20261007"}],
        )
        versions = bag.list_versions()
        assert list(versions["version"]) == ["20261014", "20261007"]
        assert versions["date"].iloc[0] == pd.Timestamp("2026-10-14")

    @responses.activate
    def test_list_versions_limit(self, bag):
        responses.add(
            responses.GET,
            VERSION_URL,
            json=[{"name": "20261014"}, {"name": "20261007"}],
        )
        assert len(bag.list_versions(limit=1)) == 1

    @responses.activate
    def test_current_version(self, bag):
        responses.add(responses.GET, DATA_VERSION_URL, json={"name": "20261014"})
        assert bag.current_version() == "20261014"

    @responses.activate
    def test_list_sets(self, bag):
        responses.add(responses.GET, SETS_URL, json=SETS)
        sets = bag.list_sets()
        assert len(sets) == len(SETS)
        assert set(sets.columns) == {
            "topic",
            "chapter",
            "aggregation",
            "temporality",
            "set_id",
        }

        dengue = bag.list_sets(topic="dengueFever")
        assert len(dengue) == 3
        assert set(dengue["temporality"]) == {"month", "year"}

    @responses.activate
    def test_list_topics(self, bag):
        responses.add(responses.GET, SETS_URL, json=SETS)
        topics = bag.list_topics()
        assert "dengueFever" in set(topics["topic"])
        dengue = topics.set_index("topic").loc["dengueFever"]
        assert dengue["n_sets"] == 3

    @responses.activate
    def test_list_export_files(self, bag):
        responses.add(responses.GET, DATA_VERSION_URL, json={"name": "20261014"})
        responses.add(
            responses.GET,
            f"{API_ROOT}/export/20261014/files",
            json=["HEPATITIS_A_oblig", "INFLUENZA_sentinella"],
        )
        files = bag.list_export_files()
        assert files == ["HEPATITIS_A_oblig", "INFLUENZA_sentinella"]

    @responses.activate
    def test_get_set_details(self, bag):
        responses.add(responses.GET, DENGUE_DETAILS_URL, json=DENGUE_DETAILS)
        details = bag.get_set_details("dengueFever", "cases", "value", "month")
        assert details["version"] == "20261007"
        assert details["availableSeriesConfigurations"][0]["CHFL"] == "CHFL"


class TestSeriesQueries:
    @responses.activate
    def test_single_series_uses_first_configuration(self, bag):
        responses.add(responses.GET, DENGUE_DETAILS_URL, json=DENGUE_DETAILS)
        responses.add(responses.POST, DENGUE_QUERY_URL, json=DENGUE_PAYLOAD)

        frame = bag.get_series("dengueFever", "cases", "value", "month")

        assert list(frame["temporal"]) == ["2026-07", "2026-08"]
        assert list(frame["value"]) == [22, 14]
        assert frame["trend"].tolist() == ["stagnant", "falling"]
        assert frame.attrs["version"] == "20261007"
        assert frame.attrs["set_id"] == "dengueFever/cases/value/month"

        sent = json.loads(responses.calls[1].request.body)
        assert sent == {"CHFL": "CHFL", "georegion": "CHFL", "type": "all"}

    @responses.activate
    def test_explicit_filters_skip_details(self, bag):
        responses.add(responses.POST, DENGUE_QUERY_URL, json=DENGUE_PAYLOAD)

        frame = bag.get_series(
            "dengueFever",
            "cases",
            "value",
            "month",
            filters={"CHFL": "CHFL", "type": "all"},
        )

        assert len(frame) == 2
        assert frame["type"].iloc[0] == "all"
        assert len(responses.calls) == 1

    @responses.activate
    def test_all_series_stacks_configurations(self, bag):
        responses.add(
            responses.GET,
            f"{API_ROOT}/data/covid19/cases/incValue/iso_week/details",
            json=COVID_DETAILS,
        )
        responses.add(
            responses.POST,
            f"{API_ROOT}/data/covid19/cases/incValue/iso_week",
            json={
                "source": "mandatory_reporting_system",
                "sourceDate": "2026-10-13",
                "version": "20261014",
                "values": [{"x": 202641, "y": 1.2, "properties": {}}],
            },
        )

        frame = bag.get_series(
            "covid19", "cases", "incValue", "iso_week", all_series=True
        )

        assert len(frame) == 2
        assert set(frame["canton"]) == {"AG", "ZH"}
        assert frame["temporal"].iloc[0] == "2026-W41"

    @responses.activate
    def test_all_series_respects_max_series(self, bag):
        responses.add(
            responses.GET,
            f"{API_ROOT}/data/covid19/cases/incValue/iso_week/details",
            json=COVID_DETAILS,
        )
        with pytest.raises(ValueError, match="exposes 2 series"):
            bag.get_series(
                "covid19",
                "cases",
                "incValue",
                "iso_week",
                all_series=True,
                max_series=1,
            )

    @responses.activate
    def test_group_by_flattens_dict_response(self, bag):
        responses.add(
            responses.POST,
            f"{API_ROOT}/data/measles/cases/value/month",
            json={
                "source": "mandatory_reporting_system",
                "version": "20261007",
                "values": {"CHFL": DENGUE_PAYLOAD["values"]},
            },
        )
        frame = bag.get_series(
            "measles",
            "cases",
            "value",
            "month",
            filters={"CHFL": "CHFL"},
            group_by="CHFL",
        )
        assert set(frame["CHFL"]) == {"CHFL"}
        assert len(frame) == 2

    @responses.activate
    def test_missing_series_raises(self, bag):
        responses.add(responses.POST, DENGUE_QUERY_URL, status=404)
        with pytest.raises(SwissBAGAPIError, match="not found"):
            bag.get_series(
                "dengueFever",
                "cases",
                "value",
                "month",
                filters={"CHFL": "CHFL"},
            )

    @responses.activate
    def test_get_disease_data_resolves_chapter(self, bag):
        responses.add(responses.GET, SETS_URL, json=SETS)
        responses.add(responses.GET, DENGUE_DETAILS_URL, json=DENGUE_DETAILS)
        responses.add(responses.POST, DENGUE_QUERY_URL, json=DENGUE_PAYLOAD)

        frame = bag.get_disease_data("dengueFever")
        assert len(frame) == 2

    @responses.activate
    def test_get_disease_data_unknown_topic(self, bag):
        responses.add(responses.GET, SETS_URL, json=SETS)
        with pytest.raises(SwissBAGAPIError, match="No set found"):
            bag.get_disease_data("nonexistent")


class TestBulkExport:
    @responses.activate
    def test_download_export_and_cache(self, bag):
        responses.add(responses.GET, DATA_VERSION_URL, json={"name": "20261014"})
        responses.add(responses.GET, HEP_A_EXPORT_URL, body=CSV_EXPORT)

        frame = bag.download_export("HEPATITIS_A_oblig")

        assert frame.shape[0] == 2
        assert frame["value"].iloc[0] == 3
        assert pd.isna(frame["value"].iloc[1])
        assert frame["temporal"].dtype == object
        assert frame.attrs["version"] == "20261014"

        cached = bag.download_export("HEPATITIS_A_oblig")
        assert len(responses.calls) == 3  # 2 version lookups + 1 download
        assert cached.shape == frame.shape

    @responses.activate
    def test_download_export_rejects_bad_format(self, bag):
        with pytest.raises(ValueError, match="format must be one of"):
            bag.download_export("HEPATITIS_A_oblig", format="xlsx")

    @responses.activate
    def test_download_export_http_error(self, bag):
        responses.add(responses.GET, HEP_A_EXPORT_URL, status=500)
        with pytest.raises(SwissBAGAPIError, match="HTTP 500"):
            bag.download_export("HEPATITIS_A_oblig", version="20261014")


@pytest.mark.parametrize(
    ("value", "temporality", "expected"),
    [
        (2026, "year", "2026"),
        (202607, "month", "2026-07"),
        (202641, "iso_week", "2026-W41"),
        (202641, "week", "2026-W41"),
        (202605, "iso_week_sentinella", "2026-W05"),
        (20250210, "date", "2025-02-10"),
        (None, "month", None),
        (float("nan"), "month", None),
    ],
)
def test_parse_temporal(value, temporality, expected):
    assert parse_temporal(value, temporality) == expected


@pytest.mark.external_api
def test_live_versions():
    bag = SwissBAGAccessor()
    versions = bag.list_versions(limit=1)
    assert not versions.empty


@pytest.mark.external_api
def test_live_series():
    bag = SwissBAGAccessor()
    frame = bag.get_series("dengueFever", "cases", "value", "month")
    assert {"temporal", "value"}.issubset(frame.columns)
    assert not frame.empty
