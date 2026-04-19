"""
Eurostat Health Data Accessor

This module provides access to European Union health statistics from Eurostat,
including:
- Health indicators and health status
- Healthcare expenditure and financing
- Health workforce and facilities
- Mortality and causes of death
- Health determinants (lifestyle, environment)

Data Source: https://ec.europa.eu/eurostat/web/health
API Documentation: https://ec.europa.eu/eurostat/web/sdmx-web-services/rest-sdmx-2.1

Author: Flávio Codeço Coelho
License: MIT
"""

import logging
from typing import Any, ClassVar, Dict, List, Optional

import pandas as pd
import requests

from epidatasets._base import BaseAccessor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import eurostat library
try:
    import eurostat

    EUROSTAT_LIB_AVAILABLE = True
except ImportError:
    EUROSTAT_LIB_AVAILABLE = False
    logger.info("eurostat library not installed. Using REST API fallback.")


class EurostatAccessor(BaseAccessor):
    """
    Accessor for Eurostat health statistics data.

    Provides access to EU health data covering all 27 member states
    (plus EFTA countries and candidate countries).

    The accessor can use either:
    1. The `eurostat` Python library (recommended): pip install eurostat
    2. Direct REST API calls (fallback if library not available)

    Example:
        >>> eurostat = EurostatAccessor()
        >>>
        >>> # Get healthcare expenditure for selected countries
        >>> exp = eurostat.get_healthcare_expenditure(
        ...     countries=['DEU', 'FRA', 'ITA'],
        ...     years=list(range(2015, 2024))
        ... )
        >>>
        >>> # Get mortality data by cause
        >>> mortality = eurostat.get_mortality_data(
        ...     cause_code='COVID-19',
        ...     countries=['DEU', 'FRA', 'ITA'],
        ...     years=[2020, 2021, 2022]
        ... )

    Data Sources:
        - Eurostat Health: https://ec.europa.eu/eurostat/web/health
        - Eurostat Data Browser: https://ec.europa.eu/eurostat/databrowser
        - API Docs: https://ec.europa.eu/eurostat/web/sdmx-web-services
    """

    source_name: ClassVar[str] = "eurostat"
    source_description: ClassVar[str] = "Eurostat health statistics - EU health indicators, mortality, expenditure, workforce"
    source_url: ClassVar[str] = "https://ec.europa.eu/eurostat/web/health"

    # Eurostat API base URLs
    BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
    REST_URL = "https://ec.europa.eu/eurostat/wdds/rest/data/v2.1/json/en"

    # EU Member States (27 countries post-Brexit)
    EU_MEMBER_STATES = {
        "AUT": "Austria",
        "BEL": "Belgium",
        "BGR": "Bulgaria",
        "HRV": "Croatia",
        "CYP": "Cyprus",
        "CZE": "Czech Republic",
        "DNK": "Denmark",
        "EST": "Estonia",
        "FIN": "Finland",
        "FRA": "France",
        "DEU": "Germany",
        "GRC": "Greece",
        "HUN": "Hungary",
        "IRL": "Ireland",
        "ITA": "Italy",
        "LVA": "Latvia",
        "LTU": "Lithuania",
        "LUX": "Luxembourg",
        "MLT": "Malta",
        "NLD": "Netherlands",
        "POL": "Poland",
        "PRT": "Portugal",
        "ROU": "Romania",
        "SVK": "Slovakia",
        "SVN": "Slovenia",
        "ESP": "Spain",
        "SWE": "Sweden",
    }

    # EFTA countries
    EFTA_COUNTRIES = {
        "ISL": "Iceland",
        "LIE": "Liechtenstein",
        "NOR": "Norway",
        "CHE": "Switzerland",
    }

    # EU Candidate countries
    CANDIDATE_COUNTRIES = {
        "ALB": "Albania",
        "MNE": "Montenegro",
        "MKD": "North Macedonia",
        "SRB": "Serbia",
        "TUR": "Turkey",
        "UKR": "Ukraine",
        "MDA": "Moldova",
        "BIH": "Bosnia and Herzegovina",
        "GEO": "Georgia",
    }

    # Former EU member (for historical data)
    FORMER_MEMBERS = {
        "GBR": "United Kingdom",  # Brexit 2020
    }

    # Common health indicator codes
    HEALTH_INDICATORS = {
        # Health status
        "hlth_silc_01": "Self-perceived health by sex, age and income",
        "hlth_silc_11": "Self-reported unmet needs for medical care",
        "hlth_silc_12": "Self-reported unmet needs for dental care",
        "hlth_silc_20": "Body mass index by sex, age and income",
        "hlth_ehis_de2": "Healthy life years by sex, age and NUTS",
        # Mortality
        "hlth_cd_aro": "Causes of death - absolute numbers",
        "hlth_cd_acdr2": "Avoidable and treatable mortality by NUTS 2",
        "demo_mlexpec": "Life expectancy by age and sex",
        "demo_pjanind__indic_de": "Infant mortality rate",
        # Healthcare expenditure
        "hlth_sha11_hf": "Health care expenditure by financing scheme",
        "hlth_sha11_hc": "Health care expenditure by function",
        "hlth_sha11_hp": "Health care expenditure by provider",
        "gov_10a_exp": "Government expenditure by function",
        # Health workforce
        "hlth_rs_prsrg": "Physicians by sex, age and NUTS 2",
        "hlth_rs_prspc": "Physicians by medical specialty",
        "hlth_rs_nursrg": "Nursing professionals by sex, age and NUTS 2",
        "hlth_rs_prac": "Health personnel by NUTS 2",
        # Health facilities
        "hlth_rs_bdsrg": "Hospital beds by type of care and NUTS 2",
        "hlth_rs_bdsnc": "Hospital beds by type of care and NACE",
        # Health determinants
        "hlth_ehis_al1b": "Alcohol consumption by sex, age and income",
        "hlth_ehis_fv1b": "Fruit and vegetable consumption",
        "hlth_ehis_pk1b": "Physical activity by sex, age and income",
        "hlth_ehis_sk1b": "Smoking habits by sex, age and income",
        # COVID-19 specific
        "demo_pjanind__covid": "Excess mortality during COVID-19",
        "hlth_ehis_ic1b": "Influenza vaccination by sex, age and risk group",
    }

    # Causes of death codes (ICD-10 chapters)
    CAUSES_OF_DEATH = {
        "TOTAL": "All causes of death",
        "A_R": "Infectious and parasitic diseases",
        "COVID-19": "COVID-19",
        "B20_B24": "HIV disease",
        "C": "Malignant neoplasms (cancer)",
        "E": "Endocrine, nutritional and metabolic diseases",
        "E10_E14": "Diabetes mellitus",
        "F": "Mental and behavioural disorders",
        "G_H": "Diseases of the nervous system and sense organs",
        "I": "Diseases of the circulatory system",
        "I20_I25": "Ischaemic heart diseases",
        "I60_I69": "Cerebrovascular diseases",
        "J": "Diseases of the respiratory system",
        "J09_J18": "Influenza and pneumonia",
        "K": "Diseases of the digestive system",
        "V_Y": "External causes of morbidity and mortality",
        "V01_X59": "Accidents",
        "X60_X84": "Intentional self-harm",
    }

    def list_countries(self) -> pd.DataFrame:
        return self.list_all_countries()

    def __init__(self, use_library: bool = True, cache_dir: Optional[str] = None):
        """
        Initialize Eurostat accessor.

        Args:
            use_library: Whether to use the eurostat Python library if available
            cache_dir: Directory to cache downloaded data (optional)
        """
        self.cache_dir = cache_dir
        self.use_library = use_library and EUROSTAT_LIB_AVAILABLE

        self._session = requests.Session()
        self._session.headers.update(
            {"User-Agent": "Eurostat-Data-Accessor/1.0 (Research Purpose)"}
        )

        if self.use_library:
            logger.info("Using eurostat Python library")
        else:
            logger.info("Using REST API fallback")

    def list_eu_countries(self) -> pd.DataFrame:
        """
        List all EU member states.

        Returns
        -------
            DataFrame with country codes and names
        """
        return pd.DataFrame(
            [(code, name) for code, name in self.EU_MEMBER_STATES.items()],
            columns=["country_code", "country_name"],
        )

    def list_all_countries(self) -> pd.DataFrame:
        """
        List all countries available in Eurostat data (EU, EFTA, candidates).

        Returns
        -------
            DataFrame with country codes, names, and membership type
        """
        data = []

        for code, name in self.EU_MEMBER_STATES.items():
            data.append(
                {"country_code": code, "country_name": name, "type": "EU Member"}
            )

        for code, name in self.EFTA_COUNTRIES.items():
            data.append({"country_code": code, "country_name": name, "type": "EFTA"})

        for code, name in self.CANDIDATE_COUNTRIES.items():
            data.append(
                {"country_code": code, "country_name": name, "type": "Candidate"}
            )

        for code, name in self.FORMER_MEMBERS.items():
            data.append(
                {"country_code": code, "country_name": name, "type": "Former EU"}
            )

        return pd.DataFrame(data)

    def list_indicators(self) -> pd.DataFrame:
        """
        List common health indicators available in Eurostat.

        Returns
        -------
            DataFrame with indicator codes and descriptions
        """
        return pd.DataFrame(
            [(code, desc) for code, desc in self.HEALTH_INDICATORS.items()],
            columns=["indicator_code", "description"],
        )

    def list_causes_of_death(self) -> pd.DataFrame:
        """
        List causes of death codes (ICD-10 based).

        Returns
        -------
            DataFrame with cause codes and descriptions
        """
        return pd.DataFrame(
            [(code, desc) for code, desc in self.CAUSES_OF_DEATH.items()],
            columns=["cause_code", "description"],
        )

    def search_indicators(self, keyword: str) -> pd.DataFrame:
        """
        Search for indicators by keyword.

        Args:
            keyword: Search term

        Returns
        -------
            DataFrame with matching indicators
        """
        indicators = self.list_indicators()
        mask = indicators["indicator_code"].str.contains(
            keyword, case=False, na=False
        ) | indicators["description"].str.contains(keyword, case=False, na=False)
        return indicators[mask]

    def get_health_indicator(
        self,
        indicator_code: str,
        countries: Optional[List[str]] = None,
        years: Optional[List[int]] = None,
        sex: Optional[str] = None,
        age_group: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Get a specific health indicator from Eurostat.

        Args:
            indicator_code: Eurostat dataset code (e.g., 'hlth_silc_01')
            countries: List of ISO2 country codes (e.g., ['DE', 'FR', 'IT'])
                      If None, returns all EU countries
            years: List of years (e.g., [2020, 2021, 2022])
                  If None, returns all available years
            sex: Filter by sex ('M', 'F', or None for both)
            age_group: Age group filter (dataset-specific)

        Returns
        -------
            DataFrame with indicator data
        """
        if countries is None:
            countries = list(self.EU_MEMBER_STATES.keys())

        # Convert ISO3 to ISO2 if needed
        countries_iso2 = [self._to_iso2(c) for c in countries]

        logger.info(
            f"Fetching indicator {indicator_code} for {len(countries)} countries"
        )

        if self.use_library:
            return self._get_with_library(
                indicator_code, countries_iso2, years, sex, age_group
            )
        else:
            return self._get_with_api(
                indicator_code, countries_iso2, years, sex, age_group
            )

    def _to_iso2(self, country_code: str) -> str:
        """Convert ISO3 to ISO2 country code."""
        mapping = {
            "AUT": "AT",
            "BEL": "BE",
            "BGR": "BG",
            "HRV": "HR",
            "CYP": "CY",
            "CZE": "CZ",
            "DNK": "DK",
            "EST": "EE",
            "FIN": "FI",
            "FRA": "FR",
            "DEU": "DE",
            "GRC": "EL",
            "HUN": "HU",
            "IRL": "IE",
            "ITA": "IT",
            "LVA": "LV",
            "LTU": "LT",
            "LUX": "LU",
            "MLT": "MT",
            "NLD": "NL",
            "POL": "PL",
            "PRT": "PT",
            "ROU": "RO",
            "SVK": "SK",
            "SVN": "SI",
            "ESP": "ES",
            "SWE": "SE",
            "ISL": "IS",
            "LIE": "LI",
            "NOR": "NO",
            "CHE": "CH",
            "GBR": "UK",
            "ALB": "AL",
            "MNE": "ME",
            "MKD": "MK",
            "SRB": "RS",
            "TUR": "TR",
            "UKR": "UA",
            "MDA": "MD",
            "BIH": "BA",
            "GEO": "GE",
        }
        return mapping.get(country_code, country_code)

    def _get_with_library(
        self,
        indicator_code: str,
        countries: List[str],
        years: Optional[List[int]],
        sex: Optional[str],
        age_group: Optional[str],
    ) -> pd.DataFrame:
        """Fetch data using eurostat library."""
        try:
            # Use eurostat library to get data
            df = eurostat.get_data_df(indicator_code)

            if df is None or df.empty:
                logger.warning(f"No data returned for {indicator_code}")
                return pd.DataFrame()

            # Filter by countries if specified
            if "geo" in df.columns and countries:
                df = df[df["geo"].isin(countries)]

            # Filter by years if specified
            if "time" in df.columns and years:
                df = df[df["time"].isin([str(y) for y in years])]

            # Filter by sex if specified
            if "sex" in df.columns and sex:
                df = df[df["sex"] == sex]

            return df

        except Exception as e:
            logger.error(f"Error using eurostat library: {e}")
            logger.info("Falling back to REST API")
            return self._get_with_api(indicator_code, countries, years, sex, age_group)

    def _get_with_api(
        self,
        indicator_code: str,
        countries: List[str],
        years: Optional[List[int]],
        sex: Optional[str],
        age_group: Optional[str],
    ) -> pd.DataFrame:
        """Fetch data using Eurostat REST API."""
        try:
            # Build API URL
            url = f"{self.REST_URL}/{indicator_code}"

            params = {
                "geo": ",".join(countries) if countries else "EU27_2020",
            }

            if years:
                params["time"] = ",".join([str(y) for y in years])

            if sex:
                params["sex"] = sex

            logger.info(f"Fetching from API: {url}")
            response = self._session.get(url, params=params, timeout=60)
            response.raise_for_status()

            data = response.json()

            # Parse Eurostat JSON format
            return self._parse_eurostat_json(data)

        except Exception as e:
            logger.error(f"Error fetching from API: {e}")
            return pd.DataFrame()

    def _parse_eurostat_json(self, data: dict) -> pd.DataFrame:
        """
        Parse Eurostat JSON response into DataFrame.

        Args:
            data: JSON data from Eurostat API

        Returns
        -------
            DataFrame with parsed data
        """
        try:
            # Extract dimension information
            dimension = data.get("dimension", {})
            value_data = data.get("value", {})

            # Get time periods
            time_dim = dimension.get("time", {}).get("category", {}).get("index", {})
            periods = list(time_dim.keys())

            # Get countries
            geo_dim = dimension.get("geo", {}).get("category", {}).get("index", {})
            countries = list(geo_dim.keys())

            # Build records
            records = []
            for i, period in enumerate(periods):
                for j, country in enumerate(countries):
                    # Calculate index for value lookup
                    idx = i * len(countries) + j
                    value = value_data.get(str(idx), {}).get("value")

                    records.append({"time": period, "geo": country, "value": value})

            df = pd.DataFrame(records)

            # Add metadata
            if "label" in data:
                df["indicator"] = data["label"]

            return df

        except Exception as e:
            logger.error(f"Error parsing Eurostat JSON: {e}")
            return pd.DataFrame()

    def get_healthcare_expenditure(
        self,
        countries: Optional[List[str]] = None,
        years: Optional[List[int]] = None,
        breakdown: str = "total",
    ) -> pd.DataFrame:
        """
        Get healthcare expenditure data.

        Args:
            countries: List of ISO3 country codes
            years: List of years
            breakdown: Level of detail ('total', 'by_scheme', 'by_function')

        Returns
        -------
            DataFrame with healthcare expenditure data
        """
        indicator_map = {
            "total": "hlth_sha11_hf",
            "by_scheme": "hlth_sha11_hf",
            "by_function": "hlth_sha11_hc",
            "by_provider": "hlth_sha11_hp",
        }

        indicator = indicator_map.get(breakdown, "hlth_sha11_hf")

        return self.get_health_indicator(indicator, countries, years)

    def get_mortality_data(
        self,
        cause_code: Optional[str] = None,
        countries: Optional[List[str]] = None,
        years: Optional[List[int]] = None,
        sex: Optional[str] = None,
        age_group: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Get mortality data by cause of death.

        Args:
            cause_code: Cause of death code (e.g., 'COVID-19', 'TOTAL')
            countries: List of ISO3 country codes
            years: List of years
            sex: Filter by sex ('M', 'F', or None for both)
            age_group: Age group filter

        Returns
        -------
            DataFrame with mortality data
        """
        indicator = "hlth_cd_aro"

        df = self.get_health_indicator(indicator, countries, years, sex, age_group)

        # Filter by cause if specified
        if cause_code and "cause" in df.columns:
            df = df[df["cause"] == cause_code]

        return df

    def get_life_expectancy(
        self,
        countries: Optional[List[str]] = None,
        years: Optional[List[int]] = None,
        sex: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Get life expectancy data.

        Args:
            countries: List of ISO3 country codes
            years: List of years
            sex: Filter by sex ('M', 'F', or None for both)

        Returns
        -------
            DataFrame with life expectancy at birth
        """
        return self.get_health_indicator("demo_mlexpec", countries, years, sex)

    def get_infant_mortality(
        self, countries: Optional[List[str]] = None, years: Optional[List[int]] = None
    ) -> pd.DataFrame:
        """
        Get infant mortality rate.

        Args:
            countries: List of ISO3 country codes
            years: List of years

        Returns
        -------
            DataFrame with infant mortality rates
        """
        return self.get_health_indicator("demo_pjanind__indic_de", countries, years)

    def get_physicians(
        self,
        countries: Optional[List[str]] = None,
        years: Optional[List[int]] = None,
        specialty: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Get physician data (counts or per capita).

        Args:
            countries: List of ISO3 country codes
            years: List of years
            specialty: Medical specialty filter

        Returns
        -------
            DataFrame with physician data
        """
        if specialty:
            indicator = "hlth_rs_prspc"
        else:
            indicator = "hlth_rs_prsrg"

        df = self.get_health_indicator(indicator, countries, years)

        if specialty and "medspec" in df.columns:
            df = df[df["medspec"] == specialty]

        return df

    def get_hospital_beds(
        self,
        countries: Optional[List[str]] = None,
        years: Optional[List[int]] = None,
        bed_type: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Get hospital bed data.

        Args:
            countries: List of ISO3 country codes
            years: List of years
            bed_type: Type of bed ('CUR_ACUTE', 'CUR_REHAB', 'LT', etc.)

        Returns
        -------
            DataFrame with hospital bed data
        """
        indicator = "hlth_rs_bdsrg"

        df = self.get_health_indicator(indicator, countries, years)

        if bed_type and "bedtype" in df.columns:
            df = df[df["bedtype"] == bed_type]

        return df

    def get_self_perceived_health(
        self,
        countries: Optional[List[str]] = None,
        years: Optional[List[int]] = None,
        sex: Optional[str] = None,
        age_group: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Get self-perceived health status data.

        Args:
            countries: List of ISO3 country codes
            years: List of years
            sex: Filter by sex ('M', 'F', or None for both)
            age_group: Age group filter

        Returns
        -------
            DataFrame with self-perceived health data
        """
        return self.get_health_indicator(
            "hlth_silc_01", countries, years, sex, age_group
        )

    def compare_countries(
        self, indicator_code: str, countries: List[str], years: List[int]
    ) -> pd.DataFrame:
        """
        Compare an indicator across multiple countries.

        Args:
            indicator_code: Eurostat indicator code
            countries: List of ISO3 country codes
            years: List of years

        Returns
        -------
            DataFrame pivoted for easy comparison
        """
        data = self.get_health_indicator(indicator_code, countries, years)

        if data.empty:
            return data

        # Try to pivot for comparison
        if "geo" in data.columns and "time" in data.columns:
            try:
                pivot = data.pivot_table(
                    index="time", columns="geo", values="value", aggfunc="first"
                )
                return pivot
            except:
                pass

        return data

    def get_data_dictionary(self, indicator_code: str) -> Dict[str, Any]:
        """
        Get data dictionary/metadata for an indicator.

        Args:
            indicator_code: Eurostat dataset code

        Returns
        -------
            Dictionary with metadata
        """
        try:
            url = f"{self.REST_URL}/{indicator_code}"
            response = self._session.get(url, timeout=30)
            response.raise_for_status()

            data = response.json()

            return {
                "indicator_code": indicator_code,
                "title": data.get("label", ""),
                "source": data.get("source", ""),
                "updated": data.get("updated", ""),
                "dimensions": list(data.get("dimension", {}).keys()),
            }

        except Exception as e:
            logger.error(f"Error fetching data dictionary: {e}")
            return {}
