#!/usr/bin/env python3
"""
Test suite for epidemiological data accessors.

These tests validate that each accessor can connect to its data source
and return valid data structures. Tests are designed to be:
- Fast: Use small data samples or cached responses
- Non-breaking: Skip if external service is unavailable
- Informative: Clear error messages on failure
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "accessors"))

# Skip marker for external API tests
requires_external_api = pytest.mark.skipif(
    os.getenv("SKIP_EXTERNAL_TESTS", "false").lower() == "true",
    reason="External API tests disabled",
)


class TestHealthDataGov:
    """Tests for HealthData.gov accessor (US health data)."""

    @requires_external_api
    def test_initialization(self):
        """Test accessor initializes correctly."""
        from healthdata_gov import HealthDataGovAccessor

        accessor = HealthDataGovAccessor()
        assert accessor is not None
        assert hasattr(accessor, "list_datasets")

    @requires_external_api
    def test_list_datasets(self):
        """Test listing available datasets."""
        from healthdata_gov import HealthDataGovAccessor

        accessor = HealthDataGovAccessor()
        datasets = accessor.list_datasets()

        assert isinstance(datasets, pd.DataFrame)
        assert len(datasets) > 0
        assert "name" in datasets.columns or "title" in datasets.columns

    @requires_external_api
    def test_get_covid_data(self):
        """Test fetching COVID-19 hospital data."""
        from healthdata_gov import HealthDataGovAccessor

        accessor = HealthDataGovAccessor()

        # Get recent data (last 7 days)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)

        df = accessor.get_hospital_capacity(
            state="CA",
            date_range=(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")),
        )

        assert isinstance(df, pd.DataFrame)
        # May be empty if no recent data, but should not error


class TestColombiaINS:
    """Tests for Colombia INS accessor."""

    @requires_external_api
    def test_initialization(self):
        """Test accessor initializes correctly."""
        from colombia_ins import ColombiaINSAccessor

        accessor = ColombiaINSAccessor()
        assert accessor is not None

    @requires_external_api
    def test_get_dengue_data(self):
        """Test fetching dengue data for Colombia."""
        from colombia_ins import ColombiaINSAccessor

        accessor = ColombiaINSAccessor()

        # Get data for current year
        current_year = datetime.now().year
        df = accessor.get_dengue_data(years=[current_year])

        assert isinstance(df, pd.DataFrame)
        # Structure validation - should have expected columns
        if len(df) > 0:
            expected_cols = ["cases", "date", "department", "municipality"]
            # At least one of these should exist
            assert any(col in df.columns for col in expected_cols)


class TestAfricaCDC:
    """Tests for Africa CDC accessor."""

    @requires_external_api
    def test_initialization(self):
        """Test accessor initializes correctly."""
        from africa_cdc import AfricaCDCAccessor

        accessor = AfricaCDCAccessor()
        assert accessor is not None

    @requires_external_api
    def test_get_countries(self):
        """Test getting list of African countries."""
        from africa_cdc import AfricaCDCAccessor

        accessor = AfricaCDCAccessor()

        countries = accessor.list_countries()

        assert isinstance(countries, (pd.DataFrame, list))
        if isinstance(countries, pd.DataFrame):
            assert len(countries) > 40  # At least 40+ African countries

    @requires_external_api
    def test_get_disease_data(self):
        """Test fetching disease surveillance data."""
        from africa_cdc import AfricaCDCAccessor

        accessor = AfricaCDCAccessor()

        # Test for a specific disease
        df = accessor.get_disease_outbreaks(disease="MALARIA")

        assert isinstance(df, pd.DataFrame)


class TestPAHO:
    """Tests for PAHO (Pan American Health Organization) accessor."""

    @requires_external_api
    def test_initialization(self):
        """Test accessor initializes correctly."""
        from paho import PAHOAccessor

        accessor = PAHOAccessor()
        assert accessor is not None

    @requires_external_api
    def test_get_dengue_data(self):
        """Test fetching PAHO dengue data."""
        from paho import PAHOAccessor

        accessor = PAHOAccessor()

        df = accessor.get_dengue_data(countries=["BRA"], years=[2024])

        assert isinstance(df, pd.DataFrame)


class TestRKI:
    """Tests for RKI Germany accessor."""

    @requires_external_api
    def test_initialization(self):
        """Test accessor initializes correctly."""
        from rki_germany import RKIGermanyAccessor

        accessor = RKIGermanyAccessor()
        assert accessor is not None

    @requires_external_api
    def test_get_covid_nowcast(self):
        """Test fetching COVID-19 nowcast data."""
        from rki_germany import RKIGermanyAccessor

        accessor = RKIGermanyAccessor()

        df = accessor.get_covid_nowcast()

        assert isinstance(df, pd.DataFrame)
        if len(df) > 0:
            assert (
                "Datum" in df.columns or "date" in df.columns or "R" in str(df.columns)
            )

    @requires_external_api
    def test_get_notifiable_diseases(self):
        """Test fetching notifiable diseases list."""
        from rki_germany import RKIGermanyAccessor

        accessor = RKIGermanyAccessor()

        diseases = accessor.list_notifiable_diseases()

        assert isinstance(diseases, (pd.DataFrame, list))
        if isinstance(diseases, pd.DataFrame):
            assert len(diseases) > 20  # Germany has 25+ notifiable diseases


class TestChinaCDC:
    """Tests for China CDC accessor."""

    @requires_external_api
    def test_initialization(self):
        """Test accessor initializes correctly."""
        from china_cdc import ChinaCDCAccessor

        accessor = ChinaCDCAccessor()
        assert accessor is not None

    @requires_external_api
    def test_get_weekly_report(self):
        """Test fetching weekly surveillance report."""
        from china_cdc import ChinaCDCAccessor

        accessor = ChinaCDCAccessor()

        # Get reports for a specific year
        df = accessor.get_weekly_reports(year=2024, week=1)

        assert isinstance(df, pd.DataFrame)


class TestIndiaIDSP:
    """Tests for India IDSP accessor."""

    @requires_external_api
    def test_initialization(self):
        """Test accessor initializes correctly."""
        from india_idsp import IndiaIDSPAccessor

        accessor = IndiaIDSPAccessor()
        assert accessor is not None

    @requires_external_api
    def test_get_outbreak_reports(self):
        """Test fetching outbreak reports."""
        from india_idsp import IndiaIDSPAccessor

        accessor = IndiaIDSPAccessor()

        df = accessor.get_outbreak_reports(years=[2024])

        assert isinstance(df, pd.DataFrame)


class TestGlobalHealth:
    """Tests for Global.health accessor (via OWID)."""

    @requires_external_api
    def test_initialization(self):
        """Test accessor initializes correctly."""
        from global_health import GlobalHealthAccessor

        accessor = GlobalHealthAccessor()
        assert accessor is not None

    @requires_external_api
    def test_get_covid_data(self):
        """Test fetching COVID-19 data from OWID."""
        from global_health import GlobalHealthAccessor

        accessor = GlobalHealthAccessor()

        df = accessor.get_case_data(disease="COVID-19", country="Brazil")

        assert isinstance(df, pd.DataFrame)
        if len(df) > 0:
            # Should have date and case columns
            date_cols = [c for c in df.columns if "date" in c.lower()]
            case_cols = [c for c in df.columns if "case" in c.lower()]
            assert len(date_cols) > 0 or len(case_cols) > 0

    @requires_external_api
    def test_get_monkeypox_data(self):
        """Test fetching Monkeypox data."""
        from global_health import GlobalHealthAccessor

        accessor = GlobalHealthAccessor()

        df = accessor.get_case_data(disease="Monkeypox")

        assert isinstance(df, pd.DataFrame)


class TestUKHSA:
    """Tests for UKHSA accessor."""

    @requires_external_api
    def test_initialization(self):
        """Test accessor initializes correctly."""
        from ukhsa import UKHSAAccessor

        accessor = UKHSAAccessor()
        assert accessor is not None

    @requires_external_api
    def test_list_diseases(self):
        """Test listing available diseases."""
        from ukhsa import UKHSAAccessor

        accessor = UKHSAAccessor()

        diseases = accessor.list_available_diseases()

        assert isinstance(diseases, (pd.DataFrame, list))

    @requires_external_api
    def test_get_covid_data(self):
        """Test fetching UK COVID-19 data."""
        from ukhsa import UKHSAAccessor

        accessor = UKHSAAccessor()

        df = accessor.get_infectious_disease_data("COVID-19")

        assert isinstance(df, pd.DataFrame)


class TestEpiPulse:
    """Tests for ECDC EpiPulse accessor."""

    def test_initialization(self):
        """Test accessor initializes correctly."""
        from epipulse import EpiPulseAccessor

        accessor = EpiPulseAccessor()
        assert accessor is not None
        assert hasattr(accessor, 'get_available_diseases')
        assert hasattr(accessor, 'get_available_countries')

    def test_get_available_diseases(self):
        """Test listing available diseases."""
        from epipulse import EpiPulseAccessor

        accessor = EpiPulseAccessor()
        diseases = accessor.get_available_diseases()

        assert isinstance(diseases, pd.DataFrame)
        assert len(diseases) > 0
        assert 'disease' in diseases.columns
        assert 'category' in diseases.columns

    def test_get_available_countries(self):
        """Test listing available countries."""
        from epipulse import EpiPulseAccessor

        accessor = EpiPulseAccessor()
        countries = accessor.get_available_countries(region="EU")

        assert isinstance(countries, pd.DataFrame)
        assert len(countries) == 27  # EU countries

    @requires_external_api
    def test_get_cases(self):
        """Test fetching case data."""
        from epipulse import EpiPulseAccessor

        accessor = EpiPulseAccessor()
        df = accessor.get_cases(
            disease="COVID-19",
            country="DE",
            year=2024
        )

        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0


class TestRespiCast:
    """Tests for ECDC RespiCast accessor."""

    def test_initialization(self):
        """Test accessor initializes correctly."""
        from respicast import RespiCastAccessor

        accessor = RespiCastAccessor()
        assert accessor is not None
        assert hasattr(accessor, 'get_available_diseases')
        assert hasattr(accessor, 'get_ensemble_forecast')

    def test_get_available_diseases(self):
        """Test listing available diseases."""
        from respicast import RespiCastAccessor

        accessor = RespiCastAccessor()
        diseases = accessor.get_available_diseases()

        assert isinstance(diseases, pd.DataFrame)
        assert len(diseases) > 0
        assert 'disease_key' in diseases.columns
        assert 'disease_name' in diseases.columns

    def test_get_available_countries(self):
        """Test listing available countries."""
        from respicast import RespiCastAccessor

        accessor = RespiCastAccessor()
        countries = accessor.get_available_countries()

        assert isinstance(countries, pd.DataFrame)
        assert len(countries) == 30  # EU/EEA countries

    @requires_external_api
    def test_get_ensemble_forecast(self):
        """Test fetching ensemble forecast."""
        from respicast import RespiCastAccessor

        accessor = RespiCastAccessor()
        forecast = accessor.get_ensemble_forecast(
            country="DE",
            disease="influenza",
            target="ili_rate",
            horizon_weeks=4
        )

        assert isinstance(forecast, pd.DataFrame)
        assert len(forecast) > 0


class TestCDCOpenData:
    """Tests for CDC Open Data accessor."""

    def test_initialization(self):
        """Test accessor initializes correctly."""
        from cdc_opendata import CDCOpenDataAccessor

        accessor = CDCOpenDataAccessor()
        assert accessor is not None
        assert hasattr(accessor, 'get_available_datasets')
        assert hasattr(accessor, 'get_covid_cases')

    def test_get_available_datasets(self):
        """Test listing available datasets."""
        from cdc_opendata import CDCOpenDataAccessor

        accessor = CDCOpenDataAccessor()
        datasets = accessor.get_available_datasets()

        assert isinstance(datasets, pd.DataFrame)
        assert len(datasets) > 0
        assert 'dataset_key' in datasets.columns
        assert 'category' in datasets.columns

    def test_list_notifiable_diseases(self):
        """Test listing notifiable diseases."""
        from cdc_opendata import CDCOpenDataAccessor

        accessor = CDCOpenDataAccessor()
        diseases = accessor.list_notifiable_diseases()

        assert isinstance(diseases, list)
        assert len(diseases) > 0
        assert "Measles" in diseases
        assert "Tuberculosis" in diseases

    @requires_external_api
    def test_get_covid_cases(self):
        """Test fetching COVID-19 data."""
        from cdc_opendata import CDCOpenDataAccessor

        accessor = CDCOpenDataAccessor()
        df = accessor.get_covid_cases(
            state="CA",
            limit=10
        )

        assert isinstance(df, pd.DataFrame)

    @requires_external_api
    def test_get_influenza_data(self):
        """Test fetching influenza data."""
        from cdc_opendata import CDCOpenDataAccessor

        accessor = CDCOpenDataAccessor()
        df = accessor.get_influenza_data(
            state="NY",
            limit=10
        )

        assert isinstance(df, pd.DataFrame)


class TestUtils:
    """Tests for utility functions."""

    def test_cache_directory_exists(self):
        """Test that cache directory can be created."""
        cache_dir = Path(__file__).parent.parent / "data" / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        assert cache_dir.exists()

    def test_import_all_accessors(self):
        """Test that all accessor modules can be imported."""
        accessor_dir = Path(__file__).parent.parent / "scripts" / "accessors"

        accessor_files = [
            "healthdata_gov.py",
            "colombia_ins.py",
            "africa_cdc.py",
            "paho.py",
            "rki_germany.py",
            "china_cdc.py",
            "india_idsp.py",
            "global_health.py",
            "ukhsa.py",
            "epipulse.py",
            "respicast.py",
            "cdc_opendata.py",
        ]

        for file in accessor_files:
            file_path = accessor_dir / file
            if file_path.exists():
                module_name = file.replace(".py", "")
                try:
                    __import__(module_name)
                except ImportError as e:
                    pytest.fail(f"Failed to import {module_name}: {e}")

    def test_cache_manager_basic(self):
        """Test CacheManager basic operations."""
        import tempfile
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        from utils import CacheManager

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = CacheManager(cache_dir=tmpdir)
            cache.set("test_key", {"data": "test_value"})
            result = cache.get("test_key")
            assert result == {"data": "test_value"}
            assert cache.get("nonexistent_key") is None

    def test_cache_manager_clear(self):
        """Test CacheManager clear functionality."""
        import tempfile
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        from utils import CacheManager

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = CacheManager(cache_dir=tmpdir)
            cache.set("key1", {"a": 1})
            cache.set("key2", {"b": 2})
            cache.clear()
            assert cache.get("key1") is None
            assert cache.get("key2") is None

    def test_rate_limiter(self):
        """Test RateLimiter basic functionality."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        from utils import RateLimiter

        limiter = RateLimiter(requests_per_second=10.0)
        limiter.wait_if_needed()
        assert limiter.last_request_time is not None

    def test_standardize_country_code(self):
        """Test country code standardization."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        from utils import standardize_country_code

        assert standardize_country_code("br") == "BRA"
        assert standardize_country_code("BR") == "BRA"
        assert standardize_country_code("BRA") == "BRA"
        assert standardize_country_code("us") == "USA"

    def test_validate_year_range_valid(self):
        """Test year range validation with valid inputs."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        from utils import validate_year_range

        validate_year_range(2020, 2024)
        validate_year_range(2000, 2000)

    def test_validate_year_range_invalid(self):
        """Test year range validation with invalid inputs."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        from utils import validate_year_range

        with pytest.raises(ValueError):
            validate_year_range(2024, 2020)

        with pytest.raises(ValueError):
            validate_year_range(1800, 2020)

    def test_merge_dataframes(self):
        """Test merge_dataframes utility."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        from utils import merge_dataframes

        df1 = pd.DataFrame({"id": [1, 2], "a": [10, 20]})
        df2 = pd.DataFrame({"id": [1, 2], "b": [30, 40]})

        result = merge_dataframes([df1, df2], on=["id"])
        assert "a" in result.columns
        assert "b" in result.columns
        assert len(result) == 2

    def test_merge_dataframes_empty(self):
        """Test merge_dataframes with empty list."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        from utils import merge_dataframes

        result = merge_dataframes([])
        assert result.empty

    def test_merge_dataframes_single(self):
        """Test merge_dataframes with single dataframe."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        from utils import merge_dataframes

        df = pd.DataFrame({"a": [1, 2]})
        result = merge_dataframes([df])
        assert len(result) == 2

    def test_save_to_multiple_formats(self):
        """Test saving dataframe to multiple formats."""
        import tempfile
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        from utils import save_to_multiple_formats

        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})

        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir) / "test_data"
            saved = save_to_multiple_formats(
                df, str(base_path), formats=["csv", "json"]
            )
            assert "csv" in saved
            assert "json" in saved
            assert saved["csv"].exists()
            assert saved["json"].exists()


