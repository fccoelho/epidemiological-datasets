"""
Malaria Atlas Project (MAP) Accessor

Provides access to malaria data from the Malaria Atlas Project.
MAP offers parasite rate survey data, vector occurrence data, administrative
boundaries, and modeled raster surfaces of malaria burden and risk.

Data Source: https://data.malariaatlas.org/
Documentation: https://github.com/malaria-atlas-project/malariaAtlas
API: WFS (Web Feature Service) and WCS (Web Coverage Service)

Requirements:
    - No API key required (public data)
    - requests library: pip install requests
    - Optional: geopandas for shapefile handling
    - Optional: rasterio for raster data

Key Datasets:
    - PR survey points (Pf and Pv prevalence rates)
    - Vector occurrence data (Anopheles species)
    - Administrative boundaries (admin0-3)
    - Modeled rasters (PfPR, mortality, incidence)

Use Cases:
    - Malaria prevalence mapping
    - Vector distribution analysis
    - Disease burden estimation
    - Spatial epidemiology research

Author: Flávio Codeço Coelho
License: MIT
"""

from __future__ import annotations

import io
import json
import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union
from urllib.parse import urlencode

import pandas as pd
import requests

# Optional dependencies
HAS_SHAPELY = False
HAS_GEOPANDAS = False
HAS_RASTERIO = False

try:
    import shapely
    HAS_SHAPELY = True
except ImportError:
    pass

try:
    import geopandas as gpd
    HAS_GEOPANDAS = True
except ImportError:
    pass

try:
    import rasterio
    from rasterio.io import MemoryFile
    HAS_RASTERIO = True
