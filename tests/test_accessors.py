"""Tests for data source accessors.

These tests validate that each accessor can be instantiated and return
valid data structures. Tests are designed to be fast and non-breaking.
"""

import json
import os
from pathlib import Path

import pandas as pd
import pytest
import requests
import responses


def requires_external_api(func):
    """Mark test as external API and skip when disabled."""
    func = pytest.mark.external_api(func)
    return pytest.mark.skipif(
        os.getenv("SKIP_EXTERNAL_TESTS", "false").lower() == "true",
        reason="External API tests disabled",
    )(func)


class TestAfricaCDC:
    def test_initialization(self):
        from epidatasets.sources.africa_cdc import AfricaCDCAccessor
        accessor = AfricaCDCAccessor()
        assert accessor is not None
        assert accessor.source_name == "africa_cdc"

    def test_get_countries(self):
        from epidatasets.sources.africa_cdc import AfricaCDCAccessor
        accessor = AfricaCDCAccessor()
        countries = accessor.list_countries()
        assert isinstance(countries, pd.DataFrame)
        assert len(countries) > 40

    def test_list_regions(self):
        from epidatasets.sources.africa_cdc import AfricaCDCAccessor
        accessor = AfricaCDCAccessor()
        regions = accessor.list_regions()
        assert isinstance(regions, pd.DataFrame)

    def test_list_priority_diseases(self):
        from epidatasets.sources.africa_cdc import AfricaCDCAccessor
        accessor = AfricaCDCAccessor()
        diseases = accessor.list_priority_diseases()
        assert isinstance(diseases, pd.DataFrame)


class TestPAHO:
    def test_initialization(self):
        from epidatasets.sources.paho import PAHOAccessor
        accessor = PAHOAccessor()
        assert accessor is not None
        assert accessor.source_name == "paho"

    def test_list_countries(self):
        from epidatasets.sources.paho import PAHOAccessor
        accessor = PAHOAccessor()
        countries = accessor.list_countries()
        assert isinstance(countries, pd.DataFrame)
        assert len(countries) > 30

    def test_list_vaccines(self):
        from epidatasets.sources.paho import PAHOAccessor
        accessor = PAHOAccessor()
        vaccines = accessor.list_vaccines()
        assert isinstance(vaccines, pd.DataFrame)

    def test_get_subregion_countries(self):
        from epidatasets.sources.paho import PAHOAccessor
        accessor = PAHOAccessor()
        andean = accessor.get_countries_by_subregion("Andean")
        assert len(andean) > 0


class TestRKI:
    def test_initialization(self):
        from epidatasets.sources.rki_germany import RKIGermanyAccessor
        accessor = RKIGermanyAccessor()
        assert accessor is not None
        assert accessor.source_name == "rki"

    def test_list_states(self):
        from epidatasets.sources.rki_germany import RKIGermanyAccessor
        accessor = RKIGermanyAccessor()
        states = accessor.list_states()
        assert isinstance(states, pd.DataFrame)

    def test_list_notifiable_diseases(self):
        from epidatasets.sources.rki_germany import RKIGermanyAccessor
        accessor = RKIGermanyAccessor()
        diseases = accessor.list_notifiable_diseases()
        assert isinstance(diseases, pd.DataFrame)


class TestChinaCDC:
    def test_initialization(self):
        from epidatasets.sources.china_cdc import ChinaCDCAccessor
        accessor = ChinaCDCAccessor()
        assert accessor is not None
        assert accessor.source_name == "china_cdc"

    def test_crossref_search_parses_records(self):
        """Regression: article discovery must use CrossRef, not the
        JavaScript-rendered volume page (which yields 0 issues)."""
        from unittest.mock import MagicMock

        from epidatasets.sources.china_cdc import ChinaCDCAccessor

        payload = {
            "message": {
                "items": [
                    {
                        "DOI": "10.46234/ccdcw2023.061",
                        "title": ["Reported Cases and Deaths of National "
                                  "Notifiable Infectious Diseases — China, "
                                  "February 2023"],
                        "container-title": ["China CDC Weekly"],
                        "issued": {"date-parts": [[2023, 6, 1]]},
                    },
                ]
            }
        }
        accessor = ChinaCDCAccessor()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = payload
        mock_resp.raise_for_status.return_value = None

        original_get = accessor._session.get
        accessor._session.get = MagicMock(return_value=mock_resp)
        try:
            df = accessor.search_articles("notifiable", year=2023)
        finally:
            accessor._session.get = original_get

        assert list(df["doi"]) == ["10.46234/ccdcw2023.061"]
        assert df["year"].iloc[0] == 2023
        assert df["pdf_url"].iloc[0].endswith("10.46234/ccdcw2023.061.pdf")

    def test_crossref_query_targets_journal_issn(self):
        from unittest.mock import MagicMock

        from epidatasets.sources.china_cdc import ChinaCDCAccessor

        accessor = ChinaCDCAccessor()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"message": {"items": []}}
        mock_resp.raise_for_status.return_value = None

        original_get = accessor._session.get
        mock_get = MagicMock(return_value=mock_resp)
        accessor._session.get = mock_get
        try:
            accessor.get_weekly_reports(2023)
        finally:
            accessor._session.get = original_get

        url = mock_get.call_args.args[0]
        assert accessor.ISSN == "2097-3101"
        assert f"/journals/{accessor.ISSN}/works" in url

    def test_list_notifiable_diseases(self):
        from epidatasets.sources.china_cdc import ChinaCDCAccessor
        accessor = ChinaCDCAccessor()
        diseases = accessor.list_notifiable_diseases()
        assert isinstance(diseases, pd.DataFrame)

    def test_list_provinces(self):
        from epidatasets.sources.china_cdc import ChinaCDCAccessor
        accessor = ChinaCDCAccessor()
        provinces = accessor.list_provinces()
        assert isinstance(provinces, pd.DataFrame)

    def test_parse_pdf_to_disease_table(self):
        from pathlib import Path

        from epidatasets.sources.china_cdc import ChinaCDCAccessor

        pdf_path = Path.home() / ".cache" / "epidatasets" / "china_cdc" / "report2024-9.pdf"
        if not pdf_path.exists():
            pytest.skip("Cached China CDC PDF not available")

        result = ChinaCDCAccessor.parse_pdf_to_disease_table(pdf_path)
        assert isinstance(result, pd.DataFrame)
        assert not result.empty
        assert "disease_en" in result.columns
        assert "cases" in result.columns
        assert "deaths" in result.columns
        assert result["cases"].notna().any()

    def test_parse_pdf_tables(self):
        from pathlib import Path

        from epidatasets.sources.china_cdc import ChinaCDCAccessor

        pdf_path = Path.home() / ".cache" / "epidatasets" / "china_cdc" / "report2024-9.pdf"
        if not pdf_path.exists():
            pytest.skip("Cached China CDC PDF not available")

        tables = ChinaCDCAccessor.parse_pdf_tables(pdf_path)
        assert isinstance(tables, list)

    def test_parse_pdf_text_lines(self):
        from pathlib import Path

        from epidatasets.sources.china_cdc import ChinaCDCAccessor

        pdf_path = Path.home() / ".cache" / "epidatasets" / "china_cdc" / "report2024-9.pdf"
        if not pdf_path.exists():
            pytest.skip("Cached China CDC PDF not available")

        rows = ChinaCDCAccessor._parse_pdf_text_lines(pdf_path)
        assert isinstance(rows, list)
        assert len(rows) > 0
        for row in rows:
            assert "disease_en" in row
            assert "cases" in row
            assert "deaths" in row
            assert "is_subitem" in row

    def test_normalise_table(self):
        from epidatasets.sources.china_cdc import ChinaCDCAccessor

        raw = pd.DataFrame(
            {
                "Disease": ["Plague", "Cholera", "Viral Hepatitis", "Total"],
                "Cases": ["5", "12", "145,230", "145,247"],
                "Deaths": ["0", "0", "42", "42"],
            }
        )
        result = ChinaCDCAccessor._normalise_table(raw)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3
        assert "Total" not in result["disease_en"].values
        assert result.iloc[0]["disease_en"] == "Plague"
        assert result.iloc[0]["cases"] == 5

    def test_disease_name_map(self):
        from epidatasets.sources.china_cdc import _DISEASE_NAME_MAP

        assert isinstance(_DISEASE_NAME_MAP, dict)
        assert len(_DISEASE_NAME_MAP) > 0
        assert "Influenza" in _DISEASE_NAME_MAP or "Plague" in _DISEASE_NAME_MAP

    def test_get_influenza_surveillance_returns_dataframe(self):
        from epidatasets.sources.china_cdc import ChinaCDCAccessor
        accessor = ChinaCDCAccessor()
        result = accessor.get_influenza_surveillance(weeks=[1, 2], year=2024)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert "week" in result.columns

    def test_get_covid_updates_returns_dataframe(self):
        from epidatasets.sources.china_cdc import ChinaCDCAccessor
        accessor = ChinaCDCAccessor()
        result = accessor.get_covid_updates()
        assert isinstance(result, pd.DataFrame)

    def test_get_vaccination_coverage_returns_dataframe(self):
        from epidatasets.sources.china_cdc import ChinaCDCAccessor
        accessor = ChinaCDCAccessor()
        result = accessor.get_vaccination_coverage(vaccines=["EPI"], year=2024)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert result.iloc[0]["vaccine"] == "EPI"


class TestIndiaIDSP:
    def test_initialization(self):
        from epidatasets.sources.india_idsp import IndiaIDSPAccessor
        accessor = IndiaIDSPAccessor()
        assert accessor is not None
        assert accessor.source_name == "india_idsp"

    def test_list_states(self):
        from epidatasets.sources.india_idsp import IndiaIDSPAccessor
        accessor = IndiaIDSPAccessor()
        states = accessor.list_states()
        assert isinstance(states, pd.DataFrame)

    def test_list_priority_diseases(self):
        from epidatasets.sources.india_idsp import IndiaIDSPAccessor
        accessor = IndiaIDSPAccessor()
        diseases = accessor.list_priority_diseases()
        assert isinstance(diseases, pd.DataFrame)


class TestUKHSA:
    def test_initialization(self):
        from epidatasets.sources.ukhsa import UKHSAAccessor
        accessor = UKHSAAccessor()
        assert accessor is not None
        assert accessor.source_name == "ukhsa"

    def test_list_diseases(self):
        from epidatasets.sources.ukhsa import UKHSAAccessor
        accessor = UKHSAAccessor()
        diseases = accessor.list_available_diseases()
        assert isinstance(diseases, (pd.DataFrame, list))


class TestOWID:
    def test_initialization(self):
        from epidatasets.sources.owid import OWIDAccessor
        accessor = OWIDAccessor()
        assert accessor is not None
        assert accessor.source_name == "owid"


class TestEurostat:
    def test_initialization(self):
        from epidatasets.sources.eurostat import EurostatAccessor
        accessor = EurostatAccessor()
        assert accessor is not None
        assert accessor.source_name == "eurostat"


class TestColombiaINS:
    def test_initialization(self):
        from epidatasets.sources.colombia_ins import ColombiaINSAccessor
        accessor = ColombiaINSAccessor()
        assert accessor is not None
        assert accessor.source_name == "colombia_ins"

    def test_list_departments(self):
        from epidatasets.sources.colombia_ins import ColombiaINSAccessor
        accessor = ColombiaINSAccessor()
        depts = accessor.list_departments()
        assert isinstance(depts, pd.DataFrame)

    def test_list_diseases(self):
        from epidatasets.sources.colombia_ins import ColombiaINSAccessor
        accessor = ColombiaINSAccessor()
        diseases = accessor.list_diseases()
        assert isinstance(diseases, pd.DataFrame)


class TestEpiPulse:
    def test_initialization(self):
        from epidatasets.sources.epipulse import EpiPulseAccessor
        accessor = EpiPulseAccessor()
        assert accessor is not None
        assert accessor.source_name == "epipulse"
        assert hasattr(accessor, "get_available_diseases")

    def test_get_available_diseases(self):
        from epidatasets.sources.epipulse import EpiPulseAccessor
        accessor = EpiPulseAccessor()
        diseases = accessor.get_available_diseases()
        assert isinstance(diseases, pd.DataFrame)
        assert len(diseases) > 0


class TestRespiCast:
    def test_initialization(self):
        from epidatasets.sources.respicast import RespiCastAccessor
        accessor = RespiCastAccessor()
        assert accessor is not None
        assert accessor.source_name == "respicast"

    def test_get_available_diseases(self):
        from epidatasets.sources.respicast import RespiCastAccessor
        accessor = RespiCastAccessor()
        diseases = accessor.get_available_diseases()
        assert isinstance(diseases, pd.DataFrame)
        assert len(diseases) > 0


class TestCDCOpenData:
    def test_initialization(self):
        from epidatasets.sources.cdc_opendata import CDCOpenDataAccessor
        accessor = CDCOpenDataAccessor()
        assert accessor is not None
        assert accessor.source_name == "cdc_opendata"

    def test_get_available_datasets(self):
        from epidatasets.sources.cdc_opendata import CDCOpenDataAccessor
        accessor = CDCOpenDataAccessor()
        datasets = accessor.get_available_datasets()
        assert isinstance(datasets, pd.DataFrame)

    def test_list_notifiable_diseases(self):
        from epidatasets.sources.cdc_opendata import CDCOpenDataAccessor
        accessor = CDCOpenDataAccessor()
        diseases = accessor.list_notifiable_diseases()
        assert isinstance(diseases, list)
        assert "Measles" in diseases


