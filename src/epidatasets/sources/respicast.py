"""
ECDC RespiCast Data Accessor

This module provides access to the European Respiratory Diseases Forecasting Hub
(RespiCast), which provides ensemble forecasts for influenza-like illness (ILI)
and acute respiratory infection (ARI) indicators from multiple international
modeling teams.

Data is fetched directly from the GitHub repositories of the European Modelling Hubs.

Data Sources:
- RespiCast Hub: https://respicast.ecdc.europa.eu/
- Syndromic Indicators Repo: https://github.com/european-modelling-hubs/RespiCast-SyndromicIndicators
- Covid-19 Repo: https://github.com/european-modelling-hubs/RespiCast-Covid19

Diseases Covered:
- Influenza / ILI (ILI incidence, ARI incidence)
- COVID-19 (cases, hospital admissions, ICU, deaths)

Forecast Horizon: 1-4 weeks ahead

Update Frequency: Weekly (every Wednesday during active season)

Geographic Coverage: 30 EU/EEA countries

License: Open data (CC-BY 4.0)

Author: Flávio Codeço Coelho
License: MIT
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import ClassVar, Dict, List, Optional, Union

import pandas as pd
import requests

from epidatasets._base import BaseAccessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RespiCastAccessor(BaseAccessor):
    """
    Accessor for ECDC RespiCast - European Respiratory Diseases Forecasting Hub.

    Provides access to:
    - Ensemble forecasts (aggregated from multiple models)
    - Target data (observed values for validation)
    - Multi-horizon forecasts (1-4 weeks ahead)

    Data is fetched from the RespiCast GitHub repositories which follow the
    hubverse standard format with quantile-based forecasts.

    Example:
        >>> respicast = RespiCastAccessor()
        >>>
        >>> # Get latest ensemble forecast for Germany
        >>> forecast = respicast.get_ensemble_forecast(
        ...     country="DE",
        ...     disease="influenza",
        ...     target="ILI incidence",
        ...     horizon_weeks=4
        ... )
        >>>
        >>> # Get truth data (observed values)
        >>> truth = respicast.get_truth_data(
        ...     country="DE",
        ...     disease="influenza",
        ...     target="ILI incidence"
        ... )

    Data Sources:
        - RespiCast Hub: https://respicast.ecdc.europa.eu/
        - GitHub Repos: https://github.com/european-modelling-hubs/
    """

    source_name: ClassVar[str] = "respicast"
    source_description: ClassVar[str] = (
        "ECDC RespiCast - European Respiratory Diseases Forecasting Hub "
        "providing ensemble forecasts for influenza, COVID-19, and RSV "
        "from multiple international modeling teams."
    )
    source_url: ClassVar[str] = "https://respicast.ecdc.europa.eu/"

    REPOS = {
        "influenza": {
            "name": "RespiCast-SyndromicIndicators",
            "full_name": "european-modelling-hubs/RespiCast-SyndromicIndicators",
            "raw_base": "https://raw.githubusercontent.com/european-modelling-hubs/RespiCast-SyndromicIndicators/main",
            "api_base": "https://api.github.com/repos/european-modelling-hubs/RespiCast-SyndromicIndicators",
            "targets": ["ILI incidence", "ARI incidence"],
        },
        "covid19": {
            "name": "RespiCast-Covid19",
            "full_name": "european-modelling-hubs/RespiCast-Covid19",
            "raw_base": "https://raw.githubusercontent.com/european-modelling-hubs/RespiCast-Covid19/main",
            "api_base": "https://api.github.com/repos/european-modelling-hubs/RespiCast-Covid19",
            "targets": [
                "COVID-19 cases",
                "COVID-19 hospital admissions",
                "COVID-19 ICU admissions",
                "COVID-19 deaths",
            ],
        },
    }

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

    DISEASES = {
        "influenza": {
            "name": "Influenza",
            "targets": ["ILI incidence", "ARI incidence"],
            "season_start_month": 9,
            "season_end_month": 5,
        },
        "covid19": {
            "name": "COVID-19",
            "targets": [
                "COVID-19 cases",
                "COVID-19 hospital admissions",
                "COVID-19 ICU admissions",
                "COVID-19 deaths",
            ],
            "season_start_month": 1,
            "season_end_month": 12,
        },
    }

    HORIZONS = [1, 2, 3, 4]

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize RespiCast accessor.

        Args:
            cache_dir: Directory to cache downloaded data. If None, uses default.
        """
        self.cache_dir = (
            Path(cache_dir)
            if cache_dir
            else Path.home() / ".cache" / "epi_data" / "respicast"
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_ttl = timedelta(hours=24)

    def _get_cache_path(self, filename: str) -> Path:
        return self.cache_dir / filename

    def _is_cache_valid(self, cache_path: Path) -> bool:
        if not cache_path.exists():
            return False
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        return datetime.now() - mtime < self._cache_ttl

    def _fetch_csv(self, url: str, cache_key: str, use_cache: bool = True) -> pd.DataFrame:
        cache_path = self._get_cache_path(cache_key)

        if use_cache and self._is_cache_valid(cache_path):
            logger.info(f"Loading cached data: {cache_path}")
            return pd.read_csv(cache_path)

        logger.info(f"Fetching data from: {url}")

        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()

            if use_cache:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                with open(cache_path, "wb") as f:
                    f.write(response.content)

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
            diseases_data.append(
                {
                    "disease_key": key,
                    "disease_name": info["name"],
                    "targets": ", ".join(info["targets"]),
                    "season_start": info["season_start_month"],
                    "season_end": info["season_end_month"],
                }
            )

        return pd.DataFrame(diseases_data)

    def list_countries(self) -> pd.DataFrame:
        """Return countries covered by RespiCast."""
        return pd.DataFrame(
            [
                {"country_code": code, "country_name": name}
                for code, name in self.COUNTRIES.items()
            ]
        )

    def get_available_countries(self) -> pd.DataFrame:
        """
        Get list of countries covered by RespiCast.

        Returns:
            DataFrame with country codes and names.
        """
        countries_data = []
        for code, name in self.COUNTRIES.items():
            countries_data.append({"code": code, "name": name})

        return pd.DataFrame(countries_data)

    def get_truth_data(
        self,
        country: str,
        disease: str,
        target: Optional[str] = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Get truth/target data (observed values) for a country and disease.

        Args:
            country: Country name (e.g., "Germany") or ISO code (e.g., "DE")
            disease: Disease key ("influenza", "covid19")
            target: Specific target metric (optional, returns all if None)
            use_cache: Whether to use cached data

        Returns:
            DataFrame with observed values over time.
        """
        if disease not in self.REPOS:
            available = list(self.REPOS.keys())
            raise ValueError(f"Unknown disease: {disease}. Available: {available}")

        country_code = self._get_country_code(country)
        if not country_code:
            raise ValueError(f"Unknown country: {country}")

        repo = self.REPOS[disease]

        if disease == "influenza":
            return self._get_syndromic_truth(country_code, target, repo, use_cache)
        else:
            return self._get_covid_truth(country_code, target, repo, use_cache)

    def _get_syndromic_truth(
        self, country_code: str, target: Optional[str], repo: dict, use_cache: bool
    ) -> pd.DataFrame:
        targets_to_fetch = [target] if target else repo["targets"]
        frames = []

        for tgt in targets_to_fetch:
            filename = f"latest-{tgt.split()[0]}_incidence.csv"
            url = f"{repo['raw_base']}/target-data/{filename}"
            cache_key = f"truth_syndromic_{tgt.split()[0].lower()}"

            try:
                df = self._fetch_csv(url, cache_key, use_cache=use_cache)
                df = df[df["location"] == country_code]
                df = df.rename(columns={"truth_date": "date", "location": "country"})
                df["target"] = tgt
                df = df[["date", "country", "target", "value"]]
                frames.append(df)
            except Exception as e:
                logger.warning(f"Failed to get truth for {tgt}: {e}")

        if frames:
            result = pd.concat(frames, ignore_index=True)
            return result.sort_values("date").reset_index(drop=True)

        return pd.DataFrame(columns=["date", "country", "target", "value"])

    def _get_covid_truth(
        self, country_code: str, target: Optional[str], repo: dict, use_cache: bool
    ) -> pd.DataFrame:
        url = f"{repo['raw_base']}/target-data/latest-COVID-19_cases.csv"
        cache_key = "truth_covid19"

        try:
            df = self._fetch_csv(url, cache_key, use_cache=use_cache)
            df = df[df["location"] == country_code]
            df = df.rename(columns={"truth_date": "date", "location": "country"})
            if target:
                df = df[df["target"] == target]
            df = df[["date", "country", "target", "value"]]
            return df.sort_values("date").reset_index(drop=True)
        except Exception as e:
            logger.warning(f"Failed to get COVID-19 truth data: {e}")
            return pd.DataFrame(columns=["date", "country", "target", "value"])

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
            disease: Disease key ("influenza", "covid19")
            target: Target metric (e.g., "ILI incidence", "ARI incidence")
            forecast_date: Forecast date (YYYY-MM-DD). If None, gets latest.
            horizon_weeks: Number of weeks ahead (1-4)
            use_cache: Whether to use cached data

        Returns:
            DataFrame with ensemble forecast including quantiles.
        """
        if disease not in self.REPOS:
            raise ValueError(
                f"Unknown disease: {disease}. Available: {list(self.REPOS.keys())}"
            )

        repo = self.REPOS[disease]

        country_code = self._get_country_code(country)
        if not country_code:
            raise ValueError(f"Unknown country: {country}")

        if not forecast_date:
            forecast_date = self._get_latest_forecast_date(disease)
            if not forecast_date:
                logger.warning("No forecast dates found")
                return pd.DataFrame()

        url = f"{repo['raw_base']}/model-output/respicast-hubEnsemble/{forecast_date}-respicast-hubEnsemble.csv"
        cache_key = f"ensemble_{disease}_{forecast_date}"

        try:
            df = self._fetch_csv(url, cache_key, use_cache=use_cache)
        except Exception as e:
            logger.error(f"Failed to get ensemble forecast: {e}")
            return pd.DataFrame()

        df = self._filter_and_pivot_forecast(df, country_code, target, horizon_weeks)

        return df

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
            if not forecast_date:
                return pd.DataFrame()

        repo = self.REPOS[disease]
        country_code = self._get_country_code(country)
        if not country_code:
            raise ValueError(f"Unknown country: {country}")

        url = f"{repo['raw_base']}/model-output/respicast-hubEnsemble/{forecast_date}-respicast-hubEnsemble.csv"
        cache_key = f"ensemble_{disease}_{forecast_date}"

        try:
            df = self._fetch_csv(url, cache_key, use_cache=use_cache)
        except Exception as e:
            logger.error(f"Failed to get forecast: {e}")
            return pd.DataFrame()

        forecasts = []
        for horizon in self.HORIZONS:
            h_df = self._filter_and_pivot_forecast(df, country_code, target, horizon)
            if not h_df.empty:
                forecasts.append(h_df)

        if forecasts:
            return pd.concat(forecasts, ignore_index=True)
        return pd.DataFrame()

    def _filter_and_pivot_forecast(
        self,
        df: pd.DataFrame,
        country_code: str,
        target: str,
        horizon_weeks: int,
    ) -> pd.DataFrame:
        df = df[
            (df["location"] == country_code)
            & (df["target"] == target)
            & (df["horizon"] == horizon_weeks)
            & (df["output_type"] == "quantile")
        ]

        if df.empty:
            return pd.DataFrame()

        pivot = df.pivot_table(
            index=["origin_date", "target", "target_end_date", "horizon", "location"],
            columns="output_type_id",
            values="value",
            aggfunc="first",
        ).reset_index()

        pivot.columns.name = None

        rename_map = {
            "origin_date": "forecast_date",
            "target_end_date": "target_date",
            "location": "country",
        }
        pivot = pivot.rename(columns=rename_map)

        quantile_map = {}
        for col in pivot.columns:
            if isinstance(col, (int, float)):
                quantile_map[col] = f"quantile_{col}"
            elif isinstance(col, str):
                try:
                    float(col)
                    quantile_map[col] = f"quantile_{col}"
                except ValueError:
                    pass

        pivot = pivot.rename(columns=quantile_map)

        if "quantile_0.5" in pivot.columns:
            pivot["point"] = pivot["quantile_0.5"]

        return pivot

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
        forecast = self.get_forecast(
            country=country,
            disease=disease,
            target=target,
            forecast_date=forecast_date,
        )

        truth = self.get_truth_data(
            country=country,
            disease=disease,
            target=target,
        )

        if forecast.empty or truth.empty:
            return pd.DataFrame()

        truth_renamed = truth.rename(columns={"date": "target_date", "value": "value_truth"})

        merged = pd.merge(
            forecast,
            truth_renamed[["target_date", "value_truth"]],
            on="target_date",
            how="left",
        )

        return merged

    def _get_country_code(self, country: str) -> Optional[str]:
        country = country.strip()

        if len(country) == 2 and country.upper() in self.COUNTRIES:
            return country.upper()

        for code, name in self.COUNTRIES.items():
            if country.lower() == name.lower():
                return code

        return None

    def _get_latest_forecast_date(self, disease: str) -> Optional[str]:
        """Query the GitHub API to find the most recent ensemble forecast date."""
        if disease not in self.REPOS:
            return None

        repo = self.REPOS[disease]
        api_url = f"{repo['api_base']}/contents/model-output/respicast-hubEnsemble"

        try:
            response = requests.get(api_url, timeout=30)
            response.raise_for_status()
            files = response.json()

            csv_files = [
                f["name"]
                for f in files
                if f["name"].endswith(".csv") and "respicast-hubEnsemble" in f["name"]
            ]

            if not csv_files:
                return None

            csv_files.sort(reverse=True)

            date_str = csv_files[0].split("-respicast-hubEnsemble.csv")[0]
            return date_str

        except Exception as e:
            logger.warning(f"Failed to get latest forecast date: {e}")
            return None

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
            summary["available_targets"] = self.DISEASES.get(disease, {}).get(
                "targets", []
            )

        return summary


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
        disease: Disease key ("influenza", "covid19")
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