except ImportError:
    pass


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MalariaAtlasAccessor:
    """
    Accessor for Malaria Atlas Project data.
    
    Provides methods to fetch:
    - Parasite Rate (PR) survey points
    - Administrative boundaries (shapefiles)
    - Vector occurrence data
    - Raster metadata and downloads
    
    No API key required - all data is publicly available.
    
    Example:
        >>> map_accessor = MalariaAtlasAccessor()
        >>> 
        >>> # Get PR data for Brazil
        >>> pr_brazil = map_accessor.get_pr_data(country="Brazil", species="Pf")
        >>> 
        >>> # Get admin boundaries
        >>> brazil_shp = map_accessor.get_admin_boundaries(iso="BRA", admin_level="admin1")
        >>> 
        >>> # List available rasters
        >>> rasters = map_accessor.list_rasters()
    """
    
    BASE_URL = "https://data.malariaatlas.org/geoserver"
    WFS_URL = f"{BASE_URL}/wfs"
    WMS_URL = f"{BASE_URL}/wms"
    WCS_URL = f"{BASE_URL}/wcs"
    
    # Available workspaces
    WORKSPACES = [
        "Malaria",
        "Interventions", 
        "Blood_Disorders",
        "Accessibility",
        "Vector_Occurrence",
        "Explorer",
        "Admin_Units"
    ]
    
    # Species options
    SPECIES_OPTIONS = ["Pf", "Pv", "BOTH"]
    
    # Admin levels
    ADMIN_LEVELS = ["admin0", "admin1", "admin2", "admin3"]
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize the MAP accessor.
        
        Args:
            cache_dir: Directory for caching data (default: ~/.cache/epidemiological_datasets/malaria_atlas)
        """
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path.home() / ".cache" / "epidemiological_datasets" / "malaria_atlas"
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'EpidemiologicalDatasets-MAP-Accessor/1.0'
        })
        
        logger.info(f"MalariaAtlasAccessor initialized. Cache: {self.cache_dir}")
    
    def _make_request(self, url: str, params: Dict = None, retries: int = 3) -> requests.Response:
        """Make HTTP request with retries."""
        for attempt in range(retries):
            try:
                response = self.session.get(url, params=params, timeout=60)
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException as e:
                if attempt == retries - 1:
                    raise
                logger.warning(f"Request failed (attempt {attempt + 1}): {e}. Retrying...")
                time.sleep(2 ** attempt)
    
    def _wfs_request(self, params: Dict) -> requests.Response:
        """Make WFS request."""
        default_params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
        }
        default_params.update(params)
        return self._make_request(self.WFS_URL, default_params)
    
    # ── Parasite Rate (PR) Data ────────────────────────────────────────────────
    
    def list_pr_versions(self) -> pd.DataFrame:
        """
        List available PR (Parasite Rate) point dataset versions.
        
        Returns:
            DataFrame with version information
        """
        params = {
            "typeName": "Malaria:PR_Data",
            "outputFormat": "application/json",
            "resultType": "hits",
        }
        
        # For versions, we need to check available feature types
        cap_params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetCapabilities",
        }
        
        response = self._make_request(self.WFS_URL, cap_params)
        
        # Parse to find PR data versions
        root = ET.fromstring(response.content)
        
        # WFS namespaces
        ns = {
            'wfs': 'http://www.opengis.net/wfs/2.0',
            'ows': 'http://www.opengis.net/ows/1.1',
        }
        
        versions = []
        for ft in root.findall('.//wfs:FeatureType', ns):
            name = ft.find('wfs:Name', ns)
            if name is not None and 'PR' in name.text:
                title = ft.find('wfs:Title', ns)
                versions.append({
                    'name': name.text,
                    'title': title.text if title is not None else name.text,
                })
        
        return pd.DataFrame(versions)
    
    def get_pr_data(
        self,
        country: Optional[Union[str, List[str]]] = None,
        iso: Optional[Union[str, List[str]]] = None,
        continent: Optional[str] = None,
        species: str = "Pf",
        extent: Optional[List[float]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Get Parasite Rate (PR) survey point data.
        
        PR data contains survey locations with parasite prevalence measurements
        for P. falciparum (Pf) and/or P. vivax (Pv).
        
        Args:
            country: Country name(s) e.g., "Brazil" or ["Brazil", "Colombia"]
            iso: ISO3 code(s) e.g., "BRA" or ["BRA", "COL"]
            continent: Continent name ("Africa", "Americas", "Asia", "Oceania")
            species: "Pf" (P. falciparum), "Pv" (P. vivax), or "BOTH"
            extent: Bounding box [min_lon, min_lat, max_lon, max_lat]
            start_date: Start date filter (YYYY-MM-DD)
            end_date: End date filter (YYYY-MM-DD)
        
        Returns:
            DataFrame with PR point data
        
        Example:
            >>> map_accessor = MalariaAtlasAccessor()
            >>> 
            >>> # Get Pf data for Brazil
            >>> pr_brazil = map_accessor.get_pr_data(iso="BRA", species="Pf")
            >>> 
            >>> # Get data for multiple countries
            >>> pr_data = map_accessor.get_pr_data(
            ...     country=["Nigeria", "Cameroon"],
            ...     species="Pf"
            ... )
        """
        if species not in self.SPECIES_OPTIONS:
            raise ValueError(f"species must be one of {self.SPECIES_OPTIONS}")
        
        # Build CQL filter
        filters = []
        
        if iso:
            if isinstance(iso, str):
                iso = [iso]
            iso_str = "','".join(iso)
            filters.append(f"country_id IN ('{iso_str}')")
        
        if country:
            if isinstance(country, str):
                country = [country]
            country_str = "','".join(country)
            filters.append(f"country IN ('{country_str}')")
        
        if continent:
            filters.append(f"continent_id = '{continent}'")
        
        if extent:
            bbox_filter = f"BBOX(geom, {extent[0]}, {extent[1]}, {extent[2]}, {extent[3]})"
            filters.append(bbox_filter)
        
        if start_date:
            filters.append(f"year_start >= {start_date[:4]}")
        
        if end_date:
            filters.append(f"year_end <= {end_date[:4]}")
        
        # Determine which feature type to use based on species
        if species == "Pf":
            type_name = "Malaria:PR_Pf"
        elif species == "Pv":
            type_name = "Malaria:PR_Pv"
        else:
            type_name = "Malaria:PR_Data"
        
        cql_filter = " AND ".join(filters) if filters else None
        
        params = {
            "typeName": type_name,
            "outputFormat": "application/json",
        }
        
        if cql_filter:
            params["CQL_FILTER"] = cql_filter
        
        logger.info(f"Fetching PR data for {country or iso or continent or 'extent'}")
        
        response = self._wfs_request(params)
        data = response.json()
        
        if 'features' not in data or not data['features']:
            logger.warning("No data returned")
            return pd.DataFrame()
        
        # Convert GeoJSON features to DataFrame
        rows = []
        for feature in data['features']:
            row = feature.get('properties', {}).copy()
            
            # Add geometry if available
            geom = feature.get('geometry')
            if geom and geom.get('type') == 'Point':
                row['longitude'] = geom['coordinates'][0]
                row['latitude'] = geom['coordinates'][1]
            
            rows.append(row)
        
        df = pd.DataFrame(rows)
        
        if df.empty:
            return df
        
        # Rename columns for clarity
        column_mapping = {
            'pf_pr': 'pf_parasite_rate',
            'pv_pr': 'pv_parasite_rate',
            'pf_pos': 'pf_positive',
            'pv_pos': 'pv_positive',
            'examined': 'sample_size',
        }
        
        df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})
        
        logger.info(f"Retrieved {len(df)} PR survey points")
        return df
    
    def get_pr_data_by_extent(
        self,
        min_lon: float,
        min_lat: float,
        max_lon: float,
        max_lat: float,
        species: str = "Pf",
    ) -> pd.DataFrame:
        """
        Get PR data within a bounding box.
        
        Args:
            min_lon: Minimum longitude
            min_lat: Minimum latitude
            max_lon: Maximum longitude
            max_lat: Maximum latitude
            species: "Pf", "Pv", or "BOTH"
        
        Returns:
            DataFrame with PR point data
        """
        extent = [min_lon, min_lat, max_lon, max_lat]
        return self.get_pr_data(extent=extent, species=species)
    
    # ── Administrative Boundaries ─────────────────────────────────────────────
    
    def list_countries(self, admin_level: str = "admin0") -> pd.DataFrame:
        """
        List available countries/administrative units.
        
        Args:
            admin_level: Administrative level ("admin0", "admin1", "admin2")
        
        Returns:
            DataFrame with available countries and ISO codes
        """
        if admin_level not in self.ADMIN_LEVELS:
            raise ValueError(f"admin_level must be one of {self.ADMIN_LEVELS}")
        
        params = {
            "typeName": f"Admin_Units:mapadmin_{admin_level}",
            "outputFormat": "application/json",
            "propertyName": "iso,name_0,admn_level",
        }
        
        response = self._wfs_request(params)
        data = response.json()
        
        rows = []
        for feature in data.get('features', []):
            props = feature.get('properties', {})
            rows.append({
                'iso': props.get('iso'),
                'name': props.get('name_0'),
                'admin_level': props.get('admn_level'),
            })
        
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.drop_duplicates().sort_values('name')
        
        return df
    
    def get_admin_boundaries(
        self,
        country: Optional[Union[str, List[str]]] = None,
        iso: Optional[Union[str, List[str]]] = None,
        admin_level: Union[str, List[str]] = "admin0",
        extent: Optional[List[float]] = None,
    ) -> Union[pd.DataFrame, 'gpd.GeoDataFrame']:
        """
        Get administrative boundary shapefiles.
        
        Args:
            country: Country name(s)
            iso: ISO3 code(s)
            admin_level: Administrative level ("admin0", "admin1", "admin2", "admin3", or list)
            extent: Bounding box [min_lon, min_lat, max_lon, max_lat]
        
        Returns:
            GeoDataFrame if geopandas available, else DataFrame
        
        Example:
            >>> map_accessor = MalariaAtlasAccessor()
            >>> 
            >>> # Get Brazil states
            >>> brazil_states = map_accessor.get_admin_boundaries(iso="BRA", admin_level="admin1")
            >>> 
            >>> # Get multiple countries
            >>> countries = map_accessor.get_admin_boundaries(
            ...     iso=["BRA", "COL", "PER"],
            ...     admin_level="admin0"
            ... )
        """
        # Handle admin_level
        if isinstance(admin_level, str) and admin_level == "all":
            admin_level = ["admin0", "admin1", "admin2", "admin3"]
        elif isinstance(admin_level, str):
            admin_level = [admin_level]
        
        invalid_levels = set(admin_level) - set(self.ADMIN_LEVELS)
        if invalid_levels:
            raise ValueError(f"Invalid admin_level: {invalid_levels}")
        
        # Build CQL filter
        filters = []
        
        if iso:
            if isinstance(iso, str):
                iso = [iso]
            iso_str = "','".join(iso)
            filters.append(f"iso IN ('{iso_str}')")
        
        if country:
            if isinstance(country, str):
                country = [country]
            country_str = "','".join(country)
            filters.append(f"name_0 IN ('{country_str}')")
        
        if extent:
            bbox_filter = f"BBOX(geom, {extent[0]}, {extent[1]}, {extent[2]}, {extent[3]})"
            filters.append(bbox_filter)
        
        cql_filter = " AND ".join(filters) if filters else None
        
        all_features = []
        
        for level in admin_level:
            params = {
                "typeName": f"Admin_Units:mapadmin_{level}",
                "outputFormat": "application/json",
            }
            
            if cql_filter:
                params["CQL_FILTER"] = cql_filter
            
            logger.info(f"Fetching {level} boundaries")
            response = self._wfs_request(params)
            data = response.json()
            all_features.extend(data.get('features', []))
        
        if not all_features:
            logger.warning("No boundary data returned")
            return pd.DataFrame()
        
        # Convert to DataFrame or GeoDataFrame
        if HAS_GEOPANDAS:
            import shapely.geometry
            
            rows = []
            geometries = []
            
            for feature in all_features:
                props = feature.get('properties', {})
                geom = feature.get('geometry')
                
                if geom:
                    try:
                        geometries.append(shapely.geometry.shape(geom))
                        rows.append(props)
                    except Exception as e:
                        logger.warning(f"Could not parse geometry: {e}")
            
            gdf = gpd.GeoDataFrame(rows, geometry=geometries, crs="EPSG:4326")
            logger.info(f"Retrieved {len(gdf)} administrative boundaries")
            return gdf
        else:
            # Return as regular DataFrame without geometry
            rows = []
            for feature in all_features:
                props = feature.get('properties', {})
                rows.append(props)
            
            df = pd.DataFrame(rows)
            logger.info(f"Retrieved {len(df)} administrative boundaries (install geopandas for geometry)")
            return df
    
    # ── Vector Occurrence Data ───────────────────────────────────────────────
    
    def list_vector_species(self) -> pd.DataFrame:
        """
        List available mosquito vector species.
        
        Returns:
            DataFrame with vector species information
        """
        params = {
            "typeName": "Vector_Occurrence:Vector_Occurrence",
            "outputFormat": "application/json",
            "propertyName": "species",
            "maxFeatures": 10000,
        }
        
        response = self._wfs_request(params)
        data = response.json()
        
        species_list = []
        for feature in data.get('features', []):
            species = feature.get('properties', {}).get('species')
            if species:
                species_list.append(species)
        
        unique_species = sorted(set(species_list))
        
        return pd.DataFrame({
            'species': unique_species,
        })
    
    def get_vector_occurrence(
        self,
        species: Optional[Union[str, List[str]]] = None,
        country: Optional[str] = None,
        iso: Optional[str] = None,
        extent: Optional[List[float]] = None,
    ) -> pd.DataFrame:
        """
        Get mosquito vector occurrence data.
        
        Args:
            species: Vector species name(s) e.g., "Anopheles gambiae"
            country: Country name
            iso: ISO3 code
            extent: Bounding box [min_lon, min_lat, max_lon, max_lat]
        
        Returns:
            DataFrame with vector occurrence points
        
        Example:
            >>> map_accessor = MalariaAtlasAccessor()
            >>> 
            >>> # Get Anopheles gambiae occurrences in Africa
            >>> vectors = map_accessor.get_vector_occurrence(
            ...     species="Anopheles gambiae",
            ...     iso="BRA"
            ... )
        """
        filters = []
        
        if species:
            if isinstance(species, str):
                species = [species]
            species_str = "','".join(species)
            filters.append(f"species IN ('{species_str}')")
        
        if country:
            filters.append(f"country = '{country}'")
        
        if iso:
            filters.append(f"country_id = '{iso}'")
        
        if extent:
            bbox_filter = f"BBOX(geom, {extent[0]}, {extent[1]}, {extent[2]}, {extent[3]})"
            filters.append(bbox_filter)
        
        cql_filter = " AND ".join(filters) if filters else None
        
        params = {
            "typeName": "Vector_Occurrence:Vector_Occurrence",
            "outputFormat": "application/json",
        }
        
        if cql_filter:
            params["CQL_FILTER"] = cql_filter
        
        logger.info(f"Fetching vector occurrence data")
        
        response = self._wfs_request(params)
        data = response.json()
        
        rows = []
        for feature in data.get('features', []):
            row = feature.get('properties', {}).copy()
            
            geom = feature.get('geometry')
            if geom and geom.get('type') == 'Point':
                row['longitude'] = geom['coordinates'][0]
                row['latitude'] = geom['coordinates'][1]
            
            rows.append(row)
        
        df = pd.DataFrame(rows)
        logger.info(f"Retrieved {len(df)} vector occurrence records")
        return df
    
    # ── Raster Data ───────────────────────────────────────────────────────────
    
    def list_rasters(self, workspace: Optional[str] = None) -> pd.DataFrame:
        """
        List available raster datasets.
        
        Args:
            workspace: Filter by workspace (e.g., "Malaria", "Vector_Occurrence")
        
        Returns:
            DataFrame with raster dataset information
        """
        params = {
            "service": "WCS",
            "version": "2.0.1",
            "request": "GetCapabilities",
        }
        
        response = self._make_request(self.WCS_URL, params)
        root = ET.fromstring(response.content)
        
        # WCS namespaces
        ns = {
            'wcs': 'http://www.opengis.net/wcs/2.0',
            'ows': 'http://www.opengis.net/ows/2.0',
        }
        
        rasters = []
        for coverage in root.findall('.//wcs:CoverageDescription', ns):
            coverage_id = coverage.find('wcs:CoverageId', ns)
            if coverage_id is None:
                continue
            
            dataset_id = coverage_id.text
            
            # Parse dataset_id to extract workspace and name
            if '__' in dataset_id:
                parts = dataset_id.split('__')
                ws = parts[0]
                name = '__'.join(parts[1:])
            else:
                ws = "Unknown"
                name = dataset_id
            
            if workspace and ws != workspace:
                continue
            
            # Get metadata
            metadata = coverage.find('.//ows:Metadata', ns)
            title = coverage.find('.//ows:Title', ns)
            abstract = coverage.find('.//ows:Abstract', ns)
            
            rasters.append({
                'dataset_id': dataset_id,
                'workspace': ws,
                'name': name,
                'title': title.text if title is not None else name,
                'abstract': abstract.text if abstract is not None else None,
            })
        
        df = pd.DataFrame(rasters)
        if not df.empty:
            df = df.sort_values(['workspace', 'name'])
        
        return df
    
    def get_raster_info(self, dataset_id: str) -> Dict:
        """
        Get metadata for a specific raster dataset.
        
        Args:
            dataset_id: Raster dataset ID
        
        Returns:
            Dictionary with raster metadata
        """
        params = {
            "service": "WCS",
            "version": "2.0.1",
            "request": "DescribeCoverage",
            "coverageId": dataset_id,
        }
        
        response = self._make_request(self.WCS_URL, params)
        root = ET.fromstring(response.content)
        
        ns = {
            'wcs': 'http://www.opengis.net/wcs/2.0',
            'gml': 'http://www.opengis.net/gml/3.2',
            'ows': 'http://www.opengis.net/ows/2.0',
        }
        
        info = {
            'dataset_id': dataset_id,
        }
        
        # Get bounding box
        bbox = root.find('.//gml:Envelope', ns)
        if bbox is not None:
            lc = bbox.find('.//gml:lowerCorner', ns)
            uc = bbox.find('.//gml:upperCorner', ns)
            if lc is not None and uc is not None:
                info['bbox'] = {
                    'lower': lc.text,
                    'upper': uc.text,
                }
        
        # Get grid dimensions
        grid = root.find('.//gml:RectifiedGrid', ns)
        if grid is not None:
            limits = grid.find('.//gml:GridEnvelope', ns)
            if limits is not None:
                low = limits.find('.//gml:low', ns)
                high = limits.find('.//gml:high', ns)
                if low is not None and high is not None:
                    info['grid_limits'] = {
                        'low': low.text,
                        'high': high.text,
                    }
        
        return info
    
    def download_raster(
        self,
        dataset_id: str,
        extent: Optional[List[float]] = None,
        year: Optional[int] = None,
        output_path: Optional[str] = None,
    ) -> Optional['rasterio.DatasetReader']:
        """
        Download a raster dataset.
        
        Args:
            dataset_id: Raster dataset ID from list_rasters()
            extent: Bounding box [min_lon, min_lat, max_lon, max_lat]
            year: Year for time-varying rasters
            output_path: Path to save raster file (optional)
        
        Returns:
            Rasterio dataset if rasterio available, else None
        
        Example:
            >>> map_accessor = MalariaAtlasAccessor()
            >>> 
            >>> # List available rasters
            >>> rasters = map_accessor.list_rasters()
            >>> 
            >>> # Download PfPR raster for Brazil
            >>> raster = map_accessor.download_raster(
            ...     dataset_id="Malaria__202206_Global_Pf_Parasite_Rate",
            ...     extent=[-74, -34, -34, 5],  # Brazil bbox
            ...     output_path="pfpr_brazil.tif"
            ... )
        """
        if not HAS_RASTERIO:
            logger.warning("rasterio not installed. Install with: pip install rasterio")
            return None
        
        # Build WCS GetCoverage request
        params = {
            "service": "WCS",
            "version": "2.0.1",
            "request": "GetCoverage",
            "coverageId": dataset_id,
            "format": "image/tiff",
        }
        
        if extent:
            # WCS uses subset parameters
            params['subset'] = [
                f"Long({extent[0]},{extent[2]})",
                f"Lat({extent[1]},{extent[3]})",
            ]
        
        if year:
            params['subset'] = params.get('subset', []) + [f"time({year}-01-01T00:00:00)"]
        
        logger.info(f"Downloading raster: {dataset_id}")
        
        response = self._make_request(self.WCS_URL, params)
        
        # Save to file or return in-memory
        if output_path:
            with open(output_path, 'wb') as f:
                f.write(response.content)
            logger.info(f"Raster saved to: {output_path}")
            return rasterio.open(output_path)
        else:
            # Return in-memory dataset
            with MemoryFile(response.content) as memfile:
                return memfile.open()
    
    # ── Utility Methods ───────────────────────────────────────────────────────
    
    def search_data(self, query: str) -> pd.DataFrame:
        """
        Search for datasets by keyword.
        
        Args:
            query: Search term
        
        Returns:
            DataFrame with matching datasets
        """
        rasters = self.list_rasters()
        
        # Filter by query
        mask = (
            rasters['name'].str.contains(query, case=False, na=False) |
            rasters['title'].str.contains(query, case=False, na=False) |
            rasters['abstract'].str.contains(query, case=False, na=False)
        )
        
        return rasters[mask]
    
    def clear_cache(self):
        """Clear cached data."""
        import shutil
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Cache cleared")


