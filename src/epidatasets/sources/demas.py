"""
DEMAS (Portal de Dados Abertos do SUS) Accessor

This module provides access to the Brazilian Ministry of Health's open data
portal — DEMAS (Departamento de Monitoramento do SUS) — via its public REST
API.

The portal exposes 80+ per-dataset endpoints (arboviroses, vacinação, CNES,
SISAGUA, saúde indígena, vigilância ambiental, etc.) documented through an
OpenAPI/Swagger 2.0 specification.  No API key is required for public
endpoints.

Data Sources:
- Portal: https://dadosabertos.saude.gov.br/
- API: https://apidadosabertos.saude.gov.br/
- Swagger spec: https://apidadosabertos.saude.gov.br/static/swagger.json

Coverage:
- Arboviroses: dengue, chikungunya, zikavirus, febre amarela
- Vacinação: PNI doses aplicadas (2020-2026), ESAVI, insumos estratégicos
- Vigilância: mpox, síndrome gripal leve
- CNES, SISAGUA, SISVAN, atenção primária, saúde indígena, and more

Pagination: ``limit`` (server-capped at 20) + ``offset`` (page number, 0-indexed).

License: Open government data (Dados Abertos do SUS)
Author: Flávio Codeço Coelho
License: MIT
"""

import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar

import pandas as pd
import requests

