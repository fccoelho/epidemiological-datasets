"""
HealthData.gov Accessor

Provides access to US health system data including hospital capacity,
COVID-19 metrics, and other health data from the HHS Protect ecosystem.

Data Source: https://healthdata.gov/
API: Socrata Open Data API (SODA)
License: Public Domain (US Government)
Update Frequency: Daily to Weekly
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import ClassVar, Optional, Union, List, Dict

from epidatasets._base import BaseAccessor
from urllib.request import urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError

import pandas as pd


class HealthDataGovAccessor(BaseAccessor):
    """
    Accessor for HealthData.gov US health system data.
    
    HealthData.gov provides data on hospital capacity, COVID-19 metrics,
    and other health system indicators from US healthcare facilities.
    
    Example:
        >>> from epidatasets.sources.healthdata_gov import HealthDataGovAccessor
        >>> hdg = HealthDataGovAccessor()
        >>> hospitals = hdg.get_hospital_capacity(state="CA")
        >>> covid = hdg.get_covid_metrics(state="NY")
    """

    source_name: ClassVar[str] = "healthdata_gov"
    source_description: ClassVar[str] = (
        "US health system data including hospital capacity, "
        "COVID-19 metrics, and other health data from the HHS Protect ecosystem."
    )
    source_url: ClassVar[str] = "https://healthdata.gov/"

    BASE_URL = "https://healthdata.gov"
    API_BASE = "https://healthdata.gov/api/views"
    
    # Popular dataset IDs on HealthData.gov
    DATASETS = {
        "hospital_capacity": {
            "id": "g62h-syeh",
            "name": "COVID-19 Reported Patient Impact and Hospital Capacity by State",
            "description": "Hospital capacity data by state",
            "update_frequency": "Daily",
            "fields": [
                "state", "date", "inpatient_beds_used", "inpatient_beds_used_covid",
                "staffed_icu_adult_patients_confirmed_covid", "total_staffed_adult_icu_beds"
            ]
        },
        "hospital_capacity_facility": {
            "id": "anag-cw7u",
            "name": "COVID-19 Reported Patient Impact and Hospital Capacity by Facility",
            "description": "Hospital capacity data by individual facility",
            "update_frequency": "Weekly"
        },
        "covid19_nursing_homes": {
            "id": "77hq-7k3a", 
            "name": "COVID-19 Nursing Home Data",
            "description": "Cases and deaths in nursing homes",
            "update_frequency": "Weekly"
        },
        "covid19_testing": {
            "id": "j8mb-icvb",
            "name": "COVID-19 Diagnostic Laboratory Testing",
            "description": "Testing data by state",
            "update_frequency": "Daily"
        },
        "vaccination_state": {
            "id": "unsk-b7fc",
            "name": "COVID-19 Vaccination Data by State",
            "description": "Vaccination progress by state",
            "update_frequency": "Daily"
        }
    }
    
    # US States and territories
    STATES = [
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
        "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
        "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
        "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
        "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
        "DC", "PR", "VI", "GU", "AS", "MP"
    ]
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize HealthData.gov accessor.
        
        Args:
            cache_dir: Directory to cache downloaded data
        """
        self.cache_dir = Path(cache_dir) if cache_dir else Path.home() / ".cache" / "epi_data" / "healthdata_gov"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_ttl = timedelta(hours=6)  # Shorter cache for daily-updated data
        
    def _get_cached_path(self, dataset_id: str) -> Path:
        """Get cache file path for a dataset."""
        return self.cache_dir / f"{dataset_id}.csv"
    
    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cache is still valid."""
        if not cache_path.exists():
            return False
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        return datetime.now() - mtime < self._cache_ttl
    
    def _fetch_socrata_data(
        self,
        dataset_id: str,
        limit: int = 50000,
        where: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Fetch data from Socrata API.
        
        Args:
            dataset_id: Socrata dataset ID
            limit: Maximum rows to fetch
            where: SoQL where clause
            
        Returns:
            DataFrame with data
        """
        url = f"{self.API_BASE}/{dataset_id}/rows.csv"
        params = {"accessType": "DOWNLOAD", "limit": limit}
        if where:
            params["$where"] = where
        
        query_string = urlencode(params)
        full_url = f"{url}?{query_string}"
        
        try:
            return pd.read_csv(full_url, low_memory=False)
        except Exception as e:
            raise RuntimeError(f"Failed to fetch data from {full_url}: {e}")
    
    def list_countries(self) -> pd.DataFrame:
        """
        List US states and territories covered by HealthData.gov.

        Returns:
            DataFrame with state codes
        """
        return pd.DataFrame({"state_code": self.STATES})

    def list_datasets(self) -> pd.DataFrame:
        """
        List available datasets.
        
        Returns:
            DataFrame with dataset information
        """
        datasets = []
        for key, info in self.DATASETS.items():
            datasets.append({
                "key": key,
                "dataset_id": info["id"],
                "name": info["name"],
                "description": info["description"],
                "update_frequency": info.get("update_frequency", "Unknown"),
                "url": f"{self.BASE_URL}/dataset/{info['id']}"
            })
        return pd.DataFrame(datasets)
    
    def get_hospital_capacity(
        self,
        state: Optional[str] = None,
        date_range: Optional[tuple] = None,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Get hospital capacity data by state.
        
        Args:
            state: State abbreviation (e.g., "CA", "NY") or None for all states
            date_range: Tuple of (start_date, end_date) as strings (YYYY-MM-DD)
            use_cache: Whether to use cached data
            
        Returns:
            DataFrame with hospital capacity metrics
            
        Example:
            >>> hdg = HealthDataGovAccessor()
            >>> ca_hospitals = hdg.get_hospital_capacity(state="CA", 
            ...                                          date_range=("2024-01-01", "2024-03-01"))
        """
        dataset_id = self.DATASETS["hospital_capacity"]["id"]
        cache_path = self._get_cached_path(f"hospital_capacity_{state or 'all'}")
        
        # Build query
        where_clauses = []
        if state:
            where_clauses.append(f"state='{state.upper()}'")
        if date_range:
            start, end = date_range
            where_clauses.append(f"date>='{start}' AND date<='{end}'")
        
        where = " AND ".join(where_clauses) if where_clauses else None
        
        # Check cache
        if use_cache and self._is_cache_valid(cache_path) and not where:
            df = pd.read_csv(cache_path, low_memory=False)
        else:
            df = self._fetch_socrata_data(dataset_id, where=where)
            if not where:  # Only cache full dataset requests
                df.to_csv(cache_path, index=False)
        
        # Convert date column
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        
        return df.reset_index(drop=True)
    
    def get_covid_metrics(
        self,
        state: Optional[str] = None,
        date_range: Optional[tuple] = None,
        metrics: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Get COVID-19 metrics from hospital reporting.
        
        Args:
            state: State abbreviation or None for all
            date_range: (start_date, end_date) tuple
            metrics: Specific metrics to include (default: all)
            
        Returns:
            DataFrame with COVID-19 metrics
        """
        # Hospital capacity dataset includes COVID metrics
        df = self.get_hospital_capacity(state, date_range)
        
        # Standard COVID metrics in this dataset
        covid_cols = [
            "inpatient_beds_used_covid",
            "staffed_icu_adult_patients_confirmed_covid",
            "total_adult_patients_hospitalized_confirmed_covid",
            "total_pediatric_patients_hospitalized_confirmed_covid",
            "deaths_covid"
        ]
        
        if metrics:
            covid_cols = [c for c in covid_cols if c in metrics]
        
        # Select relevant columns
        base_cols = ["state", "date"] if "state" in df.columns else ["date"]
        available_cols = [c for c in base_cols + covid_cols if c in df.columns]
        
        return df[available_cols].copy()
    
    def get_nursing_home_data(
        self,
        state: Optional[str] = None,
        week_ending: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get COVID-19 nursing home data.
        
        Args:
            state: State abbreviation
            week_ending: Specific week ending date (YYYY-MM-DD)
            
        Returns:
            DataFrame with nursing home cases and deaths
        """
        dataset_id = self.DATASETS["covid19_nursing_homes"]["id"]
        
        where_clauses = []
        if state:
            where_clauses.append(f"provider_state='{state.upper()}'")
        if week_ending:
            where_clauses.append(f"week_ending='{week_ending}'")
        
        where = " AND ".join(where_clauses) if where_clauses else None
        
        return self._fetch_socrata_data(dataset_id, where=where)
    
    def get_vaccination_data(
        self,
        state: Optional[str] = None,
        date_range: Optional[tuple] = None
    ) -> pd.DataFrame:
        """
        Get COVID-19 vaccination data by state.
        
        Args:
            state: State abbreviation
            date_range: (start_date, end_date) tuple
            
        Returns:
            DataFrame with vaccination metrics
        """
        dataset_id = self.DATASETS["vaccination_state"]["id"]
        
        where_clauses = []
        if state:
            where_clauses.append(f"location='{state.upper()}'")
        if date_range:
            start, end = date_range
            where_clauses.append(f"date>='{start}' AND date<='{end}'")
        
        where = " AND ".join(where_clauses) if where_clauses else None
        
        df = self._fetch_socrata_data(dataset_id, where=where)
        
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        
        return df
    
    def get_testing_data(
        self,
        state: Optional[str] = None,
        date_range: Optional[tuple] = None
    ) -> pd.DataFrame:
        """
        Get COVID-19 diagnostic testing data.
        
        Args:
            state: State abbreviation
            date_range: (start_date, end_date) tuple
            
        Returns:
            DataFrame with testing metrics
        """
        dataset_id = self.DATASETS["covid19_testing"]["id"]
        
        where_clauses = []
        if state:
            where_clauses.append(f"state='{state.upper()}'")
        if date_range:
            start, end = date_range
            where_clauses.append(f"date>='{start}' AND date<='{end}'")
        
        where = " AND ".join(where_clauses) if where_clauses else None
        
        df = self._fetch_socrata_data(dataset_id, where=where)
        
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        
        return df
    
    def get_current_hospital_stats(
        self,
        state: Optional[str] = None
    ) -> Dict:
        """
        Get current hospital statistics summary.
        
        Args:
            state: State abbreviation or None for US total
            
        Returns:
            Dictionary with current statistics
        """
        df = self.get_hospital_capacity(state)
        
        if df.empty:
            return {"error": "No data available"}
        
        # Get most recent date
        latest = df.loc[df["date"].idxmax()] if "date" in df.columns else df.iloc[0]
        
        stats = {
            "date": latest.get("date"),
            "state": state or "US Total"
        }
        
        # Key metrics
        key_metrics = [
            "inpatient_beds_used",
            "inpatient_beds_used_covid", 
            "total_staffed_adult_icu_beds",
            "staffed_icu_adult_patients_confirmed_covid"
        ]
        
        for metric in key_metrics:
            if metric in latest:
                stats[metric] = latest[metric]
        
        return stats
    
    def compare_states(
        self,
        states: List[str],
        metric: str = "inpatient_beds_used_covid",
        date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Compare metrics across multiple states.
        
        Args:
            states: List of state abbreviations
            metric: Metric to compare
            date: Specific date (default: most recent)
            
        Returns:
            DataFrame with state comparisons
        """
        data = []
        for state in states:
            try:
                df = self.get_hospital_capacity(state=state, date_range=(date, date) if date else None)
                if not df.empty:
                    latest = df.loc[df["date"].idxmax()]
                    data.append({
                        "state": state,
                        "date": latest.get("date"),
                        metric: latest.get(metric)
                    })
            except Exception as e:
                data.append({
                    "state": state,
                    "error": str(e)
                })
        
        return pd.DataFrame(data)


# Convenience functions
def get_us_hospital_capacity(
    state: Optional[str] = None,
    date_range: Optional[tuple] = None
) -> pd.DataFrame:
    """
    Convenience function to get US hospital capacity data.
    
    Args:
        state: State abbreviation (e.g., "CA")
        date_range: (start_date, end_date) tuple
        
    Returns:
        DataFrame with hospital capacity data
    """
    accessor = HealthDataGovAccessor()
    return accessor.get_hospital_capacity(state, date_range)


def get_us_covid_data(
    state: Optional[str] = None,
    date_range: Optional[tuple] = None
) -> pd.DataFrame:
    """
    Convenience function to get US COVID-19 data.
    
    Args:
        state: State abbreviation
        date_range: (start_date, end_date) tuple
        
    Returns:
        DataFrame with COVID-19 metrics
    """
    accessor = HealthDataGovAccessor()
    return accessor.get_covid_metrics(state, date_range)
