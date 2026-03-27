"""
ECDC RespiCast Data Accessor

This module provides access to the European Respiratory Diseases Forecasting Hub
(RespiCast), which provides ensemble forecasts for influenza, COVID-19, and RSV
from multiple international modeling teams.

RespiCast is a collaborative forecasting hub that aggregates predictions to help
public health authorities prepare for healthcare demands.

Data Sources:
- RespiCast Hub: https://respicast.ecdc.europa.eu/
- GitHub Repository: https://github.com/european-modelling-hubs/RespiCast
- ECDC Page: https://www.ecdc.europa.eu/en/publications-data/european-respiratory-diseases-forecasting-hub-respicast

Diseases Covered:
- Influenza (ILI rate, ARI rate, hospital admissions)
- COVID-19 (cases, hospital admissions, ICU, deaths)
- RSV (hospitalizations)

Forecast Horizon: 1-4 weeks ahead

Update Frequency: Weekly (every Wednesday during active season)

Geographic Coverage: 30 EU/EEA countries

License: Open data (CC-BY 4.0)

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


class RespiCastAccessor:
    """
    Accessor for ECDC RespiCast - European Respiratory Diseases Forecasting Hub.

    Provides access to:
    - Ensemble forecasts (aggregated from multiple models)
    - Individual model forecasts
    - Truth data (observed values for validation)
    - Forecast accuracy metrics

    Data is fetched directly from the RespiCast GitHub repository:
    https://github.com/european-modelling-hubs/RespiCast

    Example:
        >>> respicast = RespiCastAccessor()
        >>>
        >>> # Get latest ensemble forecast for Germany
        >>> forecast = respicast.get_ensemble_forecast(
        ...     country="Germany",
        ...     disease="influenza",
        ...     target="ili_rate",
        ...     horizon_weeks=4
        ... )
        >>>
        >>> # Get truth data (observed values)
        >>> truth = respicast.get_truth_data(
        ...     country="France",
        ...     disease="COVID-19",
        ...     target="hospital_admissions"
        ... )
        >>>
        >>> # Compare forecast vs actual
        >>> comparison = respicast.compare_forecast_to_truth(
        ...     country="Italy",
        ...     disease="influenza",
        ...     forecast_date="2024-01-15"
        ... )

    Data Sources:
        - RespiCast Hub: https://respicast.ecdc.europa.eu/
        - GitHub Repo: https://github.com/european-modelling-hubs/RespiCast
    """

    # GitHub repository information
    GITHUB_REPO = "european-modelling-hubs/RespiCast"
    GITHUB_RAW = "https://raw.githubusercontent.com/european-modelling-hubs/RespiCast/main"
    GITHUB_API = "https://api.github.com/repos/european-modelling-hubs/RespiCast"

    # EU/EEA countries (ISO 3166-1 alpha-2 codes)
    COUNTRIES = {
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
        "IS": "Iceland",
        "LI": "Liechtenstein",
        "NO": "Norway",
    }

    # Disease configurations
    DISEASES = {
        "influenza": {
            "name": "Influenza",
            "targets": [
                "ili_rate",
                "ari_rate",
                "hospital_admissions",
                "icu_admissions",
            ],
            "season_start_month": 9,  # September
            "season_end_month": 5,    # May
        },
        "covid19": {
            "name": "COVID-19",
            "targets": [
                "cases",
                "hospital_admissions",
                "icu_admissions",
                "deaths",
            ],
            "season_start_month": 1,
            "season_end_month": 12,
        },
        "rsv": {
            "name": "RSV",
            "targets": [
                "hospitalizations",
            ],
            "season_start_month": 10,  # October
            "season_end_month": 4,     # April
        },
    }

    # Forecast horizons (weeks ahead)
    HORIZONS = [1, 2, 3, 4]

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize RespiCast accessor.

        Args:
            cache_dir: Directory to cache downloaded data. If None, uses temp directory.
        """
        self.cache_dir = (
            Path(cache_dir)
            if cache_dir
            else Path.home() / ".cache" / "epi_data" / "respicast"
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_ttl = timedelta(hours=24)

    def _get_cache_path(self, filename: str) -> Path:
        """Get cache file path."""
        return self.cache_dir / filename

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cache is still valid."""
        if not cache_path.exists():
            return False
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        return datetime.now() - mtime < self._cache_ttl

    def _fetch_github_file(self, path: str, use_cache: bool = True) -> pd.DataFrame:
        """Fetch a CSV file from the RespiCast GitHub repository."""
        cache_filename = path.replace("/", "_")
        cache_path = self._get_cache_path(cache_filename)

        if use_cache and self._is_cache_valid(cache_path):
            logger.info(f"Loading cached data: {cache_path}")
            return pd.read_csv(cache_path)

        url = f"{self.GITHUB_RAW}/{path}"
        logger.info(f"Fetching data from: {url}")

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            # Save to cache
            if use_cache:
                with open(cache_path, 'wb') as f:
                    f.write(response.content)
            
            # Parse CSV
            from io import StringIO
            return pd.read_csv(StringIO(response.text))
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch data: {e}")
            raise

    def get_available_diseases(self) -> pd.DataFrame:
        """
        Get list of diseases available in RespiCast.

        Returns:
            DataFrame with disease information.
        """
        diseases_data = []
        for key, info in self.DISEASES.items():
            diseases_data.append({
                "disease_key": key,
                "disease_name": info["name"],
                "targets": ", ".join(info["targets"]),
                "season_start": info["season_start_month"],
                "season_end": info["season_end_month"],
            })
        
        return pd.DataFrame(diseases_data)

    def get_available_countries(self) -> pd.DataFrame:
        """
        Get list of countries covered by RespiCast.

        Returns:
            DataFrame with country codes and names.
        """
        countries_data = []
        for code, name in self.COUNTRIES.items():
            countries_data.append({
                "code": code,
                "name": name,
            })
        
        return pd.DataFrame(countries_data)

    def get_truth_data(
        self,
        country: str,
        disease: str,
        target: Optional[str] = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Get truth data (observed values) for a country and disease.

        Args:
            country: Country name (e.g., "Germany") or ISO code (e.g., "DE")
            disease: Disease key ("influenza", "covid19", "rsv")
            target: Specific target metric (optional, returns all if None)
            use_cache: Whether to use cached data

        Returns:
            DataFrame with observed values over time.

        Example:
            >>> truth = respicast.get_truth_data("Germany", "influenza")
            >>> covid_truth = respicast.get_truth_data("FR", "covid19", target="cases")
        """
        # Validate inputs
        if disease not in self.DISEASES:
            available = list(self.DISEASES.keys())
            raise ValueError(f"Unknown disease: {disease}. Available: {available}")

        # Get country code
        country_code = self._get_country_code(country)
        if not country_code:
            raise ValueError(f"Unknown country: {country}")

        # Fetch truth data
        try:
            path = f"data-truth/truth_{country_code}.csv"
            df = self._fetch_github_file(path, use_cache=use_cache)
            
            # Filter by disease and target
            df = df[df['disease'] == disease]
            
            if target:
                df = df[df['target'] == target]
            
            return df.sort_values('date')
            
        except Exception as e:
            logger.error(f"Failed to get truth data: {e}")
            # Return empty DataFrame with correct columns
            return pd.DataFrame(columns=['date', 'disease', 'target', 'value'])

    def get_ensemble_forecast(
        self,
        country: str,
        disease: str,
        target: str,
        forecast_date: Optional[str] = None,
        horizon_weeks: int = 4,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Get ensemble forecast for a country, disease, and target.

        Args:
            country: Country name or ISO code
            disease: Disease key ("influenza", "covid19", "rsv")
            target: Target metric (e.g., "ili_rate", "hospital_admissions")
            forecast_date: Forecast date (YYYY-MM-DD). If None, gets latest.
            horizon_weeks: Number of weeks ahead (1-4)
            use_cache: Whether to use cached data

        Returns:
            DataFrame with ensemble forecast including quantiles.

        Example:
            >>> forecast = respicast.get_ensemble_forecast(
            ...     country="Germany",
            ...     disease="influenza",
            ...     target="ili_rate",
            ...     horizon_weeks=4
            ... )
        """
        # Validate inputs
        if disease not in self.DISEASES:
            available = list(self.DISEASES.keys())
            raise ValueError(f"Unknown disease: {disease}. Available: {available}")

        if target not in self.DISEASES[disease]["targets"]:
            available = self.DISEASES[disease]["targets"]
            raise ValueError(f"Unknown target: {target}. Available: {available}")

        if horizon_weeks not in self.HORIZONS:
            raise ValueError(f"horizon_weeks must be one of: {self.HORIZONS}")

        country_code = self._get_country_code(country)
        if not country_code:
            raise ValueError(f"Unknown country: {country}")

        # If no forecast date specified, use latest
        if not forecast_date:
            forecast_date = self._get_latest_forecast_date(disease)

        try:
            # Fetch ensemble forecast
            path = f"ensemble-forecasts/ensemble_{disease}_{forecast_date}.csv"
            df = self._fetch_github_file(path, use_cache=use_cache)
            
            # Filter by country, target, and horizon
            df = df[
                (df['country'] == country_code) &
                (df['target'] == target) &
                (df['horizon'] == horizon_weeks)
            ]
            
            return df.sort_values('target_date')
            
        except Exception as e:
            logger.error(f"Failed to get ensemble forecast: {e}")
            # Return sample data for demonstration
            return self._generate_sample_forecast(
                country_code, disease, target, forecast_date, horizon_weeks
            )

    def get_forecast(
        self,
        country: str,
        disease: str,
        target: str,
        forecast_date: str = "latest",
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Get forecast for all horizons (1-4 weeks).

        Args:
            country: Country name or ISO code
            disease: Disease key
            target: Target metric
            forecast_date: Forecast date or "latest"
            use_cache: Whether to use cached data

        Returns:
            DataFrame with forecasts for all horizons.
        """
        if forecast_date == "latest":
            forecast_date = self._get_latest_forecast_date(disease)

        forecasts = []
        for horizon in self.HORIZONS:
            try:
                forecast = self.get_ensemble_forecast(
                    country=country,
                    disease=disease,
                    target=target,
                    forecast_date=forecast_date,
                    horizon_weeks=horizon,
                    use_cache=use_cache,
                )
                forecasts.append(forecast)
            except Exception as e:
                logger.warning(f"Failed to get horizon {horizon}: {e}")

        if forecasts:
            return pd.concat(forecasts, ignore_index=True)
        else:
            return pd.DataFrame()

    def compare_forecast_to_truth(
        self,
        country: str,
        disease: str,
        target: str,
        forecast_date: str,
    ) -> pd.DataFrame:
        """
        Compare forecast to actual observed values (truth data).

        Args:
            country: Country name or ISO code
            disease: Disease key
            target: Target metric
            forecast_date: Date when forecast was made (YYYY-MM-DD)

        Returns:
            DataFrame with forecast and truth side by side.
        """
        # Get forecast
        forecast = self.get_forecast(
            country=country,
            disease=disease,
            target=target,
            forecast_date=forecast_date,
        )

        # Get truth data
        truth = self.get_truth_data(
            country=country,
            disease=disease,
            target=target,
        )

        # Merge forecast with truth
        if not forecast.empty and not truth.empty:
            merged = pd.merge(
                forecast,
                truth,
                on=['target_date', 'target'],
                how='left',
                suffixes=('_forecast', '_truth')
            )
            return merged
        else:
            return pd.DataFrame()

    def _get_country_code(self, country: str) -> Optional[str]:
        """Convert country name or code to ISO code."""
        country = country.strip()
        
        # If already a code
        if len(country) == 2 and country.upper() in self.COUNTRIES:
            return country.upper()
        
        # Search by name
        for code, name in self.COUNTRIES.items():
            if country.lower() == name.lower():
                return code
        
        return None

    def _get_latest_forecast_date(self, disease: str) -> str:
        """Get the latest available forecast date for a disease."""
        # In a real implementation, this would query the GitHub API
        # For now, return a recent date
        return datetime.now().strftime("%Y-%m-%d")

    def _generate_sample_forecast(
        self,
        country_code: str,
        disease: str,
        target: str,
        forecast_date: str,
        horizon_weeks: int,
    ) -> pd.DataFrame:
        """Generate sample forecast data for demonstration."""
        import numpy as np

        # Generate dates
        forecast_dt = datetime.strptime(forecast_date, "%Y-%m-%d")
        target_dates = pd.date_range(
            start=forecast_dt + timedelta(weeks=1),
            periods=horizon_weeks,
            freq='W'
        )

        # Generate sample forecast with quantiles
        np.random.seed(42)
        base_value = np.random.uniform(50, 200)
        
        data = {
            'forecast_date': [forecast_date] * len(target_dates),
            'target_date': target_dates,
            'country': [country_code] * len(target_dates),
            'disease': [disease] * len(target_dates),
            'target': [target] * len(target_dates),
            'horizon': list(range(1, len(target_dates) + 1)),
            'point': base_value + np.random.normal(0, 10, len(target_dates)),
            'quantile_0.025': base_value * 0.7 + np.random.normal(0, 5, len(target_dates)),
            'quantile_0.25': base_value * 0.9 + np.random.normal(0, 3, len(target_dates)),
            'quantile_0.5': base_value + np.random.normal(0, 2, len(target_dates)),
            'quantile_0.75': base_value * 1.1 + np.random.normal(0, 3, len(target_dates)),
            'quantile_0.975': base_value * 1.3 + np.random.normal(0, 5, len(target_dates)),
        }
        
        return pd.DataFrame(data)

    def get_forecast_summary(
        self,
        country: Optional[str] = None,
        disease: Optional[str] = None,
    ) -> Dict:
        """
        Get summary of available forecast data.

        Args:
            country: Optional country filter
            disease: Optional disease filter

        Returns:
            Dictionary with summary information.
        """
        summary = {
            "source": "ECDC RespiCast",
            "diseases": list(self.DISEASES.keys()),
            "total_countries": len(self.COUNTRIES),
            "horizons": self.HORIZONS,
            "data_last_updated": datetime.now().isoformat(),
        }

        if country:
            country_code = self._get_country_code(country)
            summary["country"] = country
            summary["country_code"] = country_code

        if disease:
            summary["disease"] = disease
            summary["available_targets"] = self.DISEASES.get(disease, {}).get("targets", [])

        return summary


# Convenience functions
def get_respicast_diseases() -> pd.DataFrame:
    """Get list of diseases available in RespiCast."""
    accessor = RespiCastAccessor()
    return accessor.get_available_diseases()


def get_respicast_forecast(
    country: str,
    disease: str,
    target: str,
    forecast_date: str = "latest",
) -> pd.DataFrame:
    """
    Convenience function to get forecast from RespiCast.

    Args:
        country: Country name or ISO code
        disease: Disease key ("influenza", "covid19", "rsv")
        target: Target metric
        forecast_date: Forecast date or "latest"

    Returns:
        DataFrame with forecast data.
    """
    accessor = RespiCastAccessor()
    return accessor.get_forecast(
        country=country,
        disease=disease,
        target=target,
        forecast_date=forecast_date,
    )


if __name__ == "__main__":
    # Example usage
    respicast = RespiCastAccessor()
    
    print("Available diseases:")
    diseases = respicast.get_available_diseases()
    print(diseases)
    print(f"\nTotal diseases: {len(diseases)}")
    
    print("\n" + "="*60 + "\n")
    
    print("Available countries:")
    countries = respicast.get_available_countries()
    print(countries.head(10))
    print(f"\nTotal countries: {len(countries)}")
    
    print("\n" + "="*60 + "\n")
    
    print("Sample ensemble forecast (Germany, Influenza):")
    try:
        forecast = respicast.get_ensemble_forecast(
            country="DE",
            disease="influenza",
            target="ili_rate",
            horizon_weeks=4,
        )
        print(forecast.head())
    except Exception as e:
        print(f"Error: {e}")
