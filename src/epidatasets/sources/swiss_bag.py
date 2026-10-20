"""
Swiss BAG Infectious Diseases Dashboard (IDD) Accessor

Accesses the official Swiss Federal Office of Public Health
(Bundesamt für Gesundheit, BAG/OFSP) **Infectious Diseases Dashboard**
 IDD) REST API — the most complete open machine-readable source for
Swiss national and cantonal infectious-disease surveillance.

Coverage (54 topics / 1,600+ series sets):

- Mandatory notifiable diseases: measles, rubella, diphtheria, pertussis,
  tuberculosis, hepatitis A/B/C/E, salmonellosis, campylobacteriosis,
  EHEC, shigellosis, listeriosis, legionellosis, tick-borne encephalitis,
  Lyme borreliosis, Q fever, hantavirus, malaria, dengue, chikungunya,
  zika, west nile, mpox, HIV, syphilis, gonorrhoea, chlamydiosis, ...
- Sentinel systems: ``influenza-like_illness``,
  ``acute_respiratory_infection``, ``respiratory_pathogens``,
  ``influenza``, ``covid19``
- Environmental: ``wastewater_viral_load``, ``wastewater_sequencing``
- Antimicrobial resistance and consumption: ``antibiotic_resistance``,
  ``antibiotic_usage``, ``antibiotic_prescriptions``

Geography: national (``CH``, plus Liechtenstein ``FL`` in some series)
and cantonal (26 cantons). Stratifications include age group, sex,
pathogen/subtype, test result and wastewater treatment plant.

Data Sources:
- Dashboard: https://idd.bag.admin.ch
- API root: https://api.idd.bag.admin.ch/api/v1
- OpenAPI spec:
  https://api.idd.bag.admin.ch/swagger-ui/api-doc-middleware.json

Authentication: none required
Update Frequency: new weekly version every Wednesday (weekly snapshots
archived since 2023-11-07; some sets lag one version behind — the
``version``/``source_date`` columns returned by the accessor are
authoritative)

License: Swiss open government data (OGD) published by BAG; confirm the
exact terms of use on the dashboard footer before redistribution.

Author: Flávio Codeço Coelho
License: MIT
"""

from __future__ import annotations

import logging
import os
import time
import warnings
from pathlib import Path
from typing import ClassVar

import pandas as pd
import requests

from epidatasets._base import BaseAccessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#: The 26 Swiss cantons (ISO 3166-2:CH two-letter codes).
CANTONS: dict[str, str] = {
    "AG": "Aargau",
    "AI": "Appenzell Innerrhoden",
    "AR": "Appenzell Ausserrhoden",
    "BE": "Bern",
    "BL": "Basel-Landschaft",
    "BS": "Basel-Stadt",
    "FR": "Fribourg",
    "GE": "Geneva",
    "GL": "Glarus",
    "GR": "Graubünden",
    "JU": "Jura",
    "LU": "Luzern",
    "NE": "Neuchâtel",
    "NW": "Nidwalden",
    "OW": "Obwalden",
    "SG": "St. Gallen",
    "SH": "Schaffhausen",
    "SO": "Solothurn",
    "SZ": "Schwyz",
    "TG": "Thurgau",
    "TI": "Ticino",
    "UR": "Uri",
    "VD": "Vaud",
    "VS": "Valais",
    "ZG": "Zug",
    "ZH": "Zürich",
}

#: Column order enforced on series query results.
_SERIES_COLUMNS = [
    "topic",
    "chapter",
    "aggregation",
    "temporality",
    "temporal",
    "value",
]


