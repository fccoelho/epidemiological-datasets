"""Tests for data source accessors.

These tests validate that each accessor can be instantiated and return
valid data structures. Tests are designed to be fast and non-breaking.
"""

import os
from datetime import datetime, timedelta

import pandas as pd
import pytest


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


class TestSmoke:
    def test_package_import(self):
        import epidatasets
        assert epidatasets.__version__

    def test_base_accessor_import(self):
        from epidatasets._base import BaseAccessor
        assert BaseAccessor is not None

    def test_sources_dir_exists(self):
        from pathlib import Path
        sources_dir = Path(__file__).parent.parent / "src" / "epidatasets" / "sources"
        assert sources_dir.exists()
