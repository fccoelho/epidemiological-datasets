"""
OpenDataSUS (Portal de Dados Abertos do SUS) Catalog Accessor

This module provides access to the dataset catalog of the Brazilian Ministry
of Health open-data portal — https://dadosabertos.saude.gov.br/ — allowing
users to list all available datasets, fetch their full metadata, and download
the data resources (files) to disk.

The portal is a Next.js frontend over a CKAN backend.  The public CKAN
action API (``/api/3/action/*``) is not exposed, so this accessor talks to
the Next.js server-rendered data layer:

- Catalog listing:  ``GET /_next/data/<buildId>/dataset.json``
    with query parameters ``q``, ``groups``, ``tags``, ``res_format`` and
    ``page`` (20 rows per page).
- Dataset detail:   ``GET /_next/data/<buildId>/dataset/<slug>.json``
    returning the full CKAN package, including ``resources[]`` (the
    downloadable files, hosted e.g. on ``s3.sa-east-1.amazonaws.com``).

The ``<buildId>`` rotates on every frontend deployment, so it is discovered
at runtime from the homepage ``__NEXT_DATA__`` JSON and cached.

This accessor is complementary to:

- :class:`~epidatasets.sources.demas.DemasAccessor` — the structured DEMAS
  REST API (``apidadosabertos.saude.gov.br/v1``) for querying specific
  datasets;
- :class:`~epidatasets.sources.datasus_pysus.DataSUSAccessor` — the DATASUS
  system via ``pysus``.

Data Sources:
- Portal: https://dadosabertos.saude.gov.br/
- Structured API (covered by DemasAccessor): https://apidadosabertos.saude.gov.br/

Authentication: None required (public portal)
License: Creative Commons Atribuição-SemDerivações 3.0 (portal content)
"""

import json
import logging
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import urlparse

import pandas as pd
import requests

from epidatasets._base import BaseAccessor

logger = logging.getLogger(__name__)

_NEXT_DATA_RE = re.compile(
    r'__NEXT_DATA__"\s+type="application/json">(.*?)</script>', re.DOTALL
)