class TestECDCOpenData:
    def test_initialization(self):
        from epidatasets.sources.ecdc_opendata import ECDCOpenDataAccessor
        accessor = ECDCOpenDataAccessor()
        assert accessor is not None
        assert accessor.source_name == "ecdc"

    def test_get_available_diseases(self):
        from epidatasets.sources.ecdc_opendata import ECDCOpenDataAccessor
        accessor = ECDCOpenDataAccessor()
        diseases = accessor.get_available_diseases()
        assert isinstance(diseases, pd.DataFrame)
        assert len(diseases) > 0


class TestGlobalHealth:
    def test_initialization(self):
        from epidatasets.sources.global_health import GlobalHealthAccessor
        accessor = GlobalHealthAccessor()
        assert accessor is not None
        assert accessor.source_name == "global_health"


class TestHealthDataGov:
    def test_initialization(self):
        from epidatasets.sources.healthdata_gov import HealthDataGovAccessor
        accessor = HealthDataGovAccessor()
        assert accessor is not None
        assert accessor.source_name == "healthdata_gov"

    def test_list_datasets(self):
        from epidatasets.sources.healthdata_gov import HealthDataGovAccessor
        accessor = HealthDataGovAccessor()
        datasets = accessor.list_datasets()
        assert isinstance(datasets, pd.DataFrame)


class TestMalariaAtlas:
    def test_initialization(self):
        from epidatasets.sources.malaria_atlas import MalariaAtlasAccessor
        accessor = MalariaAtlasAccessor()
        assert accessor is not None
        assert accessor.source_name == "malaria_atlas"


class TestWHO:
    def test_initialization(self):
        from epidatasets.sources.who_ghoclient import WHOAccessor
        accessor = WHOAccessor()
        assert accessor is not None
        assert accessor.source_name == "who"


class TestPakistanNIH:
    @pytest.fixture
    def accessor(self):
        from epidatasets.sources.pakistan_nih import PakistanNIHAccessor
        return PakistanNIHAccessor()

    @pytest.fixture
    def sample_pdf_path(self):
        return Path(__file__).parent / "fixtures" / "pakistan_nih" / "Weekly_Report-51-2024.pdf"

    def test_initialization(self, accessor):
        assert accessor is not None
        assert accessor.source_name == "pakistan_nih"

    def test_list_countries(self, accessor):
        countries = accessor.list_countries()
        assert isinstance(countries, pd.DataFrame)
        assert len(countries) == 1
        assert countries.iloc[0]["country_code"] == "PK"

    def test_build_weekly_url(self, accessor):
        url = accessor._build_weekly_url(2025, 10)
        assert "nih.org.pk" in url
        assert "2025" in url
        assert "10" in url
        assert "Weekly_Report" in url

    def test_priority_diseases(self, accessor):
        assert len(accessor.PRIORITY_DISEASES) > 0
        assert "Dengue Fever" in accessor.PRIORITY_DISEASES

    def test_provinces(self, accessor):
        assert len(accessor.PROVINCES) > 0
        assert "Punjab" in accessor.PROVINCES

    def test_extract_pdf_text(self, accessor, sample_pdf_path):
        text = accessor._pdf.extract_text(sample_pdf_path)
        assert isinstance(text, str)
        assert len(text) > 0

    def test_extract_pdf_tables(self, accessor, sample_pdf_path):
        tables = accessor._pdf.extract_tables(sample_pdf_path)
        assert isinstance(tables, list)


class TestOmanMOH:
    @pytest.fixture
    def accessor(self):
        from epidatasets.sources.oman_moh import OmanMOHAccessor
        return OmanMOHAccessor()

    @pytest.fixture
    def sample_pdf_path(self):
        return Path(__file__).parent / "fixtures" / "oman_moh" / "annual_health_report_2023.pdf"

    def test_initialization(self, accessor):
        assert accessor is not None
        assert accessor.source_name == "oman_moh"

    def test_list_countries(self, accessor):
        countries = accessor.list_countries()
        assert isinstance(countries, pd.DataFrame)
        assert len(countries) == 1
        assert countries.iloc[0]["country_code"] == "OM"

    def test_build_annual_report_url(self, accessor):
        url = accessor._build_annual_report_url(2023)
        assert "moh.gov.om" in url
        assert "2023" in url

    def test_governorates(self, accessor):
        assert len(accessor.GOVERNORATES) > 0
        assert "Masqat" in accessor.GOVERNORATES

    def test_list_available_reports(self, accessor):
        reports = accessor.list_available_reports()
        assert isinstance(reports, pd.DataFrame)
        assert not reports.empty
        assert "year" in reports.columns
        assert reports["year"].min() <= 1984
        assert reports["year"].max() >= 2024

    def test_extract_pdf_text(self, accessor, sample_pdf_path):
        text = accessor._extract_pdf_text(sample_pdf_path)
        assert isinstance(text, str)
        assert "Oman Ministry of Health" in text

    def test_extract_morbidity_mortality(self, accessor, sample_pdf_path):
        df = accessor.extract_morbidity_mortality(sample_pdf_path)
        assert isinstance(df, pd.DataFrame)
        assert "disease" in df.columns
        assert "Malaria" in df["disease"].values

    def test_extract_health_indicators(self, accessor, sample_pdf_path):
        df = accessor.extract_health_indicators(sample_pdf_path)
        assert isinstance(df, pd.DataFrame)
        assert "indicator" in df.columns
        assert "life_expectancy" in df["indicator"].values

    def test_extract_health_utilization(self, accessor, sample_pdf_path):
        df = accessor.extract_health_utilization(sample_pdf_path)
        assert isinstance(df, pd.DataFrame)
        assert "metric" in df.columns
        assert "outpatient_visits" in df["metric"].values

    def test_get_governorate_data(self, accessor, sample_pdf_path):
        df = accessor.get_governorate_data(sample_pdf_path)
        assert isinstance(df, pd.DataFrame)
        assert "governorate" in df.columns
        assert "Masqat" in df["governorate"].values


class TestNZHealth:
    @pytest.fixture
    def accessor(self):
        from epidatasets.sources.nz_health import NZHealthAccessor
        return NZHealthAccessor()

    def test_source_name(self, accessor):
        assert accessor.source_name == "nz_health"
        assert "New Zealand" in accessor.source_description
        assert "stats.govt.nz" in accessor.source_url

    def test_list_countries(self, accessor):
        countries = accessor.list_countries()
        assert isinstance(countries, pd.DataFrame)
        assert len(countries) == 1
        assert countries.iloc[0]["country_code"] == "NZL"
        assert countries.iloc[0]["country_name"] == "New Zealand"

    def test_get_mortality_sample(self, accessor):
        df = accessor.get_mortality(sample=True)
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert "year" in df.columns
        assert "total_deaths" in df.columns
        assert df["year"].min() <= 2019
        assert df["year"].max() >= 2023

    def test_get_hospital_events_sample(self, accessor):
        df = accessor.get_hospital_events(sample=True)
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert "year" in df.columns
        assert "total_discharges" in df.columns
        assert df["year"].min() <= 2019
        assert df["year"].max() >= 2023

    def test_get_life_tables_sample(self, accessor):
        df = accessor.get_life_tables(sample=True)
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert "year" in df.columns
        assert "male_life_expectancy" in df.columns
        assert "female_life_expectancy" in df.columns
        assert df["year"].min() <= 2019
        assert df["year"].max() >= 2023

    def test_get_immunisation_coverage(self, accessor):
        df = accessor.get_immunisation_coverage()
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert "vaccine" in df.columns
        assert "coverage_2023" in df.columns
        assert "DTaP-IPV-HepB/Hib" in df["vaccine"].values


class TestSingaporeMOH:
    @pytest.fixture
    def accessor(self):
        from epidatasets.sources.singapore_moh import SingaporeMOHAccessor
        return SingaporeMOHAccessor()

    def test_initialization(self, accessor):
        assert accessor is not None
        assert accessor.source_name == "singapore_moh"

    def test_source_metadata(self, accessor):
        assert "Singapore" in accessor.source_description
        assert "data.gov.sg" in accessor.source_url

    def test_list_countries(self, accessor):
        countries = accessor.list_countries()
        assert isinstance(countries, pd.DataFrame)
        assert len(countries) == 1
        assert countries.iloc[0]["country_code"] == "SG"
        assert countries.iloc[0]["country_name"] == "Singapore"

    def test_notifiable_diseases(self, accessor):
        assert len(accessor.NOTIFIABLE_DISEASES) > 0
        assert "Dengue Fever" in accessor.NOTIFIABLE_DISEASES

    def test_resource_id(self, accessor):
        assert (
            accessor.RESOURCE_ID
            == "d_ca168b2cb763640d72c4600a68f9909e"
        )

    def test_sample_data(self, accessor):
        df = accessor._sample_data()
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert set(df.columns) >= {"epi_week", "disease", "no._of_cases"}
        assert df["no._of_cases"].dtype.kind in {"i", "u"}
        assert "Dengue Fever" in df["disease"].values

    def test_normalise_coerces_numeric(self, accessor):
        from epidatasets.sources.singapore_moh import SingaporeMOHAccessor
        raw = pd.DataFrame(
            [
                {"_id": 1, "epi_week": "2020-W01", "disease": "Dengue Fever",
                 "no._of_cases": "12"},
                {"_id": 2, "epi_week": "2020-W01", "disease": "Cholera",
                 "no._of_cases": "0"},
            ]
        )
        out = SingaporeMOHAccessor._normalise(raw)
        assert "_id" not in out.columns
        assert out["no._of_cases"].dtype.kind in {"i", "u"}
        # sorted by disease -> Cholera (0) before Dengue Fever (12)
        assert set(out["no._of_cases"].tolist()) == {0, 12}
        dengue = out[out["disease"] == "Dengue Fever"].iloc[0]
        assert dengue["no._of_cases"] == 12

    def test_get_summary_invalid_by(self, accessor):
        with pytest.raises(ValueError):
            accessor.get_summary(by="invalid")

    @requires_external_api
    def test_list_diseases_live(self, accessor):
        diseases = accessor.list_diseases()
        assert isinstance(diseases, pd.DataFrame)
        assert not diseases.empty
        assert "disease" in diseases.columns
        assert "Dengue Fever" in diseases["disease"].values

    @requires_external_api
    def test_get_cases_live(self, accessor):
        df = accessor.get_cases(disease="Dengue Fever", years=[2020])
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert (df["disease"] == "Dengue Fever").all()
        assert "year" in df.columns
        assert (df["year"] == 2020).all()


class TestSingaporeNEA:
    @pytest.fixture
    def accessor(self):
        from epidatasets.sources.singapore_nea import SingaporeNEAAccessor
        return SingaporeNEAAccessor()

    def test_initialization(self, accessor):
        assert accessor is not None
        assert accessor.source_name == "singapore_nea"

    def test_source_metadata(self, accessor):
        assert "Singapore" in accessor.source_description
        assert "NEA" in accessor.source_description or "National Environment" in accessor.source_description

    def test_list_countries(self, accessor):
        countries = accessor.list_countries()
        assert isinstance(countries, pd.DataFrame)
        assert len(countries) == 1
        assert countries.iloc[0]["country_code"] == "SG"
        assert countries.iloc[0]["country_name"] == "Singapore"

    def test_list_regions(self, accessor):
        regions = accessor.list_regions()
        assert isinstance(regions, pd.DataFrame)
        assert "Central" in regions["region"].values
        assert "has_cases_data" in regions.columns

    def test_dataset_ids_present(self, accessor):
        assert accessor.WEEKLY_CASES_ID.startswith("d_")
        assert accessor.DENGUE_CLUSTERS_ID.startswith("d_")
        assert "Central" in accessor.REGIONAL_CASES_IDS
        assert "Central" in accessor.BREEDING_HABITATS_IDS

    def test_weekly_summary_invalid_by(self, accessor):
        with pytest.raises(ValueError):
            accessor.get_weekly_summary(by="invalid")

    def test_sample_clusters(self, accessor):
        df = accessor._sample_clusters()
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert "case_size" in df.columns
        assert "locality" in df.columns

    def test_parse_nea_date(self, accessor):
        from epidatasets.sources.singapore_nea import _parse_nea_date
        assert _parse_nea_date("20260616150717") == "2026-06-16T15:07:17"
        assert _parse_nea_date(None) is None
        assert _parse_nea_date("notadate") == "notadate"

    @requires_external_api
    def test_get_weekly_cases_live(self, accessor):
        df = accessor.get_weekly_cases(use_cache=False)
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert set(df.columns) >= {"year", "eweek", "type_dengue", "number"}
        assert "Dengue" in df["type_dengue"].values

    @requires_external_api
    def test_get_dengue_clusters_live(self, accessor):
        df = accessor.get_dengue_clusters(use_cache=False)
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert "case_size" in df.columns
        assert "longitude" in df.columns
        assert df["longitude"].notna().any()


class TestMalaysiaMOH:
    @pytest.fixture
    def accessor(self):
        from epidatasets.sources.malaysia_moh import MalaysiaMOHAccessor
        return MalaysiaMOHAccessor()

    def test_initialization(self, accessor):
        assert accessor is not None
        assert accessor.source_name == "malaysia_moh"

    def test_source_metadata(self, accessor):
        assert "Malaysia" in accessor.source_description
        assert "data.gov.my" in accessor.source_url

    def test_list_countries(self, accessor):
        countries = accessor.list_countries()
        assert isinstance(countries, pd.DataFrame)
        assert len(countries) == 1
        assert countries.iloc[0]["country_code"] == "MY"
        assert countries.iloc[0]["country_name"] == "Malaysia"

    def test_list_states(self, accessor):
        states = accessor.list_states()
        assert isinstance(states, pd.DataFrame)
        assert "Malaysia" in states["state"].values
        assert "Selangor" in states["state"].values

    def test_dataset_ids(self, accessor):
        for key in ["covid_cases", "hospital_beds", "std_state",
                     "infant_immunisation", "blood_donations"]:
            assert key in accessor.DATASETS

    def test_cache_dir_created(self, accessor):
        assert accessor.cache_dir.exists()

    @requires_external_api
    def test_get_covid_cases_live(self, accessor):
        df = accessor.get_covid_cases(state="Malaysia",
                                       start_date="2022-01-01",
                                       end_date="2022-01-05")
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert (df["state"] == "Malaysia").all()

    @requires_external_api
    def test_get_hospital_beds_live(self, accessor):
        df = accessor.get_hospital_beds(
            state="Malaysia", hospital_type="all"
        )
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert "beds" in df.columns

    @requires_external_api
    def test_get_std_cases_live(self, accessor):
        df = accessor.get_std_cases(disease="HIV")
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert (df["disease"].str.lower() == "hiv").all()