class TestAccessorMethods:
    """Tests for additional accessor methods to improve coverage."""

    def test_healthdata_gov_methods(self):
        """Test HealthData.gov accessor additional methods."""
        from healthdata_gov import HealthDataGovAccessor

        accessor = HealthDataGovAccessor()
        datasets = accessor.list_datasets()
        assert isinstance(datasets, pd.DataFrame)
        assert len(datasets) > 0

    def test_colombia_ins_list_methods(self):
        """Test Colombia INS accessor list methods."""
        from colombia_ins import ColombiaINSAccessor

        accessor = ColombiaINSAccessor()

        depts = accessor.list_departments()
        assert isinstance(depts, pd.DataFrame)

        diseases = accessor.list_diseases()
        assert isinstance(diseases, pd.DataFrame)

        groups = accessor.list_event_groups()
        assert isinstance(groups, pd.DataFrame)

    def test_colombia_ins_region_methods(self):
        """Test Colombia INS region methods."""
        from colombia_ins import ColombiaINSAccessor

        accessor = ColombiaINSAccessor()

        andina = accessor.get_departments_by_region("Andina")
        assert len(andina) > 0

        vector_diseases = accessor.get_diseases_by_group(
            "ENFERMEDADES TRANSMITIDAS POR VECTORES"
        )
        assert len(vector_diseases) > 0

    def test_africa_cdc_list_methods(self):
        """Test Africa CDC accessor list methods."""
        from africa_cdc import AfricaCDCAccessor

        accessor = AfricaCDCAccessor()

        countries = accessor.list_countries()
        assert isinstance(countries, pd.DataFrame)

        regions = accessor.list_regions()
        assert isinstance(regions, pd.DataFrame)

        diseases = accessor.list_priority_diseases()
        assert isinstance(diseases, pd.DataFrame)

    def test_africa_cdc_region_methods(self):
        """Test Africa CDC region methods."""
        from africa_cdc import AfricaCDCAccessor

        accessor = AfricaCDCAccessor()

        eastern = accessor.get_countries_by_region("Eastern")
        assert len(eastern) > 0

    def test_paho_list_methods(self):
        """Test PAHO accessor list methods."""
        from paho import PAHOAccessor

        accessor = PAHOAccessor()

        countries = accessor.list_countries()
        assert isinstance(countries, pd.DataFrame)

        subregions = accessor.list_subregions()
        assert isinstance(subregions, pd.DataFrame)

        vaccines = accessor.list_vaccines()
        assert isinstance(vaccines, pd.DataFrame)

        diseases = accessor.list_diseases()
        assert isinstance(diseases, pd.DataFrame)

    def test_paho_subregion_methods(self):
        """Test PAHO subregion methods."""
        from paho import PAHOAccessor

        accessor = PAHOAccessor()

        andean = accessor.get_countries_by_subregion("Andean")
        assert len(andean) > 0

    def test_rki_list_methods(self):
        """Test RKI accessor list methods."""
        from rki_germany import RKIGermanyAccessor

        accessor = RKIGermanyAccessor()

        states = accessor.list_states()
        assert isinstance(states, pd.DataFrame)

        diseases = accessor.list_notifiable_diseases()
        assert isinstance(diseases, pd.DataFrame)

    def test_china_cdc_list_methods(self):
        """Test China CDC accessor list methods."""
        from china_cdc import ChinaCDCAccessor

        accessor = ChinaCDCAccessor()

        diseases = accessor.list_notifiable_diseases()
        assert isinstance(diseases, pd.DataFrame)

        provinces = accessor.list_provinces()
        assert isinstance(provinces, pd.DataFrame)

    def test_india_idsp_list_methods(self):
        """Test India IDSP accessor list methods."""
        from india_idsp import IndiaIDSPAccessor

        accessor = IndiaIDSPAccessor()

        states = accessor.list_states()
        assert isinstance(states, pd.DataFrame)

        diseases = accessor.list_priority_diseases()
        assert isinstance(diseases, pd.DataFrame)

    def test_ukhsa_list_methods(self):
        """Test UKHSA accessor list methods."""
        from ukhsa import UKHSAAccessor

        accessor = UKHSAAccessor()

        diseases = accessor.list_available_diseases()
        assert isinstance(diseases, (pd.DataFrame, list))


# Smoke tests - quick validation without external calls
class TestSmoke:
    """Quick smoke tests that don't require external APIs."""

    def test_repository_structure(self):
        """Validate basic repository structure."""
        repo_root = Path(__file__).parent.parent

        # Check essential directories exist
        assert (repo_root / "scripts" / "accessors").exists()
        assert (repo_root / "tests").exists()

    def test_accessor_files_exist(self):
        """Check that expected accessor files exist."""
        accessor_dir = Path(__file__).parent.parent / "scripts" / "accessors"

        essential_accessors = [
            "healthdata_gov.py",
            "colombia_ins.py",
            "paho.py",
        ]

        for accessor in essential_accessors:
            assert (accessor_dir / accessor).exists(), f"Missing {accessor}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
