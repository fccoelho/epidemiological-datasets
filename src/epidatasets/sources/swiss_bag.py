"""
Swiss Federal Office of Public Health (BAG / OFSP) Infectious Diseases Dashboard

Accessor for the Swiss "Infectious Diseases Dashboard" (IDD), which is
backed by a public REST API maintained by the Federal Office of Public
Health (Bundesamt für Gesundheit, BAG).  It is the most complete
machine-readable open source for Swiss national and cantonal
infectious-disease surveillance.

Coverage
--------
54 topics / 1,610 series sets spanning:

- mandatory notifiable diseases (measles, tuberculosis, hepatitis A/B/C/E,
  salmonellosis, campylobacteriosis, EHEC, shigellosis, listeriosis,
  legionellosis, pertussis, diphtheria, tetanus, brucellosis, tularaemia,
  tick-borne encephalitis, Lyme borreliosis, Q fever, hantavirus, malaria,
  dengue, chikungunya, zika, yellow fever, West Nile, mpox, HIV, syphilis,
  gonorrhoea, chlamydiosis, ...)
- sentinel systems (influenza-like illness, acute respiratory infection,
  respiratory pathogens, influenza, COVID-19)
- environmental surveillance (wastewater viral load and sequencing)
- antimicrobial resistance, antibiotic usage and prescribing

Geography: Switzerland (national, ``CH``) and its 26 cantons, plus a
handful of series covering Liechtenstein (``FL``).  Stratification by age
group, sex, pathogen/subtype, test result and wastewater treatment plant.
Temporal granularities: ``year``, ``month``, ``week``, ``iso_week``,
``iso_week_sentinella`` and ``date``.

Data Sources
------------
- Dashboard: https://idd.bag.admin.ch
- API root: https://api.idd.bag.admin.ch/api/v1

Authentication
--------------
None.  The API is public and unauthenticated.

Update Frequency
----------------
A new weekly snapshot every Wednesday (159 archived versions are listed by
the API, the oldest being ``20231107``).  Note that individual series sets
may lag one version behind the newest snapshot; the version actually
returned by the API is recorded in ``DataFrame.attrs``.

License
-------
Open government data published by the Federal Office of Public Health.
The API self-describes as a beta version; reference the dashboard and the
BAG terms of use when redistributing.

Author: Flávio Codeço Coelho
License: MIT
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, ClassVar

import pandas as pd
import requests

from epidatasets._base import BaseAccessor

logger = logging.getLogger(__name__)

API_ROOT = "https://api.idd.bag.admin.ch/api/v1"
DEFAULT_TIMEOUT = 60
EXPORT_FORMATS = ("csv", "json")

#: Temporalities exposed by the API and how their ``x`` values are encoded.
TEMPORALITIES = {
    "year": "YYYY",
    "month": "YYYYMM",
    "week": "YYYYWW",
    "iso_week": "YYYYWW",
    "iso_week_sentinella": "YYYYWW",
    "date": "YYYYMMDD",
}

#: Columns of the bulk exports that must stay textual.
_TEXT_COLUMNS = frozenset(
    {
        "valueCategory",
        "temporal",
        "temporal_type",
        "georegion",
        "georegion_type",
        "agegroup",
        "agegroup_type",
        "sex",
        "type",
        "subtype",
        "pathogen",
        "testResult",
        "testResult_type",
        "defaultView",
    }
)


class SwissBAGAPIError(RuntimeError):
    """Raised when the BAG IDD API returns an unexpected response."""


def parse_temporal(value: Any, temporality: str) -> str | None:
    """Convert an API ``x`` value into an ISO-like temporal label.

    Parameters
    ----------
    value:
        Raw ``x`` value returned by the API (usually an integer).
    temporality:
        One of :data:`TEMPORALITIES`.

    Returns
    -------
    str or None
        ``2009``, ``2020-01``, ``2026-W41`` or ``2026-10-15`` depending on
        the temporality, or ``None`` when the value is missing.
    """
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    if temporality == "year":
        return text[:4]
    if temporality == "month" and len(text) >= 6:
        return f"{text[:4]}-{text[4:6]}"
    if temporality in {"week", "iso_week", "iso_week_sentinella"} and len(text) >= 6:
        return f"{text[:4]}-W{int(text[4:6]):02d}"
    if temporality == "date" and len(text) >= 8:
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text


def _slugify(text: str) -> str:
    """Turn a file-group name into a safe cache filename fragment."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_")