# ── Convenience Functions ────────────────────────────────────────────────────

def get_malaria_pr(country: str, species: str = "Pf") -> pd.DataFrame:
    """
    Convenience function to get PR data for a country.
    
    Args:
        country: Country name
        species: "Pf", "Pv", or "BOTH"
    
    Returns:
        DataFrame with PR point data
    """
    accessor = MalariaAtlasAccessor()
    return accessor.get_pr_data(country=country, species=species)


def get_admin_boundaries(iso: str, admin_level: str = "admin0") -> Union[pd.DataFrame, 'gpd.GeoDataFrame']:
    """
    Convenience function to get administrative boundaries.
    
    Args:
        iso: ISO3 country code
        admin_level: Administrative level
    
    Returns:
        GeoDataFrame or DataFrame with boundaries
    """
    accessor = MalariaAtlasAccessor()
    return accessor.get_admin_boundaries(iso=iso, admin_level=admin_level)


def list_map_rasters(workspace: Optional[str] = None) -> pd.DataFrame:
    """
    Convenience function to list available rasters.
    
    Args:
        workspace: Filter by workspace
    
    Returns:
        DataFrame with raster information
    """
    accessor = MalariaAtlasAccessor()
    return accessor.list_rasters(workspace=workspace)


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Demo
    print("Malaria Atlas Project Accessor Demo")
    print("=" * 50)
    
    accessor = MalariaAtlasAccessor()
    
    # List available countries
    print("\n1. Listing available countries:")
    countries = accessor.list_countries(admin_level="admin0")
    print(f"   Found {len(countries)} countries")
    print(f"   Sample: {countries.head()['name'].tolist()}")
    
    # Get PR data for a country
    print("\n2. Getting PR data for Brazil:")
    try:
        pr_data = accessor.get_pr_data(iso="BRA", species="Pf")
        print(f"   Found {len(pr_data)} PR survey points")
        if not pr_data.empty:
            print(f"   Columns: {pr_data.columns.tolist()[:5]}...")
    except Exception as e:
        print(f"   Error: {e}")
    
    # List vector species
    print("\n3. Listing vector species:")
    try:
        vectors = accessor.list_vector_species()
        print(f"   Found {len(vectors)} vector species")
        print(f"   Sample: {vectors.head()['species'].tolist()}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # List rasters
    print("\n4. Listing available rasters:")
    try:
        rasters = accessor.list_rasters(workspace="Malaria")
        print(f"   Found {len(rasters)} rasters in Malaria workspace")
        if not rasters.empty:
            print(f"   Sample: {rasters.head()['title'].tolist()}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "=" * 50)
    print("Demo complete!")
