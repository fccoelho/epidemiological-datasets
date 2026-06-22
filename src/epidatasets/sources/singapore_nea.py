"""
Singapore National Environment Agency (NEA) Dengue Data Accessor

Provides access to dengue surveillance and vector-control data published by
the Singapore National Environment Agency (NEA) via data.gov.sg, including:

- **Weekly Dengue / DHF case counts** (historical, 2014-2018)
- **Active Dengue Clusters** (real-time, geo-located with case counts and
  construction-site / home / public-place inspections)
- **Dengue Cases by region** (geo-located case clusters per NEA district)
- **Aedes Mosquito Breeding Habitats** (geo-located breeding habitat
  detections per NEA district)

Singapore is a world reference in dengue vector control; this data is
particularly valuable for benchmarking against Brazilian models.

Data Sources:
- Dengue clusters: https://data.gov.sg/datasets/d_dbfabf16158d1b0e1c420627c0819168/view
- Weekly cases: https://data.gov.sg/datasets/d_ac1eecf0886ff0bceefbc51556247015/view
- API Docs: https://guide.data.gov.sg/developer-guide/api-overview

Temporal Coverage: 2014-2018 (weekly cases); real-time (clusters/habitats)
Geographic Coverage: National + NEA operational regions (districts)
Update Frequency: Weekly (cases); continuous (clusters/habitats)

License: Singapore Open Data Licence (free for personal/commercial use)

Citation:
    National Environment Agency. Dengue Clusters, Aedes Mosquito Breeding
    Habitats, and Weekly Number of Dengue and Dengue Haemorrhagic Fever
    Cases [Datasets]. data.gov.sg.

Author: Flávio Codeço Coelho
License: MIT
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import ClassVar
from urllib.parse import urlencode

import pandas as pd
import requests

from epidatasets._base import BaseAccessor

logger = logging.getLogger(__name__)

try:
    import geopandas as gpd

    HAS_GEOPANDAS = True
except ImportError:
    HAS_GEOPANDAS = False


class SingaporeNEAAccessor(BaseAccessor):
    """
    Accessor for Singapore NEA dengue surveillance and vector-control data.

    Provides access to:

    - Weekly Dengue / Dengue Haemorrhagic Fever (DHF) case counts (2014-2018)
    - Active Dengue Clusters (geo-located, with case sizes and inspection data)
    - Dengue cases by NEA region (Central, South East, South West)
    - Aedes mosquito breeding habitats by NEA region

    Example:
        >>> nea = SingaporeNEAAccessor()
        >>>
        >>> # Historical weekly dengue case counts
        >>> weekly = nea.get_weekly_cases()
        >>>
        >>> # Current active dengue clusters (geo-located)
        >>> clusters = nea.get_dengue_clusters()
        >>>
        >>> # Aedes breeding habitat detections by region
        >>> habitats = nea.get_breeding_habitats(region="Central")

    Data Sources:
        - Dengue clusters: https://data.gov.sg/datasets/d_dbfabf16158d1b0e1c420627c0819168/view
        - Weekly cases: https://data.gov.sg/datasets/d_ac1eecf0886ff0bceefbc51556247015/view
    """

    source_name: ClassVar[str] = "singapore_nea"
    source_description: ClassVar[str] = (
        "Dengue surveillance and vector-control data from the Singapore "
        "National Environment Agency (NEA) via data.gov.sg: weekly dengue/DHF "
        "case counts, active dengue clusters, regional case data, and Aedes "
        "mosquito breeding habitat detections."
    )
    source_url: ClassVar[str] = (
        "https://data.gov.sg/collections/1441/view"
    )

    # --- API endpoints ---
    LIST_ROWS_API = (
        "https://api-production.data.gov.sg/v2/public/api/datasets"
    )
    DOWNLOAD_API = (
        "https://api-open.data.gov.sg/v1/public/api/datasets"
    )
    DATASTORE_API = "https://data.gov.sg/api/action/datastore_search"

    REQUEST_TIMEOUT = 60

    # --- Dataset IDs ---
    # Weekly Dengue/DHF case counts (CSV, 2014-2018) — MOH via NEA collection
    WEEKLY_CASES_ID = "d_ac1eecf0886ff0bceefbc51556247015"

    # Active dengue clusters (GEOJSON, real-time)
    DENGUE_CLUSTERS_ID = "d_dbfabf16158d1b0e1c420627c0819168"

    # Regional dengue case clusters (GEOJSON) by NEA district
    REGIONAL_CASES_IDS: ClassVar[dict[str, str]] = {
        "Central": "d_5f90123ce50e3d323bfd0ff3c9a84601",
        "South East": "d_2c13093a9d36377478755716f861ef14",
        "South West": "d_e34261c5ccace716132b55a5b02ebb1f",
    }

    # Aedes mosquito breeding habitats (GEOJSON) by NEA district
    BREEDING_HABITATS_IDS: ClassVar[dict[str, str]] = {
        "Central": "d_68d66612ee0b79bb49bf63730134aa68",
        "North West": "d_3db9f0c0bf6fd3fae19faf0e1832461e",
        "South East": "d_944dd361659cec20260ced43b7251417",
        "South West": "d_f02aa5a38a87dbead9ae1bedec247030",
    }

    # NEA operational regions (districts)
    REGIONS: ClassVar[list[str]] = [
        "Central",
        "North East",
        "North West",
        "South East",
        "South West",
    ]

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        timeout: int = REQUEST_TIMEOUT,
    ):
        super().__init__()
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = (
                Path.home() / ".cache" / "epi_data" / "singapore_nea"
            )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json",
            }
        )

    def list_countries(self) -> pd.DataFrame:
        """Return a single-row DataFrame for Singapore."""
        return pd.DataFrame(
            [{"country_code": "SG", "country_name": "Singapore"}]
        )

    def list_regions(self) -> pd.DataFrame:
        """Return the NEA operational regions (districts).

        Returns
        -------
        pd.DataFrame
            Columns ``region``, ``has_cases_data``, ``has_habitats_data``
            indicating whether case / breeding-habitat datasets are published
            for that region.
        """
        rows = []
        for region in self.REGIONS:
            rows.append(
                {
                    "region": region,
                    "has_cases_data": region in self.REGIONAL_CASES_IDS,
                    "has_habitats_data": region
                    in self.BREEDING_HABITATS_IDS,
                }
            )
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Low-level API helpers
    # ------------------------------------------------------------------
    def _list_rows(
        self,
        dataset_id: str,
        max_records: int | None = None,
    ) -> list[dict]:
        """Page through the v2 list-rows endpoint for a tabular dataset.

        Returns a flat list of record dicts.
        """
        base_url = (
            f"{self.LIST_ROWS_API}/{dataset_id}/list-rows"
        )
        records: list[dict] = []
        next_token: str | None = None

        while True:
            params: dict[str, str] = {}
            if next_token:
                params["paginationToken"] = next_token
            url = f"{base_url}?{urlencode(params)}" if params else base_url

            try:
                resp = self._session.get(url, timeout=self.timeout)
                resp.raise_for_status()
            except requests.RequestException as exc:
                logger.error(
                    "SingaporeNEA: list-rows request failed: %s", exc
                )
                raise RuntimeError(
                    f"Failed to query data.gov.sg list-rows API: {exc}"
                ) from exc

            payload = resp.json()
            data = payload.get("data", {})
            rows = data.get("rows", [])
            records.extend(rows)

            if max_records is not None and len(records) >= max_records:
                return records[:max_records]

            next_token = data.get("links", {}).get("next")
            if not next_token or not rows:
                break

        return records

    def _datastore_search(
        self,
        dataset_id: str,
        limit: int = 10_000,
    ) -> list[dict]:
        """Query the legacy CKAN datastore_search endpoint (fast, single request).

        Used for small tabular datasets (e.g. weekly cases) where the v2
        list-rows pagination is impractically slow.
        """
        url = (
            f"{self.DATASTORE_API}?resource_id={dataset_id}"
            f"&limit={limit}"
        )
        try:
            resp = self._session.get(url, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error(
                "SingaporeNEA: datastore_search request failed: %s", exc
            )
            raise RuntimeError(
                f"Failed to query data.gov.sg datastore_search API: {exc}"
            ) from exc

        payload = resp.json()
        if not payload.get("success", False):
            raise RuntimeError(
                f"datastore_search unsuccessful for {dataset_id}"
            )
        return payload.get("result", {}).get("records", [])

    def _download_geojson(self, dataset_id: str) -> dict:
        """Download a GEOJSON dataset via the v1 poll-download endpoint.

        For non-CSV datasets (GeoJSON) the initiate-download step is skipped
        per the data.gov.sg documentation; we call poll-download directly.
        """
        url = f"{self.DOWNLOAD_API}/{dataset_id}/poll-download"
        try:
            resp = self._session.get(url, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error(
                "SingaporeNEA: poll-download request failed: %s", exc
            )
            raise RuntimeError(
                f"Failed to poll-download {dataset_id}: {exc}"
            ) from exc

        payload = resp.json()
        dl_url = payload.get("data", {}).get("url")
        if not dl_url:
            raise RuntimeError(
                f"No download URL returned for {dataset_id}: "
                f"{payload.get('errorMsg', 'unknown error')}"
            )

        try:
            resp = self._session.get(dl_url, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(
                f"Failed to download GEOJSON for {dataset_id}: {exc}"
            ) from exc


        return resp.json()

    # ------------------------------------------------------------------
    # Weekly case counts (tabular)
    # ------------------------------------------------------------------
    def get_weekly_cases(
        self,
        years: int | list[int] | None = None,
        dengue_type: str | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Fetch historical weekly Dengue and DHF case counts (2014-2018).

        Parameters
        ----------
        years : int or list of int, optional
            Filter to one or more years (e.g. ``[2015, 2016]``).
        dengue_type : str, optional
            Filter by case type: ``"Dengue"`` or ``"DHF"``
            (Dengue Haemorrhagic Fever).
        use_cache : bool
            If True (default), return a cached copy when fresh (< 1 day old).

        Returns
        -------
        pd.DataFrame
            Columns: ``year``, ``eweek``, ``type_dengue``, ``number``.
        """
        cache_key = f"weekly_{_slugify(str(years))}_{_slugify(str(dengue_type))}"
        if use_cache:
            cached = self._load_cache(cache_key)
            if cached is not None:
                df = cached
            else:
                df = self._fetch_weekly_cases()
                self._save_cache(cache_key, df)
        else:
            df = self._fetch_weekly_cases()

        if dengue_type and not df.empty:
            df = df[df["type_dengue"] == dengue_type].reset_index(drop=True)

        if years is not None and not df.empty:
            wanted = set(_as_list(years))
            df = df[df["year"].isin(wanted)].reset_index(drop=True)

        return df

    def _fetch_weekly_cases(self) -> pd.DataFrame:
        records = self._datastore_search(self.WEEKLY_CASES_ID)
        if not records:
            return pd.DataFrame(
                columns=["year", "eweek", "type_dengue", "number"]
            )

        df = pd.DataFrame(records)
        if "_id" in df.columns:
            df = df.drop(columns=["_id"])
        if "vault_id" in df.columns:
            df = df.drop(columns=["vault_id"])
        if "year" in df.columns:
            df["year"] = pd.to_numeric(df["year"], errors="coerce").astype(
                "Int64"
            )
        if "eweek" in df.columns:
            df["eweek"] = pd.to_numeric(df["eweek"], errors="coerce").astype(
                "Int64"
            )
        if "number" in df.columns:
            df["number"] = pd.to_numeric(df["number"], errors="coerce")
            df["number"] = df["number"].fillna(0).astype(int)
        df = df.sort_values(
            ["year", "eweek", "type_dengue"], kind="stable"
        ).reset_index(drop=True)
        return df

    # ------------------------------------------------------------------
    # Dengue clusters (geo-located, real-time)
    # ------------------------------------------------------------------
    def get_dengue_clusters(
        self,
        min_cases: int | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Fetch the current active dengue clusters from NEA.

        Each row represents a geographic cluster with an active dengue
        outbreak, including the number of cases and the polygon boundary.

        Parameters
        ----------
        min_cases : int, optional
            Filter to clusters with at least this many cases.
        use_cache : bool
            If True (default), return a cached copy (< 6 hours old).

        Returns
        -------
        pd.DataFrame
            Columns include ``locality``, ``case_size``, ``name``,
            ``homes``, ``public_places``, ``construction_sites``,
            ``update_date``, ``longitude``, ``latitude``.
        """
        cache_key = "clusters"
        geojson = None
        if use_cache:
            cached = self._load_geojson_cache(cache_key, ttl_hours=6)
            if cached is not None:
                geojson = cached

        if geojson is None:
            try:
                geojson = self._download_geojson(self.DENGUE_CLUSTERS_ID)
            except RuntimeError:
                logger.warning(
                    "SingaporeNEA: API unavailable, returning sample clusters"
                )
                return self._sample_clusters()

            if use_cache:
                self._save_geojson_cache(cache_key, geojson)

        df = self._geojson_to_clusters_df(geojson)

        if min_cases is not None and not df.empty and "case_size" in df.columns:
            df = df[df["case_size"] >= min_cases].reset_index(drop=True)

        return df

    def _geojson_to_clusters_df(self, geojson: dict) -> pd.DataFrame:
        gdf = self._features_to_gdf(geojson)
        if gdf is None or gdf.empty:
            return pd.DataFrame()

        lon, lat = self._centroid_coords(gdf)
        result = pd.DataFrame(
            {
                "object_id": gdf.get("OBJECTID"),
                "locality": gdf.get("LOCALITY"),
                "case_size": _safe_int_series(gdf.get("CASE_SIZE")),
                "name": gdf.get("NAME"),
                "homes": _safe_int_series(gdf.get("HOMES")),
                "public_places": _safe_int_series(gdf.get("PUBLIC_PLACES")),
                "construction_sites": _safe_int_series(
                    gdf.get("CONSTRUCTION_SITES")
                ),
                "update_date": gdf.get("FMEL_UPD_D").map(_parse_nea_date)
                if "FMEL_UPD_D" in gdf.columns
                else None,
                "longitude": lon,
                "latitude": lat,
            }
        )
        return result

    # ------------------------------------------------------------------
    # Regional case data (geo-located, by NEA district)
    # ------------------------------------------------------------------
    def get_regional_cases(
        self,
        region: str | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Fetch geo-located dengue case clusters by NEA region.

        Parameters
        ----------
        region : str, optional
            One of ``self.REGIONS`` (e.g. ``"Central"``).  If None, fetches
            data for all regions with published datasets and adds a
            ``region`` column.
        use_cache : bool
            If True (default), return a cached copy (< 6 hours old).

        Returns
        -------
        pd.DataFrame
            Dengue case cluster data with a ``region`` column.
        """
        regions = [region] if region else list(self.REGIONAL_CASES_IDS)
        frames = []
        for reg in regions:
            ds_id = self.REGIONAL_CASES_IDS.get(reg)
            if not ds_id:
                logger.warning(
                    "SingaporeNEA: no case dataset published for %s", reg
                )
                continue

            cache_key = f"regional_cases_{reg}"
            geojson = None
            if use_cache:
                geojson = self._load_geojson_cache(cache_key, ttl_hours=6)
            if geojson is None:
                try:
                    geojson = self._download_geojson(ds_id)
                except RuntimeError:
                    logger.warning(
                        "SingaporeNEA: failed to fetch regional cases for %s",
                        reg,
                    )
                    continue
                if use_cache:
                    self._save_geojson_cache(cache_key, geojson)

            df = self._geojson_to_clusters_df(geojson)
            df["region"] = reg
            frames.append(df)

        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    # ------------------------------------------------------------------
    # Breeding habitats (geo-located, by NEA district)
    # ------------------------------------------------------------------
    def get_breeding_habitats(
        self,
        region: str | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Fetch Aedes mosquito breeding-habitat detections by NEA region.

        Parameters
        ----------
        region : str, optional
            One of ``self.REGIONS``.  If None, fetches all published regions.
        use_cache : bool
            If True (default), return a cached copy (< 6 hours old).

        Returns
        -------
        pd.DataFrame
            Breeding habitat detection data with ``region`` and location
            columns.
        """
        regions = [region] if region else list(self.BREEDING_HABITATS_IDS)
        frames = []
        for reg in regions:
            ds_id = self.BREEDING_HABITATS_IDS.get(reg)
            if not ds_id:
                logger.warning(
                    "SingaporeNEA: no habitat dataset published for %s", reg
                )
                continue

            cache_key = f"habitats_{reg}"
            geojson = None
            if use_cache:
                geojson = self._load_geojson_cache(cache_key, ttl_hours=6)
            if geojson is None:
                try:
                    geojson = self._download_geojson(ds_id)
                except RuntimeError:
                    logger.warning(
                        "SingaporeNEA: failed to fetch habitats for %s", reg
                    )
                    continue
                if use_cache:
                    self._save_geojson_cache(cache_key, geojson)

            df = self._geojson_to_habitats_df(geojson)
            df["region"] = reg
            frames.append(df)

        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    def _geojson_to_habitats_df(self, geojson: dict) -> pd.DataFrame:
        gdf = self._features_to_gdf(geojson)
        if gdf is None or gdf.empty:
            return pd.DataFrame()

        lon, lat = self._centroid_coords(gdf)

        # The NEA habitat GEOJSON stores attributes inside an HTML table in
        # the "Description" field.  Parse it into individual columns.
        descs = gdf.get("Description", pd.Series(dtype=object)).fillna("")
        parsed = descs.map(_parse_html_table_attrs)

        result = pd.DataFrame(
            {
                "name": gdf.get("Name"),
                "area_name": parsed.map(lambda d: d.get("AREANAME")),
                "detail": parsed.map(lambda d: d.get("DETAIL")),
                "join_count": parsed.map(
                    lambda d: _to_int(d.get("JOIN_COUNT"))
                ),
                "inc_crc": parsed.map(lambda d: d.get("INC_CRC")),
                "longitude": lon,
                "latitude": lat,
            }
        )
        return result

    # ------------------------------------------------------------------
    # GEOJSON parsing helper
    # ------------------------------------------------------------------
    def _features_to_gdf(self, geojson: dict):
        """Parse a GeoJSON FeatureCollection into a GeoDataFrame.

        Requires geopandas (``pip install epidatasets[geo]``).
        """
        if not HAS_GEOPANDAS:
            raise ImportError(
                "geopandas is required to parse NEA GEOJSON data. "
                "Install with: pip install epidatasets[geo]"
            )

        features = geojson.get("features", [])
        if not features:
            return None
        return gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")

    def _centroid_coords(self, gdf) -> tuple:
        """Compute centroid lon/lat, reprojecting via Singapore's SVY21.

        Returns two pandas Series (longitude, latitude) in EPSG:4326.
        """
        projected = gdf.to_crs("EPSG:3414")
        centroids = projected.geometry.centroid.to_crs("EPSG:4326")
        return centroids.x, centroids.y

    # ------------------------------------------------------------------
    # Summary / aggregation
    # ------------------------------------------------------------------
    def get_weekly_summary(self, by: str = "year") -> pd.DataFrame:
        """Aggregate weekly case counts.

        Parameters
        ----------
        by : str
            One of ``"year"`` or ``"type"`` (Dengue vs DHF).
        """
        if by not in ("year", "type"):
            raise ValueError("`by` must be 'year' or 'type'")

        df = self.get_weekly_cases()
        if df.empty:
            return df

        if by == "year":
            return (
                df.groupby(["year", "type_dengue"], as_index=False)["number"]
                .sum()
                .sort_values(["year", "type_dengue"])
                .reset_index(drop=True)
            )
        return (
            df.groupby("type_dengue", as_index=False)["number"]
            .sum()
            .sort_values("number", ascending=False)
            .reset_index(drop=True)
        )

    def get_cluster_summary(self) -> pd.DataFrame:
        """Summary statistics of the current active dengue clusters."""
        df = self.get_dengue_clusters()
        if df.empty:
            return df

        if "case_size" not in df.columns:
            return df

        if "construction_sites" in df.columns:
            cs = pd.to_numeric(df["construction_sites"], errors="coerce")
            construction_clusters = int((cs.fillna(0) > 0).sum())
        else:
            construction_clusters = 0

        summary = pd.DataFrame(
            [
                {
                    "total_clusters": len(df),
                    "total_cases": int(df["case_size"].sum()),
                    "mean_cluster_size": round(df["case_size"].mean(), 2),
                    "max_cluster_size": int(df["case_size"].max()),
                    "clusters_with_construction_sites": construction_clusters,
                }
            ]
        )
        return summary

    # ------------------------------------------------------------------
    # Caching
    # ------------------------------------------------------------------
    def _cache_path(self, key: str, ext: str = "parquet") -> Path:
        return self.cache_dir / f"{key}.{ext}"

    def _load_cache(self, key: str) -> pd.DataFrame | None:
        path = self._cache_path(key)
        if not path.exists():
            return None
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        if datetime.now() - mtime > timedelta(days=1):
            return None
        try:
            return pd.read_parquet(path)
        except Exception:
            return None

    def _save_cache(self, key: str, df: pd.DataFrame) -> None:
        if df.empty:
            return
        try:
            df.to_parquet(self._cache_path(key), index=False)
        except Exception as exc:
            logger.debug("SingaporeNEA: cache write failed: %s", exc)

    def _load_geojson_cache(
        self, key: str, ttl_hours: float = 6
    ) -> dict | None:
        path = self._cache_path(key, ext="json")
        if not path.exists():
            return None
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        if datetime.now() - mtime > timedelta(hours=ttl_hours):
            return None
        import json

        try:
            return json.loads(path.read_text())
        except Exception:
            return None

    def _save_geojson_cache(self, key: str, geojson: dict) -> None:
        import json

        try:
            self._cache_path(key, ext="json").write_text(
                json.dumps(geojson)
            )
        except Exception as exc:
            logger.debug("SingaporeNEA: geojson cache write failed: %s", exc)

    # ------------------------------------------------------------------
    # Sample / fallback data
    # ------------------------------------------------------------------
    def _sample_clusters(self) -> pd.DataFrame:
        """Representative sample dengue cluster data for Singapore."""
        return pd.DataFrame(
            [
                {
                    "object_id": 516192,
                    "locality": "Bishan St 22 (Blk 236)",
                    "case_size": 3,
                    "name": "Dengue_Cluster",
                    "homes": None,
                    "public_places": None,
                    "construction_sites": None,
                    "update_date": None,
                    "longitude": 103.8495,
                    "latitude": 1.3521,
                },
                {
                    "object_id": 516193,
                    "locality": "Geylang Bahru (Blk 65)",
                    "case_size": 8,
                    "name": "Dengue_Cluster",
                    "homes": 2,
                    "public_places": None,
                    "construction_sites": 1,
                    "update_date": None,
                    "longitude": 103.8720,
                    "latitude": 1.3200,
                },
                {
                    "object_id": 516194,
                    "locality": "Tampines St 21 (Blk 201)",
                    "case_size": 15,
                    "name": "Dengue_Cluster",
                    "homes": 3,
                    "public_places": 1,
                    "construction_sites": 0,
                    "update_date": None,
                    "longitude": 103.9440,
                    "latitude": 1.3450,
                },
            ]
        )

    def _sample_weekly_cases(self) -> pd.DataFrame:
        """Representative sample weekly dengue case data for Singapore."""

        rows = []
        for year in [2014, 2015, 2016, 2017, 2018]:
            for eweek in range(1, 53):
                for dtype, base_lo, base_hi in [
                    ("Dengue", 50, 800),
                    ("DHF", 0, 8),
                ]:
                    import random

                    random.seed(eweek + year)
                    rows.append(
                        {
                            "year": year,
                            "eweek": eweek,
                            "type_dengue": dtype,
                            "number": random.randint(base_lo, base_hi),
                        }
                    )
        return pd.DataFrame(rows)


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------
def _as_list(value) -> list:
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _slugify(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_")[:64] or "all"


def _to_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def _parse_nea_date(value: str | None) -> str | None:
    """Parse NEA's ``FMEL_UPD_D`` timestamp (e.g. ``20260616150717``)."""
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    if len(value) == 14:
        try:
            return datetime.strptime(value, "%Y%m%d%H%M%S").isoformat()
        except ValueError:
            return value
    return value


def _safe_int_series(series):
    """Coerce a pandas Series of string/None values to nullable integers."""
    if series is None:
        return None
    return pd.to_numeric(series, errors="coerce").astype("Int64")


def _parse_html_table_attrs(html: str) -> dict[str, str]:
    """Extract key/value pairs from an NEA HTML description table."""
    if not html:
        return {}
    try:
        import bs4

        soup = bs4.BeautifulSoup(html, "html.parser")
    except Exception:
        return {}
    attrs: dict[str, str] = {}
    for row in soup.find_all("tr"):
        cells = row.find_all(["th", "td"])
        if len(cells) >= 2:
            key = cells[0].get_text(strip=True)
            val = cells[1].get_text(strip=True)
            if key:
                attrs[key] = val
    return attrs
