"""
OpenDengue — Global Dengue Case Count Database Accessor

Provides access to **OpenDengue**, an open database of dengue case counts
collated from publicly available surveillance data across dengue-affected
countries worldwide (Clarke et al., 2024, *Scientific Data*).

Key characteristics:

- One row per unique location-time combination, with total reported case
  counts (``dengue_total``) at national (Admin0), state/province (Admin1)
  or district (Admin2) level;
- ~100+ countries, some with series back to 1924 (most from 1990 onward);
- Three global extracts per release:
  ``national`` (country totals), ``highest_spatial`` (finest spatial
  resolution per country) and ``highest_temporal`` (finest temporal
  resolution per country);
- Versioned releases hosted on the OpenDengue GitHub repository.

Data Sources:
- Website: https://opendengue.org/
- GitHub: https://github.com/OpenDengue/master-repo
- Figshare DOI: https://doi.org/10.6084/m9.figshare.24259573
- Publication: https://doi.org/10.1038/s41597-024-03120-7

Authentication: None required
Update Frequency: ~monthly releases
License: CC BY 4.0 — **citation required** (see :data:`CITATION`).
"""

from __future__ import annotations

import difflib
import logging
import re
import time
import unicodedata
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

from epidatasets._base import BaseAccessor

logger = logging.getLogger(__name__)

#: Mandatory citation for the CC BY 4.0 licensed dataset.
CITATION = (
    "Clarke J, Lim A, Gupte P, Pigott DM, van Panhuis WG, Brady OJ. "
    "A global dataset of publicly available dengue case count data. "
    "Scientific Data. 2024;11(1):296. https://doi.org/10.1038/s41597-024-03120-7 "
    "(OpenDengue, CC BY 4.0, https://doi.org/10.6084/m9.figshare.24259573)"
)

#: Release identifiers of the three global extracts.
LEVELS: dict[str, str] = {
    "national": "National",
    "highest_spatial": "Spatial",
    "highest_temporal": "Temporal",
}

_DATE_COLUMNS = ["calendar_start_date", "calendar_end_date"]


class OpenDengueDataError(Exception):
    """Raised when OpenDengue downloads fail or a country is unknown."""


def _normalize_name(value: str) -> str:
    """Normalize a country/region name: lowercase, accent-free, collapsed."""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text.strip().lower())


