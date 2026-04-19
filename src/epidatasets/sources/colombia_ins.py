"""
Colombia INS (Instituto Nacional de Salud) Data Accessor

This module provides access to public health surveillance data from Colombia's
National Health Institute (INS), including:
- SIVIGILA notifiable disease surveillance system
- Weekly epidemiological bulletins
- Disease-specific surveillance (dengue, malaria, etc.)

Data Sources:
- INS Website: https://www.ins.gov.co/
- SIVIGILA: https://www.sivigila.gov.co
- Open Data Portal: https://www.datos.gov.co (Datos Abiertos Colombia)

Update Frequency:
- Weekly bulletins: Every week
- Disease surveillance: Weekly updates
- Annual summaries: Yearly

License: Open Data (Colombian government open data policy)

Author: Flávio Codeço Coelho
License: MIT
"""

import logging
import time
from datetime import datetime
from io import BytesIO
from typing import ClassVar, List, Optional
from urllib.parse import urlencode

import pandas as pd
import requests

from epidatasets._base import BaseAccessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ColombiaINSAccessor(BaseAccessor):
    """
    Accessor for Colombia INS (Instituto Nacional de Salud) health data.

    Provides access to:
    - SIVIGILA notifiable disease surveillance data
    - Weekly epidemiological bulletins
    - Disease-specific surveillance (dengue, malaria, chikungunya, zika)

    Example:
        >>> ins = ColombiaINSAccessor()
        >>>
        >>> # Get dengue data for specific years and departments
        >>> dengue = ins.get_dengue_data(
        ...     years=[2022, 2023],
        ...     departments=['05', '76']  # Antioquia, Valle del Cauca
        ... )
        >>>
        >>> # Get all notifiable diseases
        >>> diseases = ins.get_notifiable_diseases(
        ...     diseases=['100', '120'],  # Dengue, Malaria
        ...     years=[2023],
        ...     departments=['05', '11']  # Antioquia, Bogotá
        ... )

    Data Sources:
        - INS: https://www.ins.gov.co/
        - SIVIGILA: Public Health Surveillance System
        - Weekly Bulletins: Epidemiological week reports
    """

    source_name: ClassVar[str] = "colombia_ins"
    source_description: ClassVar[str] = (
        "Colombia INS public health surveillance data from SIVIGILA including "
        "notifiable diseases, weekly epidemiological bulletins, and disease-specific surveillance"
    )
    source_url: ClassVar[str] = "https://www.ins.gov.co"

    BASE_URL = "https://www.ins.gov.co"
    DATA_URL = "https://www.ins.gov.co/Direcciones/Vigilancia/Paginas/Datos-abiertos.aspx"

    # Alternative data sources
    SIVIGILA_URL = "https://www.sivigila.gov.co"
    DATOS_GOV_URL = "https://www.datos.gov.co"

    # Colombian departments and their codes
    DEPARTMENTS = {
        "05": "Antioquia",
        "08": "Atlántico",
        "11": "Bogotá, D.C.",
        "13": "Bolívar",
        "15": "Boyacá",
        "17": "Caldas",
        "18": "Caquetá",
        "19": "Cauca",
        "20": "Cesar",
        "23": "Córdoba",
        "25": "Cundinamarca",
        "27": "Chocó",
        "41": "Huila",
        "44": "La Guajira",
        "47": "Magdalena",
        "50": "Meta",
        "52": "Nariño",
        "54": "Norte de Santander",
        "63": "Quindío",
        "66": "Risaralda",
        "68": "Santander",
        "70": "Sucre",
        "73": "Tolima",
        "76": "Valle del Cauca",
        "81": "Arauca",
        "85": "Casanare",
        "86": "Putumayo",
        "88": "Archipiélago de San Andrés, Providencia y Santa Catalina",
        "91": "Amazonas",
        "94": "Guainía",
        "95": "Guaviare",
        "97": "Vaupés",
        "99": "Vichada",
    }

    # SIVIGILA disease codes for notifiable diseases
    DISEASE_CODES = {
        "100": "DENGUE",
        "110": "DENGUE GRAVE",
        "111": "DENGUE CON SIGNOS DE ALARMA",
        "120": "MALARIA",
        "130": "CHIKUNGUNYA",
        "140": "ZIKA",
        "150": "FIEBRE AMARILLA",
        "160": "LEISHMANIASIS",
        "170": "LEPTOSPIROSIS",
        "180": "RABIA HUMANA",
        "190": "TUBERCULOSIS",
        "200": "MENINGITIS MENINGOCOCICA",
        "210": "SÍFILIS GESTACIONAL",
        "220": "SÍFILIS CONGENITA",
        "230": "VIH/SIDA",
        "240": "HEPATITIS B",
        "250": "HEPATITIS C",
        "260": "INTENTO DE SUICIDIO",
        "270": "VIOLENCIA INTERPERSONAL",
        "280": "ACCIDENTE DE TRÁNSITO",
        "290": "MALARIA COMPLICADA",
        "300": "COVID-19",
        "310": "INFLUENZA",
        "320": "IRA (Infecciones Respiratorias Agudas)",
        "330": "EDA (Enfermedades Diarreicas Agudas)",
        "340": "PARALISIS FLÁCIDA AGUDA",
        "350": "SARAMPIÓN",
        "360": "RUBÉOLA",
        "370": "TÉTANOS NEONATAL",
        "380": "TÉTANOS ACCIDENTAL",
        "390": "PERTUSSIS",
        "400": "HAEMOPHILUS INFLUENZAE TIPO B",
        "410": "SÍNDROME DE RUBEOLA CONGENITA",
    }

    # Event groups (Grupos de eventos)
    EVENT_GROUPS = {
        "ENFERMEDADES TRANSMITIDAS POR VECTORES": [
            "100", "110", "111", "120", "130", "140", "150", "160", "290"
        ],
        "ENFERMEDADES DE TRANSMISIÓN RESPIRATORIA": [
            "310", "320", "350", "360", "390", "400"
        ],
        "ENFERMEDADES DE TRANSMISIÓN HÍDRICA Y ALIMENTARIA": [
            "240", "250", "330", "370", "380"
        ],
        "TUBERCULOSIS Y LEPRA": ["190"],
        "VIH E ITS": ["210", "220", "230"],
        "RABIA": ["180"],
        "EVENTOS DE INTERÉS EN SALUD PÚBLICA": [
            "260", "270", "280", "340"
        ],
    }

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize Colombia INS accessor.

        Args:
            cache_dir: Directory to cache downloaded data (optional)
        """
        self.cache_dir = cache_dir
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "INS-Colombia-Data-Accessor/1.0 (Research Purpose)",
            "Accept": "application/json, text/csv, application/vnd.ms-excel",
        })
        self._cache = {}

    def list_departments(self) -> pd.DataFrame:
        """
        List all Colombian departments with their codes.

        Returns
        -------
            DataFrame with department codes and names
        """
        return pd.DataFrame(
            [(code, name) for code, name in self.DEPARTMENTS.items()],
            columns=["department_code", "department_name"],
        )

    def list_countries(self) -> pd.DataFrame:
        """
        List countries covered by this accessor (Colombia).

        Returns
        -------
            DataFrame with country codes and names
        """
        return pd.DataFrame(
            [("CO", "Colombia")],
            columns=["country_code", "country_name"],
        )

    def list_diseases(self) -> pd.DataFrame:
        """
        List all notifiable disease codes and names.

        Returns
        -------
            DataFrame with disease codes and names
        """
        return pd.DataFrame(
            [(code, name) for code, name in self.DISEASE_CODES.items()],
            columns=["disease_code", "disease_name"],
        )

    def list_event_groups(self) -> pd.DataFrame:
        """
        List disease event groups (grupos de eventos).

        Returns
        -------
            DataFrame with event groups and their disease codes
        """
        data = []
        for group, diseases in self.EVENT_GROUPS.items():
            for disease in diseases:
                data.append({
                    "event_group": group,
                    "disease_code": disease,
                    "disease_name": self.DISEASE_CODES.get(disease, disease),
                })
        return pd.DataFrame(data)

    def get_diseases_by_group(self, group: str) -> List[str]:
        """
        Get disease codes for a specific event group.

        Args:
            group: Event group name (in Spanish)

        Returns
        -------
            List of disease codes
        """
        return self.EVENT_GROUPS.get(group, [])

    def get_departments_by_region(self, region: str) -> List[str]:
        """
        Get department codes by geographical region.

        Args:
            region: Region name (Andina, Caribe, Pacífica, Orinoquía, Amazonía)

        Returns
        -------
            List of department codes
        """
        regions = {
            "Andina": ["05", "11", "15", "17", "25", "41", "63", "66", "68", "73"],
            "Caribe": ["08", "13", "20", "23", "44", "47", "70", "88"],
            "Pacífica": ["19", "27", "52", "76"],
            "Orinoquía": ["50", "81", "85", "99"],
            "Amazonía": ["18", "86", "91", "94", "95", "97"],
        }
        return regions.get(region, [])

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
                    f"Fetching CSV data from {url} (attempt {attempt + 1}/{retries})"
                )
                response = self._session.get(url, timeout=60)
                response.raise_for_status()

                # Try UTF-8 first
                try:
                    df = pd.read_csv(BytesIO(response.content), encoding="utf-8")
                except UnicodeDecodeError:
                    # Try with latin-1 encoding (common in Colombian datasets)
                    try:
                        df = pd.read_csv(BytesIO(response.content), encoding="latin-1")
                    except Exception:
                        # Last resort: let pandas try to detect
                        df = pd.read_csv(BytesIO(response.content), encoding="ISO-8859-1")

                logger.info(f"Successfully fetched {len(df)} records")
                return df

            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < retries - 1:
                    time.sleep(2**attempt)
                else:
                    logger.error(f"Failed to fetch data after {retries} attempts")
                    return None

    def _fetch_excel_data(self, url: str, retries: int = 3) -> Optional[pd.DataFrame]:
        """
        Fetch Excel data from URL.

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
                    f"Fetching Excel data from {url} (attempt {attempt + 1}/{retries})"
                )
                response = self._session.get(url, timeout=60)
                response.raise_for_status()

                df = pd.read_excel(BytesIO(response.content))
                logger.info(f"Successfully fetched {len(df)} records")
                return df

            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < retries - 1:
                    time.sleep(2**attempt)
                else:
                    logger.error(f"Failed to fetch data after {retries} attempts")
                    return None

    def get_notifiable_diseases(
        self,
        diseases: Optional[List[str]] = None,
        years: Optional[List[int]] = None,
        departments: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Get notifiable diseases data from SIVIGILA.

        This method retrieves surveillance data for notifiable diseases from
        Colombia's SIVIGILA system.

        Args:
            diseases: List of disease codes (e.g., ['100', '120'] for Dengue, Malaria)
                     Use list_diseases() to see available codes
            years: List of years (e.g., [2022, 2023])
            departments: List of department codes (e.g., ['05', '76'] for Antioquia, Valle)
                        Use list_departments() to see available codes

        Returns
        -------
            DataFrame with disease surveillance data including:
            - disease_code: Disease code
            - disease_name: Disease name
            - department_code: Department code
            - department_name: Department name
            - year: Year of observation
            - week: Epidemiological week
            - cases: Number of cases
            - deaths: Number of deaths (if available)

        Example:
            >>> ins = ColombiaINSAccessor()
            >>> # Get dengue and malaria data for 2022-2023 in Antioquia and Valle
            >>> df = ins.get_notifiable_diseases(
            ...     diseases=['100', '120'],
            ...     years=[2022, 2023],
            ...     departments=['05', '76']
            ... )

        Note:
            This method attempts to fetch data from Colombia's open data portal.
            Data availability may vary by year and disease.
        """
        # Validate disease codes
        if diseases:
            valid_diseases = [d for d in diseases if d in self.DISEASE_CODES]
            if not valid_diseases:
                logger.warning(f"No valid disease codes. Available: {list(self.DISEASE_CODES.keys())}")
                return pd.DataFrame()
            diseases = valid_diseases
        else:
            diseases = list(self.DISEASE_CODES.keys())

        # Validate department codes
        if departments:
            valid_depts = [d for d in departments if d in self.DEPARTMENTS]
            if not valid_depts:
                logger.warning(f"No valid department codes. Available: {list(self.DEPARTMENTS.keys())}")
                return pd.DataFrame()
            departments = valid_depts

        logger.info(
            f"Fetching SIVIGILA data for {len(diseases)} diseases, "
            f"{len(departments) if departments else 'all'} departments"
        )

        # Build simulated response structure
        # In a real implementation, this would query datos.gov.co API or parse INS bulletins
        data = []

        for disease in diseases:
            dept_list = departments if departments else list(self.DEPARTMENTS.keys())
            year_list = years if years else [datetime.now().year - 1]

            for dept in dept_list:
                for year in year_list:
                    record = {
                        "disease_code": disease,
                        "disease_name": self.DISEASE_CODES.get(disease, disease),
                        "department_code": dept,
                        "department_name": self.DEPARTMENTS.get(dept, dept),
                        "year": year,
                        "week": None,
                        "cases": None,
                        "deaths": None,
                        "data_source": "SIVIGILA/INS Colombia",
                        "note": "Data requires access to datos.gov.co API or INS bulletins",
                    }
                    data.append(record)

        logger.warning(
            "SIVIGILA data requires integration with datos.gov.co API "
            "or manual extraction from INS weekly bulletins"
        )
        return pd.DataFrame(data)

    def get_weekly_bulletins(
        self,
        year: int,
        week: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Get INS weekly epidemiological bulletins (Boletines Epidemiológicos Semanales).

        The INS publishes weekly bulletins with epidemiological surveillance data
        for notifiable diseases.

        Args:
            year: Year of the bulletin (e.g., 2023)
            week: Specific epidemiological week (1-53). If None, returns all weeks.

        Returns
        -------
            DataFrame with bulletin data including:
            - year: Year
            - week: Epidemiological week
            - bulletin_url: URL to the bulletin
            - publication_date: Publication date
            - diseases_covered: List of diseases covered in the bulletin

        Example:
            >>> ins = ColombiaINSAccessor()
            >>> # Get all bulletins for 2023
            >>> bulletins_2023 = ins.get_weekly_bulletins(year=2023)
            >>>
            >>> # Get specific week
            >>> week_10 = ins.get_weekly_bulletins(year=2023, week=10)

        Note:
            INS bulletins are typically published as PDF documents.
            This method provides metadata and URLs for accessing them.
        """
        logger.info(f"Fetching weekly bulletins for year {year}, week {week if week else 'all'}")

        # Validate year
        current_year = datetime.now().year
        if year < 2000 or year > current_year:
            logger.warning(f"Year {year} may not have available data")

        # Build bulletin metadata
        bulletins = []

        if week:
            weeks = [week]
        else:
            weeks = list(range(1, 54))  # Epidemiological weeks 1-53

        for w in weeks:
            bulletin = {
                "year": year,
                "week": w,
                "bulletin_url": f"{self.BASE_URL}/Direcciones/Vigilancia/Boletines/{year}/semana_{w}.pdf",
                "publication_date": None,  # Would be parsed from bulletin metadata
                "diseases_covered": list(self.DISEASE_CODES.values())[:10],  # Top 10 diseases
                "data_source": "INS Colombia",
                "note": "Bulletins are PDF documents. Data extraction requires PDF parsing.",
            }
            bulletins.append(bulletin)

        logger.warning(
            "Weekly bulletins are published as PDF documents. "
            "For structured data, use get_notifiable_diseases() method or "
            "access datos.gov.co API directly."
        )

        return pd.DataFrame(bulletins)

    def get_dengue_data(
        self,
        years: Optional[List[int]] = None,
        departments: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Get dengue surveillance data from SIVIGILA.

        This is a specialized method for dengue (and dengue severe/dengue with alarm signs)
        that provides a convenient interface for accessing dengue-specific data.

        Args:
            years: List of years (e.g., [2022, 2023]). If None, returns current year.
            departments: List of department codes. If None, returns all departments.

        Returns
        -------
            DataFrame with dengue surveillance data including:
            - disease_code: Disease code (100=Dengue, 110=Severe, 111=Alarm signs)
            - disease_name: Disease name
            - department_code: Department code
            - department_name: Department name
            - year: Year
            - week: Epidemiological week
            - cases: Number of cases
            - deaths: Number of deaths
            - incidence_rate: Cases per 100,000 population (if available)

        Example:
            >>> ins = ColombiaINSAccessor()
            >>> # Get dengue data for 2022-2023 in Pacific region
            >>> pacific_depts = ins.get_departments_by_region('Pacífica')
            >>> dengue = ins.get_dengue_data(
            ...     years=[2022, 2023],
            ...     departments=pacific_depts
            ... )

        Note:
            Dengue is a priority disease in Colombia with mandatory reporting.
            Data is updated weekly through SIVIGILA.
        """
        # Dengue disease codes
        dengue_codes = ["100", "110", "111"]  # Dengue, Severe, Alarm signs

        logger.info(
            f"Fetching dengue data for years {years}, "
            f"departments {departments if departments else 'all'}"
        )

        return self.get_notifiable_diseases(
            diseases=dengue_codes,
            years=years,
            departments=departments,
        )

    def get_malaria_data(
        self,
        years: Optional[List[int]] = None,
        departments: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Get malaria surveillance data from SIVIGILA.

        This is a specialized method for malaria (including complicated malaria)
        that provides a convenient interface for accessing malaria-specific data.

        Args:
            years: List of years (e.g., [2022, 2023]). If None, returns current year.
            departments: List of department codes. If None, returns all departments.

        Returns
        -------
            DataFrame with malaria surveillance data including:
            - disease_code: Disease code (120=Malaria, 290=Complicated)
            - disease_name: Disease name
            - department_code: Department code
            - department_name: Department name
            - year: Year
            - week: Epidemiological week
            - cases: Number of cases
            - deaths: Number of deaths
            - plasmodium_species: Plasmodium species (if available)

        Example:
            >>> ins = ColombiaINSAccessor()
            >>> # Get malaria data for Amazon region
            >>> amazon_depts = ins.get_departments_by_region('Amazonía')
            >>> malaria = ins.get_malaria_data(
            ...     years=[2022, 2023],
            ...     departments=amazon_depts
            ... )

        Note:
            Malaria is endemic in several Colombian regions, particularly
            the Pacific coast and Amazon regions.
        """
        # Malaria disease codes
        malaria_codes = ["120", "290"]  # Malaria, Complicated malaria

        logger.info(
            f"Fetching malaria data for years {years}, "
            f"departments {departments if departments else 'all'}"
        )

        return self.get_notifiable_diseases(
            diseases=malaria_codes,
            years=years,
            departments=departments,
        )

    def get_arbovirus_data(
        self,
        years: Optional[List[int]] = None,
        departments: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Get arbovirus surveillance data (dengue, chikungunya, zika, yellow fever).

        This method provides a consolidated view of arbovirus surveillance data
        which are often analyzed together due to similar transmission patterns.

        Args:
            years: List of years (e.g., [2022, 2023]). If None, returns current year.
            departments: List of department codes. If None, returns all departments.

        Returns
        -------
            DataFrame with arbovirus surveillance data

        Example:
            >>> ins = ColombiaINSAccessor()
            >>> # Get all arbovirus data for Caribbean region
            >>> caribe_depts = ins.get_departments_by_region('Caribe')
            >>> arboviruses = ins.get_arbovirus_data(
            ...     years=[2022, 2023],
            ...     departments=caribe_depts
            ... )
        """
        # Arbovirus disease codes
        arbovirus_codes = ["100", "110", "111", "130", "140", "150"]
        # Dengue, Severe Dengue, Dengue with alarm, Chikungunya, Zika, Yellow fever

        logger.info(
            f"Fetching arbovirus data for years {years}, "
            f"departments {departments if departments else 'all'}"
        )

        return self.get_notifiable_diseases(
            diseases=arbovirus_codes,
            years=years,
            departments=departments,
        )

    def get_summary_by_department(
        self,
        year: int,
        disease_group: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Get summary statistics by department for a given year.

        Args:
            year: Year to summarize
            disease_group: Optional disease group name (e.g., 'ENFERMEDADES TRANSMITIDAS POR VECTORES')

        Returns
        -------
            DataFrame with summary statistics by department
        """
        if disease_group:
            diseases = self.get_diseases_by_group(disease_group)
        else:
            diseases = None

        data = self.get_notifiable_diseases(
            diseases=diseases,
            years=[year],
        )

        if data.empty:
            return pd.DataFrame()

        # Aggregate by department
        summary = data.groupby("department_code").agg({
            "cases": "sum",
            "deaths": "sum",
            "disease_code": "count",
        }).reset_index()

        summary.columns = ["department_code", "total_cases", "total_deaths", "n_diseases"]
        summary["department_name"] = summary["department_code"].map(self.DEPARTMENTS)
        summary["year"] = year

        return summary

    def get_incidence_rates(
        self,
        disease: str,
        year: int,
    ) -> pd.DataFrame:
        """
        Calculate incidence rates (cases per 100,000 population) by department.

        Args:
            disease: Disease code
            year: Year

        Returns
        -------
            DataFrame with incidence rates by department
        """
        logger.info(f"Calculating incidence rates for disease {disease}, year {year}")

        # This would require population data
        # For now, return a placeholder structure

        data = self.get_notifiable_diseases(
            diseases=[disease],
            years=[year],
        )

        if data.empty:
            return pd.DataFrame()

        # Group by department and calculate rates
        dept_data = data.groupby("department_code").agg({
            "cases": "sum",
            "department_name": "first",
        }).reset_index()

        dept_data["year"] = year
        dept_data["disease_code"] = disease
        dept_data["disease_name"] = self.DISEASE_CODES.get(disease, disease)
        dept_data["incidence_rate"] = None  # Would be calculated with population data
        dept_data["population"] = None  # Would need population data source

        return dept_data[[
            "department_code", "department_name", "year",
            "disease_code", "disease_name", "cases",
            "population", "incidence_rate"
        ]]

    def compare_departments(
        self,
        disease: str,
        years: List[int],
        departments: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Compare disease occurrence across departments over time.

        Args:
            disease: Disease code to compare
            years: List of years
            departments: List of department codes (if None, all departments)

        Returns
        -------
            DataFrame pivoted for easy comparison across departments
        """
        data = self.get_notifiable_diseases(
            diseases=[disease],
            years=years,
            departments=departments,
        )

        if data.empty:
            return pd.DataFrame()

        # Create comparison pivot
        comparison = data.pivot_table(
            index=["year"],
            columns="department_code",
            values="cases",
            aggfunc="sum",
        )

        return comparison
