"""
India IDSP (Integrated Disease Surveillance Programme) Data Accessor

This module provides access to disease surveillance data from India's
Integrated Disease Surveillance Programme (IDSP), including:
- Weekly outbreak reports
- Disease surveillance data by state/district
- Seasonal disease patterns
- Priority disease tracking

Data Sources:
- IDSP Portal: https://idsp.nic.in/
- Ministry of Health & Family Welfare: https://www.mohfw.gov.in/
- NVBDCP (Vector Borne Diseases): https://nvbdcp.gov.in/

Update Frequency:
- Weekly outbreak reports (IDSP)
- Monthly surveillance summaries
- Annual statistical reports

License: Open Government Data (India)

Author: Flávio Codeço Coelho
License: MIT
"""

import logging
from datetime import datetime
from typing import ClassVar, List, Optional, Tuple

import pandas as pd
import requests
from bs4 import BeautifulSoup

from epidatasets._base import BaseAccessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IndiaIDSPAccessor(BaseAccessor):
    """
    Accessor for India IDSP (Integrated Disease Surveillance Programme) data.

    Provides access to:
    - Weekly outbreak reports
    - Disease surveillance by state and district
    - Seasonal disease surveillance
    - Priority disease data (AIDS, Malaria, Dengue, etc.)
    - IDSP portal data extraction

    Example:
        >>> idsp = IndiaIDSPAccessor()
        >>>
        >>> # Get outbreak reports
        >>> outbreaks = idsp.get_outbreak_reports(
        ...     years=[2023],
        ...     states=["Kerala", "Maharashtra"]
        ... )
        >>>
        >>> # Get disease surveillance
        >>> dengue = idsp.get_disease_surveillance(
        ...     disease="Dengue",
        ...     states=["Delhi", "Karnataka"],
        ...     years=[2022, 2023]
        ... )

    Data Sources:
        - IDSP Portal: https://idsp.nic.in/
        - NVBDCP: https://nvbdcp.gov.in/ (Vector-borne diseases)
        - NACO: http://naco.gov.in/ (HIV/AIDS)
    """

    source_name: ClassVar[str] = "india_idsp"
    source_description: ClassVar[str] = (
        "Disease surveillance data from India's Integrated Disease Surveillance "
        "Programme (IDSP), including weekly outbreak reports, disease surveillance "
        "by state/district, seasonal disease patterns, and priority disease tracking."
    )
    source_url: ClassVar[str] = "https://idsp.nic.in/"

    # Portal URLs
    IDSP_URL = "https://idsp.nic.in"
    NVBDCP_URL = "https://nvbdcp.gov.in"
    NACO_URL = "http://naco.gov.in"
    MOHFW_URL = "https://www.mohfw.gov.in"

    # Indian states and union territories (28 states + 8 UTs)
    STATES = {
        "AN": "Andaman and Nicobar Islands",
        "AP": "Andhra Pradesh",
        "AR": "Arunachal Pradesh",
        "AS": "Assam",
        "BR": "Bihar",
        "CH": "Chandigarh",
        "CT": "Chhattisgarh",
        "DN": "Dadra and Nagar Haveli and Daman and Diu",
        "DL": "Delhi",
        "GA": "Goa",
        "GJ": "Gujarat",
        "HR": "Haryana",
        "HP": "Himachal Pradesh",
        "JK": "Jammu and Kashmir",
        "JH": "Jharkhand",
        "KA": "Karnataka",
        "KL": "Kerala",
        "LA": "Ladakh",
        "LD": "Lakshadweep",
        "MP": "Madhya Pradesh",
        "MH": "Maharashtra",
        "MN": "Manipur",
        "ML": "Meghalaya",
        "MZ": "Mizoram",
        "NL": "Nagaland",
        "OR": "Odisha",
        "PY": "Puducherry",
        "PB": "Punjab",
        "RJ": "Rajasthan",
        "SK": "Sikkim",
        "TN": "Tamil Nadu",
        "TG": "Telangana",
        "TR": "Tripura",
        "UP": "Uttar Pradesh",
        "UT": "Uttarakhand",
        "WB": "West Bengal",
    }

    # Priority diseases under IDSP surveillance
    PRIORITY_DISEASES = {
        "Acute_Diarrhoeal_Disease": {"syndrome": "S", "category": "Epidemic-prone"},
        "Bacillary_Dysentery": {"syndrome": "S", "category": "Epidemic-prone"},
        "Viral_Hepatitis": {"syndrome": "S", "category": "Epidemic-prone"},
        "Typhoid": {"syndrome": "S", "category": "Epidemic-prone"},
        "Measles": {"syndrome": "S", "category": "Epidemic-prone"},
        "Meningococcal_Meningitis": {"syndrome": "S", "category": "Epidemic-prone"},
        "Dengue": {"syndrome": "S", "category": "Epidemic-prone"},
        "Malaria": {"syndrome": "S", "category": "Epidemic-prone"},
        "Chikungunya": {"syndrome": "S", "category": "Epidemic-prone"},
        "Acute_Encephalitis_Syndrome": {"syndrome": "S", "category": "Epidemic-prone"},
        "Acute_Flaccid_Paralysis": {"syndrome": "S", "category": "Epidemic-prone"},
        "Unusual_Syndrome": {"syndrome": "U", "category": "Unknown"},
        "Influenza_Like_Illness": {"syndrome": "P", "category": "Seasonal"},
        "Severe_Acute_Respiratory_Infection": {"syndrome": "P", "category": "Seasonal"},
        "COVID_19": {"syndrome": "P", "category": "Pandemic"},
        "Leptospirosis": {"syndrome": "S", "category": "Seasonal"},
        "Malaria_Pf": {"syndrome": "S", "category": "Vector-borne"},
        "Malaria_Pv": {"syndrome": "S", "category": "Vector-borne"},
        "Dengue_Fever": {"syndrome": "S", "category": "Vector-borne"},
        "Dengue_HF": {"syndrome": "S", "category": "Vector-borne"},
        "Chikungunya_Fever": {"syndrome": "S", "category": "Vector-borne"},
        "Japanese_Encephalitis": {"syndrome": "S", "category": "Vector-borne"},
        "Kala_Azar": {"syndrome": "S", "category": "Vector-borne"},
        "Filariasis": {"syndrome": "S", "category": "Vector-borne"},
        "Tuberculosis": {"syndrome": "L", "category": "Routine"},
        "HIV_AIDS": {"syndrome": "L", "category": "Routine"},
        "Leprosy": {"syndrome": "L", "category": "Routine"},
        "Malaria_Lab": {"syndrome": "L", "category": "Lab-confirmed"},
        "Typhoid_Lab": {"syndrome": "L", "category": "Lab-confirmed"},
    }

    # Disease syndromes (S, P, U, L)
    SYNDROMES = {
        "S": "Syndromic (clinical diagnosis)",
        "P": "Presumptive (clinical + epidemiological)",
        "U": "Unusual event/syndrome",
        "L": "Laboratory confirmed",
    }

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize India IDSP accessor.

        Args:
            cache_dir: Directory to cache downloaded data (optional)
        """
        self.cache_dir = cache_dir
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": "India-IDSP-Accessor/1.0 (Research Purpose)",
                "Accept": "text/html, text/csv, application/pdf",
            }
        )
        self._cache = {}

    def list_countries(self) -> pd.DataFrame:
        """
        List countries covered by India IDSP.

        India IDSP only covers India, returning Indian states and union territories.

        Returns:
            DataFrame with country information
        """
        return pd.DataFrame(
            [{"country_code": "IN", "country_name": "India"}]
        )

    def list_states(self) -> pd.DataFrame:
        """
        List Indian states and union territories.

        Returns
        -------
            DataFrame with state codes and names
        """
        return pd.DataFrame(
            [(code, name) for code, name in self.STATES.items()],
            columns=["state_code", "state_name"],
        )

    def list_priority_diseases(self) -> pd.DataFrame:
        """
        List priority diseases under IDSP surveillance.

        Returns
        -------
            DataFrame with disease information
        """
        data = []
        for code, info in self.PRIORITY_DISEASES.items():
            data.append(
                {
                    "disease_code": code,
                    "syndrome_code": info["syndrome"],
                    "syndrome_name": self.SYNDROMES.get(info["syndrome"], "Unknown"),
                    "category": info["category"],
                }
            )
        return pd.DataFrame(data)

    def get_outbreak_reports(
        self,
        years: Optional[List[int]] = None,
        states: Optional[List[str]] = None,
        diseases: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Get weekly outbreak reports from IDSP.

        Args:
            years: List of years (e.g., [2022, 2023])
            states: List of state codes (e.g., ["KL", "MH"])
            diseases: List of disease codes to filter

        Returns
        -------
            DataFrame with outbreak report data
        """
        # Validate states
        if states:
            valid_states = [s for s in states if s in self.STATES]
            if not valid_states:
                logger.error(f"No valid state codes. Valid: {list(self.STATES.keys())}")
                return pd.DataFrame()
            states = valid_states

        # Validate diseases
        if diseases:
            valid_diseases = [d for d in diseases if d in self.PRIORITY_DISEASES]
            if not valid_diseases:
                logger.error(f"No valid disease codes. Valid: {list(self.PRIORITY_DISEASES.keys())}")
                return pd.DataFrame()
            diseases = valid_diseases

        logger.info(
            f"Fetching outbreak reports: years={years}, states={states}, diseases={diseases}"
        )

        # IDSP outbreak data is available via:
        # - Weekly PDF reports on idsp.nic.in
        # - Dashboard data (if API available)
        # - Manual data entry forms

        data = []
        years_list = years if years else [datetime.now().year]
        states_list = states if states else list(self.STATES.keys())[:5]

        for year in years_list:
            for state in states_list:
                record = {
                    "year": year,
                    "state_code": state,
                    "state_name": self.STATES[state],
                    "outbreak_id": None,
                    "disease_code": diseases[0] if diseases else None,
                    "cases_reported": None,
                    "deaths_reported": None,
                    "districts_affected": None,
                    "start_date": None,
                    "end_date": None,
                    "status": None,
                    "response_measures": None,
                    "data_source": "IDSP Weekly Outbreak Reports",
                    "note": "Data requires IDSP portal access or PDF parsing",
                }
                data.append(record)

        logger.warning(
            "IDSP outbreak data requires access to https://idsp.nic.in/ "
            "or parsing of weekly PDF reports."
        )
        return pd.DataFrame(data)

    def get_disease_surveillance(
        self,
        disease: str,
        states: Optional[List[str]] = None,
        years: Optional[List[int]] = None,
    ) -> pd.DataFrame:
        """
        Get disease surveillance data for a specific disease.

        Args:
            disease: Disease code (e.g., "Dengue", "Malaria")
            states: List of state codes
            years: List of years

        Returns
        -------
            DataFrame with surveillance data
        """
        if disease not in self.PRIORITY_DISEASES:
            valid = list(self.PRIORITY_DISEASES.keys())
            logger.error(f"Invalid disease code '{disease}'. Valid: {valid}")
            return pd.DataFrame()

        # Validate states
        if states:
            valid_states = [s for s in states if s in self.STATES]
            if not valid_states:
                logger.error(f"No valid state codes. Valid: {list(self.STATES.keys())}")
                return pd.DataFrame()
            states = valid_states

        logger.info(
            f"Fetching surveillance for {disease}: states={states}, years={years}"
        )

        # Surveillance data is collected through:
        # - Weekly S, P, L reporting
        # - District-level aggregation
        # - State-level consolidation

        data = []
        years_list = years if years else [datetime.now().year]
        states_list = states if states else ["MH", "KL", "KA"]  # Sample states

        for year in years_list:
            for state in states_list:
                record = {
                    "year": year,
                    "state_code": state,
                    "state_name": self.STATES[state],
                    "disease_code": disease,
                    "syndrome": self.PRIORITY_DISEASES[disease]["syndrome"],
                    "cases_total": None,
                    "deaths_total": None,
                    "cases_lab_confirmed": None,
                    "cases_presumptive": None,
                    "cases_syndromic": None,
                    "reporting_units": None,
                    "data_completeness": None,
                    "data_source": "IDSP Surveillance System",
                    "note": "Data requires IDSP portal access",
                }
                data.append(record)

        logger.warning(
            f"{disease} surveillance data requires IDSP portal access. "
            "Some diseases (e.g., Dengue, Malaria) also available via NVBDCP."
        )
        return pd.DataFrame(data)

    def get_vector_borne_diseases(
        self,
        diseases: List[str],
        states: Optional[List[str]] = None,
        years: Optional[List[int]] = None,
    ) -> pd.DataFrame:
        """
        Get vector-borne disease data from NVBDCP.

        Args:
            diseases: List of vector-borne diseases
                      (e.g., ["Malaria", "Dengue", "Chikungunya"])
            states: List of state codes
            years: List of years

        Returns
        -------
            DataFrame with vector-borne disease data
        """
        valid_vbd = ["Malaria", "Dengue", "Chikungunya", "Japanese_Encephalitis",
                     "Kala_Azar", "Filariasis", "Malaria_Pf", "Malaria_Pv",
                     "Dengue_Fever", "Dengue_HF", "Chikungunya_Fever"]

        diseases = [d for d in diseases if d in valid_vbd]
        if not diseases:
            logger.error(f"No valid vector-borne diseases. Valid: {valid_vbd}")
            return pd.DataFrame()

        logger.info(f"Fetching VBD data: diseases={diseases}")

        # NVBDCP data is available at https://nvbdcp.gov.in/
        # Includes monthly/district-level data

        data = []
        years_list = years if years else [datetime.now().year]

        for disease in diseases:
            for year in years_list:
                record = {
                    "year": year,
                    "disease": disease,
                    "cases": None,
                    "deaths": None,
                    "api": None,  # Annual Parasite Incidence
                    "spr": None,  # Slide Positivity Rate
                    "data_source": "NVBDCP / IDSP",
                    "note": "Data requires NVBDCP portal access",
                }
                data.append(record)

        logger.warning(
            "Vector-borne disease data available via https://nvbdcp.gov.in/"
        )
        return pd.DataFrame(data)

    def get_weekly_surveillance_summary(
        self,
        year: int,
        week: int,
        state: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Get weekly surveillance summary (Form S, P, L data).

        Args:
            year: Year
            week: Epidemiological week (1-52)
            state: State code (optional, default: all India)

        Returns
        -------
            DataFrame with weekly surveillance data
        """
        logger.info(f"Fetching weekly summary for {year} week {week}, state={state}")

        # IDSP weekly surveillance uses S (Syndromic), P (Presumptive), L (Lab) forms
        # Data is aggregated weekly from reporting units

        data = []
        diseases = list(self.PRIORITY_DISEASES.keys())[:10]  # Sample

        for disease in diseases:
            record = {
                "year": year,
                "week": week,
                "state": state or "All India",
                "disease_code": disease,
                "syndromic_cases": None,
                "presumptive_cases": None,
                "lab_confirmed_cases": None,
                "deaths": None,
                "reporting_units": None,
                "data_source": "IDSP Weekly S/P/L Reports",
                "note": "Data requires IDSP portal access",
            }
            data.append(record)

        return pd.DataFrame(data)

    def get_seasonal_patterns(
        self,
        disease: str,
        years: List[int],
    ) -> pd.DataFrame:
        """
        Get seasonal disease patterns.

        Args:
            disease: Disease code
            years: List of years to analyze

        Returns
        -------
            DataFrame with seasonal pattern data
        """
        logger.info(f"Analyzing seasonal patterns for {disease}")

        data = []
        for year in years:
            for month in range(1, 13):
                record = {
                    "year": year,
                    "month": month,
                    "disease": disease,
                    "cases": None,
                    "expected_cases": None,  # Based on historical patterns
                    "alert_threshold": None,
                    "epidemic_threshold": None,
                    "data_source": "IDSP Historical Analysis",
                    "note": "Seasonal analysis requires historical data",
                }
                data.append(record)

        return pd.DataFrame(data)

    def get_lab_surveillance(
        self,
        diseases: Optional[List[str]] = None,
        states: Optional[List[str]] = None,
        year: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Get laboratory surveillance data (Form L).

        Args:
            diseases: List of diseases
            states: List of states
            year: Year

        Returns
        -------
            DataFrame with laboratory data
        """
        logger.info("Fetching laboratory surveillance data")

        # Lab surveillance includes:
        # - Samples tested
        # - Positive results
        # - Pathogen identification

        data = []
        year = year or datetime.now().year
        diseases = diseases or ["Malaria_Lab", "Typhoid_Lab"]

        for disease in diseases:
            record = {
                "year": year,
                "disease": disease,
                "samples_tested": None,
                "positive_cases": None,
                "positivity_rate": None,
                "reporting_labs": None,
                "data_source": "IDSP Lab Surveillance (Form L)",
                "note": "Lab data requires IDSP portal access",
            }
            data.append(record)

        return pd.DataFrame(data)

    def search_portal(
        self,
        query: str,
        category: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Search IDSP portal for documents/reports.

        Args:
            query: Search query
            category: Document category (outbreak, guideline, report, etc.)

        Returns
        -------
            DataFrame with search results
        """
        logger.info(f"Searching IDSP portal for '{query}'")

        # Portal search would require web scraping
        # Categories: outbreak reports, guidelines, training materials, forms

        results = []
        result = {
            "title": None,
            "category": category or "All",
            "date": None,
            "url": None,
            "file_type": None,
            "note": "Portal search requires web scraping",
        }
        results.append(result)

        return pd.DataFrame(results)

    def get_state_comparison(
        self,
        disease: str,
        year: int,
        metric: str = "cases",
    ) -> pd.DataFrame:
        """
        Compare disease burden across states.

        Args:
            disease: Disease code
            year: Year
            metric: Metric to compare (cases, deaths, incidence)

        Returns
        -------
            DataFrame with state comparison
        """
        logger.info(f"Comparing {disease} across states for {year}")

        data = []
        for state_code in list(self.STATES.keys())[:10]:  # Sample
            record = {
                "state_code": state_code,
                "state_name": self.STATES[state_code],
                "year": year,
                "disease": disease,
                "cases": None,
                "deaths": None,
                "incidence_per_100k": None,
                "population": None,
                "rank": None,
                "data_source": "IDSP",
                "note": "Comparison requires data aggregation",
            }
            data.append(record)

        return pd.DataFrame(data)

    def download_weekly_report(
        self,
        year: int,
        week: int,
        output_path: Optional[str] = None,
    ) -> Optional[str]:
        """
        Download a specific weekly outbreak report PDF.

        Args:
            year: Report year
            week: Epidemiological week
            output_path: Path to save PDF (optional)

        Returns
        -------
            Path to downloaded file or None
        """
        logger.info(f"Downloading weekly report for {year} week {week}")

        # Report URLs follow a pattern on idsp.nic.in
        # e.g., https://idsp.nic.in/WriteReadData/l892s/...week{week}.pdf

        # This would require:
        # 1. Scraping the portal for report links
        # 2. Downloading the PDF
        # 3. Optionally parsing the PDF content

        logger.warning(
            "Weekly report download requires portal scraping. "
            "Visit https://idsp.nic.in/ for manual downloads."
        )
        return None

    def get_idsp_dashboard_data(
        self,
        indicator: str,
        states: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Get data from IDSP dashboard (if API available).

        Args:
            indicator: Dashboard indicator
            states: List of state codes

        Returns
        -------
            DataFrame with dashboard data
        """
        logger.info(f"Fetching dashboard data for {indicator}")

        # Some IDSP data may be available via:
        # - Internal APIs (if accessible)
        # - Data.gov.in portal
        # - CKAN API

        data = []
        record = {
            "indicator": indicator,
            "value": None,
            "date": None,
            "state": states[0] if states else "All India",
            "data_source": "IDSP Dashboard",
            "note": "Dashboard data requires API access",
        }
        data.append(record)

        return pd.DataFrame(data)
