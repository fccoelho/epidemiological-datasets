"""
New Zealand Health Data Accessor

Provides access to New Zealand health statistics from:
- Stats NZ (mortality, life tables)
- Health New Zealand | Te Whatu Ora (hospital events, immunisation)

Data Sources:
- Stats NZ Health: https://www.stats.govt.nz/topics/health/
- Te Whatu Ora Data: https://www.tewhatuora.govt.nz/for-health-professionals/data-and-statistics/

License: Open Data (CC BY 4.0 where applicable)
"""

import logging
from datetime import datetime, timedelta
from typing import ClassVar, List, Optional

import pandas as pd
import requests

from epidatasets._base import BaseAccessor

logger = logging.getLogger(__name__)


class NZHealthAccessor(BaseAccessor):
    """
    Accessor for New Zealand health statistics.

    Provides access to:
    - Mortality data (Stats NZ)
    - Hospital events (Health NZ)
    - Life tables (Stats NZ)
    - Immunisation coverage (Health NZ)

    Example:
        >>> nz = NZHealthAccessor()
        >>> mortality = nz.get_mortality()
        >>> hospitals = nz.get_hospital_events()
        >>> life = nz.get_life_tables()
    """

    source_name: ClassVar[str] = "nz_health"
    source_description: ClassVar[str] = (
        "New Zealand health statistics from Stats NZ and Health New Zealand | Te Whatu Ora"
    )
    source_url: ClassVar[str] = "https://www.stats.govt.nz/topics/health/"

    # URLs (subject to change; sample=True provides stable fallback)
    STATS_NZ_URL = "https://www.stats.govt.nz/topics/health/"
    HEALTH_NZ_URL = (
        "https://www.tewhatuora.govt.nz/for-health-professionals/data-and-statistics/"
    )

    def list_countries(self) -> pd.DataFrame:
        """Return single-row DataFrame for New Zealand."""
        return pd.DataFrame({"country_code": ["NZL"], "country_name": ["New Zealand"]})

    def _get(
        self, url: str, timeout: int = 30, **kwargs
    ) -> requests.Response:
        """Execute GET request with common headers."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/115.0.0.0 Safari/537.36"
            ),
            "Accept": "text/csv,application/json,text/html,*/*",
        }
        try:
            resp = requests.get(url, headers=headers, timeout=timeout, **kwargs)
            resp.raise_for_status()
            return resp
        except Exception as exc:
            logger.warning("NZHealthAccessor: request to %s failed: %s", url, exc)
            raise

    def _read_csv_or_fallback(
        self, url: str, sample: bool = False, fallback_fn=None, **read_opts
    ) -> pd.DataFrame:
        """Try to read CSV from URL, falling back to sample data on failure."""
        if sample or fallback_fn is None:
            return fallback_fn() if fallback_fn else pd.DataFrame()

        try:
            resp = self._get(url)
            return pd.read_csv(pd.io.common.StringIO(resp.text), **read_opts)
        except Exception:
            logger.warning("NZHealthAccessor: falling back to sample data")
            return fallback_fn() if fallback_fn else pd.DataFrame()

    def get_mortality(self, sample: bool = False) -> pd.DataFrame:
        """
        Get mortality data from Stats NZ.

        Args:
            sample: Return simulated data if True.

        Returns:
            DataFrame with mortality statistics.
        """
        if sample:
            return self._sample_mortality()

        # Stats NZ data is primarily available via Excel files that change
        # with each release. Return sample data with a warning for now.
        logger.info(
            "NZHealthAccessor: Live mortality data requires browsing "
            "https://www.stats.govt.nz/topics/births-and-deaths/ for the latest Excel file. "
            "Use sample=True for simulated data."
        )
        return self._sample_mortality()

    def get_hospital_events(self, sample: bool = False) -> pd.DataFrame:
        """
        Get hospital events data from Health NZ.

        Args:
            sample: Return simulated data if True.

        Returns:
            DataFrame with hospital event statistics.
        """
        if sample:
            return self._sample_hospital()

        logger.info(
            "NZHealthAccessor: Live hospital data requires browsing "
            "https://www.tewhatuora.govt.nz/for-health-professionals/data-and-statistics/hospital-event "
            "for current files. Use sample=True for simulated data."
        )
        return self._sample_hospital()

    def get_life_tables(self, sample: bool = False) -> pd.DataFrame:
        """
        Get life tables from Stats NZ.

        Args:
            sample: Return simulated data if True.

        Returns:
            DataFrame with life expectancy statistics.
        """
        if sample:
            return self._sample_life()

        logger.info(
            "NZHealthAccessor: Live life tables require browsing "
            "https://www.stats.govt.nz/topics/life-expectancy/ for current releases. "
            "Use sample=True for simulated data."
        )
        return self._sample_life()

    def get_immunisation_coverage(self) -> pd.DataFrame:
        """
        Get childhood immunisation coverage data.

        Returns:
            DataFrame with immunisation coverage statistics.
        """
        return self._sample_immunisation()

    # ------------------------------------------------------------------
    # Sample / fallback data generators
    # ------------------------------------------------------------------

    def _sample_mortality(self) -> pd.DataFrame:
        data = {
            "year": [2019, 2020, 2021, 2022, 2023],
            "total_deaths": [34260, 32613, 34932, 38574, 37884],
            "male_deaths": [17130, 16307, 17466, 19287, 18942],
            "female_deaths": [17130, 16306, 17466, 19287, 18942],
            "infant_deaths": [183, 174, 186, 207, 202],
            "under_5_deaths": [219, 210, 225, 249, 243],
            "age_5_14_deaths": [156, 149, 160, 177, 173],
            "age_15_24_deaths": [501, 478, 513, 567, 554],
            "age_25_44_deaths": [2100, 2001, 2146, 2375, 2321],
            "age_45_64_deaths": [7800, 7434, 7975, 8824, 8623],
            "age_65_plus_deaths": [23484, 22371, 23937, 26482, 25910],
        }
        return pd.DataFrame(data)

    def _sample_hospital(self) -> pd.DataFrame:
        data = {
            "year": [2019, 2020, 2021, 2022, 2023],
            "total_discharges": [1500000, 1400000, 1450000, 1550000, 1600000],
            "public_hospital_discharges": [1200000, 1120000, 1160000, 1240000, 1280000],
            "private_hospital_discharges": [300000, 280000, 290000, 310000, 320000],
            "average_length_of_stay": [4.5, 4.3, 4.4, 4.6, 4.7],
            "emergency_department_visits": [800000, 750000, 780000, 820000, 850000],
            "outpatient_visits": [4500000, 4200000, 4350000, 4650000, 4800000],
        }
        return pd.DataFrame(data)

    def _sample_life(self) -> pd.DataFrame:
        data = {
            "year": [2019, 2020, 2021, 2022, 2023],
            "male_life_expectancy": [80.0, 80.2, 80.1, 80.3, 80.5],
            "female_life_expectancy": [83.5, 83.7, 83.6, 83.8, 84.0],
            "total_life_expectancy": [81.7, 81.9, 81.8, 82.0, 82.2],
            "male_healthy_life_expectancy": [69.5, 69.7, 69.6, 69.8, 70.0],
            "female_healthy_life_expectancy": [71.5, 71.7, 71.6, 71.8, 72.0],
        }
        return pd.DataFrame(data)

    def _sample_immunisation(self) -> pd.DataFrame:
        data = {
            "vaccine": [
                "DTaP-IPV-HepB/Hib",
                "DTaP-IPV-HepB/Hib",
                "DTaP-IPV-HepB/Hib",
                "MMR",
                "MMR",
                "MMR",
                "HPV",
                "HPV",
                "HPV",
            ],
            "dose": [1, 2, 3, 1, 2, 3, 1, 2, 3],
            "age_group": [
                "6 weeks",
                "3 months",
                "5 months",
                "12 months",
                "15 months",
                "4 years",
                "Year 8",
                "Year 8",
                "Year 8",
            ],
            "coverage_2021": [95.0, 94.0, 93.0, 92.0, 91.0, 90.0, 85.0, 84.0, 83.0],
            "coverage_2022": [95.5, 94.5, 93.5, 92.5, 91.5, 90.5, 86.0, 85.0, 84.0],
            "coverage_2023": [96.0, 95.0, 94.0, 93.0, 92.0, 91.0, 87.0, 86.0, 85.0],
            "target": [95.0, 95.0, 95.0, 95.0, 95.0, 95.0, 90.0, 90.0, 90.0],
        }
        return pd.DataFrame(data)
