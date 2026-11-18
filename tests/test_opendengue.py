"""Tests for the OpenDengue global dengue case count accessor.

Network-free tests serve small fixture zips through the ``responses``
library using the accessor's ``base_url`` override.  Live tests are gated
behind ``@pytest.mark.external_api``.
"""

import io
import zipfile

import pandas as pd
import pytest
import responses

from epidatasets.sources.opendengue import (
    CITATION,
    LEVELS,
    OpenDengueAccessor,
    OpenDengueDataError,
)

BASE = "https://example.com/opendengue"

NATIONAL_CSV = """adm_0_name,adm_1_name,adm_2_name,full_name,ISO_A0,FAO_GAUL_code,RNE_iso_code,IBGE_code,calendar_start_date,calendar_end_date,Year,dengue_total,case_definition_standardised,S_res,T_res,UUID
"BRAZIL",NA,NA,"BRAZIL","BRA",38,NA,NA,"2019-01-06","2019-01-12",2019,1234,"Confirmed total","Admin0","Week","MOH-BRA-2019-W02"
"BRAZIL",NA,NA,"BRAZIL","BRA",38,NA,NA,"2019-01-13","2019-01-19",2019,1500,"Confirmed total","Admin0","Week","MOH-BRA-2019-W03"
"BRAZIL",NA,NA,"BRAZIL","BRA",38,NA,NA,"2023-07-01","2023-07-31",2023,42000,"Confirmed total","Admin0","Month","MOH-BRA-2023-M07"
"INDIA",NA,NA,"INDIA","IND",107,NA,NA,"2015-06-01","2015-06-30",2015,8000,"Suspected","Admin0","Month","NVBDCP-IND-2015-M06"
"INDIA",NA,NA,"INDIA","IND",107,NA,NA,"2015-07-01","2015-07-31",2015,9500,"Suspected","Admin0","Month","NVBDCP-IND-2015-M07"
"VIET NAM",NA,NA,"VIET NAM","VNM",174,NA,NA,"2022-01-01","2022-01-31",2022,12000,"Confirmed total","Admin0","Month","WHO-WPRO-VNM-2022-M01"
"""

SPATIAL_CSV = """adm_0_name,adm_1_name,adm_2_name,full_name,ISO_A0,FAO_GAUL_code,RNE_iso_code,IBGE_code,calendar_start_date,calendar_end_date,Year,dengue_total,case_definition_standardised,S_res,T_res,UUID
"BRAZIL","RIO DE JANEIRO",NA,"BRAZIL_RIO DE JANEIRO","BRA",38,NA,330455,"2019-01-06","2019-01-12",2019,300,"Confirmed total","Admin1","Week","MOH-BRA-RJ-2019-W02"
"BRAZIL","RIO DE JANEIRO",NA,"BRAZIL_RIO DE JANEIRO","BRA",38,NA,330455,"2019-01-13","2019-01-19",2019,410,"Confirmed total","Admin1","Week","MOH-BRA-RJ-2019-W03"
"BRAZIL","SÃO PAULO","Campinas","BRAZIL_SÃO PAULO_Campinas","BRA",38,NA,350950,"2023-07-01","2023-07-31",2023,210,"Confirmed total","Admin2","Month","MOH-BRA-SP-Campinas-2023-M07"
"INDIA","Delhi",NA,"INDIA_Delhi","IND",107,NA,NA,"2015-06-01","2015-06-30",2015,900,"Confirmed total","Admin1","Month","NVBDCP-IND-Delhi-2015-M06"
"""