class TestThailandDDC:
    @pytest.fixture
    def accessor(self):
        from epidatasets.sources.thailand_ddc import ThailandDDCAccessor
        return ThailandDDCAccessor()

    def test_initialization(self, accessor):
        assert accessor is not None
        assert accessor.source_name == "thailand_ddc"

    def test_list_countries(self, accessor):
        countries = accessor.list_countries()
        assert len(countries) == 1
        assert countries.iloc[0]["country_code"] == "TH"

    def test_list_provinces(self, accessor):
        provinces = accessor.list_provinces()
        assert len(provinces) >= 77
        assert "Bangkok" in provinces["province"].values

    def test_list_diseases(self, accessor):
        diseases = accessor.list_diseases()
        assert len(diseases) > 20
        assert "Dengue Total" in diseases["disease"].values

    def test_get_surveillance_data(self, accessor):
        df = accessor.get_surveillance_data(year=2022)
        assert len(df) > 0
        assert set(df.columns) >= {"year", "province", "disease", "cases"}

    def test_get_dengue_cases(self, accessor):
        df = accessor.get_dengue_cases()
        assert "Dengue Total" in df["disease"].values
        assert len(df) > 0

    def test_get_national_summary(self, accessor):
        df = accessor.get_national_summary()
        assert "cases" in df.columns
        assert df["cases"].sum() > 0

    def test_get_provincial_summary(self, accessor):
        df = accessor.get_provincial_summary(disease="Dengue Total")
        assert len(df) >= 77


class TestIndonesiaMOH:
    @pytest.fixture
    def accessor(self):
        from epidatasets.sources.indonesia_moh import IndonesiaMOHAccessor
        return IndonesiaMOHAccessor()

    def test_initialization(self, accessor):
        assert accessor is not None
        assert accessor.source_name == "indonesia_moh"

    def test_list_countries(self, accessor):
        countries = accessor.list_countries()
        assert len(countries) == 1
        assert countries.iloc[0]["country_code"] == "ID"

    def test_list_provinces(self, accessor):
        provinces = accessor.list_provinces()
        assert len(provinces) >= 38
        assert "DKI Jakarta" in provinces["province"].values

    def test_list_diseases(self, accessor):
        diseases = accessor.list_diseases()
        assert len(diseases) >= 20
        assert "Dengue Fever" in diseases["disease"].values

    def test_get_dengue_cases(self, accessor):
        df = accessor.get_dengue_cases()
        assert "Dengue Fever" in df["disease"].values

    def test_get_tuberculosis_cases(self, accessor):
        df = accessor.get_tuberculosis_cases()
        assert "Tuberculosis (all forms)" in df["disease"].values

    def test_get_national_summary(self, accessor):
        df = accessor.get_national_summary()
        assert "cases" in df.columns
        assert df["cases"].sum() > 0


class TestECDCAtlas:
    @pytest.fixture
    def accessor(self):
        from epidatasets.sources.ecdc_atlas import ECDCAtlasAccessor
        return ECDCAtlasAccessor()

    def test_initialization(self, accessor):
        assert accessor is not None
        assert accessor.source_name == "ecdc_atlas"

    def test_list_countries(self, accessor):
        countries = accessor.list_countries()
        assert len(countries) >= 30
        assert "DE" in countries["country_code"].values

    def test_get_available_diseases(self, accessor):
        diseases = accessor.get_available_diseases()
        assert len(diseases) >= 50
        assert "Measles" in diseases["disease"].values

    def test_get_disease_categories(self, accessor):
        cats = accessor.get_disease_categories()
        assert len(cats) >= 7
        assert "vaccine_preventable" in cats["category"].values

    def test_get_disease_data(self, accessor):
        df = accessor.get_disease_data("Measles", years=[2022])
        assert len(df) > 0
        assert (df["disease"] == "Measles").all()

    def test_get_amr_data(self, accessor):
        df = accessor.get_amr_data(pathogen="E. coli")
        assert len(df) > 0
        assert (df["pathogen"] == "E. coli").all()

    def test_get_spatial_data(self, accessor):
        df = accessor.get_spatial_data("Measles")
        assert "longitude" in df.columns
        assert "latitude" in df.columns

    def test_get_summary_statistics(self, accessor):
        df = accessor.get_summary_statistics()
        assert "total_cases" in df.columns
        assert df["total_cases"].sum() > 0

    def test_invalid_disease_raises(self, accessor):
        with pytest.raises(ValueError):
            accessor.get_disease_data("NonExistentDisease")

class TestGoogleEarthEngine:
    @pytest.fixture
    def accessor(self):
        from epidatasets.sources.google_earth_engine import GoogleEarthEngineAccessor
        return GoogleEarthEngineAccessor(project=os.getenv("EE_PROJECT"))

    def test_initialization(self, accessor):
        assert accessor is not None
        assert accessor.source_name == "google_earth_engine"

    @requires_external_api
    def test_list_countries(self, accessor):
        countries = accessor.list_countries()
        assert isinstance(countries, pd.DataFrame)
        assert len(countries) > 100
        assert "country_code" in countries.columns
        assert "country_name" in countries.columns

    @requires_external_api
    def test_get_ndvi_urban_area(self, accessor):
        """Downtown São Paulo: expect NDVI in a valid, low-vegetation range."""
        ndvi = accessor.get_ndvi(
            lon=-46.63, lat=-23.55,
            start_date="2021-03-01", end_date="2021-03-31",
        )
        assert ndvi is not None
        assert -1.0 <= ndvi <= 1.0

    @requires_external_api
    def test_get_built_up_index_forest_vs_urban(self, accessor):
        """NDBI should be lower (more negative) for dense forest than for a dense urban core."""
        forest_ndbi = accessor.get_built_up_index(
            lon=-62.5, lat=-4.0,
            start_date="2021-01-01", end_date="2021-12-31",
        )
        urban_ndbi = accessor.get_built_up_index(
            lon=-46.63, lat=-23.55,
            start_date="2021-03-01", end_date="2021-03-31",
        )
        assert forest_ndbi is not None
        assert urban_ndbi is not None
        assert forest_ndbi < urban_ndbi

    @requires_external_api
    def test_no_imagery_raises_clear_error(self, accessor):
        """A 1-day window over a persistently cloudy region should raise a
        clear ValueError, not a cryptic band-name crash."""
        with pytest.raises(ValueError, match="No Landsat 8 images found"):
            accessor.get_ndvi(
                lon=-62.5, lat=-4.0,
                start_date="2021-03-01", end_date="2021-03-02",
            )

class TestSmoke:
    def test_package_import(self):
        import epidatasets
        assert epidatasets.__version__  # __version__ is a plain string

    def test_base_accessor_import(self):
        from epidatasets._base import BaseAccessor
        assert BaseAccessor is not None

    def test_sources_dir_exists(self):
        from pathlib import Path
        sources_dir = Path(__file__).parent.parent / "src" / "epidatasets" / "sources"
        assert sources_dir.exists()


