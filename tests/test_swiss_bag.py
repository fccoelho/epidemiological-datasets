"""Tests for the Swiss BAG Infectious Diseases Dashboard (IDD) accessor.

Network-free tests mock the BAG IDD REST API with the ``responses``
library.  Live tests are gated behind ``@pytest.mark.external_api``.
"""

import json

import pandas as pd
import pytest
import requests
import responses

from epidatasets.sources.swiss_bag import SwissBAGAccessor

API_ROOT = SwissBAGAccessor.API_ROOT
VERSION_URL = f"{API_ROOT}/version"
DATA_VERSION_URL = f"{API_ROOT}/data/version"
SETS_URL = f"{API_ROOT}/data/sets"
DENGUE_DETAILS_URL = f"{API_ROOT}/data/dengueFever/cases/value/month/details"
DENGUE_QUERY_URL = f"{API_ROOT}/data/dengueFever/cases/value/month"
COVID_DETAILS_URL = f"{API_ROOT}/data/covid19/cases/incValue/iso_week/details"
COVID_QUERY_URL = f"{API_ROOT}/data/covid19/cases/incValue/iso_week"
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
        assert list(countries["country_code"]) == ["CH", "FL"]

    def test_list_cantons(self):
        cantons = SwissBAGAccessor.list_cantons()
        assert len(cantons) == 26
        assert set(cantons.columns) == {"canton", "canton_name"}

    @responses.activate
    def test_list_versions(self, bag):
        responses.add(
            responses.GET,
            VERSION_URL,
            json=[{"name": "20261014"}, {"name": "20261007"}],
        )
        versions = bag.list_versions()
        assert list(versions["version"]) == ["20261014", "20261007"]
        assert versions["date"].iloc[0] == "2026-10-14"

    @responses.activate
    def test_list_versions_parses_rerun_suffixes(self, bag):
        responses.add(
            responses.GET,
            VERSION_URL,
            json=[{"name": "20250827_V2"}, {"name": "20261014"}],
        )
        versions = bag.list_versions()
        assert versions["date"].iloc[0] == "2025-08-27"

    @responses.activate
    def test_current_version(self, bag):
        responses.add(responses.GET, DATA_VERSION_URL, json={"name": "20261014"})
        assert bag.current_version == "20261014"

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
        }

        dengue = bag.list_sets(topic="dengueFever")
        assert len(dengue) == 3
        assert set(dengue["temporality"]) == {"month", "year"}

    @responses.activate
    def test_list_sets_unknown_topic(self, bag):
        responses.add(responses.GET, SETS_URL, json=SETS)
        with pytest.raises(ValueError, match="Unknown topic"):
            bag.list_sets(topic="nonexistent")

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
        responses.add(responses.GET, SETS_URL, json=SETS)
        responses.add(responses.GET, DENGUE_DETAILS_URL, json=DENGUE_DETAILS)
        details = bag.get_set_details("dengueFever", "cases", "value", "month")
        assert details["version"] == "20261007"
        assert details["availableSeriesConfigurations"][0]["CHFL"] == "CHFL"

    @responses.activate
    def test_get_set_details_unknown_set(self, bag):
        responses.add(responses.GET, SETS_URL, json=SETS)
        with pytest.raises(ValueError, match="Unknown series set"):
            bag.get_set_details("measles", "cases", "value", "month")


class TestSeriesQueries:
    @responses.activate
    def test_single_series_uses_first_configuration(self, bag):
        responses.add(responses.GET, SETS_URL, json=SETS)
        responses.add(responses.GET, DENGUE_DETAILS_URL, json=DENGUE_DETAILS)
        responses.add(responses.POST, DENGUE_QUERY_URL, json=DENGUE_PAYLOAD)

        frame = bag.get_series("dengueFever", "cases", "value", "month")

        assert list(frame["temporal"]) == ["2026-07", "2026-08"]
        assert list(frame["value"]) == [22, 14]
        assert frame["trend"].tolist() == ["stagnant", "falling"]
        assert frame["version"].iloc[0] == "20261007"

        sent = json.loads(responses.calls[-1].request.body)
        assert sent == {"CHFL": "CHFL", "georegion": "CHFL", "type": "all"}

    @responses.activate
    def test_filters_are_merged_into_configuration(self, bag):
        responses.add(responses.GET, SETS_URL, json=SETS)
        responses.add(responses.GET, DENGUE_DETAILS_URL, json=DENGUE_DETAILS)
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
        assert len(responses.calls) == 3

    @responses.activate
    def test_unknown_filter_property_raises(self, bag):
        responses.add(responses.GET, SETS_URL, json=SETS)
        responses.add(responses.GET, DENGUE_DETAILS_URL, json=DENGUE_DETAILS)
        with pytest.raises(ValueError, match="not part of the"):
            bag.get_series(
                "dengueFever",
                "cases",
                "value",
                "month",
                filters={"canton": "ZH"},
            )

    @responses.activate
    def test_all_series_stacks_configurations(self, bag):
        responses.add(responses.GET, SETS_URL, json=SETS)
        responses.add(responses.GET, COVID_DETAILS_URL, json=COVID_DETAILS)
        responses.add(
            responses.POST,
            COVID_QUERY_URL,
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
    def test_all_series_no_configuration_match_raises(self, bag):
        responses.add(responses.GET, SETS_URL, json=SETS)
        responses.add(responses.GET, COVID_DETAILS_URL, json=COVID_DETAILS)
        with pytest.raises(ValueError, match="No series configuration"):
            bag.get_series(
                "covid19",
                "cases",
                "incValue",
                "iso_week",
                all_series=True,
                filters={"canton": "BE"},
            )

    @responses.activate
    def test_missing_series_raises_http_error(self, bag):
        responses.add(responses.GET, SETS_URL, json=SETS)
        responses.add(responses.GET, DENGUE_DETAILS_URL, json=DENGUE_DETAILS)
        responses.add(responses.POST, DENGUE_QUERY_URL, status=404)
        with pytest.raises(requests.exceptions.HTTPError):
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
        with pytest.raises(ValueError, match="Unknown topic"):
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

        cached = bag.download_export("HEPATITIS_A_oblig")
        assert len(responses.calls) == 3  # 2 version lookups + 1 download
        assert cached.shape == frame.shape

    @responses.activate
    def test_download_export_rejects_bad_format(self, bag):
        with pytest.raises(ValueError, match="Unsupported format"):
            bag.download_export("HEPATITIS_A_oblig", format="xlsx")

    @responses.activate
    def test_download_export_http_error(self, bag):
        responses.add(responses.GET, HEP_A_EXPORT_URL, status=500)
        with pytest.raises(requests.exceptions.HTTPError):
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
        (2026, "unknown", "2026"),
    ],
)
def test_parse_temporal(value, temporality, expected):
    assert SwissBAGAccessor._parse_temporal(value, temporality) == expected


@pytest.mark.external_api
def test_live_versions():
    bag = SwissBAGAccessor()
    versions = bag.list_versions().head(1)
    assert not versions.empty


@pytest.mark.external_api
def test_live_series():
    bag = SwissBAGAccessor()
    frame = bag.get_series("dengueFever", "cases", "value", "month")
    assert {"temporal", "value"}.issubset(frame.columns)
    assert not frame.empty
