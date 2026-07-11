"""
Google Earth Engine (GEE) Accessor

Provides access to planetary-scale satellite imagery for epidemiological
modeling, including Landsat, Sentinel-2, and MODIS derived indicators.

Data Source: https://earthengine.google.com/
API: Earth Engine Python API
Documentation: https://developers.google.com/earth-engine

Requirements:
    - Google account with Earth Engine access (register at
      https://signup.earthengine.google.com/, free for research/nonprofit use)
    - earthengine-api Python library: pip install earthengine-api
    - One-time interactive auth: run `earthengine authenticate` in a shell,
      or call ee.Authenticate() once from Python

Key Datasets:
    - LANDSAT/LC08/C02/T1_L2: Landsat 8 Collection 2, Level 2 (surface reflectance)
    - COPERNICUS/S2_SR_HARMONIZED: Sentinel-2 surface reflectance
    - MODIS/061/MOD13Q1: MODIS vegetation indices (16-day, 250m)
    - USDOS/LSIB_SIMPLE/2017: Simplified country boundaries

Use Cases:
    - Vegetation coverage / mosquito breeding habitat proxy (NDVI)
    - Urban density analysis (NDBI - built-up index)
    - Informal settlement growth / detection (NDBI change over time)
    - Standing water proxy relevant to breeding sites (NDWI)

Notes on quotas:
    This accessor returns *reduced scalar values* (e.g. mean NDVI over a
    region) rather than raw raster exports, to stay well within Earth
    Engine's interactive-use quotas. Raster/export workflows
    (Export.image.toDrive) are intentionally out of scope for this
    accessor and would need separate, explicitly-batched handling.

Author: <KARNAK-OZA>
License: MIT
"""

from __future__ import annotations

import logging
import os
from typing import ClassVar

import pandas as pd

from epidatasets._base import BaseAccessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Optional import - earthengine-api is required only if using this accessor
try:
    import ee

    HAS_EE = True
except ImportError:
    HAS_EE = False
    logger.warning(
        "earthengine-api not installed. Install with: pip install earthengine-api"
    )


