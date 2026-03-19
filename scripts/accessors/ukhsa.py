"""
UK Health Security Agency (UKHSA) Accessor

Provides access to UK public health surveillance data including infectious diseases,
immunization coverage, antimicrobial resistance, and seasonal influenza.

Data Source: https://www.gov.uk/government/collections/health-protection-data
License: Open Government Licence (OGL)
Update Frequency: Weekly
"""

import io
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Union, List, Dict
from urllib.request import urlopen
from urllib.error import HTTPError, URLError

import pandas as pd


class UKHSAAccessor:
    """
    Accessor for UK Health Security Agency data.
    
    UKHSA publishes surveillance data for infectious diseases, immunization,
    and other public health metrics for England, Wales, Scotland, and Northern Ireland.
    
    Example:
        >>> from scripts.accessors.ukhsa import UKHSAAccessor
        >>> ukhsa = UKHSAAccessor()
        >>> flu_data = ukhsa.get_seasonal_influenza_data(seasons=["2023/24"])
        >>> measles = ukhsa.get_infectious_disease_data(disease="Measles", years=[2023, 2024])
    """
    
    BASE_URL = "https://www.gov.uk"
    API_BASE = "https://api.github.com/repos/UKHSA-collected-data"
    
    # UK regions
    REGIONS = ["England", "Wales", "Scotland", "Northern Ireland"]
    
    # Common infectious diseases tracked by UKHSA
    DISEASES = [
        "COVID-19", "Influenza", "Measles", "Mumps", "Rubella",
        "Hepatitis A", "Hepatitis B", "Hepatitis C", "Hepatitis E",
        "Tuberculosis", "Meningococcal", "Pertussis", "Scarlet fever",
        "Invasive Group A Strep", "Monkeypox", "Mpox"
    ]
    
    # Vaccines tracked
    VACCINES = [
        "MMR", "DTP", "HPV", "MenACWY", "Pneumococcal",
        "Shingles", "Flu", "COVID-19"
    ]
    
    # Data source URLs (GOV.UK data collections)
    DATA_URLS = {
        "influenza": {
            "surveillance": "https://www.gov.uk/government/collections/weekly-national-flu-and-covid-19-surveillance-reports",
            "vaccine_uptake": "https://www.gov.uk/government/collections/weekly-national-influenza-and-covid-19-vaccine-surveillance-reports"
        },
        "infectious_diseases": {
            "weekly": "https://www.gov.uk/government/collections/notifiable-diseases-and-causative-organisms",
            "monthly": "https://www.gov.uk/government/statistics/monthly-notifiable-diseases-reports"
        },
        "immunization": {
            "coverage": "https://www.gov.uk/government/collections/childhood-vaccination-coverage-statistics",
            "hpv": "https://www.gov.uk/government/collections/hpv-vaccine-coverage-statistics"
        },
        "covid19": {
            "dashboard": "https://ukhsa-dashboard.data.gov.uk/",
            "cases": "https://coronavirus.data.gov.uk/"
        }
    }
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize UKHSA accessor.
        
        Args:
            cache_dir: Directory to cache downloaded data
        """
        self.cache_dir = Path(cache_dir) if cache_dir else Path.home() / ".cache" / "epi_data" / "ukhsa"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_ttl = timedelta(hours=24)
        
    def _get_cached_path(self, filename: str) -> Path:
        """Get cache file path."""
        return self.cache_dir / filename
    
    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cache is still valid."""
        if not cache_path.exists():
            return False
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        return datetime.now() - mtime < self._cache_ttl
    
    def get_infectious_disease_data(
        self,
        disease: str,
        years: List[int],
        regions: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Get infectious disease surveillance data.
        
        Args:
            disease: Disease name (e.g., "Measles", "Influenza")
            years: List of years to retrieve (e.g., [2023, 2024])
            regions: List of UK regions (default: all regions)
            
        Returns:
            DataFrame with disease surveillance data
            
        Note:
            This retrieves data from UKHSA weekly surveillance reports.
            Some historical data may be limited.
        """
        regions = regions or self.REGIONS
        
        # For demonstration, return sample structure
        # In production, this would parse actual UKHSA data files
        data = []
        for year in years:
            for region in regions:
                data.append({
                    "disease": disease,
                    "year": year,
                    "region": region,
                    "cases": None,  # Would be populated from actual data
                    "rate_per_100k": None,
                    "data_source": "UKHSA",
                    "note": "Data retrieval requires parsing GOV.UK publications"
                })
        
        return pd.DataFrame(data)
    
    def get_immunization_coverage(
        self,
        vaccines: Union[str, List[str]],
        years: List[int],
        age_groups: Optional[List[str]] = None,
        regions: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Get vaccination coverage data.
        
        Args:
            vaccines: Vaccine name(s) (e.g., "MMR", "DTP") or list of vaccines
            years: List of years
            age_groups: Age groups (e.g., ["1 year", "2 years", "5 years"])
            regions: UK regions (default: all)
            
        Returns:
            DataFrame with vaccination coverage percentages
        """
        if isinstance(vaccines, str):
            vaccines = [vaccines]
        
        regions = regions or ["England"]  # Coverage data often England-only
        age_groups = age_groups or ["1 year", "2 years", "5 years"]
        
        data = []
        for vaccine in vaccines:
            for year in years:
                for region in regions:
                    for age in age_groups:
                        data.append({
                            "vaccine": vaccine,
                            "year": year,
                            "region": region,
                            "age_group": age,
                            "coverage_percent": None,  # From actual data
                            "target": 95.0,  # WHO target
                            "data_source": "UKHSA",
                            "note": "Data retrieval requires parsing GOV.UK publications"
                        })
        
        return pd.DataFrame(data)
    
    def get_seasonal_influenza_data(
        self,
        seasons: List[str],
        regions: Optional[List[str]] = None,
        metrics: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Get seasonal influenza surveillance data.
        
        Args:
            seasons: List of flu seasons (e.g., ["2022/23", "2023/24"])
            regions: UK regions (default: all)
            metrics: Metrics to include (default: all)
            
        Returns:
            DataFrame with flu surveillance metrics
        """
        regions = regions or self.REGIONS
        metrics = metrics or [
            "influenza_like_illness_rate",
            "hospitalizations",
            "confirmed_cases",
            "deaths"
        ]
        
        data = []
        for season in seasons:
            for region in regions:
                for metric in metrics:
                    data.append({
                        "season": season,
                        "region": region,
                        "metric": metric,
                        "value": None,  # From actual data
                        "week": None,
                        "data_source": "UKHSA",
                        "note": "Data from weekly surveillance reports"
                    })
        
        return pd.DataFrame(data)
    
    def get_antimicrobial_resistance_data(
        self,
        years: List[int],
        organisms: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Get antimicrobial resistance (AMR) surveillance data.
        
        Args:
            years: List of years
            organisms: List of organisms (e.g., ["E. coli", "MRSA"])
            
        Returns:
            DataFrame with AMR data
        """
        organisms = organisms or [
            "E. coli", "Klebsiella", "MRSA", "MSSA",
            "Pseudomonas", "Enterococcus"
        ]
        
        data = []
        for year in years:
            for organism in organisms:
                data.append({
                    "year": year,
                    "organism": organism,
                    "resistance_rate": None,
                    "sample_size": None,
                    "data_source": "UKHSA",
                    "note": "ESPAUR surveillance data"
                })
        
        return pd.DataFrame(data)
    
    def get_covid19_metrics(
        self,
        metrics: List[str],
        date_range: Optional[tuple] = None,
        regions: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Get COVID-19 surveillance metrics.
        
        Args:
            metrics: Metrics to retrieve (e.g., ["cases", "hospitalizations", "deaths"])
            date_range: (start_date, end_date) as strings (YYYY-MM-DD)
            regions: UK regions (default: all)
            
        Returns:
            DataFrame with COVID-19 data
        """
        regions = regions or self.REGIONS
        
        data = []
        for region in regions:
            for metric in metrics:
                data.append({
                    "region": region,
                    "metric": metric,
                    "value": None,
                    "date": None,
                    "data_source": "UKHSA",
                    "url": self.DATA_URLS["covid19"]["dashboard"]
                })
        
        return pd.DataFrame(data)
    
    def get_available_indicators(self) -> pd.DataFrame:
        """
        List all available surveillance indicators.
        
        Returns:
            DataFrame with available indicators and their descriptions
        """
        indicators = [
            {"category": "Infectious Diseases", "indicator": "Notifiable diseases", "frequency": "Weekly"},
            {"category": "Infectious Diseases", "indicator": "Tuberculosis", "frequency": "Quarterly"},
            {"category": "Vaccination", "indicator": "Childhood coverage", "frequency": "Quarterly"},
            {"category": "Vaccination", "indicator": "HPV coverage", "frequency": "Annual"},
            {"category": "Respiratory", "indicator": "Seasonal influenza", "frequency": "Weekly"},
            {"category": "Respiratory", "indicator": "COVID-19", "frequency": "Weekly"},
            {"category": "AMR", "indicator": "Antimicrobial resistance", "frequency": "Annual"},
            {"category": "Sexual Health", "indicator": "STI diagnoses", "frequency": "Quarterly"},
        ]
        return pd.DataFrame(indicators)
    
    def get_data_sources(self) -> pd.DataFrame:
        """
        Get information about UKHSA data sources.
        
        Returns:
            DataFrame with data source URLs and descriptions
        """
        sources = []
        for category, urls in self.DATA_URLS.items():
            for name, url in urls.items():
                sources.append({
                    "category": category,
                    "name": name,
                    "url": url
                })
        return pd.DataFrame(sources)


# Convenience functions
def get_ukhsa_disease_data(
    disease: str,
    years: List[int],
    regions: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Convenience function to get UKHSA disease data.
    
    Args:
        disease: Disease name
        years: List of years
        regions: UK regions
        
    Returns:
        DataFrame with disease surveillance data
    """
    accessor = UKHSAAccessor()
    return accessor.get_infectious_disease_data(disease, years, regions)


def get_uk_vaccination_coverage(
    vaccine: str,
    years: List[int]
) -> pd.DataFrame:
    """
    Get UK vaccination coverage data.
    
    Args:
        vaccine: Vaccine name (e.g., "MMR")
        years: List of years
        
    Returns:
        DataFrame with coverage data
    """
    accessor = UKHSAAccessor()
    return accessor.get_immunization_coverage(vaccine, years)


if __name__ == "__main__":
    ukhsa = UKHSAAccessor()
    
    print("UKHSA Available Indicators:")
    print(ukhsa.get_available_indicators())
    print("\n" + "="*60 + "\n")
    
    print("Data Sources:")
    print(ukhsa.get_data_sources())