class SwissBAGAccessor(BaseAccessor):
    """Accessor for the Swiss BAG Infectious Diseases Dashboard (IDD) API.

    Examples
    --------
    >>> from epidatasets import get_source
    >>> bag = get_source("swiss_bag")
    >>>
    >>> # What is available?
    >>> bag.list_topics().head()
    >>> bag.list_sets(topic="dengueFever")
    >>>
    >>> # Monthly dengue notifications in Switzerland
    >>> df = bag.get_series("dengueFever", "cases", "value", "month")
    >>>
    >>> # Weekly COVID-19 incidence for every canton
    >>> cantons = bag.get_series(
    ...     "covid19",
    ...     "cases",
    ...     "incValue",
    ...     "iso_week",
    ...     all_series=True,
    ... )
    >>>
    >>> # Bulk export of the sentinel influenza data
    >>> flu = bag.download_export("INFLUENZA_sentinella")
    """

    source_name: ClassVar[str] = "swiss_bag"
    source_description: ClassVar[str] = (
        "Swiss Federal Office of Public Health (BAG) Infectious Diseases "
        "Dashboard: national and cantonal surveillance of notifiable "
        "diseases, sentinel ILI/ARI and respiratory pathogens, wastewater "
        "viral load and antimicrobial resistance."
    )
    source_url: ClassVar[str] = "https://idd.bag.admin.ch"

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path.home() / ".cache" / "epidatasets" / "swiss_bag"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": (
                    "epidatasets/SwissBAGAccessor "
                    "(+https://github.com/fccoelho/epidemiological-datasets)"
                ),
                "Accept": "application/json",
            }
        )
        self._sets_cache: list[str] | None = None

    # ------------------------------------------------------------------
    # Catalogue helpers
    # ------------------------------------------------------------------
    def list_countries(self) -> pd.DataFrame:
        """Return the countries covered by the dashboard (CH and LI)."""
        return pd.DataFrame(
            [
                {"country_code": "CH", "country_name": "Switzerland"},
                {"country_code": "LI", "country_name": "Liechtenstein"},
            ]
        )

    def list_versions(self, limit: int | None = None) -> pd.DataFrame:
        """List the weekly data snapshots published by the API.

        Parameters
        ----------
        limit:
            Return only the ``limit`` most recent versions.

        Returns
        -------
        pandas.DataFrame
            Columns ``version`` (``YYYYMMDD`` string) and ``date``.
        """
        payload = self._get("version")
        names = [item["name"] for item in payload if item.get("name")]
        if limit is not None:
            names = names[:limit]
        return pd.DataFrame(
            {
                "version": names,
                "date": pd.to_datetime(names, format="%Y%m%d", errors="coerce"),
            }
        )

    def current_version(self) -> str:
        """Return the version of the newest available snapshot."""
        payload = self._get("data/version")
        if isinstance(payload, dict):
            for key in ("version", "name", "data"):
                value = payload.get(key)
                if isinstance(value, str):
                    return value
        return str(payload)

    def list_sets(
        self,
        topic: str | None = None,
        chapter: str | None = None,
        aggregation: str | None = None,
        temporality: str | None = None,
    ) -> pd.DataFrame:
        """List the series sets (``topic/chapter/aggregation/temporality``).

        Each row of the returned DataFrame is one queryable series set.
        """
        if self._sets_cache is None:
            payload = self._get("data/sets")
            if not isinstance(payload, list):
                raise SwissBAGAPIError("Unexpected response for /data/sets")
            self._sets_cache = [str(item) for item in payload]

        rows = []
        for set_id in self._sets_cache:
            parts = set_id.split("/")
            if len(parts) != 4:
                continue
            rows.append(
                {
                    "topic": parts[0],
                    "chapter": parts[1],
                    "aggregation": parts[2],
                    "temporality": parts[3],
                    "set_id": set_id,
                }
            )
        df = pd.DataFrame(rows)
        if df.empty:
            return df
        filters = {
            "topic": topic,
            "chapter": chapter,
            "aggregation": aggregation,
            "temporality": temporality,
        }
        for column, value in filters.items():
            if value is not None:
                df = df[df[column] == value]
        return df.reset_index(drop=True)

    def list_topics(self) -> pd.DataFrame:
        """Summarise the available topics and their number of sets."""
        sets = self.list_sets()
        if sets.empty:
            return sets
        grouped = (
            sets.groupby("topic")
            .agg(
                n_sets=("set_id", "size"),
                chapters=("chapter", lambda s: ", ".join(sorted(set(s)))),
                temporalities=(
                    "temporality",
                    lambda s: ", ".join(sorted(set(s))),
                ),
            )
            .reset_index()
            .sort_values("topic")
            .reset_index(drop=True)
        )
        return grouped

    def list_export_files(self, version: str | None = None) -> list[str]:
        """List the bulk-export file groups for a version.

        Only 14 file groups are exported in bulk; every other topic has to
        be queried through :meth:`get_series`.
        """
        version = version or self.current_version()
        payload = self._get(f"export/{version}/files")
        if not isinstance(payload, list):
            raise SwissBAGAPIError(
                f"Unexpected response for /export/{version}/files"
            )
        return [str(item) for item in payload]

    def get_set_details(
        self,
        topic: str,
        chapter: str,
        aggregation: str,
        temporality: str,
    ) -> dict[str, Any]:
        """Return the metadata (properties, series configurations) of a set."""
        set_id = self._set_id(topic, chapter, aggregation, temporality)
        payload = self._get(f"data/{set_id}/details")
        if not isinstance(payload, dict):
            raise SwissBAGAPIError(f"Unexpected response for {set_id}/details")
        return payload

    # ------------------------------------------------------------------
    # Series queries
    # ------------------------------------------------------------------
    def get_series(
        self,
        topic: str,
        chapter: str,
        aggregation: str,
        temporality: str,
        filters: Mapping[str, Any] | None = None,
        all_series: bool = False,
        max_series: int = 200,
        group_by: str | None = None,
    ) -> pd.DataFrame:
        """Query one or more time series from a series set.

        Parameters
        ----------
        topic, chapter, aggregation, temporality:
            Identify the series set; see :meth:`list_sets`.
        filters:
            Property-to-value mapping used as the request body, e.g.
            ``{"georegion": "canton", "canton": "ZH"}``.  When omitted, the
            series configurations advertised by the API are used (the first
            one by default, all of them with ``all_series=True``).
        all_series:
            Query every configuration advertised for the set and stack the
            results, adding one column per filter property.
        max_series:
            Safety limit for ``all_series``.
        group_by:
            Optional comma-separated property list passed to the API as
            ``?groupBy=``; the grouped response is flattened into columns.

        Returns
        -------
        pandas.DataFrame
            Columns ``temporal`` and ``value`` followed by the filter
            properties and the per-point properties (``trend``,
            ``dataComplete``, ...).  ``DataFrame.attrs`` carries ``set_id``,
            ``version``, ``source`` and ``source_date``.
        """
        set_id = self._set_id(topic, chapter, aggregation, temporality)

        if filters is not None:
            configurations: list[dict[str, Any]] = [dict(filters)]
        else:
            details = self.get_set_details(
                topic, chapter, aggregation, temporality
            )
            configurations = [
                dict(cfg)
                for cfg in details.get("availableSeriesConfigurations") or []
            ]
            if not configurations:
                raise SwissBAGAPIError(
                    f"No series configuration available for {set_id}"
                )
            if not all_series:
                configurations = configurations[:1]
            elif len(configurations) > max_series:
                raise ValueError(
                    f"{set_id} exposes {len(configurations)} series; "
                    f"pass filters or raise max_series (currently {max_series})"
                )

        frames = []
        for configuration in configurations:
            payload = self._query(set_id, configuration, group_by=group_by)
            frame = self._values_to_frame(
                payload.get("values"),
                temporality=temporality,
                filters=configuration,
                group_by=group_by,
            )
            frame.attrs["version"] = payload.get("version")
            frame.attrs["source"] = payload.get("source")
            frame.attrs["source_date"] = payload.get("sourceDate")
            frames.append(frame)

        if len(frames) == 1:
            result = frames[0]
        else:
            non_empty = [frame for frame in frames if not frame.empty]
            if not non_empty:
                result = frames[0]
                result.attrs["set_id"] = set_id
                return result
            result = pd.concat(non_empty, ignore_index=True)
        result.attrs.setdefault("version", frames[0].attrs.get("version"))
        result.attrs["set_id"] = set_id
        return result

    def get_disease_data(
        self,
        topic: str,
        aggregation: str = "value",
        temporality: str = "month",
        chapter: str | None = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """Query a disease topic resolving the chapter automatically.

        ``chapter`` is inferred from :meth:`list_sets`, preferring
        ``cases``, then ``consultations``, ``detections`` and finally the
        first available chapter.
        """
        available = self.list_sets(
            topic=topic, aggregation=aggregation, temporality=temporality
        )
        if available.empty:
            raise SwissBAGAPIError(
                f"No set found for topic={topic!r}, aggregation="
                f"{aggregation!r}, temporality={temporality!r}"
            )
        if chapter is None:
            chapters = list(dict.fromkeys(available["chapter"]))
            for preferred in ("cases", "consultations", "detections", "samples"):
                if preferred in chapters:
                    chapter = preferred
                    break
            else:
                chapter = chapters[0]
        return self.get_series(
            topic, chapter, aggregation, temporality, **kwargs
        )

    # ------------------------------------------------------------------
    # Bulk exports
    # ------------------------------------------------------------------
    def export_path(
        self, file: str, format: str = "csv", version: str | None = None
    ) -> Path:
        """Return the local cache path of a bulk export."""
        if format not in EXPORT_FORMATS:
            raise ValueError(
                f"format must be one of {EXPORT_FORMATS}, got {format!r}"
            )
        version = version or self.current_version()
        return self.cache_dir / f"{version}_{_slugify(file)}.{format}"

    def download_export(
        self,
        file: str,
        format: str = "csv",
        version: str | None = None,
        use_cache: bool = True,
        **read_kwargs: Any,
    ) -> pd.DataFrame:
        """Download (or reuse the cached copy of) a bulk export.

        Parameters
        ----------
        file:
            Export file group, see :meth:`list_export_files`.
        format:
            ``"csv"`` (default) or ``"json"``.
        version:
            Snapshot version; defaults to the current one.
        use_cache:
            Reuse a previously downloaded copy when present.
        **read_kwargs:
            Forwarded to :func:`pandas.read_csv`.
        """
        if format not in EXPORT_FORMATS:
            raise ValueError(
                f"format must be one of {EXPORT_FORMATS}, got {format!r}"
            )
        version = version or self.current_version()
        path = self.export_path(file, format=format, version=version)
        if not (use_cache and path.exists() and path.stat().st_size > 0):
            url = f"{API_ROOT}/export/{version}/{file}/{format}"
            logger.info("Downloading %s", url)
            response = self._session.get(url, timeout=self.timeout)
            if response.status_code != 200:
                raise SwissBAGAPIError(
                    f"Export {file!r} ({format}) failed with HTTP "
                    f"{response.status_code}"
                )
            path.write_bytes(response.content)

        if format == "csv":
            frame = pd.read_csv(path, low_memory=False, **read_kwargs)
        else:
            frame = pd.read_json(path)
        frame = self._clean_export_frame(frame)
        frame.attrs["version"] = version
        frame.attrs["file"] = file
        return frame

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _set_id(
        self, topic: str, chapter: str, aggregation: str, temporality: str
    ) -> str:
        return f"{topic}/{chapter}/{aggregation}/{temporality}"

    def _get(self, path: str) -> Any:
        url = f"{API_ROOT}/{path}"
        response = self._session.get(url, timeout=self.timeout)
        if response.status_code >= 400:
            raise SwissBAGAPIError(
                f"GET {url} failed with HTTP {response.status_code}"
            )
        return response.json()

    def _query(
        self,
        set_id: str,
        configuration: Mapping[str, Any],
        group_by: str | None = None,
    ) -> dict[str, Any]:
        url = f"{API_ROOT}/data/{set_id}"
        params = {"groupBy": group_by} if group_by else None
        response = self._session.post(
            url, json=dict(configuration), params=params, timeout=self.timeout
        )
        if response.status_code == 404:
            raise SwissBAGAPIError(
                f"Series {set_id} not found for configuration "
                f"{dict(configuration)}; check get_set_details()"
            )
        if response.status_code >= 400:
            raise SwissBAGAPIError(
                f"POST {url} failed with HTTP {response.status_code}"
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise SwissBAGAPIError(f"Unexpected response for {set_id}")
        return payload

    def _values_to_frame(
        self,
        values: Any,
        temporality: str,
        filters: Mapping[str, Any] | None = None,
        group_by: str | None = None,
    ) -> pd.DataFrame:
        group_keys = (
            [key.strip() for key in group_by.split(",") if key.strip()]
            if group_by
            else []
        )
        rows: list[dict[str, Any]] = []

        if isinstance(values, dict):
            for key, series in values.items():
                key_parts = [part.strip() for part in str(key).split(",")]
                for item in series or []:
                    row: dict[str, Any] = {}
                    for index, name in enumerate(group_keys):
                        if index < len(key_parts):
                            row[name] = key_parts[index]
                    row.update(self._point_to_row(item, temporality, filters))
                    rows.append(row)
        else:
            for item in values or []:
                rows.append(self._point_to_row(item, temporality, filters))

        if not rows:
            return pd.DataFrame(columns=["temporal", "value"])

        frame = pd.DataFrame(rows)
        leading = [column for column in ("temporal", "value") if column in frame]
        ordered = leading + [c for c in frame.columns if c not in leading]
        return frame[ordered]

    @staticmethod
    def _point_to_row(
        item: Mapping[str, Any],
        temporality: str,
        filters: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        row: dict[str, Any] = {}
        properties = item.get("properties") or {}
        if isinstance(properties, dict):
            row.update(properties)
        if filters:
            row.update(dict(filters))
        row["temporal"] = parse_temporal(item.get("x"), temporality)
        row["value"] = item.get("y")
        return row

    @staticmethod
    def _clean_export_frame(frame: pd.DataFrame) -> pd.DataFrame:
        """Replace the ``"NA"`` marker and coerce numeric columns."""
        frame = frame.replace({"NA": pd.NA, "": pd.NA})
        for column in frame.columns:
            if column in _TEXT_COLUMNS:
                continue
            if frame[column].dtype != object:
                continue
            converted = pd.to_numeric(frame[column], errors="coerce")
            if converted.notna().sum() >= frame[column].notna().sum():
                frame[column] = converted
        return frame

    def __repr__(self) -> str:
        return f"SwissBAGAccessor(cache_dir={str(self.cache_dir)!r})"


__all__ = [
    "SwissBAGAccessor",
    "SwissBAGAPIError",
    "parse_temporal",
    "API_ROOT",
    "TEMPORALITIES",
]
