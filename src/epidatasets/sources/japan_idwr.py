"""
Japan IDWR (Infectious Diseases Weekly Report) Accessor

This module provides access to the Japan Infectious Diseases Weekly Report
(IDWR) published by the Japan Institute for Health Security (JIHS, formerly
the National Institute of Infectious Diseases — NIID).

The IDWR provides prefecture-level weekly surveillance data for:

- **Notifiable diseases** (88 diseases, e.g. measles, rubella, pertussis,
  tuberculosis, syphilis) — cases by week and cumulative totals
- **Sentinel-reporting diseases** (19 diseases, e.g. influenza, RSV,
  chickenpox, hand-foot-and-mouth disease) — cases and cases-per-sentinel,
  both weekly and cumulative

Data Sources:
- IDWR portal (English): https://id-info.jihs.go.jp/en/surveillance/idwr/
- Rapid reports (weekly CSVs): https://id-info.jihs.go.jp/en/surveillance/idwr/rapid/
- JIHS: https://www.jihs.go.jp/

Coverage:
- Geography: Japan — all 47 prefectures (adm1)
- Time: epidemiological weeks, **2023-W01 to present** on the current
  portal (earlier reports live in the legacy NIID archive with a
  different structure and are not covered by this accessor)

Authentication: None required (public CSV downloads)
Update Frequency: Weekly (Tuesday preliminary, Friday final)
License: Open data (terms of use on the portal)

Author: Flávio Codeço Coelho
License: MIT
"""

import io
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar

import pandas as pd
import requests

from epidatasets._base import BaseAccessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JapanIDWRDataError(Exception):
    """
    Raised when an IDWR weekly report cannot be retrieved or parsed.

    This typically means the requested week has not been published yet,
    does not exist in the requested year, or the download failed after
    retries.
    """


@dataclass
class WeeklyReport:
    """
    Parsed tables for a single IDWR weekly report.

    Attributes:
        year: Epidemiological year.
        week: Epidemiological week number.
        as_of: "Data collected as of" date parsed from the report, if present.
        notifiable_diseases: Tidy DataFrame with columns ``prefecture``,
            ``disease``, ``current_week``, ``cumulative``.
        sentinel_diseases: Tidy DataFrame with columns ``prefecture``,
            ``disease``, ``current_week``, ``per_sentinel``.
        sentinel_diseases_delayed: Same shape as ``sentinel_diseases``,
            including delayed reports (Table "teitenari").
        sentinel_diseases_cumulative: Tidy DataFrame with columns
            ``prefecture``, ``disease``, ``cumulative_cases``,
            ``cumulative_per_sentinel``.
        national_totals: National ("Total No.") row for every table.
    """

    year: int
    week: int
    as_of: pd.Timestamp | None = None
    notifiable_diseases: pd.DataFrame = field(default_factory=pd.DataFrame)
    sentinel_diseases: pd.DataFrame = field(default_factory=pd.DataFrame)
    sentinel_diseases_delayed: pd.DataFrame = field(default_factory=pd.DataFrame)
    sentinel_diseases_cumulative: pd.DataFrame = field(default_factory=pd.DataFrame)
    national_totals: dict[str, dict[str, Any]] = field(default_factory=dict)

    def __repr__(self) -> str:
        return (
            f"WeeklyReport(year={self.year}, week={self.week}, "
            f"as_of={self.as_of.date() if self.as_of is not None else None})"
        )


