"""
Copernicus Climate Data Store (CDS) Accessor

Provides access to climate and weather data from the Copernicus Climate Data Store.
CDS offers a wide range of climate data products including ERA5 reanalysis,
temperature, precipitation, humidity, and other meteorological variables.

Data Source: https://cds.climate.copernicus.eu/
API: CDS API (Python library: cdsapi)
Documentation: https://cds.climate.copernicus.eu/how-to-api

Requirements:
    - Free CDS account (register at https://cds.climate.copernicus.eu/)
    - API credentials configured in ~/.cdsapirc or environment variables
    - cdsapi Python library: pip install cdsapi

Key Datasets:
    - ERA5 hourly data on single levels (reanalysis-era5-single-levels)
    - ERA5 hourly data on pressure levels (reanalysis-era5-pressure-levels)
    - ERA5-Land hourly data (reanalysis-era5-land)

Common Variables for Epidemiological Modeling:
    - 2m_temperature: Air temperature at 2 meters
    - total_precipitation: Total precipitation
    - 2m_dewpoint_temperature: Dewpoint temperature (for humidity)
    - relative_humidity: Relative humidity
    - surface_solar_radiation_downwards: Solar radiation

Use Cases:
    - Temperature/precipitation correlation with dengue transmission
    - Predictive model features for disease forecasting
    - Seasonality analysis of vector-borne diseases
    - Aedes aegypti breeding site prediction

Author: Flávio Codeço Coelho
License: MIT
"""

import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Optional import - cdsapi is required only if using this accessor
try:
    import cdsapi
    HAS_CDSAPI = True
except ImportError:
    HAS_CDSAPI = False
    logger.warning("cdsapi not installed. Install with: pip install cdsapi")

try:
    import xarray as xr
    HAS_XARRAY = True
except ImportError:
    HAS_XARRAY = False
    logger.warning("xarray not installed. Install with: pip install xarray netCDF4")