class GoogleEarthEngineAccessor(BaseAccessor):
    """
    Accessor for Google Earth Engine (GEE) satellite imagery and derived indices.

    Provides reduced (scalar) indicator values -- NDVI, NDBI, NDWI -- over a
    point or region, for use as features in epidemiological models (e.g.
    vegetation/breeding-site proxies, urban density, settlement growth).

    Setup:
        1. Register at https://signup.earthengine.google.com/
        2. Install earthengine-api: pip install earthengine-api
        3. Authenticate once: run `earthengine authenticate` in a terminal
        4. (Optional) set an EE_PROJECT env var to your GEE cloud project ID

    Example:
        >>> from epidatasets.sources.google_earth_engine import GoogleEarthEngineAccessor
        >>> gee = GoogleEarthEngineAccessor()
        >>>
        >>> # Mean NDVI near Rio de Janeiro over a date range
        >>> ndvi = gee.get_ndvi(
        ...     lon=-43.2, lat=-22.9, buffer_m=10000,
        ...     start_date='2021-03-01', end_date='2021-03-31',
        ... )
        >>>
        >>> # Built-up index (urban density proxy) for the same area
        >>> ndbi = gee.get_built_up_index(
        ...     lon=-43.2, lat=-22.9, buffer_m=10000,
        ...     start_date='2021-03-01', end_date='2021-03-31',
        ... )
    """

    source_name: ClassVar[str] = "google_earth_engine"
    source_description: ClassVar[str] = (
        "Google Earth Engine satellite imagery (Landsat, Sentinel-2, MODIS) "
        "and derived vegetation/built-up indices for epidemiological modeling"
    )
    source_url: ClassVar[str] = "https://earthengine.google.com/"

    # Image collections used by this accessor
    COLLECTIONS = {
        "landsat8_sr": "LANDSAT/LC08/C02/T1_L2",
        "sentinel2_sr": "COPERNICUS/S2_SR_HARMONIZED",
        "modis_vi": "MODIS/061/MOD13Q1",
        "countries": "USDOS/LSIB_SIMPLE/2017",
    }

    # Landsat 8 Collection 2 L2 band names for red/NIR/SWIR
    LANDSAT8_BANDS = {"red": "SR_B4", "nir": "SR_B5", "swir": "SR_B6", "green": "SR_B3"}

    def __init__(
        self,
        project: str | None = None,
        cloud_cover_max: int = 20,
    ):
        """
        Initialize the Google Earth Engine accessor.

        Args:
            project: GEE cloud project ID. Falls back to EE_PROJECT env var.
                Required for accounts registered under the newer
                project-based GEE access model.
            cloud_cover_max: Max acceptable cloud cover percentage (0-100)
                when filtering Landsat/Sentinel-2 image collections.

        Raises:
            ImportError: If earthengine-api is not installed.
            RuntimeError: If Earth Engine initialization fails (e.g. not
                authenticated yet -- run `earthengine authenticate`).
        """
        if not HAS_EE:
            raise ImportError(
                "earthengine-api is required. Install with: "
                "pip install earthengine-api\n"
                "Then run `earthengine authenticate` once in a terminal."
            )

        self.project = project or os.getenv("EE_PROJECT")
        self.cloud_cover_max = cloud_cover_max

        try:
            ee.Initialize(project=self.project)
            logger.info(
                "Earth Engine initialized successfully (project=%s)", self.project
            )
        except Exception as e:
            raise RuntimeError(
                "Failed to initialize Earth Engine. Make sure you've run "
                "`earthengine authenticate` and, if required, set EE_PROJECT "
                f"to a valid GEE cloud project. Original error: {e}"
            ) from e

    # ------------------------------------------------------------------
    # Required by BaseAccessor
    # ------------------------------------------------------------------
    def list_countries(self) -> pd.DataFrame:
        """Return countries available via GEE's simplified LSIB boundaries.

        Returns
        -------
        pd.DataFrame
            Columns ``country_code`` (FIPS 10-4, as provided by LSIB) and
            ``country_name``.
        """
        fc = ee.FeatureCollection(self.COLLECTIONS["countries"])
        names = fc.aggregate_array("country_na").getInfo()
        codes = fc.aggregate_array("country_co").getInfo()
        return pd.DataFrame({"country_code": codes, "country_name": names})

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _aoi(self, lon: float, lat: float, buffer_m: float) -> ee.Geometry:
        return ee.Geometry.Point([lon, lat]).buffer(buffer_m)   # type: ignore[no-any-return]

    def _landsat_composite(
        self, aoi: ee.Geometry, start_date: str, end_date: str
    ) -> ee.Image:
        """Cloud-filtered median composite from Landsat 8 SR over a date range."""
        collection = (
            ee.ImageCollection(self.COLLECTIONS["landsat8_sr"])
            .filterBounds(aoi)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.lt("CLOUD_COVER", self.cloud_cover_max))
        )
        count = collection.size().getInfo()
        if count == 0:
            raise ValueError(
                f"No Landsat 8 images found for this area/date range "
                f"({start_date} to {end_date}) with cloud cover < {self.cloud_cover_max}%. "
                f"Try widening the date range or raising cloud_cover_max."
            )
        return collection.median()  # type: ignore[no-any-return]

    def _reduce_mean(
        self, image: ee.Image, band_name: str, aoi: ee.Geometry, scale: int
    ) -> float | None:
        result = (
            image.select(band_name)
            .reduceRegion(
                reducer=ee.Reducer.mean(), geometry=aoi, scale=scale, maxPixels=1e9
            )
            .get(band_name)
        )
        value = result.getInfo()
        return float(value) if value is not None else None

    # ------------------------------------------------------------------
    # Vegetation coverage / mosquito habitat proxy
    # ------------------------------------------------------------------
    def get_ndvi(
        self,
        lon: float,
        lat: float,
        start_date: str,
        end_date: str,
        buffer_m: float = 10000,
        scale: int = 30,
    ) -> float | None:
        """Mean NDVI over a buffered point -- vegetation coverage proxy
        relevant to mosquito breeding habitat likelihood."""
        aoi = self._aoi(lon, lat, buffer_m)
        image = self._landsat_composite(aoi, start_date, end_date)
        ndvi = image.normalizedDifference(
            [self.LANDSAT8_BANDS["nir"], self.LANDSAT8_BANDS["red"]]
        ).rename("NDVI")
        return self._reduce_mean(ndvi, "NDVI", aoi, scale)

    def get_ndwi(
        self,
        lon: float,
        lat: float,
        start_date: str,
        end_date: str,
        buffer_m: float = 10000,
        scale: int = 30,
    ) -> float | None:
        """Mean NDWI over a buffered point -- standing-water proxy,
        relevant to identifying potential mosquito breeding sites."""
        aoi = self._aoi(lon, lat, buffer_m)
        image = self._landsat_composite(aoi, start_date, end_date)
        ndwi = image.normalizedDifference(
            [self.LANDSAT8_BANDS["green"], self.LANDSAT8_BANDS["nir"]]
        ).rename("NDWI")
        return self._reduce_mean(ndwi, "NDWI", aoi, scale)

    # ------------------------------------------------------------------
    # Urban density / informal settlement detection
    # ------------------------------------------------------------------
    def get_built_up_index(
        self,
        lon: float,
        lat: float,
        start_date: str,
        end_date: str,
        buffer_m: float = 10000,
        scale: int = 30,
    ) -> float | None:
        """Mean NDBI (built-up index) over a buffered point -- urban
        density proxy."""
        aoi = self._aoi(lon, lat, buffer_m)
        image = self._landsat_composite(aoi, start_date, end_date)
        ndbi = image.normalizedDifference(
            [self.LANDSAT8_BANDS["swir"], self.LANDSAT8_BANDS["nir"]]
        ).rename("NDBI")
        return self._reduce_mean(ndbi, "NDBI", aoi, scale)

    def get_built_up_change(
        self,
        lon: float,
        lat: float,
        start_date_before: str,
        end_date_before: str,
        start_date_after: str,
        end_date_after: str,
        buffer_m: float = 10000,
        scale: int = 30,
    ) -> float | None:
        """Change in mean NDBI between two periods -- positive values
        indicate new/growing built-up area, useful as an informal
        settlement growth signal."""
        before = self.get_built_up_index(
            lon, lat, start_date_before, end_date_before, buffer_m, scale
        )
        after = self.get_built_up_index(
            lon, lat, start_date_after, end_date_after, buffer_m, scale
        )
        if before is None or after is None:
            return None
        return after - before
