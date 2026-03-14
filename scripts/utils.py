"""
Common utilities for epidemiological data access.
"""

import pandas as pd
from typing import Dict, Any, Optional
import requests
from pathlib import Path
import json
from datetime import datetime


class CacheManager:
    """
    Simple file-based cache for API responses.
    """
    
    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
    
    def _get_cache_path(self, key: str) -> Path:
        """Generate cache file path from key."""
        safe_key = key.replace("/", "_").replace(":", "_")
        return self.cache_dir / f"{safe_key}.json"
    
    def get(self, key: str, max_age_hours: int = 24) -> Optional[Dict]:
        """
        Retrieve cached data if it exists and is not expired.
        
        Args:
            key: Cache key
            max_age_hours: Maximum age of cache in hours
            
        Returns:
            Cached data or None
        """
        cache_path = self._get_cache_path(key)
        
        if not cache_path.exists():
            return None
        
        # Check age
        mod_time = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age_hours = (datetime.now() - mod_time).total_seconds() / 3600
        
        if age_hours > max_age_hours:
            return None
        
        # Load and return
        with open(cache_path, 'r') as f:
            return json.load(f)
    
    def set(self, key: str, data: Dict) -> None:
        """
        Store data in cache.
        
        Args:
            key: Cache key
            data: Data to cache
        """
        cache_path = self._get_cache_path(key)
        with open(cache_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def clear(self) -> None:
        """Clear all cached data."""
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()


class RateLimiter:
    """
    Simple rate limiter for API requests.
    """
    
    def __init__(self, requests_per_second: float = 1.0):
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time: Optional[float] = None
    
    def wait_if_needed(self) -> None:
        """Wait if necessary to maintain rate limit."""
        import time
        
        if self.last_request_time is not None:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
        
        self.last_request_time = time.time()


def standardize_country_code(code: str) -> str:
    """
    Standardize country code to ISO3 format.
    
    Args:
        code: Country code (ISO2 or ISO3)
        
    Returns:
        ISO3 country code
    """
    # Mapping of common ISO2 to ISO3 codes
    iso2_to_iso3 = {
        "BR": "BRA", "US": "USA", "GB": "GBR", "FR": "FRA",
        "DE": "DEU", "IN": "IND", "CN": "CHN", "JP": "JPN",
        "AU": "AUS", "CA": "CAN", "MX": "MEX", "AR": "ARG",
        "ZA": "ZAF", "NG": "NGA", "EG": "EGY", "KE": "KEN"
    }
    
    if len(code) == 2:
        return iso2_to_iso3.get(code.upper(), code.upper())
    return code.upper()


def validate_year_range(start_year: int, end_year: int) -> None:
    """
    Validate year range for data queries.
    
    Args:
        start_year: Start year
        end_year: End year
        
    Raises:
        ValueError: If year range is invalid
    """
    current_year = datetime.now().year
    
    if start_year > end_year:
        raise ValueError(f"Start year {start_year} must be <= end year {end_year}")
    
    if end_year > current_year + 1:  # Allow projections
        raise ValueError(f"End year {end_year} cannot be > {current_year + 1}")
    
    if start_year < 1900:
        raise ValueError(f"Start year {start_year} seems too early")


def merge_dataframes(
    df_list: list,
    on: list = None,
    how: str = "outer"
) -> pd.DataFrame:
    """
    Safely merge multiple dataframes.
    
    Args:
        df_list: List of dataframes to merge
        on: Columns to merge on
        how: Merge type ("outer", "inner", "left", "right")
        
    Returns:
        Merged dataframe
    """
    if not df_list:
        return pd.DataFrame()
    
    if len(df_list) == 1:
        return df_list[0]
    
    result = df_list[0]
    for df in df_list[1:]:
        if on:
            result = result.merge(df, on=on, how=how, suffixes=("", "_dup"))
        else:
            result = result.merge(df, left_index=True, right_index=True, how=how)
    
    return result


def save_to_multiple_formats(
    df: pd.DataFrame,
    base_path: str,
    formats: list = None
) -> Dict[str, Path]:
    """
    Save dataframe to multiple formats.
    
    Args:
        df: Dataframe to save
        base_path: Base file path (without extension)
        formats: List of formats ("csv", "parquet", "json", "xlsx")
        
    Returns:
        Dictionary mapping format to saved path
    """
    if formats is None:
        formats = ["csv", "parquet"]
    
    base = Path(base_path)
    saved_paths = {}
    
    for fmt in formats:
        if fmt == "csv":
            path = base.with_suffix(".csv")
            df.to_csv(path, index=False)
            saved_paths["csv"] = path
            
        elif fmt == "parquet":
            path = base.with_suffix(".parquet")
            df.to_parquet(path, index=False)
            saved_paths["parquet"] = path
            
        elif fmt == "json":
            path = base.with_suffix(".json")
            df.to_json(path, orient="records", indent=2)
            saved_paths["json"] = path
            
        elif fmt == "xlsx":
            path = base.with_suffix(".xlsx")
            df.to_excel(path, index=False)
            saved_paths["xlsx"] = path
    
    return saved_paths
