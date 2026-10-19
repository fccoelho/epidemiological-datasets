"""
SRAG — Severe Acute Respiratory Syndrome (Sivep-Gripe / e-SUS Notifica) Accessor

Provides access to the official Brazilian national surveillance dataset for
Severe Acute Respiratory Syndrome (Síndrome Respiratória Aguda Grave — SRAG),
published by the Ministry of Health on the OpenData SUS portal.

The dataset contains **individual case records** (line-level) with
epidemiological, clinical, laboratory and outcome variables, covering all
Brazilian municipalities from 2019 onward.  Annual files ("bancos") are
published per year: past years are frozen snapshots, while the current
year is a "banco vivo" updated weekly.

Data is resolved through the portal's dataset page
(https://dadosabertos.saude.gov.br/dataset/srag-2019-a-2026) and downloaded
directly from the Ministry of Health S3 bucket as CSV (default), Parquet,
JSON or XML.  Files are large (0.5–3 GB per year), so downloads are streamed
and reading is chunked/lazy.

Data Sources:
- Portal page: https://dadosabertos.saude.gov.br/dataset/srag-2019-a-2026
- Reference scripts (R): https://gitlab.com/cgcovid/dados-abertos
- IBGE municipalities: https://servicodados.ibge.gov.br/api/v1/localidades/municipios

Authentication: None required (open data)
Update Frequency: Weekly (current-year "banco vivo")
License: Dados Abertos do SUS

This accessor is complementary to:

- :class:`~epidatasets.sources.opendatasus.OpenDataSUSAccessor` — the
  generic catalog accessor (metadata and raw downloads for any dataset);
- :class:`~epidatasets.sources.datasus_pysus.DataSUSAccessor` — the older
  DATASUS/PySUS access route.
"""

from __future__ import annotations

import logging
import re
import time
import unicodedata
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from epidatasets._base import BaseAccessor
from epidatasets.sources.opendatasus import OpenDataSUSAccessor

logger = logging.getLogger(__name__)

#: SRAG dataset slug on the OpenData SUS portal
SRAG_DATASET_SLUG = "srag-2019-a-2026"

#: Candidate columns used to resolve each filter, in order of preference
#: (residence first, notification second).
STATE_COLUMNS = ["SG_UF", "SG_UF_NOT", "SG_UF_INTE"]
MUNICIPALITY_COLUMNS = ["CO_MUN_RES", "CO_MUN_NOT", "CO_MU_INTE"]
WEEK_COLUMNS = ["SEM_NOT", "SEM_PRI"]
OUTCOME_COLUMN = "EVOLUCAO"
AGE_COLUMNS = ["NU_IDADE_N", "TP_IDADE"]

#: Laboratory confirmation columns per pathogen (value "1" = detected).
#: Sivep-Gripe PCR and antigen panels.
PATHOGEN_COLUMNS: dict[str, list[str]] = {
    "sars-cov-2": ["PCR_SARS2", "AN_SARS2"],
    "sars_cov_2": ["PCR_SARS2", "AN_SARS2"],
    "covid-19": ["PCR_SARS2", "AN_SARS2"],
    "covid19": ["PCR_SARS2", "AN_SARS2"],
    "influenza": ["PCR_FLUASU", "PCR_FLUBLI", "POS_PCRFLU", "POS_AN_FLU"],
    "influenza a": ["PCR_FLUASU"],
    "influenza b": ["PCR_FLUBLI"],
    "vsr": ["PCR_VSR", "AN_VSR"],
    "rsv": ["PCR_VSR", "AN_VSR"],
    "adenovirus": ["PCR_ADENO", "AN_ADENO"],
    "parainfluenza": [
        "PCR_PARA1",
        "PCR_PARA2",
        "PCR_PARA3",
        "PCR_PARA4",
        "AN_PARA1",
        "AN_PARA2",
        "AN_PARA3",
    ],
    "metapneumovirus": ["PCR_METAP"],
    "rhinovirus": ["PCR_RINO"],
}

