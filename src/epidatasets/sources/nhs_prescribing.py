"""
NHS England Prescribing Accessor

Provides access to NHS England primary care prescribing data through two
complementary sources:

1. **OpenPrescribing REST API** (EBM DataLab, University of Oxford)
   - Spending totals at national, CCG/SICBL and practice level, aggregated
     by BNF code and month.
   - Prescribing quality measures (e.g. antibiotic stewardship, opioid
     monitoring) at national and organisation level.
   - Organisation location data (GeoJSON) for practices and CCGs.
   - BNF code and organisation code search.

2. **English Prescribing Dataset (EPD)** published by the NHS Business
   Services Authority (NHSBSA) as monthly bulk CSV files (~600 million
   rows/year, practice-level detail with SNOMED codes).  Files are
   discovered via the NHSBSA open data portal (CKAN) and read with
   chunked/lazy evaluation.

Data Sources:
- OpenPrescribing: https://openprescribing.net/
- OpenPrescribing API docs: https://openprescribing.net/api/
- NHSBSA EPD: https://www.nhsbsa.nhs.uk/prescription-data/prescribing-data/english-prescribing-data-epd
- NHSBSA open data portal: https://opendata.nhsbsa.net

Authentication: None required
Update Frequency: Monthly
Coverage: England (NHS primary care), 2010-present (API), 2020-11-present (EPD)
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from collections.abc import Callable, Iterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar, cast

import pandas as pd
import requests

from epidatasets._base import BaseAccessor

logger = logging.getLogger(__name__)

# BNF chapters (British National Formulary classification)
BNF_CHAPTERS: dict[int, str] = {
    1: "Gastro-Intestinal System",
    2: "Cardiovascular System",
    3: "Respiratory System",
    4: "Central Nervous System",
    5: "Infections",
    6: "Endocrine System",
    7: "Obstetrics, Gynaecology and Urinary-Tract Disorders",
    8: "Malignant Disease and Immunosuppression",
    9: "Nutrition and Blood",
    10: "Musculoskeletal and Joint Diseases",
    11: "Eye",
    12: "Ear, Nose and Oropharynx",
    13: "Skin",
    14: "Immunological Products and Vaccines",
    15: "Anaesthesia",
}


class NHSPrescribingAPIError(Exception):
    """Raised when an NHS prescribing API request fails after retries.

    Wraps the original network/HTTP error and includes retry guidance.
    """


def bnf_to_flat(code: str) -> str:
    """Convert a dotted hierarchical BNF code to its flat form.

    BNF presentation codes are flat strings where the chapter is two digits
    (``05``), followed by two-digit section and paragraph components and a
    one-digit sub-paragraph (e.g. ``0501013B0AAAAAA``).  The dotted form
    uses the human-readable hierarchy (e.g. ``5.1.1.3`` for the
    sub-paragraph covering broad-spectrum penicillins).

    Parameters
    ----------
    code : str
        BNF code in either dotted (``"5.1"``) or flat (``"0501"``) form.

    Returns
    -------
    str
        The flat, uppercase form of the code (``"5.1"`` -> ``"0501"``).

    Examples
    --------
    >>> bnf_to_flat("5.1")
    '0501'
    >>> bnf_to_flat("5.1.1.3")
    '0501013'
    >>> bnf_to_flat("0501013B0")
    '0501013B0'
    """
    code = code.strip().upper()
    if "." not in code:
        # a bare single digit is a chapter number ("5" -> "05")
        if len(code) == 1 and code.isdigit():
            return code.zfill(2)
        return code
    parts = code.split(".")
    # chapter is zero-padded to 2 digits; section and paragraph to 2 digits
    # each; the sub-paragraph is a single digit
    flat = parts[0].zfill(2)
    for i, part in enumerate(parts[1:], start=1):
        flat += part.zfill(2) if i <= 2 else part.zfill(1)
    return flat


def bnf_level(code: str) -> str:
    """Return the hierarchical level name of a BNF code.

    Parameters
    ----------
    code : str
        BNF code in dotted or flat form.

    Returns
    -------
    str
        One of ``"chapter"``, ``"section"``, ``"paragraph"``,
        ``"subparagraph"``, ``"chemical"``, ``"product"``,
        ``"presentation"``.

    Examples
    --------
    >>> bnf_level("5")
    'chapter'
    >>> bnf_level("5.1")
    'section'
    >>> bnf_level("0501013B0")
    'chemical'
    """
    if "." in code:
        depth = code.count(".") + 1
        return {1: "chapter", 2: "section", 3: "paragraph", 4: "subparagraph"}.get(
            depth, "unknown"
        )
    n = len(bnf_to_flat(code))
    if n <= 2:
        return "chapter"
    if n <= 4:
        return "section"
    if n <= 6:
        return "paragraph"
    if n <= 7:
        return "subparagraph"
    if n <= 9:
        return "chemical"
    if n <= 11:
        return "product"
    return "presentation"


def filter_bnf(
    df: pd.DataFrame,
    prefix: str,
    code_col: str = "BNF_CODE",
) -> pd.DataFrame:
    """Filter a DataFrame of prescribing records by a BNF code prefix.

    Works at any hierarchy level: chapter (``"5"``), section (``"5.1"``),
    paragraph (``"5.1.1"``), sub-paragraph (``"5.1.1.3"``), chemical
    (``"0501013B0"``) or deeper.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing a BNF code column.
    prefix : str
        BNF code prefix in dotted or flat form.
    code_col : str
        Name of the BNF code column (default ``"BNF_CODE"``).

    Returns
    -------
    pd.DataFrame
        Rows whose BNF code starts with the flat prefix.
    """
    if df.empty or code_col not in df.columns:
        return df
    flat = bnf_to_flat(prefix)
    mask = df[code_col].astype(str).str.upper().str.startswith(flat)
    return df[mask].reset_index(drop=True)


class NHSPrescribingAccessor(BaseAccessor):
    """Accessor for NHS England prescribing data.

    Combines the OpenPrescribing REST API (aggregated spending and quality
    measures) with the NHSBSA English Prescribing Dataset (practice-level
    bulk CSVs).

    Example
    -------
    >>> from epidatasets.sources.nhs_prescribing import NHSPrescribingAccessor
    >>> accessor = NHSPrescribingAccessor()
    >>> spending = accessor.get_spending(bnf_code="5.1")  # antibiotics
    >>> ccg = accessor.get_spending_by_ccg(bnf_code="5.1", year_month="2024-01")
    >>> practices = accessor.get_practice_locations()  # GeoJSON -> DataFrame
    """

    source_name: ClassVar[str] = "nhs_prescribing"
    source_description: ClassVar[str] = (
        "NHS England primary care prescribing data: OpenPrescribing REST API "
        "(spending, prescribing quality measures, organisation locations) and "
        "the NHSBSA English Prescribing Dataset (EPD) monthly bulk CSVs."
    )
    source_url: ClassVar[str] = "https://openprescribing.net/api/"

    API_BASE = "https://openprescribing.net/api/1.0"
    CKAN_BASE = "https://opendata.nhsbsa.net"
    EPD_DATASET_ID = "english-prescribing-dataset-epd-with-snomed-code"

    # org_type aliases -> /measure_by_<endpoint>/
    _MEASURE_ORG_ENDPOINTS = {
        "practice": "measure_by_practice",
        "ccg": "measure_by_sicbl",
        "sicbl": "measure_by_sicbl",
        "icb": "measure_by_icb",
        "stp": "measure_by_icb",
        "pcn": "measure_by_pcn",
        "regional_team": "measure_by_regional_team",
    }

    # EPD columns that need numeric coercion (values arrive as strings,
    # sometimes with a trailing ".")
    EPD_NUMERIC_COLUMNS = [
        "QUANTITY",
        "ITEMS",
        "TOTAL_QUANTITY",
        "ADQUSAGE",
        "NIC",
        "ACTUAL_COST",
    ]

    def __init__(
        self,
        cache_dir: str | None = None,
        cache_ttl_days: float = 7.0,
        timeout: int = 60,
        max_retries: int = 3,
        api_base: str | None = None,
        ckan_base: str | None = None,
    ):
        """Initialize the NHS prescribing accessor.

        Parameters
        ----------
        cache_dir : str, optional
            Directory for the filesystem cache.  Defaults to
            ``~/.cache/epi_data/nhs_prescribing``.
        cache_ttl_days : float
            Cache time-to-live in days.  Defaults to 7 days, aligned with
            the monthly release cycle.
        timeout : int
            HTTP timeout in seconds.
        max_retries : int
            Maximum number of attempts for transient failures.
        api_base : str, optional
            Override the OpenPrescribing API base URL (for testing).
        ckan_base : str, optional
            Override the NHSBSA CKAN base URL (for testing).
        """
        self.cache_dir = (
            Path(cache_dir)
            if cache_dir
            else Path.home() / ".cache" / "epi_data" / "nhs_prescribing"
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_ttl = timedelta(days=cache_ttl_days)
        self.timeout = timeout
        self.max_retries = max(1, max_retries)
        self.api_base = api_base or self.API_BASE
        self.ckan_base = ckan_base or self.CKAN_BASE
        self._session = requests.Session()
        self._session.headers.update({"Accept": "application/json"})

    # ------------------------------------------------------------------
    # Low-level plumbing: retries, errors, caching
    # ------------------------------------------------------------------

    def _request_json(self, url: str, params: dict | None = None) -> Any:
        """GET a URL and return the parsed JSON, with retries.

        Raises
        ------
        NHSPrescribingAPIError
            If the request fails after ``max_retries`` attempts or returns
            a non-success HTTP status.
        """
        params = dict(params or {})
        params.setdefault("format", "json")
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self._session.get(url, params=params, timeout=self.timeout)
                if 200 <= resp.status_code < 300:
                    return resp.json()
                if resp.status_code >= 500 and attempt < self.max_retries:
                    last_exc = requests.HTTPError(
                        f"HTTP {resp.status_code} for {resp.url}"
                    )
                    time.sleep(attempt)  # linear backoff: 1s, 2s, ...
                    continue
                raise NHSPrescribingAPIError(
                    f"HTTP {resp.status_code} for {resp.url}. "
                    "The service may be temporarily unavailable; retry later "
                    "or check https://openprescribing.net/api/ for status."
                )
            except (
                requests.ConnectionError,
                requests.Timeout,
            ) as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    time.sleep(attempt)
        raise NHSPrescribingAPIError(
            f"Request to {url} failed after {self.max_retries} attempts "
            f"(last error: {last_exc}). Retry with NHSPrescribingAccessor"
            f"(max_retries={self.max_retries + 2}) or try again later."
        ) from last_exc

    def _cache_path(self, name: str) -> Path:
        digest = hashlib.md5(name.encode()).hexdigest()[:12]  # noqa: S324
        return self.cache_dir / digest

    def _is_cache_valid(self, path: Path) -> bool:
        if not path.exists():
            return False
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        return datetime.now() - mtime < self._cache_ttl

    def _cached_dataframe(
        self,
        key: str,
        fetch: Callable[[], pd.DataFrame],
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Cache a DataFrame on the filesystem with a TTL."""
        path = self._cache_path(key)
        if use_cache and self._is_cache_valid(path):
            try:
                cached = pd.read_csv(path)
                if not cached.empty:
                    return cached
                logger.debug("Empty cache entry for %s; refetching", key)
            except Exception as exc:  # corrupted cache: refetch
                logger.warning("Discarding corrupted cache file %s: %s", path, exc)
        df = fetch()
        df.to_csv(path, index=False)
        return df

    def _api_get_dataframe(
        self,
        endpoint: str,
        params: dict | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """GET an OpenPrescribing endpoint and return a DataFrame."""
        key = endpoint + "?" + json.dumps(params or {}, sort_keys=True)

        def fetch() -> pd.DataFrame:
            data = self._request_json(f"{self.api_base}/{endpoint}/", params)
            if isinstance(data, dict):
                # single record or error payload
                return pd.DataFrame([data])
            return pd.DataFrame(data)

        return self._cached_dataframe(key, fetch, use_cache=use_cache)

    # ------------------------------------------------------------------
    # BNF helpers
    # ------------------------------------------------------------------

    def list_bnf_chapters(self) -> pd.DataFrame:
        """Return the BNF chapter reference table.

        Returns
        -------
        pd.DataFrame
            Columns ``chapter_code`` (flat 2-digit form), ``chapter_number``
            and ``chapter_name``.
        """
        rows = [
            {
                "chapter_code": f"{number:02d}",
                "chapter_number": number,
                "chapter_name": name,
                "level": "chapter",
            }
            for number, name in BNF_CHAPTERS.items()
        ]
        return pd.DataFrame(rows)

    def search_bnf_codes(
        self, query: str, exact: bool = False, use_cache: bool = True
    ) -> pd.DataFrame:
        """Search the BNF classification via the OpenPrescribing API.

        Parameters
        ----------
        query : str
            A BNF code prefix or a (partial) drug/section name.
        exact : bool
            Require exact code/name matches.
        use_cache : bool
            Use the filesystem cache when possible.

        Returns
        -------
        pd.DataFrame
            Columns include ``id``, ``name`` and ``type`` (one of
            ``"BNF chapter"``, ``"BNF section"``, ``"BNF paragraph"``,
            ``"BNF subparagraph"``, ``"chemical"``, ``"product"``,
            ``"product format"``).
        """
        params: dict[str, Any] = {"q": query}
        if exact:
            params["exact"] = "true"
        return self._api_get_dataframe("bnf_code", params, use_cache=use_cache)

    # ------------------------------------------------------------------
    # OpenPrescribing: spending endpoints
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_date_param(year_month: str | None) -> str | None:
        """Normalize ``"2024-01"`` / ``"202401"`` to the API's ``YYYY-MM-DD``."""
        if not year_month:
            return None
        match = re.match(r"^(\d{4})-?(\d{2})$", year_month.strip())
        if not match:
            raise ValueError(
                f"Invalid year_month {year_month!r}: expected 'YYYY-MM' or 'YYYYMM'"
            )
        return f"{match.group(1)}-{match.group(2)}-01"

    def get_spending(
        self,
        bnf_code: str,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Get national (All England) monthly spending for a BNF code.

        Parameters
        ----------
        bnf_code : str
            BNF code or prefix in dotted or flat form (e.g. ``"5.1"`` for
            antibacterial drugs, ``"0501013B0"`` for amoxicillin).

        Returns
        -------
        pd.DataFrame
            Columns ``row_id``, ``row_name``, ``date``, ``items``,
            ``quantity`` and ``actual_cost``, one row per month.
        """
        params = {"code": bnf_to_flat(bnf_code)}
        df = self._api_get_dataframe("spending", params, use_cache=use_cache)
        if not df.empty and "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        return df

    def get_spending_by_ccg(
        self,
        bnf_code: str,
        ccg_code: str | None = None,
        year_month: str | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Get monthly spending by CCG/SICBL for a BNF code.

        Parameters
        ----------
        bnf_code : str
            BNF code or prefix (e.g. ``"5.1"``).
        ccg_code : str, optional
            Restrict to one CCG/SICBL code (e.g. ``"15N"``).  When omitted,
            all CCGs are returned.
        year_month : str, optional
            Restrict to a single month, ``"YYYY-MM"`` or ``"YYYYMM"``.

        Returns
        -------
        pd.DataFrame
            Columns ``row_id`` (CCG code), ``row_name``, ``date``,
            ``items``, ``quantity`` and ``actual_cost``.
        """
        params: dict[str, Any] = {"code": bnf_to_flat(bnf_code)}
        if ccg_code:
            params["org"] = ccg_code
        date = self._normalize_date_param(year_month)
        if date:
            params["date"] = date
        df = self._api_get_dataframe("spending_by_sicbl", params, use_cache=use_cache)
        if not df.empty and "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        return df

    def get_spending_by_practice(
        self,
        bnf_code: str,
        ccg_code: str | None = None,
        practice_code: str | None = None,
        year_month: str | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Get monthly spending by GP practice for a BNF code.

        The upstream API requires either an organisation filter or a single
        month, so at least one of ``ccg_code``, ``practice_code`` or
        ``year_month`` must be provided.

        Parameters
        ----------
        bnf_code : str
            BNF code or prefix (e.g. ``"5.1"``).
        ccg_code : str, optional
            Return all practices within this CCG/SICBL.
        practice_code : str, optional
            Restrict to a single practice (e.g. ``"L81001"``).
        year_month : str, optional
            Restrict to a single month, ``"YYYY-MM"`` or ``"YYYYMM"``.

        Returns
        -------
        pd.DataFrame
            Columns ``row_id`` (practice code), ``row_name``, ``date``,
            ``items``, ``quantity``, ``actual_cost``, ``ccg`` and
            ``setting``.
        """
        if not (ccg_code or practice_code or year_month):
            raise ValueError(
                "Provide at least one of ccg_code, practice_code or "
                "year_month (the API does not return all practices over "
                "all months in a single request)."
            )
        params: dict[str, Any] = {"code": bnf_to_flat(bnf_code)}
        org = practice_code or ccg_code
        if org:
            params["org"] = org
        date = self._normalize_date_param(year_month)
        if date:
            params["date"] = date
        df = self._api_get_dataframe(
            "spending_by_practice", params, use_cache=use_cache
        )
        if not df.empty and "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        return df

    # ------------------------------------------------------------------
    # OpenPrescribing: measures
    # ------------------------------------------------------------------

    def get_measures(
        self,
        measure: str | list[str] | None = None,
        org_type: str | None = None,
        org_code: str | None = None,
        tags: str | list[str] | None = None,
        aggregate: bool = False,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Get prescribing quality measures.

        Without ``org_type`` this returns national-level measure data
        (flattened).  With ``org_type`` (e.g. ``"practice"``, ``"ccg"``)
        it queries the organisation-level endpoints.

        Parameters
        ----------
        measure : str or list[str], optional
            Measure id(s), e.g. ``"ktt9_antibiotics"``.  When omitted all
            measures are returned.
        org_type : str, optional
            One of ``"practice"``, ``"ccg"``, ``"icb"``, ``"pcn"``,
            ``"regional_team"``.
        org_code : str, optional
            Organisation code to filter by (required for practice-level
            queries unless ``aggregate=True``).
        tags : str or list[str], optional
            Filter measures by tag (e.g. ``"antibiotics"``).
        aggregate : bool
            Aggregate over all organisations of the given type.

        Returns
        -------
        pd.DataFrame
            Organisation-level rows have columns ``measure``, ``org_type``,
            ``org_id``, ``org_name``, ``date``, ``numerator``,
            ``denominator``, ``calc_value`` and ``percentile``.  National
            rows carry the measure metadata plus one row per month.
        """
        measure_param: str | None = None
        if isinstance(measure, (list, tuple)):
            measure_param = ",".join(measure) if measure else None
        elif measure:
            measure_param = measure

        if org_type:
            endpoint = self._MEASURE_ORG_ENDPOINTS.get(org_type.lower())
            if endpoint is None:
                valid = ", ".join(sorted(self._MEASURE_ORG_ENDPOINTS))
                raise ValueError(
                    f"Unknown org_type {org_type!r}. Valid values: {valid}"
                )
            if org_type.lower() == "practice" and not (org_code or aggregate):
                raise ValueError(
                    "Practice-level measure queries require org_code or aggregate=True."
                )
            params: dict[str, Any] = {}
            if measure_param:
                params["measure"] = measure_param
            if tags:
                params["tags"] = (
                    ",".join(tags) if isinstance(tags, (list, tuple)) else tags
                )
            if org_code:
                params["org"] = org_code
            if aggregate:
                params["aggregate"] = "true"
            df = self._api_get_dataframe(endpoint, params, use_cache=use_cache)
            if not df.empty and "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
            return df

        # National level: nested response {"measures": [{..., "data": [...]}]}
        params = {}
        if measure_param:
            params["measure"] = measure_param
        if tags:
            params["tags"] = ",".join(tags) if isinstance(tags, (list, tuple)) else tags
        key = "measure?" + json.dumps(params, sort_keys=True)

        def fetch() -> pd.DataFrame:
            payload = self._request_json(f"{self.api_base}/measure/", params)
            rows: list[dict[str, Any]] = []
            for m in payload.get("measures", []):
                meta = {k: v for k, v in m.items() if k != "data"}
                for point in m.get("data", []):
                    rows.append({**meta, **point})
            return pd.DataFrame(rows)

        df = self._cached_dataframe(key, fetch, use_cache=use_cache)
        if not df.empty and "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        return df

    def get_measure_definitions(self, use_cache: bool = True) -> pd.DataFrame:
        """Return metadata for all prescribing quality measures.

        Returns
        -------
        pd.DataFrame
            One row per measure with columns ``id``, ``name``, ``title``,
            ``description``, ``why_it_matters``, ``tags``, ``low_is_good``,
            etc.
        """
        key = "measure_definitions"

        def fetch() -> pd.DataFrame:
            payload = self._request_json(f"{self.api_base}/measure/", {})
            rows = [
                {k: v for k, v in m.items() if k != "data"}
                for m in payload.get("measures", [])
            ]
            return pd.DataFrame(rows)

        return self._cached_dataframe(key, fetch, use_cache=use_cache)

    # ------------------------------------------------------------------
    # OpenPrescribing: organisation codes and locations
    # ------------------------------------------------------------------

    def search_org_codes(
        self,
        query: str,
        org_type: str | None = None,
        exact: bool = False,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Search for NHS organisation codes by name or code.

        Parameters
        ----------
        query : str
            Full or partial organisation code or name.
        org_type : str, optional
            One of ``"practice"``, ``"ccg"``, ``"pcn"``, ``"stp"`` (ICB),
            ``"regional_team"``.
        exact : bool
            Require exact matches.

        Returns
        -------
        pd.DataFrame
            Columns ``id``, ``code``, ``name``, ``type`` (and ``ccg`` for
            practices).
        """
        params: dict[str, Any] = {"q": query}
        if org_type:
            params["org_type"] = org_type
        if exact:
            params["exact"] = "true"
        return self._api_get_dataframe("org_code", params, use_cache=use_cache)

    def _get_org_locations(
        self,
        org_type: str,
        org_code: str | None = None,
        centroids: bool = False,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Fetch GeoJSON organisation locations and flatten to a DataFrame."""
        params: dict[str, Any] = {"org_type": org_type}
        if org_code:
            params["q"] = org_code
        if centroids:
            params["centroids"] = "true"
        key = "org_location?" + json.dumps(params, sort_keys=True)

        def fetch() -> pd.DataFrame:
            payload = self._request_json(f"{self.api_base}/org_location/", params)
            rows: list[dict[str, Any]] = []
            for feature in payload.get("features", []):
                props = dict(feature.get("properties", {}))
                geometry = feature.get("geometry") or {}
                coords = geometry.get("coordinates")
                if isinstance(coords, (list, tuple)) and len(coords) >= 2:
                    props["lon"] = coords[0]
                    props["lat"] = coords[1]
                rows.append(props)
            return pd.DataFrame(rows)

        return self._cached_dataframe(key, fetch, use_cache=use_cache)

    def get_practice_locations(
        self,
        ccg_code: str | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Get GP practice locations (points) for spatial analysis.

        Parameters
        ----------
        ccg_code : str, optional
            Restrict to practices in this CCG/SICBL (the API also accepts
            a practice code here).

        Returns
        -------
        pd.DataFrame
            Columns ``code``, ``name``, ``setting``, ``lat`` and ``lon``.
        """
        return self._get_org_locations(
            "practice", org_code=ccg_code, use_cache=use_cache
        )

    def get_ccg_locations(self, use_cache: bool = True) -> pd.DataFrame:
        """Get CCG/SICBL centroid locations for spatial analysis.

        Returns
        -------
        pd.DataFrame
            Columns ``code``, ``name``, ``ons_code``, ``org_type``,
            ``lat`` and ``lon``.
        """
        return self._get_org_locations("ccg", centroids=True, use_cache=use_cache)

    def geocode_orgs(
        self,
        org_codes: str | list[str],
        org_type: str = "practice",
    ) -> pd.DataFrame:
        """Resolve organisation codes to geographic coordinates.

        Parameters
        ----------
        org_codes : str or list[str]
            One or more organisation codes (or a parent CCG code when
            ``org_type="practice"``).
        org_type : str
            ``"practice"`` or ``"ccg"``.

        Returns
        -------
        pd.DataFrame
            Location rows including ``lat``/``lon``, restricted to the
            requested codes (for practices, all practices of the given
            CCG when a CCG code is supplied).
        """
        if isinstance(org_codes, str):
            org_codes = [org_codes]
        query = ",".join(org_codes)
        locations = self._get_org_locations(org_type, org_code=query)
        if locations.empty or "code" not in locations.columns:
            return locations
        codes = {c.upper() for c in org_codes}
        mask = locations["code"].astype(str).str.upper().isin(codes)
        if mask.any():
            # direct code matches; when none match, the API expanded a
            # parent CCG code into its practices and we keep every row
            locations = locations[mask]
        return locations.reset_index(drop=True)

    # ------------------------------------------------------------------
    # NHSBSA English Prescribing Dataset (EPD) bulk CSVs
    # ------------------------------------------------------------------

    def _epd_index(self, use_cache: bool = True) -> dict[str, str]:
        """Return the EPD resource index ``{"YYYYMM": download_url}``."""
        path = self.cache_dir / "epd_index.json"
        if use_cache and self._is_cache_valid(path):
            try:
                return cast("dict[str, str]", json.loads(path.read_text()))
            except Exception as exc:
                logger.warning("Discarding corrupted EPD index: %s", exc)
        url = f"{self.ckan_base}/api/3/action/package_show"
        payload = self._request_json(url, {"id": self.EPD_DATASET_ID})
        try:
            resources = payload["result"]["resources"]
        except (KeyError, TypeError) as exc:
            raise NHSPrescribingAPIError(
                f"Unexpected CKAN response for EPD dataset {self.EPD_DATASET_ID!r}"
            ) from exc
        index: dict[str, str] = {}
        for resource in resources:
            match = re.match(r"^EPD_SNOMED_(\d{6})$", str(resource.get("name", "")))
            if match and resource.get("url"):
                index[match.group(1)] = resource["url"]
        path.write_text(json.dumps(index))
        return index

    def list_epd_months(self, use_cache: bool = True) -> list[str]:
        """List available EPD months as ``YYYYMM`` strings."""
        return sorted(self._epd_index(use_cache=use_cache))

    def _download_epd(self, url: str, destination: Path) -> None:
        """Stream-download an EPD CSV to ``destination`` atomically."""
        tmp = destination.with_suffix(".part")
        try:
            with self._session.get(url, stream=True, timeout=self.timeout) as resp:
                resp.raise_for_status()
                with open(tmp, "wb") as fh:
                    for chunk in resp.iter_content(chunk_size=1 << 20):
                        if chunk:
                            fh.write(chunk)
            tmp.rename(destination)
        except requests.RequestException as exc:
            tmp.unlink(missing_ok=True)
            raise NHSPrescribingAPIError(
                f"Failed to download EPD file from {url}: {exc}. "
                "The file may be very large; check your connection and "
                "retry, or increase the timeout."
            ) from exc

    def _read_epd_chunks(
        self,
        path: Path,
        chunksize: int,
        bnf_prefix: str | None,
    ) -> Iterator[pd.DataFrame]:
        """Yield processed EPD chunks, optionally BNF-filtered."""
        flat = bnf_to_flat(bnf_prefix) if bnf_prefix else None
        for chunk in pd.read_csv(path, chunksize=chunksize, dtype=str):
            for col in self.EPD_NUMERIC_COLUMNS:
                if col in chunk.columns:
                    chunk[col] = pd.to_numeric(chunk[col], errors="coerce")
            if flat and "BNF_CODE" in chunk.columns:
                chunk = chunk[chunk["BNF_CODE"].str.upper().str.startswith(flat)]
            yield chunk

    def get_epd_month(
        self,
        year: int,
        month: int,
        bnf_section: str | None = None,
        chunksize: int | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame | Iterator[pd.DataFrame]:
        """Read one monthly English Prescribing Dataset (EPD) CSV.

        EPD files are large (hundreds of MB, ~10M+ rows per month).  Use
        ``chunksize`` for chunked/lazy evaluation, optionally filtered to a
        BNF section so filtering happens without materialising the full
        month in memory.

        Parameters
        ----------
        year : int
            Release year (data available from November 2020).
        month : int
            Release month (1-12).
        bnf_section : str, optional
            BNF prefix filter at any hierarchy level (e.g. ``"5.1"`` for
            antibacterial drugs).
        chunksize : int, optional
            When given, return an iterator of DataFrames with at most
            ``chunksize`` rows each (lazy evaluation).
        use_cache : bool
            Reuse a previously downloaded file within the cache TTL.

        Returns
        -------
        pd.DataFrame or Iterator[pd.DataFrame]
            EPD records with numeric columns coerced
            (``ITEMS``, ``QUANTITY``, ``TOTAL_QUANTITY``, ``ADQUSAGE``,
            ``NIC``, ``ACTUAL_COST``).
        """
        year_month = f"{year:04d}{month:02d}"
        index = self._epd_index(use_cache=use_cache)
        if year_month not in index:
            available = ", ".join(self.list_epd_months(use_cache=use_cache))
            raise ValueError(
                f"No EPD file for {year_month}. Available months: {available}"
            )
        cache_file = self.cache_dir / f"epd_snomed_{year_month}.csv"
        if use_cache and self._is_cache_valid(cache_file):
            logger.debug("Using cached EPD file %s", cache_file)
        else:
            logger.info("Downloading EPD %s (this may take a while)...", year_month)
            self._download_epd(index[year_month], cache_file)
        if chunksize:
            return self._read_epd_chunks(cache_file, chunksize, bnf_section)
        chunks = self._read_epd_chunks(cache_file, 1 << 20, bnf_section)
        df = pd.concat(chunks, ignore_index=True)
        return df

    def get_epd_timeseries(
        self,
        bnf_code: str,
        start_year_month: str,
        end_year_month: str,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Build a monthly time-series for a BNF code from the EPD.

        Iterates over the available EPD months within the range, filters
        each month by the BNF prefix and aggregates items, quantities and
        costs.  Each month's CSV is cached, so repeated calls only
        download missing months.

        Parameters
        ----------
        bnf_code : str
            BNF code prefix in dotted or flat form (e.g. ``"0501013B0"``
            for amoxicillin).
        start_year_month : str
            First month, ``"YYYY-MM"`` or ``"YYYYMM"``.
        end_year_month : str
            Last month, ``"YYYY-MM"`` or ``"YYYYMM"``.

        Returns
        -------
        pd.DataFrame
            One row per month with columns ``YEAR_MONTH``, ``ITEMS``,
            ``TOTAL_QUANTITY``, ``QUANTITY``, ``NIC`` and ``ACTUAL_COST``.
        """

        def norm(value: str) -> str:
            return value.replace("-", "").strip()

        start, end = norm(start_year_month), norm(end_year_month)
        if len(start) != 6 or len(end) != 6 or start > end:
            raise ValueError(f"Invalid range {start_year_month!r}..{end_year_month!r}")
        months = [
            m for m in self.list_epd_months(use_cache=use_cache) if start <= m <= end
        ]
        if not months:
            raise ValueError(
                f"No EPD months available between {start} and {end}. "
                f"Available range: {self.list_epd_months(use_cache=use_cache)}"
            )
        frames: list[pd.DataFrame] = []
        for m in months:
            year, month = int(m[:4]), int(m[4:])
            df = self.get_epd_month(
                year,
                month,
                bnf_section=bnf_code,
                use_cache=use_cache,
            )
            assert isinstance(df, pd.DataFrame)  # chunksize not used above
            agg_cols = [
                col
                for col in [
                    "ITEMS",
                    "TOTAL_QUANTITY",
                    "QUANTITY",
                    "NIC",
                    "ACTUAL_COST",
                ]
                if col in df.columns
            ]
            if not agg_cols:
                continue
            monthly = df[agg_cols].sum().to_frame().T
            monthly.insert(0, "YEAR_MONTH", m)
            frames.append(monthly)
        if not frames:
            return pd.DataFrame(
                columns=["YEAR_MONTH", "ITEMS", "TOTAL_QUANTITY", "NIC", "ACTUAL_COST"]
            )
        out = pd.concat(frames, ignore_index=True)
        for col in out.columns:
            if col != "YEAR_MONTH":
                out[col] = pd.to_numeric(out[col], errors="coerce")
        return out

    # ------------------------------------------------------------------
    # BaseAccessor interface
    # ------------------------------------------------------------------

    def list_countries(self) -> pd.DataFrame:
        """Return countries covered by this source (England only)."""
        return pd.DataFrame([{"country_code": "GB-ENG", "country_name": "England"}])