class OpenDengueAccessor(BaseAccessor):
    """Accessor for the OpenDengue global dengue case count database.

    Example
    -------
    >>> from epidatasets.sources.opendengue import OpenDengueAccessor
    >>> od = OpenDengueAccessor()
    >>> print(od.citation())                  # CC BY 4.0, cite it!
    >>> national = od.get_global(level="national")
    >>> brazil = od.get_country("Brazil")     # finest resolution
    >>> rj = od.get_timeseries("Brazil", admin1="Rio de Janeiro")
    """

    source_name = "opendengue"
    source_description = (
        "OpenDengue — global database of publicly available dengue case "
        "counts, collated for 100+ countries at national/state/district "
        "level (Clarke et al. 2024, Sci Data; CC BY 4.0)."
    )
    source_url = "https://opendengue.org/"

    #: Latest release known to work with this accessor
    DEFAULT_VERSION = "V1.3"
    RAW_BASE = "https://raw.githubusercontent.com/OpenDengue/master-repo/main"

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        cache_ttl_days: float = 30.0,
        version: str | None = None,
        timeout: int = 300,
        max_retries: int = 3,
        base_url: str | None = None,
    ):
        """Initialize the OpenDengue accessor.

        Parameters
        ----------
        cache_dir : str or Path, optional
            Directory for cached downloads (default
            ``~/.cache/epi_data/opendengue``).
        cache_ttl_days : float
            Cache TTL in days, aligned with the ~monthly release cycle.
        version : str, optional
            Release version (default ``"V1.3"``).
        timeout : int
            HTTP timeout in seconds (extracts are ~55 MB compressed).
        max_retries : int
            Attempts for transient failures.
        base_url : str, optional
            Override the download base URL (for testing).
        """
        self.cache_dir = (
            Path(cache_dir)
            if cache_dir
            else Path.home() / ".cache" / "epi_data" / "opendengue"
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_ttl = timedelta(days=cache_ttl_days)
        self.version = version or self.DEFAULT_VERSION
        self.timeout = timeout
        self.max_retries = max(1, max_retries)
        self.base_url = base_url or self.RAW_BASE
        self._session = requests.Session()

    # ------------------------------------------------------------------
    # Public metadata
    # ------------------------------------------------------------------

    @staticmethod
    def citation() -> str:
        """Return the mandatory dataset citation (CC BY 4.0)."""
        return CITATION

    def list_countries(
        self, level: str = "national", use_cache: bool = True
    ) -> pd.DataFrame:
        """List the countries present in a global extract.

        Satisfies the :class:`~epidatasets._base.BaseAccessor` interface
        (columns ``country_code``/``country_name``).

        Parameters
        ----------
        level : str
            ``"national"``, ``"highest_spatial"`` or
            ``"highest_temporal"``.
        use_cache : bool
            Use the filesystem cache when possible.

        Returns
        -------
        pd.DataFrame
            Columns ``country_name`` and ``country_code`` (ISO 3166-1
            alpha-3).
        """
        df = self.get_global(level=level, use_cache=use_cache)
        return (
            df[["adm_0_name", "ISO_A0"]]
            .drop_duplicates()
            .rename(columns={"adm_0_name": "country_name", "ISO_A0": "country_code"})
            .sort_values("country_name")
            .reset_index(drop=True)
        )

    # ------------------------------------------------------------------
    # Download + cache
    # ------------------------------------------------------------------

    def _zip_url(self, level: str) -> str:
        try:
            release = LEVELS[level]
        except KeyError:
            known = ", ".join(sorted(LEVELS))
            raise ValueError(
                f"Unknown level {level!r}. Valid levels: {known}"
            ) from None
        # release directories use dots (V1.3), file names use underscores
        file_version = self.version.replace(".", "_")
        return (
            f"{self.base_url}/data/releases/{self.version}/"
            f"{release}_extract_{file_version}.zip"
        )

    def _is_cache_valid(self, path: Path) -> bool:
        if not path.exists():
            return False
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        return datetime.now() - mtime < self._cache_ttl

    def _download(self, url: str, destination: Path) -> Path:
        """Stream a file to ``destination`` atomically, with retries."""
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
            raise OpenDengueDataError(
                f"Failed to download OpenDengue {self.version} from {url}: "
                f"{exc}. Retry later or pin another version."
            ) from exc

    def _ensure_extract(self, level: str, use_cache: bool = True) -> Path:
        """Download (or reuse) one global extract, returning the CSV path."""
        url = self._zip_url(level)
        csv_path = self.cache_dir / f"{LEVELS[level]}_extract_{self.version}.csv"
        if use_cache and self._is_cache_valid(csv_path):
            return csv_path
        zip_path = self.cache_dir / f"{LEVELS[level]}_extract_{self.version}.zip"
        self._download(url, zip_path)
        try:
            with zipfile.ZipFile(zip_path) as archive:
                names = [n for n in archive.namelist() if n.lower().endswith(".csv")]
                if not names:
                    raise OpenDengueDataError(f"No CSV entry inside {zip_path.name}.")
                with archive.open(names[0]) as src, open(csv_path, "wb") as dst:
                    for chunk in iter(lambda: src.read(1 << 20), b""):
                        dst.write(chunk)
        except zipfile.BadZipFile as exc:
            zip_path.unlink(missing_ok=True)
            csv_path.unlink(missing_ok=True)
            raise OpenDengueDataError(
                f"Corrupted download for {zip_path.name}: {exc}. "
                "The cache was cleared; retry."
            ) from exc
        zip_path.unlink(missing_ok=True)  # keep only the extracted CSV
        return csv_path

    @staticmethod
    def _read_extract(path: Path) -> pd.DataFrame:
        df = pd.read_csv(path)
        df.columns = [str(c).strip() for c in df.columns]
        for column in _DATE_COLUMNS:
            if column in df.columns:
                df[column] = pd.to_datetime(df[column], errors="coerce")
        if "dengue_total" in df.columns:
            df["dengue_total"] = pd.to_numeric(df["dengue_total"], errors="coerce")
        if "Year" in df.columns:
            df["Year"] = pd.to_numeric(df["Year"], errors="coerce").astype("Int64")
        return df

    # ------------------------------------------------------------------
    # Public data access
    # ------------------------------------------------------------------

    def get_global(
        self, level: str = "national", use_cache: bool = True
    ) -> pd.DataFrame:
        """Load one of the three global OpenDengue extracts.

        Parameters
        ----------
        level : str
            ``"national"`` (country totals, small), ``"highest_spatial"``
            (finest spatial resolution per country, ~500 MB in memory)
            or ``"highest_temporal"`` (finest temporal resolution per
            country).

        Returns
        -------
        pd.DataFrame
            Standard OpenDengue columns (``adm_0_name``, ``adm_1_name``,
            ``adm_2_name``, ``calendar_start_date``,
            ``calendar_end_date``, ``Year``, ``dengue_total``,
            ``case_definition_standardised``, ``S_res``, ``T_res``,
            ``UUID``, ...).
        """
        path = self._ensure_extract(level, use_cache=use_cache)
        return self._read_extract(path)

    # -- country helpers -------------------------------------------------

    @staticmethod
    def _country_names(df: pd.DataFrame) -> dict[str, str]:
        """Map normalized country name -> canonical name."""
        pairs = df[["adm_0_name"]].dropna().drop_duplicates()
        return {_normalize_name(n): str(n) for n in pairs["adm_0_name"]}

    def _match_country(self, df: pd.DataFrame, country: str) -> str:
        """Resolve a country name/ISO3 to the canonical ``adm_0_name``."""
        names = self._country_names(df)
        target = _normalize_name(country)

        if target in names:
            return names[target]

        if "ISO_A0" in df.columns:
            iso = str(country).strip().upper()
            codes = df[["adm_0_name", "ISO_A0"]].dropna().drop_duplicates()
            hit = codes[codes["ISO_A0"].str.upper() == iso]
            if not hit.empty:
                return str(hit.iloc[0]["adm_0_name"])

        close = difflib.get_close_matches(target, list(names), n=3, cutoff=0.8)
        if close:
            matched = names[close[0]]
            logger.info("Fuzzy-matched country %r -> %r", country, matched)
            return matched
        suggestions = ", ".join(names[c] for c in close) if close else "none"
        raise OpenDengueDataError(
            f"Country {country!r} not found in OpenDengue. "
            f"Closest matches: {suggestions}. Use list_countries() to "
            "see all available names."
        )

    @staticmethod
    def _normalize_dates(
        start_date: str | datetime | None,
        end_date: str | datetime | None,
    ) -> tuple[datetime | None, datetime | None]:
        def parse(value: str | datetime | None) -> datetime | None:
            if value is None or isinstance(value, datetime):
                return value
            return pd.to_datetime(value)

        start, end = parse(start_date), parse(end_date)
        if start and end and start > end:
            raise ValueError("start_date must not be after end_date.")
        return start, end

    @staticmethod
    def _date_mask(
        df: pd.DataFrame,
        start: datetime | None,
        end: datetime | None,
    ) -> pd.Series:
        """Keep rows whose reporting period overlaps [start, end]."""
        if "calendar_start_date" not in df.columns:
            return pd.Series(True, index=df.index)
        keep = pd.Series(True, index=df.index)
        if end is not None:
            keep &= df["calendar_start_date"] <= end
        if start is not None:
            column = df["calendar_end_date"]
            column = column.fillna(df["calendar_start_date"])
            keep &= column >= start
        return keep

    @staticmethod
    def _admin_mask(df: pd.DataFrame, admin_level: int | None) -> pd.Series:
        if admin_level is None:
            return pd.Series(True, index=df.index)
        if admin_level not in (0, 1, 2):
            raise ValueError("admin_level must be 0, 1 or 2.")
        if "S_res" not in df.columns:
            return pd.Series(True, index=df.index)
        return df["S_res"].astype(str).str.lower() == f"admin{admin_level}"

    def get_country(
        self,
        country: str,
        start_date: str | datetime | None = None,
        end_date: str | datetime | None = None,
        admin_level: int | None = None,
        level: str = "highest_temporal",
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Load the dengue case counts of one country.

        Parameters
        ----------
        country : str
            Country name (case/accent-insensitive, fuzzy-matched) or
            ISO 3166-1 alpha-3 code (e.g. ``"BRA"``).
        start_date, end_date : str or datetime, optional
            Keep rows whose reporting period overlaps the range.
        admin_level : int, optional
            ``0``, ``1`` or ``2`` to restrict to national, adm1 (state)
            or adm2 (district) series.
        level : str
            Global extract to filter from; default
            ``"highest_temporal"`` (finest temporal resolution per
            country — usually the best for time-series).  Use
            ``"highest_spatial"`` for the finest spatial detail and
            ``"national"`` for plain country totals.
        use_cache : bool
            Use the filesystem cache when possible.

        Returns
        -------
        pd.DataFrame
            One row per location-period, sorted by ``calendar_start_date``.

        Raises
        ------
        OpenDengueDataError
            If the country cannot be matched.
        """
        df = self.get_global(level=level, use_cache=use_cache)
        canonical = self._match_country(df, country)
        out = df[df["adm_0_name"] == canonical]
        start, end = self._normalize_dates(start_date, end_date)
        out = out[self._date_mask(out, start, end)]
        out = out[self._admin_mask(out, admin_level)]
        if "calendar_start_date" in out.columns:
            out = out.sort_values("calendar_start_date")
        return out.reset_index(drop=True)

    def get_timeseries(
        self,
        country: str,
        admin1: str | None = None,
        admin2: str | None = None,
        start_date: str | datetime | None = None,
        end_date: str | datetime | None = None,
        level: str = "highest_temporal",
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Case-count time-series for one specific location.

        Parameters
        ----------
        country : str
            Country name or ISO3 code.
        admin1 : str, optional
            State/province name (case/accent-insensitive).
        admin2 : str, optional
            District name (case/accent-insensitive).
        start_date, end_date : str or datetime, optional
            Reporting-period overlap filter.

        Returns
        -------
        pd.DataFrame
            Rows for the selected location sorted by date.
        """

        def location_mask(df: pd.DataFrame, column: str, value: str) -> pd.Series:
            if column not in df.columns:
                return pd.Series(False, index=df.index)
            target = _normalize_name(value)
            return df[column].map(_normalize_name) == target

        df = self.get_country(
            country,
            start_date=start_date,
            end_date=end_date,
            level=level,
            use_cache=use_cache,
        )
        if admin1 is not None:
            df = df[location_mask(df, "adm_1_name", admin1)]
            if df.empty:
                raise OpenDengueDataError(
                    f"Admin-1 location {admin1!r} not found for "
                    f"{country!r}. Inspect the adm_1_name values of "
                    "get_country() for valid names."
                )
        if admin2 is not None:
            df = df[location_mask(df, "adm_2_name", admin2)]
            if df.empty:
                raise OpenDengueDataError(
                    f"Admin-2 location {admin2!r} not found for "
                    f"{country!r}. Inspect the adm_2_name values of "
                    "get_country() for valid names."
                )
        return df.reset_index(drop=True)

    def get_sources(
        self,
        country: str | None = None,
        level: str = "national",
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Summarize the underlying data-source series per country.

        Each OpenDengue ``UUID`` identifies one source series (the
        prefix encodes the originating surveillance source, e.g.
        ``WHOEMRO``, ``PAHO``).  This helper counts the distinct series
        and rows per country.

        Parameters
        ----------
        country : str, optional
            Restrict to one country (fuzzy-matched).
        level : str
            Global extract to inspect.
        use_cache : bool
            Use the filesystem cache when possible.

        Returns
        -------
        pd.DataFrame
            Columns ``adm_0_name``, ``n_series`` (distinct UUIDs) and
            ``n_records``.
        """
        df = self.get_global(level=level, use_cache=use_cache)
        if country is not None:
            canonical = self._match_country(df, country)
            df = df[df["adm_0_name"] == canonical]
        uuid_column = "UUID" if "UUID" in df.columns else None
        if uuid_column is None:
            raise OpenDengueDataError("UUID column missing from this release.")
        grouped = (
            df.groupby("adm_0_name")
            .agg(n_series=("UUID", "nunique"), n_records=("UUID", "size"))
            .reset_index()
            .sort_values("n_records", ascending=False)
        )
        return grouped.reset_index(drop=True)