#: Case outcome codes (EVOLUCAO): 1 = cure, 2 = death (SRAG),
#: 3 = death from other causes.
OUTCOME_CODES: dict[str, set[str]] = {
    "cure": {"1"},
    "cura": {"1"},
    "death": {"2", "3"},
    "obito": {"2", "3"},
    "óbito": {"2", "3"},
}

#: Grouping options for :meth:`SRAGOpenDataSUSAccessor.get_weekly_counts`
GROUP_COLUMNS: dict[str, list[str]] = {
    "state": STATE_COLUMNS,
    "municipality": MUNICIPALITY_COLUMNS,
    "region": ["CO_REGIONA"],
    "macroregion": ["CO_RG_RESI", "CO_RG_INTE"],
}

IBGE_MUNICIPALITIES_URL = (
    "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
)


class SRAGDataError(Exception):
    """Raised when SRAG metadata resolution or downloads fail.

    Wraps the original network/HTTP error with retry guidance.
    """


def _normalize_pathogen(name: str) -> str:
    """Normalize a pathogen name for lookup (case/accent insensitive)."""
    text = unicodedata.normalize("NFKD", name.strip().lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def _slugify_pathogen(name: str) -> str:
    """Turn a pathogen name into a safe column-name slug."""
    slug = _normalize_pathogen(name)
    slug = re.sub(r"[^a-z0-9]+", "_", slug).strip("_")
    return slug or "unknown"


def _municipality_key(code: Any) -> str:
    """Normalize an IBGE municipality code to its 6-digit prefix.

    SRAG files use both the 6-digit geocode (``354980``) and the 7-digit
    code with check digit (``3549806``); the first 6 digits identify the
    municipality in both cases.
    """
    digits = re.sub(r"\D", "", str(code))
    return digits.zfill(6)[:6]


class SRAGOpenDataSUSAccessor(BaseAccessor):
    """Accessor for the SRAG (Sivep-Gripe / e-SUS Notifica) line-level data.

    Example
    -------
    >>> from epidatasets.sources.srag_opendata_sus import (
    ...     SRAGOpenDataSUSAccessor
    ... )
    >>> srag = SRAGOpenDataSUSAccessor()
    >>> srag.available_years()                    # [2019, ..., 2026]
    >>> df = srag.get_year(2024, state="RJ")      # chunked + filtered
    >>> ts = srag.get_weekly_counts([2023, 2024], groupby="state")
    """

    source_name = "srag"
    source_description = (
        "Brazilian national SRAG surveillance (Sivep-Gripe / e-SUS Notifica): "
        "line-level severe acute respiratory syndrome cases with demographic, "
        "clinical, laboratory and outcome variables, published per year on "
        "OpenData SUS (weekly-updated 'banco vivo' for the current year)."
    )
    source_url = "https://dadosabertos.saude.gov.br/dataset/srag-2019-a-2026"

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        live_ttl_hours: float = 24.0,
        timeout: int = 120,
        max_retries: int = 3,
    ):
        """Initialize the SRAG accessor.

        Parameters
        ----------
        cache_dir : str or Path, optional
            Directory for cached metadata and data files.  Defaults to
            ``~/.cache/epi_data/srag``.
        live_ttl_hours : float
            Cache TTL for the current (live, weekly-updated) year's files.
            Frozen years are cached without expiry.
        timeout : int
            HTTP timeout in seconds (files are multi-GB, be generous).
        max_retries : int
            Attempts for transient failures.
        """
        self.cache_dir = (
            Path(cache_dir)
            if cache_dir
            else Path.home() / ".cache" / "epi_data" / "srag"
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._live_ttl = timedelta(hours=live_ttl_hours)
        self.timeout = timeout
        self.max_retries = max(1, max_retries)
        self._session = requests.Session()
        self._sus = OpenDataSUSAccessor(cache_dir=str(self.cache_dir / "_portal"))
        self._municipalities: pd.DataFrame | None = None

    # ------------------------------------------------------------------
    # Metadata discovery (via the OpenData SUS portal)
    # ------------------------------------------------------------------

    def list_resources(self, use_cache: bool = True) -> pd.DataFrame:
        """List the SRAG dataset's data resources.

        Returns
        -------
        pd.DataFrame
            Columns ``year``, ``name``, ``format`` and ``url`` for the
            per-year CSV/Parquet/JSON/XML files (documentation PDFs and
            API links excluded).
        """
        resources = self._sus.get_resources(SRAG_DATASET_SLUG, use_cache=use_cache)
        rows = []
        for _, res in resources.iterrows():
            match = re.match(r"^\s*(\d{4})\s*-", str(res.get("name", "")))
            fmt = str(res.get("format", "")).strip().upper()
            if not match or fmt not in {"CSV", "PARQUET", "JSON", "XML"}:
                continue
            rows.append(
                {
                    "year": int(match.group(1)),
                    "name": res.get("name"),
                    "format": fmt,
                    "url": res.get("url"),
                }
            )
        return pd.DataFrame(rows)

    def available_years(self, use_cache: bool = True) -> list[int]:
        """Return the SRAG years available on the portal, sorted."""
        resources = self.list_resources(use_cache=use_cache)
        return sorted({int(y) for y in resources["year"]})

    def _resolve_url(self, year: int, fmt: str = "CSV", use_cache: bool = True) -> str:
        """Resolve the download URL for one year's file."""
        fmt = fmt.strip().upper()
        resources = self.list_resources(use_cache=use_cache)
        matches = resources[(resources["year"] == year) & (resources["format"] == fmt)]
        if matches.empty:
            available = ", ".join(
                f"{y}" for y in self.available_years(use_cache=use_cache)
            )
            raise ValueError(
                f"No {fmt} resource for SRAG year {year}. Available years: {available}"
            )
        return str(matches.iloc[0]["url"])

    # ------------------------------------------------------------------
    # Download + cache
    # ------------------------------------------------------------------

    def _is_cache_valid(self, path: Path, year: int) -> bool:
        """Frozen years cache forever; the live year honours the TTL."""
        if not path.exists():
            return False
        if year < datetime.now().year:
            return True  # frozen
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        return datetime.now() - mtime < self._live_ttl

    def _download(self, year: int, fmt: str, url: str, destination: Path) -> Path:
        """Stream one SRAG file to ``destination`` atomically."""
        tmp = destination.with_suffix(".part")
        try:
            for attempt in range(1, self.max_retries + 1):
                try:
                    with self._session.get(
                        url, stream=True, timeout=self.timeout
                    ) as resp:
                        resp.raise_for_status()
                        with open(tmp, "wb") as fh:
                            for chunk in resp.iter_content(chunk_size=1 << 20):
                                if chunk:
                                    fh.write(chunk)
                    tmp.rename(destination)
                    return destination
                except (requests.ConnectionError, requests.Timeout) as exc:
                    if attempt == self.max_retries:
                        raise exc
                    logger.warning(
                        "Download attempt %d/%d failed (%s); retrying...",
                        attempt,
                        self.max_retries,
                        exc,
                    )
                    time.sleep(attempt)
            raise RuntimeError("unreachable")  # pragma: no cover
        except requests.RequestException as exc:
            tmp.unlink(missing_ok=True)
            raise SRAGDataError(
                f"Failed to download SRAG {year} ({fmt}) from {url}: {exc}. "
                "Files are large; check your connection and retry."
            ) from exc

    def _ensure_file(self, year: int, fmt: str = "CSV", use_cache: bool = True) -> Path:
        """Download (or reuse) one year's file, returning its local path."""
        url = self._resolve_url(year, fmt=fmt, use_cache=use_cache)
        ext = fmt.lower()
        destination = self.cache_dir / f"SRAG_{year}.{ext}"
        if use_cache and self._is_cache_valid(destination, year):
            logger.debug("Using cached SRAG %s file %s", year, destination)
            return destination
        logger.info("Downloading SRAG %s (%s)... this may take a while", year, fmt)
        return self._download(year, fmt, url, destination)

    # ------------------------------------------------------------------
    # Reading and filtering
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_encoding(path: Path) -> str:
        """Sniff the file encoding (UTF-8 with Latin-1 fallback)."""
        with open(path, "rb") as fh:
            sample = fh.read(65536)
        try:
            sample.decode("utf-8")
            return "utf-8"
        except UnicodeDecodeError:
            return "latin-1"

    @staticmethod
    def _resolve_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
        """Return the first candidate column present in ``df``."""
        columns = {str(c).upper() for c in df.columns}
        for candidate in candidates:
            if candidate in columns:
                return candidate
        return None

    @staticmethod
    def _pathogen_mask(df: pd.DataFrame, pathogen: str) -> pd.Series:
        """Boolean mask of cases lab-confirmed for a pathogen."""
        key = _normalize_pathogen(pathogen)
        if key not in PATHOGEN_COLUMNS:
            known = ", ".join(sorted(set(PATHOGEN_COLUMNS)))
            raise ValueError(f"Unknown pathogen {pathogen!r}. Supported: {known}")
        columns = [
            c
            for c in PATHOGEN_COLUMNS[key]
            if c in {str(col).upper() for col in df.columns}
        ]
        if not columns:
            raise ValueError(
                f"No laboratory column for {pathogen!r} in this file "
                f"(looked for {PATHOGEN_COLUMNS[key]})."
            )
        mask = pd.Series(False, index=df.index)
        for column in columns:
            values = df[column].astype(str).str.strip()
            mask |= values.eq("1")
        return mask

    @staticmethod
    def _age_in_years(df: pd.DataFrame) -> pd.Series | None:
        """Convert NU_IDADE_N/TP_IDADE into age in years."""
        if "NU_IDADE_N" not in df.columns:
            return None
        age = pd.to_numeric(df["NU_IDADE_N"], errors="coerce")
        if "TP_IDADE" in df.columns:
            unit = pd.to_numeric(df["TP_IDADE"], errors="coerce")
            divisor = unit.map({1: 365.25, 2: 30.4375, 3: 1.0})
            age = age / divisor
        return age

    def _apply_filters(
        self,
        df: pd.DataFrame,
        state: str | None = None,
        municipality_code: int | str | None = None,
        week_start: int | None = None,
        week_end: int | None = None,
        pathogen: str | None = None,
        outcome: str | None = None,
        age_min: float | None = None,
        age_max: float | None = None,
    ) -> pd.DataFrame:
        """Apply all filters to one chunk of records."""
        n_before = len(df)

        if state:
            column = self._resolve_column(df, STATE_COLUMNS)
            if column is None:
                raise ValueError(f"No state column found (looked for {STATE_COLUMNS}).")
            df = df[df[column].astype(str).str.strip().str.upper() == state.upper()]

        if municipality_code is not None:
            column = self._resolve_column(df, MUNICIPALITY_COLUMNS)
            if column is None:
                raise ValueError(
                    f"No municipality column found (looked for {MUNICIPALITY_COLUMNS})."
                )
            target = _municipality_key(municipality_code)
            df = df[df[column].map(_municipality_key) == target]

        if week_start is not None or week_end is not None:
            column = self._resolve_column(df, WEEK_COLUMNS)
            if column is None:
                raise ValueError(
                    f"No epi-week column found (looked for {WEEK_COLUMNS})."
                )
            week = pd.to_numeric(df[column], errors="coerce")
            if week_start is not None:
                df = df[week >= week_start]
                week = week.loc[df.index]
            if week_end is not None:
                df = df[week <= week_end]

        if pathogen:
            df = df[self._pathogen_mask(df, pathogen)]

        if outcome:
            key = _normalize_pathogen(outcome)
            if key not in OUTCOME_CODES:
                known = ", ".join(sorted(set(OUTCOME_CODES)))
                raise ValueError(f"Unknown outcome {outcome!r}. Supported: {known}")
            column = self._resolve_column(df, [OUTCOME_COLUMN])
            if column is None:
                raise ValueError(f"No {OUTCOME_COLUMN} column in this file.")
            df = df[df[column].astype(str).str.strip().isin(OUTCOME_CODES[key])]

        if age_min is not None or age_max is not None:
            age = self._age_in_years(df)
            if age is None:
                raise ValueError(f"No age column found (looked for {AGE_COLUMNS}).")
            if age_min is not None:
                df = df[age >= age_min]
                age = age.loc[df.index]
            if age_max is not None:
                df = df[age <= age_max]

        if len(df) < n_before:
            logger.debug("Filtered chunk: %d -> %d rows", n_before, len(df))
        return df

    def _read_chunks(
        self,
        path: Path,
        fmt: str,
        chunksize: int,
        columns: list[str] | None,
        filters: dict[str, Any],
    ) -> Iterator[pd.DataFrame]:
        """Yield filtered chunks of one SRAG file (CSV or Parquet)."""
        if fmt == "CSV":
            encoding = self._detect_encoding(path)
            reader = pd.read_csv(
                path,
                sep=";",
                encoding=encoding,
                dtype=str,
                chunksize=chunksize,
            )
            for chunk in reader:
                chunk.columns = [str(c).strip().upper() for c in chunk.columns]
                filtered = self._apply_filters(chunk, **filters)
                if columns:
                    filtered = filtered[[c for c in columns if c in filtered.columns]]
                yield filtered
        elif fmt == "PARQUET":
            try:
                parquet = pd.read_parquet(path)
            except ImportError as exc:  # pragma: no cover - env dependent
                raise SRAGDataError(
                    "Parquet support requires pyarrow or fastparquet; "
                    "install it or use fmt='CSV'."
                ) from exc
            parquet.columns = [str(c).strip().upper() for c in parquet.columns]
            for start in range(0, len(parquet), chunksize):
                chunk = parquet.iloc[start : start + chunksize]
                filtered = self._apply_filters(chunk, **filters)
                if columns:
                    filtered = filtered[[c for c in columns if c in filtered.columns]]
                yield filtered
        else:
            raise ValueError(f"Unsupported format {fmt!r}; use CSV or PARQUET.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_year(
        self,
        year: int,
        state: str | None = None,
        municipality_code: int | str | None = None,
        week_start: int | None = None,
        week_end: int | None = None,
        pathogen: str | None = None,
        outcome: str | None = None,
        age_min: float | None = None,
        age_max: float | None = None,
        columns: list[str] | None = None,
        fmt: str = "CSV",
        chunksize: int | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame | Iterator[pd.DataFrame]:
        """Load one year of SRAG line-level records with optional filters.

        Files are 0.5–3 GB per year, so records are read in chunks and
        filtered chunk-by-chunk; use ``chunksize`` for lazy evaluation.
        All filters are composable.

        Parameters
        ----------
        year : int
            SRAG year (2019 onward).
        state : str, optional
            Two-letter state abbreviation of residence (e.g. ``"RJ"``).
        municipality_code : int or str, optional
            IBGE municipality code (6 or 7 digits) of residence.
        week_start, week_end : int, optional
            Epidemiological week range (notification week, 1–53).
        pathogen : str, optional
            Laboratory-confirmed pathogen: ``"SARS-CoV-2"``,
            ``"Influenza"``, ``"Influenza A"``, ``"Influenza B"``,
            ``"VSR"``/``"RSV"``, ``"Adenovirus"``, ``"Parainfluenza"``,
            ``"Metapneumovirus"``, ``"Rhinovirus"``.
        outcome : str, optional
            ``"cure"`` or ``"death"``.
        age_min, age_max : float, optional
            Age range in years.
        columns : list[str], optional
            Restrict the returned columns (filters still apply).
        fmt : str
            File format: ``"CSV"`` (default) or ``"PARQUET"``.
        chunksize : int, optional
            When given, return an iterator of DataFrames instead of a
            single concatenated DataFrame.
        use_cache : bool
            Reuse cached downloads (frozen years never expire).

        Returns
        -------
        pd.DataFrame or Iterator[pd.DataFrame]
            Filtered SRAG records.
        """
        filters = {
            "state": state,
            "municipality_code": municipality_code,
            "week_start": week_start,
            "week_end": week_end,
            "pathogen": pathogen,
            "outcome": outcome,
            "age_min": age_min,
            "age_max": age_max,
        }
        path = self._ensure_file(year, fmt=fmt, use_cache=use_cache)
        iterator = self._read_chunks(
            path, fmt.upper(), chunksize or 1 << 20, columns, filters
        )
        if chunksize:
            return iterator
        return pd.concat(iterator, ignore_index=True)

    @staticmethod
    def _chunk_weekly_counts(
        chunk: pd.DataFrame,
        year: int,
        group_col: str,
        week_col: str,
        pathogen_cols: dict[str, list[str]],
    ) -> pd.DataFrame:
        """Aggregate one chunk into weekly counts by group and pathogen."""
        week = pd.to_numeric(chunk[week_col], errors="coerce")
        group = chunk[group_col].astype(str).str.strip()
        agg = pd.DataFrame({"epi_week": week, "group": group})
        series: dict[str, pd.Series] = {
            "total": agg.groupby(["epi_week", "group"]).size()
        }
        for pathogen, columns in pathogen_cols.items():
            mask = pd.Series(False, index=chunk.index)
            for column in columns:
                mask |= chunk[column].astype(str).str.strip().eq("1")
            series[f"cases_{_slugify_pathogen(pathogen)}"] = agg[mask].groupby(
                ["epi_week", "group"]
            ).size()
        out = pd.concat(series, axis=1).reset_index()
        out.insert(0, "year", year)
        return out

    def get_weekly_counts(
        self,
        years: list[int] | int,
        groupby: str = "state",
        pathogens: list[str] | str | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Weekly SRAG case counts grouped by geography and pathogen.

        Reads only the minimal columns of each year's file and returns a
        wide table with one ``total`` column plus one column per
        lab-confirmed pathogen.

        Parameters
        ----------
        years : int or list[int]
            SRAG years to aggregate.
        groupby : str
            ``"state"``, ``"municipality"``, ``"region"`` or
            ``"macroregion"``.
        pathogens : str or list[str], optional
            Pathogens to add as extra count columns (see
            :meth:`get_year`).  ``None`` returns totals only.

        Returns
        -------
        pd.DataFrame
            Columns ``year``, ``epi_week``, ``<group>``, ``total`` and
            one ``cases_<pathogen>`` column per requested pathogen.
        """
        key = groupby.strip().lower()
        if key not in GROUP_COLUMNS:
            known = ", ".join(sorted(GROUP_COLUMNS))
            raise ValueError(f"Unknown groupby {groupby!r}. Valid: {known}")
        if isinstance(years, int):
            years = [years]
        if isinstance(pathogens, str):
            pathogens = [pathogens]
        if pathogens:
            for p in pathogens:
                if _normalize_pathogen(p) not in PATHOGEN_COLUMNS:
                    known = ", ".join(sorted(set(PATHOGEN_COLUMNS)))
                    raise ValueError(f"Unknown pathogen {p!r}. Supported: {known}")

        frames: list[pd.DataFrame] = []
        for year in years:
            path = self._ensure_file(year, fmt="CSV", use_cache=use_cache)
            encoding = self._detect_encoding(path)
            reader = pd.read_csv(
                path,
                sep=";",
                encoding=encoding,
                dtype=str,
                chunksize=1 << 20,
            )
            group_col: str | None = None
            week_col: str | None = None
            pathogen_cols: dict[str, list[str]] = {}
            parts: list[pd.DataFrame] = []
            for chunk in reader:
                chunk.columns = [str(c).strip().upper() for c in chunk.columns]
                if group_col is None:
                    group_col = self._resolve_column(
                        df=chunk, candidates=GROUP_COLUMNS[key]
                    )
                    week_col = self._resolve_column(df=chunk, candidates=WEEK_COLUMNS)
                    if group_col is None or week_col is None:
                        raise ValueError(
                            f"Could not resolve grouping/week columns for "
                            f"{groupby!r} in SRAG {year} "
                            f"(looked for {GROUP_COLUMNS[key]} / {WEEK_COLUMNS})."
                        )
                    for p in pathogens or []:
                        pathogen_cols[p] = [
                            c
                            for c in PATHOGEN_COLUMNS[_normalize_pathogen(p)]
                            if c in {str(col).upper() for col in chunk.columns}
                        ]
                assert group_col is not None and week_col is not None
                parts.append(
                    self._chunk_weekly_counts(
                        chunk, year, group_col, week_col, pathogen_cols
                    )
                )
            if not parts:
                continue
            year_df = pd.concat(parts, ignore_index=True)
            groupers = [c for c in ["year", "epi_week", "group"] if c in year_df]
            value_cols = [c for c in year_df.columns if c not in groupers]
            year_df = year_df.groupby(groupers, as_index=False)[value_cols].sum(
                min_count=1
            )
            year_df = year_df.rename(columns={"group": group_col})
            frames.append(year_df)

        if not frames:
            return pd.DataFrame(columns=["year", "epi_week", key, "total"])
        result = pd.concat(frames, ignore_index=True)
        return result.sort_values(["year", "epi_week"]).reset_index(drop=True)

    # ------------------------------------------------------------------
    # IBGE municipality helpers
    # ------------------------------------------------------------------

    def get_municipalities(self, state: str | None = None) -> pd.DataFrame:
        """Return the IBGE municipality table.

        Parameters
        ----------
        state : str, optional
            Two-letter state abbreviation (e.g. ``"RJ"``).

        Returns
        -------
        pd.DataFrame
            Columns ``municipality_code`` (7-digit IBGE code),
            ``municipality_name``, ``state`` and ``state_name``.
        """
        cache_file = self.cache_dir / "ibge_municipios.json"
        if self._municipalities is None:
            if cache_file.exists():
                age = datetime.now() - datetime.fromtimestamp(
                    cache_file.stat().st_mtime
                )
                if age < timedelta(days=30):
                    self._municipalities = pd.read_json(
                        cache_file, dtype={"municipality_code": str}
                    )
            if self._municipalities is None:
                try:
                    resp = self._session.get(
                        IBGE_MUNICIPALITIES_URL, timeout=self.timeout
                    )
                    resp.raise_for_status()
                    payload = resp.json()
                except requests.RequestException as exc:
                    raise SRAGDataError(
                        f"Failed to fetch IBGE municipalities: {exc}. Retry later."
                    ) from exc
                rows = []
                for m in payload:
                    uf = (
                        ((m.get("microrregiao") or {}).get("mesorregiao") or {})
                        .get("UF")
                        or {}
                    )
                    rows.append(
                        {
                            "municipality_code": str(m.get("id", "")).zfill(7),
                            "municipality_name": m.get("nome", ""),
                            "state": uf.get("sigla", ""),
                            "state_name": uf.get("nome", ""),
                        }
                    )
                self._municipalities = pd.DataFrame(rows)
                self._municipalities.to_json(
                    cache_file, orient="records", force_ascii=False
                )
        table = self._municipalities
        if state:
            table = table[table["state"].str.upper() == state.upper()]
        return table.reset_index(drop=True)

    def municipality_name(self, code: int | str) -> str:
        """Resolve an IBGE municipality code to its name."""
        key = _municipality_key(code)
        table = self.get_municipalities()
        match = table[table["municipality_code"].map(_municipality_key) == key]
        if match.empty:
            raise ValueError(f"Unknown IBGE municipality code {code!r}.")
        return str(match.iloc[0]["municipality_name"])

    def municipality_code(self, name: str, state: str | None = None) -> str:
        """Resolve a municipality name to its 7-digit IBGE code.

        Parameters
        ----------
        name : str
            Municipality name (case- and accent-insensitive).
        state : str, optional
            Two-letter state to disambiguate homonyms.
        """
        table = self.get_municipalities(state=state)
        target = _normalize_pathogen(name)
        normalized = table["municipality_name"].map(_normalize_pathogen)
        match = table[normalized == target]
        if match.empty:
            raise ValueError(
                f"Unknown municipality {name!r}"
                + (f" in state {state!r}" if state else "")
                + "."
            )
        if len(match) > 1 and state is None:
            options = ", ".join(sorted(match["state"]))
            raise ValueError(
                f"Multiple municipalities named {name!r} (states: {options}); "
                "pass state=<UF> to disambiguate."
            )
        return str(match.iloc[0]["municipality_code"])

    # ------------------------------------------------------------------
    # BaseAccessor interface
    # ------------------------------------------------------------------

    def list_countries(self) -> pd.DataFrame:
        """Return countries covered by this source (Brazil only)."""
        return pd.DataFrame([{"country_code": "BR", "country_name": "Brazil"}])
