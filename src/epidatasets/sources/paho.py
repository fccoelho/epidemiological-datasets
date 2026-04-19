"""
PAHO (Pan American Health Organization) Data Accessor

This module provides access to health data from the Pan American Health
Organization (PAHO), which covers all countries in the Americas
(North, Central, South America and the Caribbean).

PAHO Data Portal: https://www.paho.org/en/data

Data available includes:
- Immunization coverage (vaccination rates)
- Disease surveillance (malaria, dengue, chikungunya, zika, etc.)
- Mortality and demographic data
- Health system indicators

Author: Flávio Codeço Coelho
License: MIT
"""

import logging
import time
from datetime import datetime
from io import StringIO
from typing import ClassVar, List, Optional

import pandas as pd
import requests

from epidatasets._base import BaseAccessor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PAHOAccessor(BaseAccessor):
    """
    Accessor for PAHO (Pan American Health Organization) health data.

    Provides access to health statistics covering all countries in the
    Americas (North America, Central America, South America, Caribbean).

    Example:
        >>> paho = PAHOAccessor()
        >>>
        >>> # Get immunization coverage for specific vaccines
        >>> imm_data = paho.get_immunization_coverage(
        ...     vaccines=['MCV1', 'DTP3'],
        ...     countries=['BRA', 'MEX', 'COL'],
        ...     years=list(range(2015, 2024))
        ... )
        >>>
        >>> # Get malaria incidence data
        >>> malaria = paho.get_malaria_incidence(
        ...     countries=['BRA', 'COL', 'PER'],
        ...     years=[2020, 2021, 2022]
        ... )

    Data Sources:
        - PAHO Data Portal: https://www.paho.org/en/data
        - PAHO Immunization: https://www.paho.org/en/topics/immunization
        - PAHO Disease Surveillance: Various country reports
    """

    source_name: ClassVar[str] = "paho"
    source_description: ClassVar[str] = (
        "Pan American Health Organization (PAHO) health data covering "
        "immunization, disease surveillance, and health indicators "
        "for countries in the Americas."
    )
    source_url: ClassVar[str] = "https://www.paho.org"

    BASE_URL = "https://www.paho.org"
    DATA_PORTAL_URL = "https://www.paho.org/en/data"

    # Country codes for PAHO member states
    COUNTRIES = {
        "ATG": "Antigua and Barbuda",
        "ARG": "Argentina",
        "BHS": "Bahamas",
        "BRB": "Barbados",
        "BLZ": "Belize",
        "BOL": "Bolivia",
        "BRA": "Brazil",
        "CAN": "Canada",
        "CHL": "Chile",
        "COL": "Colombia",
        "CRI": "Costa Rica",
        "CUB": "Cuba",
        "DMA": "Dominica",
        "DOM": "Dominican Republic",
        "ECU": "Ecuador",
        "SLV": "El Salvador",
        "GRD": "Grenada",
        "GTM": "Guatemala",
        "GUY": "Guyana",
        "HTI": "Haiti",
        "HND": "Honduras",
        "JAM": "Jamaica",
        "MEX": "Mexico",
        "NIC": "Nicaragua",
        "PAN": "Panama",
        "PRY": "Paraguay",
        "PER": "Peru",
        "KNA": "Saint Kitts and Nevis",
        "LCA": "Saint Lucia",
        "VCT": "Saint Vincent and the Grenadines",
        "SUR": "Suriname",
        "TTO": "Trinidad and Tobago",
        "USA": "United States of America",
        "URY": "Uruguay",
        "VEN": "Venezuela",
    }

    # PAHO subregions
    SUBREGIONS = {
        "North America": ["CAN", "USA"],
        "Central America": ["BLZ", "CRI", "SLV", "GTM", "HND", "MEX", "NIC", "PAN"],
        "Caribbean": [
            "ATG",
            "BHS",
            "BRB",
            "CUB",
            "DMA",
            "DOM",
            "GRD",
            "HTI",
            "JAM",
            "KNA",
            "LCA",
            "TTO",
            "VCT",
        ],
        "Andean": ["BOL", "COL", "ECU", "PER", "VEN"],
        "Southern Cone": ["ARG", "BRA", "CHL", "PRY", "URY"],
        "Guyanas": ["GUY", "SUR"],
    }

    # Vaccine codes (common PAHO/WHO codes)
    VACCINES = {
        "BCG": "Tuberculosis",
        "DTP1": "Diphtheria-tetanus-pertussis (1st dose)",
        "DTP3": "Diphtheria-tetanus-pertussis (3rd dose)",
        "HepB3": "Hepatitis B (3rd dose)",
        "Hib3": "Haemophilus influenzae type b (3rd dose)",
        "MCV1": "Measles-containing vaccine (1st dose)",
        "MCV2": "Measles-containing vaccine (2nd dose)",
        "Pol3": "Polio (3rd dose)",
        "PCV3": "Pneumococcal conjugate vaccine (3rd dose)",
        "ROTAC": "Rotavirus vaccine",
        "RCV1": "Rubella-containing vaccine (1st dose)",
        "YFV": "Yellow fever vaccine",
    }

    # Priority diseases for PAHO surveillance
    DISEASES = {
        "MALARIA": "Malaria",
        "DENGUE": "Dengue",
        "CHIKV": "Chikungunya",
        "ZIKV": "Zika virus",
        "YF": "Yellow fever",
        "MEASLES": "Measles",
        "COVID19": "COVID-19",
        "INFLUENZA": "Influenza",
    }

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize PAHO accessor.

        Args:
            cache_dir: Directory to cache downloaded data (optional)
        """
        self.cache_dir = cache_dir
        self._session = requests.Session()
        self._session.headers.update(
            {"User-Agent": "PAHO-Data-Accessor/1.0 (Research Purpose)"}
        )
        self._cache = {}

    def list_countries(self) -> pd.DataFrame:
        """
        List all PAHO member countries.

        Returns
        -------
            DataFrame with country codes and names
        """
        return pd.DataFrame(
            [(code, name) for code, name in self.COUNTRIES.items()],
            columns=["country_code", "country_name"],
        )

    def list_subregions(self) -> pd.DataFrame:
        """
        List PAHO subregions with their countries.

        Returns
        -------
            DataFrame with subregion information
        """
        data = []
        for subregion, countries in self.SUBREGIONS.items():
            for country in countries:
                data.append(
                    {
                        "subregion": subregion,
                        "country_code": country,
                        "country_name": self.COUNTRIES.get(country, country),
                    }
                )
        return pd.DataFrame(data)

    def list_vaccines(self) -> pd.DataFrame:
        """
        List available vaccine codes and descriptions.

        Returns
        -------
            DataFrame with vaccine information
        """
        return pd.DataFrame(
            [(code, desc) for code, desc in self.VACCINES.items()],
            columns=["vaccine_code", "vaccine_name"],
        )

    def list_diseases(self) -> pd.DataFrame:
        """
        List priority diseases for PAHO surveillance.

        Returns
        -------
            DataFrame with disease codes and names
        """
        return pd.DataFrame(
            [(code, name) for code, name in self.DISEASES.items()],
            columns=["disease_code", "disease_name"],
        )

    def get_countries_by_subregion(self, subregion: str) -> List[str]:
        """
        Get list of country codes for a subregion.

        Args:
            subregion: Subregion name (e.g., "South America", "Caribbean")

        Returns
        -------
            List of ISO3 country codes
        """
        return self.SUBREGIONS.get(subregion, [])

    def _fetch_csv_data(self, url: str, retries: int = 3) -> Optional[pd.DataFrame]:
        """
        Fetch CSV data from URL with retry logic.

        Args:
            url: URL to fetch
            retries: Number of retry attempts

        Returns
        -------
            DataFrame or None if failed
        """
        for attempt in range(retries):
            try:
                logger.info(
                    f"Fetching data from {url} (attempt {attempt + 1}/{retries})"
                )
                response = self._session.get(url, timeout=30)
                response.raise_for_status()

                # Try to parse as CSV
                df = pd.read_csv(StringIO(response.text))
                logger.info(f"Successfully fetched {len(df)} records")
                return df

            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < retries - 1:
                    time.sleep(2**attempt)  # Exponential backoff
                else:
                    logger.error(f"Failed to fetch data after {retries} attempts")
                    return None

    def get_immunization_coverage(
        self,
        vaccines: List[str],
        countries: Optional[List[str]] = None,
        years: Optional[List[int]] = None,
        subregion: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Get immunization coverage data for specified vaccines.

        This method returns vaccination coverage rates (% of target population)
        for the specified vaccines, countries, and years.

        Args:
            vaccines: List of vaccine codes (e.g., ['DTP3', 'MCV1'])
                     Use list_vaccines() to see available codes
            countries: List of ISO3 country codes (e.g., ['BRA', 'MEX'])
                      If None and subregion is None, returns all countries
            years: List of years (e.g., [2020, 2021, 2022])
                  If None, returns all available years
            subregion: PAHO subregion name (alternative to countries list)
                      Options: "North America", "Central America", "Caribbean",
                               "Andean", "Southern Cone", "Guyanas"

        Returns
        -------
            DataFrame with columns:
            - country_code: ISO3 country code
            - country_name: Country name
            - year: Year of observation
            - vaccine_code: Vaccine code
            - vaccine_name: Vaccine name
            - coverage: Coverage percentage (0-100)
            - target_population: Target population for vaccination
            - vaccinated: Number of vaccinated individuals

        Example:
            >>> paho = PAHOAccessor()
            >>> # Get DTP3 coverage for South America
            >>> df = paho.get_immunization_coverage(
            ...     vaccines=['DTP3'],
            ...     subregion='Southern Cone',
            ...     years=list(range(2015, 2024))
            ... )
            >>>
            >>> # Get multiple vaccines for specific countries
            >>> df = paho.get_immunization_coverage(
            ...     vaccines=['DTP3', 'MCV1', 'HepB3'],
            ...     countries=['BRA', 'COL', 'MEX'],
            ...     years=[2020, 2021, 2022]
            ... )

        Note:
            This uses WHO/UNICEF Estimates of National Immunization Coverage (WUENIC)
            data which is the standard source for immunization coverage.
        """
        # Resolve countries from subregion if specified
        if subregion and not countries:
            countries = self.get_countries_by_subregion(subregion)

        if not countries:
            countries = list(self.COUNTRIES.keys())

        # Filter to valid vaccine codes
        valid_vaccines = [v for v in vaccines if v in self.VACCINES]
        if not valid_vaccines:
            raise ValueError(
                f"No valid vaccine codes. Available: {list(self.VACCINES.keys())}"
            )

        # Use WHO Immunization API as the data source
        # This is the same data that PAHO uses
        logger.info(
            f"Fetching immunization data for {len(valid_vaccines)} vaccines, "
            f"{len(countries)} countries"
        )

        all_data = []

        for vaccine in valid_vaccines:
            for country in countries:
                # Fetch from WHO Immunization API
                df = self._fetch_who_immunization_data(country, vaccine, years)
                if df is not None and not df.empty:
                    df["vaccine_code"] = vaccine
                    df["vaccine_name"] = self.VACCINES.get(vaccine, vaccine)
                    df["country_name"] = self.COUNTRIES.get(country, country)
                    all_data.append(df)

        if not all_data:
            logger.warning("No data retrieved")
            return pd.DataFrame()

        result = pd.concat(all_data, ignore_index=True)

        # Standardize column names
        column_mapping = {
            "ISO_code": "country_code",
            "Country": "country_name",
            "Year": "year",
            "Coverage": "coverage",
            "TargetPopulation": "target_population",
            "Vaccinated": "vaccinated",
        }
        result = result.rename(
            columns={k: v for k, v in column_mapping.items() if k in result.columns}
        )

        logger.info(f"Retrieved {len(result)} immunization records")
        return result

    def _fetch_who_immunization_data(
        self, country: str, vaccine: str, years: Optional[List[int]] = None
    ) -> Optional[pd.DataFrame]:
        """
        Fetch immunization data from WHO API.

        Args:
            country: ISO3 country code
            vaccine: Vaccine code
            years: List of years

        Returns
        -------
            DataFrame or None
        """
        try:
            # WHO Immunization API endpoint
            url = "https://immunizationdata.who.int/api/data/MEASURE/Coverage"

            params = {
                "dimension": f"GEOGRAPHY:{country};VACCINE:{vaccine}",
                "format": "json",
            }

            response = self._session.get(url, params=params, timeout=30)

            if response.status_code == 200:
                data = response.json()

                # Parse the response
                records = []
                for item in data.get("data", []):
                    record = {
                        "country_code": country,
                        "year": item.get("year"),
                        "coverage": item.get("value"),
                        "target_population": item.get("target", None),
                        "vaccinated": item.get("vaccinated", None),
                    }

                    # Filter by years if specified
                    if years is None or record["year"] in years:
                        records.append(record)

                return pd.DataFrame(records)
            else:
                logger.warning(f"WHO API returned status {response.status_code}")
                return None

        except Exception as e:
            logger.warning(f"Error fetching WHO immunization data: {e}")
            return None

    def get_malaria_incidence(
        self,
        countries: Optional[List[str]] = None,
        years: Optional[List[int]] = None,
        subregion: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Get malaria incidence data for PAHO countries.

        Args:
            countries: List of ISO3 country codes
            years: List of years
            subregion: PAHO subregion name

        Returns
        -------
            DataFrame with malaria incidence data
        """
        if subregion and not countries:
            countries = self.get_countries_by_subregion(subregion)

        if not countries:
            # Malaria-endemic countries in PAHO
            countries = [
                "BRA",
                "COL",
                "ECU",
                "VEN",
                "GUY",
                "SUR",
                "PER",
                "BOL",
                "HND",
                "NIC",
                "GTM",
                "SLV",
                "CRI",
                "PAN",
                "DOM",
                "HTI",
            ]

        logger.info(f"Fetching malaria data for {len(countries)} countries")

        # Use WHO GHO API for malaria data
        all_data = []

        for country in countries:
            df = self._fetch_who_malaria_data(country, years)
            if df is not None and not df.empty:
                df["country_name"] = self.COUNTRIES.get(country, country)
                all_data.append(df)

        if not all_data:
            return pd.DataFrame()

        result = pd.concat(all_data, ignore_index=True)
        logger.info(f"Retrieved {len(result)} malaria records")
        return result

    def _fetch_who_malaria_data(
        self, country: str, years: Optional[List[int]] = None
    ) -> Optional[pd.DataFrame]:
        """Fetch malaria data from WHO GHO API."""
        try:
            # WHO GHO API for malaria
            url = "https://ghoapi.azureedge.net/api/MALARIA_EST_INCIDENCE"

            filter_parts = [f"SpatialDim eq '{country}'"]
            if years:
                years_filter = " or ".join([f"TimeDim eq {y}" for y in years])
                filter_parts.append(f"({years_filter})")

            params = {"$filter": " and ".join(filter_parts)}

            response = self._session.get(url, params=params, timeout=30)

            if response.status_code == 200:
                data = response.json()
                records = []

                for item in data.get("value", []):
                    records.append(
                        {
                            "country_code": country,
                            "year": item.get("TimeDim"),
                            "incidence_rate": item.get("NumericValue"),
                            "incidence_low": item.get("Low"),
                            "incidence_high": item.get("High"),
                            "data_source": "WHO GHO",
                        }
                    )

                return pd.DataFrame(records)

            return None

        except Exception as e:
            logger.warning(f"Error fetching malaria data: {e}")
            return None

    def get_dengue_data(
        self,
        countries: Optional[List[str]] = None,
        years: Optional[List[int]] = None,
        subregion: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Get dengue surveillance data for PAHO countries.

        Args:
            countries: List of ISO3 country codes
            years: List of years
            subregion: PAHO subregion name

        Returns
        -------
            DataFrame with dengue case data
        """
        if subregion and not countries:
            countries = self.get_countries_by_subregion(subregion)

        if not countries:
            # Dengue-endemic countries
            countries = list(self.COUNTRIES.keys())

        logger.info(f"Fetching dengue data for {len(countries)} countries")

        # Note: Dengue data is often published in PAHO epidemiological bulletins
        # This method provides a structure for accessing such data

        # Placeholder for actual implementation
        # In practice, this would scrape PAHO bulletins or use country reports

        data = []
        for country in countries:
            # Simulated data structure
            record = {
                "country_code": country,
                "country_name": self.COUNTRIES.get(country, country),
                "year": years[0] if years else datetime.now().year,
                "cases_reported": None,  # Would be filled from actual data
                "deaths": None,
                "incidence_rate": None,
                "severe_cases": None,
                "data_source": "PAHO/WHO",
                "note": "Dengue data typically available from PAHO epidemiological bulletins",
            }
            data.append(record)

        logger.warning("Dengue data requires manual extraction from PAHO bulletins")
        return pd.DataFrame(data)

    def get_health_indicators(
        self,
        indicator: str,
        countries: Optional[List[str]] = None,
        years: Optional[List[int]] = None,
        subregion: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Get specific health indicators for PAHO countries.

        Args:
            indicator: Health indicator code (e.g., 'LIFE_EXPECTANCY', 'MORTALITY_INFANT')
            countries: List of ISO3 country codes
            years: List of years
            subregion: PAHO subregion name

        Returns
        -------
            DataFrame with indicator data
        """
        if subregion and not countries:
            countries = self.get_countries_by_subregion(subregion)

        if not countries:
            countries = list(self.COUNTRIES.keys())

        # Map common indicators to WHO GHO codes
        indicator_map = {
            "LIFE_EXPECTANCY": "WHOSIS_000001",
            "LIFE_EXPECTANCY_HEALTHY": "WHOSIS_000002",
            "MORTALITY_INFANT": "MDG_0000000001",
            "MORTALITY_UNDER5": "MDG_0000000007",
            "MORTALITY_MATERNAL": "MDG_0000000026",
        }

        who_indicator = indicator_map.get(indicator, indicator)

        logger.info(f"Fetching indicator '{indicator}' for {len(countries)} countries")

        all_data = []
        for country in countries:
            df = self._fetch_who_indicator(who_indicator, country, years)
            if df is not None and not df.empty:
                df["indicator"] = indicator
                df["country_name"] = self.COUNTRIES.get(country, country)
                all_data.append(df)

        if not all_data:
            return pd.DataFrame()

        result = pd.concat(all_data, ignore_index=True)
        return result

    def _fetch_who_indicator(
        self, indicator: str, country: str, years: Optional[List[int]] = None
    ) -> Optional[pd.DataFrame]:
        """Fetch indicator data from WHO GHO API."""
        try:
            url = f"https://ghoapi.azureedge.net/api/{indicator}"

            filter_parts = [f"SpatialDim eq '{country}'"]
            if years:
                years_filter = " or ".join([f"TimeDim eq {y}" for y in years])
                filter_parts.append(f"({years_filter})")

            params = {"$filter": " and ".join(filter_parts)}

            response = self._session.get(url, params=params, timeout=30)

            if response.status_code == 200:
                data = response.json()
                records = []

                for item in data.get("value", []):
                    records.append(
                        {
                            "country_code": country,
                            "year": item.get("TimeDim"),
                            "value": item.get("NumericValue"),
                            "value_low": item.get("Low"),
                            "value_high": item.get("High"),
                            "data_source": "WHO GHO",
                        }
                    )

                return pd.DataFrame(records)

            return None

        except Exception as e:
            logger.warning(f"Error fetching indicator data: {e}")
            return None

    def compare_countries(
        self, indicator: str, countries: List[str], years: List[int]
    ) -> pd.DataFrame:
        """
        Compare a health indicator across multiple countries.

        Args:
            indicator: Health indicator code
            countries: List of ISO3 country codes
            years: List of years

        Returns
        -------
            DataFrame pivoted for easy comparison
        """
        data = self.get_health_indicators(indicator, countries, years)

        if data.empty or "value" not in data.columns:
            return data

        # Pivot for comparison
        comparison = data.pivot_table(
            index="year", columns="country_code", values="value", aggfunc="first"
        )

        return comparison

    def get_regional_summary(self, indicator: str, year: int) -> pd.DataFrame:
        """
        Get summary statistics for an indicator by PAHO subregion.

        Args:
            indicator: Health indicator code
            year: Year to analyze

        Returns
        -------
            DataFrame with subregion summaries
        """
        summaries = []

        for subregion, countries in self.SUBREGIONS.items():
            data = self.get_health_indicators(indicator, countries, [year])

            if not data.empty and "value" in data.columns:
                valid_data = data[data["value"].notna()]

                if not valid_data.empty:
                    summaries.append(
                        {
                            "subregion": subregion,
                            "year": year,
                            "indicator": indicator,
                            "mean_value": valid_data["value"].mean(),
                            "median_value": valid_data["value"].median(),
                            "min_value": valid_data["value"].min(),
                            "max_value": valid_data["value"].max(),
                            "n_countries": len(valid_data),
                            "countries": ", ".join(valid_data["country_code"].tolist()),
                        }
                    )

        return pd.DataFrame(summaries)

