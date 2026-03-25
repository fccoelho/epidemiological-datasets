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
        ]

        for file in accessor_files:
            file_path = accessor_dir / file
            if file_path.exists():
                # Try to import
                module_name = file.replace(".py", "")
                try:
                    __import__(module_name)
                except ImportError as e:
                    pytest.fail(f"Failed to import {module_name}: {e}")


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
