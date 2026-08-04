"""
Global Mammal Parasite Database (GMPD) version 2.0 Accessor

This module provides access to the Global Mammal Parasite Database (GMPD), a
comprehensive compilation of parasites and pathogens from wild primate,
carnivore, and ungulate hosts, obtained from over 2,700 published scientific
literature sources.

Data Source:
    - Portal: https://parasites.nunn-lab.org/
    - GitHub: https://github.com/globalbioticinteractions/global-mammal-parasite-database
    - Wiley Supplement: https://esajournals.onlinelibrary.wiley.com/doi/full/10.1002/ecy.1799

The main data file (``GMPD_main.csv``) contains 24,000+ host-parasite
association records with standardized taxonomies, sampling metadata, and
geospatial information.

Key Features:
    - 24,000+ host-parasite association records
    - 2,700+ literature sources reviewed
    - Covers wild ungulates, carnivores, and primates
    - Georeferenced location data with latitude/longitude coordinates
    - Sampling methodology and sample size metadata
    - Parasite transmission mode classifications

Authentication: None required (open access download)
License: Open access; cite Stephens et al. (2017) Ecology 98:1476

Reference:
    Stephens, P.R., Pappalardo, P., Huang, S., Byers, J.E., Farrell, M.J.,
    Gehman, A., Ghai, R.R., Haas, S.E., Han, B., Park, A.W., Schmidt, J.P.,
    Altizer, S., Ezenwa, V.O. & Nunn, C.L. (2017). Global Mammal Parasite
    Database version 2.0. *Ecology*, 98(5), 1476.
    https://doi.org/10.1002/ecy.1799

Author: Flávio Codeço Coelho
License: MIT
"""

import logging
import time
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Any, ClassVar

import pandas as pd
import requests

