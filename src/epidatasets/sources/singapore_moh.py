"""
Singapore Ministry of Health (MOH) Weekly Infectious Disease Bulletin Accessor

Provides access to the "Weekly Infectious Disease Bulletin Cases" dataset
published by the Singapore Ministry of Health (MOH) via data.gov.sg.

The dataset reports the number of notified cases for ~30+ notifiable
infectious diseases (including Dengue, Chikungunya, Cholera, Avian
Influenza, Acute Viral Hepatitis B/C, etc.) at the national level, broken
down by epidemiological week.

Data Sources:
- Dataset page: https://data.gov.sg/datasets/d_ca168b2cb763640d72c4600a68f9909e
- REST API: https://data.gov.sg/api/action/datastore_search
- API Docs: https://guide.data.gov.sg/developer-guide/api-overview

Temporal Coverage: 2012-2022 (epidemiological weeks)
Geographic Coverage: National (Singapore)
Update Frequency: Weekly (historical dataset)

License: Singapore Open Data Licence (free for personal/commercial use)

Citation:
    Ministry of Health. (2016). Weekly Infectious Disease Bulletin Cases
    [Dataset]. data.gov.sg.

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


class SingaporeMOHAccessor(BaseAccessor):
    """
    Accessor for the Singapore MOH Weekly Infectious Disease Bulletin Cases.

    Provides access to weekly notified case counts for ~30+ notifiable
    infectious diseases in Singapore, sourced from the Ministry of Health
    via the data.gov.sg CKAN datastore REST API.

    Example:
        >>> moh = SingaporeMOHAccessor()
        >>>
        >>> # List notifiable diseases covered
        >>> diseases = moh.list_diseases()
        >>>
        >>> # Fetch all weekly bulletin cases
        >>> df = moh.get_cases()
        >>>
        >>> # Filter by disease and/or year
        >>> dengue = moh.get_cases(disease="Dengue Fever", years=[2019, 2020])
        >>>
        >>> # Fetch a specific epidemiological week
        >>> week = moh.get_cases(epi_week="2020-W15")

    Data Sources:
        - Dataset: https://data.gov.sg/datasets/d_ca168b2cb763640d72c4600a68f9909e
        - API: https://data.gov.sg/api/action/datastore_search
    """

    source_name: ClassVar[str] = "singapore_moh"
    source_description: ClassVar[str] = (
        "Weekly Infectious Disease Bulletin Cases from the Singapore Ministry "
        "of Health (MOH) via data.gov.sg, covering ~30+ notifiable diseases "
        "by epidemiological week (2012-2022)."
    )
    source_url: ClassVar[str] = (
        "https://data.gov.sg/datasets/d_ca168b2cb763640d72c4600a68f9909e"
    )

    API_BASE = "https://data.gov.sg/api/action/datastore_search"
    DATASET_URL = (
        "https://data.gov.sg/datasets/d_ca168b2cb763640d72c4600a68f9909e"
    )
    RESOURCE_ID = "d_ca168b2cb763640d72c4600a68f9909e"

    DEFAULT_PAGE_SIZE = 10_000
    REQUEST_TIMEOUT = 60

    # Notifiable diseases tracked in the Singapore bulletin.  Used as a
    # reference list and for sample/fallback data generation.
    NOTIFIABLE_DISEASES: ClassVar[list[str]] = [
        "Acute Viral hepatitis B",
        "Acute Viral hepatitis C",
        "Avian Influenza",
        "Campylobacterenterosis",
        "Chikungunya Fever",
        "Cholera",
        "Dengue Fever",
        "Dengue Haemorrhagic Fever",
        "Diphtheria",
        "Enterovirus A71 (EV-A71)",
        "Food-borne illness",
        "Haemophilus influenzae type b",
        "Hand, Foot and Mouth Disease",
        "Hepatitis A",
        "Hepatitis E",
        "Herpangina",
        "Influenza",
        "Legionellosis",
        "Leprosy",
        "Leptospirosis",
        "Malaria",
        "Measles",
        "Meningococcal Disease",
        "Mumps",
        "Nipah Virus Infection",
        "Non-tuberculous Mycobacterial Disease",
        "Pertussis",
        "Plague",
        "Pneumococcal Disease (invasive)",
        "Poliomyelitis",
        "Rabies",
        "Rubella",
        "Salmonellosis (non-enteric fever)",
        "Scrub Typhus",
        "Severe Acute Respiratory Syndrome (SARS)",
        "Smallpox",
        "Tetanus",
        "Tuberculosis",
        "Typhoid Fever",
        "Varicella",
        "Viral Haemorrhagic Fever (other)",
        "Yellow Fever",
        "Zika Virus Infection",
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
                Path.home() / ".cache" / "epi_data" / "singapore_moh"
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

    # ------------------------------------------------------------------
    # Low-level API helpers
    # ------------------------------------------------------------------
    def _api_search(
        self,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
        filters: dict[str, str | int] | None = None,
        fields: list[str] | None = None,
    ) -> dict:
        """Call the CKAN datastore_search endpoint.

        Parameters
        ----------
        limit : int
            Maximum number of records to return per page.
        offset : int
            Offset for pagination.
        filters : dict, optional
            Mapping of field name to value, applied server-side via the
            ``filters`` query parameter.
        fields : list of str, optional
            Restrict the returned columns.

        Returns
        -------
        dict
            The decoded JSON ``result`` object.
        """
        params: dict[str, str | int | list[str]] = {
            "resource_id": self.RESOURCE_ID,
            "limit": limit,
            "offset": offset,
        }
        if filters:
            import json

            params["filters"] = json.dumps(filters)
        if fields:
            params["fields"] = ",".join(fields)

        url = f"{self.API_BASE}?{urlencode(params)}"
        try:
            resp = self._session.get(url, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("SingaporeMOHAccessor: request to %s failed: %s", url, exc)
            raise RuntimeError(f"Failed to query data.gov.sg API: {exc}") from exc

        payload = resp.json()
        if not payload.get("success", False):
            error = payload.get("error", {}).get("message", "unknown error")
            raise RuntimeError(f"data.gov.sg API call unsuccessful: {error}")

        return payload.get("result", {})

    def _fetch_all(
        self,
        filters: dict[str, str | int] | None = None,
        fields: list[str] | None = None,
        max_records: int | None = None,
    ) -> pd.DataFrame:
        """Page through the datastore until all matching records are fetched."""
        frames: list[pd.DataFrame] = []
        offset = 0
        total: int | None = None

        while True:
            result = self._api_search(
                limit=self.DEFAULT_PAGE_SIZE,
                offset=offset,
                filters=filters,
                fields=fields,
            )
            records = result.get("records", [])
            if records:
                frames.append(pd.DataFrame(records))
            if total is None:
                total = result.get("total")

            offset += len(records)
            if len(records) < self.DEFAULT_PAGE_SIZE:
                break
            if max_records is not None and offset >= max_records:
                break

        if not frames:
            return pd.DataFrame(
                columns=["epi_week", "disease", "no._of_cases"]
            )

        df = pd.concat(frames, ignore_index=True)
        if max_records is not None and len(df) > max_records:
            df = df.iloc[:max_records].reset_index(drop=True)

        return self._normalise(df)

    @staticmethod
    def _normalise(df: pd.DataFrame) -> pd.DataFrame:
        """Clean and type-cast raw API records."""
        if df.empty:
            return df

        # Coerce case counts to numeric.  The API returns them as strings.
        if "no._of_cases" in df.columns:
            df["no._of_cases"] = pd.to_numeric(
                df["no._of_cases"], errors="coerce"
            ).fillna(0).astype(int)

        if "_id" in df.columns:
            df = df.drop(columns=["_id"])

        if "epi_week" in df.columns:
            df = df.sort_values(
                ["epi_week", "disease"], kind="stable"
            ).reset_index(drop=True)

        return df

    # ------------------------------------------------------------------
    # Public data accessors
    # ------------------------------------------------------------------
    def list_diseases(self, refresh: bool = False) -> pd.DataFrame:
        """Return the distinct diseases present in the dataset.

        Parameters
        ----------
        refresh : bool
            Force a fresh API query rather than using the cached result.

        Returns
        -------
        pd.DataFrame
            Columns ``disease`` and ``record_count`` (number of epi-weeks
            in which the disease appears).
        """
        cache_path = self.cache_dir / "diseases.parquet"
        if not refresh and cache_path.exists():
            try:
                return pd.read_parquet(cache_path)
            except Exception:
                pass

        try:
            df = self._fetch_all(fields=["disease", "epi_week"])
        except RuntimeError as exc:
            logger.warning(
                "SingaporeMOHAccessor: falling back to static disease list: %s",
                exc,
            )
            return pd.DataFrame(
                {"disease": self.NOTIFIABLE_DISEASES}
            )

        if df.empty:
            return pd.DataFrame({"disease": self.NOTIFIABLE_DISEASES})

        summary = (
            df.groupby("disease")["epi_week"]
            .nunique()
            .reset_index(name="record_count")
            .sort_values("disease")
            .reset_index(drop=True)
        )
        try:
            summary.to_parquet(cache_path, index=False)
        except Exception:
            pass
        return summary

    def list_epi_weeks(self) -> pd.DataFrame:
        """Return the distinct epidemiological weeks covered by the dataset."""
        try:
            df = self._fetch_all(fields=["epi_week"])
        except RuntimeError as exc:
            logger.warning(
                "SingaporeMOHAccessor: using sample epi-weeks: %s", exc
            )
            return self._sample_data()["epi_week"].drop_duplicates().to_frame()

        if df.empty:
            return pd.DataFrame(columns=["epi_week"])

        weeks = (
            df[["epi_week"]]
            .drop_duplicates()
            .sort_values("epi_week")
            .reset_index(drop=True)
        )
        years = weeks["epi_week"].str.extract(
            r"(\d{4})", expand=False
        ).astype("Int64")
        weeks["year"] = years
        return weeks

    def get_cases(
        self,
        disease: str | list[str] | None = None,
        years: int | list[int] | None = None,
        epi_week: str | list[str] | None = None,
        use_cache: bool = True,
        max_records: int | None = None,
    ) -> pd.DataFrame:
        """
        Fetch weekly infectious disease bulletin cases.

        Parameters
        ----------
        disease : str or list of str, optional
            Filter to one or more disease names (case-sensitive, matching the
            dataset exactly, e.g. ``"Dengue Fever"``).
        years : int or list of int, optional
            Filter to one or more years (e.g. ``[2019, 2020]``).
        epi_week : str or list of str, optional
            Filter to specific epidemiological weeks in ``YYYY-Www`` format
            (e.g. ``"2020-W15"``).
        use_cache : bool
            If True (default), return a cached copy when available.
        max_records : int, optional
            Cap on the total number of records returned.

        Returns
        -------
        pd.DataFrame
            Columns: ``epi_week``, ``disease``, ``no._of_cases``.  When
            ``years`` is given, a ``year`` column is added.
        """
        filters: dict[str, str | int] = {}

        if disease is not None:
            if isinstance(disease, (list, tuple, set)):
                values = list(disease)
                if len(values) == 1:
                    filters["disease"] = str(values[0])
            else:
                filters["disease"] = str(disease)

        if epi_week is not None:
            if isinstance(epi_week, (list, tuple, set)):
                values = list(epi_week)
                if len(values) == 1:
                    filters["epi_week"] = str(values[0])
            else:
                filters["epi_week"] = str(epi_week)

        cache_key_parts = [str(filters)]
        if years is not None:
            cache_key_parts.append(str(sorted(_as_list(years))))
        cache_key_parts.append(str(max_records))
        cache_key = _slugify("|".join(cache_key_parts))

        if use_cache:
            df = self._load_cache(cache_key)
            if df is not None:
                return df

        try:
            df = self._fetch_all(filters=filters, max_records=max_records)
        except RuntimeError:
            logger.warning(
                "SingaporeMOHAccessor: API unavailable, returning sample data"
            )
            df = self._sample_data()

        if years is not None and not df.empty and "epi_week" in df.columns:
            wanted = set(_as_list(years))
            extracted = df["epi_week"].str.extract(
                r"(\d{4})", expand=False
            ).astype("Int64")
            df = df.assign(year=extracted)
            df = df[df["year"].isin(wanted)].reset_index(drop=True)
        elif not df.empty and "epi_week" in df.columns:
            extracted = df["epi_week"].str.extract(
                r"(\d{4})", expand=False
            ).astype("Int64")
            df = df.assign(year=extracted)

        if disease is not None and "disease" in df.columns and not df.empty:
            wanted_diseases = set(_as_list(disease))
            df = df[df["disease"].isin(wanted_diseases)].reset_index(drop=True)

        if use_cache:
            self._save_cache(cache_key, df)
        return df

    def get_dengue_cases(
        self,
        years: int | list[int] | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Convenience wrapper returning Dengue Fever and Dengue Haemorrhagic Fever cases."""
        return self.get_cases(
            disease=["Dengue Fever", "Dengue Haemorrhagic Fever"],
            years=years,
            use_cache=use_cache,
        )

    def get_summary(
        self,
        by: str = "disease",
    ) -> pd.DataFrame:
        """
        Aggregate the full bulletin into a summary table.

        Parameters
        ----------
        by : str
            One of ``"disease"`` or ``"year"``.  Groups case counts by the
            chosen dimension.

        Returns
        -------
        pd.DataFrame
            Aggregated case counts.
        """
        if by not in ("disease", "year"):
            raise ValueError("`by` must be 'disease' or 'year'")

        df = self.get_cases()
        if df.empty:
            return df

        if by == "year":
            return (
                df.groupby("year", as_index=False)["no._of_cases"]
                .sum()
                .sort_values("year")
                .reset_index(drop=True)
            )

        return (
            df.groupby("disease", as_index=False)["no._of_cases"]
            .sum()
            .sort_values("no._of_cases", ascending=False)
            .reset_index(drop=True)
        )

    # ------------------------------------------------------------------
    # Caching
    # ------------------------------------------------------------------
    def _cache_path(self, key: str, ext: str = "parquet") -> Path:
        return self.cache_dir / f"cases_{key}.{ext}"

    def _load_cache(self, key: str) -> pd.DataFrame | None:
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            df = pd.read_parquet(path)
            if self._is_cache_fresh(path):
                return df
        except Exception:
            pass
        return None

    def _save_cache(self, key: str, df: pd.DataFrame) -> None:
        if df.empty:
            return
        path = self._cache_path(key)
        try:
            df.to_parquet(path, index=False)
        except Exception as exc:
            logger.debug("SingaporeMOHAccessor: cache write failed: %s", exc)

    def _is_cache_fresh(self, path: Path) -> bool:
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        return datetime.now() - mtime < timedelta(days=1)

    # ------------------------------------------------------------------
    # Sample / fallback data
    # ------------------------------------------------------------------
    def _sample_data(self) -> pd.DataFrame:
        """Return representative sample data for Singapore (fallback)."""
        weeks = [f"2020-W{w:02d}" for w in range(1, 14)]
        diseases = [
            "Dengue Fever",
            "Dengue Haemorrhagic Fever",
            "Chikungunya Fever",
            "Cholera",
            "Acute Viral hepatitis B",
            "Hand, Foot and Mouth Disease",
            "Influenza",
            "Malaria",
            "Measles",
            "Salmonellosis (non-enteric fever)",
            "Typhoid Fever",
            "Varicella",
            "Zika Virus Infection",
        ]
        import itertools
        import random

        random.seed(42)
        rows = []
        for epi_week, disease in itertools.product(weeks, diseases):
            base = {
                "Dengue Fever": (40, 320),
                "Dengue Haemorrhagic Fever": (1, 12),
                "Chikungunya Fever": (0, 8),
                "Cholera": (0, 2),
                "Acute Viral hepatitis B": (1, 6),
                "Hand, Foot and Mouth Disease": (150, 950),
                "Influenza": (200, 1800),
                "Malaria": (2, 18),
                "Measles": (0, 4),
                "Salmonellosis (non-enteric fever)": (5, 45),
                "Typhoid Fever": (0, 5),
                "Varicella": (30, 220),
                "Zika Virus Infection": (0, 3),
            }.get(disease, (0, 10))
            cases = random.randint(base[0], base[1])
            rows.append(
                {
                    "epi_week": epi_week,
                    "disease": disease,
                    "no._of_cases": cases,
                }
            )
        return pd.DataFrame(rows)


def _as_list(value) -> list:
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _slugify(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_")[:64] or "all"
