"""
CDC Open Data Accessor

Provides access to US Centers for Disease Control and Prevention (CDC) open data
including infectious disease surveillance, chronic disease indicators, and
behavioral risk factor surveillance.

Data Source: https://data.cdc.gov/
API: Socrata Open Data API (SODA)
License: Public Domain (US Government)
Update Frequency: Varies by dataset (Daily to Annual)

Author: Flávio Codeço Coelho
License: MIT
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import ClassVar, Dict, List, Optional, Union, Any
from urllib.request import urlopen
from urllib.parse import urlencode, quote
from urllib.error import HTTPError, URLError

import pandas as pd

from epidatasets._base import BaseAccessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CDCOpenDataAccessor(BaseAccessor):
    """
    Accessor for CDC Open Data Portal (data.cdc.gov).
    
    The CDC Open Data Portal provides access to surveillance data, statistics,
    and reports from the Centers for Disease Control and Prevention.
    
    Data Categories:
    - Infectious diseases (COVID-19, Influenza, HIV, Hepatitis, etc.)
    - Chronic disease indicators
    - Behavioral Risk Factor Surveillance System (BRFSS)
    - Vital statistics (births, deaths)
    - Environmental health data
    
    Example:
        >>> from scripts.accessors.cdc_opendata import CDCOpenDataAccessor
        >>> cdc = CDCOpenDataAccessor()
        >>> 
        >>> # Get COVID-19 case data
        >>> covid = cdc.get_covid_cases(state="CA", limit=1000)
        >>> 
        >>> # Get influenza surveillance data
        >>> flu = cdc.get_influenza_data(season="2023-24")
        >>> 
        >>> # Get chronic disease indicators
        >>> diabetes = cdc.get_chronic_disease_indicator("DIABETES", state="US")
    
    Data Source:
        - Portal: https://data.cdc.gov/
        - API Docs: https://dev.socrata.com/
    """

    source_name: ClassVar[str] = "cdc_opendata"
    source_description: ClassVar[str] = (
        "US CDC open data including infectious disease surveillance, chronic disease "
        "indicators, behavioral risk factor surveillance, and vital statistics"
    )
    source_url: ClassVar[str] = "https://data.cdc.gov"
    
    BASE_URL = "https://data.cdc.gov"
    API_BASE = "https://data.cdc.gov/resource"
    
    # Key CDC datasets available on data.cdc.gov
    DATASETS = {
        # COVID-19 Data
        "covid_cases_deaths": {
            "id": "9mfh-cb36",
            "name": "United States COVID-19 Cases and Deaths by State over Time",
            "description": "COVID-19 cases and deaths by state and date",
            "update_frequency": "Daily",
            "category": "infectious_disease"
        },
        "covid_vaccinations": {
            "id": "unsk-b7fc",
            "name": "COVID-19 Vaccination Data by State",
            "description": "Vaccination progress by jurisdiction",
            "update_frequency": "Daily",
            "category": "infectious_disease"
        },
        
        # Influenza Data
        "flu_surveillance": {
            "id": "gakp-6h6c",
            "name": "Influenza Laboratory-Confirmed Cases by State",
            "description": "Weekly influenza surveillance data",
            "update_frequency": "Weekly",
            "category": "infectious_disease"
        },
        "flu_hospitalizations": {
            "id": "qq4v-32f5",
            "name": "Laboratory-Confirmed Influenza Hospitalizations",
            "description": "FluSurv-NET hospitalization data",
            "update_frequency": "Weekly",
            "category": "infectious_disease"
        },
        
        # HIV/AIDS Data
        "hiv_surveillance": {
            "id": "f4p5-8m47",
            "name": "HIV Surveillance Data",
            "description": "Diagnoses by state and demographic",
            "update_frequency": "Annual",
            "category": "infectious_disease"
        },
        
        # Hepatitis Data
        "hepatitis_surveillance": {
            "id": "6i2p-7d52",
            "name": "Viral Hepatitis Surveillance",
            "description": "Hepatitis A, B, and C cases",
            "update_frequency": "Annual",
            "category": "infectious_disease"
        },
        
        # Chronic Disease Indicators
        "chronic_disease_indicators": {
            "id": "g4ie-h725",
            "name": "Chronic Disease Indicators (CDI)",
            "description": "Chronic disease prevalence by state",
            "update_frequency": "Annual",
            "category": "chronic_disease"
        },
        
        # BRFSS Data
        "brfss_prevalence": {
            "id": "acme-vg9e",
            "name": "BRFSS Prevalence Data",
            "description": "Behavioral Risk Factor Surveillance",
            "update_frequency": "Annual",
            "category": "behavioral"
        },
        
        # Mortality Data
        "mortality_underlying": {
            "id": "u95x-48mz",
            "name": "Underlying Cause of Death",
            "description": "Death counts by cause and state",
            "update_frequency": "Annual",
            "category": "mortality"
        },
        
        # Environmental Health
        "environmental_health": {
            "id": "9r6u-7kbf",
            "name": "Environmental Public Health Tracking",
            "description": "Environmental health indicators",
            "update_frequency": "Annual",
            "category": "environmental"
        },
        
        # Vaccination Coverage
        "vaccination_coverage": {
            "id": "h7pm-wmzq",
            "name": "Vaccination Coverage among Adults",
            "description": "Adult vaccination coverage by state",
            "update_frequency": "Annual",
            "category": "vaccination"
        },
        
        # STD Surveillance
        "std_surveillance": {
            "id": "i6u9-s37f",
            "name": "Sexually Transmitted Disease Surveillance",
            "description": "STD cases by state and disease",
            "update_frequency": "Annual",
            "category": "infectious_disease"
        },
        
        # TB Surveillance
        "tb_surveillance": {
            "id": "p2e6-x6c5",
            "name": "Tuberculosis Surveillance",
            "description": "TB cases by state and year",
            "update_frequency": "Annual",
            "category": "infectious_disease"
        },
        
        # NNDSS Data
        "nndss_weekly": {
            "id": "w3uq-8pd5",
            "name": "NNDSS Weekly Data",
            "description": "Notifiable diseases weekly reports",
            "update_frequency": "Weekly",
            "category": "infectious_disease"
        }
    }
    
    # US States and territories (ISO codes)
    STATES = {
        "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
        "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
        "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
        "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
        "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
        "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
        "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
        "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
        "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
        "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
        "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
        "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
        "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
        "PR": "Puerto Rico", "VI": "Virgin Islands", "GU": "Guam",
        "AS": "American Samoa", "MP": "Northern Mariana Islands", "US": "United States"
    }
    
    # Common notifiable diseases in NNDSS
    NOTIFIABLE_DISEASES = [
        "Anthrax", "Botulism", "Brucellosis", "Campylobacteriosis", "Cholera",
        "Coccidioidomycosis", "Cryptosporidiosis", "Cyclosporiasis", "Dengue",
        "Diphtheria", "Ehrlichiosis", "Giardiasis", "Gonorrhea", "Hansen disease",
        "Hantavirus", "Hemolytic uremic syndrome", "Hepatitis A", "Hepatitis B",
        "Hepatitis C", "HIV", "Influenza", "Legionellosis", "Leptospirosis",
        "Listeriosis", "Lyme disease", "Malaria", "Measles", "Meningococcal",
        "Mumps", "Novel Influenza A", "Pertussis", "Plague", "Psittacosis",
        "Q fever", "Rabies", "Rubella", "Salmonellosis", "Severe Acute Respiratory Syndrome",
        "Shigellosis", "Smallpox", "Spotted fever rickettsiosis", "Streptococcal toxic shock",
        "Syphilis", "Tetanus", "Toxic shock syndrome", "Trichinellosis", "Tuberculosis",
        "Tularemia", "Typhoid fever", "Vancomycin-intermediate Staphylococcus aureus",
        "Varicella", "Vibriosis", "Viral hemorrhagic fever", "West Nile virus",
        "Yellow fever", "Zika"
    ]
    
    def __init__(self, app_token: Optional[str] = None, cache_dir: Optional[str] = None):
        """
        Initialize CDC Open Data accessor.
        
        Args:
            app_token: Socrata app token for higher rate limits (optional)
            cache_dir: Directory to cache downloaded data
        """
        self.app_token = app_token
        self.cache_dir = Path(cache_dir) if cache_dir else Path.home() / ".cache" / "epi_data" / "cdc"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_ttl = timedelta(hours=6)
        
    def _get_cached_path(self, dataset_id: str, query_hash: str = "") -> Path:
        """Get cache file path for a dataset query."""
        cache_name = f"{dataset_id}_{query_hash}" if query_hash else dataset_id
        return self.cache_dir / f"{cache_name}.csv"
    
    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cache file is still valid."""
        if not cache_path.exists():
            return False
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        return datetime.now() - mtime < self._cache_ttl
    
    def _build_url(self, dataset_id: str, query_params: Optional[Dict] = None) -> str:
        """Build SODA API URL with optional query parameters."""
        url = f"{self.API_BASE}/{dataset_id}.json"
        
        if query_params:
            # Socrata uses SoQL query language
            soql_params = {}
            
            if "$limit" in query_params:
                soql_params["$limit"] = query_params["$limit"]
            if "$offset" in query_params:
                soql_params["$offset"] = query_params["$offset"]
            if "$order" in query_params:
                soql_params["$order"] = query_params["$order"]
            if "$where" in query_params:
                soql_params["$where"] = query_params["$where"]
            if "$select" in query_params:
                soql_params["$select"] = query_params["$select"]
            if "$group" in query_params:
                soql_params["$group"] = query_params["$group"]
            
            if soql_params:
                url += "?" + urlencode(soql_params, safe="=<>!&'")
        
        return url
    
    def _fetch_data(self, url: str, use_cache: bool = True, cache_path: Optional[Path] = None) -> pd.DataFrame:
        """Fetch data from CDC API with optional caching."""
        # Check cache first
        if use_cache and cache_path and self._is_cache_valid(cache_path):
            logger.info(f"Loading cached data from {cache_path}")
            return pd.read_csv(cache_path)
        
        # Prepare headers
        headers = {}
        if self.app_token:
            headers["X-App-Token"] = self.app_token
        
        logger.info(f"Fetching data from: {url}")
        
        try:
            request = urlopen(url, timeout=60)
            data = json.loads(request.read().decode())
            
            if not data:
                return pd.DataFrame()
            
            df = pd.DataFrame(data)
            
            # Save to cache
            if use_cache and cache_path:
                df.to_csv(cache_path, index=False)
            
            return df
            
        except HTTPError as e:
            logger.error(f"HTTP Error {e.code}: {e.reason}")
            raise
        except URLError as e:
            logger.error(f"URL Error: {e.reason}")
            raise
        except Exception as e:
            logger.error(f"Error fetching data: {e}")
            raise
    
    def get_available_datasets(self, category: Optional[str] = None) -> pd.DataFrame:
        """
        Get list of available CDC datasets.
        
        Args:
            category: Filter by category ("infectious_disease", "chronic_disease", etc.)
        
        Returns:
            DataFrame with dataset information
        """
        datasets = []
        for key, info in self.DATASETS.items():
            if category is None or info.get("category") == category:
                datasets.append({
                    "dataset_key": key,
                    "dataset_id": info["id"],
                    "name": info["name"],
                    "description": info["description"],
                    "update_frequency": info["update_frequency"],
                    "category": info.get("category", "unknown")
                })
        
        return pd.DataFrame(datasets)
    
    def get_covid_cases(
        self,
        state: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 10000,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Get COVID-19 cases and deaths by state.
        
        Args:
            state: Two-letter state code (e.g., "CA", "NY")
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            limit: Maximum number of records to return
            use_cache: Whether to use cached data
        
        Returns:
            DataFrame with COVID-19 data
        """
        dataset_id = self.DATASETS["covid_cases_deaths"]["id"]
        
        # Build where clause
        where_conditions = []
        if state:
            state = state.upper()
            where_conditions.append(f"state='{state}'")
        if start_date:
            where_conditions.append(f"submission_date>='{start_date}'")
        if end_date:
            where_conditions.append(f"submission_date<='{end_date}'")
        
        query_params = {
            "$limit": limit,
            "$order": "submission_date DESC"
        }
        if where_conditions:
            query_params["$where"] = " AND ".join(where_conditions)
        
        url = self._build_url(dataset_id, query_params)
        cache_path = self._get_cached_path(f"{dataset_id}_{state or 'all'}")
        
        df = self._fetch_data(url, use_cache=use_cache, cache_path=cache_path)
        
        # Convert numeric columns
        numeric_cols = [
            "tot_cases", "conf_cases", "prob_cases", "new_case",
            "pnew_case", "tot_death", "conf_death", "prob_death", 
            "new_death", "pnew_death", "created_at"
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Convert date column
        if 'submission_date' in df.columns:
            df['submission_date'] = pd.to_datetime(df['submission_date'])
        
        return df
    
    def get_influenza_data(
        self,
        state: Optional[str] = None,
        season: Optional[str] = None,
        limit: int = 5000,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Get influenza laboratory-confirmed cases by state.
        
        Args:
            state: Two-letter state code
            season: Influenza season (e.g., "2023-24")
            limit: Maximum number of records
            use_cache: Whether to use cached data
        
        Returns:
            DataFrame with influenza surveillance data
        """
        dataset_id = self.DATASETS["flu_surveillance"]["id"]
        
        where_conditions = []
        if state:
            state = state.upper()
            where_conditions.append(f"statename='{self.STATES.get(state, state)}'")
        if season:
            where_conditions.append(f"season='{season}'")
        
        query_params = {
            "$limit": limit,
            "$order": "weekendingdate DESC"
        }
        if where_conditions:
            query_params["$where"] = " AND ".join(where_conditions)
        
        url = self._build_url(dataset_id, query_params)
        cache_path = self._get_cached_path(f"flu_{state or 'all'}_{season or 'all'}")
        
        df = self._fetch_data(url, use_cache=use_cache, cache_path=cache_path)
        
        # Convert date column
        if 'weekendingdate' in df.columns:
            df['weekendingdate'] = pd.to_datetime(df['weekendingdate'])
        
        return df
    
    def get_chronic_disease_indicator(
        self,
        indicator: str,
        state: Optional[str] = None,
        year: Optional[int] = None,
        stratification: Optional[str] = None,
        limit: int = 10000,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Get Chronic Disease Indicators (CDI) data.
        
        Args:
            indicator: Indicator abbreviation (e.g., "DIABETES", "OBESITY")
            state: Two-letter state code or "US" for national
            year: Data year
            stratification: Demographic stratification (e.g., "RACE", "GENDER")
            limit: Maximum number of records
            use_cache: Whether to use cached data
        
        Returns:
            DataFrame with CDI data
        """
        dataset_id = self.DATASETS["chronic_disease_indicators"]["id"]
        
        where_conditions = [f"indicatorabbr='{indicator.upper()}'"]
        
        if state:
            if state.upper() == "US":
                where_conditions.append("locationabbr='US'")
            else:
                where_conditions.append(f"locationabbr='{state.upper()}'")
        if year:
            where_conditions.append(f"yearstart={year}")
        if stratification:
            where_conditions.append(f"stratificationcategory1='{stratification}'")
        
        query_params = {
            "$limit": limit,
            "$order": "yearstart DESC",
            "$where": " AND ".join(where_conditions)
        }
        
        url = self._build_url(dataset_id, query_params)
        cache_key = f"cdi_{indicator}_{state or 'all'}_{year or 'all'}"
        cache_path = self._get_cached_path(cache_key)
        
        return self._fetch_data(url, use_cache=use_cache, cache_path=cache_path)
    
    def get_nndss_data(
        self,
        disease: Optional[str] = None,
        state: Optional[str] = None,
        year: Optional[int] = None,
        mmwr_week: Optional[int] = None,
        limit: int = 5000,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Get NNDSS (National Notifiable Diseases Surveillance System) data.
        
        Args:
            disease: Disease name from NOTIFIABLE_DISEASES list
            state: Two-letter state code
            year: MMWR year
            mmwr_week: MMWR week number (1-53)
            limit: Maximum number of records
            use_cache: Whether to use cached data
        
        Returns:
            DataFrame with NNDSS data
        """
        dataset_id = self.DATASETS["nndss_weekly"]["id"]
        
        where_conditions = []
        if disease:
            where_conditions.append(f"disease='{disease}'")
        if state:
            where_conditions.append(f"state='{state.upper()}'")
        if year:
            where_conditions.append(f"mmwryear={year}")
        if mmwr_week:
            where_conditions.append(f"mmwrweek={mmwr_week}")
        
        query_params = {
            "$limit": limit,
            "$order": "mmwryear DESC, mmwrweek DESC"
        }
        if where_conditions:
            query_params["$where"] = " AND ".join(where_conditions)
        
        url = self._build_url(dataset_id, query_params)
        cache_key = f"nndss_{disease or 'all'}_{state or 'all'}_{year or 'all'}"
        cache_path = self._get_cached_path(cache_key)
        
        return self._fetch_data(url, use_cache=use_cache, cache_path=cache_path)
    
    def get_hiv_data(
        self,
        state: Optional[str] = None,
        year: Optional[int] = None,
        limit: int = 5000,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Get HIV surveillance data.
        
        Args:
            state: Two-letter state code
            year: Data year
            limit: Maximum number of records
            use_cache: Whether to use cached data
        
        Returns:
            DataFrame with HIV surveillance data
        """
        dataset_id = self.DATASETS["hiv_surveillance"]["id"]
        
        where_conditions = []
        if state:
            where_conditions.append(f"geography='{self.STATES.get(state.upper(), state)}'")
        if year:
            where_conditions.append(f"year={year}")
        
        query_params = {
            "$limit": limit,
            "$order": "year DESC"
        }
        if where_conditions:
            query_params["$where"] = " AND ".join(where_conditions)
        
        url = self._build_url(dataset_id, query_params)
        cache_path = self._get_cached_path(f"hiv_{state or 'all'}_{year or 'all'}")
        
        return self._fetch_data(url, use_cache=use_cache, cache_path=cache_path)
    
    def get_dataset_info(self, dataset_key: str) -> Dict[str, Any]:
        """
        Get information about a specific dataset.
        
        Args:
            dataset_key: Key from DATASETS dictionary
        
        Returns:
            Dictionary with dataset information
        """
        if dataset_key not in self.DATASETS:
            available = list(self.DATASETS.keys())
            raise ValueError(f"Unknown dataset: {dataset_key}. Available: {available}")
        
        return self.DATASETS[dataset_key].copy()
    
    def list_notifiable_diseases(self) -> List[str]:
        """
        Get list of notifiable diseases available in NNDSS.
        
        Returns:
            List of disease names
        """
        return self.NOTIFIABLE_DISEASES.copy()

    def list_countries(self) -> pd.DataFrame:
        """
        List US states and territories as the country-level breakdown.

        Returns:
            DataFrame with state codes and names
        """
        return pd.DataFrame(
            [(code, name) for code, name in self.STATES.items()],
            columns=["state_code", "state_name"],
        )


# Convenience functions
def get_cdc_datasets(category: Optional[str] = None) -> pd.DataFrame:
    """Get list of available CDC datasets."""
    accessor = CDCOpenDataAccessor()
    return accessor.get_available_datasets(category=category)


def get_cdc_covid(
    state: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 10000
) -> pd.DataFrame:
    """
    Convenience function to get COVID-19 data from CDC.
    
    Args:
        state: Two-letter state code
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        limit: Maximum records
    
    Returns:
        DataFrame with COVID-19 data
    """
    accessor = CDCOpenDataAccessor()
    return accessor.get_covid_cases(
        state=state,
        start_date=start_date,
        end_date=end_date,
        limit=limit
    )


def get_cdc_influenza(
    state: Optional[str] = None,
    season: Optional[str] = None,
    limit: int = 5000
) -> pd.DataFrame:
    """
    Convenience function to get influenza data from CDC.
    
    Args:
        state: Two-letter state code
        season: Influenza season (e.g., "2023-24")
        limit: Maximum records
    
    Returns:
        DataFrame with influenza data
    """
    accessor = CDCOpenDataAccessor()
    return accessor.get_influenza_data(
        state=state,
        season=season,
        limit=limit
    )
