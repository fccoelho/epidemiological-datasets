"""
Our World in Data (OWID) Health Data Accessor

This module provides access to comprehensive health datasets from Our World in Data,
including:
- COVID-19 data (cases, deaths, testing, hospitalizations)
- Vaccination data (global vaccination progress)
- Excess mortality data
- Health inequality metrics
- Disease burden data

Data Sources:
- OWID Website: https://ourworldindata.org/health
- COVID-19 Data: https://github.com/owid/covid-19-data
- General Datasets: https://github.com/owid/owid-datasets

Update Frequency:
- COVID-19 data: Daily
- Other health data: Weekly

License: CC BY (Creative Commons Attribution)

Author: Flávio Codeço Coelho
License: MIT
"""

import logging
import time
from io import StringIO
from typing import List, Optional

import pandas as pd
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OWIDAccessor:
    """
    Accessor for Our World in Data (OWID) health statistics.

    Provides access to global health data covering all countries worldwide,
    including:
    - COVID-19 cases, deaths, testing, and hospitalizations
    - Vaccination data and progress
    - Excess mortality estimates
    - Health inequality metrics
    - Disease burden statistics

    Example:
        >>> owid = OWIDAccessor()
        >>>
        >>> # Get COVID-19 data for specific countries
        >>> covid = owid.get_covid_data(
        ...     countries=['BRA', 'USA', 'IND'],
        ...     metrics=['cases', 'deaths', 'hospitalizations']
        ... )
        >>>
        >>> # Get vaccination data
        >>> vax = owid.get_vaccination_data(countries=['BRA', 'USA'])
        >>>
        >>> # Get excess mortality
        >>> excess = owid.get_excess_mortality(countries=['GBR', 'ITA'])

    Data Sources:
        - OWID Health: https://ourworldindata.org/health
        - COVID-19 Data: https://github.com/owid/covid-19-data
        - Catalog: https://github.com/owid/owid-datasets
    """

    # GitHub raw content base URLs
    GITHUB_BASE_URL = "https://raw.githubusercontent.com/owid"
    COVID_REPO = "covid-19-data"
    DATASETS_REPO = "owid-datasets"

    # API endpoints
    COVID_API_URL = "https://covid.ourworldindata.org/data"

    # Standard country list (ISO3 codes)
    COUNTRIES = {
        "AFG": "Afghanistan",
        "ALB": "Albania",
        "DZA": "Algeria",
        "AND": "Andorra",
        "AGO": "Angola",
        "ATG": "Antigua and Barbuda",
        "ARG": "Argentina",
        "ARM": "Armenia",
        "AUS": "Australia",
        "AUT": "Austria",
        "AZE": "Azerbaijan",
        "BHS": "Bahamas",
        "BHR": "Bahrain",
        "BGD": "Bangladesh",
        "BRB": "Barbados",
        "BLR": "Belarus",
        "BEL": "Belgium",
        "BLZ": "Belize",
        "BEN": "Benin",
        "BTN": "Bhutan",
        "BOL": "Bolivia",
        "BIH": "Bosnia and Herzegovina",
        "BWA": "Botswana",
        "BRA": "Brazil",
        "BRN": "Brunei",
        "BGR": "Bulgaria",
        "BFA": "Burkina Faso",
        "BDI": "Burundi",
        "KHM": "Cambodia",
        "CMR": "Cameroon",
        "CAN": "Canada",
        "CPV": "Cape Verde",
        "CAF": "Central African Republic",
        "TCD": "Chad",
        "CHL": "Chile",
        "CHN": "China",
        "COL": "Colombia",
        "COM": "Comoros",
        "COG": "Congo",
        "CRI": "Costa Rica",
        "HRV": "Croatia",
        "CUB": "Cuba",
        "CYP": "Cyprus",
        "CZE": "Czech Republic",
        "COD": "Democratic Republic of Congo",
        "DNK": "Denmark",
        "DJI": "Djibouti",
        "DMA": "Dominica",
        "DOM": "Dominican Republic",
        "ECU": "Ecuador",
        "EGY": "Egypt",
        "SLV": "El Salvador",
        "GNQ": "Equatorial Guinea",
        "ERI": "Eritrea",
        "EST": "Estonia",
        "SWZ": "Eswatini",
        "ETH": "Ethiopia",
        "FJI": "Fiji",
        "FIN": "Finland",
        "FRA": "France",
        "GAB": "Gabon",
        "GMB": "Gambia",
        "GEO": "Georgia",
        "DEU": "Germany",
        "GHA": "Ghana",
        "GRC": "Greece",
        "GRD": "Grenada",
        "GTM": "Guatemala",
        "GIN": "Guinea",
        "GNB": "Guinea-Bissau",
        "GUY": "Guyana",
        "HTI": "Haiti",
        "HND": "Honduras",
        "HUN": "Hungary",
        "ISL": "Iceland",
        "IND": "India",
        "IDN": "Indonesia",
        "IRN": "Iran",
        "IRQ": "Iraq",
        "IRL": "Ireland",
        "ISR": "Israel",
        "ITA": "Italy",
        "JAM": "Jamaica",
        "JPN": "Japan",
        "JOR": "Jordan",
        "KAZ": "Kazakhstan",
        "KEN": "Kenya",
        "KIR": "Kiribati",
        "KWT": "Kuwait",
        "KGZ": "Kyrgyzstan",
        "LAO": "Laos",
        "LVA": "Latvia",
        "LBN": "Lebanon",
        "LSO": "Lesotho",
        "LBR": "Liberia",
        "LBY": "Libya",
        "LIE": "Liechtenstein",
        "LTU": "Lithuania",
        "LUX": "Luxembourg",
        "MDG": "Madagascar",
        "MWI": "Malawi",
        "MYS": "Malaysia",
        "MDV": "Maldives",
        "MLI": "Mali",
        "MLT": "Malta",
        "MRT": "Mauritania",
        "MUS": "Mauritius",
        "MEX": "Mexico",
        "MDA": "Moldova",
        "MCO": "Monaco",
        "MNG": "Mongolia",
        "MNE": "Montenegro",
        "MAR": "Morocco",
        "MOZ": "Mozambique",
        "MMR": "Myanmar",
        "NAM": "Namibia",
        "NRU": "Nauru",
        "NPL": "Nepal",
        "NLD": "Netherlands",
        "NZL": "New Zealand",
        "NIC": "Nicaragua",
        "NER": "Niger",
        "NGA": "Nigeria",
        "MKD": "North Macedonia",
        "NOR": "Norway",
        "OMN": "Oman",
        "PAK": "Pakistan",
        "PLW": "Palau",
        "PSE": "Palestine",
        "PAN": "Panama",
        "PNG": "Papua New Guinea",
        "PRY": "Paraguay",
        "PER": "Peru",
        "PHL": "Philippines",
        "POL": "Poland",
        "PRT": "Portugal",
        "QAT": "Qatar",
        "ROU": "Romania",
        "RUS": "Russia",
        "RWA": "Rwanda",
        "KNA": "Saint Kitts and Nevis",
        "LCA": "Saint Lucia",
        "VCT": "Saint Vincent and the Grenadines",
        "WSM": "Samoa",
        "SMR": "San Marino",
        "STP": "Sao Tome and Principe",
        "SAU": "Saudi Arabia",
        "SEN": "Senegal",
        "SRB": "Serbia",
        "SYC": "Seychelles",
        "SLE": "Sierra Leone",
        "SGP": "Singapore",
        "SVK": "Slovakia",
        "SVN": "Slovenia",
        "SLB": "Solomon Islands",
        "SOM": "Somalia",
        "ZAF": "South Africa",
        "KOR": "South Korea",
        "SSD": "South Sudan",
        "ESP": "Spain",
        "LKA": "Sri Lanka",
        "SDN": "Sudan",
        "SUR": "Suriname",
        "SWE": "Sweden",
        "CHE": "Switzerland",
        "SYR": "Syria",
        "TWN": "Taiwan",
        "TJK": "Tajikistan",
        "TZA": "Tanzania",
        "THA": "Thailand",
        "TLS": "Timor-Leste",
        "TGO": "Togo",
        "TON": "Tonga",
        "TTO": "Trinidad and Tobago",
        "TUN": "Tunisia",
        "TUR": "Turkey",
        "TKM": "Turkmenistan",
        "TUV": "Tuvalu",
        "UGA": "Uganda",
        "UKR": "Ukraine",
        "ARE": "United Arab Emirates",
        "GBR": "United Kingdom",
        "USA": "United States",
        "URY": "Uruguay",
        "UZB": "Uzbekistan",
        "VUT": "Vanuatu",
        "VAT": "Vatican",
        "VEN": "Venezuela",
        "VNM": "Vietnam",
        "YEM": "Yemen",
        "ZMB": "Zambia",
        "ZWE": "Zimbabwe",
    }

    # Continent/region mapping
    REGIONS = {
        "Africa": [
            "DZA",
            "AGO",
            "BEN",
            "BWA",
            "BFA",
            "BDI",
            "CMR",
            "CPV",
            "CAF",
            "TCD",
            "COM",
            "COG",
            "COD",
            "CIV",
            "DJI",
            "EGY",
            "GNQ",
            "ERI",
            "SWZ",
            "ETH",
            "GAB",
            "GMB",
            "GHA",
            "GIN",
            "GNB",
            "KEN",
            "LSO",
            "LBR",
            "LBY",
            "MDG",
            "MWI",
            "MLI",
            "MRT",
            "MUS",
            "MAR",
            "MOZ",
            "NAM",
            "NER",
            "NGA",
            "RWA",
            "STP",
            "SEN",
            "SYC",
            "SLE",
            "SOM",
            "ZAF",
            "SSD",
            "SDN",
            "TZA",
            "TGO",
            "TUN",
            "UGA",
            "ZMB",
            "ZWE",
        ],
        "Asia": [
            "AFG",
            "ARM",
            "AZE",
            "BHR",
            "BGD",
            "BTN",
            "BRN",
            "KHM",
            "CHN",
            "CYP",
            "GEO",
            "IND",
            "IDN",
            "IRN",
            "IRQ",
            "ISR",
            "JPN",
            "JOR",
            "KAZ",
            "KWT",
            "KGZ",
            "LAO",
            "LBN",
            "MYS",
            "MDV",
            "MNG",
            "MMR",
            "NPL",
            "PRK",
            "OMN",
            "PAK",
            "PSE",
            "PHL",
            "QAT",
            "SAU",
            "SGP",
            "KOR",
            "LKA",
            "SYR",
            "TWN",
            "TJK",
            "THA",
            "TLS",
            "TUR",
            "TKM",
            "ARE",
            "UZB",
            "VNM",
            "YEM",
        ],
        "Europe": [
            "ALB",
            "AND",
            "AUT",
            "BLR",
            "BEL",
            "BIH",
            "BGR",
            "HRV",
            "CYP",
            "CZE",
            "DNK",
            "EST",
            "FIN",
            "FRA",
            "DEU",
            "GRC",
            "HUN",
            "ISL",
            "IRL",
            "ITA",
            "LVA",
            "LIE",
            "LTU",
            "LUX",
            "MLT",
            "MDA",
            "MCO",
            "MNE",
            "NLD",
            "MKD",
            "NOR",
            "POL",
            "PRT",
            "ROU",
            "RUS",
            "SMR",
            "SRB",
            "SVK",
            "SVN",
            "ESP",
            "SWE",
            "CHE",
            "UKR",
            "GBR",
            "VAT",
        ],
        "North America": ["CAN", "USA", "MEX"],
        "South America": [
            "ARG",
            "BOL",
            "BRA",
            "CHL",
            "COL",
            "ECU",
            "GUY",
            "PRY",
            "PER",
            "SUR",
            "URY",
            "VEN",
        ],
        "Oceania": [
            "AUS",
            "FJI",
            "KIR",
            "MHL",
            "FSM",
            "NRU",
            "NZL",
            "PLW",
            "PNG",
            "WSM",
            "SLB",
            "TON",
            "TUV",
            "VUT",
        ],
    }

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize OWID accessor.

        Args:
            cache_dir: Directory to cache downloaded data (optional)
        """
        self.cache_dir = cache_dir
        self._session = requests.Session()
        self._session.headers.update(
            {"User-Agent": "OWID-Data-Accessor/1.0 (Research Purpose)"}
        )
        self._cache = {}

    def list_countries(self) -> pd.DataFrame:
        """
        List all countries available in OWID datasets.

        Returns
        -------
            DataFrame with country codes and names
        """
        return pd.DataFrame(
            [(code, name) for code, name in self.COUNTRIES.items()],
            columns=["country_code", "country_name"],
        )

    def list_regions(self) -> pd.DataFrame:
        """
        List regions with their countries.

        Returns
        -------
            DataFrame with region information
        """
        data = []
        for region, countries in self.REGIONS.items():
            for country in countries:
                data.append(
                    {
                        "region": region,
                        "country_code": country,
                        "country_name": self.COUNTRIES.get(country, country),
                    }
                )
        return pd.DataFrame(data)

    def list_available_datasets(self) -> pd.DataFrame:
        """
        List available datasets from OWID.

        Returns
        -------
            DataFrame with available datasets and their descriptions
        """
        datasets = [
            {
                "dataset": "covid_data",
                "description": "COVID-19 cases, deaths, testing, and hospitalizations",
                "update_frequency": "Daily",
                "url": f"{self.COVID_API_URL}/owid-covid-data.csv",
                "method": "get_covid_data",
            },
            {
                "dataset": "vaccination_data",
                "description": "COVID-19 vaccination data by country",
                "update_frequency": "Daily",
                "url": f"{self.COVID_API_URL}/owid-covid-data.csv",
                "method": "get_vaccination_data",
            },
            {
                "dataset": "excess_mortality",
                "description": "Excess mortality estimates during COVID-19",
                "update_frequency": "Weekly",
                "url": f"{self.COVID_API_URL}/excess_mortality/excess_mortality.csv",
                "method": "get_excess_mortality",
            },
            {
                "dataset": "hospitalizations",
                "description": "COVID-19 hospitalization and ICU data",
                "update_frequency": "Weekly",
                "url": f"{self.COVID_API_URL}/hospitalizations/covid-hospitalizations.csv",
                "method": 'get_covid_data(metrics=["hospitalizations"])',
            },
            {
                "dataset": "covid_testing",
                "description": "COVID-19 testing data by country",
                "update_frequency": "Weekly",
                "url": f"{self.COVID_API_URL}/testing/covid-testing-all-observations.csv",
                "method": 'get_covid_data(metrics=["tests"])',
            },
        ]
        return pd.DataFrame(datasets)

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
                response = self._session.get(url, timeout=60)
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

    def get_covid_data(
        self,
        countries: Optional[List[str]] = None,
        metrics: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Get COVID-19 data for specified countries and metrics.

        Args:
            countries: List of ISO3 country codes (e.g., ['BRA', 'USA'])
                      If None, returns all countries
            metrics: List of metrics to include. Options:
                    - 'cases': Total and new cases
                    - 'deaths': Total and new deaths
                    - 'tests': Testing data
                    - 'hospitalizations': Hospital and ICU patients
                    - 'reproduction_rate': R value
                    - 'policy': Government response indices
                    If None, returns all metrics
            start_date: Start date in 'YYYY-MM-DD' format
            end_date: End date in 'YYYY-MM-DD' format

        Returns
        -------
            DataFrame with COVID-19 data

        Example:
            >>> owid = OWIDAccessor()
            >>>
            >>> # Get all metrics for Brazil
            >>> df = owid.get_covid_data(countries=['BRA'])
            >>>
            >>> # Get specific metrics for multiple countries
            >>> df = owid.get_covid_data(
            ...     countries=['BRA', 'USA', 'IND'],
            ...     metrics=['cases', 'deaths', 'hospitalizations'],
            ...     start_date='2021-01-01',
            ...     end_date='2021-12-31'
            ... )
        """
        # Fetch the main COVID dataset
        url = f"{self.COVID_API_URL}/owid-covid-data.csv"
        df = self._fetch_csv_data(url)

        if df is None or df.empty:
            logger.error("Failed to fetch COVID-19 data")
            return pd.DataFrame()

        # Filter by countries if specified
        if countries:
            valid_countries = [c for c in countries if c in self.COUNTRIES]
            if not valid_countries:
                logger.warning("No valid country codes provided")
                return pd.DataFrame()
            df = df[df["iso_code"].isin(valid_countries)]

        # Parse date column
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])

            # Filter by date range
            if start_date:
                df = df[df["date"] >= start_date]
            if end_date:
                df = df[df["date"] <= end_date]

        # Select columns based on metrics
        if metrics:
            base_cols = ["iso_code", "continent", "location", "date"]
            metric_cols = []

            metric_mapping = {
                "cases": [
                    "total_cases",
                    "new_cases",
                    "total_cases_per_million",
                    "new_cases_per_million",
                ],
                "deaths": [
                    "total_deaths",
                    "new_deaths",
                    "total_deaths_per_million",
                    "new_deaths_per_million",
                ],
                "tests": [
                    "total_tests",
                    "new_tests",
                    "total_tests_per_thousand",
                    "new_tests_per_thousand",
                    "positive_rate",
                ],
                "hospitalizations": [
                    "hosp_patients",
                    "hosp_patients_per_million",
                    "icu_patients",
                    "icu_patients_per_million",
                ],
                "reproduction_rate": ["reproduction_rate"],
                "policy": [
                    "stringency_index",
                    "containment_health_index",
                    "economic_support_index",
                ],
            }

            for metric in metrics:
                if metric in metric_mapping:
                    metric_cols.extend(metric_mapping[metric])

            available_cols = [c for c in base_cols + metric_cols if c in df.columns]
            df = df[available_cols]

        # Rename iso_code to country_code for consistency
        if "iso_code" in df.columns:
            df = df.rename(columns={"iso_code": "country_code"})

        logger.info(
            f"Retrieved {len(df)} COVID-19 records for {df['country_code'].nunique()} countries"
        )
        return df

    def get_vaccination_data(
        self,
        countries: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Get COVID-19 vaccination data for specified countries.

        Args:
            countries: List of ISO3 country codes
            start_date: Start date in 'YYYY-MM-DD' format
            end_date: End date in 'YYYY-MM-DD' format

        Returns
        -------
            DataFrame with vaccination data including:
            - total_vaccinations
            - people_vaccinated
            - people_fully_vaccinated
            - total_boosters
            - Daily and per capita metrics

        Example:
            >>> owid = OWIDAccessor()
            >>> vax = owid.get_vaccination_data(countries=['BRA', 'USA', 'GBR'])
            >>> print(vax[['country_code', 'date', 'people_fully_vaccinated_per_hundred']].tail())
        """
        # Use the main COVID dataset which includes vaccination data
        url = f"{self.COVID_API_URL}/owid-covid-data.csv"
        df = self._fetch_csv_data(url)

        if df is None or df.empty:
            logger.error("Failed to fetch vaccination data")
            return pd.DataFrame()

        # Filter by countries
        if countries:
            valid_countries = [c for c in countries if c in self.COUNTRIES]
            df = df[df["iso_code"].isin(valid_countries)]

        # Parse date
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])

            if start_date:
                df = df[df["date"] >= start_date]
            if end_date:
                df = df[df["date"] <= end_date]

        # Select vaccination columns
        vax_cols = [
            "iso_code",
            "continent",
            "location",
            "date",
            "total_vaccinations",
            "people_vaccinated",
            "people_fully_vaccinated",
            "total_boosters",
            "new_vaccinations",
            "new_vaccinations_smoothed",
            "total_vaccinations_per_hundred",
            "people_vaccinated_per_hundred",
            "people_fully_vaccinated_per_hundred",
            "total_boosters_per_hundred",
            "new_vaccinations_smoothed_per_million",
            "population",
        ]

        available_cols = [c for c in vax_cols if c in df.columns]
        df = df[available_cols]

        # Rename for consistency
        if "iso_code" in df.columns:
            df = df.rename(columns={"iso_code": "country_code"})

        logger.info(
            f"Retrieved {len(df)} vaccination records for {df['country_code'].nunique()} countries"
        )
        return df

    def get_excess_mortality(
        self,
        countries: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Get excess mortality data for specified countries.

        Excess mortality measures the difference between observed deaths
        and expected deaths based on historical trends, providing a more
        comprehensive picture of COVID-19's impact.

        Args:
            countries: List of ISO3 country codes
            start_date: Start date in 'YYYY-MM-DD' format
            end_date: End date in 'YYYY-MM-DD' format

        Returns
        -------
            DataFrame with excess mortality data including:
            - deaths: Observed deaths
            - expected_deaths: Expected deaths based on historical trends
            - excess_deaths: Difference (observed - expected)
            - excess_deaths_per_100k: Per capita metric

        Example:
            >>> owid = OWIDAccessor()
            >>> excess = owid.get_excess_mortality(countries=['USA', 'GBR', 'ITA'])
            >>> # Calculate total excess deaths
            >>> total_excess = excess.groupby('country_code')['excess_deaths'].sum()
        """
        url = f"{self.COVID_API_URL}/excess_mortality/excess_mortality.csv"
        df = self._fetch_csv_data(url)

        if df is None or df.empty:
            logger.error("Failed to fetch excess mortality data")
            return pd.DataFrame()

        # Filter by countries
        if countries:
            valid_countries = [c for c in countries if c in self.COUNTRIES]
            df = df[df["iso3c"].isin(valid_countries)]

        # Parse date
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])

            if start_date:
                df = df[df["date"] >= start_date]
            if end_date:
                df = df[df["date"] <= end_date]

        # Rename columns for consistency
        col_mapping = {
            "iso3c": "country_code",
            "location_name": "country_name",
        }
        df = df.rename(
            columns={k: v for k, v in col_mapping.items() if k in df.columns}
        )

        logger.info(
            f"Retrieved {len(df)} excess mortality records for {df['country_code'].nunique()} countries"
        )
        return df

    def get_testing_data(
        self,
        countries: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Get COVID-19 testing data for specified countries.

        Args:
            countries: List of ISO3 country codes
            start_date: Start date in 'YYYY-MM-DD' format
            end_date: End date in 'YYYY-MM-DD' format

        Returns
        -------
            DataFrame with testing data including:
            - total_tests
            - new_tests
            - tests_per_case
            - positive_rate

        Example:
            >>> owid = OWIDAccessor()
            >>> tests = owid.get_testing_data(countries=['BRA', 'USA'])
            >>> print(tests[['country_code', 'date', 'positive_rate']].head(10))
        """
        url = f"{self.COVID_API_URL}/testing/covid-testing-all-observations.csv"
        df = self._fetch_csv_data(url)

        if df is None or df.empty:
            logger.error("Failed to fetch testing data")
            return pd.DataFrame()

        # Filter by countries
        if countries:
            valid_countries = [c for c in countries if c in self.COUNTRIES]
            df = df[df["ISO code"].isin(valid_countries)]

        # Parse date
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"])

            if start_date:
                df = df[df["Date"] >= start_date]
            if end_date:
                df = df[df["Date"] <= end_date]

        # Rename columns for consistency
        col_mapping = {
            "ISO code": "country_code",
            "Entity": "country_name",
            "Date": "date",
        }
        df = df.rename(
            columns={k: v for k, v in col_mapping.items() if k in df.columns}
        )

        logger.info(
            f"Retrieved {len(df)} testing records for {df['country_code'].nunique()} countries"
        )
        return df

    def get_hospitalizations_data(
        self,
        countries: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Get COVID-19 hospitalization data for specified countries.

        Args:
            countries: List of ISO3 country codes
            start_date: Start date in 'YYYY-MM-DD' format
            end_date: End date in 'YYYY-MM-DD' format

        Returns
        -------
            DataFrame with hospitalization data including:
            - hosp_patients: Current hospital patients
            - icu_patients: Current ICU patients
            - Weekly admissions data

        Example:
            >>> owid = OWIDAccessor()
            >>> hosp = owid.get_hospitalizations_data(countries=['USA', 'ITA'])
        """
        url = f"{self.COVID_API_URL}/hospitalizations/covid-hospitalizations.csv"
        df = self._fetch_csv_data(url)

        if df is None or df.empty:
            logger.error("Failed to fetch hospitalizations data")
            return pd.DataFrame()

        # Filter by countries
        if countries:
            valid_countries = [c for c in countries if c in self.COUNTRIES]
            df = df[df["iso_code"].isin(valid_countries)]

        # Parse date
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])

            if start_date:
                df = df[df["date"] >= start_date]
            if end_date:
                df = df[df["date"] <= end_date]

        # Rename columns for consistency
        col_mapping = {
            "iso_code": "country_code",
        }
        df = df.rename(
            columns={k: v for k, v in col_mapping.items() if k in df.columns}
        )

        logger.info(
            f"Retrieved {len(df)} hospitalization records for {df['country_code'].nunique()} countries"
        )
        return df

    def get_latest_data(
        self, countries: Optional[List[str]] = None, metrics: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Get the latest available COVID-19 data for each country.

        Args:
            countries: List of ISO3 country codes
            metrics: List of metrics to include

        Returns
        -------
            DataFrame with the most recent data point for each country

        Example:
            >>> owid = OWIDAccessor()
            >>> latest = owid.get_latest_data(countries=['BRA', 'USA', 'IND'])
            >>> print(latest[['country_code', 'date', 'total_cases', 'total_deaths']])
        """
        df = self.get_covid_data(countries=countries, metrics=metrics)

        if df.empty:
            return df

        # Get latest date for each country
        latest_idx = df.groupby("country_code")["date"].idxmax()
        latest_df = df.loc[latest_idx].reset_index(drop=True)

        logger.info(f"Retrieved latest data for {len(latest_df)} countries")
        return latest_df

    def get_global_summary(self) -> pd.DataFrame:
        """
        Get global summary statistics from the latest data.

        Returns
        -------
            DataFrame with summary statistics

        Example:
            >>> owid = OWIDAccessor()
            >>> summary = owid.get_global_summary()
            >>> print(summary)
        """
        latest = self.get_latest_data()

        if latest.empty:
            return pd.DataFrame()

        summary = {"metric": [], "value": [], "unit": []}

        # Calculate global totals
        if "total_cases" in latest.columns:
            summary["metric"].append("Total Cases")
            summary["value"].append(latest["total_cases"].sum())
            summary["unit"].append("cases")

        if "total_deaths" in latest.columns:
            summary["metric"].append("Total Deaths")
            summary["value"].append(latest["total_deaths"].sum())
            summary["unit"].append("deaths")

        if "total_vaccinations" in latest.columns:
            summary["metric"].append("Total Vaccinations")
            summary["value"].append(latest["total_vaccinations"].sum())
            summary["unit"].append("doses")

        if "people_fully_vaccinated" in latest.columns:
            summary["metric"].append("People Fully Vaccinated")
            summary["value"].append(latest["people_fully_vaccinated"].sum())
            summary["unit"].append("people")

        return pd.DataFrame(summary)

    def compare_countries(
        self,
        countries: List[str],
        metric: str = "total_cases_per_million",
        normalize_by_population: bool = True,
    ) -> pd.DataFrame:
        """
        Compare a specific metric across multiple countries.

        Args:
            countries: List of ISO3 country codes
            metric: Metric to compare (e.g., 'total_cases', 'total_deaths_per_million')
            normalize_by_population: Whether to use per capita metrics

        Returns
        -------
            DataFrame pivoted for easy comparison

        Example:
            >>> owid = OWIDAccessor()
            >>> comparison = owid.compare_countries(
            ...     countries=['BRA', 'USA', 'IND', 'GBR'],
            ...     metric='total_deaths_per_million'
            ... )
            >>> comparison.plot(figsize=(12, 6))
        """
        df = self.get_covid_data(countries=countries)

        if df.empty or metric not in df.columns:
            logger.warning(f"Metric '{metric}' not found in data")
            return df

        # Pivot for comparison
        comparison = df.pivot_table(
            index="date", columns="country_code", values=metric, aggfunc="first"
        )

        return comparison

    def get_region_aggregates(
        self, region: str, metric: str = "new_cases", aggregation: str = "sum"
    ) -> pd.DataFrame:
        """
        Get aggregated data for a specific region.

        Args:
            region: Region name (e.g., 'South America', 'Europe')
            metric: Metric to aggregate
            aggregation: Aggregation function ('sum', 'mean', 'median')

        Returns
        -------
            DataFrame with regional aggregates

        Example:
            >>> owid = OWIDAccessor()
            >>> sa_cases = owid.get_region_aggregates('South America', 'new_cases')
        """
        if region not in self.REGIONS:
            logger.warning(
                f"Region '{region}' not found. Available: {list(self.REGIONS.keys())}"
            )
            return pd.DataFrame()

        countries = self.REGIONS[region]
        df = self.get_covid_data(countries=countries)

        if df.empty or metric not in df.columns:
            return df

        # Aggregate by date
        if aggregation == "sum":
            agg_df = df.groupby("date")[metric].sum().reset_index()
        elif aggregation == "mean":
            agg_df = df.groupby("date")[metric].mean().reset_index()
        elif aggregation == "median":
            agg_df = df.groupby("date")[metric].median().reset_index()
        else:
            agg_df = df.groupby("date")[metric].sum().reset_index()

        agg_df["region"] = region
        agg_df["aggregation"] = aggregation

        return agg_df


def main():
    """
    Example usage of OWIDAccessor.
    """
    print("=" * 70)
    print("Our World in Data (OWID) Health Data Accessor")
    print("=" * 70)

    owid = OWIDAccessor()

    # List countries
    print("\n🌍 Available Countries:")
    countries = owid.list_countries()
    print(f"Total countries: {len(countries)}")
    print("\nFirst 10 countries:")
    print(countries.head(10).to_string(index=False))

    # List regions
    print("\n📍 Available Regions:")
    regions = owid.list_regions()
    for region in regions["region"].unique():
        n_countries = len(regions[regions["region"] == region])
        print(f"  - {region}: {n_countries} countries")

    # List available datasets
    print("\n📊 Available Datasets:")
    datasets = owid.list_available_datasets()
    for _, row in datasets.iterrows():
        print(f"  - {row['dataset']}: {row['description']}")
        print(f"    Update: {row['update_frequency']}")

    # Example: Get latest global summary (commented to avoid API calls)
    # print("\n🌐 Global Summary (Latest):")
    # summary = owid.get_global_summary()
    # print(summary.to_string(index=False))

    print("\n✅ OWID accessor ready to use!")
    print("\nExample usage:")
    print("  owid = OWIDAccessor()")
    print("  covid = owid.get_covid_data(")
    print("      countries=['BRA', 'USA', 'IND'],")
    print("      metrics=['cases', 'deaths', 'hospitalizations']")
    print("  )")
    print("\n  vax = owid.get_vaccination_data(countries=['BRA', 'USA'])")
    print("  excess = owid.get_excess_mortality(countries=['GBR', 'ITA'])")


if __name__ == "__main__":
    main()