class SwissBAGAccessor(BaseAccessor):
    """
    Accessor for the Swiss BAG Infectious Diseases Dashboard (IDD) API.

    Example:
        >>> from epidatasets.sources.swiss_bag import SwissBAGAccessor
        >>> bag = SwissBAGAccessor()
        >>>
        >>> # Explore the catalogue
        >>> bag.list_topics()                    # 54 topics
        >>> bag.list_sets(topic="dengueFever")   # chapter/aggregation/temporality
        >>> bag.list_versions().tail()           # weekly snapshots
        >>>
        >>> # National monthly dengue cases
        >>> bag.get_disease_data("dengueFever", temporality="month")
        >>>
        >>> # Canton-level weekly COVID-19 incidence (all cantons)
        >>> bag.get_series(
        ...     "covid19", "cases", "incValue", "iso_week",
        ...     filters={"georegion": "canton"}, all_series=True,
        ... )
        >>>
        >>> # Bulk export (cached)
        >>> bag.download_export("INFLUENZA_sentinella", format="csv")

    Data Sources:
        - Infectious Diseases Dashboard: https://idd.bag.admin.ch
        - BAG (Federal Office of Public Health): https://www.bag.admin.ch
    """

    source_name: ClassVar[str] = "swiss_bag"
    source_description: ClassVar[str] = (
        "Swiss Federal Office of Public Health (BAG) Infectious Diseases "
        "Dashboard: national and cantonal surveillance for notifiable "
        "diseases, sentinel ILI/ARI, respiratory pathogens, wastewater "
        "viral load/sequencing and antimicrobial resistance/consumption"
    )
    source_url: ClassVar[str] = "https://idd.bag.admin.ch"

    #: Versioned REST API root (unauthenticated; beta but export-stable).
    API_ROOT = "https://api.idd.bag.admin.ch/api/v1"
    #: OpenAPI 3.0.1 description of the API.
    OPENAPI_SPEC_URL = (
        "https://api.idd.bag.admin.ch/swagger-ui/"
        "api-doc-middleware.json"
    )

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        cache_ttl_days: float = 7.0,
        timeout: int = 120,
    ):
        """
        Initialize the accessor.

        Args:
            cache_dir: Directory for cached bulk exports (default
                ``~/.cache/epidatasets/swiss_bag``).
            cache_ttl_days: TTL for cached downloads of the *current*
                version (weekly release cycle). Explicit-version
                downloads are immutable and cached permanently.
            timeout: HTTP timeout in seconds.
        """
        if cache_dir is None:
            cache_dir = os.path.join(
                os.path.expanduser("~"),
                ".cache",
                "epidatasets",
                "swiss_bag",
            )
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_ttl_days = cache_ttl_days
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) epidatasets/"
                    "SwissBAGAccessor (Research Purpose)"
                ),
                "Accept": "application/json,text/csv,*/*",
            }
        )
        # in-memory caches for catalogue metadata
        self._sets_cache: list[str] | None = None
        self._details_cache: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(self, path: str, **kwargs) -> requests.Response:
        url = f"{self.API_ROOT}{path}"
        resp = self._session.get(url, timeout=self.timeout, **kwargs)
        resp.raise_for_status()
        return resp

    @staticmethod
    def _parse_temporal(x: int, temporality: str) -> str:
        """
        Decode the API's integer ``x`` time axis into an ISO-like label.

        Encodings: ``year`` → ``2013``; ``month`` → ``2013-01``;
        ``week``/``iso_week``/``iso_week_sentinella`` → ``2013-W01``;
        ``date`` → ``2013-02-10``.
        """
        x = int(x)
        if temporality == "year":
            return str(x)
        if temporality == "month":
            return f"{x // 100:04d}-{x % 100:02d}"
        if temporality in ("week", "iso_week", "iso_week_sentinella"):
            return f"{x // 100:04d}-W{x % 100:02d}"
        if temporality == "date":
            return f"{x // 10000:04d}-{(x // 100) % 100:02d}-{x % 100:02d}"
        return str(x)

    def _set_identifier(
        self,
        topic: str,
        chapter: str,
        aggregation: str,
        temporality: str,
    ) -> str:
        return f"{topic}/{chapter}/{aggregation}/{temporality}"

    # ------------------------------------------------------------------
    # Catalogue discovery
    # ------------------------------------------------------------------

    def list_countries(self) -> pd.DataFrame:
        """
        Countries covered by the dashboard.

        Liechtenstein (``FL``) is reported jointly with Switzerland
        (``CHFL``) in several series; it is only surfaced where a series
        carries the ``country`` property.

        Returns:
            DataFrame with ``country_code`` and ``country_name``.
        """
        return pd.DataFrame(
            [
                {"country_code": "CH", "country_name": "Switzerland"},
                {"country_code": "FL", "country_name": "Liechtenstein"},
            ]
        )

    @staticmethod
    def list_cantons() -> pd.DataFrame:
        """The 26 Swiss cantons (``canton`` code and ``canton_name``)."""
        return pd.DataFrame(
            [
                {"canton": code, "canton_name": name}
                for code, name in CANTONS.items()
            ]
        )

    def list_versions(self) -> pd.DataFrame:
        """
        Weekly data versions available in the API.

        Returns:
            DataFrame with ``version`` (e.g. ``"20261014"``) and
            ``date`` (``"2026-10-14"``), newest first.
        """
        payload = self._get("/version").json()
        rows = []
        for entry in payload:
            name = str(entry.get("name", ""))
            # names are YYYYMMDD, with rare re-run suffixes (e.g. "20250827_V2")
            digits = name.split("_", 1)[0]
            date = None
            if len(digits) == 8 and digits.isdigit():
                date = f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
            rows.append({"version": name, "date": date})
        logger.info(f"Found {len(rows)} IDD data versions")
        return pd.DataFrame(rows)

    @property
    def current_version(self) -> str:
        """Identifier of the current data version (e.g. ``"20261014"``)."""
        return str(self._get("/data/version").json()["name"])

    def list_sets(self, topic: str | None = None) -> pd.DataFrame:
        """
        List all series sets (``topic/chapter/aggregation/temporality``).

        Args:
            topic: Optional topic filter (e.g. ``"dengueFever"``).

        Returns:
            DataFrame with ``topic``, ``chapter``, ``aggregation`` and
            ``temporality`` columns.
        """
        if self._sets_cache is None:
            self._sets_cache = self._get("/data/sets").json()
            logger.info(f"Fetched {len(self._sets_cache)} IDD series sets")
        rows = []
        for entry in self._sets_cache:
            parts = entry.split("/")
            if len(parts) != 4:
                continue
            rows.append(
                {
                    "topic": parts[0],
                    "chapter": parts[1],
                    "aggregation": parts[2],
                    "temporality": parts[3],
                }
            )
        df = pd.DataFrame(rows)
        if topic is not None:
            df = df[df["topic"] == topic].reset_index(drop=True)
            if df.empty:
                known = sorted({r["topic"] for r in rows})
                raise ValueError(
                    f"Unknown topic '{topic}'. "
                    f"Use list_topics(); {len(known)} topics available."
                )
        return df

    def list_topics(self) -> pd.DataFrame:
        """
        Summarise the available topics.

        Returns:
            DataFrame with ``topic``, ``n_sets``, ``chapters``,
            ``aggregations`` and ``temporalities`` (list columns).
        """
        sets = self.list_sets()
        grouped = (
            sets.groupby("topic")
            .agg(
                n_sets=("chapter", "size"),
                chapters=("chapter", lambda s: sorted(set(s))),
                aggregations=("aggregation", lambda s: sorted(set(s))),
                temporalities=("temporality", lambda s: sorted(set(s))),
            )
            .reset_index()
        )
        logger.info(f"Found {len(grouped)} IDD topics")
        return grouped

    def get_set_details(
        self,
        topic: str,
        chapter: str,
        aggregation: str,
        temporality: str,
    ) -> dict:
        """
        Fetch the metadata of one series set: source system, data
        version, the ``properties`` map (possible values per property)
        and ``availableSeriesConfigurations`` (the valid POST bodies).

        Args:
            topic: Topic (e.g. ``"measles"``).
            chapter: Chapter (e.g. ``"cases"``).
            aggregation: Aggregation (e.g. ``"value"``).
            temporality: Temporality (e.g. ``"month"``).

        Returns:
            The raw JSON metadata dict.
        """
        identifier = self._set_identifier(
            topic, chapter, aggregation, temporality
        )
        if identifier not in self._details_cache:
            known = self.list_sets()
            known_sets = set(
                known["topic"]
                + "/"
                + known["chapter"]
                + "/"
                + known["aggregation"]
                + "/"
                + known["temporality"]
            )
            if identifier not in known_sets:
                raise ValueError(
                    f"Unknown series set '{identifier}'. "
                    "Use list_sets() to browse available sets."
                )
            self._details_cache[identifier] = self._get(
                f"/data/{identifier}/details"
            ).json()
        return self._details_cache[identifier]

    # ------------------------------------------------------------------
    # Series queries
    # ------------------------------------------------------------------

    def _query_series(
        self,
        topic: str,
        chapter: str,
        aggregation: str,
        temporality: str,
        body: dict,
    ) -> pd.DataFrame:
        """POST one series query (body from ``availableSeriesConfigurations``)."""
        identifier = self._set_identifier(
            topic, chapter, aggregation, temporality
        )
        resp = self._session.post(
            f"{self.API_ROOT}/data/{identifier}",
            json=body,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        payload = resp.json()

        rows: list[dict] = []
        for point in payload.get("values", []):
            row: dict = {
                "temporal": self._parse_temporal(
                    point.get("x"), temporality
                ),
                "value": point.get("y"),
            }
            row.update(point.get("properties") or {})
            row.update(body)
            row["topic"] = topic
            row["chapter"] = chapter
            row["aggregation"] = aggregation
            row["temporality"] = temporality
            row["source"] = payload.get("source")
            row["source_date"] = payload.get("sourceDate")
            row["version"] = payload.get("version")
            rows.append(row)

        df = pd.DataFrame(rows)
        if df.empty:
            return pd.DataFrame(
                columns=[
                    *_SERIES_COLUMNS,
                    "source",
                    "source_date",
                    "version",
                ]
            )
        ordered = [
            *_SERIES_COLUMNS,
            *(c for c in df.columns if c not in _SERIES_COLUMNS),
        ]
        return df[ordered]

    def get_series(
        self,
        topic: str,
        chapter: str,
        aggregation: str,
        temporality: str,
        filters: dict | None = None,
        all_series: bool = False,
    ) -> pd.DataFrame:
        """
        Query one series set as a tidy DataFrame.

        The POST body must match one of the set's
        ``availableSeriesConfigurations`` (an empty body yields HTTP
        404), so the set ``/details`` metadata is fetched first and the
        body is built from it.

        Args:
            topic: Topic (e.g. ``"covid19"``).
            chapter: Chapter (e.g. ``"cases"``).
            aggregation: Aggregation (e.g. ``"incValue"``).
            temporality: Temporality (e.g. ``"iso_week"``).
            filters: Optional property→value constraints applied to the
                configuration (e.g. ``{"georegion": "canton",
                "canton": "ZH"}``). Property values must be valid for
                the set (see :meth:`get_set_details`).
            all_series: Fan out over every
                ``availableSeriesConfigurations`` entry matching
                *filters* and concatenate the results (the rows carry
                the configuration properties as columns).

        Returns:
            Tidy DataFrame with ``topic``, ``chapter``, ``aggregation``,
            ``temporality``, ``temporal`` (parsed from the integer time
            axis), ``value``, per-value properties (``trend``,
            ``dataComplete``, ...), the configuration properties
            (``georegion``, ``canton``, ``agegroup``, ...) and
            ``source``/``source_date``/``version``.
        """
        details = self.get_set_details(
            topic, chapter, aggregation, temporality
        )
        configs = details.get("availableSeriesConfigurations") or []
        if not configs:
            raise ValueError(
                f"Series set {topic}/{chapter}/{aggregation}/{temporality} "
                "exposes no availableSeriesConfigurations"
            )
        filters = dict(filters or {})

        if all_series:
            selected = [
                dict(cfg)
                for cfg in configs
                if all(cfg.get(k) == v for k, v in filters.items())
            ]
            if not selected:
                raise ValueError(
                    "No series configuration matches filters "
                    f"{filters}; {len(configs)} configurations "
                    "available (see get_set_details())"
                )
            logger.info(
                f"Querying {len(selected)} series configuration(s) of "
                f"{topic}/{chapter}/{aggregation}/{temporality}"
            )
        else:
            base = next(
                (
                    cfg
                    for cfg in configs
                    if all(cfg.get(k) == v for k, v in filters.items())
                ),
                None,
            )
            if base is None:
                base = dict(configs[0])
                unknown = [k for k in filters if k not in base]
                if unknown:
                    raise ValueError(
                        f"Filter properties {unknown} are not part of the "
                        f"series configuration (properties: "
                        f"{sorted(base)}); see get_set_details()"
                    )
            body = dict(base)
            body.update(filters)
            selected = [body]

        frames = [
            self._query_series(
                topic, chapter, aggregation, temporality, body
            )
            for body in selected
        ]
        # fan-out frames may carry different per-value property columns;
        # the union-with-NaN behaviour is exactly what we want
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            result = pd.concat(frames, ignore_index=True)
        logger.info(
            f"Retrieved {len(result)} values for "
            f"{topic}/{chapter}/{aggregation}/{temporality}"
        )
        return result

    def get_disease_data(
        self,
        topic: str,
        temporality: str = "month",
        aggregation: str = "value",
        chapter: str | None = None,
        filters: dict | None = None,
    ) -> pd.DataFrame:
        """
        Convenience wrapper: resolve the chapter of a disease topic and
        fetch its series.

        Args:
            topic: Disease topic (e.g. ``"dengueFever"``).
            temporality: Temporality (default ``"month"``).
            aggregation: Aggregation (default ``"value"``, i.e. case
                counts; use ``"incValue"`` for incidence per 100k).
            chapter: Optional explicit chapter (default: ``"cases"``
                when available, otherwise the first alphabetically).
            filters: Optional property→value constraints (see
                :meth:`get_series`).

        Returns:
            Tidy DataFrame (see :meth:`get_series`).
        """
        sets = self.list_sets(topic=topic)
        if sets.empty:
            raise ValueError(f"Unknown topic '{topic}'")
        if chapter is None:
            chapters = sorted(set(sets["chapter"]))
            chapter = "cases" if "cases" in chapters else chapters[0]
        available = sets[sets["chapter"] == chapter]
        if temporality not in set(available["temporality"]):
            raise ValueError(
                f"Topic '{topic}' chapter '{chapter}' has no "
                f"'{temporality}' temporality; available: "
                f"{sorted(set(available['temporality']))}"
            )
        if aggregation not in set(
            available[available["temporality"] == temporality][
                "aggregation"
            ]
        ):
            raise ValueError(
                f"Topic '{topic}' chapter '{chapter}' temporality "
                f"'{temporality}' has no '{aggregation}' aggregation; "
                f"available: "
                f"{sorted(set(available[available['temporality'] == temporality]['aggregation']))}"
            )
        return self.get_series(
            topic, chapter, aggregation, temporality, filters=filters
        )

    # ------------------------------------------------------------------
    # Bulk exports
    # ------------------------------------------------------------------

    def list_export_files(self, version: str | None = None) -> list[str]:
        """
        Bulk-export file groups available for *version*.

        Args:
            version: Data version (default: current). The export
                controller is the API's most stable part; prefer bulk
                exports where a group exists for the topic of interest.

        Returns:
            Sorted list of file group names (e.g.
            ``"INFLUENZA_sentinella"``).
        """
        version = version or self.current_version
        files = self._get(f"/export/{version}/files").json()
        logger.info(f"Found {len(files)} export file groups for {version}")
        return sorted(str(f) for f in files)

    def download_export(
        self,
        file: str,
        format: str = "csv",
        version: str | None = None,
        max_age_days: float | None = None,
    ) -> pd.DataFrame:
        """
        Download (and cache) a bulk export as a DataFrame.

        Args:
            file: Export file group (see :meth:`list_export_files`).
            format: ``"csv"`` or ``"json"``.
            version: Data version (default: current). Explicit-version
                downloads are immutable and cached permanently.
            max_age_days: Optional cache TTL override (default: the
                accessor's ``cache_ttl_days``; only applied to downloads
                of the *current* version).

        Returns:
            DataFrame of the export records (one row per
            geography×stratification×period).
        """
        if format not in ("csv", "json"):
            raise ValueError(f"Unsupported format '{format}' (csv|json)")
        explicit_version = version is not None
        version = version or self.current_version

        cache_path = self.cache_dir / f"export_{version}_{file}.{format}"
        ttl = (
            self._cache_ttl_days
            if max_age_days is None
            else max_age_days
        )
        if cache_path.exists():
            if explicit_version:
                logger.info(f"Cache hit: {cache_path.name}")
                return self._read_export(cache_path, format)
            age_days = (
                time.time() - cache_path.stat().st_mtime
            ) / 86400
            if age_days < ttl:
                logger.info(f"Cache hit: {cache_path.name}")
                return self._read_export(cache_path, format)

        url = f"{self.API_ROOT}/export/{version}/{file}/{format}"
        logger.info(f"Downloading export {file} ({format}) for {version}")
        resp = self._session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        cache_path.write_bytes(resp.content)
        return self._read_export(cache_path, format)

    @staticmethod
    def _read_export(path: Path, format: str) -> pd.DataFrame:
        if format == "csv":
            return pd.read_csv(path)
        import json

        records = json.loads(path.read_text())
        return pd.DataFrame(records)
