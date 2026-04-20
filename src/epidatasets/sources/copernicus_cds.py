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

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import ClassVar, Dict, List, Optional, Tuple, Union

import pandas as pd

from epidatasets._base import BaseAccessor

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


class CopernicusCDSAccessor(BaseAccessor):
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
        >>> from epidatasets.sources.copernicus_cds import CopernicusCDSAccessor
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

    source_name: ClassVar[str] = "copernicus_cds"
    source_description: ClassVar[str] = (
        "Copernicus Climate Data Store ERA5 reanalysis and climate datasets "
        "for epidemiological modeling and research"
    )
    source_url: ClassVar[str] = "https://cds.climate.copernicus.eu/"
    
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

    # Brazilian state capitals and major cities with coordinates (lat, lon)
    # Format: {city_name: [latitude, longitude, state_code, ibge_code]}
    BRAZIL_CITIES = {
        # State capitals
        'sao_paulo': [-23.5505, -46.6333, 'SP', 3550308],
        'rio_de_janeiro': [-22.9068, -43.1729, 'RJ', 3304557],
        'salvador': [-12.9714, -38.5014, 'BA', 2927408],
        'fortaleza': [-3.7172, -38.5434, 'CE', 2304400],
        'belo_horizonte': [-19.9167, -43.9345, 'MG', 3106200],
        'brasilia': [-15.7975, -47.8919, 'DF', 5300108],
        'curitiba': [-25.4284, -49.2733, 'PR', 4106902],
        'manaus': [-3.1190, -60.0217, 'AM', 1302603],
        'recife': [-8.0476, -34.8770, 'PE', 2611606],
        'porto_alegre': [-30.0346, -51.2177, 'RS', 4314902],
        'belem': [-1.4558, -48.4902, 'PA', 1501402],
        'goiania': [-16.6869, -49.2648, 'GO', 5208707],
        'sao_luis': [-2.5297, -44.3028, 'MA', 2111300],
        'maceio': [-9.6659, -35.7350, 'AL', 2704302],
        'natal': [-5.7793, -35.2009, 'RN', 2408102],
        'teresina': [-5.0892, -42.8019, 'PI', 2211001],
        'campo_grande': [-20.4697, -54.6201, 'MS', 5002704],
        'joao_pessoa': [-7.1150, -34.8641, 'PB', 2507507],
        'aracaju': [-10.9472, -37.0731, 'SE', 2800308],
        'cuiaba': [-15.6014, -56.0979, 'MT', 5103403],
        'florianopolis': [-27.5949, -48.5480, 'SC', 4205407],
        'vitoria': [-20.2976, -40.2958, 'ES', 3205309],
        'porto_velho': [-8.7612, -63.9004, 'RO', 1100205],
        'macapa': [0.0355, -51.0705, 'AP', 1600303],
        'boa_vista': [2.8235, -60.6758, 'RR', 1400100],
        'rio_branco': [-9.9747, -67.8243, 'AC', 1200401],
        'palmas': [-10.1840, -48.3347, 'TO', 1721000],

        # Major non-capital cities (high dengue incidence)
        'campinas': [-22.9053, -47.0659, 'SP', 3509502],
        'santos': [-23.9614, -46.3281, 'SP', 3548500],
        'ribeirao_preto': [-21.1704, -47.8103, 'SP', 3543402],
        'sao_jose_dos_campos': [-23.1794, -45.8868, 'SP', 3549904],
        'sorocaba': [-23.5017, -47.4581, 'SP', 3552205],
        'nova_iguacu': [-22.7590, -43.4511, 'RJ', 3303500],
        'duque_de_caxias': [-22.7868, -43.3131, 'RJ', 3301702],
        'sao_goncalo': [-22.8268, -43.0539, 'RJ', 3304904],
        'feira_de_santana': [-12.2664, -38.9663, 'BA', 2910800],
        'vitoria_da_conquista': [-14.8619, -40.8443, 'BA', 2932907],
        'juazeiro_do_norte': [-7.2247, -39.3136, 'CE', 2307304],
        'petrolina': [-9.3891, -40.5031, 'PE', 2611101],
        'jundiai': [-23.1857, -46.8978, 'SP', 3525904],
        'piracicaba': [-22.7343, -47.6481, 'SP', 3538709],
        'uberlandia': [-18.9186, -48.2772, 'MG', 3170206],
        'contagem': [-19.9386, -44.0529, 'MG', 3118601],
        'betim': [-19.9672, -44.2007, 'MG', 3106705],
        'montes_claros': [-16.7286, -43.8578, 'MG', 3143302],
        'sao_jose_do_rio_preto': [-20.8113, -49.3758, 'SP', 3549805],
        'presidente_prudente': [-22.1256, -51.3889, 'SP', 3541406],
        'londrina': [-23.3045, -51.1696, 'PR', 4113700],
        'maringa': [-23.4205, -51.9333, 'PR', 4115200],
        'foz_do_iguacu': [-25.5163, -54.5854, 'PR', 4108304],
        'joinville': [-26.3044, -48.8464, 'SC', 4209102],
        'blumenau': [-26.9187, -49.0660, 'SC', 4202404],
        'criciuma': [-28.6782, -49.3704, 'SC', 4204608],
        'pelotas': [-31.7719, -52.3425, 'RS', 4314407],
        'caxias_do_sul': [-29.1631, -51.1793, 'RS', 4305108],
        'santa_maria': [-29.6868, -53.8149, 'RS', 4316908],
        'canoas': [-29.9170, -51.1860, 'RS', 4304606],
        'vila_velha': [-20.3417, -40.2871, 'ES', 3205200],
        'serra': [-20.1216, -40.3072, 'ES', 3205002],
        'linhares': [-19.3958, -40.0644, 'ES', 3203205],
        'aracatuba': [-21.2095, -50.4390, 'SP', 3502804],
        'marilia': [-22.2176, -49.9501, 'SP', 3539007],
        'itu': [-23.2642, -47.2992, 'SP', 3523909],
        'barueri': [-23.5112, -46.8762, 'SP', 3505708],
        'diadema': [-23.6819, -46.6203, 'SP', 3513801],
        'maua': [-23.6677, -46.4613, 'SP', 3529401],
        'carapicuiba': [-23.5229, -46.8345, 'SP', 3510609],
        'osasco': [-23.5320, -46.7916, 'SP', 3534401],
        'guarulhos': [-23.4540, -46.5335, 'SP', 3518800],
        'sao_bernardo_do_campo': [-23.6914, -46.5646, 'SP', 3548708],
        'santo_andre': [-23.6739, -46.5369, 'SP', 3547809],
        'sao_caesano_do_sul': [-23.6233, -46.5552, 'SP', 3548807],
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

    # ── City-level Data Methods ─────────────────────────────────────────────

    def get_city_bounding_box(
        self,
        city: str,
        buffer_km: float = 50.0,
    ) -> List[float]:
        """
        Calculate a bounding box around a city.

        Args:
            city: City name (e.g., 'sao_paulo', 'rio_de_janeiro') or IBGE geocode
            buffer_km: Buffer distance in km around the city center (default: 50km)

        Returns:
            Bounding box [North, West, South, East] in degrees

        Example:
            >>> box = cds.get_city_bounding_box('sao_paulo', buffer_km=30)
            >>> print(box)  # [ -23.28, -46.90, -23.82, -46.37]
        """
        # Try to find by IBGE code (numeric string)
        if isinstance(city, str) and city.isdigit():
            geocode = int(city)
            city_data = None
            for name, data in self.BRAZIL_CITIES.items():
                if data[3] == geocode:
                    city_data = data
                    city_name = name
                    break
            if city_data is None:
                raise ValueError(f"City with IBGE geocode {geocode} not found")
        else:
            # Normalize city name
            city_normalized = city.lower().replace(' ', '_').replace('-', '_')
            if city_normalized not in self.BRAZIL_CITIES:
                # Try matching without accents
                from unicodedata import normalize
                city_normalized = normalize('NFKD', city_normalized).encode('ASCII', 'ignore').decode('ASCII')
                if city_normalized not in self.BRAZIL_CITIES:
                    available = list(self.BRAZIL_CITIES.keys())[:10]
                    raise ValueError(
                        f"City '{city}' not found. Try one of: {', '.join(available)}...\n"
                        f"Use list_cities() to see all available cities."
                    )
            city_data = self.BRAZIL_CITIES[city_normalized]
            city_name = city_normalized

        lat, lon = city_data[0], city_data[1]

        # Convert km to degrees (approximate)
        # 1 degree lat ≈ 111 km
        # 1 degree lon ≈ 111 km * cos(lat)
        lat_buffer = buffer_km / 111.0
        lon_buffer = buffer_km / (111.0 * abs(__import__('math').cos(__import__('math').radians(lat))))

        # [North, West, South, East]
        bbox = [
            lat + lat_buffer,   # North
            lon - lon_buffer,   # West
            lat - lat_buffer,   # South
            lon + lon_buffer,   # East
        ]

        logger.info(f"Bounding box for {city_name}: {bbox}")
        return bbox

    def list_cities(
        self,
        state: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        List available Brazilian cities with coordinates.

        Args:
            state: Filter by state code (e.g., 'SP', 'RJ', 'BA')

        Returns:
            DataFrame with city information
        """
        data = []
        for name, info in self.BRAZIL_CITIES.items():
            if state is None or info[2] == state.upper():
                data.append({
                    'name': name.replace('_', ' ').title(),
                    'state': info[2],
                    'ibge_code': info[3],
                    'latitude': info[0],
                    'longitude': info[1],
                })

        df = pd.DataFrame(data)
        if not df.empty:
            df = df.sort_values(['state', 'name'])
        return df

    def list_countries(self) -> pd.DataFrame:
        """
        List countries for which predefined area data is available.

        Returns:
            DataFrame with country/region names and bounding boxes
        """
        return pd.DataFrame(
            [(k, str(v)) for k, v in self.AREAS.items()],
            columns=["region_name", "bounding_box"],
        )

    def get_city_data(
        self,
        city: str,
        variable: Union[str, List[str]],
        start_date: str,
        end_date: str,
        buffer_km: float = 50.0,
        dataset: str = 'era5-single-levels',
        use_cache: bool = True,
        **kwargs
    ) -> Union[xr.Dataset, str]:
        """
        Get climate data for a specific city/municipality.

        Fetches data for a bounding box around the city center.

        Args:
            city: City name (e.g., 'sao_paulo', 'rio_de_janeiro') or IBGE geocode
            variable: Variable name(s) to retrieve
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            buffer_km: Buffer distance in km around city center (default: 50km)
            dataset: Dataset name
            use_cache: Whether to use cached data
            **kwargs: Additional request parameters

        Returns:
            xarray Dataset with climate data for the city area

        Example:
            >>> cds = CopernicusCDSAccessor()
            >>>
            >>> # Get temperature for São Paulo with 30km buffer
            >>> temp_sp = cds.get_city_data(
            ...     city='sao_paulo',
            ...     variable='2m_temperature',
            ...     start_date='2024-01-01',
            ...     end_date='2024-01-31',
            ...     buffer_km=30,
            ... )
            >>>
            >>> # Get data by IBGE geocode
            >>> temp_rj = cds.get_city_data(
            ...     city='3304557',  # Rio de Janeiro geocode
            ...     variable='2m_temperature',
            ...     start_date='2024-01-01',
            ...     end_date='2024-01-31',
            ... )
        """
        # Get bounding box for the city
        bbox = self.get_city_bounding_box(city, buffer_km)

        # Fetch data
        logger.info(f"Fetching data for city '{city}' with {buffer_km}km buffer")
        return self.get_era5_data(
            variable=variable,
            start_date=start_date,
            end_date=end_date,
            area=bbox,
            dataset=dataset,
            use_cache=use_cache,
            **kwargs
        )

    def get_city_temperature(
        self,
        city: str,
        start_date: str,
        end_date: str,
        buffer_km: float = 50.0,
        use_cache: bool = True,
    ) -> Union[xr.Dataset, str]:
        """
        Convenience method to get temperature data for a city.

        Args:
            city: City name or IBGE geocode
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            buffer_km: Buffer distance in km around city center
            use_cache: Whether to use cached data

        Returns:
            xarray Dataset with temperature data for the city

        Example:
            >>> temp = cds.get_city_temperature('sao_paulo', '2024-01-01', '2024-01-31')
        """
        return self.get_city_data(
            city=city,
            variable='2m_temperature',
            start_date=start_date,
            end_date=end_date,
            buffer_km=buffer_km,
            use_cache=use_cache,
        )

    def get_city_precipitation(
        self,
        city: str,
        start_date: str,
        end_date: str,
        buffer_km: float = 50.0,
        use_cache: bool = True,
    ) -> Union[xr.Dataset, str]:
        """
        Convenience method to get precipitation data for a city.

        Args:
            city: City name or IBGE geocode
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            buffer_km: Buffer distance in km around city center
            use_cache: Whether to use cached data

        Returns:
            xarray Dataset with precipitation data for the city
        """
        return self.get_city_data(
            city=city,
            variable='total_precipitation',
            start_date=start_date,
            end_date=end_date,
            buffer_km=buffer_km,
            use_cache=use_cache,
        )

    def get_city_timeseries(
        self,
        city: str,
        variable: str,
        start_date: str,
        end_date: str,
        buffer_km: float = 50.0,
        aggregation: str = 'mean',
        spatial_agg: str = 'mean',
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Get a clean time series DataFrame for a city.

        Convenience method that fetches data, aggregates it spatially and temporally,
        and returns a pandas DataFrame ready for analysis.

        Args:
            city: City name or IBGE geocode
            variable: Variable name (e.g., '2m_temperature')
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            buffer_km: Buffer distance in km around city center
            aggregation: Temporal aggregation ('mean', 'sum', 'min', 'max', 'daily', 'weekly', 'hourly')
            spatial_agg: Spatial aggregation ('mean', 'min', 'max')
            use_cache: Whether to use cached data

        Returns:
            pandas DataFrame with columns: [date, value]

        Example:
            >>> # Daily mean temperature for São Paulo
            >>> df = cds.get_city_timeseries(
            ...     city='sao_paulo',
            ...     variable='2m_temperature',
            ...     start_date='2024-01-01',
            ...     end_date='2024-01-31',
            ...     aggregation='daily',
            ... )
        """
        if not HAS_XARRAY:
            raise ImportError("xarray is required for this method")

        # Fetch data
        ds = self.get_city_data(
            city=city,
            variable=variable,
            start_date=start_date,
            end_date=end_date,
            buffer_km=buffer_km,
            use_cache=use_cache,
        )

        # Spatial aggregation
        if spatial_agg == 'mean':
            ds_spatial = ds.mean(dim=['latitude', 'longitude'])
        elif spatial_agg == 'min':
            ds_spatial = ds.min(dim=['latitude', 'longitude'])
        elif spatial_agg == 'max':
            ds_spatial = ds.max(dim=['latitude', 'longitude'])
        else:
            raise ValueError(f"spatial_agg '{spatial_agg}' not supported. Use: mean, min, max")

        # Temporal aggregation
        if aggregation == 'hourly':
            ds_final = ds_spatial
        elif aggregation == 'daily':
            ds_final = ds_spatial.resample(time='1D').mean()
        elif aggregation == 'weekly':
            ds_final = ds_spatial.resample(time='1W').mean()
        elif aggregation in ['mean', 'sum', 'min', 'max']:
            # These are already done by resample
            ds_final = ds_spatial
        else:
            raise ValueError(f"aggregation '{aggregation}' not supported")

        # Convert to DataFrame
        df = ds_final.to_dataframe().reset_index()

        # Get the variable column name (it varies depending on dataset)
        value_col = [c for c in df.columns if c not in ['time', 'latitude', 'longitude']][0]
        df = df.rename(columns={'time': 'date', value_col: 'value'})

        return df[['date', 'value']]


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
