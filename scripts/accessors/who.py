"""
WHO Global Health Observatory Data Accessor

This module provides access to WHO GHO data through their API.
"""

import requests
import pandas as pd
from typing import List, Optional, Dict, Any
import json
from pathlib import Path


class WHOAccessor:
    """
    Accessor for WHO Global Health Observatory (GHO) data.
    
    The GHO API provides access to health indicators from countries worldwide.
    
    Example:
        >>> who = WHOAccessor()
        >>> data = who.get_indicator(
        ...     indicator="Malaria incidence (per 1,000 population at risk)",
        ...     years=[2020, 2021, 2022],
        ...     countries=["BRA", "IND"]
        ... )
    """
    
    BASE_URL = "https://ghoapi.azureedge.net/api"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "epidemiological-datasets/1.0 (Research)"
        })
        self._indicators_cache: Optional[pd.DataFrame] = None
    
    def get_indicators_list(self) -> pd.DataFrame:
        """
        Fetch the list of available health indicators.
        
        Returns:
            DataFrame with columns: IndicatorCode, IndicatorName, Language
        """
        if self._indicators_cache is not None:
            return self._indicators_cache
            
        url = f"{self.BASE_URL}/Indicator"
        response = self.session.get(url)
        response.raise_for_status()
        
        data = response.json()["value"]
        self._indicators_cache = pd.DataFrame(data)
        return self._indicators_cache
    
    def search_indicators(self, keyword: str) -> pd.DataFrame:
        """
        Search for indicators by keyword.
        
        Args:
            keyword: Search term (case-insensitive)
            
        Returns:
            DataFrame with matching indicators
        """
        indicators = self.get_indicators_list()
        mask = indicators["IndicatorName"].str.contains(keyword, case=False, na=False)
        return indicators[mask]
    
    def get_indicator(
        self,
        indicator: str,
        years: Optional[List[int]] = None,
        countries: Optional[List[str]] = None,
        sex: Optional[str] = None,
        age_group: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Fetch data for a specific indicator.
        
        Args:
            indicator: Indicator code or name (e.g., "MALARIA_EST_INCIDENCE")
            years: List of years to fetch (e.g., [2020, 2021, 2022])
            countries: List of ISO3 country codes (e.g., ["BRA", "USA"])
            sex: Filter by sex ("MLE", "FMLE", or "BTSX")
            age_group: Filter by age group code
            
        Returns:
            DataFrame with indicator data
        """
        # Resolve indicator code if name was provided
        if " " in indicator:
            indicators = self.get_indicators_list()
            match = indicators[indicators["IndicatorName"] == indicator]
            if match.empty:
                raise ValueError(f"Indicator not found: {indicator}")
            indicator_code = match.iloc[0]["IndicatorCode"]
        else:
            indicator_code = indicator
        
        # Build filter
        filters = []
        if years:
            year_filter = " or ".join([f"year eq {y}" for y in years])
            filters.append(f"({year_filter})")
        
        if countries:
            country_filter = " or ".join([f"SpatialDim eq '{c}'" for c in countries])
            filters.append(f"({country_filter})")
        
        if sex:
            filters.append(f"Dim1 eq '{sex}'")
        
        if age_group:
            filters.append(f"Dim2 eq '{age_group}'")
        
        # Construct URL
        filter_str = " and ".join(filters) if filters else ""
        url = f"{self.BASE_URL}/{indicator_code}"
        
        params = {}
        if filter_str:
            params["$filter"] = filter_str
        
        # Fetch data
        all_data = []
        while url:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            result = response.json()
            if "value" in result:
                all_data.extend(result["value"])
            
            # Handle pagination
            url = result.get("odata.nextLink")
            params = {}  # Clear params for subsequent requests
        
        if not all_data:
            return pd.DataFrame()
        
        df = pd.DataFrame(all_data)
        
        # Clean up columns
        column_mapping = {
            "SpatialDim": "country_code",
            "TimeDim": "year",
            "NumericValue": "value",
            "Value": "value_text",
            "IndicatorCode": "indicator_code",
            "Dim1": "sex",
            "Dim2": "age_group",
            "Dim3": "other_dimension"
        }
        
        df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})
        
        return df
    
    def get_countries_list(self) -> pd.DataFrame:
        """
        Fetch list of available countries and their codes.
        
        Returns:
            DataFrame with country codes and names
        """
        url = f"{self.BASE_URL}/DIMENSION/COUNTRY/DimensionValues"
        response = self.session.get(url)
        response.raise_for_status()
        
        data = response.json()["value"]
        return pd.DataFrame(data)
    
    def get_available_years(self, indicator: str) -> List[int]:
        """
        Get list of years available for an indicator.
        
        Args:
            indicator: Indicator code or name
            
        Returns:
            List of available years
        """
        url = f"{self.BASE_URL}/DIMENSION/YEAR/DimensionValues"
        response = self.session.get(url)
        response.raise_for_status()
        
        data = response.json()["value"]
        years = [int(item["Code"]) for item in data if item["Code"].isdigit()]
        return sorted(years)


def main():
    """
    Example usage of WHOAccessor.
    """
    print("WHO Global Health Observatory Data Accessor")
    print("=" * 50)
    
    who = WHOAccessor()
    
    # List available indicators
    print("\nFetching indicators list...")
    indicators = who.get_indicators_list()
    print(f"Total indicators available: {len(indicators)}")
    
    # Search for malaria-related indicators
    print("\nSearching for 'malaria' indicators...")
    malaria_indicators = who.search_indicators("malaria")
    print(f"Found {len(malaria_indicators)} malaria-related indicators:")
    for _, row in malaria_indicators.head().iterrows():
        print(f"  - {row['IndicatorCode']}: {row['IndicatorName']}")
    
    # Fetch specific indicator data
    print("\nFetching malaria incidence data for Brazil and India...")
    try:
        data = who.get_indicator(
            indicator="MALARIA_EST_INCIDENCE",
            years=[2020, 2021, 2022],
            countries=["BRA", "IND", "NGA"]
        )
        print(f"Retrieved {len(data)} records")
        if not data.empty:
            print(data.head())
    except Exception as e:
        print(f"Error fetching data: {e}")


if __name__ == "__main__":
    main()
