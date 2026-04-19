"""
WHO Global Health Observatory Data Accessor using ghoclient

This module provides a wrapper around the ghoclient library for accessing
WHO Global Health Observatory (GHO) data.

ghoclient is a Python client developed by Flávio Codeço Coelho for the
WHO GHO API, providing access to health indicators from countries worldwide.

Repository: https://github.com/fccoelho/ghoclient
PyPI: https://pypi.org/project/ghoclient/
"""

import logging
from typing import Any, ClassVar, Dict, List, Optional

import pandas as pd

from epidatasets._base import BaseAccessor
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# WHO Region Constants
WHO_REGIONS = {
    "AFRO": "Africa",
    "AMRO": "Americas", 
    "EMRO": "Eastern Mediterranean",
    "EURO": "Europe",
    "SEARO": "South-East Asia",
    "WPRO": "Western Pacific"
}

# EMRO (Eastern Mediterranean Region) Countries
# Source: https://www.emro.who.int/countries.html
EMRO_COUNTRIES = {
    "AFG": "Afghanistan",
    "BHR": "Bahrain",
    "DJI": "Djibouti",
    "EGY": "Egypt",
    "IRN": "Iran (Islamic Republic of)",
    "IRQ": "Iraq",
    "JOR": "Jordan",
    "KWT": "Kuwait",
    "LBN": "Lebanon",
    "LBY": "Libya",
    "MAR": "Morocco",
    "OMN": "Oman",
    "PAK": "Pakistan",
    "PSE": "Palestine",
    "QAT": "Qatar",
    "SAU": "Saudi Arabia",
    "SOM": "Somalia",
    "SDN": "Sudan",
    "SYR": "Syrian Arab Republic",
    "TUN": "Tunisia",
    "ARE": "United Arab Emirates",
    "YEM": "Yemen"
}


