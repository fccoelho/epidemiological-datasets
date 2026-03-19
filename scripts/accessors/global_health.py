"""
Global.health Accessor

Provides access to standardized, curated line-list data for pandemics and epidemics
including COVID-19, Monkeypox, and other disease outbreaks.

Data Source: https://global.health/
License: CC BY 4.0 (Open Data)
Update Frequency: Daily (during active outbreaks)
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Union, List
from urllib.request import urlopen
from urllib.error import HTTPError

import pandas as pd


class GlobalHealthAccessor:
    """
    Accessor for Global.health pandemic/epidemic line-list data.
    
    Global.health provides standardized, geocoded case data with detailed
    metadata including demographics, symptoms, outcomes, and travel history.
    
    Example:
        >>> from scripts.accessors.global_health import GlobalHealthAccessor
        >>> gh = GlobalHealthAccessor()
        >>> covid_data = gh.get_case_data(disease="COVID-19", country="Brazil")
        >>> mpox_data = gh.get_case_data(disease="Monkeypox")
    """
    
    BASE_URL = "https://raw.githubusercontent.com/globaldothealth/list/main"
    DATA_CATALOG_URL = "https://api.github.com/repos/globaldothealth/list/contents"
    
    # Known dataset paths in their GitHub repository
    DATASETS = {
        "COVID-19": {
            "url": "https://raw.githubusercontent.com/globaldothealth/list/main/data/cases.csv",
            "description": "Global COVID-19 line-list data",
            "fields": ["case_id", "country", "date_confirmation", "outcome", "age", "sex", "latitude", "longitude"]
        },
        "Monkeypox": {
            "url": "https://raw.githubusercontent.com/globaldothealth/monkeypox/main/data/monkeypox.csv",
            "description": "Global Monkeypox line-list data",
            "fields": ["case_id", "country", "date_confirmation", "outcome", "age", "sex"]
        }
    }
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize Global.health accessor.
        
        Args:
            cache_dir: Directory to cache downloaded data. If None, uses temp directory.
        """
        self.cache_dir = Path(cache_dir) if cache_dir else Path.home() / ".cache" / "epi_data" / "global_health"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_ttl = timedelta(hours=24)  # Cache for 24 hours
        
    def _get_cached_path(self, dataset_name: str) -> Path:
        """Get cache file path for a dataset."""
        return self.cache_dir / f"{dataset_name.lower().replace(' ', '_')}.csv"
    
    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cache file is still valid."""
        if not cache_path.exists():
            return False
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        return datetime.now() - mtime < self._cache_ttl
    
    def _download_data(self, url: str, cache_path: Path) -> pd.DataFrame:
        """Download data from URL and cache it."""
        try:
            df = pd.read_csv(url, low_memory=False)
            df.to_csv(cache_path, index=False)
            return df
        except Exception as e:
            raise RuntimeError(f"Failed to download data from {url}: {e}")
    
    def list_available_datasets(self) -> pd.DataFrame:
        """
        List available datasets from Global.health.
        
        Returns:
            DataFrame with dataset information including name, description, and URL.
        """
        datasets = []
        for name, info in self.DATASETS.items():
            datasets.append({
                "dataset_name": name,
                "description": info["description"],
                "url": info["url"],
                "available": True
            })
        return pd.DataFrame(datasets)
    
    def get_case_data(
        self,
        disease: str,
        country: Optional[str] = None,
        date_range: Optional[tuple] = None,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Get line-list case data for a specific disease.
        
        Args:
            disease: Disease name (e.g., "COVID-19", "Monkeypox")
            country: Filter by country name (optional)
            date_range: Tuple of (start_date, end_date) as strings (YYYY-MM-DD)
            use_cache: Whether to use cached data if available
            
        Returns:
            DataFrame with case line-list data
            
        Example:
            >>> gh = GlobalHealthAccessor()
            >>> df = gh.get_case_data("COVID-19", country="Brazil", 
            ...                       date_range=("2022-01-01", "2022-12-31"))
        """
        if disease not in self.DATASETS:
            available = ", ".join(self.DATASETS.keys())
            raise ValueError(f"Unknown disease '{disease}'. Available: {available}")
        
        dataset_info = self.DATASETS[disease]
        cache_path = self._get_cached_path(disease)
        
        # Check cache
        if use_cache and self._is_cache_valid(cache_path):
            df = pd.read_csv(cache_path, low_memory=False)
        else:
            df = self._download_data(dataset_info["url"], cache_path)
        
        # Apply filters
        if country and "country" in df.columns:
            df = df[df["country"].str.lower() == country.lower()]
        
        if date_range and "date_confirmation" in df.columns:
            start_date, end_date = date_range
            df["date_confirmation"] = pd.to_datetime(df["date_confirmation"], errors="coerce")
            df = df[
                (df["date_confirmation"] >= start_date) & 
                (df["date_confirmation"] <= end_date)
            ]
        
        return df.reset_index(drop=True)
    
    def get_outbreak_metadata(self, disease: str) -> dict:
        """
        Get metadata about an outbreak dataset.
        
        Args:
            disease: Disease name (e.g., "COVID-19", "Monkeypox")
            
        Returns:
            Dictionary with outbreak metadata
        """
        if disease not in self.DATASETS:
            available = ", ".join(self.DATASETS.keys())
            raise ValueError(f"Unknown disease '{disease}'. Available: {available}")
        
        # Try to get data and compute statistics
        try:
            df = self.get_case_data(disease, use_cache=True)
            metadata = {
                "disease": disease,
                "description": self.DATASETS[disease]["description"],
                "total_cases": len(df),
                "url": self.DATASETS[disease]["url"],
                "fields": list(df.columns),
                "date_range": None,
                "countries": None
            }
            
            if "date_confirmation" in df.columns:
                dates = pd.to_datetime(df["date_confirmation"], errors="coerce")
                metadata["date_range"] = {
                    "earliest": dates.min().strftime("%Y-%m-%d") if not dates.isna().all() else None,
                    "latest": dates.max().strftime("%Y-%m-%d") if not dates.isna().all() else None
                }
            
            if "country" in df.columns:
                metadata["countries"] = df["country"].dropna().unique().tolist()
                metadata["num_countries"] = len(metadata["countries"])
            
            return metadata
            
        except Exception as e:
            return {
                "disease": disease,
                "description": self.DATASETS[disease]["description"],
                "url": self.DATASETS[disease]["url"],
                "error": str(e)
            }
    
    def get_geocoded_cases(
        self,
        disease: str,
        country: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get geocoded cases with latitude/longitude coordinates.
        
        Args:
            disease: Disease name
            country: Filter by country (optional)
            
        Returns:
            DataFrame with case data including coordinates
        """
        df = self.get_case_data(disease, country=country)
        
        # Check for coordinate columns
        coord_cols = ["latitude", "longitude", "lat", "lon", "lng"]
        has_coords = any(col in df.columns for col in coord_cols)
        
        if not has_coords:
            # Try to find admin level columns that might be geocoded
            geo_cols = [col for col in df.columns if any(
                x in col.lower() for x in ["admin", "location", "geo", "lat", "lon"]
            )]
            if geo_cols:
                print(f"No coordinates found. Available geo columns: {geo_cols}")
            else:
                print("Warning: No geocoded data available for this dataset")
        
        return df
    
    def compare_outbreaks(
        self,
        diseases: List[str],
        metric: str = "total_cases"
    ) -> pd.DataFrame:
        """
        Compare multiple disease outbreaks.
        
        Args:
            diseases: List of disease names to compare
            metric: Metric to compare (default: "total_cases")
            
        Returns:
            DataFrame with comparison metrics
        """
        comparison = []
        for disease in diseases:
            try:
                metadata = self.get_outbreak_metadata(disease)
                comparison.append({
                    "disease": disease,
                    "total_cases": metadata.get("total_cases", 0),
                    "num_countries": metadata.get("num_countries", 0),
                    "earliest_case": metadata.get("date_range", {}).get("earliest"),
                    "latest_case": metadata.get("date_range", {}).get("latest"),
                    "url": metadata.get("url")
                })
            except Exception as e:
                comparison.append({
                    "disease": disease,
                    "error": str(e)
                })
        
        return pd.DataFrame(comparison)


# Convenience functions for direct use
def get_global_health_data(
    disease: str,
    country: Optional[str] = None,
    date_range: Optional[tuple] = None
) -> pd.DataFrame:
    """
    Convenience function to get Global.health data.
    
    Args:
        disease: Disease name (e.g., "COVID-19", "Monkeypox")
        country: Filter by country
        date_range: Tuple of (start_date, end_date)
        
    Returns:
        DataFrame with case data
    """
    accessor = GlobalHealthAccessor()
    return accessor.get_case_data(disease, country, date_range)


def list_datasets() -> pd.DataFrame:
    """List available Global.health datasets."""
    accessor = GlobalHealthAccessor()
    return accessor.list_available_datasets()


if __name__ == "__main__":
    # Example usage
    gh = GlobalHealthAccessor()
    
    print("Available datasets:")
    print(gh.list_available_datasets())
    print("\n" + "="*60 + "\n")
    
    # Get COVID-19 metadata
    print("COVID-19 Outbreak Metadata:")
    metadata = gh.get_outbreak_metadata("COVID-19")
    for key, value in metadata.items():
        if key == "countries" and value:
            print(f"  {key}: {len(value)} countries")
        else:
            print(f"  {key}: {value}")