class CopernicusCDSAccessor:
    """
    Accessor for Copernicus Climate Data Store (CDS).
    
    Provides access to ERA5 reanalysis data and other climate datasets
    for epidemiological modeling and research.
    
    Setup:
        1. Register at https://cds.climate.copernicus.eu/
        2. Install cdsapi: pip install cdsapi
        3. Configure credentials in ~/.cdsapirc:
           url: https://cds.climate.copernicus.eu/api
           key: YOUR_API_KEY
        4. Accept the Terms of Use for each dataset you want to access
    
    Example:
        >>> from scripts.accessors.copernicus_cds import CopernicusCDSAccessor
        >>> cds = CopernicusCDSAccessor()
        >>> 
        >>> # Get temperature data for Brazil
        >>> temp = cds.get_era5_data(
        ...     variable='2m_temperature',
        ...     start_date='2024-01-01',
        ...     end_date='2024-01-31',
        ...     area=[5, -75, -35, -35],  # North, West, South, East
        ... )
        >>> 
        >>> # Calculate weekly means for epidemiological analysis
        >>> weekly = cds.aggregate_to_weekly(temp)
    """
    
    # Main ERA5 datasets
    DATASETS = {
        'era5-single-levels': 'reanalysis-era5-single-levels',
        'era5-pressure-levels': 'reanalysis-era5-pressure-levels',
        'era5-land': 'reanalysis-era5-land',
        'era5-land-monthly-means': 'reanalysis-era5-land-monthly-means',
        'seasonal-original-single-levels': 'seasonal-original-single-levels',
    }
    
    # Common variables for epidemiological modeling
    VARIABLES = {
        '2m_temperature': '2m temperature',
        'total_precipitation': 'Total precipitation',
        '2m_dewpoint_temperature': '2m dewpoint temperature',
        'relative_humidity': 'Relative humidity',
        'surface_pressure': 'Surface pressure',
        'surface_solar_radiation_downwards': 'Surface solar radiation downwards',
        'surface_thermal_radiation_downwards': 'Surface thermal radiation downwards',
        '10m_u_component_of_wind': '10m u-component of wind',
        '10m_v_component_of_wind': '10m v-component of wind',
        'evaporation': 'Evaporation',
        'potential_evaporation': 'Potential evaporation',
        'soil_temperature_level_1': 'Soil temperature level 1',
        'volumetric_soil_water_layer_1': 'Volumetric soil water layer 1',
    }
    
    # Predefined areas (North, West, South, East)
    AREAS = {
        'brazil': [5, -75, -35, -35],
        'south_america': [15, -85, -60, -30],
        'global': [90, -180, -90, 180],
        'europe': [75, -25, 30, 45],
        'africa': [40, -20, -40, 55],
        'asia': [55, 60, -15, 150],
        'north_america': [75, -170, 10, -50],
    }
    
    def __init__(
        self,
        cache_dir: Optional[str] = None,
        cache_ttl: int = 168,  # 7 days default for climate data
        wait_completion: bool = True,
    ):
        """
        Initialize Copernicus CDS accessor.
        
        Args:
            cache_dir: Directory to cache downloaded data
            cache_ttl: Cache time-to-live in hours (default: 168 = 7 days)
            wait_completion: Whether to wait for CDS request completion
        
        Raises:
            ImportError: If cdsapi is not installed
            RuntimeError: If CDS credentials are not configured
        """
        if not HAS_CDSAPI:
            raise ImportError(
                "cdsapi is required. Install with: pip install cdsapi\n"
                "Then configure your CDS credentials in ~/.cdsapirc"
            )
        
        # Check credentials
        self._check_credentials()
        
        # Initialize CDS client
        try:
            self.client = cdsapi.Client(
                url=self.cds_url,
                key=self.cds_key,
            )
            logger.info("CDS client initialized successfully")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize CDS client: {e}") from e
        
        # Setup caching
        self.cache_dir = (
            Path(cache_dir)
            if cache_dir
            else Path.home() / ".cache" / "epi_data" / "copernicus_cds"
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_ttl = timedelta(hours=cache_ttl)
        self._wait_completion = wait_completion
        
        logger.info(f"Copernicus CDS accessor initialized (cache: {self.cache_dir})")
    
    def _check_credentials(self) -> None:
        """Check and load CDS API credentials."""
        # Try environment variables first
        self.cds_url = os.getenv('CDSAPI_URL', 'https://cds.climate.copernicus.eu/api')
        self.cds_key = os.getenv('CDSAPI_KEY')
        
        # If not in environment, try config file
        if not self.cds_key:
            config_paths = [
                Path.home() / ".cdsapirc",
                Path.home() / ".nanobot" / "config" / "cdsapi.env",
                Path.home() / ".config" / "epi_data" / "cdsapi.env",
                Path(".cdsapirc"),
            ]
            
            for config_path in config_paths:
                if config_path.exists():
                    try:
                        with open(config_path) as f:
                            for line in f:
                                if line.startswith('url:'):
                                    self.cds_url = line.split(':', 1)[1].strip()
                                elif line.startswith('key:'):
                                    self.cds_key = line.split(':', 1)[1].strip()
                                elif '=' in line and 'CDSAPI' in line:
                                    # Handle env file format
                                    key, value = line.split('=', 1)
                                    if 'URL' in key:
                                        self.cds_url = value.strip()
                                    elif 'KEY' in key:
                                        self.cds_key = value.strip()
                    except Exception as e:
                        logger.warning(f"Failed to read config from {config_path}: {e}")
        
        if not self.cds_key:
            raise RuntimeError(
                "CDS API credentials not found.\n"
                "Please configure in one of:\n"
                "  - Environment variables: CDSAPI_URL, CDSAPI_KEY\n"
                "  - Config file: ~/.cdsapirc\n"
                "  - Config file: ~/.nanobot/config/cdsapi.env\n\n"
                "To get credentials:\n"
                "  1. Register at https://cds.climate.copernicus.eu/\n"
                "  2. Go to your profile page\n"
                "  3. Copy the API key\n"
                "  4. Create ~/.cdsapirc with:\n"
                "     url: https://cds.climate.copernicus.eu/api\n"
                "     key: YOUR_API_KEY"
            )
    
    def _get_cache_path(self, filename: str) -> Path:
        """Return the path to a cache file."""
        safe_filename = filename.replace('/', '_').replace('\\', '_').replace(':', '_')
        return self.cache_dir / safe_filename
    
    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Return True if the cache file exists and is younger than the TTL."""
        if not cache_path.exists():
            return False
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        return datetime.now() - mtime < self._cache_ttl
    
    def _build_request(
        self,
        variable: Union[str, List[str]],
        start_date: str,
        end_date: str,
        area: Optional[List[float]] = None,
        dataset: str = 'era5-single-levels',
        **kwargs
    ) -> Dict:
        """
        Build CDS API request parameters.
        
        Args:
            variable: Variable name(s) to retrieve
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            area: Bounding box [North, West, South, East]
            dataset: Dataset name
            **kwargs: Additional request parameters
        
        Returns:
            Request dictionary for CDS API
        """
        # Parse dates
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        # Build years, months, days lists
        years = list(range(start.year, end.year + 1))
        years = [str(y) for y in years]
        
        months = list(range(1, 13))
        months = [f"{m:02d}" for m in months]
        
        days = list(range(1, 32))
        days = [f"{d:02d}" for d in days]
        
        # All hours
        times = [f"{h:02d}:00" for h in range(24)]
        
        request = {
            'product_type': ['reanalysis'],
            'variable': [variable] if isinstance(variable, str) else variable,
            'year': years,
            'month': months,
            'day': days,
            'time': times,
            'data_format': 'netcdf',
            'download_format': 'unarchived',
        }
        
        # Add area if specified
        if area:
            request['area'] = area
        
        # Add any additional parameters
        request.update(kwargs)
        
        return request
    
    def get_era5_data(
        self,
        variable: Union[str, List[str]],
        start_date: str,
        end_date: str,
        area: Optional[Union[str, List[float]]] = None,
        dataset: str = 'era5-single-levels',
        use_cache: bool = True,
        **kwargs
    ) -> Union[xr.Dataset, str]:
        """
        Retrieve ERA5 reanalysis data from CDS.
        
        Args:
            variable: Variable name(s) to retrieve
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            area: Bounding box [North, West, South, East] or predefined area name
            dataset: Dataset name ('era5-single-levels', 'era5-land', etc.)
            use_cache: Whether to use cached data
            **kwargs: Additional request parameters
        
        Returns:
            xarray Dataset with the retrieved data, or path to file if xarray not available
        
        Example:
            >>> cds = CopernicusCDSAccessor()
            >>> # Get temperature for Brazil
            >>> temp = cds.get_era5_data(
            ...     variable='2m_temperature',
            ...     start_date='2024-01-01',
            ...     end_date='2024-01-31',
            ...     area='brazil',
            ... )
        """
        # Resolve area
        if isinstance(area, str):
            if area not in self.AREAS:
                raise ValueError(f"Area '{area}' not recognized. Choose from: {list(self.AREAS.keys())}")
            area = self.AREAS[area]
        
        # Build request
        request = self._build_request(
            variable=variable,
            start_date=start_date,
            end_date=end_date,
            area=area,
            dataset=dataset,
            **kwargs
        )
        
        # Generate cache filename
        var_str = variable.replace(' ', '_') if isinstance(variable, str) else '_'.join(variable)
        area_str = '_'.join([str(a) for a in area]) if area else 'global'
        cache_name = f"{dataset}_{var_str}_{start_date}_{end_date}_{area_str}.nc"
        cache_path = self._get_cache_path(cache_name)
        
        # Check cache
        if use_cache and self._is_cache_valid(cache_path):
            logger.info(f"Loading from cache: {cache_path.name}")
            if HAS_XARRAY:
                return xr.open_dataset(cache_path)
            else:
                return str(cache_path)
        
        # Download from CDS
        dataset_id = self.DATASETS.get(dataset, dataset)
        logger.info(f"Requesting data from CDS: {dataset_id}")
        logger.info(f"Variable: {variable}")
        logger.info(f"Period: {start_date} to {end_date}")
        logger.info(f"Area: {area if area else 'global'}")
        
        try:
            self.client.retrieve(
                dataset_id,
                request,
                str(cache_path)
            )
            logger.info(f"Data downloaded to: {cache_path}")
            
            if HAS_XARRAY:
                return xr.open_dataset(cache_path)
            else:
                return str(cache_path)
                
        except Exception as e:
            logger.error(f"Failed to retrieve data from CDS: {e}")
            raise RuntimeError(f"CDS data retrieval failed: {e}") from e
    
    def get_temperature(
        self,
        start_date: str,
        end_date: str,
        area: Optional[Union[str, List[float]]] = None,
        use_cache: bool = True,
    ) -> Union[xr.Dataset, str]:
        """
        Convenience method to get 2m temperature data.
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            area: Bounding box or predefined area name
            use_cache: Whether to use cached data
        
        Returns:
            xarray Dataset with temperature data
        """
        return self.get_era5_data(
            variable='2m_temperature',
            start_date=start_date,
            end_date=end_date,
            area=area,
            use_cache=use_cache,
        )
    
    def get_precipitation(
        self,
        start_date: str,
        end_date: str,
        area: Optional[Union[str, List[float]]] = None,
        use_cache: bool = True,
    ) -> Union[xr.Dataset, str]:
        """
        Convenience method to get total precipitation data.
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            area: Bounding box or predefined area name
            use_cache: Whether to use cached data
        
        Returns:
            xarray Dataset with precipitation data
        """
        return self.get_era5_data(
            variable='total_precipitation',
            start_date=start_date,
            end_date=end_date,
            area=area,
            use_cache=use_cache,
        )
    
    def get_humidity(
        self,
        start_date: str,
        end_date: str,
        area: Optional[Union[str, List[float]]] = None,
        use_cache: bool = True,
    ) -> Union[xr.Dataset, str]:
        """
        Convenience method to get relative humidity data.
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            area: Bounding box or predefined area name
            use_cache: Whether to use cached data
        
        Returns:
            xarray Dataset with humidity data
        """
        return self.get_era5_data(
            variable='relative_humidity',
            start_date=start_date,
            end_date=end_date,
            area=area,
            use_cache=use_cache,
        )
    
    def aggregate_to_daily(
        self,
        ds: xr.Dataset,
        method: str = 'mean',
    ) -> xr.Dataset:
        """
        Aggregate hourly ERA5 data to daily values.
        
        Args:
            ds: xarray Dataset with hourly data
            method: Aggregation method ('mean', 'sum', 'min', 'max')
        
        Returns:
            xarray Dataset with daily aggregated data
        """
        if not HAS_XARRAY:
            raise ImportError("xarray is required for data aggregation")
        
        # Group by day and aggregate
        if method == 'mean':
            return ds.resample(time='1D').mean()
        elif method == 'sum':
            return ds.resample(time='1D').sum()
        elif method == 'min':
            return ds.resample(time='1D').min()
        elif method == 'max':
            return ds.resample(time='1D').max()
        else:
            raise ValueError(f"Method '{method}' not supported. Use: mean, sum, min, max")
    
    def aggregate_to_weekly(
        self,
        ds: xr.Dataset,
        method: str = 'mean',
    ) -> xr.Dataset:
        """
        Aggregate data to weekly values.
        
        Args:
            ds: xarray Dataset
            method: Aggregation method ('mean', 'sum', 'min', 'max')
        
        Returns:
            xarray Dataset with weekly aggregated data
        """
        if not HAS_XARRAY:
            raise ImportError("xarray is required for data aggregation")
        
        if method == 'mean':
            return ds.resample(time='1W').mean()
        elif method == 'sum':
            return ds.resample(time='1W').sum()
        elif method == 'min':
            return ds.resample(time='1W').min()
        elif method == 'max':
            return ds.resample(time='1W').max()
        else:
            raise ValueError(f"Method '{method}' not supported")
    
    def to_dataframe(
        self,
        ds: xr.Dataset,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
    ) -> pd.DataFrame:
        """
        Convert xarray Dataset to pandas DataFrame.
        
        If lat/lon are provided, extracts data for the nearest point.
        Otherwise, returns flattened data for all points.
        
        Args:
            ds: xarray Dataset
            lat: Latitude for point extraction (optional)
            lon: Longitude for point extraction (optional)
        
        Returns:
            pandas DataFrame
        """
        if not HAS_XARRAY:
            raise ImportError("xarray is required")
        
        if lat is not None and lon is not None:
            # Extract data for nearest point
            ds_point = ds.sel(latitude=lat, longitude=lon, method='nearest')
            return ds_point.to_dataframe().reset_index()
        else:
            # Return all data as flattened dataframe
            return ds.to_dataframe().reset_index()
    
    def list_variables(self) -> pd.DataFrame:
        """
        List available variables for epidemiological modeling.
        
        Returns:
            DataFrame with variable codes and descriptions
        """
        return pd.DataFrame([
            {'code': k, 'name': v} for k, v in self.VARIABLES.items()
        ])
    
    def list_datasets(self) -> pd.DataFrame:
        """
        List available datasets.
        
        Returns:
            DataFrame with dataset codes and IDs
        """
        return pd.DataFrame([
            {'code': k, 'dataset_id': v} for k, v in self.DATASETS.items()
        ])
    
    def list_areas(self) -> pd.DataFrame:
        """
        List predefined areas.
        
        Returns:
            DataFrame with area names and bounding boxes
        """
        return pd.DataFrame([
            {'name': k, 'bounds': v} for k, v in self.AREAS.items()
        ])
    
    def clear_cache(self):
        """Clear all cached data."""
        import shutil
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Cache cleared")


# ── Convenience Functions ────────────────────────────────────────────────────


def get_climate_data(
    variable: str,
    start_date: str,
    end_date: str,
    area: Optional[Union[str, List[float]]] = None,
    cache_dir: Optional[str] = None,
) -> Union[xr.Dataset, str]:
    """
    Convenience function to get climate data.
    
    Args:
        variable: Variable name (e.g., '2m_temperature')
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        area: Bounding box or predefined area name
        cache_dir: Cache directory path
    
    Returns:
        xarray Dataset with climate data
    """
    cds = CopernicusCDSAccessor(cache_dir=cache_dir)
    return cds.get_era5_data(
        variable=variable,
        start_date=start_date,
        end_date=end_date,
        area=area,
    )


# ── Main ─────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    print("🛰️ Copernicus Climate Data Store (CDS) Accessor")
    print("=" * 60)
    
    try:
        # Initialize accessor
        cds = CopernicusCDSAccessor()
        print("✅ CDS accessor initialized successfully")
        
        # List available variables
        print("\n📋 Available variables:")
        vars_df = cds.list_variables()
        print(vars_df.head(10).to_string(index=False))
        
        # List predefined areas
        print("\n🌍 Predefined areas:")
        areas_df = cds.list_areas()
        print(areas_df.to_string(index=False))
        
        print("\n" + "=" * 60)
        print("To download data, use:")
        print("  >>> data = cds.get_temperature('2024-01-01', '2024-01-31', area='brazil')")
        print("\nNote: Ensure you have accepted the Terms of Use for ERA5")
        print("      at https://cds.climate.copernicus.eu/")
        
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("\nInstall required packages:")
        print("  pip install cdsapi xarray netCDF4 pandas")
        
    except RuntimeError as e:
        print(f"❌ Configuration Error: {e}")
        print("\nTo set up CDS credentials:")
        print("  1. Register at https://cds.climate.copernicus.eu/")
        print("  2. Get your API key from your profile")
        print("  3. Create ~/.cdsapirc with:")
        print("     url: https://cds.climate.copernicus.eu/api")
        print("     key: YOUR_API_KEY")