def zip_bytes(csv_text: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("extract.csv", csv_text)
    return buffer.getvalue()


def _write_extract(path, csv_text):
    path.write_text(csv_text)
    return path


@pytest.fixture
def accessor(tmp_path):
    return OpenDengueAccessor(
        cache_dir=str(tmp_path / "opendengue"),
        version="V1.3",
        base_url=BASE,
    )


def register_zips(include_spatial: bool = True):
    responses.add(
        responses.GET,
        f"{BASE}/data/releases/V1.3/National_extract_V1_3.zip",
        body=zip_bytes(NATIONAL_CSV),
        status=200,
    )
    if include_spatial:
        responses.add(
            responses.GET,
            f"{BASE}/data/releases/V1.3/Spatial_extract_V1_3.zip",
            body=zip_bytes(SPATIAL_CSV),
            status=200,
        )
        responses.add(
            responses.GET,
            f"{BASE}/data/releases/V1.3/Temporal_extract_V1_3.zip",
            body=zip_bytes(SPATIAL_CSV),
            status=200,
        )


# ---------------------------------------------------------------------------
# Basics
# ---------------------------------------------------------------------------


class TestBasics:
    def test_initialization(self, accessor):
        assert accessor.source_name == "opendengue"
        assert "OpenDengue" in accessor.source_description
        assert accessor.source_url == "https://opendengue.org/"
        assert accessor.cache_dir.exists()
        assert accessor.version == "V1.3"

    def test_citation_is_mandatory_and_complete(self):
        citation = OpenDengueAccessor.citation()
        assert citation == CITATION
        assert "Scientific Data" in citation
        assert "10.1038/s41597-024-03120-7" in citation
        assert "CC BY 4.0" in citation

    def test_invalid_level(self, accessor):
        with pytest.raises(ValueError, match="Valid levels"):
            accessor.get_global(level="galactic")

    def test_list_countries(self, accessor):
        assert set(LEVELS) == {"national", "highest_spatial", "highest_temporal"}
        # countries list comes from the default (national) extract
        accessor._ensure_extract = lambda level, use_cache=True: _write_extract(
            accessor.cache_dir / "National_extract_V1.3.csv", NATIONAL_CSV
        )
        countries = accessor.list_countries()
        assert {"country_code", "country_name"} == set(countries.columns)
        assert "BRA" in countries["country_code"].values
        assert len(countries) == 3


def _write_extract(path, csv_text):
    path.write_text(csv_text)
    return path


# ---------------------------------------------------------------------------
# get_global
# ---------------------------------------------------------------------------


class TestGetGlobal:
    @responses.activate
    def test_get_global_national(self, accessor):
        register_zips()
        df = accessor.get_global(level="national")
        assert len(df) == 6
        assert pd.api.types.is_datetime64_any_dtype(df["calendar_start_date"])
        assert pd.api.types.is_numeric_dtype(df["dengue_total"])
        assert df["Year"].dtype.name == "Int64"
        assert df["adm_1_name"].isna().all()

    @responses.activate
    def test_caching(self, accessor):
        register_zips()
        accessor.get_global(level="national")
        accessor.get_global(level="national")
        assert len(responses.calls) == 1
        # no zip residue, only the extracted csv
        assert not list(accessor.cache_dir.glob("*.zip"))

    @responses.activate
    def test_ttl_expiry(self, tmp_path):
        import os

        acc = OpenDengueAccessor(
            cache_dir=str(tmp_path / "od"),
            version="V1.3",
            base_url=BASE,
            cache_ttl_days=0,
        )
        register_zips()
        acc.get_global(level="national")
        for f in acc.cache_dir.glob("*.csv"):
            os.utime(f, (0, 0))
        responses.calls.reset()
        register_zips()
        acc.get_global(level="national")
        assert len(responses.calls) == 1

    @responses.activate
    def test_corrupted_zip(self, accessor):
        responses.add(
            responses.GET,
            f"{BASE}/data/releases/V1.3/National_extract_V1_3.zip",
            body=b"this is not a zip",
        )
        with pytest.raises(OpenDengueDataError, match="Corrupted download"):
            accessor.get_global(level="national")
        # cache cleared for retry
        assert not list(accessor.cache_dir.glob("National*"))

    @responses.activate
    def test_download_error_wrapped(self, accessor):
        import requests as requests_lib

        responses.add(
            responses.GET,
            f"{BASE}/data/releases/V1.3/National_extract_V1_3.zip",
            body=requests_lib.exceptions.ConnectionError("boom"),
        )
        with pytest.raises(OpenDengueDataError, match="Failed to download"):
            accessor.get_global(level="national")
        assert not list(accessor.cache_dir.glob("*.part"))


# ---------------------------------------------------------------------------
# Country matching
# ---------------------------------------------------------------------------


class TestCountryMatching:
    @responses.activate
    def test_exact_case_insensitive(self, accessor):
        register_zips()
        df = accessor.get_country("brazil")
        assert set(df["adm_0_name"]) == {"BRAZIL"}
        assert len(df) == 3  # default extract (highest_temporal) fixture

    @responses.activate
    def test_iso3_code(self, accessor):
        register_zips()
        df = accessor.get_country("IND")
        assert set(df["adm_0_name"]) == {"INDIA"}

    @responses.activate
    def test_fuzzy_misspelling(self, accessor):
        register_zips()
        df = accessor.get_country("Brasil")  # one letter off
        assert set(df["adm_0_name"]) == {"BRAZIL"}

    @responses.activate
    def test_unknown_country_raises_with_suggestions(self, accessor):
        register_zips()
        with pytest.raises(OpenDengueDataError, match="Closest matches"):
            accessor.get_country("Narnia")


# ---------------------------------------------------------------------------
# Filtering: dates, admin levels, locations
# ---------------------------------------------------------------------------


class TestFilters:
    @responses.activate
    def test_date_range_overlap(self, accessor):
        register_zips()
        # July 2023 month overlaps the window ending 2023-07-15
        df = accessor.get_country(
            "BRA",
            start_date="2023-07-01",
            end_date="2023-07-15",
            level="national",
        )
        assert len(df) == 1
        assert df.iloc[0]["dengue_total"] == 42000

    @responses.activate
    def test_date_filter_datetime_objects(self, accessor):
        from datetime import datetime

        register_zips()
        df = accessor.get_country(
            "BRA",
            start_date=datetime(2019, 1, 13),
            end_date=datetime(2019, 6, 30),
            level="national",
        )
        assert len(df) == 1  # only the week starting 2019-01-13
        assert df.iloc[0]["dengue_total"] == 1500

    @responses.activate
    def test_invalid_date_range(self, accessor):
        register_zips()
        with pytest.raises(ValueError, match="start_date"):
            accessor.get_country(
                "BRA",
                start_date="2020-01-01",
                end_date="2019-01-01",
                level="national",
            )

    @responses.activate
    def test_admin_level_filter(self, accessor):
        register_zips()
        states = accessor.get_country("BRA", admin_level=1, level="highest_spatial")
        assert len(states) == 2  # two Rio de Janeiro weeks
        districts = accessor.get_country("BRA", admin_level=2, level="highest_spatial")
        assert len(districts) == 1
        assert districts.iloc[0]["adm_2_name"] == "Campinas"
        with pytest.raises(ValueError, match="admin_level"):
            accessor.get_country("BRA", admin_level=3)

    @responses.activate
    def test_timeseries_by_admin1(self, accessor):
        register_zips()
        ts = accessor.get_timeseries(
            "Brazil", admin1="rio de janeiro", level="highest_spatial"
        )
        assert len(ts) == 2
        assert ts["dengue_total"].tolist() == [300, 410]

    @responses.activate
    def test_timeseries_accent_insensitive_admin1(self, accessor):
        register_zips()
        ts = accessor.get_timeseries(
            "Brazil", admin1="Sao Paulo", admin2="campinas", level="highest_spatial"
        )
        assert len(ts) == 1

    @responses.activate
    def test_timeseries_unknown_admin_raises(self, accessor):
        register_zips()
        with pytest.raises(OpenDengueDataError, match="Admin-1"):
            accessor.get_timeseries("Brazil", admin1="Xanadu", level="highest_spatial")


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------


class TestSources:
    @responses.activate
    def test_get_sources_all(self, accessor):
        register_zips()
        sources = accessor.get_sources()
        assert set(sources.columns) == {"adm_0_name", "n_series", "n_records"}
        brazil = sources[sources["adm_0_name"] == "BRAZIL"].iloc[0]
        assert brazil["n_records"] == 3
        assert brazil["n_series"] == 3

    @responses.activate
    def test_get_sources_one_country(self, accessor):
        register_zips()
        sources = accessor.get_sources(country="Vietnam")
        assert len(sources) == 1
        assert sources.iloc[0]["adm_0_name"] == "VIET NAM"


# ---------------------------------------------------------------------------
# Live integration smoke tests
# ---------------------------------------------------------------------------


@pytest.mark.external_api
@pytest.mark.integration
@pytest.mark.skipif(
    __import__("os").getenv("SKIP_EXTERNAL_TESTS", "false").lower() == "true",
    reason="External API tests disabled",
)
class TestLiveSmoke:
    def test_live_national_extract(self, tmp_path):
        acc = OpenDengueAccessor(cache_dir=str(tmp_path / "od"))
        df = acc.get_global(level="national", use_cache=False)
        assert not df.empty
        assert "dengue_total" in df.columns
        assert df["adm_0_name"].nunique() > 50

    def test_live_country_brazil(self, tmp_path):
        acc = OpenDengueAccessor(cache_dir=str(tmp_path / "od"))
        df = acc.get_country("Brazil", level="national", use_cache=False)
        assert set(df["adm_0_name"]) == {"BRAZIL"}
        assert df["dengue_total"].sum() > 0
