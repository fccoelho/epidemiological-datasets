"""
UK Health Security Agency (UKHSA) Accessor

Provides access to UK public health surveillance data including infectious diseases,
immunization coverage, and respiratory illness tracking.

Data Source: https://api.ukhsa-dashboard.data.gov.uk/
License: Open Government Licence (OGL)
Update Frequency: Weekly
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Union, List
from urllib.parse import quote
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

logger = logging.getLogger(__name__)

import pandas as pd


class UKHSAAccessor:
    """
    Accessor for UK Health Security Agency data via the UKHSA Dashboard API.

    Fetches real surveillance data for COVID-19, Influenza, Measles, and other
    infectious diseases tracked by UKHSA.

    Example:
        >>> from scripts.accessors.ukhsa import UKHSAAccessor
        >>> ukhsa = UKHSAAccessor()
        >>> covid = ukhsa.get_infectious_disease_data("COVID-19")
        >>> measles = ukhsa.get_infectious_disease_data("Measles")
    """

    API_BASE = "https://api.ukhsa-dashboard.data.gov.uk"

    # Map disease names to their API path components
    DISEASE_MAP = {
        "COVID-19": {
            "sub_theme": "respiratory",
            "topic": "COVID-19",
            "metric": "COVID-19_cases_casesByDay",
        },
        "Influenza": {
            "sub_theme": "respiratory",
            "topic": "Influenza",
            "metric": "influenza_testing_positivityByWeek",
        },
        "RSV": {
            "sub_theme": "respiratory",
            "topic": "RSV",
            "metric": "RSV_cases_casesByWeek",
        },
        "Measles": {
            "sub_theme": "vaccine_preventable",
            "topic": "Measles",
            "metric": "measles_cases_casesByOnsetWeek",
        },
    }

    # Default page size for API requests (max observed: 365)
    PAGE_SIZE = 365

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize UKHSA accessor.

        Args:
            cache_dir: Directory to cache downloaded data. If None, uses temp directory.
        """
        self.cache_dir = Path(cache_dir) if cache_dir else Path.home() / ".cache" / "epi_data" / "ukhsa"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_ttl = timedelta(hours=24)

    def _get_cached_path(self, filename: str) -> Path:
        """Get cache file path."""
        return self.cache_dir / filename

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cache is still valid."""
        if not cache_path.exists():
            return False
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        return datetime.now() - mtime < self._cache_ttl

    def _fetch_api(self, url: str) -> dict:
        """Fetch a single page from the UKHSA API."""
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())

    def _fetch_all_pages(self, url: str, max_pages: int = 100) -> list:
        """Fetch all pages from a paginated UKHSA API endpoint."""
        all_results = []
        page_url = f"{url}?page_size={self.PAGE_SIZE}"
        seen = set()
        for _ in range(max_pages):
            if not page_url or page_url in seen:
                if page_url in seen:
                    logger.warning("Pagination loop detected, stopping at: %s", page_url)
                break
            seen.add(page_url)
            data = self._fetch_api(page_url)
            all_results.extend(data.get("results", []))
            page_url = data.get("next")
        return all_results

    def _build_metric_url(self, disease: str, geography: str = "England") -> str:
        """Build the API URL for a disease metric."""
        if disease not in self.DISEASE_MAP:
            available = ", ".join(self.DISEASE_MAP.keys())
            raise ValueError(f"Unknown disease '{disease}'. Available: {available}")

        info = self.DISEASE_MAP[disease]
        geo_encoded = quote(geography, safe="")
        return (
            f"{self.API_BASE}/themes/infectious_disease"
            f"/sub_themes/{info['sub_theme']}"
            f"/topics/{info['topic']}"
            f"/geography_types/Nation"
            f"/geographies/{geo_encoded}"
            f"/metrics/{info['metric']}"
        )

    def get_infectious_disease_data(
        self,
        disease: str,
        years: Optional[List[int]] = None,
        geography: str = "England",
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Get infectious disease surveillance data from UKHSA.

        Args:
            disease: Disease name ("COVID-19", "Influenza", "Measles", "RSV")
            years: Filter to specific years (optional, default: all available)
            geography: UK geography (default: "England")
            use_cache: Whether to use cached data if available

        Returns:
            DataFrame with columns: date, disease, geography, cases, year, epiweek
        """
        cache_file = f"{disease.lower().replace('-', '_')}_{geography.lower()}.csv"
        cache_path = self._get_cached_path(cache_file)

        if use_cache and self._is_cache_valid(cache_path):
            df = pd.read_csv(cache_path, parse_dates=["date"])
        else:
            url = self._build_metric_url(disease, geography)
            try:
                records = self._fetch_all_pages(url)
            except (HTTPError, URLError) as e:
                raise RuntimeError(f"Failed to fetch {disease} data from UKHSA API: {e}")

            if not records:
                return pd.DataFrame(columns=["date", "disease", "geography", "cases", "year", "epiweek"])

            df = pd.DataFrame(records)
            df = df.rename(columns={
                "metric_value": "cases",
                "topic": "disease",
            })
            df["date"] = pd.to_datetime(df["date"])
            if "cases" not in df.columns:
                logger.warning("API response missing 'metric_value' field; 'cases' column will be absent")
            # Keep useful columns
            keep = ["date", "disease", "geography", "cases", "year", "epiweek"]
            df = df[[c for c in keep if c in df.columns]]
            df.to_csv(cache_path, index=False)

        if years:
            if "year" in df.columns:
                df = df[df["year"].isin(years)]
            elif "date" in df.columns:
                df = df[df["date"].dt.year.isin(years)]

        return df.sort_values("date").reset_index(drop=True)

    def list_available_diseases(self) -> pd.DataFrame:
        """
        List diseases available through this accessor.

        Returns:
            DataFrame with disease names and their API details.
        """
        rows = []
        for name, info in self.DISEASE_MAP.items():
            rows.append({
                "disease": name,
                "sub_theme": info["sub_theme"],
                "metric": info["metric"],
            })
        return pd.DataFrame(rows)

    def get_available_metrics(self, disease: str, geography: str = "England") -> List[str]:
        """
        List all available metrics for a disease from the API.

        Args:
            disease: Disease name
            geography: UK geography

        Returns:
            List of metric names available for this disease.
        """
        if disease not in self.DISEASE_MAP:
            available = ", ".join(self.DISEASE_MAP.keys())
            raise ValueError(f"Unknown disease '{disease}'. Available: {available}")

        info = self.DISEASE_MAP[disease]
        geo_encoded = quote(geography, safe="")
        url = (
            f"{self.API_BASE}/themes/infectious_disease"
            f"/sub_themes/{info['sub_theme']}"
            f"/topics/{info['topic']}"
            f"/geography_types/Nation"
            f"/geographies/{geo_encoded}"
            f"/metrics"
        )
        try:
            data = self._fetch_api(url)
            results = data.get("results", data) if isinstance(data, dict) else data
            return [m["name"] for m in results if isinstance(m, dict) and "name" in m]
        except Exception as e:
            logger.warning("Failed to fetch metrics for %s: %s", disease, e)
            return []

    # ── Backward-compatible methods ──────────────────────────────────────
    # These existed in the original stub implementation. They now delegate
    # to get_infectious_disease_data() where possible, or return structured
    # DataFrames with real metadata.

    REGIONS = ["England", "Wales", "Scotland", "Northern Ireland"]

    def get_immunization_coverage(
        self,
        vaccines: Union[str, List[str]],
        years: List[int],
        age_groups: Optional[List[str]] = None,
        regions: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """Get vaccination coverage data. Currently limited to available API data."""
        logger.info("Immunization coverage data is not yet available via the UKHSA Dashboard API.")
        if isinstance(vaccines, str):
            vaccines = [vaccines]
        regions = regions or ["England"]
        age_groups = age_groups or ["1 year", "2 years", "5 years"]
        data = []
        for vaccine in vaccines:
            for year in years:
                for region in regions:
                    for age in age_groups:
                        data.append({
                            "vaccine": vaccine, "year": year, "region": region,
                            "age_group": age, "coverage_percent": None, "target": 95.0,
                            "data_source": "UKHSA",
                            "note": "Immunization coverage not yet available via Dashboard API",
                        })
        return pd.DataFrame(data)

    def get_seasonal_influenza_data(
        self,
        seasons: List[str],
        regions: Optional[List[str]] = None,
        metrics: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """Get seasonal influenza data. Delegates to get_infectious_disease_data for Influenza."""
        df = self.get_infectious_disease_data("Influenza")
        if not df.empty and seasons:
            # Map seasons like "2023/24" to year 2023
            season_years = []
            for s in seasons:
                try:
                    season_years.append(int(s.split("/")[0]))
                except (ValueError, IndexError):
                    pass
            if season_years and "year" in df.columns:
                df = df[df["year"].isin(season_years)]
        return df.reset_index(drop=True)

    def get_antimicrobial_resistance_data(
        self,
        years: List[int],
        organisms: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """Get AMR data. Not yet available via Dashboard API."""
        logger.info("AMR data is not yet available via the UKHSA Dashboard API.")
        organisms = organisms or ["E. coli", "Klebsiella", "MRSA", "MSSA"]
        data = []
        for year in years:
            for organism in organisms:
                data.append({
                    "year": year, "organism": organism,
                    "resistance_rate": None, "sample_size": None,
                    "data_source": "UKHSA",
                    "note": "AMR data not yet available via Dashboard API",
                })
        return pd.DataFrame(data)

    def get_covid19_metrics(
        self,
        metrics: List[str],
        date_range: Optional[tuple] = None,
        regions: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """Get COVID-19 metrics. Delegates to get_infectious_disease_data."""
        df = self.get_infectious_disease_data("COVID-19")
        if date_range and "date" in df.columns:
            start, end = date_range
            df = df[(df["date"] >= start) & (df["date"] <= end)]
        return df.reset_index(drop=True)

    def get_available_indicators(self) -> pd.DataFrame:
        """List all available surveillance indicators."""
        indicators = [
            {"category": "Infectious Diseases", "indicator": "COVID-19 cases", "frequency": "Daily", "api_available": True},
            {"category": "Infectious Diseases", "indicator": "Influenza cases", "frequency": "Weekly", "api_available": True},
            {"category": "Infectious Diseases", "indicator": "Measles cases", "frequency": "Weekly", "api_available": True},
            {"category": "Infectious Diseases", "indicator": "RSV cases", "frequency": "Weekly", "api_available": True},
            {"category": "Vaccination", "indicator": "Childhood coverage", "frequency": "Quarterly", "api_available": False},
            {"category": "AMR", "indicator": "Antimicrobial resistance", "frequency": "Annual", "api_available": False},
        ]
        return pd.DataFrame(indicators)

    def get_data_sources(self) -> pd.DataFrame:
        """Get information about UKHSA data sources."""
        sources = [
            {"category": "Dashboard API", "name": "UKHSA Dashboard", "url": self.API_BASE},
            {"category": "Infectious Diseases", "name": "COVID-19", "url": f"{self.API_BASE}/themes/infectious_disease/sub_themes/respiratory/topics/COVID-19"},
            {"category": "Infectious Diseases", "name": "Influenza", "url": f"{self.API_BASE}/themes/infectious_disease/sub_themes/respiratory/topics/Influenza"},
            {"category": "Infectious Diseases", "name": "Measles", "url": f"{self.API_BASE}/themes/infectious_disease/sub_themes/vaccine_preventable/topics/Measles"},
        ]
        return pd.DataFrame(sources)


# Convenience functions
def get_ukhsa_disease_data(
    disease: str,
    years: Optional[List[int]] = None,
) -> pd.DataFrame:
    """
    Convenience function to get UKHSA disease data.

    Args:
        disease: Disease name ("COVID-19", "Influenza", "Measles", "RSV")
        years: Filter to specific years (optional)

    Returns:
        DataFrame with surveillance data
    """
    accessor = UKHSAAccessor()
    return accessor.get_infectious_disease_data(disease, years=years)


def get_uk_vaccination_coverage(
    vaccine: str,
    years: List[int],
) -> pd.DataFrame:
    """Get UK vaccination coverage data."""
    accessor = UKHSAAccessor()
    return accessor.get_immunization_coverage(vaccine, years)


def list_diseases() -> pd.DataFrame:
    """List available diseases."""
    accessor = UKHSAAccessor()
    return accessor.list_available_diseases()


if __name__ == "__main__":
    ukhsa = UKHSAAccessor()

    print("Available diseases:")
    print(ukhsa.list_available_diseases())
    print("\n" + "=" * 60 + "\n")

    for disease in ["COVID-19", "Measles"]:
        print(f"{disease} data:")
        df = ukhsa.get_infectious_disease_data(disease)
        print(f"  Records: {len(df)}")
        if len(df) > 0:
            print(f"  Date range: {df['date'].min()} to {df['date'].max()}")
            print(df.head(3).to_string())
        print()