from epidatasets._base import BaseAccessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DemasAccessor(BaseAccessor):
    """
    Accessor for the DEMAS Portal de Dados Abertos do SUS.

    Provides access to 80+ Brazilian Ministry of Health open datasets via the
    public REST API.  Dataset discovery is driven by the API's OpenAPI/Swagger
    specification — there is no generic CKAN ``package_search``; instead each
    dataset has a dedicated endpoint (e.g. ``/arboviroses/dengue``).

    The API caps page size at 20 records and uses ``offset`` as a 0-indexed
    page number.  By default :meth:`get_dataset` fetches a single page for
    quick inspection; use :meth:`get_dataset_all` to page through all records
    (with a ``max_pages`` guard for large datasets).

    Example:
        >>> from epidatasets.sources.demas import DemasAccessor
        >>> demas = DemasAccessor()
        >>>
        >>> # Discover available datasets
        >>> datasets = demas.list_datasets(domain="Agravo Arboviroses")
        >>>
        >>> # Search by keyword
        >>> matches = demas.search_datasets("dengue")
        >>>
        >>> # Fetch a single page of dengue records
        >>> df = demas.get_dataset("/arboviroses/dengue", year=2024)
        >>>
        >>> # Fetch all records (with a page guard)
        >>> df_all = demas.get_dataset_all("/arboviroses/dengue", max_pages=50)

    Data Sources:
        - Portal: https://dadosabertos.saude.gov.br/
        - API: https://apidadosabertos.saude.gov.br/
    """

    source_name: ClassVar[str] = "demas"
    source_description: ClassVar[str] = (
        "DEMAS — Portal de Dados Abertos do SUS (Brazilian Ministry of Health). "
        "80+ public health datasets including arboviroses, vacinação, CNES, "
        "SISAGUA, vigilância ambiental and saúde indígena."
    )
    source_url: ClassVar[str] = "https://dadosabertos.saude.gov.br/"

    BASE_URL: ClassVar[str] = "https://apidadosabertos.saude.gov.br"
    SWAGGER_URL: ClassVar[str] = f"{BASE_URL}/static/swagger.json"
    MAX_PAGE_SIZE: ClassVar[int] = 20

    def __init__(self, cache_dir: str | None = None, cache_ttl_hours: int = 24):
        """
        Initialize the DEMAS accessor.

        Args:
            cache_dir: Directory to cache downloaded data. If None, uses the
                default ``~/.cache/epi_data/demas``.
            cache_ttl_hours: Cache time-to-live in hours. The swagger spec is
                cached for the same TTL.
        """
        self.cache_dir = (
            Path(cache_dir)
            if cache_dir
            else Path.home() / ".cache" / "epi_data" / "demas"
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_ttl = timedelta(hours=cache_ttl_hours)
        self._session = requests.Session()
        self._session.headers.update(
            {"User-Agent": "epidatasets-demas-accessor/1.0 (research)"}
        )
        self._swagger: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # Caching helpers
    # ------------------------------------------------------------------
    def _get_cache_path(self, cache_key: str, suffix: str = "json") -> Path:
        return self.cache_dir / f"{cache_key}.{suffix}"

    def _is_cache_valid(self, cache_path: Path) -> bool:
        if not cache_path.exists():
            return False
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        return datetime.now() - mtime < self._cache_ttl

    def _read_cache(self, cache_path: Path) -> Any:
        import json

        with open(cache_path) as f:
            return json.load(f)

    def _write_cache(self, cache_path: Path, data: Any) -> None:
        import json

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump(data, f)

    # ------------------------------------------------------------------
    # HTTP helper
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
            cache_key: Cache file key. If None, derived from the URL + params.
            retries: Number of retry attempts on failure.
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

    # ------------------------------------------------------------------
    # Swagger spec (the dataset catalog)
    # ------------------------------------------------------------------
    def _load_swagger(self, use_cache: bool = True) -> dict[str, Any]:
        """Fetch (and cache) the OpenAPI/Swagger specification."""
        if self._swagger is not None:
            return self._swagger
        self._swagger = self._get_json(
            self.SWAGGER_URL, use_cache=use_cache, cache_key="swagger_spec"
        )
        return self._swagger

    # ------------------------------------------------------------------
    # Abstract method implementation
    # ------------------------------------------------------------------
    def list_countries(self) -> pd.DataFrame:
        """Return a single-row DataFrame for Brazil (DEMAS is Brazil-only)."""
        return pd.DataFrame(
            [("BR", "Brazil")], columns=["country_code", "country_name"]
        )

    # ------------------------------------------------------------------
    # Dataset discovery
    # ------------------------------------------------------------------
    def list_domains(self, use_cache: bool = True) -> pd.DataFrame:
        """
        List the dataset domains (Swagger tags).

        Returns
        -------
        pd.DataFrame
            Columns ``domain`` and ``description``.
        """
        swagger = self._load_swagger(use_cache=use_cache)
        tags = swagger.get("tags", []) or []
        rows = [
            {"domain": t.get("name"), "description": t.get("description", "")}
            for t in tags
        ]
        return pd.DataFrame(rows)

    def list_datasets(
        self,
        domain: str | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        List all available DEMAS datasets (GET endpoints from the Swagger spec).

        Args:
            domain: Optional domain/tag filter (e.g. ``"Agravo Arboviroses"``).
                If None, returns all datasets.
            use_cache: Whether to use cached swagger spec.

        Returns
        -------
        pd.DataFrame
            Columns ``domain``, ``endpoint``, ``summary``, ``has_year_filter``,
            ``query_params``.
        """
        swagger = self._load_swagger(use_cache=use_cache)
        paths = swagger.get("paths", {}) or {}
        rows = []
        for path, methods in paths.items():
            get = methods.get("get")
            if get is None:
                continue
            tags = get.get("tags") or [""]
            tag = tags[0]
            if domain is not None and tag != domain:
                continue
            params = get.get("parameters", []) or []
            query_params = [p["name"] for p in params if p.get("in") == "query"]
            rows.append(
                {
                    "domain": tag,
                    "endpoint": path,
                    "summary": get.get("summary", ""),
                    "has_year_filter": "nu_ano" in query_params,
                    "query_params": ", ".join(query_params),
                }
            )
        return pd.DataFrame(rows)

    def search_datasets(
        self,
        keyword: str,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Search datasets by keyword (case-insensitive) in endpoint path or summary.

        Args:
            keyword: Search term (e.g. ``"dengue"``, ``"vacinação"``).
            use_cache: Whether to use cached swagger spec.

        Returns
        -------
        pd.DataFrame
            Filtered dataset listing.
        """
        df = self.list_datasets(use_cache=use_cache)
        if df.empty:
            return df
        mask = (
            df["endpoint"].str.contains(keyword, case=False, na=False)
            | df["summary"].str.contains(keyword, case=False, na=False)
            | df["domain"].str.contains(keyword, case=False, na=False)
        )
        return df[mask].reset_index(drop=True)

    # ------------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_records(data: Any) -> list[dict[str, Any]]:
        """
        Extract the list of records from a DEMAS response.

        Each endpoint returns a dict with a single endpoint-specific list key
        (e.g. ``{"parametros": [...]}``, ``{"doses_aplicadas_pni": [...]}``).
        This helper returns the first list value found.
        """
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for value in data.values():
                if isinstance(value, list):
                    return value
        return []

    def get_dataset(
        self,
        endpoint: str,
        year: int | None = None,
        limit: int = 20,
        offset: int = 0,
        path_params: dict[str, Any] | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Fetch a single page of records from a DEMAS dataset endpoint.

        Args:
            endpoint: API path (e.g. ``"/arboviroses/dengue"``).
            year: Optional year filter (``nu_ano``) for endpoints that support it.
            limit: Page size (server-capped at 20).
            offset: Page number (0-indexed).
            path_params: Optional values for path parameters
                (e.g. ``{"codigo_cnes": 12345}`` for ``/cnes/estabelecimentos/{codigo_cnes}``).
            use_cache: Whether to use cached data.

        Returns
        -------
        pd.DataFrame
            One page of records.
        """
        path = self._fill_path_params(endpoint, path_params)
        params: dict[str, Any] = {
            "limit": min(limit, self.MAX_PAGE_SIZE),
            "offset": offset,
        }
        if year is not None:
            params["nu_ano"] = str(year)

        url = f"{self.BASE_URL}{path}"
        data = self._get_json(url, params=params, use_cache=use_cache)
        records = self._extract_records(data)
        return pd.DataFrame(records)

    def get_dataset_all(
        self,
        endpoint: str,
        year: int | None = None,
        max_pages: int | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Fetch all records from a DEMAS dataset by paginating through results.

        Pages are fetched (20 records each) until a page returns fewer than
        the page size or is empty.  A ``max_pages`` guard prevents unbounded
        fetches on large datasets.

        Args:
            endpoint: API path (e.g. ``"/arboviroses/dengue"``).
            year: Optional year filter (``nu_ano``).
            max_pages: Maximum number of pages to fetch. If None, fetches
                until exhausted (use with caution on large datasets).
            use_cache: Whether to use cached data for individual pages.

        Returns
        -------
        pd.DataFrame
            All fetched records concatenated.
        """
        frames: list[pd.DataFrame] = []
        page = 0
        while True:
            if max_pages is not None and page >= max_pages:
                logger.info(f"Reached max_pages={max_pages}, stopping.")
                break
            df = self.get_dataset(
                endpoint,
                year=year,
                limit=self.MAX_PAGE_SIZE,
                offset=page,
                use_cache=use_cache,
            )
            if df.empty:
                logger.info(f"Empty page {page}, stopping.")
                break
            frames.append(df)
            logger.info(f"Page {page}: {len(df)} records (total: {sum(len(f) for f in frames)})")
            if len(df) < self.MAX_PAGE_SIZE:
                break
            page += 1
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    @staticmethod
    def _fill_path_params(
        endpoint: str, path_params: dict[str, Any] | None
    ) -> str:
        """Substitute ``{param}`` placeholders in the endpoint path."""
        path = endpoint
        if path_params:
            for key, value in path_params.items():
                path = path.replace(f"{{{key}}}", str(value))
        return path

    # ------------------------------------------------------------------
    # Convenience methods for key epidemiological endpoints
    # ------------------------------------------------------------------
    def get_arbovirose(
        self,
        disease: str = "dengue",
        year: int | None = None,
        limit: int = 20,
        offset: int = 0,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Fetch a page of arbovirose occurrence records.

        Args:
            disease: One of ``"dengue"``, ``"chikungunya"``, ``"zikavirus"``,
                ``"febre-amarela-epzootias"``, or
                ``"febre-amarela-humanos-primatas-nao-humanos"``.
            year: Optional year filter (``nu_ano``).
            limit: Page size (server-capped at 20).
            offset: Page number (0-indexed).
            use_cache: Whether to use cached data.
        """
        endpoint = f"/arboviroses/{disease}"
        return self.get_dataset(
            endpoint, year=year, limit=limit, offset=offset, use_cache=use_cache
        )

    def get_vacinacao_pni(
        self,
        year: int,
        limit: int = 20,
        offset: int = 0,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Fetch a page of PNI (Programa Nacional de Imunizações) applied doses.

        Args:
            year: Year of data (2020-2026).
            limit: Page size (server-capped at 20).
            offset: Page number (0-indexed).
            use_cache: Whether to use cached data.
        """
        if year < 2020 or year > 2026:
            raise ValueError(f"PNI year must be between 2020 and 2026, got {year}")
        endpoint = f"/vacinacao/doses-aplicadas-pni-{year}"
        return self.get_dataset(
            endpoint, limit=limit, offset=offset, use_cache=use_cache
        )

    def get_mpox(
        self,
        limit: int = 20,
        offset: int = 0,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Fetch a page of mpox notification records."""
        return self.get_dataset(
            "/vigilancia-e-meio-ambiente/mpox",
            limit=limit,
            offset=offset,
            use_cache=use_cache,
        )

    def get_sindrome_gripal(
        self,
        year: int,
        limit: int = 20,
        offset: int = 0,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Fetch a page of mild influenza-like illness (síndrome gripal) records.

        Args:
            year: Year of data (2020-2023).
            limit: Page size (server-capped at 20).
            offset: Page number (0-indexed).
            use_cache: Whether to use cached data.
        """
        if year < 2020 or year > 2023:
            raise ValueError(
                f"Síndrome gripal year must be between 2020 and 2023, got {year}"
            )
        endpoint = f"/vigilancia-e-meio-ambiente/notificacoes-de-sindrome-gripal-leve-{year}"
        return self.get_dataset(
            endpoint, limit=limit, offset=offset, use_cache=use_cache
        )


# ----------------------------------------------------------------------
# Convenience functions
# ----------------------------------------------------------------------
def list_demas_datasets(domain: str | None = None) -> pd.DataFrame:
    """Convenience function to list DEMAS datasets."""
    return DemasAccessor().list_datasets(domain=domain)


def search_demas_datasets(keyword: str) -> pd.DataFrame:
    """Convenience function to search DEMAS datasets by keyword."""
    return DemasAccessor().search_datasets(keyword=keyword)


def get_demas_dataset(
    endpoint: str,
    year: int | None = None,
    limit: int = 20,
    offset: int = 0,
) -> pd.DataFrame:
    """Convenience function to fetch a single page from a DEMAS dataset."""
    return DemasAccessor().get_dataset(
        endpoint, year=year, limit=limit, offset=offset
    )
