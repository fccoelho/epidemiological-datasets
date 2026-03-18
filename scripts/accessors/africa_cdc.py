"""
Africa CDC (Centres for Disease Control and Prevention) Data Accessor

This module provides access to public health surveillance data from the African
Centres for Disease Control and Prevention (Africa CDC), including:
- Disease outbreak data and weekly outbreak briefs
- COVID-19 surveillance data for African countries
- Vaccination coverage data
- Event-based surveillance (EBS) data

Data Sources:
- Africa CDC: https://africacdc.org/
- Weekly Outbreak Briefs: Published on Africa CDC website
- COVID-19 Dashboard: Historical data available
- IDSR (Integrated Disease Surveillance and Response): National data

Update Frequency:
- Weekly outbreak briefs: Every week
- COVID-19 data: Daily (during pandemic)
- Event-based surveillance: Real-time alerts

License: Open Data (Africa CDC public health mission)

Author: Flávio Codeço Coelho
License: MIT
"""

import logging
from datetime import datetime
from typing import List, Optional, Tuple

import pandas as pd
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AfricaCDCAccessor:
    """
    Accessor for Africa CDC (African Centres for Disease Control and Prevention) data.

    Provides access to:
    - Disease outbreak surveillance data
    - COVID-19 historical data for African countries
    - Vaccination coverage data
    - Event-based surveillance alerts
    - Weekly outbreak briefs

    Example:
        >>> africa_cdc = AfricaCDCAccessor()
        >>>
        >>> # Get current disease outbreaks
        >>> outbreaks = africa_cdc.get_disease_outbreaks()
        >>>
        >>> # Get COVID-19 data for specific countries
        >>> covid = africa_cdc.get_covid_data(
        ...     countries=['Nigeria', 'South Africa', 'Kenya'],
        ...     date_range=('2020-03-01', '2021-12-31')
        ... )
        >>>
        >>> # Get vaccination coverage
        >>> vaccination = africa_cdc.get_vaccination_coverage(
        ...     countries=['Nigeria', 'Ethiopia'],
        ...     vaccines=['COVID-19', 'Measles']
        ... )

    Data Sources:
        - Africa CDC: https://africacdc.org/
        - Weekly Outbreak Briefs: PDF reports
        - IDSR: Integrated Disease Surveillance and Response
        - Member State reports
    """

    # Base URLs for Africa CDC
    BASE_URL = "https://africacdc.org"

    # African Union Member States (55 countries)
    COUNTRIES = {
        "DZ": "Algeria",
        "AO": "Angola",
        "BJ": "Benin",
        "BW": "Botswana",
        "BF": "Burkina Faso",
        "BI": "Burundi",
        "CV": "Cabo Verde",
        "CM": "Cameroon",
        "CF": "Central African Republic",
        "TD": "Chad",
        "KM": "Comoros",
        "CG": "Congo",
        "CD": "Democratic Republic of the Congo",
        "CI": "Côte d'Ivoire",
        "DJ": "Djibouti",
        "EG": "Egypt",
        "GQ": "Equatorial Guinea",
        "ER": "Eritrea",
        "SZ": "Eswatini",
        "ET": "Ethiopia",
        "GA": "Gabon",
        "GM": "Gambia",
        "GH": "Ghana",
        "GN": "Guinea",
        "GW": "Guinea-Bissau",
        "KE": "Kenya",
        "LS": "Lesotho",
        "LR": "Liberia",
        "LY": "Libya",
        "MG": "Madagascar",
        "MW": "Malawi",
        "ML": "Mali",
        "MR": "Mauritania",
        "MU": "Mauritius",
        "MA": "Morocco",
        "MZ": "Mozambique",
        "NA": "Namibia",
        "NE": "Niger",
        "NG": "Nigeria",
        "RW": "Rwanda",
        "ST": "Sao Tome and Principe",
        "SN": "Senegal",
        "SC": "Seychelles",
        "SL": "Sierra Leone",
        "SO": "Somalia",
        "ZA": "South Africa",
        "SS": "South Sudan",
        "SD": "Sudan",
        "TZ": "Tanzania",
        "TG": "Togo",
        "TN": "Tunisia",
        "UG": "Uganda",
        "ZM": "Zambia",
        "ZW": "Zimbabwe",
    }

    # Africa CDC Regions
    REGIONS = {
        "Central": ["CM", "CF", "TD", "CG", "CD", "GQ", "GA", "ST"],
        "Eastern": [
            "BI",
            "DJ",
            "ER",
            "ET",
            "KE",
            "MG",
            "MW",
            "MU",
            "RW",
            "SC",
            "SO",
            "SS",
            "TZ",
            "UG",
            "ZM",
            "ZW",
        ],
        "Northern": ["DZ", "EG", "LY", "MA", "TN", "SD"],
        "Southern": ["AO", "BW", "SZ", "LS", "MW", "MZ", "NA", "ZA", "ZM", "ZW"],
        "Western": [
            "BJ",
            "BF",
            "CV",
            "CI",
            "GM",
            "GH",
            "GN",
            "GW",
            "LR",
            "ML",
            "MR",
            "NE",
            "NG",
            "SN",
            "SL",
            "TG",
        ],
    }

    # Priority diseases tracked by Africa CDC
    PRIORITY_DISEASES = {
        "COVID-19": "Coronavirus Disease 2019",
        "EBOLA": "Ebola Virus Disease",
        "MARBRG": "Marburg Virus Disease",
        "LASSA": "Lassa Fever",
        "CHOLERA": "Cholera",
        "MEASLES": "Measles",
        "YELLOW_FEVER": "Yellow Fever",
        "MPOX": "Mpox (Monkeypox)",
        "CCHF": "Crimean-Congo Hemorrhagic Fever",
        "RVF": "Rift Valley Fever",
        "DENGUE": "Dengue Fever",
        "MALARIA": "Malaria",
        "TYPHOID": "Typhoid Fever",
        "MENINGITIS": "Meningococcal Meningitis",
        "INFLUENZA": "Influenza",
    }

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize Africa CDC accessor.

        Args:
            cache_dir: Directory to cache downloaded data (optional)
        """
        self.cache_dir = cache_dir
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": "Africa-CDC-Data-Accessor/1.0 (Research Purpose)",
                "Accept": "application/json, text/csv, application/pdf",
            }
        )
        self._cache = {}

    def list_countries(self) -> pd.DataFrame:
        """
        List all African Union member states.

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
        List Africa CDC regions and their countries.

        Returns
        -------
            DataFrame with regions and country codes
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

    def list_priority_diseases(self) -> pd.DataFrame:
        """
        List priority diseases tracked by Africa CDC.

        Returns
        -------
            DataFrame with disease codes and names
        """
        return pd.DataFrame(
            [(code, name) for code, name in self.PRIORITY_DISEASES.items()],
            columns=["disease_code", "disease_name"],
        )

    def get_countries_by_region(self, region: str) -> List[str]:
        """
        Get country codes by Africa CDC region.

        Args:
            region: Region name (Central, Eastern, Northern, Southern, Western)

        Returns
        -------
            List of country codes
        """
        return self.REGIONS.get(region, [])

    def get_disease_outbreaks(
        self,
        disease: Optional[str] = None,
        countries: Optional[List[str]] = None,
        date_range: Optional[Tuple[str, str]] = None,
    ) -> pd.DataFrame:
        """
        Get disease outbreak data from Africa CDC.

        This method retrieves outbreak surveillance data from Africa CDC's
        weekly outbreak briefs and event-based surveillance system.

        Args:
            disease: Disease code (e.g., 'COVID-19', 'EBOLA', 'CHOLERA')
                    Use list_priority_diseases() to see available codes
            countries: List of ISO country codes (e.g., ['NG', 'ZA', 'KE'])
                      Use list_countries() to see available codes
            date_range: Tuple of (start_date, end_date) in 'YYYY-MM-DD' format

        Returns
        -------
            DataFrame with outbreak data including:
            - disease_code: Disease code
            - disease_name: Disease name
            - country_code: ISO country code
            - country_name: Country name
            - date_reported: Date the outbreak was reported
            - cases: Number of confirmed cases
            - deaths: Number of deaths
            - status: Outbreak status (active, contained, etc.)
            - source: Data source

        Example:
            >>> africa_cdc = AfricaCDCAccessor()
            >>> # Get all current Ebola outbreaks
            >>> ebola = africa_cdc.get_disease_outbreaks(disease='EBOLA')
            >>>
            >>> # Get outbreaks in West Africa
            >>> west_africa = africa_cdc.get_countries_by_region('Western')
            >>> outbreaks = africa_cdc.get_disease_outbreaks(countries=west_africa)

        Note:
            This method provides data based on Africa CDC's weekly outbreak briefs.
            For real-time data, use get_event_based_surveillance().
        """
        # Validate disease code
        if disease and disease not in self.PRIORITY_DISEASES:
            valid_diseases = list(self.PRIORITY_DISEASES.keys())
            logger.warning(
                f"Disease '{disease}' not recognized. Valid codes: {valid_diseases}"
            )
            return pd.DataFrame()

        # Validate country codes
        if countries:
            valid_countries = [c for c in countries if c in self.COUNTRIES]
            if not valid_countries:
                logger.warning(
                    f"No valid country codes. Available: {list(self.COUNTRIES.keys())}"
                )
                return pd.DataFrame()
            countries = valid_countries

        logger.info(
            f"Fetching outbreak data for disease={disease}, "
            f"countries={len(countries) if countries else 'all'}"
        )

        # In a real implementation, this would:
        # 1. Scrape Africa CDC outbreak briefs
        # 2. Query IDSR databases via API if available
        # 3. Parse weekly PDF reports
        # For now, return a structured template

        data = []
        country_list = countries if countries else list(self.COUNTRIES.keys())
        disease_list = [disease] if disease else list(self.PRIORITY_DISEASES.keys())

        for d_code in disease_list:
            for c_code in country_list:
                record = {
                    "disease_code": d_code,
                    "disease_name": self.PRIORITY_DISEASES.get(d_code, d_code),
                    "country_code": c_code,
                    "country_name": self.COUNTRIES.get(c_code, c_code),
                    "date_reported": None,
                    "cases": None,
                    "deaths": None,
                    "status": "Data requires access to Africa CDC outbreak briefs",
                    "source": "Africa CDC Weekly Outbreak Briefs",
                    "note": "Integration with Africa CDC API or PDF parsing required",
                }
                data.append(record)

        logger.warning(
            "Outbreak data requires integration with Africa CDC weekly briefs "
            "or IDSR databases. This is a placeholder structure."
        )
        return pd.DataFrame(data)

    def get_covid_data(
        self,
        countries: Optional[List[str]] = None,
        date_range: Optional[Tuple[str, str]] = None,
    ) -> pd.DataFrame:
        """
        Get COVID-19 surveillance data for African countries.

        This method retrieves historical COVID-19 data (cases, deaths,
        recoveries, tests) for African countries.

        Args:
            countries: List of ISO country codes (e.g., ['NG', 'ZA', 'KE'])
                      Use list_countries() to see available codes
            date_range: Tuple of (start_date, end_date) in 'YYYY-MM-DD' format
                       Default: Full pandemic period (2020-2023)

        Returns
        -------
            DataFrame with COVID-19 data including:
            - country_code: ISO country code
            - country_name: Country name
            - date: Date of observation
            - cases_total: Cumulative confirmed cases
            - cases_new: New cases reported
            - deaths_total: Cumulative deaths
            - deaths_new: New deaths reported
            - recovered_total: Cumulative recoveries
            - tests_total: Cumulative tests conducted
            - source: Data source

        Example:
            >>> africa_cdc = AfricaCDCAccessor()
            >>> # Get COVID-19 data for all of 2021
            >>> covid = africa_cdc.get_covid_data(
            ...     countries=['ZA', 'NG', 'ET'],
            ...     date_range=('2021-01-01', '2021-12-31')
            ... )
            >>>
            >>> # Get data for East Africa
            >>> east_africa = africa_cdc.get_countries_by_region('Eastern')
            >>> covid_east = africa_cdc.get_covid_data(countries=east_africa)

        Note:
            COVID-19 data is historical (pandemic period).
            Consider using OWID or WHO sources for more complete global data.
            Africa CDC data may focus on African-specific surveillance.
        """
        # Validate country codes
        if countries:
            valid_countries = [c for c in countries if c in self.COUNTRIES]
            if not valid_countries:
                logger.warning(
                    f"No valid country codes. Available: {list(self.COUNTRIES.keys())}"
                )
                return pd.DataFrame()
            countries = valid_countries

        # Default date range: pandemic period
        if date_range is None:
            date_range = ("2020-03-01", "2023-12-31")

        logger.info(
            f"Fetching COVID-19 data for {len(countries) if countries else 'all'} countries, "
            f"period: {date_range[0]} to {date_range[1]}"
        )

        # Placeholder structure
        data = []
        country_list = countries if countries else list(self.COUNTRIES.keys())

        for c_code in country_list:
            record = {
                "country_code": c_code,
                "country_name": self.COUNTRIES.get(c_code, c_code),
                "date_from": date_range[0],
                "date_to": date_range[1],
                "cases_total": None,
                "cases_new": None,
                "deaths_total": None,
                "deaths_new": None,
                "recovered_total": None,
                "tests_total": None,
                "source": "Africa CDC / National Ministries of Health",
                "note": "Data requires access to Africa CDC COVID-19 dashboard or OWID",
            }
            data.append(record)

        logger.warning(
            "COVID-19 data requires integration with Africa CDC dashboard "
            "or alternative sources (OWID, WHO). This is a placeholder structure."
        )
        return pd.DataFrame(data)

    def get_vaccination_coverage(
        self,
        countries: List[str],
        vaccines: List[str],
    ) -> pd.DataFrame:
        """
        Get vaccination coverage data for African countries.

        This method retrieves vaccination coverage data for specified
        vaccines and countries.

        Args:
            countries: List of ISO country codes (e.g., ['NG', 'ZA'])
                      Use list_countries() to see available codes
            vaccines: List of vaccine names (e.g., ['COVID-19', 'Measles', 'Yellow Fever'])

        Returns
        -------
            DataFrame with vaccination coverage data including:
            - country_code: ISO country code
            - country_name: Country name
            - vaccine: Vaccine name
            - coverage_percentage: Percentage of target population vaccinated
            - doses_administered: Total doses administered
            - target_population: Target population size
            - date: Date of coverage estimate
            - source: Data source

        Example:
            >>> africa_cdc = AfricaCDCAccessor()
            >>> # Get COVID-19 vaccination for West Africa
            >>> west_africa = africa_cdc.get_countries_by_region('Western')
            >>> covid_vax = africa_cdc.get_vaccination_coverage(
            ...     countries=west_africa,
            ...     vaccines=['COVID-19']
            ... )
            >>>
            >>> # Get multiple vaccines for specific countries
            >>> vax_data = africa_cdc.get_vaccination_coverage(
            ...     countries=['NG', 'ET', 'ZA'],
            ...     vaccines=['COVID-19', 'Measles', 'Yellow Fever']
            ... )

        Note:
            Vaccination data may be sourced from:
            - Africa CDC Vaccine Delivery Alliance (AVDA)
            - WHO Immunization Data Portal
            - National immunization programs
        """
        # Validate inputs
        if not countries or not vaccines:
            logger.warning("Both 'countries' and 'vaccines' parameters are required")
            return pd.DataFrame()

        valid_countries = [c for c in countries if c in self.COUNTRIES]
        if not valid_countries:
            logger.warning(
                f"No valid country codes. Available: {list(self.COUNTRIES.keys())}"
            )
            return pd.DataFrame()

        logger.info(
            f"Fetching vaccination data for {len(valid_countries)} countries, "
            f"vaccines: {vaccines}"
        )

        # Placeholder structure
        data = []
        for c_code in valid_countries:
            for vaccine in vaccines:
                record = {
                    "country_code": c_code,
                    "country_name": self.COUNTRIES.get(c_code, c_code),
                    "vaccine": vaccine,
                    "coverage_percentage": None,
                    "doses_administered": None,
                    "target_population": None,
                    "date": None,
                    "source": "Africa CDC / WHO Immunization Portal",
                    "note": "Data requires access to WHO or AVDA databases",
                }
                data.append(record)

        logger.warning(
            "Vaccination data requires integration with WHO Immunization Data Portal "
            "or Africa CDC AVDA. This is a placeholder structure."
        )
        return pd.DataFrame(data)

    def get_event_based_surveillance(
        self,
        countries: Optional[List[str]] = None,
        date_range: Optional[Tuple[str, str]] = None,
    ) -> pd.DataFrame:
        """
        Get Event-Based Surveillance (EBS) alerts from Africa CDC.

        Event-based surveillance captures potential public health threats
        through real-time monitoring of various sources including media
        reports, rumors, and community alerts.

        Args:
            countries: List of ISO country codes to filter by
            date_range: Tuple of (start_date, end_date) in 'YYYY-MM-DD' format

        Returns
        -------
            DataFrame with EBS alerts including:
            - alert_id: Unique alert identifier
            - country_code: ISO country code
            - country_name: Country name
            - event_type: Type of health event
            - description: Brief description of the event
            - date_detected: Date the event was detected
            - verification_status: Status (verified, unverified, discarded)
            - risk_level: Risk assessment (low, medium, high)
            - source: Information source

        Example:
            >>> africa_cdc = AfricaCDCAccessor()
            >>> # Get recent EBS alerts
            >>> alerts = africa_cdc.get_event_based_surveillance()
            >>>
            >>> # Get alerts for specific countries
            >>> sahel = ['ML', 'NE', 'TD', 'BF']
            >>> sahel_alerts = africa_cdc.get_event_based_surveillance(
            ...     countries=sahel,
            ...     date_range=('2024-01-01', '2024-12-31')
            ... )

        Note:
            EBS data requires access to Africa CDC's EBS platform
            or participation in the surveillance network.
        """
        # Validate country codes
        if countries:
            valid_countries = [c for c in countries if c in self.COUNTRIES]
            if not valid_countries:
                logger.warning(
                    f"No valid country codes. Available: {list(self.COUNTRIES.keys())}"
                )
                return pd.DataFrame()
            countries = valid_countries

        logger.info(
            f"Fetching EBS alerts for {len(countries) if countries else 'all'} countries"
        )

        # Placeholder structure
        data = []
        country_list = countries if countries else list(self.COUNTRIES.keys())

        for c_code in country_list:
            record = {
                "alert_id": None,
                "country_code": c_code,
                "country_name": self.COUNTRIES.get(c_code, c_code),
                "event_type": None,
                "description": None,
                "date_detected": None,
                "verification_status": "Data requires EBS platform access",
                "risk_level": None,
                "source": "Africa CDC EBS",
                "note": "Integration with Africa CDC EBS system required",
            }
            data.append(record)

        logger.warning(
            "EBS data requires access to Africa CDC's Event-Based Surveillance "
            "platform. This is a placeholder structure."
        )
        return pd.DataFrame(data)

    def get_weekly_outbreak_brief(
        self,
        year: int,
        week: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Get Africa CDC Weekly Outbreak Brief metadata.

        Africa CDC publishes weekly outbreak briefs summarizing
        disease outbreaks across the African continent.

        Args:
            year: Year of the brief (e.g., 2024)
            week: Specific epidemiological week (1-53). If None, returns all weeks.

        Returns
        -------
            DataFrame with outbreak brief metadata including:
            - year: Year
            - week: Epidemiological week
            - brief_url: URL to the brief document
            - publication_date: Publication date
            - diseases_covered: List of diseases mentioned
            - countries_mentioned: Countries with reported outbreaks

        Example:
            >>> africa_cdc = AfricaCDCAccessor()
            >>> # Get all briefs for 2024
            >>> briefs_2024 = africa_cdc.get_weekly_outbreak_brief(year=2024)
            >>>
            >>> # Get specific week
            >>> week_20 = africa_cdc.get_weekly_outbreak_brief(year=2024, week=20)

        Note:
            Weekly briefs are typically published as PDF documents.
            This method provides metadata and URLs for accessing them.
        """
        logger.info(
            f"Fetching outbreak briefs for year {year}, week {week if week else 'all'}"
        )

        # Validate year
        current_year = datetime.now().year
        if year < 2020 or year > current_year:
            logger.warning(f"Year {year} may not have available briefs")

        # Build brief metadata
        briefs = []

        if week:
            weeks = [week]
        else:
            weeks = list(range(1, 54))

        for w in weeks:
            brief = {
                "year": year,
                "week": w,
                "brief_url": f"{self.BASE_URL}/resources/?filter=outbreak-brief&year={year}&week={w}",
                "publication_date": None,
                "diseases_covered": list(self.PRIORITY_DISEASES.values())[:10],
                "countries_mentioned": "Varies by week",
                "data_source": "Africa CDC",
                "note": "Briefs are PDF documents. Data extraction requires PDF parsing.",
            }
            briefs.append(brief)

        logger.warning(
            "Weekly outbreak briefs are published as PDF documents. "
            "For structured data, use get_disease_outbreaks() or access IDSR databases."
        )

        return pd.DataFrame(briefs)

    def get_summary_by_country(
        self,
        year: int,
        disease: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Get outbreak summary statistics by country for a given year.

        Args:
            year: Year to summarize
            disease: Optional disease code to filter by

        Returns
        -------
            DataFrame with summary statistics by country
        """
        outbreaks = self.get_disease_outbreaks(
            disease=disease,
            date_range=(f"{year}-01-01", f"{year}-12-31"),
        )

        if outbreaks.empty:
            return pd.DataFrame()

        # Aggregate by country
        summary = (
            outbreaks.groupby("country_code")
            .agg(
                {
                    "cases": "sum",
                    "deaths": "sum",
                    "disease_code": "count",
                }
            )
            .reset_index()
        )

        summary.columns = ["country_code", "total_cases", "total_deaths", "n_outbreaks"]
        summary["country_name"] = summary["country_code"].map(self.COUNTRIES)
        summary["year"] = year

        return summary

    def compare_regions(
        self,
        disease: str,
        year: int,
    ) -> pd.DataFrame:
        """
        Compare disease occurrence across Africa CDC regions.

        Args:
            disease: Disease code to compare
            year: Year to compare

        Returns
        -------
            DataFrame with regional comparison
        """
        outbreaks = self.get_disease_outbreaks(
            disease=disease,
            date_range=(f"{year}-01-01", f"{year}-12-31"),
        )

        if outbreaks.empty:
            return pd.DataFrame()

        # Add region information
        region_map = {}
        for region, countries in self.REGIONS.items():
            for c in countries:
                region_map[c] = region

        outbreaks["region"] = outbreaks["country_code"].map(region_map)

        # Aggregate by region
        comparison = (
            outbreaks.groupby("region")
            .agg(
                {
                    "cases": "sum",
                    "deaths": "sum",
                    "country_code": "nunique",
                }
            )
            .reset_index()
        )

        comparison.columns = ["region", "total_cases", "total_deaths", "n_countries"]
        comparison["year"] = year
        comparison["disease_code"] = disease
        comparison["disease_name"] = self.PRIORITY_DISEASES.get(disease, disease)

        return comparison


def main():
    """
    Example usage of AfricaCDCAccessor.
    """
    print("=" * 70)
    print("Africa CDC (Centres for Disease Control and Prevention) Data Accessor")
    print("=" * 70)

    africa_cdc = AfricaCDCAccessor()

    # List countries
    print("\n🌍 African Union Member States:")
    countries = africa_cdc.list_countries()
    print(f"Total countries: {len(countries)}")
    print("\nFirst 10 countries:")
    print(countries.head(10).to_string(index=False))

    # List regions
    print("\n🗺️  Africa CDC Regions:")
    regions = africa_cdc.list_regions()
    for region in regions["region"].unique():
        n_countries = len(regions[regions["region"] == region])
        print(f"  - {region}: {n_countries} countries")

    # List priority diseases
    print("\n🦠 Priority Diseases:")
    diseases = africa_cdc.list_priority_diseases()
    print(f"Total diseases: {len(diseases)}")
    for _, row in diseases.head(10).iterrows():
        print(f"  - {row['disease_code']}: {row['disease_name']}")

    # Show example data access
    print("\n📊 Example Usage:")
    print("  africa_cdc = AfricaCDCAccessor()")
    print("  outbreaks = africa_cdc.get_disease_outbreaks(disease='EBOLA')")
    print("  covid = africa_cdc.get_covid_data(")
    print("      countries=['NG', 'ZA', 'KE'],")
    print("      date_range=('2020-03-01', '2021-12-31')")
    print("  )")
    print("  vaccination = africa_cdc.get_vaccination_coverage(")
    print("      countries=['NG', 'ET'],")
    print("      vaccines=['COVID-19', 'Measles']")
    print("  )")
    print("  alerts = africa_cdc.get_event_based_surveillance()")

    print("\n✅ Africa CDC accessor ready to use!")


if __name__ == "__main__":
    main()
