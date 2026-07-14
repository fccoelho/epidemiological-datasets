"""
disease.sh API Accessor

This module provides access to the disease.sh open API — a free, open-source
API providing global disease statistics, including COVID-19 (cases, deaths,
testing, vaccinations) and influenza surveillance data from the US CDC.

Data Sources:
- disease.sh: https://disease.sh/
- Documentation: https://disease.sh/docs/
- GitHub: https://github.com/disease-sh/api

Diseases Covered:
- COVID-19: global/country/state totals, historical time series, vaccine coverage
- Influenza: US CDC ILINet, Public Health Lab, and Clinical Lab weekly data

Authentication: None required (public API)
Rate Limits: Generous, no key needed
License: Open data (sources: Worldometers, JHU CSSE, CDC, etc.)

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


class DiseaseShAccessor(BaseAccessor):
    """
    Accessor for the disease.sh open disease data API.

    Provides access to:
    - Global and country-level COVID-19 statistics (current totals)
    - Historical COVID-19 time series with configurable date ranges
    - COVID-19 vaccination coverage data (global and per-country)
    - US state-level COVID-19 data
    - US CDC influenza surveillance (ILINet, Public Health Lab, Clinical Lab)

    No API key is required.  Responses are cached on disk with a configurable
    time-to-live.

    Example:
        >>> from epidatasets.sources.disease_sh import DiseaseShAccessor
        >>> ds = DiseaseShAccessor()
        >>>
        >>> # Global COVID-19 totals
        >>> totals = ds.get_global_totals()
        >>>
        >>> # Historical time series for Brazil
        >>> hist = ds.get_historical(country="Brazil", lastdays=30)
        >>>
        >>> # Vaccination coverage
        >>> vax = ds.get_vaccine_coverage(country="USA", lastdays=60)
        >>>
        >>> # US CDC influenza ILI surveillance
        >>> ili = ds.get_influenza_ilinet()

    Data Sources:
        - disease.sh: https://disease.sh/
        - GitHub: https://github.com/disease-sh/api
    """

    source_name: ClassVar[str] = "disease_sh"
    source_description: ClassVar[str] = (
        "disease.sh — a free, open-source API providing global disease "
        "statistics including COVID-19 cases, deaths, testing, vaccinations, "
        "and US CDC influenza surveillance data."
    )
    source_url: ClassVar[str] = "https://disease.sh/"

    BASE_URL: ClassVar[str] = "https://disease.sh"

    # Influenza endpoints map (US CDC sourced, weekly)
    INFLUENZA_ENDPOINTS: ClassVar[dict[str, str]] = {
        "ilinet": "/v3/influenza/CDC/ILINet",
        "public_health_lab": "/v3/influenza/CDC/USPHL",
        "clinical_lab": "/v3/influenza/CDC/USCL",
    }

    DISEASES: ClassVar[dict[str, dict[str, Any]]] = {
        "covid19": {
            "name": "COVID-19",
            "description": "Global COVID-19 cases, deaths, testing, and vaccinations",
            "endpoints": ["all", "countries", "historical", "vaccine", "states"],
        },
        "influenza": {
            "name": "Influenza",
            "description": "US CDC influenza surveillance (ILI, strain typing, clinical labs)",
            "endpoints": list(INFLUENZA_ENDPOINTS.keys()),
        },
    }

    def __init__(self, cache_dir: str | None = None, cache_ttl_hours: int = 1):
        """
        Initialize the disease.sh accessor.

        Args:
            cache_dir: Directory to cache downloaded data. If None, uses the
                default ``~/.cache/epi_data/disease_sh``.
            cache_ttl_hours: Cache time-to-live in hours. disease.sh data is
                updated frequently, so a short TTL is recommended.
        """
        self.cache_dir = (
            Path(cache_dir)
            if cache_dir
            else Path.home() / ".cache" / "epi_data" / "disease_sh"
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_ttl = timedelta(hours=cache_ttl_hours)
        self._session = requests.Session()
        self._session.headers.update(
            {"User-Agent": "epidatasets-disease-sh-accessor/1.0 (research)"}
        )

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
    def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        use_cache: bool = True,
        retries: int = 3,
    ) -> Any:
        """
        Fetch JSON data from the disease.sh API with caching and retries.

        Args:
            path: API path beginning with ``/`` (e.g. ``/v3/covid-19/all``).
            params: Optional query parameters.
            use_cache: Whether to use the on-disk cache.
            retries: Number of retry attempts on failure.

        Returns:
            Parsed JSON response (dict or list).
        """
        url = f"{self.BASE_URL}{path}"
        cache_key = path.strip("/").replace("/", "_")
        if params:
            cache_key += "_" + "_".join(f"{k}-{v}" for k, v in sorted(params.items()))
        cache_path = self._get_cache_path(cache_key)

        if use_cache and self._is_cache_valid(cache_path):
            logger.info(f"Loading cached data: {cache_path}")
            return self._read_cache(cache_path)

        for attempt in range(retries):
            try:
                logger.info(
                    f"Fetching {url} (attempt {attempt + 1}/{retries})"
                )
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

    # ------------------------------------------------------------------
    # Abstract method implementation
    # ------------------------------------------------------------------
    def list_countries(self) -> pd.DataFrame:
        """
        Return a DataFrame of countries covered by disease.sh COVID-19 data.

        Returns
        -------
        pd.DataFrame
            Columns ``country_code`` (ISO2), ``country_name``, ``iso3``,
            ``lat``, ``long``.
        """
        data = self._get("/v3/covid-19/countries", params={"allowNull": "false"})
        rows = []
        for item in data:
            info = item.get("countryInfo", {}) or {}
            rows.append(
                {
                    "country_code": info.get("iso2"),
                    "country_name": item.get("country"),
                    "iso3": info.get("iso3"),
                    "lat": info.get("lat"),
                    "long": info.get("long"),
                }
            )
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------
    def get_available_diseases(self) -> pd.DataFrame:
        """
        Get list of diseases available in disease.sh.

        Returns
        -------
        pd.DataFrame
            DataFrame with disease information.
        """
        rows = []
        for key, info in self.DISEASES.items():
            rows.append(
                {
                    "disease_key": key,
                    "disease_name": info["name"],
                    "description": info["description"],
                    "endpoints": ", ".join(info["endpoints"]),
                }
            )
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # COVID-19: current totals
    # ------------------------------------------------------------------
    def get_global_totals(self, use_cache: bool = True) -> pd.DataFrame:
        """
        Get global COVID-19 totals (cases, deaths, recovered, active, tests).

        Args:
            use_cache: Whether to use cached data.

        Returns
        -------
        pd.DataFrame
            One-row DataFrame with global totals.
        """
        data = self._get("/v3/covid-19/all", use_cache=use_cache)
        df = pd.DataFrame([data])
        if "updated" in df.columns:
            df["updated"] = pd.to_datetime(df["updated"], unit="ms", errors="coerce")
        return df

    def get_country_data(
        self,
        country: str | list[str] | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Get current COVID-19 data per country.

        Args:
            country: A single country name, ISO2/ISO3 code, or a list of them.
                If None, returns data for all countries.
            use_cache: Whether to use cached data.

        Returns
        -------
        pd.DataFrame
            DataFrame with per-country COVID-19 statistics.
        """
        if country is None:
            data = self._get(
                "/v3/covid-19/countries", params={"allowNull": "false"}, use_cache=use_cache
            )
        elif isinstance(country, list):
            codes = ",".join(str(c) for c in country)
            data = self._get(f"/v3/covid-19/countries/{codes}", use_cache=use_cache)
        else:
            data = self._get(f"/v3/covid-19/countries/{country}", use_cache=use_cache)
            data = [data] if isinstance(data, dict) else data

        rows = []
        for item in data:
            info = item.get("countryInfo", {}) or {}
            row = {
                "country": item.get("country"),
                "country_code": info.get("iso2"),
                "iso3": info.get("iso3"),
                "lat": info.get("lat"),
                "long": info.get("long"),
                "continent": item.get("continent"),
                "cases": item.get("cases"),
                "todayCases": item.get("todayCases"),
                "deaths": item.get("deaths"),
                "todayDeaths": item.get("todayDeaths"),
                "recovered": item.get("recovered"),
                "active": item.get("active"),
                "critical": item.get("critical"),
                "casesPerOneMillion": item.get("casesPerOneMillion"),
                "deathsPerOneMillion": item.get("deathsPerOneMillion"),
                "tests": item.get("tests"),
                "testsPerOneMillion": item.get("testsPerOneMillion"),
                "population": item.get("population"),
                "updated": item.get("updated"),
            }
            rows.append(row)

        df = pd.DataFrame(rows)
        if "updated" in df.columns:
            df["updated"] = pd.to_datetime(df["updated"], unit="ms", errors="coerce")
        return df

    def get_states(self, use_cache: bool = True) -> pd.DataFrame:
        """
        Get US state-level COVID-19 data.

        Args:
            use_cache: Whether to use cached data.

        Returns
        -------
        pd.DataFrame
            DataFrame with per-state COVID-19 statistics.
        """
        data = self._get("/v3/covid-19/states", use_cache=use_cache)
        df = pd.DataFrame(data)
        if "updated" in df.columns:
            df["updated"] = pd.to_datetime(df["updated"], unit="ms", errors="coerce")
        return df

    # ------------------------------------------------------------------
    # COVID-19: historical time series
    # ------------------------------------------------------------------
    def get_historical(
        self,
        country: str | list[str] | None = None,
        lastdays: int = 30,
        start_date: str | None = None,
        end_date: str | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Get historical COVID-19 time series.

        Args:
            country: A country name/ISO code, list of countries, or None for
                global totals.
            lastdays: Number of days of history to fetch (disease.sh default).
            start_date: Optional start date ``YYYY-MM-DD`` to filter the
                returned series (inclusive).
            end_date: Optional end date ``YYYY-MM-DD`` to filter (inclusive).
            use_cache: Whether to use cached data.

        Returns
        -------
        pd.DataFrame
            Long-form DataFrame with columns ``country``, ``date``,
            ``cases``, ``deaths``, ``recovered``.  For the global query the
            ``country`` column is set to ``"World"``.

        Example:
            >>> ds = DiseaseShAccessor()
            >>> hist = ds.get_historical(country="USA", lastdays=30)
            >>> hist = ds.get_historical(
            ...     country=["USA", "BRA"], start_date="2023-01-01",
            ...     end_date="2023-01-31",
            ... )
        """
        params: dict[str, Any] = {"lastdays": str(lastdays)}

        if country is None:
            data = self._get("/v3/covid-19/historical/all", params=params, use_cache=use_cache)
            return self._flatten_global_timeline(
                data, start_date=start_date, end_date=end_date
            )

        if isinstance(country, list):
            codes = ",".join(str(c) for c in country)
            data = self._get(
                f"/v3/covid-19/historical/{codes}", params=params, use_cache=use_cache
            )
        else:
            data = self._get(
                f"/v3/covid-19/historical/{country}", params=params, use_cache=use_cache
            )
            data = [data] if isinstance(data, dict) else data

        return self._flatten_country_timeline(
            data, start_date=start_date, end_date=end_date
        )

    def _parse_disease_sh_date(self, date_str: str) -> pd.Timestamp | None:
        """Parse a disease.sh date string (``M/D/YY``) into a Timestamp."""
        if not date_str:
            return None
        try:
            return pd.to_datetime(date_str, format="%m/%d/%y", errors="coerce")
        except (ValueError, TypeError):
            return pd.to_datetime(date_str, errors="coerce")

    def _flatten_global_timeline(
        self,
        data: dict[str, Any],
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Flatten the global historical timeline into a long-form DataFrame."""
        rows = []
        for metric in ("cases", "deaths", "recovered"):
            series = data.get(metric, {}) or {}
            for date_str, value in series.items():
                rows.append(
                    {
                        "country": "World",
                        "date": self._parse_disease_sh_date(date_str),
                        "metric": metric,
                        "value": value,
                    }
                )
        if not rows:
            return pd.DataFrame(columns=["country", "date", "metric", "value"])
        df = pd.DataFrame(rows)
        df = df.pivot_table(
            index=["country", "date"], columns="metric", values="value", aggfunc="first"
        ).reset_index()
        df.columns.name = None
        df = self._filter_dates(df, start_date, end_date)
        return df.sort_values("date").reset_index(drop=True)

    def _flatten_country_timeline(
        self,
        data: list[dict[str, Any]],
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Flatten per-country historical timelines into a long-form DataFrame."""
        rows = []
        for entry in data:
            country_name = entry.get("country", "Unknown")
            # ``province`` may be a list (e.g. ["mainland"]) or a string
            province = entry.get("province")
            if isinstance(province, list):
                province = ", ".join(str(p) for p in province) if province else None
            timeline = entry.get("timeline", {}) or {}
            for metric in ("cases", "deaths", "recovered"):
                series = timeline.get(metric, {}) or {}
                for date_str, value in series.items():
                    rows.append(
                        {
                            "country": country_name,
                            "province": province,
                            "date": self._parse_disease_sh_date(date_str),
                            "metric": metric,
                            "value": value,
                        }
                    )
        if not rows:
            return pd.DataFrame(
                columns=["country", "province", "date", "cases", "deaths", "recovered"]
            )
        df = pd.DataFrame(rows)
        df = df.pivot_table(
            index=["country", "province", "date"],
            columns="metric",
            values="value",
            aggfunc="first",
        ).reset_index()
        df.columns.name = None
        df = self._filter_dates(df, start_date, end_date)
        return df.sort_values(["country", "date"]).reset_index(drop=True)

    def _filter_dates(
        self,
        df: pd.DataFrame,
        start_date: str | None,
        end_date: str | None,
    ) -> pd.DataFrame:
        """Apply optional start/end date filtering to a DataFrame with a ``date`` column."""
        if df.empty or "date" not in df.columns:
            return df
        if start_date:
            df = df[df["date"] >= pd.to_datetime(start_date)]
        if end_date:
            df = df[df["date"] <= pd.to_datetime(end_date)]
        return df

    # ------------------------------------------------------------------
    # COVID-19: vaccine coverage
    # ------------------------------------------------------------------
    def get_vaccine_coverage(
        self,
        country: str | None = None,
        lastdays: int = 30,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Get COVID-19 vaccination coverage data.

        Args:
            country: A country name/ISO code. If None, returns global coverage.
            lastdays: Number of days of history to fetch.
            use_cache: Whether to use cached data.

        Returns
        -------
        pd.DataFrame
            For global coverage: columns ``date``, ``total``, ``daily``,
            ``totalPerHundred``, ``dailyPerMillion``.
            For per-country coverage: columns ``country``, ``date``, ``total``,
            ``daily``, ``totalPerHundred``, ``dailyPerMillion``.
        """
        params: dict[str, Any] = {"lastdays": str(lastdays), "fullData": "true"}

        if country is None:
            data = self._get(
                "/v3/covid-19/vaccine/coverage", params=params, use_cache=use_cache
            )
            return self._flatten_global_vaccine(data)

        data = self._get(
            "/v3/covid-19/vaccine/coverage/countries",
            params=params,
            use_cache=use_cache,
        )
        return self._flatten_country_vaccine(data, target_country=country)

    def _flatten_global_vaccine(self, data: list[dict[str, Any]]) -> pd.DataFrame:
        """Flatten the global vaccine coverage time series."""
        if not isinstance(data, list):
            return pd.DataFrame()
        df = pd.DataFrame(data)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], format="%m/%d/%y", errors="coerce")
        return df.sort_values("date").reset_index(drop=True)

    def _flatten_country_vaccine(
        self, data: list[dict[str, Any]], target_country: str | None = None
    ) -> pd.DataFrame:
        """Flatten per-country vaccine coverage time series."""
        rows = []
        for entry in data:
            country_name = entry.get("country")
            if target_country and country_name and target_country.lower() not in (
                country_name.lower(),
            ):
                continue
            timeline = entry.get("timeline", []) or []
            for point in timeline:
                rows.append(
                    {
                        "country": country_name,
                        "date": pd.to_datetime(
                            point.get("date"), format="%m/%d/%y", errors="coerce"
                        ),
                        "total": point.get("total"),
                        "daily": point.get("daily"),
                        "totalPerHundred": point.get("totalPerHundred"),
                        "dailyPerMillion": point.get("dailyPerMillion"),
                    }
                )
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values(["country", "date"]).reset_index(drop=True)
        return df

    # ------------------------------------------------------------------
    # Influenza (US CDC, weekly)
    # ------------------------------------------------------------------
    def _get_influenza(self, endpoint_key: str) -> pd.DataFrame:
        """Fetch and flatten an influenza CDC endpoint."""
        path = self.INFLUENZA_ENDPOINTS[endpoint_key]
        data = self._get(path)
        if not isinstance(data, dict):
            return pd.DataFrame()
        payload = data.get("data", []) or []
        df = pd.DataFrame(payload)
        # Split "week": "2021 - 40/52" -> year, week
        if "week" in df.columns:
            split = df["week"].astype(str).str.split(r"\s*-\s*", n=1, expand=True)
            if split.shape[1] == 2:
                df["year"] = pd.to_numeric(split[0], errors="coerce")
                week_part = split[1].str.split("/", n=1, expand=True)
                df["week_num"] = pd.to_numeric(week_part[0], errors="coerce")
        df["source"] = data.get("source")
        df["updated"] = pd.to_datetime(
            data.get("updated"), unit="ms", errors="coerce"
        )
        return df

    def get_influenza_ilinet(self, use_cache: bool = True) -> pd.DataFrame:
        """
        Get US CDC ILINet influenza-like illness surveillance data (weekly).

        Includes ILI counts by age group, total patients, and weighted/unweighted
        percent ILI.

        Args:
            use_cache: Whether to use cached data.

        Returns
        -------
        pd.DataFrame
            Weekly ILI surveillance with ``year`` and ``week_num`` columns.
        """
        return self._get_influenza("ilinet")

    def get_influenza_public_health_lab(self, use_cache: bool = True) -> pd.DataFrame:
        """
        Get US CDC Public Health Lab influenza strain typing data (weekly).

        Includes counts of influenza A/B subtypes and total tests.

        Args:
            use_cache: Whether to use cached data.

        Returns
        -------
        pd.DataFrame
            Weekly strain typing data with ``year`` and ``week_num`` columns.
        """
        return self._get_influenza("public_health_lab")

    def get_influenza_clinical_lab(self, use_cache: bool = True) -> pd.DataFrame:
        """
        Get US CDC Clinical Lab influenza data (weekly).

        Includes total A/B counts, percent positive, and total tests.

        Args:
            use_cache: Whether to use cached data.

        Returns
        -------
        pd.DataFrame
            Weekly clinical lab data with ``year`` and ``week_num`` columns.
        """
        return self._get_influenza("clinical_lab")

    def get_influenza_summary(self) -> pd.DataFrame:
        """
        Get a summary of available influenza endpoints.

        Returns
        -------
        pd.DataFrame
            DataFrame describing each influenza endpoint.
        """
        rows = []
        for key, path in self.INFLUENZA_ENDPOINTS.items():
            rows.append(
                {
                    "endpoint_key": key,
                    "url": f"{self.BASE_URL}{path}",
                    "description": {
                        "ilinet": "US CDC ILINet ILI surveillance (by age group)",
                        "public_health_lab": "US CDC Public Health Lab strain typing",
                        "clinical_lab": "US CDC Clinical Lab totals and % positive",
                    }.get(key, ""),
                    "method": {
                        "ilinet": "get_influenza_ilinet",
                        "public_health_lab": "get_influenza_public_health_lab",
                        "clinical_lab": "get_influenza_clinical_lab",
                    }.get(key, ""),
                }
            )
        return pd.DataFrame(rows)


# ----------------------------------------------------------------------
# Convenience functions
# ----------------------------------------------------------------------
def get_global_covid_totals() -> pd.DataFrame:
    """Convenience function to fetch global COVID-19 totals from disease.sh."""
    return DiseaseShAccessor().get_global_totals()


def get_country_covid_data(country: str | list[str] | None = None) -> pd.DataFrame:
    """Convenience function to fetch per-country COVID-19 data from disease.sh."""
    return DiseaseShAccessor().get_country_data(country=country)


def get_covid_historical(
    country: str | list[str] | None = None,
    lastdays: int = 30,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    """Convenience function to fetch historical COVID-19 time series from disease.sh."""
    return DiseaseShAccessor().get_historical(
        country=country, lastdays=lastdays, start_date=start_date, end_date=end_date
    )


def get_covid_vaccine_coverage(
    country: str | None = None, lastdays: int = 30
) -> pd.DataFrame:
    """Convenience function to fetch COVID-19 vaccine coverage from disease.sh."""
    return DiseaseShAccessor().get_vaccine_coverage(country=country, lastdays=lastdays)
