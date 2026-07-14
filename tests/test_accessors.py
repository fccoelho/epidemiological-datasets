"""Tests for data source accessors.

These tests validate that each accessor can be instantiated and return
valid data structures. Tests are designed to be fast and non-breaking.
"""

import os
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest
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
        assert epidatasets.__version__()

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