class TestDiseaseSh:
    """Tests for the disease.sh API accessor.

    Network-free tests use the ``responses`` library to mock the disease.sh
    API.  Live tests are gated behind ``@requires_external_api``.
    """

    @pytest.fixture
    def accessor(self, tmp_path):
        from epidatasets.sources.disease_sh import DiseaseShAccessor

        return DiseaseShAccessor(cache_dir=str(tmp_path / "disease_sh"))

    def test_initialization(self, accessor):
        assert accessor is not None
        assert accessor.source_name == "disease_sh"
        assert "disease.sh" in accessor.source_description
        assert accessor.source_url == "https://disease.sh/"
        assert accessor.cache_dir.exists()

    def test_available_diseases(self, accessor):
        diseases = accessor.get_available_diseases()
        assert isinstance(diseases, pd.DataFrame)
        assert len(diseases) == 2
        assert "covid19" in diseases["disease_key"].values
        assert "influenza" in diseases["disease_key"].values

    def test_influenza_summary(self, accessor):
        summary = accessor.get_influenza_summary()
        assert isinstance(summary, pd.DataFrame)
        assert len(summary) == 3
        assert set(summary["endpoint_key"]) == {
            "ilinet",
            "public_health_lab",
            "clinical_lab",
        }

    @responses.activate
    def test_list_countries(self, accessor):
        responses.add(
            responses.GET,
            "https://disease.sh/v3/covid-19/countries",
            json=[
                {
                    "country": "Afghanistan",
                    "countryInfo": {
                        "iso2": "AF",
                        "iso3": "AFG",
                        "lat": 33,
                        "long": 65,
                    },
                    "cases": 234174,
                },
                {
                    "country": "Brazil",
                    "countryInfo": {
                        "iso2": "BR",
                        "iso3": "BRA",
                        "lat": -14,
                        "long": -51,
                    },
                    "cases": 37700000,
                },
            ],
            status=200,
        )
        countries = accessor.list_countries()
        assert isinstance(countries, pd.DataFrame)
        assert len(countries) == 2
        assert set(countries.columns) >= {
            "country_code",
            "country_name",
            "iso3",
            "lat",
            "long",
        }
        assert "BR" in countries["country_code"].values
        assert "Brazil" in countries["country_name"].values

    @responses.activate
    def test_get_global_totals(self, accessor):
        responses.add(
            responses.GET,
            "https://disease.sh/v3/covid-19/all",
            json={
                "updated": 1783967832683,
                "cases": 704753890,
                "deaths": 7010681,
                "recovered": 675619811,
                "active": 22123398,
                "tests": 7026505313,
                "population": 7944935131,
                "affectedCountries": 231,
            },
            status=200,
        )
        df = accessor.get_global_totals(use_cache=False)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert df.iloc[0]["cases"] == 704753890
        assert df.iloc[0]["deaths"] == 7010681
        assert pd.notna(df.iloc[0]["updated"])

    @responses.activate
    def test_get_country_data_single(self, accessor):
        responses.add(
            responses.GET,
            "https://disease.sh/v3/covid-19/countries/USA",
            json={
                "country": "USA",
                "countryInfo": {"iso2": "US", "iso3": "USA", "lat": 38, "long": -97},
                "cases": 103646975,
                "deaths": 1127928,
                "population": 333000000,
                "updated": 1783967832814,
            },
            status=200,
        )
        df = accessor.get_country_data(country="USA", use_cache=False)
        assert len(df) == 1
        assert df.iloc[0]["country"] == "USA"
        assert df.iloc[0]["country_code"] == "US"
        assert df.iloc[0]["cases"] == 103646975

    @responses.activate
    def test_get_historical_country(self, accessor):
        responses.add(
            responses.GET,
            "https://disease.sh/v3/covid-19/historical/USA",
            json={
                "country": "USA",
                "province": ["mainland"],
                "timeline": {
                    "cases": {"1/1/23": 100, "1/2/23": 110, "1/3/23": 120},
                    "deaths": {"1/1/23": 5, "1/2/23": 6, "1/3/23": 7},
                    "recovered": {"1/1/23": 0, "1/2/23": 0, "1/3/23": 0},
                },
            },
            status=200,
        )
        df = accessor.get_historical(country="USA", lastdays=3, use_cache=False)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
        assert set(df.columns) >= {"country", "date", "cases", "deaths", "recovered"}
        assert (df["country"] == "USA").all()
        # Date parsing from M/D/YY
        assert df["date"].dtype.kind == "M"
        first = df.iloc[0]
        assert first["date"] == pd.Timestamp("2023-01-01")
        assert first["cases"] == 100

    @responses.activate
    def test_get_historical_date_filter(self, accessor):
        responses.add(
            responses.GET,
            "https://disease.sh/v3/covid-19/historical/USA",
            json={
                "country": "USA",
                "province": ["mainland"],
                "timeline": {
                    "cases": {
                        "1/1/23": 100,
                        "1/2/23": 110,
                        "1/3/23": 120,
                        "1/4/23": 130,
                        "1/5/23": 140,
                    },
                    "deaths": {
                        "1/1/23": 5,
                        "1/2/23": 6,
                        "1/3/23": 7,
                        "1/4/23": 8,
                        "1/5/23": 9,
                    },
                    "recovered": {f"1/{d}/23": 0 for d in range(1, 6)},
                },
            },
            status=200,
        )
        df = accessor.get_historical(
            country="USA",
            lastdays=5,
            start_date="2023-01-02",
            end_date="2023-01-04",
            use_cache=False,
        )
        assert len(df) == 3
        assert df["date"].min() == pd.Timestamp("2023-01-02")
        assert df["date"].max() == pd.Timestamp("2023-01-04")

    @responses.activate
    def test_get_historical_global(self, accessor):
        responses.add(
            responses.GET,
            "https://disease.sh/v3/covid-19/historical/all",
            json={
                "cases": {"3/5/23": 676024901, "3/6/23": 676082941},
                "deaths": {"3/5/23": 6877749, "3/6/23": 6878115},
                "recovered": {"3/5/23": 0, "3/6/23": 0},
            },
            status=200,
        )
        df = accessor.get_historical(country=None, lastdays=2, use_cache=False)
        assert len(df) == 2
        assert (df["country"] == "World").all()
        assert df.iloc[0]["cases"] == 676024901

    @responses.activate
    def test_get_vaccine_coverage_global(self, accessor):
        responses.add(
            responses.GET,
            "https://disease.sh/v3/covid-19/vaccine/coverage",
            json=[
                {
                    "total": 13578774356,
                    "daily": 0,
                    "totalPerHundred": 0,
                    "dailyPerMillion": 0,
                    "date": "7/17/25",
                },
                {
                    "total": 13578774356,
                    "daily": 1000,
                    "totalPerHundred": 0,
                    "dailyPerMillion": 0,
                    "date": "7/18/25",
                },
            ],
            status=200,
        )
        df = accessor.get_vaccine_coverage(country=None, lastdays=2, use_cache=False)
        assert len(df) == 2
        assert "total" in df.columns
        assert df["date"].dtype.kind == "M"

    @responses.activate
    def test_get_vaccine_coverage_country(self, accessor):
        responses.add(
            responses.GET,
            "https://disease.sh/v3/covid-19/vaccine/coverage/countries",
            json=[
                {
                    "country": "Afghanistan",
                    "timeline": [
                        {
                            "total": 22964750,
                            "daily": 0,
                            "totalPerHundred": 0,
                            "dailyPerMillion": 0,
                            "date": "7/19/25",
                        },
                    ],
                },
                {
                    "country": "Brazil",
                    "timeline": [
                        {
                            "total": 500000000,
                            "daily": 500,
                            "totalPerHundred": 220,
                            "dailyPerMillion": 2,
                            "date": "7/19/25",
                        },
                    ],
                },
            ],
            status=200,
        )
        df = accessor.get_vaccine_coverage(country="Brazil", lastdays=1, use_cache=False)
        assert len(df) == 1
        assert (df["country"] == "Brazil").all()
        assert df.iloc[0]["total"] == 500000000

    @responses.activate
    def test_get_states(self, accessor):
        responses.add(
            responses.GET,
            "https://disease.sh/v3/covid-19/states",
            json=[
                {
                    "state": "California",
                    "updated": 1783967832172,
                    "cases": 12711918,
                    "deaths": 112443,
                    "population": 39512223,
                },
                {
                    "state": "Texas",
                    "updated": 1783967832172,
                    "cases": 8000000,
                    "deaths": 95000,
                    "population": 30000000,
                },
            ],
            status=200,
        )
        df = accessor.get_states(use_cache=False)
        assert len(df) == 2
        assert "California" in df["state"].values
        assert pd.notna(df.iloc[0]["updated"])

    @responses.activate
    def test_get_influenza_ilinet(self, accessor):
        responses.add(
            responses.GET,
            "https://disease.sh/v3/influenza/CDC/ILINet",
            json={
                "updated": 1783934241274,
                "source": "www.cdc.gov/flu",
                "data": [
                    {
                        "week": "2021 - 40/52",
                        "age 0-4": 13064,
                        "age 5-24": 13042,
                        "totalILI": 39191,
                        "totalPatients": 2010559,
                        "percentUnweightedILI": 1.9,
                        "percentWeightedILI": 2,
                    },
                    {
                        "week": "2021 - 41/52",
                        "age 0-4": 13019,
                        "totalILI": 37217,
                        "totalPatients": 1973817,
                        "percentUnweightedILI": 1.9,
                        "percentWeightedILI": 1.9,
                    },
                ],
            },
            status=200,
        )
        df = accessor.get_influenza_ilinet(use_cache=False)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert "year" in df.columns
        assert "week_num" in df.columns
        assert df.iloc[0]["year"] == 2021
        assert df.iloc[0]["week_num"] == 40
        assert df.iloc[0]["totalILI"] == 39191
        assert df.iloc[0]["source"] == "www.cdc.gov/flu"
        assert pd.notna(df.iloc[0]["updated"])

    @responses.activate
    def test_get_influenza_clinical_lab(self, accessor):
        responses.add(
            responses.GET,
            "https://disease.sh/v3/influenza/CDC/USCL",
            json={
                "updated": 1783934242481,
                "source": "www.cdc.gov/flu",
                "data": [
                    {
                        "week": "2021 - 40/52",
                        "totalA": 38,
                        "totalB": 28,
                        "percentPositiveA": 0.07,
                        "percentPositiveB": 0.05,
                        "totalTests": 49177,
                        "percentPositive": 0.13,
                    },
                ],
            },
            status=200,
        )
        df = accessor.get_influenza_clinical_lab(use_cache=False)
        assert len(df) == 1
        assert df.iloc[0]["totalA"] == 38
        assert df.iloc[0]["totalTests"] == 49177
        assert df.iloc[0]["year"] == 2021

    @responses.activate
    def test_get_country_data_invalid_country_raises_value_error(self, accessor):
        responses.add(
            responses.GET,
            "https://disease.sh/v3/covid-19/countries/Atlantis",
            json={"message": "Country not found or doesn't have any historical data"},
            status=404,
        )
        with pytest.raises(ValueError, match="Unknown country.*Atlantis"):
            accessor.get_country_data("Atlantis")

    @responses.activate
    def test_get_historical_invalid_country_raises_value_error(self, accessor):
        responses.add(
            responses.GET,
            "https://disease.sh/v3/covid-19/historical/Atlantis",
            json={"message": "Country not found or doesn't have any historical data"},
            status=404,
        )
        with pytest.raises(ValueError, match="Unknown country"):
            accessor.get_historical(country="Atlantis")

    @responses.activate
    def test_404_is_not_retried(self, accessor):
        responses.add(
            responses.GET,
            "https://disease.sh/v3/covid-19/countries/Atlantis",
            json={"message": "Country not found"},
            status=404,
        )
        with pytest.raises(ValueError):
            accessor.get_country_data("Atlantis")
        assert len(responses.calls) == 1

    @responses.activate
    def test_network_error_wrapped_in_api_error(self, accessor, monkeypatch):
        from epidatasets.sources.disease_sh import DiseaseShAPIError

        monkeypatch.setattr(
            "epidatasets.sources.disease_sh.time.sleep", lambda s: None
        )
        responses.add(
            responses.GET,
            "https://disease.sh/v3/covid-19/all",
            body=requests.exceptions.ConnectionError("connection refused"),
        )
        with pytest.raises(DiseaseShAPIError) as excinfo:
            accessor.get_global_totals(use_cache=False)
        assert excinfo.value.attempts == 3
        assert excinfo.value.url == "https://disease.sh/v3/covid-19/all"
        assert excinfo.value.status_code is None
        assert len(responses.calls) == 3

    @responses.activate
    def test_server_error_wrapped_in_api_error(self, accessor, monkeypatch):
        from epidatasets.sources.disease_sh import DiseaseShAPIError

        monkeypatch.setattr(
            "epidatasets.sources.disease_sh.time.sleep", lambda s: None
        )
        responses.add(
            responses.GET,
            "https://disease.sh/v3/covid-19/states",
            json={"message": "Internal server error"},
            status=500,
        )
        with pytest.raises(DiseaseShAPIError) as excinfo:
            accessor.get_states(use_cache=False)
        assert excinfo.value.status_code == 500
        assert excinfo.value.attempts == 3

    @responses.activate
    def test_retry_then_success(self, accessor, monkeypatch):
        monkeypatch.setattr(
            "epidatasets.sources.disease_sh.time.sleep", lambda s: None
        )
        responses.add(
            responses.GET,
            "https://disease.sh/v3/covid-19/all",
            json={"message": "Bad gateway"},
            status=502,
        )
        responses.add(
            responses.GET,
            "https://disease.sh/v3/covid-19/all",
            json={"cases": 704753890, "deaths": 7010681},
            status=200,
        )
        df = accessor.get_global_totals(use_cache=False)
        assert len(df) == 1
        assert df.iloc[0]["cases"] == 704753890
        assert len(responses.calls) == 2

    @responses.activate
    def test_cache_write_read_and_bypass(self, accessor):
        responses.add(
            responses.GET,
            "https://disease.sh/v3/covid-19/all",
            json={"cases": 704753890, "deaths": 7010681},
            status=200,
        )
        # First call fetches and caches
        accessor.get_global_totals()
        assert len(responses.calls) == 1
        # Second call is served from cache (no extra HTTP call)
        df = accessor.get_global_totals()
        assert len(responses.calls) == 1
        assert df.iloc[0]["cases"] == 704753890
        # use_cache=False forces a fresh HTTP call
        accessor.get_global_totals(use_cache=False)
        assert len(responses.calls) == 2

    @responses.activate
    def test_cache_ttl_expiry(self, accessor):
        import os
        import time as time_mod

        responses.add(
            responses.GET,
            "https://disease.sh/v3/covid-19/all",
            json={"cases": 704753890},
            status=200,
        )
        accessor.get_global_totals()
        assert len(responses.calls) == 1
        # Backdate the cache file beyond the TTL (default 1 hour)
        cache_file = accessor.cache_dir / "v3_covid-19_all.json"
        stale = time_mod.time() - 2 * 3600
        os.utime(cache_file, (stale, stale))
        accessor.get_global_totals()
        assert len(responses.calls) == 2

    @responses.activate
    def test_get_country_data_list(self, accessor):
        responses.add(
            responses.GET,
            "https://disease.sh/v3/covid-19/countries/Brazil,USA",
            json=[
                {
                    "country": "Brazil",
                    "countryInfo": {"iso2": "BR", "iso3": "BRA"},
                    "cases": 37700000,
                },
                {
                    "country": "USA",
                    "countryInfo": {"iso2": "US", "iso3": "USA"},
                    "cases": 103000000,
                },
            ],
            status=200,
        )
        df = accessor.get_country_data(["Brazil", "USA"])
        assert len(df) == 2
        assert set(df["country"]) == {"Brazil", "USA"}

    @responses.activate
    def test_get_influenza_public_health_lab(self, accessor):
        responses.add(
            responses.GET,
            "https://disease.sh/v3/influenza/CDC/USPHL",
            json={
                "updated": 1783934242481,
                "source": "www.cdc.gov/flu",
                "data": [
                    {
                        "week": "2021 - 40/52",
                        "totalA": 40,
                        "totalB": 12,
                        "totalTested": 300,
                    },
                ],
            },
            status=200,
        )
        df = accessor.get_influenza_public_health_lab(use_cache=False)
        assert len(df) == 1
        assert df.iloc[0]["totalA"] == 40
        assert df.iloc[0]["year"] == 2021
        assert df.iloc[0]["week_num"] == 40

    @requires_external_api
    def test_list_countries_live(self, accessor):
        countries = accessor.list_countries()
        assert isinstance(countries, pd.DataFrame)
        assert len(countries) > 200
        assert "BR" in countries["country_code"].values

    @requires_external_api
    def test_get_global_totals_live(self, accessor):
        df = accessor.get_global_totals()
        assert len(df) == 1
        assert df.iloc[0]["cases"] > 0