class OpenDataSUSAccessor(BaseAccessor):
    """
    Accessor for the OpenDataSUS (SUS open-data) dataset catalog.

    Provides access to:
    - The full catalog of datasets (with search and filter by group, tag
      and resource format)
    - Full CKAN package metadata for each dataset (organization, license,
      creation/modification dates, extras, ...)
    - The list of data resources of each dataset, and file downloads to
      disk

    Example:
        >>> from epidatasets.sources.opendatasus import OpenDataSUSAccessor
        >>> acc = OpenDataSUSAccessor()
        >>>
        >>> # List datasets in the "arboviroses" group
        >>> dfs = acc.list_datasets(group="arboviroses")
        >>>
        >>> # Full metadata of a dataset
        >>> meta = acc.get_dataset_metadata("arboviroses-dengue")
        >>>
        >>> # Download all CSV resources of a dataset
        >>> paths = acc.download_dataset("arboviroses-dengue", fmt="CSV")

    Data Sources:
        - Portal: https://dadosabertos.saude.gov.br/
    """

    source_name: ClassVar[str] = "opendatasus"
    source_description: ClassVar[str] = (
        "OpenDataSUS — the catalog of the Brazilian Ministry of Health "
        "open-data portal (dadosabertos.saude.gov.br): list all datasets, "
        "fetch their metadata and download their data resources."
    )
    source_url: ClassVar[str] = "https://dadosabertos.saude.gov.br/"

    BASE_URL: ClassVar[str] = "https://dadosabertos.saude.gov.br"
    PAGE_SIZE: ClassVar[int] = 20

    def __init__(self, cache_dir: str | None = None, cache_ttl_hours: int = 24):
        """
        Initialize the OpenDataSUS accessor.

        Args:
            cache_dir: Directory to cache downloaded data. If None, uses the
                default ``~/.cache/epi_data/opendatasus``.
            cache_ttl_hours: Cache time-to-live in hours. The Next.js
                ``buildId`` and catalog responses are cached for the same
                TTL.
        """
        self.cache_dir = (
            Path(cache_dir)
            if cache_dir
            else Path.home() / ".cache" / "epi_data" / "opendatasus"
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_ttl = timedelta(hours=cache_ttl_hours)
        self._session = requests.Session()
        self._session.headers.update(
            {"User-Agent": "epidatasets-opendatasus-accessor/1.0 (research)"}
        )
        self._build_id: str | None = None

    # ------------------------------------------------------------------
    # Caching helpers
    # ------------------------------------------------------------------
    def _get_cache_path(self, cache_key: str) -> Path:
        return self.cache_dir / f"{cache_key}.json"

    def _is_cache_valid(self, cache_path: Path) -> bool:
        if not cache_path.exists():
            return False
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        return datetime.now() - mtime < self._cache_ttl

    def _read_cache(self, cache_path: Path) -> Any:
        with open(cache_path) as f:
            return json.load(f)

    def _write_cache(self, cache_path: Path, data: Any) -> None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump(data, f)

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------
    def _get_json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        use_cache: bool = True,
        cache_key: str | None = None,
        retries: int = 3,
    ) -> Any:
        """
        Fetch JSON from a URL with caching and retries.

        Args:
            url: Full URL to fetch.
            params: Optional query parameters.
            use_cache: Whether to use the on-disk cache.
            cache_key: Cache file key. If None, derived from the URL +
                params.
            retries: Number of retry attempts on failure.

        Returns:
            Parsed JSON response (dict or list).
        """
        if cache_key is None:
            cache_key = url.replace("https://", "").replace("/", "_").replace(":", "_")
            if params:
                cache_key += "_" + "_".join(
                    f"{k}-{v}" for k, v in sorted(params.items())
                )
        cache_path = self._get_cache_path(cache_key)

        if use_cache and self._is_cache_valid(cache_path):
            logger.info(f"Loading cached data: {cache_path}")
            return self._read_cache(cache_path)

        for attempt in range(retries):
            try:
                logger.info(f"Fetching {url} (attempt {attempt + 1}/{retries})")
                response = self._session.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                if use_cache:
                    self._write_cache(cache_path, data)
                return data
            except requests.exceptions.RequestException as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < retries - 1:
                    time.sleep(2**attempt)
                else:
                    logger.error(f"Failed to fetch {url} after {retries} attempts")
                    raise

        # Unreachable, but satisfies type checkers
        raise RuntimeError("unreachable")

    def _get_build_id(self, use_cache: bool = True) -> str:
        """
        Discover the current Next.js ``buildId`` of the portal.

        The buildId rotates on every frontend deployment, so it is scraped
        from the homepage ``__NEXT_DATA__`` JSON and cached (memory + disk).

        Args:
            use_cache: Whether to use the cached buildId.

        Returns:
            The current buildId string.

        Raises:
            RuntimeError: If the buildId cannot be extracted.
        """
        if self._build_id is not None:
            return self._build_id

        cache_path = self._get_cache_path("build_id")
        if use_cache and self._is_cache_valid(cache_path):
            cached = self._read_cache(cache_path)
            build_id = cached.get("buildId") if isinstance(cached, dict) else None
            if build_id:
                self._build_id = str(build_id)
                return self._build_id

        url = f"{self.BASE_URL}/"
        response = self._session.get(url, timeout=30)
        response.raise_for_status()
        match = _NEXT_DATA_RE.search(response.text)
        if not match:
            raise RuntimeError(
                "Could not extract __NEXT_DATA__ from the OpenDataSUS "
                "homepage; the portal frontend may have changed."
            )
        build_id = json.loads(match.group(1)).get("buildId")
        if not build_id:
            raise RuntimeError(
                "No 'buildId' in the OpenDataSUS homepage __NEXT_DATA__."
            )
        self._build_id = str(build_id)
        self._write_cache(cache_path, {"buildId": self._build_id})
        return self._build_id

    # ------------------------------------------------------------------
    # Abstract method implementation
    # ------------------------------------------------------------------
    def list_countries(self) -> pd.DataFrame:
        """Return a single-row DataFrame for Brazil (portal is Brazil-only)."""
        return pd.DataFrame(
            [("BR", "Brazil")], columns=["country_code", "country_name"]
        )

    # ------------------------------------------------------------------
    # Dataset discovery
    # ------------------------------------------------------------------
    def _search_params(
        self,
        q: str | None = None,
        group: str | None = None,
        tag: str | None = None,
        fmt: str | None = None,
        page: int = 1,
    ) -> dict[str, Any]:
        """Build query parameters for the catalog search endpoint."""
        params: dict[str, Any] = {"page": page}
        if q:
            params["q"] = q
        if group:
            params["groups"] = group
        if tag:
            params["tags"] = tag
        if fmt:
            params["res_format"] = fmt
        return params

    def _fetch_catalog_page(
        self,
        q: str | None = None,
        group: str | None = None,
        tag: str | None = None,
        fmt: str | None = None,
        page: int = 1,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """
        Fetch a single page of the dataset catalog.

        Returns:
            The ``pageProps`` dict of the search page, containing
            ``packages``, ``numberOfPackages``, ``availableFilters`` and
            the pagination fields.
        """
        build_id = self._get_build_id(use_cache=use_cache)
        url = f"{self.BASE_URL}/_next/data/{build_id}/dataset.json"
        params = self._search_params(q, group, tag, fmt, page)
        data = self._get_json(url, params=params, use_cache=use_cache)
        page_props: dict[str, Any] = data.get("pageProps", {})
        if "packages" not in page_props:
            raise RuntimeError(
                "Unexpected catalog response from OpenDataSUS; the portal "
                "frontend data format may have changed."
            )
        return page_props

    @staticmethod
    def _packages_to_frame(packages: list[dict[str, Any]]) -> pd.DataFrame:
        """Normalize a list of catalog packages into a DataFrame."""
        rows = []
        for pkg in packages:
            rows.append(
                {
                    "name": pkg.get("name"),
                    "title": pkg.get("title"),
                    "notes": pkg.get("notes"),
                    "formats": ", ".join(pkg.get("formats") or []),
                    "groups": ", ".join(
                        g.get("display_name") or g.get("name", "")
                        for g in pkg.get("groups") or []
                    ),
                    "tags": ", ".join(
                        t.get("display_name") or t.get("name", "")
                        for t in pkg.get("tags") or []
                    ),
                }
            )
        return pd.DataFrame(rows)

    def list_datasets(
        self,
        q: str | None = None,
        group: str | None = None,
        tag: str | None = None,
        fmt: str | None = None,
        page: int = 1,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        List datasets from the OpenDataSUS catalog (one page).

        Args:
            q: Free-text search query.
            group: Filter by group/theme name (e.g. ``"arboviroses"``).
            tag: Filter by tag name (e.g. ``"covid-19"``).
            fmt: Filter by resource format (e.g. ``"CSV"``).
            page: Page number (20 datasets per page).
            use_cache: Whether to use the on-disk cache.

        Returns:
            DataFrame with columns ``name`` (slug), ``title``, ``notes``
            (description), ``formats``, ``groups`` and ``tags``.
        """
        page_props = self._fetch_catalog_page(
            q=q, group=group, tag=tag, fmt=fmt, page=page, use_cache=use_cache
        )
        return self._packages_to_frame(page_props.get("packages", []))

    def list_datasets_all(
        self,
        q: str | None = None,
        group: str | None = None,
        tag: str | None = None,
        fmt: str | None = None,
        max_pages: int | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        List all datasets matching the filters, fetching every page.

        Args:
            q: Free-text search query.
            group: Filter by group/theme name.
            tag: Filter by tag name.
            fmt: Filter by resource format.
            max_pages: Optional safety cap on the number of pages fetched.
            use_cache: Whether to use the on-disk cache.

        Returns:
            DataFrame with the same columns as :meth:`list_datasets`.
        """
        frames: list[pd.DataFrame] = []
        page = 1
        while True:
            if max_pages is not None and page > max_pages:
                logger.warning(
                    f"Reached max_pages={max_pages}; results may be incomplete."
                )
                break
            page_props = self._fetch_catalog_page(
                q=q, group=group, tag=tag, fmt=fmt, page=page, use_cache=use_cache
            )
            packages = page_props.get("packages", [])
            if not packages:
                break
            frames.append(self._packages_to_frame(packages))
            total = int(page_props.get("numberOfPackages") or 0)
            if page * self.PAGE_SIZE >= total:
                break
            page += 1
        if not frames:
            return pd.DataFrame(
                columns=["name", "title", "notes", "formats", "groups", "tags"]
            )
        return pd.concat(frames, ignore_index=True)

    def list_groups(self, use_cache: bool = True) -> pd.DataFrame:
        """
        List the groups (themes) available in the catalog.

        Args:
            use_cache: Whether to use the on-disk cache.

        Returns:
            DataFrame with columns ``name`` and ``display_name``.
        """
        page_props = self._fetch_catalog_page(use_cache=use_cache)
        groups = page_props.get("availableFilters", {}).get("groups", []) or []
        return pd.DataFrame(
            [
                {"name": g.get("name"), "display_name": g.get("display_name")}
                for g in groups
            ]
        )

    def list_tags(self, use_cache: bool = True) -> pd.DataFrame:
        """
        List the tags available in the catalog.

        Args:
            use_cache: Whether to use the on-disk cache.

        Returns:
            DataFrame with columns ``name`` and ``display_name``.
        """
        page_props = self._fetch_catalog_page(use_cache=use_cache)
        tags = page_props.get("availableFilters", {}).get("tags", []) or []
        return pd.DataFrame(
            [
                {"name": t.get("name"), "display_name": t.get("display_name")}
                for t in tags
            ]
        )

    # ------------------------------------------------------------------
    # Dataset metadata
    # ------------------------------------------------------------------
    def get_dataset(self, slug: str, use_cache: bool = True) -> dict[str, Any]:
        """
        Fetch the full CKAN package (metadata) of a dataset.

        Args:
            slug: Dataset identifier (the ``name`` column of
                :meth:`list_datasets`), e.g. ``"bps"``.
            use_cache: Whether to use the on-disk cache.

        Returns:
            Dict with the full dataset record, including ``resources``.

        Raises:
            KeyError: If the dataset does not exist.
        """
        build_id = self._get_build_id(use_cache=use_cache)
        url = f"{self.BASE_URL}/_next/data/{build_id}/dataset/{slug}.json"
        data = self._get_json(url, params={"slug": slug}, use_cache=use_cache)
        page_props: dict[str, Any] = data.get("pageProps", {})
        if not page_props or "name" not in page_props:
            raise KeyError(f"Dataset '{slug}' not found in the OpenDataSUS catalog.")
        return page_props

    def get_dataset_metadata(self, slug: str, use_cache: bool = True) -> pd.DataFrame:
        """
        Fetch standardized metadata of a dataset as a DataFrame.

        Args:
            slug: Dataset identifier (e.g. ``"bps"``).
            use_cache: Whether to use the on-disk cache.

        Returns:
            DataFrame with columns ``field`` and ``value`` covering title,
            description, organization, license, dates, tags, extras, etc.
        """
        pkg = self.get_dataset(slug, use_cache=use_cache)
        rows = []
        skip = {"resources", "tags", "groups", "extras"}
        for key in sorted(pkg):
            if key in skip:
                continue
            rows.append({"field": key, "value": pkg.get(key)})
        for tag in pkg.get("tags", []) or []:
            rows.append({"field": "tag", "value": tag.get("name")})
        for group in pkg.get("groups", []) or []:
            rows.append({"field": "group", "value": group.get("name")})
        for extra in pkg.get("extras", []) or []:
            rows.append(
                {"field": f"extra:{extra.get('key')}", "value": extra.get("value")}
            )
        return pd.DataFrame(rows, columns=["field", "value"])

    def get_resources(self, slug: str, use_cache: bool = True) -> pd.DataFrame:
        """
        List the data resources (downloadable files) of a dataset.

        Args:
            slug: Dataset identifier (e.g. ``"bps"``).
            use_cache: Whether to use the on-disk cache.

        Returns:
            DataFrame with columns ``resource_id``, ``name``,
            ``description``, ``format``, ``url``, ``size``, ``mimetype``,
            ``last_modified``, ``position``.
        """
        pkg = self.get_dataset(slug, use_cache=use_cache)
        rows = []
        for res in pkg.get("resources", []) or []:
            rows.append(
                {
                    "resource_id": res.get("id"),
                    "name": res.get("name"),
                    "description": res.get("description"),
                    "format": res.get("format"),
                    "url": res.get("url"),
                    "size": res.get("size"),
                    "mimetype": res.get("mimetype"),
                    "last_modified": res.get("last_modified"),
                    "position": res.get("position"),
                }
            )
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Downloads
    # ------------------------------------------------------------------
    @staticmethod
    def _filename_for(resource: dict[str, Any], slug: str, index: int) -> str:
        """Derive a safe filename for a resource download."""
        base = (
            resource.get("name")
            or Path(urlparse(str(resource.get("url", ""))).path).name
            or f"resource_{index}"
        )
        base = re.sub(r"[^\w.\- ]", "_", str(base)).strip() or f"resource_{index}"
        fmt = (resource.get("format") or "").strip().lower()
        if fmt and fmt != "api" and not base.lower().endswith(f".{fmt}"):
            base = f"{base}.{fmt}"
        return base

    def download_resource(
        self,
        slug: str,
        resource_id: str | None = None,
        name: str | None = None,
        fmt: str | None = None,
        dest_dir: str | Path | None = None,
        use_cache: bool = True,
    ) -> Path:
        """
        Download a single resource of a dataset to disk.

        Exactly one selector among ``resource_id`` and ``name`` must be
        given.  Resources with format ``API`` (documentation links) cannot
        be downloaded.

        Args:
            slug: Dataset identifier (e.g. ``"bps"``).
            resource_id: Resource id to download.
            name: Resource name to download.
            fmt: Optional extra filter on resource format.
            dest_dir: Destination directory. If None, uses
                ``<cache_dir>/downloads/<slug>/``.
            use_cache: Whether to use the on-disk cache for metadata.

        Returns:
            Path to the downloaded file.

        Raises:
            ValueError: If the selector is missing/ambiguous or no
                matching downloadable resource is found.
        """
        if (resource_id is None) == (name is None):
            raise ValueError("Provide exactly one of 'resource_id' or 'name'.")
        resources = self.get_resources(slug, use_cache=use_cache)
        if resource_id is not None:
            matches = resources[resources["resource_id"] == resource_id]
        else:
            matches = resources[resources["name"] == name]
        if fmt:
            matches = matches[matches["format"].str.upper() == fmt.upper()]
        matches = matches[matches["format"].str.upper() != "API"]
        if matches.empty:
            raise ValueError(
                f"No downloadable resource matching resource_id={resource_id!r}, "
                f"name={name!r}, fmt={fmt!r} for dataset '{slug}'."
            )
        res = matches.iloc[0]
        url = str(res["url"])
        position = int(res["position"]) if pd.notna(res["position"]) else 0

        filename = self._filename_for(
            {"name": res["name"], "format": res["format"], "url": url},
            slug,
            position,
        )
        dest = Path(dest_dir) if dest_dir else self.cache_dir / "downloads" / slug
        dest.mkdir(parents=True, exist_ok=True)
        dest_path = dest / filename

        logger.info(f"Downloading {url} -> {dest_path}")
        response = self._session.get(url, stream=True, timeout=120)
        response.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1 << 16):
                if chunk:
                    f.write(chunk)
        return dest_path

    def download_dataset(
        self,
        slug: str,
        dest_dir: str | Path | None = None,
        fmt: str | None = None,
        use_cache: bool = True,
    ) -> list[Path]:
        """
        Download all downloadable resources of a dataset.

        Args:
            slug: Dataset identifier (e.g. ``"bps"``).
            dest_dir: Destination directory. If None, uses
                ``<cache_dir>/downloads/<slug>/``.
            fmt: Optional filter on resource format (e.g. ``"CSV"``).
            use_cache: Whether to use the on-disk cache for metadata.

        Returns:
            List of paths to the downloaded files.
        """
        pkg = self.get_dataset(slug, use_cache=use_cache)
        resources = pkg.get("resources", []) or []
        dest = Path(dest_dir) if dest_dir else self.cache_dir / "downloads" / slug
        dest.mkdir(parents=True, exist_ok=True)

        paths: list[Path] = []
        for i, res in enumerate(resources):
            resource_format = (res.get("format") or "").strip().upper()
            if resource_format == "API":
                logger.info(f"Skipping API resource '{res.get('name')}' (not a file).")
                continue
            if fmt and resource_format != fmt.upper():
                continue
            url = str(res.get("url", ""))
            if not url:
                logger.warning(f"Skipping resource without URL: {res.get('name')}")
                continue
            filename = self._filename_for(res, slug, i)
            dest_path = dest / filename
            logger.info(f"Downloading {url} -> {dest_path}")
            response = self._session.get(url, stream=True, timeout=120)
            response.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=1 << 16):
                    if chunk:
                        f.write(chunk)
            paths.append(dest_path)
        if not paths:
            logger.warning(
                f"No downloadable resources found for dataset '{slug}' (fmt={fmt!r})."
            )
        return paths