class WHOAccessor(BaseAccessor):
    """
    Accessor for WHO Global Health Observatory (GHO) data using ghoclient.

    This is a wrapper around ghoclient that provides a standardized interface
    consistent with other accessors in this repository.

    Example:
        >>> who = WHOAccessor()
        >>> data = who.get_indicator(
        ...     indicator="MALARIA_EST_INCIDENCE",
        ...     years=[2020, 2021, 2022],
        ...     countries=["BRA", "IND", "NGA"]
        ... )

    Requirements:
        pip install ghoclient
    """

    source_name: ClassVar[str] = "who"
    source_description: ClassVar[str] = (
        "WHO Global Health Observatory (GHO) data providing access to "
        "health indicators from countries worldwide via the ghoclient library."
    )
    source_url: ClassVar[str] = "https://ghoapi.azureedge.net/api/"

    def __init__(self):
        self._client = None

    def _get_client(self):
        """Lazy load GHOClient."""
        if self._client is None:
            try:
                from ghoclient import GHOClient

                self._client = GHOClient()
            except ImportError:
                raise ImportError(
                    "ghoclient is required. Install with: pip install ghoclient"
                )
        return self._client

    def list_countries(self) -> pd.DataFrame:
        """Return countries available in the WHO GHO."""
        return self.get_countries_list()

    def get_indicators_list(self) -> pd.DataFrame:
        """
        Fetch the list of available health indicators.

        Returns
        -------
            DataFrame with indicator information
        """
        client = self._get_client()

        logger.info("Fetching WHO indicators list...")
        indicators = client.get_indicators()

        # Convert to DataFrame if not already
        if isinstance(indicators, pd.DataFrame):
            return indicators
        else:
            return pd.DataFrame(indicators)

    def search_indicators(self, keyword: str) -> pd.DataFrame:
        """
        Search for indicators by keyword.

        Args:
            keyword: Search term (case-insensitive)

        Returns
        -------
            DataFrame with matching indicators
        """
        client = self._get_client()

        logger.info(f"Searching indicators for '{keyword}'...")
        results = client.search_indicators(keyword)

        if isinstance(results, pd.DataFrame):
            return results
        else:
            return pd.DataFrame(results)

    def get_indicator(
        self,
        indicator: str,
        years: Optional[List[int]] = None,
        countries: Optional[List[str]] = None,
        sex: Optional[str] = None,
        age_group: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Fetch data for a specific indicator.

        Args:
            indicator: Indicator code (e.g., "MALARIA_EST_INCIDENCE")
                      or indicator name
            years: List of years to fetch (e.g., [2020, 2021, 2022])
            countries: List of ISO3 country codes (e.g., ["BRA", "USA"])
            sex: Filter by sex ("MLE", "FMLE", or "BTSX")
            age_group: Filter by age group code

        Returns
        -------
            DataFrame with indicator data with standardized columns:
            - country_code: ISO3 country code
            - year: Year of observation
            - value: Numeric value
            - indicator_code: WHO indicator code
        """
        client = self._get_client()

        # Resolve indicator code if name was provided
        if " " in indicator or len(indicator) > 50:
            # Likely a name, search for code
            indicators = self.search_indicators(indicator)
            if not indicators.empty:
                # Get first match
                if "IndicatorCode" in indicators.columns:
                    indicator_code = indicators.iloc[0]["IndicatorCode"]
                elif "indicator_code" in indicators.columns:
                    indicator_code = indicators.iloc[0]["indicator_code"]
                else:
                    indicator_code = indicator
                logger.info(f"Resolved indicator to code: {indicator_code}")
            else:
                indicator_code = indicator
        else:
            indicator_code = indicator

        logger.info(f"Fetching data for indicator: {indicator_code}")

        # Build query parameters
        params = {"indicator": indicator_code}

        if years:
            params["years"] = years
        if countries:
            params["countries"] = countries
        if sex:
            params["sex"] = sex
        if age_group:
            params["age_group"] = age_group

        # Fetch data
        data = client.get_indicator(**params)

        if isinstance(data, pd.DataFrame):
            df = data
        else:
            df = pd.DataFrame(data)

        # Standardize column names
        column_mapping = {
            "SpatialDim": "country_code",
            "TimeDim": "year",
            "NumericValue": "value",
            "Value": "value",
            "IndicatorCode": "indicator_code",
            "Dim1": "sex",
            "Dim2": "age_group",
            "Dim3": "other_dimension",
            "country": "country_code",
            "date": "year",
        }

        df = df.rename(
            columns={k: v for k, v in column_mapping.items() if k in df.columns}
        )

        logger.info(f"Retrieved {len(df)} records")
        return df

    def get_countries_list(self) -> pd.DataFrame:
        """
        Fetch list of available countries and their codes.

        Returns
        -------
            DataFrame with country information
        """
        client = self._get_client()

        logger.info("Fetching countries list...")
        countries = client.get_countries()

        if isinstance(countries, pd.DataFrame):
            return countries
        else:
            return pd.DataFrame(countries)

    def get_available_years(self, indicator: str) -> List[int]:
        """
        Get list of years available for an indicator.

        Args:
            indicator: Indicator code or name

        Returns
        -------
            List of available years
        """
        client = self._get_client()

        logger.info(f"Fetching available years for {indicator}...")
        years = client.get_years(indicator)

        if isinstance(years, list):
            return sorted(years)
        else:
            return sorted(list(years))

    def get_indicator_metadata(self, indicator: str) -> Dict[str, Any]:
        """
        Get metadata for a specific indicator.

        Args:
            indicator: Indicator code

        Returns
        -------
            Dictionary with metadata
        """
        client = self._get_client()

        logger.info(f"Fetching metadata for {indicator}...")
        metadata = client.get_indicator_metadata(indicator)

        return metadata if isinstance(metadata, dict) else dict(metadata)

    def compare_countries(
        self, indicator: str, countries: List[str], years: Optional[List[int]] = None
    ) -> pd.DataFrame:
        """
        Compare indicator values across multiple countries.

        Args:
            indicator: Indicator code
            countries: List of ISO3 country codes
            years: List of years (optional, gets all available if not specified)

        Returns
        -------
            DataFrame with data for all countries
        """
        if years is None:
            years = self.get_available_years(indicator)

        data = self.get_indicator(indicator=indicator, years=years, countries=countries)

        # Pivot for easy comparison
        if (
            "value" in data.columns
            and "country_code" in data.columns
            and "year" in data.columns
        ):
            comparison = data.pivot_table(
                index="year", columns="country_code", values="value", aggfunc="mean"
            )
            return comparison

        return data

    def get_global_health_trends(
        self,
        indicator: str,
        start_year: int,
        end_year: int,
        region: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Get global trends for a health indicator over time.

        Args:
            indicator: Indicator code
            start_year: Start year
            end_year: End year
            region: WHO region code (optional, e.g., "AFRO", "AMRO", "SEARO")

        Returns
        -------
            DataFrame with trend data
        """
        years = list(range(start_year, end_year + 1))

        if region:
            # Get countries in region first
            countries_df = self.get_countries_list()
            if "region" in countries_df.columns:
                countries = countries_df[countries_df["region"] == region][
                    "country_code"
                ].tolist()
            else:
                countries = None
        else:
            countries = None

        data = self.get_indicator(indicator=indicator, years=years, countries=countries)

        # Calculate global/regional aggregates
        if "value" in data.columns and "year" in data.columns:
            trends = (
                data.groupby("year")["value"]
                .agg(["mean", "median", "std", "count"])
                .reset_index()
            )
            trends.columns = [
                "year",
                "mean_value",
                "median_value",
                "std_value",
                "n_countries",
            ]
            return trends

        return data

    def get_healthy_life_expectancy(
        self, countries: List[str], years: Optional[List[int]] = None
    ) -> pd.DataFrame:
        """
        Convenience method for healthy life expectancy (HALE).

        Args:
            countries: List of ISO3 country codes
            years: List of years

        Returns
        -------
            DataFrame with HALE data
        """
        return self.get_indicator(
            indicator="WHOSIS_000002", countries=countries, years=years  # HALE at birth
        )

    def get_malaria_incidence(
        self, countries: List[str], years: Optional[List[int]] = None
    ) -> pd.DataFrame:
        """
        Convenience method for malaria incidence.

        Args:
            countries: List of ISO3 country codes
            years: List of years

        Returns
        -------
            DataFrame with malaria incidence data
        """
        return self.get_indicator(
            indicator="MALARIA_EST_INCIDENCE", countries=countries, years=years
        )

    def get_covid_vaccination(
        self, countries: List[str], years: Optional[List[int]] = None
    ) -> pd.DataFrame:
        """
        Convenience method for COVID-19 vaccination coverage.

        Args:
            countries: List of ISO3 country codes
            years: List of years

        Returns
        -------
            DataFrame with vaccination data
        """
        return self.get_indicator(
            indicator="COVID19_VACCINATION", countries=countries, years=years
        )

    # ==================== EMRO (Eastern Mediterranean) Methods ====================

    def get_emro_countries(self) -> pd.DataFrame:
        """
        Get list of EMRO (Eastern Mediterranean) countries.

        Returns
        -------
            DataFrame with EMRO country codes and names
        """
        data = {
            "country_code": list(EMRO_COUNTRIES.keys()),
            "country_name": list(EMRO_COUNTRIES.values()),
            "who_region": ["EMRO"] * len(EMRO_COUNTRIES)
        }
        return pd.DataFrame(data)

    def get_emro_indicator(
        self,
        indicator: str,
        years: Optional[List[int]] = None,
        sex: Optional[str] = None,
        age_group: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Fetch indicator data for all EMRO countries.

        Args:
            indicator: Indicator code (e.g., "MALARIA_EST_INCIDENCE")
            years: List of years to fetch
            sex: Filter by sex ("MLE", "FMLE", or "BTSX")
            age_group: Filter by age group code

        Returns
        -------
            DataFrame with indicator data for EMRO countries
        """
        emro_codes = list(EMRO_COUNTRIES.keys())
        logger.info(f"Fetching {indicator} data for {len(emro_codes)} EMRO countries...")
        
        return self.get_indicator(
            indicator=indicator,
            years=years,
            countries=emro_codes,
            sex=sex,
            age_group=age_group
        )

    def get_emro_health_trends(
        self,
        indicator: str,
        start_year: int,
        end_year: int,
    ) -> pd.DataFrame:
        """
        Get health trends for EMRO region over time.

        Args:
            indicator: Indicator code
            start_year: Start year
            end_year: End year

        Returns
        -------
            DataFrame with EMRO regional trends
        """
        years = list(range(start_year, end_year + 1))
        data = self.get_emro_indicator(indicator=indicator, years=years)

        # Calculate EMRO aggregates
        if "value" in data.columns and "year" in data.columns:
            trends = (
                data.groupby("year")["value"]
                .agg(["mean", "median", "std", "count", "min", "max"])
                .reset_index()
            )
            trends.columns = [
                "year",
                "emro_mean",
                "emro_median", 
                "emro_std",
                "n_countries",
                "emro_min",
                "emro_max"
            ]
            trends["region"] = "EMRO"
            return trends

        return data

    def get_emro_malaria_data(
        self, years: Optional[List[int]] = None
    ) -> pd.DataFrame:
        """
        Get malaria incidence data for EMRO countries.

        Malaria is a significant health issue in parts of the EMRO region
        (particularly Afghanistan, Pakistan, Somalia, Sudan, Yemen).

        Args:
            years: List of years

        Returns
        -------
            DataFrame with malaria data for EMRO countries
        """
        return self.get_emro_indicator(
            indicator="MALARIA_EST_INCIDENCE",
            years=years
        )

    def get_emro_life_expectancy(
        self, years: Optional[List[int]] = None
    ) -> pd.DataFrame:
        """
        Get healthy life expectancy (HALE) data for EMRO countries.

        Args:
            years: List of years

        Returns
        -------
            DataFrame with HALE data for EMRO countries
        """
        return self.get_emro_indicator(
            indicator="WHOSIS_000002",  # HALE at birth
            years=years
        )

    def compare_emro_countries(
        self, indicator: str, years: Optional[List[int]] = None
    ) -> pd.DataFrame:
        """
        Compare indicator values across all EMRO countries.

        Args:
            indicator: Indicator code
            years: List of years

        Returns
        -------
            DataFrame pivoted by country for easy comparison
        """
        data = self.get_emro_indicator(indicator=indicator, years=years)
        
        if (
            "value" in data.columns
            and "country_code" in data.columns
            and "year" in data.columns
        ):
            comparison = data.pivot_table(
                index="year",
                columns="country_code",
                values="value",
                aggfunc="mean"
            )
            return comparison

        return data

