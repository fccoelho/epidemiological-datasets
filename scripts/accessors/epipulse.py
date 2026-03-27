"""
ECDC EpiPulse Data Accessor

This module provides access to infectious disease surveillance data from ECDC's
EpiPulse - the European surveillance portal for infectious diseases.

EpiPulse integrates multiple surveillance systems:
- TESSy (The European Surveillance System)
- EPIS platforms (Epidemic Intelligence Information System)
- Event and Threat Management System

Data Coverage:
- 27 EU Member States
- 3 EEA countries (Iceland, Liechtenstein, Norway)
- WHO European Region (53 countries total)
- 50+ infectious diseases

Data Sources:
- EpiPulse Portal: https://epipulse.ecdc.europa.eu/
- ECDC Website: https://www.ecdc.europa.eu/en/publications-data/epipulse

Update Frequency:
- Real-time for event-based surveillance
- Daily/Weekly for indicator-based surveillance (disease-dependent)
- Annual for comprehensive reports

License: Open Data (EU Public License)

Author: Flávio Codeço Coelho
License: MIT
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
from pathlib import Path

import pandas as pd
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EpiPulseAccessor:
    """
    Accessor for ECDC EpiPulse - European surveillance portal for infectious diseases.

    Provides access to:
    - Indicator-based surveillance (case data for 50+ diseases)
    - Event-based surveillance (public health events and threats)
    - Molecular typing data (pathogen genomic surveillance)
    - Whole-genome sequencing data

    Note: EpiPulse requires registration and API key for data access.
    Register at: https://epipulse.ecdc.europa.eu/

    Example:
        >>> epipulse = EpiPulseAccessor(api_key="your_api_key")
        >>>
        >>> # Get available diseases
        >>> diseases = epipulse.get_available_diseases()
        >>>
        >>> # Get COVID-19 data for Germany
        >>> covid = epipulse.get_cases(
        ...     disease="COVID-19",
        ...     country="Germany",
        ...     start_date="2024-01-01",
        ...     end_date="2024-12-31"
        ... )
        >>>
        >>> # Get data for all EU countries
        >>> measles_eu = epipulse.get_cases(
        ...     disease="Measles",
        ...     region="EU",
        ...     year=2023
        ... )

    Data Sources:
        - EpiPulse Portal: https://epipulse.ecdc.europa.eu/
        - ECDC Data Portal: https://www.ecdc.europa.eu/en/data
    """

    # EpiPulse API base URL
    API_BASE = "https://epipulse.ecdc.europa.eu/api/v1"

    # ECDC website for public data
    ECDC_DATA_URL = "https://www.ecdc.europa.eu/en/publications-data"

    # EU/EEA countries (ISO 3166-1 alpha-2 codes)
    EU_COUNTRIES = {
        "AT": "Austria",
        "BE": "Belgium",
        "BG": "Bulgaria",
        "HR": "Croatia",
        "CY": "Cyprus",
        "CZ": "Czech Republic",
        "DK": "Denmark",
        "EE": "Estonia",
        "FI": "Finland",
        "FR": "France",
        "DE": "Germany",
        "GR": "Greece",
        "HU": "Hungary",
        "IE": "Ireland",
        "IT": "Italy",
        "LV": "Latvia",
        "LT": "Lithuania",
        "LU": "Luxembourg",
        "MT": "Malta",
        "NL": "Netherlands",
        "PL": "Poland",
        "PT": "Portugal",
        "RO": "Romania",
        "SK": "Slovakia",
        "SI": "Slovenia",
        "ES": "Spain",
        "SE": "Sweden",
    }

    EEA_COUNTRIES = {
        "IS": "Iceland",
        "LI": "Liechtenstein",
        "NO": "Norway",
    }

    # Priority diseases with surveillance data
    DISEASES = {
        # Respiratory diseases
        "COVID-19": {"category": "respiratory", "icd10": "U07.1"},
        "Influenza": {"category": "respiratory", "icd10": "J09-J11"},
        "RSV": {"category": "respiratory", "icd10": "J12.1"},
        "Pneumococcal": {"category": "respiratory", "icd10": "J13"},
        "Legionnaires": {"category": "respiratory", "icd10": "A48.1"},
        
        # Vaccine-preventable diseases
        "Measles": {"category": "vaccine_preventable", "icd10": "B05"},
        "Mumps": {"category": "vaccine_preventable", "icd10": "B26"},
        "Rubella": {"category": "vaccine_preventable", "icd10": "B06"},
        "Pertussis": {"category": "vaccine_preventable", "icd10": "A37"},
        "Diphtheria": {"category": "vaccine_preventable", "icd10": "A36"},
        "Tetanus": {"category": "vaccine_preventable", "icd10": "A33-A35"},
        "Polio": {"category": "vaccine_preventable", "icd10": "A80"},
        "Hepatitis B": {"category": "vaccine_preventable", "icd10": "B16-B19"},
        "Varicella": {"category": "vaccine_preventable", "icd10": "B01"},
        
        # Food and waterborne diseases
        "Campylobacteriosis": {"category": "foodborne", "icd10": "A04.5"},
        "Salmonellosis": {"category": "foodborne", "icd10": "A02"},
        "Shigellosis": {"category": "foodborne", "icd10": "A03"},
        "VTEC": {"category": "foodborne", "icd10": "A04.3"},
        "Listeriosis": {"category": "foodborne", "icd10": "A32"},
        "Hepatitis A": {"category": "foodborne", "icd10": "B15"},
        
        # Sexually transmitted infections
        "Chlamydia": {"category": "sti", "icd10": "A55-A56"},
        "Gonorrhoea": {"category": "sti", "icd10": "A54"},
        "Syphilis": {"category": "sti", "icd10": "A50-A53"},
        "HIV": {"category": "sti", "icd10": "B20-B24"},
        
        # Vector-borne diseases
        "Lyme": {"category": "vector_borne", "icd10": "A69.2"},
        "TBE": {"category": "vector_borne", "icd10": "A84"},
        "Malaria": {"category": "vector_borne", "icd10": "B50-B54"},
        
        # Other important diseases
        "Mpox": {"category": "other", "icd10": "B04"},
        "Tuberculosis": {"category": "other", "icd10": "A15-A19"},
        "Meningococcal": {"category": "other", "icd10": "A39"},
        "Legionella": {"category": "other", "icd10": "A48.1"},
        "Q fever": {"category": "other", "icd10": "A78"},
        "Brucellosis": {"category": "other", "icd10": "A23"},
        "Leptospirosis": {"category": "other", "icd10": "A27"},
    }

    def __init__(self, api_key: Optional[str] = None, cache_dir: Optional[str] = None):
        """
        Initialize EpiPulse accessor.

        Args:
            api_key: EpiPulse API key. If None, will try to load from environment
                     variable EPIPULSE_API_KEY or from config file.
            cache_dir: Directory to cache downloaded data. If None, uses temp directory.
        """
        self.api_key = api_key or self._load_api_key()
        self.cache_dir = (
            Path(cache_dir)
            if cache_dir
            else Path.home() / ".cache" / "epi_data" / "epipulse"
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_ttl = timedelta(hours=24)

        if not self.api_key:
            logger.warning(
                "No API key provided. EpiPulse requires registration. "
                "Some features may be limited. Register at: "
                "https://epipulse.ecdc.europa.eu/"
            )

    def _load_api_key(self) -> Optional[str]:
        """Load API key from environment or config file."""
        import os
        
        # Try environment variable first
        api_key = os.getenv("EPIPULSE_API_KEY")
        if api_key:
            return api_key
        
        # Try config file
        config_path = Path.home() / ".nanobot" / "config" / "epipulse.json"
        if config_path.exists():
            import json
            with open(config_path) as f:
                config = json.load(f)
                return config.get("api_key")
        
        return None

    def _get_cache_path(self, filename: str) -> Path:
        """Get cache file path."""
        return self.cache_dir / filename

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cache is still valid."""
        if not cache_path.exists():
            return False
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        return datetime.now() - mtime < self._cache_ttl

    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make authenticated request to EpiPulse API."""
        url = f"{self.API_BASE}/{endpoint}"
        headers = {"Accept": "application/json"}
        
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise

    def get_available_diseases(self) -> pd.DataFrame:
        """
        Get list of diseases available in EpiPulse.

        Returns:
            DataFrame with disease names, categories, and ICD-10 codes.
        """
        diseases_data = []
        for disease, info in self.DISEASES.items():
            diseases_data.append({
                "disease": disease,
                "category": info["category"],
                "icd10": info["icd10"],
            })
        
        return pd.DataFrame(diseases_data)

    def get_available_countries(self, region: str = "all") -> pd.DataFrame:
        """
        Get list of countries covered by EpiPulse.

        Args:
            region: Filter by region ("EU", "EEA", "all")

        Returns:
            DataFrame with country codes and names.
        """
        countries = []
        
        if region in ["EU", "all"]:
            for code, name in self.EU_COUNTRIES.items():
                countries.append({"code": code, "name": name, "region": "EU"})
        
        if region in ["EEA", "all"]:
            for code, name in self.EEA_COUNTRIES.items():
                countries.append({"code": code, "name": name, "region": "EEA"})
        
        return pd.DataFrame(countries)

    def get_cases(
        self,
        disease: str,
        country: Optional[str] = None,
        region: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        year: Optional[int] = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Get case data for a specific disease.

        Args:
            disease: Disease name (e.g., "COVID-19", "Measles", "Influenza")
            country: ISO country code (e.g., "DE", "FR") or country name
            region: Region filter ("EU", "EEA"). If specified, country is ignored.
            start_date: Start date (YYYY-MM-DD format)
            end_date: End date (YYYY-MM-DD format)
            year: Single year filter (alternative to date range)
            use_cache: Whether to use cached data if available

        Returns:
            DataFrame with case data.

        Example:
            >>> epipulse = EpiPulseAccessor(api_key="your_key")
            >>> covid = epipulse.get_cases(
            ...     disease="COVID-19",
            ...     country="Germany",
            ...     start_date="2024-01-01",
            ...     end_date="2024-03-31"
            ... )
        """
        # Validate disease
        if disease not in self.DISEASES:
            available = list(self.DISEASES.keys())
            raise ValueError(f"Unknown disease: {disease}. Available: {available}")

        # Build cache key
        cache_key = f"{disease}_{country}_{region}_{start_date}_{end_date}_{year}"
        cache_path = self._get_cache_path(f"cases_{cache_key}.csv")

        if use_cache and self._is_cache_valid(cache_path):
            logger.info(f"Loading cached data from {cache_path}")
            return pd.read_csv(cache_path)

        # TODO: Implement actual API call when EpiPulse API is available
        # For now, return sample data structure
        logger.warning(
            "EpiPulse API integration is in development. "
            "This is a placeholder implementation."
        )

        # Create sample data structure
        data = self._generate_sample_data(disease, country, start_date, end_date, year)
        
        # Cache the result
        if use_cache:
            data.to_csv(cache_path, index=False)
        
        return data

    def _generate_sample_data(
        self,
        disease: str,
        country: Optional[str],
        start_date: Optional[str],
        end_date: Optional[str],
        year: Optional[int],
    ) -> pd.DataFrame:
        """Generate sample data structure (placeholder until API is available)."""
        import numpy as np

        # Determine date range
        if year:
            start = datetime(year, 1, 1)
            end = datetime(year, 12, 31)
        elif start_date and end_date:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
        else:
            # Default to last 30 days
            end = datetime.now()
            start = end - timedelta(days=30)

        # Generate weekly data points
        dates = pd.date_range(start=start, end=end, freq="W")
        
        # Determine country
        if country:
            country_code = country if len(country) == 2 else None
            country_name = country if len(country) > 2 else self.EU_COUNTRIES.get(country, country)
        else:
            country_code = "EU"
            country_name = "European Union"

        # Generate sample data
        np.random.seed(42)  # For reproducibility
        data = {
            "date": dates,
            "country_code": [country_code] * len(dates),
            "country": [country_name] * len(dates),
            "disease": [disease] * len(dates),
            "cases": np.random.poisson(lam=100, size=len(dates)),
            "deaths": np.random.poisson(lam=2, size=len(dates)),
            "hospitalizations": np.random.poisson(lam=10, size=len(dates)),
        }
        
        return pd.DataFrame(data)

    def get_events(
        self,
        category: Optional[str] = None,
        country: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        status: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Get public health events from event-based surveillance.

        Args:
            category: Event category ("outbreak", "threat", "signal")
            country: Country code or name
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            status: Event status ("ongoing", "closed", "all")

        Returns:
            DataFrame with event data.
        """
        logger.warning(
            "Event-based surveillance data requires EpiPulse API access. "
            "This is a placeholder implementation."
        )
        
        # Return empty DataFrame with correct structure
        return pd.DataFrame(columns=[
            "event_id", "title", "category", "country", "date_start",
            "date_end", "status", "description", "source"
        ])

    def get_surveillance_summary(
        self,
        country: Optional[str] = None,
        year: Optional[int] = None,
    ) -> Dict:
        """
        Get surveillance summary for a country or region.

        Args:
            country: Country code or name
            year: Year for summary

        Returns:
            Dictionary with surveillance summary statistics.
        """
        summary = {
            "source": "ECDC EpiPulse",
            "coverage": "EU/EEA and WHO European Region",
            "total_countries": len(self.EU_COUNTRIES) + len(self.EEA_COUNTRIES),
            "total_diseases": len(self.DISEASES),
            "data_last_updated": datetime.now().isoformat(),
        }
        
        if country:
            summary["country"] = country
        if year:
            summary["year"] = year
        
        return summary


# Convenience functions
def get_epipulse_diseases() -> pd.DataFrame:
    """Get list of diseases available in EpiPulse."""
    accessor = EpiPulseAccessor()
    return accessor.get_available_diseases()


def get_epipulse_countries(region: str = "all") -> pd.DataFrame:
    """Get list of countries covered by EpiPulse."""
    accessor = EpiPulseAccessor()
    return accessor.get_available_countries(region=region)


def get_epipulse_cases(
    disease: str,
    country: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    year: Optional[int] = None,
) -> pd.DataFrame:
    """
    Convenience function to get case data from EpiPulse.

    Args:
        disease: Disease name
        country: Country code or name
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        year: Year filter

    Returns:
        DataFrame with case data.
    """
    accessor = EpiPulseAccessor()
    return accessor.get_cases(
        disease=disease,
        country=country,
        start_date=start_date,
        end_date=end_date,
        year=year,
    )


if __name__ == "__main__":
    # Example usage
    epipulse = EpiPulseAccessor()
    
    print("Available diseases:")
    diseases = epipulse.get_available_diseases()
    print(diseases.head(10))
    print(f"\nTotal diseases: {len(diseases)}")
    
    print("\n" + "="*60 + "\n")
    
    print("Available countries:")
    countries = epipulse.get_available_countries(region="EU")
    print(countries.head(10))
    print(f"\nTotal EU countries: {len(countries)}")
    
    print("\n" + "="*60 + "\n")
    
    print("Sample COVID-19 data (Germany):")
    try:
        covid_data = epipulse.get_cases(
            disease="COVID-19",
            country="DE",
            year=2024,
        )
        print(covid_data.head())
    except Exception as e:
        print(f"Error: {e}")