class JapanIDWRAccessor(BaseAccessor):
    """
    Accessor for the Japan IDWR prefecture-level weekly surveillance data.

    Provides access to:

    - Week discovery (available years, weeks, latest report)
    - Full weekly reports with notifiable and sentinel disease tables
    - Disease time-series across a range of weeks
    - Per-prefecture filtered snapshots

    Reports are cached on disk (default TTL 24 h — data updates weekly).

    Example:
        >>> from epidatasets.sources.japan_idwr import JapanIDWRAccessor
        >>> idwr = JapanIDWRAccessor()
        >>>
        >>> # Latest available report
        >>> year, week = idwr.get_latest_week()
        >>> report = idwr.get_week(year, week)
        >>>
        >>> # Notifiable diseases table (measles, rubella, ...)
        >>> report.notifiable_diseases.head()
        >>>
        >>> # Time series of influenza-like sentinel reports
        >>> flu = idwr.get_disease_series(
        ...     "influenza", start_year=2026, start_week=1,
        ...     end_year=2026, end_week=32,
        ... )

    Data Sources:
        - https://id-info.jihs.go.jp/en/surveillance/idwr/
    """

    source_name: ClassVar[str] = "japan_idwr"
    source_description: ClassVar[str] = (
        "Japan Infectious Diseases Weekly Report (IDWR) — prefecture-level "
        "weekly surveillance of notifiable and sentinel-reporting diseases "
        "published by the Japan Institute for Health Security (JIHS)."
    )
    source_url: ClassVar[str] = (
        "https://id-info.jihs.go.jp/en/surveillance/idwr/"
    )

    BASE_URL: ClassVar[str] = "https://id-info.jihs.go.jp"
    RAPID_BASE: ClassVar[str] = "/en/surveillance/idwr/rapid"

    MIN_YEAR: ClassVar[int] = 2023

    TABLES: ClassVar[dict[str, str]] = {
        "notifiable": "zensu",
        "sentinel_weekly": "teiten",
        "sentinel_weekly_delayed": "teitenari",
        "sentinel_cumulative": "teitenrui",
    }

    VALUE_COLUMNS: ClassVar[dict[str, list[str]]] = {
        "notifiable": ["current_week", "cumulative"],
        "sentinel_weekly": ["current_week", "per_sentinel"],
        "sentinel_weekly_delayed": ["current_week", "per_sentinel"],
        "sentinel_cumulative": ["cumulative_cases", "cumulative_per_sentinel"],
    }

    PREFECTURES: ClassVar[list[str]] = [
        "Hokkaido", "Aomori", "Iwate", "Miyagi", "Akita", "Yamagata",
        "Fukushima", "Ibaraki", "Tochigi", "Gunma", "Saitama", "Chiba",
        "Tokyo", "Kanagawa", "Niigata", "Toyama", "Ishikawa", "Fukui",
        "Yamanashi", "Nagano", "Gifu", "Shizuoka", "Aichi", "Mie", "Shiga",
        "Kyoto", "Osaka", "Hyogo", "Nara", "Wakayama", "Tottori", "Shimane",
        "Okayama", "Hiroshima", "Yamaguchi", "Tokushima", "Kagawa", "Ehime",
        "Kochi", "Fukuoka", "Saga", "Nagasaki", "Kumamoto", "Oita",
        "Miyazaki", "Kagoshima", "Okinawa",
    ]

    DISEASE_ALIASES: ClassVar[dict[str, str]] = {
        "influenza": "Influenza(excld. avian influenza and pandemic influenza)",
        "flu": "Influenza(excld. avian influenza and pandemic influenza)",
        "rsv": "Respiratory syncytial virus infection",
        "chickenpox": "Chickenpox",
        "varicella": "Chickenpox",
        "hfmd": "Hand, foot and mouth disease",
        "hand foot mouth": "Hand, foot and mouth disease",
        "fifth disease": "Erythema infection",
        "erythema infectiosum": "Erythema infection",
        "measles": "Measles",
        "rubella": "Rubella",
        "pertussis": "Pertussis",
        "whooping cough": "Pertussis",
        "diphtheria": "Diphtheria",
        "tb": "Tuberculosis",
        "tuberculosis": "Tuberculosis",
        "syphilis": "Syphilis",
        "mumps": "Mumps",
        "herpangina": "Herpangina",
        "gastroenteritis": "Infectious gastroenteritis",
        "strep pharyngitis": "Group A streptococcal pharyngitis",
        "pharyngoconjunctival fever": "Pharyngoconjunctival fever",
        "exanthem subitum": "Exanthem subitum",
        "bacterial meningitis": "Bacterial meningitis",
        "aseptic meningitis": "Aseptic meningitis",
        "mycoplasma pneumonia": "Mycoplasma pneumonia",
        "chlamydial pneumonia": "Chlamydial pneumonia(excluding psittacosis)",
        "rotavirus": "Infectious gastroenteritis (only by Rotavirus)",
        "covid19": "COVID-19",
        "covid-19": "COVID-19",
        "aids": "Acquired immunodeficiency syndrome (AIDS)",
        "dengue": "Dengue fever",
        "tetanus": "Tetanus",
        "malaria": "Malaria",
        "cholera": "Cholera",
        "typhoid": "Typhoid fever",
        "hepatitis a": "Hepatitis A",
        "hepatitis e": "Hepatitis E",
        "mpox": "Mpox",
        "ambiasis": "Amebiasis",
        "amebiasis": "Amebiasis",
        "scrub typhus": "Scrub typhus(Tsutsugamushi disease)",
        "japanese encephalitis": "Japanese encephalitis",
    }

    def __init__(self, cache_dir: str | None = None, cache_ttl_hours: int = 24):
        """
        Initialize the Japan IDWR accessor.

        Args:
            cache_dir: Directory to cache downloaded reports. If None, uses
                the default ``~/.cache/epidatasets/japan_idwr``.
            cache_ttl_hours: Cache time-to-live in hours. The default of
                24 h suits the weekly publication cadence.
        """
        self.cache_dir = (
            Path(cache_dir)
            if cache_dir
            else Path.home() / ".cache" / "epidatasets" / "japan_idwr"
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_ttl = timedelta(hours=cache_ttl_hours)
        self._session = requests.Session()
        self._session.headers.update(
            {"User-Agent": "epidatasets-japan-idwr-accessor/1.0 (research)"}
        )

    # ------------------------------------------------------------------
    # Caching helpers
    # ------------------------------------------------------------------
    def _cache_valid(self, path: Path) -> bool:
        if not path.exists():
            return False
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        return datetime.now() - mtime < self._cache_ttl

    # ------------------------------------------------------------------
    # HTTP helper
    # ------------------------------------------------------------------
    def _fetch(
        self,
        url: str,
        binary: bool = False,
        use_cache: bool = True,
        retries: int = 3,
    ) -> str | bytes:
        """
        Fetch a URL with retries and optional on-disk caching.

        Args:
            url: Absolute URL to fetch.
            binary: If True return raw bytes, else decode as text
                (UTF-8 with cp932 fallback).
            use_cache: Whether to use the on-disk cache.
            retries: Number of retry attempts on failure.

        Returns:
            Response body as ``str`` (or ``bytes`` when ``binary``).

        Raises:
            JapanIDWRDataError: If the request fails after retries.
        """
        cache_path = self.cache_dir / re.sub(r"[^A-Za-z0-9_.-]", "_", url[-120:])
        if use_cache and self._cache_valid(cache_path):
            logger.info(f"Loading cached data: {cache_path}")
            if binary:
                return cache_path.read_bytes()
            return cache_path.read_text(encoding="utf-8", errors="replace")

        last_error: Exception | None = None
        for attempt in range(retries):
            try:
                logger.info(f"Fetching {url} (attempt {attempt + 1}/{retries})")
                response = self._session.get(url, timeout=30)
                response.raise_for_status()
                body: str | bytes = (
                    response.content
                    if binary
                    else self._decode(response.content)
                )
                if use_cache:
                    cache_path.write_bytes(
                        body if isinstance(body, bytes) else body.encode("utf-8")
                    )
                return body
            except requests.exceptions.RequestException as e:
                status_code = getattr(e.response, "status_code", None)
                non_retryable = (
                    status_code is not None and 400 <= status_code < 500
                )
                if non_retryable or attempt >= retries - 1:
                    raise JapanIDWRDataError(
                        f"Failed to fetch {url}: {e}"
                    ) from e
                last_error = e
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                time.sleep(2**attempt)
        raise JapanIDWRDataError(f"Failed to fetch {url}: {last_error}")

    @staticmethod
    def _decode(content: bytes) -> str:
        """Decode CSV bytes as UTF-8, falling back to cp932 (Japanese)."""
        for encoding in ("utf-8", "cp932"):
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        return content.decode("utf-8", errors="replace")

    # ------------------------------------------------------------------
    # Abstract method implementation
    # ------------------------------------------------------------------
    def list_countries(self) -> pd.DataFrame:
        """
        Return a one-row DataFrame describing geographic coverage.

        Returns
        -------
        pd.DataFrame
            Columns ``country_code``, ``country_name``.
        """
        return pd.DataFrame(
            [("JP", "Japan")], columns=["country_code", "country_name"]
        )

    # ------------------------------------------------------------------
    # Week discovery
    # ------------------------------------------------------------------
    def get_available_years(self, use_cache: bool = True) -> list[int]:
        """
        List years with rapid reports on the current portal.

        Returns
        -------
        list[int]
            Sorted list of years (currently 2023 onward).
        """
        cache_path = self.cache_dir / "discovery_years.json"
        if use_cache and self._cache_valid(cache_path):
            return json.loads(cache_path.read_text())

        html = self._fetch(f"{self.BASE_URL}{self.RAPID_BASE}/index.html")
        assert isinstance(html, str)
        years = sorted(
            {
                int(m)
                for m in re.findall(r"\./(\d{4})/index\.html", html)
                if int(m) >= self.MIN_YEAR
            }
        )
        if not years:
            raise JapanIDWRDataError(
                "No report years found on the IDWR rapid portal — "
                "the site structure may have changed."
            )
        cache_path.write_text(json.dumps(years))
        return years

    def get_available_weeks(self, year: int, use_cache: bool = True) -> list[int]:
        """
        List published epidemiological weeks for a year.

        Args:
            year: Epidemiological year (>= 2023).
            use_cache: Whether to use the on-disk cache.

        Returns
        -------
        list[int]
            Sorted week numbers.

        Raises:
            ValueError: If ``year`` predates portal coverage.
        """
        self._validate_year(year)
        cache_path = self.cache_dir / f"discovery_weeks_{year}.json"
        if use_cache and self._cache_valid(cache_path):
            return json.loads(cache_path.read_text())

        html = self._fetch(f"{self.BASE_URL}{self.RAPID_BASE}/{year}/index.html")
        assert isinstance(html, str)
        weeks = sorted(
            {
                int(m)
                for m in re.findall(r"\./(\d{1,2})/index\.html", html)
                if 1 <= int(m) <= 53
            }
        )
        if not weeks:
            raise JapanIDWRDataError(
                f"No weekly reports discovered for {year} — "
                "the site structure may have changed."
            )
        cache_path.write_text(json.dumps(weeks))
        return weeks

    def get_latest_week(self, use_cache: bool = True) -> tuple[int, int]:
        """
        Return the most recent published (year, week).

        Returns
        -------
        tuple[int, int]
            ``(year, week)`` of the latest available report.
        """
        years = self.get_available_years(use_cache=use_cache)
        weeks = self.get_available_weeks(years[-1], use_cache=use_cache)
        return years[-1], weeks[-1]

    # ------------------------------------------------------------------
    # CSV URL builder + parsing
    # ------------------------------------------------------------------
    def _csv_url(self, year: int, week: int, table_key: str) -> str:
        table = self.TABLES[table_key]
        return (
            f"{self.BASE_URL}{self.RAPID_BASE}/{year}/{week:02d}/"
            f"{table}{week:02d}.csv"
        )

    @staticmethod
    def _clean_value(v: Any) -> float | None:
        """Convert a CSV cell to float, mapping '-', '' and '?' to None."""
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        s = str(v).strip()
        if s in {"-", "", "?"}:
            return None
        return pd.to_numeric(s.replace(",", ""), errors="coerce")

    def _parse_week_csv(
        self, text: str, table_key: str, year: int, week: int
    ) -> tuple[pd.DataFrame, dict[str, Any], pd.Timestamp | None]:
        """
        Parse one IDWR weekly CSV into a tidy DataFrame.

        Args:
            text: Raw CSV text.
            table_key: One of ``TABLES`` keys (defines value column names).
            year: Report year (used for the ``as_of`` parse).
            week: Report week.

        Returns:
            Tuple ``(tidy_df, national_totals, as_of)`` where ``tidy_df``
            has columns ``prefecture``, ``disease`` plus two value columns
            named after ``VALUE_COLUMNS[table_key]``.
        """
        lines = text.splitlines()
        as_of = None
        for line in lines[:3]:
            m = re.search(r"Data collected as of ([A-Za-z]+ \d{1,2}, \d{4})", line)
            if m:
                as_of = pd.to_datetime(m.group(1), errors="coerce")
                break

        raw = pd.read_csv(
            io.StringIO(text), skiprows=3, header=[0, 1], dtype=str
        ).dropna(axis=1, how="all")

        value_names = self.VALUE_COLUMNS[table_key]
        prefecture_col = raw.columns[0]
        headers = [
            c[0] if not str(c[0]).startswith("Unnamed") else None
            for c in raw.columns[1:]
        ]
        diseases = pd.Series(headers).ffill()

        records: list[dict[str, Any]] = []
        totals: dict[str, Any] = {}
        for _, row in raw.iterrows():
            prefecture = str(row[prefecture_col]).strip()
            is_total = prefecture == "Total No."
            target = totals if is_total else records
            for i in range(0, len(diseases), 2):
                disease = diseases.iloc[i]
                if pd.isna(disease):
                    continue
                entry = {"disease": disease}
                for j, name in enumerate(value_names):
                    col = raw.columns[1 + i + j] if i + j < len(diseases) else None
                    entry[name] = (
                        self._clean_value(row[col]) if col is not None else None
                    )
                if is_total:
                    target[disease] = entry
                else:
                    target.append({"prefecture": prefecture, **entry})

        df = pd.DataFrame(
            records, columns=["prefecture", "disease", *value_names]
        )
        return df, totals, as_of

    def _fetch_table(
        self, year: int, week: int, table_key: str, use_cache: bool = True
    ) -> tuple[pd.DataFrame, dict[str, Any], pd.Timestamp | None]:
        """Download (or load from cache) and parse one table for one week."""
        url = self._csv_url(year, week, table_key)
        try:
            text = self._fetch(url, use_cache=use_cache)
        except JapanIDWRDataError as e:
            raise JapanIDWRDataError(
                f"No IDWR report for {year} week {week} "
                f"({self.TABLES[table_key]}): {e}"
            ) from e
        assert isinstance(text, str)
        return self._parse_week_csv(text, table_key, year, week)

    # ------------------------------------------------------------------
    # Public data access
    # ------------------------------------------------------------------
    def get_week(self, year: int, week: int, use_cache: bool = True) -> WeeklyReport:
        """
        Retrieve a full weekly IDWR report.

        Args:
            year: Epidemiological year (>= 2023).
            week: Epidemiological week (1-53).
            use_cache: Whether to use the on-disk cache.

        Returns
        -------
        WeeklyReport
            Parsed report with all four tables and national totals.

        Raises:
            ValueError: If year/week are outside valid ranges.
            JapanIDWRDataError: If the report is not published or the
                download fails.
        """
        self._validate_year(year)
        self._validate_week(week)

        report = WeeklyReport(year=year, week=week)
        report.notifiable_diseases, totals, as_of = self._fetch_table(
            year, week, "notifiable", use_cache
        )
        report.as_of = as_of
        report.national_totals["notifiable"] = totals
        for key, attr in (
            ("sentinel_weekly", "sentinel_diseases"),
            ("sentinel_weekly_delayed", "sentinel_diseases_delayed"),
            ("sentinel_cumulative", "sentinel_diseases_cumulative"),
        ):
            try:
                df, totals, _ = self._fetch_table(year, week, key, use_cache)
                setattr(report, attr, df)
                report.national_totals[key] = totals
            except JapanIDWRDataError as e:
                logger.warning(
                    f"Table {key} unavailable for {year}-W{week}: {e}"
                )
        return report

    def get_notifiable_diseases(
        self, year: int, week: int, use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Get the notifiable diseases table (Table 1) for one week.

        Returns
        -------
        pd.DataFrame
            Columns ``prefecture``, ``disease``, ``current_week``,
            ``cumulative``.
        """
        df, _, _ = self._fetch_table(year, week, "notifiable", use_cache)
        return df

    def get_sentinel_diseases(
        self,
        year: int,
        week: int,
        table: str = "weekly",
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Get a sentinel-reporting diseases table for one week.

        Args:
            year: Epidemiological year.
            week: Epidemiological week.
            table: ``"weekly"`` (Table 2), ``"weekly_delayed"`` (Table 2
                incl. delayed reports) or ``"cumulative"`` (Table 3).
            use_cache: Whether to use the on-disk cache.

        Returns
        -------
        pd.DataFrame
            Columns ``prefecture``, ``disease``, ``current_week``,
            ``per_sentinel`` (weekly tables) or ``prefecture``,
            ``disease``, ``cumulative_cases``, ``cumulative_per_sentinel``
            (cumulative table).
        """
        key = f"sentinel_{table}"
        if key not in self.TABLES:
            raise ValueError(
                f"Invalid table {table!r}. Use one of: "
                "'weekly', 'weekly_delayed', 'cumulative'."
            )
        df, _, _ = self._fetch_table(year, week, key, use_cache)
        return df

    # ------------------------------------------------------------------
    # Disease / prefecture lookups
    # ------------------------------------------------------------------
    def resolve_disease(self, disease: str, df: pd.DataFrame | None = None) -> str:
        """
        Resolve a disease name or alias to its official CSV header name.

        Args:
            disease: User-provided name (e.g. ``"flu"``, ``"HFMD"``).
            df: Optional parsed table to search case-insensitively when
                the alias map has no entry.

        Returns
        -------
        str
            The official disease name as used in the IDWR tables.

        Raises:
            ValueError: If no match is found.
        """
        norm = self._normalize_name(disease)
        if norm in self.DISEASE_ALIASES:
            return self.DISEASE_ALIASES[norm]

        if df is not None and "disease" in df.columns:
            for official in df["disease"].dropna().unique():
                if self._normalize_name(official) == norm:
                    return official

        raise ValueError(
            f"Unknown disease: {disease!r}. Call get_week(...) and inspect "
            "the 'disease' column for the official names, or use a known "
            "alias (e.g. 'influenza', 'measles', 'HFMD')."
        )

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Lowercase, strip punctuation and collapse whitespace."""
        return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", "", name.lower())).strip()

    def _resolve_prefecture(self, prefecture: str) -> str:
        """Match a prefecture name case-insensitively against the 47 names."""
        target = prefecture.strip().lower()
        for name in self.PREFECTURES:
            if name.lower() == target:
                return name
        raise ValueError(
            f"Unknown prefecture: {prefecture!r}. Japan has 47 prefectures; "
            "see JapanIDWRAccessor.PREFECTURES for the accepted names."
        )

    def get_by_prefecture(
        self,
        prefecture: str,
        year: int,
        week: int,
        use_cache: bool = True,
    ) -> WeeklyReport:
        """
        Get a weekly report filtered to a single prefecture.

        Args:
            prefecture: Prefecture name (case-insensitive), e.g. ``"Tokyo"``.
            year: Epidemiological year.
            week: Epidemiological week.
            use_cache: Whether to use the on-disk cache.

        Returns
        -------
        WeeklyReport
            All tables filtered to the requested prefecture.
        """
        official = self._resolve_prefecture(prefecture)
        report = self.get_week(year, week, use_cache=use_cache)
        report.notifiable_diseases = report.notifiable_diseases[
            report.notifiable_diseases["prefecture"] == official
        ]
        report.sentinel_diseases = report.sentinel_diseases[
            report.sentinel_diseases["prefecture"] == official
        ]
        report.sentinel_diseases_delayed = report.sentinel_diseases_delayed[
            report.sentinel_diseases_delayed["prefecture"] == official
        ]
        report.sentinel_diseases_cumulative = (
            report.sentinel_diseases_cumulative[
                report.sentinel_diseases_cumulative["prefecture"] == official
            ]
        )
        return report

    def get_disease_series(
        self,
        disease: str,
        start_year: int,
        start_week: int = 1,
        end_year: int | None = None,
        end_week: int | None = None,
        table: str = "notifiable",
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Build a weekly time series for one disease across weeks.

        Args:
            disease: Disease name or alias (see ``DISEASE_ALIASES``).
            start_year: First epidemiological year.
            start_week: First week of the start year.
            end_year: Last year (defaults to ``start_year``).
            end_week: Last week (defaults to the latest published week).
            table: ``"notifiable"``, ``"sentinel_weekly"`` or
                ``"sentinel_cumulative"``.
            use_cache: Whether to use the on-disk cache.

        Returns
        -------
        pd.DataFrame
            Columns ``year``, ``week``, ``prefecture``, ``disease`` plus
            the table's value columns. Weeks without a published report
            are skipped with a warning.
        """
        if table not in {"notifiable", "sentinel_weekly", "sentinel_cumulative"}:
            raise ValueError(
                "table must be 'notifiable', 'sentinel_weekly' or "
                "'sentinel_cumulative'."
            )
        end_year = end_year or start_year
        if end_year < start_year:
            raise ValueError("end_year must be >= start_year")

        frames: list[pd.DataFrame] = []
        for year in range(start_year, end_year + 1):
            available = set(self.get_available_weeks(year, use_cache=use_cache))
            first = start_week if year == start_year else 1
            if end_year is not None and year == end_year and end_week is not None:
                last = end_week
            else:
                last = max(available) if available else 53
            for week in range(first, last + 1):
                if available and week not in available:
                    logger.warning(
                        f"Skipping {year}-W{week}: no published report."
                    )
                    continue
                try:
                    df, _, _ = self._fetch_table(year, week, table, use_cache)
                except JapanIDWRDataError as e:
                    logger.warning(f"Skipping {year}-W{week}: {e}")
                    continue
                official = self.resolve_disease(disease, df)
                sub = df[df["disease"] == official].copy()
                if sub.empty:
                    logger.warning(
                        f"{year}-W{week}: disease {official!r} not in table."
                    )
                    continue
                sub.insert(0, "week", week)
                sub.insert(0, "year", year)
                frames.append(sub)

        if not frames:
            raise JapanIDWRDataError(
                f"No data found for disease {disease!r} in "
                f"{start_year}-W{start_week}..{end_year}-W{end_week}."
            )
        return pd.concat(frames, ignore_index=True)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def _validate_year(self, year: int) -> None:
        if year < self.MIN_YEAR:
            raise ValueError(
                f"Year {year} is before portal coverage (>= {self.MIN_YEAR}). "
                "Reports from 1996-2022 live in the legacy NIID archive "
                "(https://www.niid.go.jp/niid/en/surveillance/) and are not "
                "available through this accessor."
            )
        if year > datetime.now().year + 1:
            raise ValueError(f"Year {year} is in the future.")

    @staticmethod
    def _validate_week(week: int) -> None:
        if not 1 <= week <= 53:
            raise ValueError(f"Week must be between 1 and 53, got {week}.")
