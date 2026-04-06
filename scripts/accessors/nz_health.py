"""
New Zealand Ministry of Health Accessor

Provides access to New Zealand public health statistics including mortality,
hospital events, and immunisation data.

Data Source: https://www.health.govt.nz/nz-health-statistics
License: Creative Commons Attribution 4.0 International (CC BY 4.0)
Update Frequency: Annual
Coverage: New Zealand
"""

import logging
from io import StringIO
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

import pandas as pd

logger = logging.getLogger(__name__)


class NZHealthAccessor:
    """
    Accessor for New Zealand Ministry of Health statistics.

    Fetches publicly available health data including mortality,
    hospital events, and immunisation coverage from the NZ Ministry of Health
    and Health New Zealand – Te Whatu Ora.

    Example:
        >>> from scripts.accessors.nz_health import NZHealthAccessor
        >>> nz = NZHealthAccessor()
        >>> mortality = nz.get_mortality(years=[2021, 2022])
        >>> hospitals = nz.get_hospital_events()
        >>> immunisation = nz.get_immunisation_coverage()
    """

    BASE_URL = "https://www.health.govt.nz"

    # Publicly available CSV/data endpoints from Health NZ and Stats NZ
    DATA_SOURCES = {
        "mortality": {
            "url": "https://www.stats.govt.nz/assets/Uploads/Deaths/Deaths-year-ended-December-2023/Download-data/deaths-year-ended-december-2023.csv",
            "description": "Deaths registered in New Zealand (Stats NZ)",
        },
        "life_tables": {
            "url": "https://www.stats.govt.nz/assets/Uploads/National-and-subnational-period-life-tables/National-and-subnational-period-life-tables-2017-2019/Download-data/New-Zealand-and-district-health-board-period-life-tables-2017-2019-by-NZDep2018-CSV.csv",
            "description": "NZ period life tables by deprivation index",
        },
        "hospitals": {
            "url": "https://www.health.govt.nz/system/files/documents/pages/public-hospitals-april-2026.csv",
            "description": "List of certified public hospitals in New Zealand",
        },
    }

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize NZ Health accessor.

        Args:
            cache_dir: Directory to cache downloaded data.
                       Defaults to ~/.cache/epi_data/nz_health/
        """
        self.cache_dir = (
            Path(cache_dir)
            if cache_dir
            else Path.home() / ".cache" / "epi_data" / "nz_health"
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_ttl = timedelta(hours=24)

    # ── Internal helpers ─────────────────────────────────────────────────

    def _get_cached_path(self, filename: str) -> Path:
        """Return the path to a cache file."""
        return self.cache_dir / filename

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Return True if the cache file exists and is younger than the TTL."""
        if not cache_path.exists():
            return False
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        return datetime.now() - mtime < self._cache_ttl

    def _fetch_csv(self, url: str) -> pd.DataFrame:
        """Download a CSV from *url* and return it as a DataFrame."""
        req = Request(url, headers={"User-Agent": "epidemiological-datasets/1.0"})
        try:
            with urlopen(req, timeout=30) as resp:
                content = resp.read().decode("utf-8", errors="replace")
            return pd.read_csv(StringIO(content))
        except (HTTPError, URLError) as exc:
            raise RuntimeError(f"Failed to fetch data from {url}: {exc}") from exc

    def _load_with_cache(self, key: str, url: str) -> pd.DataFrame:
        """Return cached DataFrame for *key*, downloading from *url* if needed."""
        cache_path = self._get_cached_path(f"{key}.csv")
        if self._is_cache_valid(cache_path):
            logger.info("Loading %s from cache.", key)
            return pd.read_csv(cache_path)
        logger.info("Downloading %s from %s", key, url)
        df = self._fetch_csv(url)
        df.to_csv(cache_path, index=False)
        return df

    # ── Public methods ───────────────────────────────────────────────────

    def get_mortality(
        self,
        years: Optional[List[int]] = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Download NZ mortality (deaths) data.

        Data comes from Stats NZ's registered deaths dataset and includes
        cause-of-death information broken down by age, sex, and ethnicity.

        Args:
            years: Filter to specific calendar years. If None, all years returned.
            use_cache: Use locally cached file if available and fresh.

        Returns:
            DataFrame with death records. Columns vary by source file but
            typically include: year, age, sex, ethnicity, cause_of_death.
        """
        source = self.DATA_SOURCES["mortality"]
        if use_cache:
            df = self._load_with_cache("mortality", source["url"])
        else:
            df = self._fetch_csv(source["url"])

        # Normalise column names to lowercase with underscores
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

        # Try to filter by year if a year column exists
        if years:
            year_cols = [c for c in df.columns if "year" in c]
            if year_cols:
                df = df[df[year_cols[0]].isin(years)]
            else:
                logger.warning(
                    "No year column found in mortality data; 'years' filter ignored."
                )

        return df.reset_index(drop=True)

    def get_hospital_events(
        self,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Download the list of certified public hospitals in New Zealand.

        Data comes from the Ministry of Health's certified providers list
        (updated annually).

        Args:
            use_cache: Use locally cached file if available and fresh.

        Returns:
            DataFrame with hospital details (name, location, district, etc.).
        """
        source = self.DATA_SOURCES["hospitals"]
        if use_cache:
            df = self._load_with_cache("hospitals", source["url"])
        else:
            df = self._fetch_csv(source["url"])

        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        return df.reset_index(drop=True)

    def get_immunisation_coverage(
        self,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Return a summary DataFrame of NZ immunisation coverage indicators.

        Full immunisation microdata requires access to the National Immunisation
        Register (NIR) which is not publicly downloadable. This method returns
        a structured summary of the most recently published coverage statistics
        sourced from the Ministry of Health's annual reports.

        Args:
            use_cache: Unused — data is static. Kept for API consistency.

        Returns:
            DataFrame with coverage rates by vaccine, age group, and year.
        """
        # Published figures from MoH Health and Independence Report 2023/2024
        records = [
            {
                "year": 2023,
                "vaccine": "Childhood immunisation (age 8 months)",
                "ethnicity": "Māori",
                "coverage_percent": 69.7,
                "data_source": "National Immunisation Register (NIR)",
            },
            {
                "year": 2023,
                "vaccine": "Childhood immunisation (age 8 months)",
                "ethnicity": "Non-Māori",
                "coverage_percent": 88.6,
                "data_source": "National Immunisation Register (NIR)",
            },
            {
                "year": 2023,
                "vaccine": "Childhood immunisation (age 2 years)",
                "ethnicity": "Māori",
                "coverage_percent": 68.9,
                "data_source": "National Immunisation Register (NIR)",
            },
            {
                "year": 2023,
                "vaccine": "Childhood immunisation (age 2 years)",
                "ethnicity": "Non-Māori",
                "coverage_percent": 87.8,
                "data_source": "National Immunisation Register (NIR)",
            },
        ]
        return pd.DataFrame(records)

    def get_life_tables(
        self,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Download NZ national period life tables (2017–2019) by deprivation index.

        Args:
            use_cache: Use locally cached file if available and fresh.

        Returns:
            DataFrame with life expectancy data by age, sex, and NZDep2018 decile.
        """
        source = self.DATA_SOURCES["life_tables"]
        if use_cache:
            df = self._load_with_cache("life_tables", source["url"])
        else:
            df = self._fetch_csv(source["url"])

        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        return df.reset_index(drop=True)

    def list_data_sources(self) -> pd.DataFrame:
        """
        List all data sources available through this accessor.

        Returns:
            DataFrame with source keys, URLs, and descriptions.
        """
        rows = [
            {"key": k, "url": v["url"], "description": v["description"]}
            for k, v in self.DATA_SOURCES.items()
        ]
        return pd.DataFrame(rows)


# ── Convenience functions ────────────────────────────────────────────────────


def get_nz_mortality(years: Optional[List[int]] = None) -> pd.DataFrame:
    """
    Convenience function to get NZ mortality data.

    Args:
        years: Filter to specific years (optional).

    Returns:
        DataFrame with registered death records.
    """
    return NZHealthAccessor().get_mortality(years=years)


def get_nz_hospital_events() -> pd.DataFrame:
    """
    Convenience function to get NZ hospital listing.

    Returns:
        DataFrame with certified public hospital details.
    """
    return NZHealthAccessor().get_hospital_events()


def get_nz_immunisation_coverage() -> pd.DataFrame:
    """
    Convenience function to get NZ immunisation coverage summary.

    Returns:
        DataFrame with published coverage rates by vaccine and ethnicity.
    """
    return NZHealthAccessor().get_immunisation_coverage()


if __name__ == "__main__":
    nz = NZHealthAccessor()

    print("NZ Health Data Sources:")
    print(nz.list_data_sources().to_string(index=False))
    print("\n" + "=" * 60 + "\n")

    print("Immunisation Coverage (published figures):")
    print(nz.get_immunisation_coverage().to_string(index=False))
    print("\n" + "=" * 60 + "\n")

    print("Hospital Events (public hospital list):")
    try:
        df = nz.get_hospital_events()
        print(f"Records: {len(df)}")
        print(df.head(5).to_string())
    except RuntimeError as e:
        print(f"Note: {e}")
    print()

    print("Mortality data:")
    try:
        df = nz.get_mortality()
        print(f"Records: {len(df)}")
        print(df.head(5).to_string())
    except RuntimeError as e:
        print(f"Note: {e}")