# Minimal swagger fixture for DEMAS discovery tests
class TestJapanIDWR:
    """Tests for the Japan IDWR accessor.

    Network-free tests use the ``responses`` library with fixture CSVs
    trimmed from real IDWR weekly reports.  Live tests are gated behind
    ``@requires_external_api``.
    """

    BASE = "https://id-info.jihs.go.jp/en/surveillance/idwr/rapid"

    @pytest.fixture
    def accessor(self, tmp_path):
        from epidatasets.sources.japan_idwr import JapanIDWRAccessor

        return JapanIDWRAccessor(cache_dir=str(tmp_path / "japan_idwr"))

    @staticmethod
    def _fixture(name: str) -> str:
        path = Path(__file__).parent / "fixtures" / "idwr" / name
        return path.read_text(encoding="utf-8")

    def test_initialization(self, accessor):
        assert accessor.source_name == "japan_idwr"
        assert "IDWR" in accessor.source_description
        assert accessor.cache_dir.exists()
        assert len(accessor.PREFECTURES) == 47

    def test_list_countries(self, accessor):
        countries = accessor.list_countries()
        assert countries.iloc[0]["country_code"] == "JP"
        assert countries.iloc[0]["country_name"] == "Japan"

    @responses.activate
    def test_get_available_years(self, accessor):
        responses.add(
            responses.GET,
            f"{self.BASE}/index.html",
            body='<a href="./2015/index.html">2015</a>'
            '<a href="./2023/index.html">2023</a>'
            '<a href="./2026/index.html">2026</a>',
            status=200,
        )
        years = accessor.get_available_years(use_cache=False)
        assert years == [2023, 2026]

    @responses.activate
    def test_get_available_weeks(self, accessor):
        responses.add(
            responses.GET,
            f"{self.BASE}/2026/index.html",
            body='<a href="./01/index.html">01</a>'
            '<a href="./32/index.html">32</a>'
            '<a href="./css/index.html">css</a>',
            status=200,
        )
        weeks = accessor.get_available_weeks(2026, use_cache=False)
        assert weeks == [1, 32]

    @responses.activate
    def test_get_latest_week(self, accessor):
        responses.add(
            responses.GET,
            f"{self.BASE}/index.html",
            body='<a href="./2023/index.html"></a><a href="./2026/index.html"></a>',
            status=200,
        )
        responses.add(
            responses.GET,
            f"{self.BASE}/2026/index.html",
            body='<a href="./31/index.html"></a><a href="./32/index.html"></a>',
            status=200,
        )
        assert accessor.get_latest_week(use_cache=False) == (2026, 32)

    def test_year_before_coverage_raises_value_error(self, accessor):
        with pytest.raises(ValueError, match="before portal coverage"):
            accessor.get_week(2019, 10)

    def test_invalid_week_raises_value_error(self, accessor):
        with pytest.raises(ValueError, match="between 1 and 53"):
            accessor.get_week(2026, 54)

    @responses.activate
    def test_missing_week_raises_data_error(self, accessor):
        responses.add(
            responses.GET,
            f"{self.BASE}/2023/53/zensu53.csv",
            body="Not Found",
            status=404,
        )
        from epidatasets.sources.japan_idwr import JapanIDWRDataError

        with pytest.raises(JapanIDWRDataError, match="No IDWR report for 2023 week 53"):
            accessor.get_week(2023, 53, use_cache=False)

    @responses.activate
    def test_get_week_parses_all_tables(self, accessor):
        for table in ("zensu", "teiten", "teitenari", "teitenrui"):
            responses.add(
                responses.GET,
                f"{self.BASE}/2026/32/{table}32.csv",
                body=self._fixture(f"{table}32.csv"),
                status=200,
            )
        report = accessor.get_week(2026, 32, use_cache=False)

        assert report.year == 2026 and report.week == 32
        assert report.as_of == pd.Timestamp("2026-08-12")

        nd = report.notifiable_diseases
        assert list(nd.columns) == [
            "prefecture", "disease", "current_week", "cumulative",
        ]
        assert set(nd["prefecture"]) == {
            "Hokkaido", "Aomori", "Chiba", "Kyoto", "Kagoshima",
        }
        assert nd["disease"].nunique() == 3
        tb = nd[nd["disease"] == "Tuberculosis"]
        assert tb["current_week"].sum() > 0

        sd = report.sentinel_diseases
        assert list(sd.columns) == [
            "prefecture", "disease", "current_week", "per_sentinel",
        ]
        assert sd["disease"].nunique() == 3

        delayed = report.sentinel_diseases_delayed
        assert delayed["disease"].unique().tolist() == [
            "Acute respiratory infection"
        ]

        cum = report.sentinel_diseases_cumulative
        assert list(cum.columns) == [
            "prefecture", "disease", "cumulative_cases",
            "cumulative_per_sentinel",
        ]

        totals = report.national_totals["notifiable"]["Tuberculosis"]
        assert totals["current_week"] == 249
        assert totals["cumulative"] == 8902

    @responses.activate
    def test_dash_values_become_nan(self, accessor):
        responses.add(
            responses.GET,
            f"{self.BASE}/2026/32/teiten32.csv",
            body=self._fixture("teiten32.csv"),
            status=200,
        )
        df = accessor.get_sentinel_diseases(2026, 32, use_cache=False)
        ahc = df[df["disease"] == "Acute hemorrhagic conjunctivitis"]
        assert ahc["per_sentinel"].isna().sum() >= 1
        assert ahc["current_week"].isna().sum() >= 1
        mumps = df[df["disease"] == "Mumps"]
        assert mumps["current_week"].notna().all()

    def test_invalid_sentinel_table_raises(self, accessor):
        with pytest.raises(ValueError, match="Invalid table"):
            accessor.get_sentinel_diseases(2026, 32, table="bogus")

    def test_resolve_disease_aliases(self, accessor):
        assert accessor.resolve_disease("flu").startswith("Influenza")
        assert accessor.resolve_disease("HFMD") == "Hand, foot and mouth disease"
        assert accessor.resolve_disease("Measles") == "Measles"
        assert accessor.resolve_disease("whooping cough") == "Pertussis"
        with pytest.raises(ValueError, match="Unknown disease"):
            accessor.resolve_disease("unicorn pox")

    def test_resolve_disease_from_dataframe(self, accessor):
        df = pd.DataFrame({"disease": ["Scrub typhus(Tsutsugamushi disease)"]})
        resolved = accessor.resolve_disease("Scrub typhus", df)
        assert resolved.startswith("Scrub typhus")

    def test_prefecture_resolution(self, accessor):
        with pytest.raises(ValueError, match="Unknown prefecture"):
            accessor.get_by_prefecture("Shangri-La", 2026, 32)

    @responses.activate
    def test_get_by_prefecture(self, accessor):
        for table in ("zensu", "teiten", "teitenari", "teitenrui"):
            responses.add(
                responses.GET,
                f"{self.BASE}/2026/32/{table}32.csv",
                body=self._fixture(f"{table}32.csv"),
                status=200,
            )
        report = accessor.get_by_prefecture("kyoto", 2026, 32, use_cache=False)
        assert set(report.notifiable_diseases["prefecture"]) == {"Kyoto"}
        assert len(report.notifiable_diseases) == 3

    @responses.activate
    def test_get_disease_series(self, accessor):
        body = self._fixture("zensu32.csv")
        for week in (31, 32):
            responses.add(
                responses.GET,
                f"{self.BASE}/2026/{week}/zensu{week}.csv",
                body=body.replace("32nd week, 2026", f"{week}th week, 2026"),
                status=200,
            )
        responses.add(
            responses.GET,
            f"{self.BASE}/2026/index.html",
            body='<a href="./31/index.html"></a><a href="./32/index.html"></a>',
            status=200,
        )
        ts = accessor.get_disease_series(
            "tb", start_year=2026, start_week=31, end_year=2026, end_week=32,
            use_cache=False,
        )
        assert set(ts["week"]) == {31, 32}
        assert set(ts.columns) == {
            "year", "week", "prefecture", "disease", "current_week",
            "cumulative",
        }
        assert (ts["disease"] == "Tuberculosis").all()

    def test_get_disease_series_invalid_table(self, accessor):
        with pytest.raises(ValueError, match="table must be"):
            accessor.get_disease_series(
                "measles", start_year=2026, table="bogus"
            )

    @responses.activate
    def test_cache_prevents_refetch(self, accessor):
        responses.add(
            responses.GET,
            f"{self.BASE}/2026/32/teiten32.csv",
            body=self._fixture("teiten32.csv"),
            status=200,
        )
        accessor.get_sentinel_diseases(2026, 32, use_cache=True)
        accessor.get_sentinel_diseases(2026, 32, use_cache=True)
        assert len(responses.calls) == 1

    def test_decode_falls_back_to_cp932(self):
        from epidatasets.sources.japan_idwr import JapanIDWRAccessor

        decoded = JapanIDWRAccessor._decode("麻疹".encode("cp932"))
        assert decoded == "麻疹"

    @requires_external_api
    def test_latest_week_live(self, accessor):
        year, week = accessor.get_latest_week()
        assert year >= 2023
        assert 1 <= week <= 53

    @requires_external_api
    def test_get_week_live(self, accessor):
        year, week = accessor.get_latest_week()
        report = accessor.get_week(year, week, use_cache=False)
        nd = report.notifiable_diseases
        assert nd["prefecture"].nunique() == 47
        assert nd["disease"].nunique() > 50
        assert report.sentinel_diseases["disease"].nunique() >= 19


_DEMAS_SWAGGER = {
    "swagger": "2.0",
    "info": {"title": "DEMAS - API de Dados Abertos"},
    "tags": [
        {"name": "Agravo Arboviroses", "description": "Arboviroses"},
        {"name": "Vacinação", "description": "Vacinação"},
        {"name": "CNES", "description": "CNES"},
    ],
    "paths": {
        "/arboviroses/dengue": {
            "get": {
                "tags": ["Agravo Arboviroses"],
                "summary": "Obtém base de ocorrência de arbovirose Dengue",
                "parameters": [
                    {"name": "nu_ano", "in": "query", "type": "string"},
                    {"name": "limit", "in": "query", "type": "integer"},
                    {"name": "offset", "in": "query", "type": "integer"},
                ],
            }
        },
        "/arboviroses/chikungunya": {
            "get": {
                "tags": ["Agravo Arboviroses"],
                "summary": "Obtém base de ocorrência de arbovirose Chikungunya",
                "parameters": [
                    {"name": "nu_ano", "in": "query", "type": "string"},
                    {"name": "limit", "in": "query", "type": "integer"},
                    {"name": "offset", "in": "query", "type": "integer"},
                ],
            }
        },
        "/vacinacao/doses-aplicadas-pni-2024": {
            "get": {
                "tags": ["Vacinação"],
                "summary": "Dose aplicadas pelo Programa Nacional de Imunizações (PNI) - 2024",
                "parameters": [
                    {"name": "limit", "in": "query", "type": "integer"},
                    {"name": "offset", "in": "query", "type": "integer"},
                ],
            }
        },
        "/cnes/estabelecimentos/{codigo_cnes}": {
            "get": {
                "tags": ["CNES"],
                "summary": "Obtém estabelecimento utilizando o código CNES.",
                "parameters": [
                    {"name": "codigo_cnes", "in": "path", "type": "integer"},
                    {"name": "limit", "in": "query", "type": "integer"},
                    {"name": "offset", "in": "query", "type": "integer"},
                ],
            }
        },
        "/autenticacao/login": {
            "post": {
                "tags": ["Autenticação"],
                "summary": "Obtém access token",
            }
        },
    },
}