from epidatasets._base import BaseAccessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GMPDAccessor(BaseAccessor):
    """
    Accessor for the Global Mammal Parasite Database (GMPD) version 2.0.

    Provides access to host-parasite association records for wild mammals
    (primates, carnivores, and ungulates) compiled from over 2,700 published
    scientific literature sources.

    The full main dataset (~24,000 records) is downloaded once and cached on
    disk, after which queries are served from the local cache.

    Example:
        >>> from epidatasets.sources.gmpd import GMPDAccessor
        >>> gmpd = GMPDAccessor()
        >>>
        >>> # List the three host groups covered
        >>> groups = gmpd.list_host_groups()
        >>>
        >>> # Get all primate virus records
        >>> primate_viruses = gmpd.get_records(group="Primates", parasite_type="Virus")
        >>>
        >>> # Unique host species
        >>> hosts = gmpd.list_hosts(group="Carnivores")

    Data Sources:
        - Portal: https://parasites.nunn-lab.org/
        - GitHub: https://github.com/globalbioticinteractions/global-mammal-parasite-database
    """

    source_name: ClassVar[str] = "gmpd"
    source_description: ClassVar[str] = (
        "Global Mammal Parasite Database (GMPD) version 2.0 — a compilation of "
        "parasites and pathogens from wild primate, carnivore, and ungulate "
        "hosts, with host-parasite association records, standardized taxonomies, "
        "sampling metadata, and geospatial information from 2,700+ literature "
        "sources."
    )
    source_url: ClassVar[str] = "https://parasites.nunn-lab.org/"

    BASE_URL: ClassVar[str] = (
        "https://raw.githubusercontent.com/globalbioticinteractions/"
        "global-mammal-parasite-database/master"
    )
    MAIN_CSV_URL: ClassVar[str] = f"{BASE_URL}/GMPD_main.csv"

    # Host groups reported in the ``Group`` column (lower-cased in raw data).
    HOST_GROUPS: ClassVar[list[str]] = ["primates", "carnivores", "ungulates"]

    # Parasite types reported in the ``ParType`` column.
    PARASITE_TYPES: ClassVar[list[str]] = [
        "Virus",
        "Bacteria",
        "Protozoa",
        "Helminth",
        "Arthropod",
        "Fungus",
    ]

    # Canonical column name mapping (raw GMPD -> snake_case friendly names).
    COLUMN_MAP: ClassVar[dict[str, str]] = {
        "Group": "group",
        "HostReportedName": "host_reported_name",
        "HostCorrectedName": "host_corrected_name",
        "HostOrder": "host_order",
        "HostFamily": "host_family",
        "HostEnvironment": "host_environment",
        "ParasiteReportedName": "parasite_reported_name",
        "ParasiteCorrectedName": "parasite_corrected_name",
        "HasBinomialName": "has_binomial_name",
        "ParType": "parasite_type",
        "ParPhylum": "parasite_phylum",
        "ParClass": "parasite_class",
        "Citation": "citation",
        "LocationName": "location_name",
        "Longitude": "longitude",
        "Latitude": "latitude",
        "PopulationType": "population_type",
        "SamplingBasis": "sampling_basis",
        "SampleNotes": "sample_notes",
        "Prevalence": "prevalence",
        "HostsSampled": "hosts_sampled",
        "HostSex": "host_sex",
        "HostAge": "host_age",
        "Intensity": "intensity",
        "IntensityMeasure": "intensity_measure",
        "NativeRange": "native_range",
        "NumSamples": "num_samples",
        "SamplingType": "sampling_type",
    }

    def __init__(
        self,
        cache_dir: str | None = None,
        cache_ttl_days: int = 30,
    ):
        """
        Initialize the GMPD accessor.

        Args:
            cache_dir: Directory to cache downloaded data. If None, uses the
                default ``~/.cache/epi_data/gmpd``.
            cache_ttl_days: Cache time-to-live in days. GMPD is updated
                irregularly, so a long TTL is appropriate.
        """
        self.cache_dir = (
            Path(cache_dir)
            if cache_dir
            else Path.home() / ".cache" / "epi_data" / "gmpd"
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_ttl = timedelta(days=cache_ttl_days)
        self._session = requests.Session()
        self._session.headers.update(
            {"User-Agent": "epidatasets-gmpd-accessor/1.0 (research)"}
        )

    # ------------------------------------------------------------------
    # Caching helpers
    # ------------------------------------------------------------------
    @property
    def _cache_path(self) -> Path:
        return self.cache_dir / "GMPD_main.csv"

    def _is_cache_valid(self) -> bool:
        if not self._cache_path.exists():
            return False
        mtime = datetime.fromtimestamp(self._cache_path.stat().st_mtime)
        return datetime.now() - mtime < self._cache_ttl

    def _read_cache(self) -> pd.DataFrame:
        return pd.read_csv(self._cache_path, na_values=["NA"])

    def _write_cache(self, text: str) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._cache_path, "w") as f:
            f.write(text)

    def clear_cache(self) -> None:
        """Remove the locally cached GMPD main dataset."""
        if self._cache_path.exists():
            self._cache_path.unlink()
            logger.info("Cleared GMPD cache: %s", self._cache_path)

    # ------------------------------------------------------------------
    # Download / load
    # ------------------------------------------------------------------
    def _download_csv(self, retries: int = 3) -> str:
        """Download the raw GMPD main CSV text with retry logic."""
        last_exc: Exception | None = None
        for attempt in range(retries):
            try:
                logger.info(
                    "Fetching GMPD main data (attempt %d/%d)", attempt + 1, retries
                )
                response = self._session.get(self.MAIN_CSV_URL, timeout=120)
                response.raise_for_status()
                text: str = response.text
                return text
            except requests.exceptions.RequestException as exc:
                last_exc = exc
                logger.warning("Attempt %d failed: %s", attempt + 1, exc)
                if attempt < retries - 1:
                    time.sleep(2**attempt)
        raise RuntimeError(
            f"Failed to download GMPD main data after {retries} attempts"
        ) from last_exc

    def _load_main(
        self,
        use_cache: bool = True,
        normalize: bool = True,
    ) -> pd.DataFrame:
        """
        Load the full GMPD main dataset, downloading and caching if needed.

        Args:
            use_cache: Whether to read from / write to the on-disk cache.
            normalize: Whether to rename columns to snake_case and coerce
                numeric / coordinate columns.

        Returns:
            The main host-parasite association DataFrame.
        """
        if use_cache and self._is_cache_valid():
            logger.info("Loading cached GMPD data: %s", self._cache_path)
            df = self._read_cache()
        else:
            text = self._download_csv()
            df = pd.read_csv(StringIO(text), na_values=["NA"])
            if use_cache:
                self._write_cache(text)

        if normalize:
            df = self._normalize(df)
        return df

    def _normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        """Rename columns and coerce numeric / coordinate columns."""
        df = df.rename(
            columns={k: v for k, v in self.COLUMN_MAP.items() if k in df.columns}
        )

        for col in ("hosts_sampled", "num_samples"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        for col in ("longitude", "latitude"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        if "prevalence" in df.columns:
            df["prevalence"] = pd.to_numeric(df["prevalence"], errors="coerce")

        # Normalise the ``group`` column to title case for friendly filtering.
        if "group" in df.columns:
            df["group"] = df["group"].astype(str).str.strip().str.title()
        return df

    # ------------------------------------------------------------------
    # Abstract method implementation
    # ------------------------------------------------------------------
    def list_countries(self, use_cache: bool = True) -> pd.DataFrame:
        """
        Return a DataFrame of sampling locations covered by GMPD.

        GMPD records free-text locality names (e.g. "Namibia and South
        Africa") rather than ISO country codes, so ``country_code`` is left
        empty and ``country_name`` holds the reported locality.

        Returns
        -------
        pd.DataFrame
            Columns ``country_code`` (NaN) and ``country_name`` (unique
            sampling localities), plus a ``record_count`` column.
        """
        df = self._load_main(use_cache=use_cache)
        if "location_name" not in df.columns:
            return pd.DataFrame(
                columns=["country_code", "country_name", "record_count"]
            )
        counts = (
            df.dropna(subset=["location_name"])
            .groupby("location_name")
            .size()
            .reset_index(name="record_count")
            .rename(columns={"location_name": "country_name"})
            .sort_values("record_count", ascending=False)
            .reset_index(drop=True)
        )
        counts.insert(0, "country_code", [None] * len(counts))
        return counts

    # ------------------------------------------------------------------
    # Metadata helpers
    # ------------------------------------------------------------------
    def list_host_groups(self) -> pd.DataFrame:
        """
        List the host groups (taxonomic orders) covered by GMPD.

        Returns
        -------
        pd.DataFrame
            DataFrame describing the three host groups.
        """
        rows = [
            {
                "group": "Primates",
                "description": "Monkeys, apes, and other primates",
                "orders": "Primates",
            },
            {
                "group": "Carnivores",
                "description": "Cats, dogs, bears, and other carnivores",
                "orders": "Carnivora",
            },
            {
                "group": "Ungulates",
                "description": "Hooved mammals (Artiodactyla, Perissodactyla)",
                "orders": "Artiodactyla, Perissodactyla",
            },
        ]
        return pd.DataFrame(rows)

    def list_datasets(self) -> pd.DataFrame:
        """
        Describe the datasets distributed with GMPD version 2.0.

        Returns
        -------
        pd.DataFrame
            DataFrame with the available GMPD data files.
        """
        rows = [
            {
                "dataset": "GMPD_main",
                "description": "Main host-parasite association records (24,000+ entries)",
                "url": self.MAIN_CSV_URL,
                "available": True,
                "method": "get_records",
            },
            {
                "dataset": "GMPD_parasite_taxonomy",
                "description": "Parasite taxonomy and transmission modes",
                "url": "",
                "available": False,
                "method": "",
            },
            {
                "dataset": "GMPD_host_taxonomy",
                "description": "Host taxonomy information",
                "url": "",
                "available": False,
                "method": "",
            },
            {
                "dataset": "GMPD_references",
                "description": "Bibliographic references for all records",
                "url": "",
                "available": False,
                "method": "",
            },
        ]
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Record retrieval
    # ------------------------------------------------------------------
    def get_records(
        self,
        group: str | list[str] | None = None,
        parasite_type: str | list[str] | None = None,
        host: str | list[str] | None = None,
        parasite: str | list[str] | None = None,
        host_order: str | list[str] | None = None,
        host_family: str | list[str] | None = None,
        location: str | list[str] | None = None,
        has_coordinates: bool | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Get host-parasite association records with optional filtering.

        All filters are case-insensitive and matched against the *corrected*
        (standardized) host / parasite names where applicable.

        Args:
            group: Host group filter. One or more of ``"Primates"``,
                ``"Carnivores"``, ``"Ungulates"``.
            parasite_type: Parasite type filter. One or more of ``"Virus"``,
                ``"Bacteria"``, ``"Protozoa"``, ``"Helminth"``,
                ``"Arthropod"``, ``"Fungus"``.
            host: Host species name(s) (corrected binomial).
            parasite: Parasite species name(s) (corrected binomial).
            host_order: Host taxonomic order(s), e.g. ``"Primates"``.
            host_family: Host taxonomic family(es), e.g. ``"Felidae"``.
            location: Sampling locality name(s) (free text).
            has_coordinates: If True, keep only records with latitude and
                longitude; if False, keep only records without.
            use_cache: Whether to use the on-disk cache.

        Returns
        -------
        pd.DataFrame
            Filtered host-parasite association records.

        Example:
            >>> gmpd = GMPDAccessor()
            >>> # Primate viruses with geographic coordinates
            >>> df = gmpd.get_records(
            ...     group="Primates", parasite_type="Virus", has_coordinates=True
            ... )
        """
        df = self._load_main(use_cache=use_cache)
        if df.empty:
            return df

        df = self._filter_values(df, "group", group, title=True)
        df = self._filter_values(df, "parasite_type", parasite_type, title=True)
        df = self._filter_values(df, "host_corrected_name", host)
        df = self._filter_values(df, "parasite_corrected_name", parasite)
        df = self._filter_values(df, "host_order", host_order, title=True)
        df = self._filter_values(df, "host_family", host_family, title=True)
        df = self._filter_values(df, "location_name", location)

        if has_coordinates is True and {"longitude", "latitude"}.issubset(df.columns):
            df = df.dropna(subset=["longitude", "latitude"])
        elif has_coordinates is False and {"longitude", "latitude"}.issubset(
            df.columns
        ):
            df = df[df["longitude"].isna() | df["latitude"].isna()]

        logger.info("Retrieved %d GMPD records", len(df))
        return df.reset_index(drop=True)

    def _filter_values(
        self,
        df: pd.DataFrame,
        column: str,
        values: str | list[str] | None,
        title: bool = False,
    ) -> pd.DataFrame:
        """Apply a case-insensitive equality filter against a column."""
        if values is None or column not in df.columns or df.empty:
            return df
        if isinstance(values, str):
            values = [values]
        wanted = [str(v).strip() for v in values if v is not None]
        if not wanted:
            return df
        if title:
            wanted = [v.title() for v in wanted]
        mask = (
            df[column]
            .astype(str)
            .str.strip()
            .str.title()
            .isin([v.title() for v in wanted])
        )
        return df[mask]

    # ------------------------------------------------------------------
    # Derived listings
    # ------------------------------------------------------------------
    def list_hosts(
        self,
        group: str | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        List unique host species in the database.

        Args:
            group: Optional host group filter (``"Primates"``,
                ``"Carnivores"``, ``"Ungulates"``).
            use_cache: Whether to use the on-disk cache.

        Returns
        -------
        pd.DataFrame
            One row per host species with order, family, and record count.
        """
        df = self.get_records(group=group, use_cache=use_cache)
        if df.empty or "host_corrected_name" not in df.columns:
            return pd.DataFrame()
        cols = [
            "host_corrected_name",
            "host_order",
            "host_family",
            "group",
        ]
        available = [c for c in cols if c in df.columns]
        hosts = (
            df.dropna(subset=["host_corrected_name"])
            .groupby(available, dropna=False)
            .size()
            .reset_index(name="record_count")
            .rename(columns={"host_corrected_name": "host"})
            .sort_values(["record_count", "host"], ascending=[False, True])
            .reset_index(drop=True)
        )
        return hosts

    def list_parasites(
        self,
        parasite_type: str | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        List unique parasite species in the database.

        Args:
            parasite_type: Optional parasite type filter (e.g. ``"Virus"``).
            use_cache: Whether to use the on-disk cache.

        Returns
        -------
        pd.DataFrame
            One row per parasite species with phylum, class, and record count.
        """
        df = self.get_records(parasite_type=parasite_type, use_cache=use_cache)
        if df.empty or "parasite_corrected_name" not in df.columns:
            return pd.DataFrame()
        cols = [
            "parasite_corrected_name",
            "parasite_type",
            "parasite_phylum",
            "parasite_class",
        ]
        available = [c for c in cols if c in df.columns]
        parasites = (
            df.dropna(subset=["parasite_corrected_name"])
            .groupby(available, dropna=False)
            .size()
            .reset_index(name="record_count")
            .rename(columns={"parasite_corrected_name": "parasite"})
            .sort_values(["record_count", "parasite"], ascending=[False, True])
            .reset_index(drop=True)
        )
        return parasites

    def list_parasite_types(self, use_cache: bool = True) -> pd.DataFrame:
        """
        Summarise parasite types (virus, bacteria, helminth, etc.).

        Returns
        -------
        pd.DataFrame
            One row per parasite type with the number of records and unique
            parasites.
        """
        df = self._load_main(use_cache=use_cache)
        if df.empty or "parasite_type" not in df.columns:
            return pd.DataFrame()
        grouped = df.dropna(subset=["parasite_type"]).groupby("parasite_type")
        summary = grouped.agg(
            record_count=("parasite_type", "size"),
            unique_parasites=(
                "parasite_corrected_name",
                lambda s: s.dropna().nunique(),
            ),
            unique_hosts=(
                "host_corrected_name",
                lambda s: s.dropna().nunique(),
            ),
        ).reset_index()
        return summary.sort_values("record_count", ascending=False).reset_index(
            drop=True
        )

    # ------------------------------------------------------------------
    # Interaction / aggregation helpers
    # ------------------------------------------------------------------
    def get_interactions(
        self,
        group: str | None = None,
        parasite_type: str | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Get unique host-parasite interaction pairs.

        Args:
            group: Optional host group filter.
            parasite_type: Optional parasite type filter.
            use_cache: Whether to use the on-disk cache.

        Returns
        -------
        pd.DataFrame
            One row per unique host-parasite pair with the number of records
            and literature citations supporting the interaction.
        """
        df = self.get_records(
            group=group, parasite_type=parasite_type, use_cache=use_cache
        )
        if df.empty:
            return df
        required = {"host_corrected_name", "parasite_corrected_name"}
        if not required.issubset(df.columns):
            return pd.DataFrame()
        clean = df.dropna(subset=["host_corrected_name", "parasite_corrected_name"])
        agg_cols: dict[str, tuple[str, Any]] = {
            "record_count": ("parasite_corrected_name", "size"),
        }
        if "citation" in clean.columns:
            agg_cols["citations"] = (
                "citation",
                lambda s: ", ".join(sorted({str(c) for c in s.dropna()})),
            )
        interactions = (
            clean.groupby(
                ["host_corrected_name", "parasite_corrected_name"], dropna=False
            )
            .agg(**agg_cols)
            .reset_index()
            .sort_values(
                ["record_count", "host_corrected_name", "parasite_corrected_name"],
                ascending=[False, True, True],
            )
            .reset_index(drop=True)
        )
        return interactions

    def get_summary_statistics(self, use_cache: bool = True) -> pd.DataFrame:
        """
        Compute high-level summary statistics for the GMPD main dataset.

        Returns
        -------
        pd.DataFrame
            A one-row DataFrame with totals for records, hosts, parasites,
            citations, localities, and georeferenced records.
        """
        df = self._load_main(use_cache=use_cache)
        if df.empty:
            return pd.DataFrame()
        stats = {
            "total_records": len(df),
            "unique_hosts": df["host_corrected_name"].dropna().nunique()
            if "host_corrected_name" in df.columns
            else 0,
            "unique_parasites": df["parasite_corrected_name"].dropna().nunique()
            if "parasite_corrected_name" in df.columns
            else 0,
            "unique_citations": df["citation"].dropna().nunique()
            if "citation" in df.columns
            else 0,
            "unique_localities": df["location_name"].dropna().nunique()
            if "location_name" in df.columns
            else 0,
            "host_groups": df["group"].dropna().nunique()
            if "group" in df.columns
            else 0,
            "georeferenced_records": (
                df.dropna(subset=["longitude", "latitude"]).shape[0]
                if {"longitude", "latitude"}.issubset(df.columns)
                else 0
            ),
        }
        return pd.DataFrame([stats])

    def search_records(
        self,
        query: str,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Search host and parasite names for a case-insensitive substring.

        Args:
            query: Search term (matched against host and parasite names).
            use_cache: Whether to use the on-disk cache.

        Returns
        -------
        pd.DataFrame
            Records whose host or parasite name matches the query.
        """
        df = self._load_main(use_cache=use_cache)
        if df.empty or not query:
            return df
        name_cols = [
            c
            for c in ("host_corrected_name", "parasite_corrected_name")
            if c in df.columns
        ]
        if not name_cols:
            return df
        mask = pd.Series(False, index=df.index)
        for col in name_cols:
            mask = mask | df[col].astype(str).str.contains(query, case=False, na=False)
        return df[mask].reset_index(drop=True)


# ----------------------------------------------------------------------
# Convenience functions
# ----------------------------------------------------------------------
def get_records(
    group: str | list[str] | None = None,
    parasite_type: str | list[str] | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """Convenience function to fetch GMPD host-parasite records."""
    return GMPDAccessor().get_records(
        group=group, parasite_type=parasite_type, use_cache=use_cache
    )


def list_hosts(group: str | None = None, use_cache: bool = True) -> pd.DataFrame:
    """Convenience function to list unique GMPD host species."""
    return GMPDAccessor().list_hosts(group=group, use_cache=use_cache)


def list_parasites(
    parasite_type: str | None = None, use_cache: bool = True
) -> pd.DataFrame:
    """Convenience function to list unique GMPD parasite species."""
    return GMPDAccessor().list_parasites(
        parasite_type=parasite_type, use_cache=use_cache
    )
