"""Tests for utility modules."""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from epidatasets.utils.cache import CacheManager
from epidatasets.utils.rate_limit import RateLimiter
from epidatasets.utils.geo import standardize_country_code
from epidatasets.utils.validation import validate_year_range
from epidatasets.utils.io import merge_dataframes, save_to_multiple_formats


class TestCacheManager:
    def test_set_and_get(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = CacheManager(cache_dir=tmpdir)
            cache.set("test_key", {"data": "test_value"})
            result = cache.get("test_key")
            assert result == {"data": "test_value"}

    def test_get_missing_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = CacheManager(cache_dir=tmpdir)
            assert cache.get("nonexistent_key") is None

    def test_clear(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = CacheManager(cache_dir=tmpdir)
            cache.set("key1", {"a": 1})
            cache.set("key2", {"b": 2})
            cache.clear()
            assert cache.get("key1") is None
            assert cache.get("key2") is None


class TestRateLimiter:
    def test_basic(self):
        limiter = RateLimiter(requests_per_second=10.0)
        limiter.wait_if_needed()
        assert limiter.last_request_time is not None


class TestGeoUtils:
    def test_iso2_to_iso3(self):
        assert standardize_country_code("br") == "BRA"
        assert standardize_country_code("BR") == "BRA"
        assert standardize_country_code("BRA") == "BRA"
        assert standardize_country_code("us") == "USA"

    def test_already_iso3(self):
        assert standardize_country_code("GBR") == "GBR"
        assert standardize_country_code("DEU") == "DEU"


class TestValidation:
    def test_valid_ranges(self):
        validate_year_range(2020, 2024)
        validate_year_range(2000, 2000)

    def test_invalid_start_after_end(self):
        with pytest.raises(ValueError):
            validate_year_range(2024, 2020)

    def test_invalid_too_early(self):
        with pytest.raises(ValueError):
            validate_year_range(1800, 2020)


class TestMergeDataframes:
    def test_merge_two(self):
        df1 = pd.DataFrame({"id": [1, 2], "a": [10, 20]})
        df2 = pd.DataFrame({"id": [1, 2], "b": [30, 40]})
        result = merge_dataframes([df1, df2], on=["id"])
        assert "a" in result.columns
        assert "b" in result.columns
        assert len(result) == 2

    def test_merge_empty(self):
        result = merge_dataframes([])
        assert result.empty

    def test_merge_single(self):
        df = pd.DataFrame({"a": [1, 2]})
        result = merge_dataframes([df])
        assert len(result) == 2


class TestSaveFormats:
    def test_csv_and_json(self):
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir) / "test_data"
            saved = save_to_multiple_formats(df, str(base_path), formats=["csv", "json"])
            assert "csv" in saved
            assert "json" in saved
            assert saved["csv"].exists()
            assert saved["json"].exists()