class TestDemas:
    """Tests for the DEMAS (Portal de Dados Abertos do SUS) accessor.

    Network-free tests mock the swagger spec and data endpoints via the
    ``responses`` library.  Live tests are gated behind ``@requires_external_api``.
    """

    @pytest.fixture
    def accessor(self, tmp_path):
        from epidatasets.sources.demas import DemasAccessor

        return DemasAccessor(cache_dir=str(tmp_path / "demas"))

    @responses.activate
    def test_initialization(self, accessor):
        responses.add(
            responses.GET,
            "https://apidadosabertos.saude.gov.br/static/swagger.json",
            json=_DEMAS_SWAGGER,
            status=200,
        )
        # Force reload of swagger for this fresh accessor
        accessor._swagger = None
        assert accessor.source_name == "demas"
        assert "DEMAS" in accessor.source_description
        assert accessor.source_url == "https://dadosabertos.saude.gov.br/"
        assert accessor.cache_dir.exists()
        assert accessor.MAX_PAGE_SIZE == 20

    @responses.activate
    def test_list_countries(self, accessor):
        countries = accessor.list_countries()
        assert len(countries) == 1
        assert countries.iloc[0]["country_code"] == "BR"
        assert countries.iloc[0]["country_name"] == "Brazil"

    @responses.activate
    def test_list_domains(self, accessor):
        responses.add(
            responses.GET,
            "https://apidadosabertos.saude.gov.br/static/swagger.json",
            json=_DEMAS_SWAGGER,
            status=200,
        )
        accessor._swagger = None
        domains = accessor.list_domains(use_cache=False)
        assert isinstance(domains, pd.DataFrame)
        assert "Agravo Arboviroses" in domains["domain"].values
        assert "Vacinação" in domains["domain"].values

    @responses.activate
    def test_list_datasets(self, accessor):
        responses.add(
            responses.GET,
            "https://apidadosabertos.saude.gov.br/static/swagger.json",
            json=_DEMAS_SWAGGER,
            status=200,
        )
        accessor._swagger = None
        df = accessor.list_datasets(use_cache=False)
        # 4 GET endpoints (the POST login is excluded)
        assert len(df) == 4
        assert set(df.columns) == {
            "domain",
            "endpoint",
            "summary",
            "has_year_filter",
            "query_params",
        }
        assert "/arboviroses/dengue" in df["endpoint"].values
        dengue = df[df["endpoint"] == "/arboviroses/dengue"].iloc[0]
        assert dengue["domain"] == "Agravo Arboviroses"
        assert bool(dengue["has_year_filter"]) is True
        # PNI 2024 has no nu_ano filter
        pni = df[df["endpoint"] == "/vacinacao/doses-aplicadas-pni-2024"].iloc[0]
        assert bool(pni["has_year_filter"]) is False

    @responses.activate
    def test_list_datasets_domain_filter(self, accessor):
        responses.add(
            responses.GET,
            "https://apidadosabertos.saude.gov.br/static/swagger.json",
            json=_DEMAS_SWAGGER,
            status=200,
        )
        accessor._swagger = None
        df = accessor.list_datasets(domain="Agravo Arboviroses", use_cache=False)
        assert len(df) == 2
        assert (df["domain"] == "Agravo Arboviroses").all()

    @responses.activate
    def test_search_datasets(self, accessor):
        responses.add(
            responses.GET,
            "https://apidadosabertos.saude.gov.br/static/swagger.json",
            json=_DEMAS_SWAGGER,
            status=200,
        )
        accessor._swagger = None
        matches = accessor.search_datasets("dengue", use_cache=False)
        assert len(matches) == 1
        assert matches.iloc[0]["endpoint"] == "/arboviroses/dengue"

    @responses.activate
    def test_search_datasets_portuguese(self, accessor):
        responses.add(
            responses.GET,
            "https://apidadosabertos.saude.gov.br/static/swagger.json",
            json=_DEMAS_SWAGGER,
            status=200,
        )
        accessor._swagger = None
        matches = accessor.search_datasets("vacinação", use_cache=False)
        assert len(matches) == 1
        assert matches.iloc[0]["endpoint"] == "/vacinacao/doses-aplicadas-pni-2024"

    @responses.activate
    def test_get_dataset_single_page(self, accessor):
        responses.add(
            responses.GET,
            "https://apidadosabertos.saude.gov.br/arboviroses/dengue",
            json={"parametros": [{"id_agravo": "A90", "nu_ano": "2024", "sg_uf": "RJ"}]},
            status=200,
        )
        df = accessor.get_dataset("/arboviroses/dengue", year=2024, use_cache=False)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert df.iloc[0]["id_agravo"] == "A90"
        assert df.iloc[0]["sg_uf"] == "RJ"
        # Verify the year filter was sent as nu_ano
        sent_params = responses.calls[0].request.params
        assert sent_params["nu_ano"] == "2024"

    @responses.activate
    def test_get_dataset_varied_response_key(self, accessor):
        """The response list key varies per endpoint; verify auto-extraction."""
        responses.add(
            responses.GET,
            "https://apidadosabertos.saude.gov.br/cnes/tipounidades",
            json={"tipos_unidade": [{"codigo": 1, "nome": "Hospital"}]},
            status=200,
        )
        df = accessor.get_dataset("/cnes/tipounidades", use_cache=False)
        assert len(df) == 1
        assert df.iloc[0]["nome"] == "Hospital"

    @responses.activate
    def test_get_dataset_limit_capped(self, accessor):
        """The accessor must enforce the 20-record server cap."""
        responses.add(
            responses.GET,
            "https://apidadosabertos.saude.gov.br/arboviroses/dengue",
            json={"parametros": []},
            status=200,
        )
        accessor.get_dataset("/arboviroses/dengue", limit=500, use_cache=False)
        sent_params = responses.calls[0].request.params
        assert sent_params["limit"] == "20"

    @responses.activate
    def test_get_dataset_path_params(self, accessor):
        """Path parameters like {codigo_cnes} are substituted."""
        responses.add(
            responses.GET,
            "https://apidadosabertos.saude.gov.br/cnes/estabelecimentos/12345",
            json={"estabelecimento": [{"codigo_cnes": 12345, "nome": "Hospital X"}]},
            status=200,
        )
        df = accessor.get_dataset(
            "/cnes/estabelecimentos/{codigo_cnes}",
            path_params={"codigo_cnes": 12345},
            use_cache=False,
        )
        assert len(df) == 1
        assert df.iloc[0]["codigo_cnes"] == 12345

    @responses.activate
    def test_get_dataset_all_pagination(self, accessor):
        """get_dataset_all pages until a short page is returned."""
        # Page 0 and 1 are full (20 records), page 2 is partial (5)
        full_page = {"parametros": [{"id": i} for i in range(20)]}
        short_page = {"parametros": [{"id": i} for i in range(5)]}

        # Use responses with multiple registrations keyed by query params
        responses.add(
            responses.GET,
            "https://apidadosabertos.saude.gov.br/arboviroses/dengue",
            json=full_page,
            status=200,
            match=[responses.matchers.query_param_matcher({"limit": "20", "offset": "0", "nu_ano": "2024"})],
        )
        responses.add(
            responses.GET,
            "https://apidadosabertos.saude.gov.br/arboviroses/dengue",
            json=full_page,
            status=200,
            match=[responses.matchers.query_param_matcher({"limit": "20", "offset": "1", "nu_ano": "2024"})],
        )
        responses.add(
            responses.GET,
            "https://apidadosabertos.saude.gov.br/arboviroses/dengue",
            json=short_page,
            status=200,
            match=[responses.matchers.query_param_matcher({"limit": "20", "offset": "2", "nu_ano": "2024"})],
        )
        df = accessor.get_dataset_all(
            "/arboviroses/dengue", year=2024, use_cache=False
        )
        assert len(df) == 45  # 20 + 20 + 5
        assert len(responses.calls) == 3

    @responses.activate
    def test_get_dataset_all_max_pages(self, accessor):
        """max_pages caps the number of requests."""
        full_page = {"parametros": [{"id": i} for i in range(20)]}
        responses.add(
            responses.GET,
            "https://apidadosabertos.saude.gov.br/arboviroses/dengue",
            json=full_page,
            status=200,
            match=[responses.matchers.query_param_matcher({"limit": "20", "offset": "0"})],
        )
        responses.add(
            responses.GET,
            "https://apidadosabertos.saude.gov.br/arboviroses/dengue",
            json=full_page,
            status=200,
            match=[responses.matchers.query_param_matcher({"limit": "20", "offset": "1"})],
        )
        df = accessor.get_dataset_all(
            "/arboviroses/dengue", max_pages=2, use_cache=False
        )
        assert len(df) == 40
        assert len(responses.calls) == 2

    @responses.activate
    def test_get_arbovirose(self, accessor):
        responses.add(
            responses.GET,
            "https://apidadosabertos.saude.gov.br/arboviroses/chikungunya",
            json={"parametros": [{"id_agravo": "A92.0"}]},
            status=200,
        )
        df = accessor.get_arbovirose(disease="chikungunya", use_cache=False)
        assert len(df) == 1
        assert df.iloc[0]["id_agravo"] == "A92.0"

    @responses.activate
    def test_get_vacinacao_pni(self, accessor):
        responses.add(
            responses.GET,
            "https://apidadosabertos.saude.gov.br/vacinacao/doses-aplicadas-pni-2024",
            json={"doses_aplicadas_pni": [{"vacina": "COVID-19", "dose": 1}]},
            status=200,
        )
        df = accessor.get_vacinacao_pni(year=2024, use_cache=False)
        assert len(df) == 1
        assert df.iloc[0]["vacina"] == "COVID-19"

    def test_get_vacinacao_pni_invalid_year(self, accessor):
        with pytest.raises(ValueError):
            accessor.get_vacinacao_pni(year=2019)
        with pytest.raises(ValueError):
            accessor.get_vacinacao_pni(year=2027)

    def test_get_sindrome_gripal_invalid_year(self, accessor):
        with pytest.raises(ValueError):
            accessor.get_sindrome_gripal(year=2024)

    def test_extract_records_helper(self):
        from epidatasets.sources.demas import DemasAccessor

        assert DemasAccessor._extract_records({"parametros": [{"a": 1}]}) == [{"a": 1}]
        assert DemasAccessor._extract_records({"doses_aplicadas_pni": [{"b": 2}]}) == [
            {"b": 2}
        ]
        assert DemasAccessor._extract_records([{"c": 3}]) == [{"c": 3}]
        assert DemasAccessor._extract_records({"no": "list"}) == []
        assert DemasAccessor._extract_records(None) == []

    def test_fill_path_params_helper(self):
        from epidatasets.sources.demas import DemasAccessor

        assert (
            DemasAccessor._fill_path_params(
                "/cnes/estabelecimentos/{codigo_cnes}", {"codigo_cnes": 12345}
            )
            == "/cnes/estabelecimentos/12345"
        )
        assert (
            DemasAccessor._fill_path_params("/arboviroses/dengue", None)
            == "/arboviroses/dengue"
        )

    @requires_external_api
    def test_list_datasets_live(self, accessor):
        accessor._swagger = None
        df = accessor.list_datasets(use_cache=False)
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 50
        assert "/arboviroses/dengue" in df["endpoint"].values

    @requires_external_api
    def test_get_dataset_live(self, accessor):
        df = accessor.get_dataset("/arboviroses/dengue", year=2024, use_cache=False)
        assert isinstance(df, pd.DataFrame)
        assert not df.empty


# Sample GMPD main CSV for mocked tests (columns match the real schema).
_GMPD_MAIN_CSV = (
    "Group,HostReportedName,HostCorrectedName,HostOrder,HostFamily,HostEnvironment,"
    "ParasiteReportedName,ParasiteCorrectedName,HasBinomialName,ParType,ParPhylum,"
    "ParClass,Citation,LocationName,Longitude,Latitude,PopulationType,SamplingBasis,"
    "SampleNotes,Prevalence,HostsSampled,HostSex,HostAge,Intensity,IntensityMeasure,"
    "NativeRange,NumSamples,SamplingType\n"
    "carnivores,Acinonyx jubatus,Acinonyx jubatus,Carnivora,Felidae,terrestrial,"
    "Feline coronavirus,Alphacoronavirus Alphacoronavirus 1,yes,Virus,RNA virus,ss+,"
    "Kennedy et al. 2003,Namibia and South Africa,18.49,-22.96,WN,Animals,NA,0.581,"
    "43,NA,NA,,NA,Yes,43,Serology\n"
    "carnivores,Acinonyx jubatus,Acinonyx jubatus,Carnivora,Felidae,terrestrial,"
    "Feline coronavirus,Alphacoronavirus Alphacoronavirus 1,yes,Virus,RNA virus,ss+,"
    "Kennedy et al. 2003,Namibia and South Africa,18.49,-22.96,WN,Animals,NA,0.163,"
    "43,NA,NA,,NA,Yes,43,PCR\n"
    "primates,Pan troglodytes,Pan troglodytes,Primates,Hominidae,terrestrial,"
    "Plasmodium falciparum,Plasmodium falciparum,yes,Protozoa,Apicomplexa,Aconoidasica,"
    "Liu et al. 2010,Cameroon,11.50,3.87,WN,Animals,NA,0.25,120,F,Adult,NA,NA,Yes,"
    "120,Blood smear\n"
    "primates,Gorilla gorilla,Gorilla gorilla,Primates,Hominidae,terrestrial,"
    "Strongyloides fulleborni,Strongyloides fulleborni,yes,Helminth,Nematoda,"
    "Chromadorea,Hasegawa et al. 2010,NA,NA,NA,WN,Faecal,NA,0.75,40,M,Adult,3.2,epg,"
    "Yes,40,Faecal\n"
    "ungulates,Bos taurus,Bos taurus,Artiodactyla,Bovidae,terrestrial,"
    "Bacillus anthracis,Bacillus anthracis,yes,Bacteria,Firmicutes,Bacilli,"
    "Hugh-Jones et al. 2008,NA,NA,NA,WN,Animals,NA,NA,NA,NA,NA,,No,NA,NA,Culture\n"
)


class TestGMPD:
    """Tests for the Global Mammal Parasite Database (GMPD) accessor.

    Network-free tests mock the GMPD main CSV via the ``responses`` library.
    Live tests are gated behind ``@requires_external_api``.
    """

    @pytest.fixture
    def accessor(self, tmp_path):
        from epidatasets.sources.gmpd import GMPDAccessor

        return GMPDAccessor(cache_dir=str(tmp_path / "gmpd"))

    def test_initialization(self, accessor):
        assert accessor is not None
        assert accessor.source_name == "gmpd"
        assert "Global Mammal Parasite Database" in accessor.source_description
        assert accessor.source_url == "https://parasites.nunn-lab.org/"
        assert accessor.cache_dir.exists()

    def test_host_groups_constant(self, accessor):
        assert "primates" in accessor.HOST_GROUPS
        assert "carnivores" in accessor.HOST_GROUPS
        assert "ungulates" in accessor.HOST_GROUPS

    def test_list_host_groups(self, accessor):
        groups = accessor.list_host_groups()
        assert isinstance(groups, pd.DataFrame)
        assert len(groups) == 3
        assert set(groups["group"]) == {"Primates", "Carnivores", "Ungulates"}

    def test_list_datasets(self, accessor):
        datasets = accessor.list_datasets()
        assert isinstance(datasets, pd.DataFrame)
        assert "GMPD_main" in datasets["dataset"].values
        main = datasets[datasets["dataset"] == "GMPD_main"].iloc[0]
        assert bool(main["available"]) is True
        assert main["method"] == "get_records"

    def test_column_map_keys(self, accessor):
        # Every canonical column maps to a snake_case name
        for raw in ("Group", "HostCorrectedName", "ParType", "Citation", "Longitude"):
            assert raw in accessor.COLUMN_MAP

    @responses.activate
    def test_list_countries(self, accessor):
        responses.add(
            responses.GET,
            "https://raw.githubusercontent.com/globalbioticinteractions/"
            "global-mammal-parasite-database/master/GMPD_main.csv",
            body=_GMPD_MAIN_CSV,
            status=200,
            content_type="text/csv",
        )
        countries = accessor.list_countries(use_cache=False)
        assert isinstance(countries, pd.DataFrame)
        assert {"country_code", "country_name", "record_count"}.issubset(
            countries.columns
        )
        # "NA" location is excluded; two unique localities remain
        assert len(countries) == 2
        assert "Namibia and South Africa" in countries["country_name"].values
        assert countries.iloc[0]["record_count"] == 2  # most frequent

    @responses.activate
    def test_get_records_all(self, accessor):
        responses.add(
            responses.GET,
            "https://raw.githubusercontent.com/globalbioticinteractions/"
            "global-mammal-parasite-database/master/GMPD_main.csv",
            body=_GMPD_MAIN_CSV,
            status=200,
            content_type="text/csv",
        )
        df = accessor.get_records(use_cache=False)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 5
        # Columns are normalized to snake_case
        assert "host_corrected_name" in df.columns
        assert "parasite_type" in df.columns
        assert "group" in df.columns
        # group is title-cased
        assert set(df["group"]) <= {"Primates", "Carnivores", "Ungulates"}
        # numeric coercion
        assert df["hosts_sampled"].dtype.kind in {"i", "u", "f"}
        assert df["longitude"].dtype.kind in {"i", "u", "f"}

    @responses.activate
    def test_get_records_filter_group(self, accessor):
        responses.add(
            responses.GET,
            "https://raw.githubusercontent.com/globalbioticinteractions/"
            "global-mammal-parasite-database/master/GMPD_main.csv",
            body=_GMPD_MAIN_CSV,
            status=200,
            content_type="text/csv",
        )
        df = accessor.get_records(group="Primates", use_cache=False)
        assert (df["group"] == "Primates").all()
        assert len(df) == 2
        # case-insensitive filtering
        df2 = accessor.get_records(group="primates", use_cache=False)
        assert (df2["group"] == "Primates").all()

    @responses.activate
    def test_get_records_filter_parasite_type(self, accessor):
        responses.add(
            responses.GET,
            "https://raw.githubusercontent.com/globalbioticinteractions/"
            "global-mammal-parasite-database/master/GMPD_main.csv",
            body=_GMPD_MAIN_CSV,
            status=200,
            content_type="text/csv",
        )
        df = accessor.get_records(parasite_type="Virus", use_cache=False)
        assert len(df) == 2
        assert (df["parasite_type"] == "Virus").all()

    @responses.activate
    def test_get_records_has_coordinates(self, accessor):
        responses.add(
            responses.GET,
            "https://raw.githubusercontent.com/globalbioticinteractions/"
            "global-mammal-parasite-database/master/GMPD_main.csv",
            body=_GMPD_MAIN_CSV,
            status=200,
            content_type="text/csv",
        )
        geo = accessor.get_records(has_coordinates=True, use_cache=False)
        assert geo["longitude"].notna().all()
        assert len(geo) == 3
        no_geo = accessor.get_records(has_coordinates=False, use_cache=False)
        assert no_geo["longitude"].isna().all()

    @responses.activate
    def test_get_records_filter_host_and_location(self, accessor):
        responses.add(
            responses.GET,
            "https://raw.githubusercontent.com/globalbioticinteractions/"
            "global-mammal-parasite-database/master/GMPD_main.csv",
            body=_GMPD_MAIN_CSV,
            status=200,
            content_type="text/csv",
        )
        df = accessor.get_records(host="Pan troglodytes", use_cache=False)
        assert len(df) == 1
        assert df.iloc[0]["host_corrected_name"] == "Pan troglodytes"

        loc = accessor.get_records(location="Cameroon", use_cache=False)
        assert len(loc) == 1
        assert loc.iloc[0]["location_name"] == "Cameroon"

    @responses.activate
    def test_list_hosts(self, accessor):
        responses.add(
            responses.GET,
            "https://raw.githubusercontent.com/globalbioticinteractions/"
            "global-mammal-parasite-database/master/GMPD_main.csv",
            body=_GMPD_MAIN_CSV,
            status=200,
            content_type="text/csv",
        )
        hosts = accessor.list_hosts(use_cache=False)
        assert isinstance(hosts, pd.DataFrame)
        assert "host" in hosts.columns
        assert "record_count" in hosts.columns
        assert "Acinonyx jubatus" in hosts["host"].values
        # Acinonyx jubatus has 2 records -> should rank first
        assert hosts.iloc[0]["host"] == "Acinonyx jubatus"
        assert hosts.iloc[0]["record_count"] == 2

    @responses.activate
    def test_list_parasites(self, accessor):
        responses.add(
            responses.GET,
            "https://raw.githubusercontent.com/globalbioticinteractions/"
            "global-mammal-parasite-database/master/GMPD_main.csv",
            body=_GMPD_MAIN_CSV,
            status=200,
            content_type="text/csv",
        )
        parasites = accessor.list_parasites(parasite_type="Virus", use_cache=False)
        assert isinstance(parasites, pd.DataFrame)
        assert "parasite" in parasites.columns
        assert len(parasites) == 1
        assert parasites.iloc[0]["record_count"] == 2

    @responses.activate
    def test_list_parasite_types(self, accessor):
        responses.add(
            responses.GET,
            "https://raw.githubusercontent.com/globalbioticinteractions/"
            "global-mammal-parasite-database/master/GMPD_main.csv",
            body=_GMPD_MAIN_CSV,
            status=200,
            content_type="text/csv",
        )
        types = accessor.list_parasite_types(use_cache=False)
        assert isinstance(types, pd.DataFrame)
        assert "parasite_type" in types.columns
        assert "record_count" in types.columns
        # Virus has 2 records and is the most frequent
        assert types.iloc[0]["parasite_type"] == "Virus"
        assert types.iloc[0]["record_count"] == 2

    @responses.activate
    def test_get_interactions(self, accessor):
        responses.add(
            responses.GET,
            "https://raw.githubusercontent.com/globalbioticinteractions/"
            "global-mammal-parasite-database/master/GMPD_main.csv",
            body=_GMPD_MAIN_CSV,
            status=200,
            content_type="text/csv",
        )
        interactions = accessor.get_interactions(use_cache=False)
        assert isinstance(interactions, pd.DataFrame)
        assert {"host_corrected_name", "parasite_corrected_name", "record_count"}.issubset(
            interactions.columns
        )
        # Acinonyx jubatus <-> Alphacoronavirus is supported by 2 records
        ace = interactions[
            interactions["host_corrected_name"] == "Acinonyx jubatus"
        ]
        assert len(ace) == 1
        assert ace.iloc[0]["record_count"] == 2
        assert "citations" in interactions.columns

    @responses.activate
    def test_get_summary_statistics(self, accessor):
        responses.add(
            responses.GET,
            "https://raw.githubusercontent.com/globalbioticinteractions/"
            "global-mammal-parasite-database/master/GMPD_main.csv",
            body=_GMPD_MAIN_CSV,
            status=200,
            content_type="text/csv",
        )
        summary = accessor.get_summary_statistics(use_cache=False)
        assert isinstance(summary, pd.DataFrame)
        assert len(summary) == 1
        row = summary.iloc[0]
        assert row["total_records"] == 5
        assert row["unique_hosts"] == 4
        assert row["unique_citations"] == 4
        assert row["georeferenced_records"] == 3
        assert row["host_groups"] == 3

    @responses.activate
    def test_search_records(self, accessor):
        responses.add(
            responses.GET,
            "https://raw.githubusercontent.com/globalbioticinteractions/"
            "global-mammal-parasite-database/master/GMPD_main.csv",
            body=_GMPD_MAIN_CSV,
            status=200,
            content_type="text/csv",
        )
        # Match parasite name substring
        df = accessor.search_records("Plasmodium", use_cache=False)
        assert len(df) == 1
        assert df.iloc[0]["parasite_corrected_name"] == "Plasmodium falciparum"
        # Match host name substring (case-insensitive)
        df2 = accessor.search_records("gorilla", use_cache=False)
        assert len(df2) == 1
        assert df2.iloc[0]["host_corrected_name"] == "Gorilla gorilla"

    @responses.activate
    def test_cache_write_and_read(self, accessor):
        responses.add(
            responses.GET,
            "https://raw.githubusercontent.com/globalbioticinteractions/"
            "global-mammal-parasite-database/master/GMPD_main.csv",
            body=_GMPD_MAIN_CSV,
            status=200,
            content_type="text/csv",
        )
        # First call downloads and writes the cache
        accessor.get_records(use_cache=True)
        cache_file = accessor.cache_dir / "GMPD_main.csv"
        assert cache_file.exists()
        # Only one network call happened
        assert len(responses.calls) == 1

        # Second call should be served from cache (no new network call)
        accessor.get_records(use_cache=True)
        assert len(responses.calls) == 1

    def test_clear_cache(self, tmp_path):
        from epidatasets.sources.gmpd import GMPDAccessor

        acc = GMPDAccessor(cache_dir=str(tmp_path / "gmpd2"))
        cache_file = acc.cache_dir / "GMPD_main.csv"
        cache_file.write_text("dummy")
        assert cache_file.exists()
        acc.clear_cache()
        assert not cache_file.exists()

    @requires_external_api
    def test_get_records_live(self, accessor):
        df = accessor.get_records(group="Primates", parasite_type="Virus", use_cache=True)
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert (df["group"] == "Primates").all()

    @requires_external_api
    def test_get_summary_statistics_live(self, accessor):
        summary = accessor.get_summary_statistics(use_cache=True)
        assert isinstance(summary, pd.DataFrame)
        assert summary.iloc[0]["total_records"] > 1000


# ---------------------------------------------------------------------------
# GISAID Tests
# ---------------------------------------------------------------------------

GISAID_TEST_CREDS = {"username": "test_user", "password": "test_pass"}


class TestGISAID:
    """Tests for GISAID accessor.

    Tests use explicit credentials to avoid triggering the credential
    discovery flow which would raise ValueError without env vars/config.
    Browser automation tests (query, download) are gated behind
    @requires_external_api since they need Playwright + real credentials.
    """

    @pytest.fixture
    def accessor(self, tmp_path):
        from epidatasets.sources.gisaid import GISAIDAccessor
        acc = GISAIDAccessor(
            database="EpiCoV",
            username="test_user",
            password="test_pass",
            cache_dir=str(tmp_path / "gisaid"),
        )
        yield acc
        acc.close()

    @pytest.fixture
    def accessor_epiflu(self, tmp_path):
        from epidatasets.sources.gisaid import GISAIDAccessor
        acc = GISAIDAccessor(
            database="EpiFlu",
            username="test_user",
            password="test_pass",
            cache_dir=str(tmp_path / "gisaid_flu"),
        )
        yield acc
        acc.close()

    def test_initialization(self, accessor):
        assert accessor.source_name == "gisaid"
        assert accessor.database == "EpiCoV"
        assert accessor.cache_dir.exists()
        assert "GISAID" in accessor.source_description

    def test_initialization_epiflu(self, accessor_epiflu):
        assert accessor_epiflu.database == "EpiFlu"

    def test_initialization_epipox(self, tmp_path):
        from epidatasets.sources.gisaid import GISAIDAccessor
        acc = GISAIDAccessor(
            database="EpiPox",
            username="test_user",
            password="test_pass",
            cache_dir=str(tmp_path / "gisaid_pox"),
        )
        try:
            assert acc.database == "EpiPox"
        finally:
            acc.close()

    def test_initialization_epirsv(self, tmp_path):
        from epidatasets.sources.gisaid import GISAIDAccessor
        acc = GISAIDAccessor(
            database="EpiRSV",
            username="test_user",
            password="test_pass",
            cache_dir=str(tmp_path / "gisaid_rsv"),
        )
        try:
            assert acc.database == "EpiRSV"
        finally:
            acc.close()

    def test_initialization_epiarbo(self, tmp_path):
        from epidatasets.sources.gisaid import GISAIDAccessor
        acc = GISAIDAccessor(
            database="EpiArbo",
            username="test_user",
            password="test_pass",
            cache_dir=str(tmp_path / "gisaid_arbo"),
        )
        try:
            assert acc.database == "EpiArbo"
        finally:
            acc.close()

    def test_invalid_database(self, tmp_path):
        from epidatasets.sources.gisaid import GISAIDAccessor
        with pytest.raises(ValueError, match="not supported"):
            GISAIDAccessor(
                database="InvalidDB",
                username="test_user",
                password="test_pass",
                cache_dir=str(tmp_path / "gisaid_invalid"),
            )

    def test_list_databases(self, accessor):
        dbs = accessor.list_databases()
        assert isinstance(dbs, pd.DataFrame)
        assert len(dbs) == 5
        assert "EpiCoV" in dbs["database"].values
        assert "EpiFlu" in dbs["database"].values
        assert "EpiPox" in dbs["database"].values
        assert "EpiRSV" in dbs["database"].values
        assert "EpiArbo" in dbs["database"].values
        assert "description" in dbs.columns
        assert "pathogens" in dbs.columns

    def test_list_countries(self, accessor):
        countries = accessor.list_countries()
        assert isinstance(countries, pd.DataFrame)
        assert len(countries) > 190
        assert "country_code" in countries.columns
        assert "country_name" in countries.columns
        assert "region" in countries.columns
        assert "BRA" in countries["country_code"].values
        assert "USA" in countries["country_code"].values

    def test_get_regions(self, accessor):
        regions = accessor.get_regions()
        assert isinstance(regions, list)
        assert len(regions) == 6
        assert "South America" in regions
        assert "Europe" in regions
        assert "Asia" in regions
        assert "Africa" in regions
        assert "North America" in regions
        assert "Oceania" in regions

    def test_get_countries_by_region_valid(self, accessor):
        df = accessor.get_countries_by_region("South America")
        assert isinstance(df, pd.DataFrame)
        assert "BRA" in df["country_code"].values
        assert "Brazil" in df["country_name"].values

    def test_get_countries_by_region_invalid(self, accessor):
        with pytest.raises(ValueError, match="not found"):
            accessor.get_countries_by_region("Atlantis")

    def test_credential_loading_from_env(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GISAID_USERNAME", "env_user")
        monkeypatch.setenv("GISAID_PASSWORD", "env_pass")
        from epidatasets.sources.gisaid import GISAIDAccessor
        acc = GISAIDAccessor(
            database="EpiCoV", cache_dir=str(tmp_path / "gisaid_env")
        )
        try:
            assert acc.username == "env_user"
            assert acc.password == "env_pass"
        finally:
            acc.close()

    def test_credential_loading_from_config(self, tmp_path):
        config_dir = tmp_path / "epi_data"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "gisaid.json"
        config_file.write_text(
            '{"username": "config_user", "password": "config_pass"}'
        )
        from epidatasets.sources.gisaid import GISAIDAccessor
        acc = GISAIDAccessor(
            database="EpiCoV",
            config_path=str(config_file),
            cache_dir=str(tmp_path / "gisaid_cfg"),
        )
        try:
            assert acc.username == "config_user"
            assert acc.password == "config_pass"
        finally:
            acc.close()

    def test_missing_credentials_non_interactive(self, monkeypatch, tmp_path):
        monkeypatch.delenv("GISAID_USERNAME", raising=False)
        monkeypatch.delenv("GISAID_PASSWORD", raising=False)
        from epidatasets.sources.gisaid import GISAIDAccessor
        with pytest.raises((ValueError, OSError)):
            GISAIDAccessor(
                database="EpiCoV",
                cache_dir=str(tmp_path / "gisaid_noauth"),
            )

    def test_constructor_credentials_override(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GISAID_USERNAME", "env_user")
        monkeypatch.setenv("GISAID_PASSWORD", "env_pass")
        from epidatasets.sources.gisaid import GISAIDAccessor
        acc = GISAIDAccessor(
            database="EpiCoV",
            username="explicit_user",
            password="explicit_pass",
            cache_dir=str(tmp_path / "gisaid_override"),
        )
        try:
            assert acc.username == "explicit_user"
            assert acc.password == "explicit_pass"
        finally:
            acc.close()

    def test_info(self, accessor):
        info_str = accessor.info()
        assert "EpiCoV" in info_str
        assert "GISAID" in info_str
        assert "5,000" in info_str

    def test_info_for_different_database(self, accessor_epiflu):
        info_str = accessor_epiflu.info()
        assert "EpiFlu" in info_str
        assert "Influenza" in info_str

    def test_countries_dataframe_structure(self, accessor):
        df = accessor.list_countries()
        assert df["country_code"].str.len().between(2, 3).all()
        assert df["country_name"].notna().all()
        assert df["region"].notna().all()
        regions = df["region"].unique()
        assert len(regions) == 6

    def test_worker_thread_runs_in_separate_thread(self, accessor):
        import threading

        main_tid = threading.get_ident()

        def _get_tid():
            return threading.get_ident()

        worker_tid = accessor._worker(_get_tid)
        assert worker_tid != main_tid, (
            "Worker must run in a separate thread from main"
        )

    def test_worker_thread_returns_result(self, accessor):
        result = accessor._worker(lambda x, y: x + y, 10, 32)
        assert result == 42

    def test_worker_thread_propagates_exceptions(self, accessor):
        with pytest.raises(ValueError, match="test error"):
            accessor._worker(lambda: (_ for _ in ()).throw(ValueError("test error")))

    def test_jupyter_asyncio_compatibility(self, accessor):
        """Simulate Jupyter's asyncio event loop and verify the worker
        thread still functions correctly."""
        import asyncio

        async def _with_running_loop():
            main_tid = id(asyncio.get_running_loop())

            def _check():
                # Verify we can get a result from the worker while
                # an asyncio loop is running on the main thread
                return "ok"

            result = accessor._worker(_check)
            return result, main_tid

        loop = asyncio.new_event_loop()
        try:
            result, _ = loop.run_until_complete(_with_running_loop())
            assert result == "ok"
        finally:
            loop.close()

    @requires_external_api
    def test_query_live(self):
        import os

        from epidatasets.sources.gisaid import GISAIDAccessor

        username = os.getenv("GISAID_USERNAME")
        password = os.getenv("GISAID_PASSWORD")
        if not username or not password:
            pytest.skip("GISAID credentials not set")
        acc = GISAIDAccessor(database="EpiCoV", username=username, password=password)
        try:
            df = acc.query(location="Brazil", nrows=10)
            assert isinstance(df, pd.DataFrame)
        finally:
            acc.close()


class TestOpenDataSUS:
    """Tests for the OpenDataSUS catalog accessor.

    Network-free tests mock the portal's Next.js data endpoints via
    ``responses``.  Live tests are gated behind ``@requires_external_api``.
    """

    BUILD_ID = "testbuild123"
    BASE = "https://dadosabertos.saude.gov.br"

    @pytest.fixture
    def accessor(self, tmp_path):
        from epidatasets.sources.opendatasus import OpenDataSUSAccessor

        return OpenDataSUSAccessor(cache_dir=str(tmp_path / "opendatasus"))

    @staticmethod
    def _mock_homepage():
        next_data = json.dumps({"buildId": TestOpenDataSUS.BUILD_ID})
        html = (
            '<script id="__NEXT_DATA__" type="application/json">'
            f"{next_data}</script>"
        )
        responses.add(
            responses.GET,
            "https://dadosabertos.saude.gov.br/",
            body=html,
            status=200,
        )

    @staticmethod
    def _catalog_page(packages, total=2):
        return {
            "pageProps": {
                "currentFilters": {
                    "q": None,
                    "groups": None,
                    "tags": None,
                    "res_format": None,
                },
                "availableFilters": {
                    "groups": [
                        {"display_name": "Arboviroses", "name": "arboviroses"}
                    ],
                    "tags": [{"display_name": "covid-19", "name": "covid-19"}],
                },
                "numberOfPackages": total,
                "packages": packages,
                "page": 1,
                "rows": 20,
            }
        }

    _PKG1 = {
        "name": "bps",
        "title": "Banco de Preços em Saúde - BPS",
        "notes": "Registry of purchases of medicines and devices.",
        "formats": ["CSV", "API"],
        "groups": [
            {"display_name": "Economia da Saúde", "name": "economia-da-saude"}
        ],
        "tags": [{"display_name": "Preços", "name": "Preços"}],
    }
    _PKG2 = {
        "name": "arboviroses-dengue",
        "title": "Dengue",
        "notes": "Dengue notification data.",
        "formats": ["CSV"],
        "groups": [{"display_name": "Arboviroses", "name": "arboviroses"}],
        "tags": [{"display_name": "dengue", "name": "dengue"}],
    }

    _BPS_DETAIL = {
        "pageProps": {
            "name": "bps",
            "title": "Banco de Preços em Saúde - BPS",
            "notes": "Registry of purchases.",
            "organization": {
                "name": "ministerio-da-saude",
                "title": "Ministério da Saúde",
            },
            "license_title": "",
            "metadata_created": "2024-12-05T17:58:59.632645",
            "metadata_modified": "2026-08-12T08:53:18.286478",
            "num_resources": 3,
            "num_tags": 1,
            "extras": [{"key": "update_frequency", "value": "monthly"}],
            "tags": [{"name": "Preços"}],
            "groups": [{"name": "economia-da-saude"}],
            "resources": [
                {
                    "id": "res-api",
                    "name": "API documentation",
                    "format": "API",
                    "url": "https://apidadosabertos.saude.gov.br/v1/#/BPS",
                    "position": 0,
                    "size": None,
                },
                {
                    "id": "res-csv",
                    "name": "BPS CSV 2024",
                    "format": "CSV",
                    "url": "https://s3.example.com/BPS/csv/2024_csv.zip",
                    "position": 1,
                    "size": 12345,
                },
                {
                    "id": "res-pdf",
                    "name": "BPS Metadados",
                    "format": "PDF",
                    "url": "https://s3.example.com/BPS/Metadados.pdf",
                    "position": 2,
                    "size": 100,
                },
            ],
        }
    }

    def test_initialization(self, accessor):
        assert accessor is not None
        assert accessor.source_name == "opendatasus"
        assert "OpenDataSUS" in accessor.source_description
        assert accessor.source_url == "https://dadosabertos.saude.gov.br/"
        assert accessor.cache_dir.exists()

    def test_list_countries(self, accessor):
        countries = accessor.list_countries()
        assert isinstance(countries, pd.DataFrame)
        assert countries.iloc[0]["country_code"] == "BR"
        assert countries.iloc[0]["country_name"] == "Brazil"

    @responses.activate
    def test_get_build_id(self, accessor):
        self._mock_homepage()
        assert accessor._get_build_id(use_cache=False) == self.BUILD_ID

    @responses.activate
    def test_list_datasets(self, accessor):
        self._mock_homepage()
        responses.add(
            responses.GET,
            f"{self.BASE}/_next/data/{self.BUILD_ID}/dataset.json?page=1",
            json=self._catalog_page([self._PKG1, self._PKG2], total=2),
            status=200,
        )
        df = accessor.list_datasets(use_cache=False)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert set(df.columns) == {
            "name",
            "title",
            "notes",
            "formats",
            "groups",
            "tags",
        }
        assert "bps" in df["name"].values
        assert "CSV" in df.loc[df["name"] == "bps", "formats"].iloc[0]

    @responses.activate
    def test_list_datasets_group_filter(self, accessor):
        self._mock_homepage()
        responses.add(
            responses.GET,
            f"{self.BASE}/_next/data/{self.BUILD_ID}/dataset.json"
            "?page=1&groups=arboviroses",
            json=self._catalog_page([self._PKG2], total=1),
            status=200,
        )
        df = accessor.list_datasets(group="arboviroses", use_cache=False)
        assert len(df) == 1
        assert df.iloc[0]["name"] == "arboviroses-dengue"

    @responses.activate
    def test_list_groups_and_tags(self, accessor):
        self._mock_homepage()
        responses.add(
            responses.GET,
            f"{self.BASE}/_next/data/{self.BUILD_ID}/dataset.json?page=1",
            json=self._catalog_page([self._PKG1], total=1),
            status=200,
        )
        groups = accessor.list_groups(use_cache=False)
        tags = accessor.list_tags(use_cache=False)
        assert "arboviroses" in groups["name"].values
        assert "covid-19" in tags["name"].values

    @responses.activate
    def test_list_datasets_all_pagination(self, accessor):
        self._mock_homepage()
        responses.add(
            responses.GET,
            f"{self.BASE}/_next/data/{self.BUILD_ID}/dataset.json?page=1",
            json=self._catalog_page([self._PKG1], total=21),
            status=200,
        )
        responses.add(
            responses.GET,
            f"{self.BASE}/_next/data/{self.BUILD_ID}/dataset.json?page=2",
            json={
                "pageProps": {
                    "currentFilters": {},
                    "availableFilters": {"groups": [], "tags": []},
                    "numberOfPackages": 21,
                    "packages": [self._PKG2],
                    "page": 2,
                    "rows": 20,
                }
            },
            status=200,
        )
        df = accessor.list_datasets_all(use_cache=False)
        assert len(df) == 2
        assert list(df["name"]) == ["bps", "arboviroses-dengue"]

    @responses.activate
    def test_list_datasets_all_max_pages(self, accessor):
        self._mock_homepage()
        responses.add(
            responses.GET,
            f"{self.BASE}/_next/data/{self.BUILD_ID}/dataset.json?page=1",
            json=self._catalog_page([self._PKG1], total=40),
            status=200,
        )
        df = accessor.list_datasets_all(max_pages=1, use_cache=False)
        assert len(df) == 1  # capped after page 1

    @responses.activate
    def test_get_dataset_and_metadata(self, accessor):
        self._mock_homepage()
        responses.add(
            responses.GET,
            f"{self.BASE}/_next/data/{self.BUILD_ID}/dataset/bps.json?slug=bps",
            json=self._BPS_DETAIL,
            status=200,
        )
        pkg = accessor.get_dataset("bps", use_cache=False)
        assert pkg["name"] == "bps"
        assert len(pkg["resources"]) == 3

        meta = accessor.get_dataset_metadata("bps", use_cache=False)
        assert isinstance(meta, pd.DataFrame)
        assert set(meta.columns) == {"field", "value"}
        fields = set(meta["field"])
        assert "title" in fields
        assert "metadata_modified" in fields
        assert "extra:update_frequency" in fields

    @responses.activate
    def test_get_dataset_not_found(self, accessor):
        self._mock_homepage()
        responses.add(
            responses.GET,
            f"{self.BASE}/_next/data/{self.BUILD_ID}/dataset/nope.json?slug=nope",
            json={"pageProps": {"statusCode": 500}},
            status=200,
        )
        with pytest.raises(KeyError):
            accessor.get_dataset("nope", use_cache=False)

    @responses.activate
    def test_get_resources(self, accessor):
        self._mock_homepage()
        responses.add(
            responses.GET,
            f"{self.BASE}/_next/data/{self.BUILD_ID}/dataset/bps.json?slug=bps",
            json=self._BPS_DETAIL,
            status=200,
        )
        res = accessor.get_resources("bps", use_cache=False)
        assert isinstance(res, pd.DataFrame)
        assert len(res) == 3
        assert set(res.columns) >= {
            "resource_id",
            "name",
            "format",
            "url",
            "size",
            "position",
        }
        assert "res-csv" in res["resource_id"].values

    @responses.activate
    def test_download_resource(self, accessor, tmp_path):
        self._mock_homepage()
        responses.add(
            responses.GET,
            f"{self.BASE}/_next/data/{self.BUILD_ID}/dataset/bps.json?slug=bps",
            json=self._BPS_DETAIL,
            status=200,
        )
        responses.add(
            responses.GET,
            "https://s3.example.com/BPS/csv/2024_csv.zip",
            body=b"fake-zip-bytes",
            status=200,
        )
        path = accessor.download_resource(
            "bps",
            name="BPS CSV 2024",
            dest_dir=str(tmp_path / "dl"),
            use_cache=False,
        )
        assert isinstance(path, Path)
        assert path.exists()
        assert path.read_bytes() == b"fake-zip-bytes"
        assert path.name == "BPS CSV 2024.csv"  # format appended

    @responses.activate
    def test_download_resource_api_rejected(self, accessor, tmp_path):
        self._mock_homepage()
        responses.add(
            responses.GET,
            f"{self.BASE}/_next/data/{self.BUILD_ID}/dataset/bps.json?slug=bps",
            json=self._BPS_DETAIL,
            status=200,
        )
        with pytest.raises(ValueError):
            accessor.download_resource(
                "bps",
                name="API documentation",
                dest_dir=str(tmp_path / "dl"),
                use_cache=False,
            )

    def test_download_resource_needs_selector(self, accessor):
        with pytest.raises(ValueError):
            accessor.download_resource("bps", use_cache=False)
        with pytest.raises(ValueError):
            accessor.download_resource(
                "bps", resource_id="res-csv", name="BPS CSV 2024", use_cache=False
            )

    @responses.activate
    def test_download_dataset(self, accessor, tmp_path):
        self._mock_homepage()
        responses.add(
            responses.GET,
            f"{self.BASE}/_next/data/{self.BUILD_ID}/dataset/bps.json?slug=bps",
            json=self._BPS_DETAIL,
            status=200,
        )
        responses.add(
            responses.GET,
            "https://s3.example.com/BPS/csv/2024_csv.zip",
            body=b"fake-zip-bytes",
            status=200,
        )
        responses.add(
            responses.GET,
            "https://s3.example.com/BPS/Metadados.pdf",
            body=b"%PDF-fake",
            status=200,
        )
        paths = accessor.download_dataset(
            "bps", dest_dir=str(tmp_path / "dl"), use_cache=False
        )
        assert len(paths) == 2  # API resource skipped
        assert all(p.exists() for p in paths)

        paths_csv = accessor.download_dataset(
            "bps", dest_dir=str(tmp_path / "dl2"), fmt="CSV", use_cache=False
        )
        assert len(paths_csv) == 1
        assert paths_csv[0].name.endswith(".csv")

    @requires_external_api
    def test_live_list_datasets(self, accessor):
        df = accessor.list_datasets(q="covid", use_cache=False)
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    @requires_external_api
    def test_live_get_dataset_metadata(self, accessor):
        meta = accessor.get_dataset_metadata("bps", use_cache=False)
        assert isinstance(meta, pd.DataFrame)
        assert len(meta) > 0
