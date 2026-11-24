"""
Enhanced Infectious Diseases Database (EID2) Accessor

This module provides access to the Enhanced Infectious Diseases Database
(EID2), an evidence-based open-access database maintained by the LUCINDA
team at the University of Liverpool.  EID2 uses a "Big Data" approach to
mine openly accessible information from scientific literature and
pre-existing databases (NCBI Nucleotide, PubMed, GeoNames) to map the
relationships between human and animal diseases, their hosts, and
disease-causing pathogens.

Data Source:
    - Portal: https://eid2.liverpool.ac.uk/
    - Project: https://www.liverpool.ac.uk/infection-veterinary-and-ecological-sciences/research/groups/climate-and-infectious-diseases-of-animals/eid2/
    - Species-species interactions (FigShare): https://doi.org/10.6084/m9.figshare.1381853
    - Species-location interactions (FigShare): https://doi.org/10.6084/m9.figshare.1381854
    - Updated 2022 organism interactions (FigShare): https://figshare.com/articles/dataset/EID2_organism_interactions_raw_2022_csv/22060922

Key Features:
    - 22,515 unique species-species interactions (6,314 carrier and 8,905
      cargo species) backed by NCBI sequences and PubMed publications
    - 157,204 location records linking 72,533 species to countries and
      first administrative divisions worldwide
    - Taxonomy based on NCBI Taxonomy with manual supplements
    - Evidence-backed entries: every interaction carries the supporting
      sequence (GI) and publication (PMID) identifiers

Datasets:
    1. ``interactions`` — species-species interactions (cargo-carrier):
       pathogen-host, vector-host, commensal and mutualistic records (2014)
    2. ``locations`` — species-location interactions at country and
       first-administrative-division level (2014)
    3. ``raw_2022`` — updated raw organism interactions with NCBI
       taxonomic identifiers (2022)

Authentication: None required for bulk downloads (FigShare). The web
interface needs free registration; automated scraping of the web
interface is explicitly prohibited by the EID2 team — this accessor
only uses the sanctioned bulk downloads.

License: Creative Commons Attribution 4.0 (CC BY 4.0). Please cite
Wardeh et al. (2015) when using this data.

Reference:
    Wardeh, M., Risley, C., McIntyre, M.K., Setzkorn, C. & Baylis, M.
    (2015). Database of host-pathogen and related species interactions,
    and their global distribution. *Scientific Data* 2, 150049.
    https://doi.org/10.1038/sdata.2015.49

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


class EID2Accessor(BaseAccessor):
    """
    Accessor for the Enhanced Infectious Diseases Database (EID2).

    Provides access to evidence-backed host-pathogen, vector-host and
    other carrier-cargo interactions compiled from scientific literature
    and NCBI/PubMed metadata, together with the geographic distribution
    of the species involved, at country and first administrative
    division level.

    Datasets are downloaded from FigShare once and cached on disk,
    after which queries are served from the local cache.

    Example:
        >>> from epidatasets.sources.eid2 import EID2Accessor
        >>> eid2 = EID2Accessor()
        >>>
        >>> # All virus interactions involving human carriers
        >>> df = eid2.get_interactions(
        ...     cargo="human parainfluenza virus 1",
        ...     carrier="homo sapiens",
        ... )
        >>>
        >>> # Species recorded in a country and its regions
        >>> locations = eid2.get_locations(country="brazil")
        >>>
        >>> # Updated 2022 interactions with NCBI taxonomic IDs
        >>> raw = eid2.get_raw_interactions_2022()

    Data Sources:
        - Portal: https://eid2.liverpool.ac.uk/
        - FigShare: https://doi.org/10.6084/m9.figshare.1381853
        - FigShare: https://doi.org/10.6084/m9.figshare.1381854
    """

    source_name: ClassVar[str] = "eid2"
    source_description: ClassVar[str] = (
        "Enhanced Infectious Diseases Database (EID2) — an evidence-based "
        "open-access database of host-pathogen and related species "
        "interactions, and their global distribution, mined from scientific "
        "literature and NCBI/PubMed metadata by the University of Liverpool "
        "LUCINDA team."
    )
    source_url: ClassVar[str] = "https://eid2.liverpool.ac.uk/"

    # FigShare article DOIs / identifiers
    INTERACTIONS_DOI: ClassVar[str] = "10.6084/m9.figshare.1381853"
    LOCATIONS_DOI: ClassVar[str] = "10.6084/m9.figshare.1381854"
    RAW_2022_ARTICLE: ClassVar[str] = (
        "https://figshare.com/articles/dataset/EID2_organism_interactions_raw_2022_csv/22060922"
    )

    # Direct bulk-download endpoints (FigShare ndownloader)
    SPECIES_INTERACTIONS_URL: ClassVar[str] = (
        "https://ndownloader.figshare.com/files/2196534"
    )
    LOCATION_INTERACTIONS_URL: ClassVar[str] = (
        "https://ndownloader.figshare.com/files/2081622"
    )
    RAW_INTERACTIONS_2022_URL: ClassVar[str] = (
        "https://ndownloader.figshare.com/files/39418972"
    )

    # Canonical column name mapping: species-species interactions (2014).
    INTERACTIONS_COLUMN_MAP: ClassVar[dict[str, str]] = {
        "Cargo": "cargo",
        "Cargo classification": "cargo_classification",
        "Carrier": "carrier",
        "Carrier classification": "carrier_classification",
        "Sequences count": "sequences_count",
        "Publications count": "publications_count",
        "Sequences": "sequences",
        "Publications": "publications",
    }

    # Canonical column name mapping: species-location interactions (2014).
    LOCATION_COLUMN_MAP: ClassVar[dict[str, str]] = {
        "Species": "species",
        "Species classification": "species_classification",
        "Country": "country",
        "Region": "region",
        "Sequences count": "sequences_count",
        "Publications count": "publications_count",
        "Sequences": "sequences",
        "Publications": "publications",
    }

    # Canonical column name mapping: raw organism interactions (2022).
    RAW_2022_COLUMN_MAP: ClassVar[dict[str, str]] = {
        "cargo": "cargo",
        "cargoID": "cargo_id",
        "cargoTaxID": "cargo_tax_id",
        "cargoRank": "cargo_rank",
        "cargoclass": "cargo_class",
        "carrier": "carrier",
        "carrierid": "carrier_id",
        "carriertaxid": "carrier_tax_id",
        "carrierRank": "carrier_rank",
        "carrierclass": "carrier_class",
        "sequencesNo": "sequences_count",
        "papersNo": "publications_count",
    }

    # Read the ~50 MB 2022 file in chunks to limit memory use.
    RAW_2022_CHUNKSIZE: ClassVar[int] = 100_000

    def __init__(
        self,
        cache_dir: str | None = None,
        cache_ttl_days: int = 30,
    ):
        """
        Initialize the EID2 accessor.

        Args:
            cache_dir: Directory to cache downloaded data. If None, uses
                the default ``~/.cache/epi_data/eid2``.
            cache_ttl_days: Cache time-to-live in days. EID2 is updated
                continuously, but bulk FigShare snapshots change rarely,
                so a long TTL is appropriate.
        """
        self.cache_dir = (
            Path(cache_dir)
            if cache_dir
            else Path.home() / ".cache" / "epi_data" / "eid2"
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_ttl = timedelta(days=cache_ttl_days)
        self._session = requests.Session()
        self._session.headers.update(
            {"User-Agent": "epidatasets-eid2-accessor/1.0 (research)"}
        )

    # ------------------------------------------------------------------
    # Caching helpers
    # ------------------------------------------------------------------
    def _cache_path(self, dataset: str) -> Path:
        """Return the cache file path for a named dataset."""
        filenames = {
            "interactions": "SpeciesInteractions_EID2.csv",
            "locations": "LocationInteractions_EID2.csv",
            "raw_2022": "EID2_organism_interactions_raw_2022.csv",
        }
        return self.cache_dir / filenames[dataset]

    def _is_cache_valid(self, dataset: str) -> bool:
        path = self._cache_path(dataset)
        if not path.exists():
            return False
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        return datetime.now() - mtime < self._cache_ttl

    def _read_cache(self, dataset: str) -> str:
        with open(self._cache_path(dataset)) as f:
            return f.read()

    def _write_cache(self, dataset: str, text: str) -> None:
        self._cache_path(dataset).parent.mkdir(parents=True, exist_ok=True)
        with open(self._cache_path(dataset), "w") as f:
            f.write(text)

    def clear_cache(self) -> None:
        """Remove all locally cached EID2 datasets."""
        for dataset in ("interactions", "locations", "raw_2022"):
            path = self._cache_path(dataset)
            if path.exists():
                path.unlink()
                logger.info("Cleared EID2 cache: %s", path)

    # ------------------------------------------------------------------
    # Download / load
    # ------------------------------------------------------------------
    def _download_csv(self, url: str, retries: int = 3) -> str:
        """Download a raw CSV text file with retry logic."""
        last_exc: Exception | None = None
        for attempt in range(retries):
            try:
                logger.info("Fetching %s (attempt %d/%d)", url, attempt + 1, retries)
                response = self._session.get(url, timeout=300)
                response.raise_for_status()
                return response.text
            except requests.exceptions.RequestException as exc:
                last_exc = exc
                logger.warning("Attempt %d failed: %s", attempt + 1, exc)
                if attempt < retries - 1:
                    time.sleep(2**attempt)
        raise RuntimeError(
            f"Failed to download {url} after {retries} attempts"
        ) from last_exc

    def _load_dataset(
        self,
        dataset: str,
        url: str,
        use_cache: bool = True,
    ) -> str:
        """Load a dataset's raw CSV text, downloading and caching if needed."""
        if use_cache and self._is_cache_valid(dataset):
            logger.info("Loading cached EID2 data: %s", self._cache_path(dataset))
            return self._read_cache(dataset)
        text = self._download_csv(url)
        if use_cache:
            self._write_cache(dataset, text)
        return text

    def _load_interactions(
        self,
        use_cache: bool = True,
        normalize: bool = True,
    ) -> pd.DataFrame:
        """
        Load the species-species interactions dataset (2014).

        Args:
            use_cache: Whether to read from / write to the on-disk cache.
            normalize: Whether to rename columns to snake_case and coerce
                numeric columns.

        Returns:
            The species-species interactions DataFrame.
        """
        text = self._load_dataset(
            "interactions", self.SPECIES_INTERACTIONS_URL, use_cache
        )
        df = pd.read_csv(StringIO(text), na_values=["NA"])
        if normalize:
            df = self._normalize(df, self.INTERACTIONS_COLUMN_MAP)
        return df

    def _load_locations(
        self,
        use_cache: bool = True,
        normalize: bool = True,
    ) -> pd.DataFrame:
        """
        Load the species-location interactions dataset (2014).

        Args:
            use_cache: Whether to read from / write to the on-disk cache.
            normalize: Whether to rename columns to snake_case and coerce
                numeric columns.

        Returns:
            The species-location interactions DataFrame.
        """
        text = self._load_dataset(
            "locations", self.LOCATION_INTERACTIONS_URL, use_cache
        )
        df = pd.read_csv(StringIO(text), na_values=["NA"])
        if normalize:
            df = self._normalize(df, self.LOCATION_COLUMN_MAP)
        return df

    def _load_raw_2022(
        self,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Load the updated raw organism interactions dataset (2022).

        The file is ~50 MB, so it is read in chunks and concatenated.

        Args:
            use_cache: Whether to read from / write to the on-disk cache.

        Returns:
            The raw 2022 organism interactions DataFrame.
        """
        text = self._load_dataset("raw_2022", self.RAW_INTERACTIONS_2022_URL, use_cache)
        chunks = pd.read_csv(
            StringIO(text),
            na_values=["NA"],
            chunksize=self.RAW_2022_CHUNKSIZE,
        )
        df: pd.DataFrame = pd.concat(chunks, ignore_index=True)
        return self._normalize(df, self.RAW_2022_COLUMN_MAP)

    def _normalize(self, df: pd.DataFrame, column_map: dict[str, str]) -> pd.DataFrame:
        """Rename columns and coerce numeric columns."""
        df = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})
        for col in ("sequences_count", "publications_count"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        # Tidy whitespace on name/location columns.
        for col in df.columns:
            if df[col].dtype == object and col not in (
                "sequences",
                "publications",
            ):
                df[col] = df[col].astype("string").str.strip().replace("", pd.NA)
        return df

    @staticmethod
    def parse_evidence(value: Any) -> list[str]:
        """
        Split an evidence cell (``;``-separated GI or PMID list) into items.

        Args:
            value: Raw cell value, e.g. ``"404244281;306035150"``.

        Returns:
            A list of identifier strings (empty when the cell is missing).
        """
        if pd.isna(value):
            return []
        return [item.strip() for item in str(value).split(";") if item.strip()]

    # ------------------------------------------------------------------
    # Abstract method implementation
    # ------------------------------------------------------------------
    def list_countries(self, use_cache: bool = True) -> pd.DataFrame:
        """
        Return a DataFrame of countries covered by EID2.

        Country names come from GeoNames as lower-case free text, so
        ``country_code`` is left empty and ``country_name`` holds the
        reported country.

        Returns
        -------
        pd.DataFrame
            Columns ``country_code`` (NaN), ``country_name`` (unique
            countries) and ``record_count`` (species-location records),
            sorted by ``record_count`` descending.
        """
        df = self._load_locations(use_cache=use_cache)
        if df.empty or "country" not in df.columns:
            return pd.DataFrame(
                columns=["country_code", "country_name", "record_count"]
            )
        counts = (
            df.dropna(subset=["country"])
            .groupby("country")
            .size()
            .reset_index(name="record_count")
            .rename(columns={"country": "country_name"})
            .sort_values("record_count", ascending=False)
            .reset_index(drop=True)
        )
        counts.insert(0, "country_code", [None] * len(counts))
        return counts

    # ------------------------------------------------------------------
    # Metadata helpers
    # ------------------------------------------------------------------
    def list_datasets(self) -> pd.DataFrame:
        """
        Describe the EID2 bulk datasets distributed via FigShare.

        Returns
        -------
        pd.DataFrame
            DataFrame with the available EID2 data files.
        """
        rows = [
            {
                "dataset": "interactions",
                "description": (
                    "Species-species interactions (cargo-carrier), "
                    "evidence-backed with sequence and publication IDs (2014)"
                ),
                "url": self.SPECIES_INTERACTIONS_URL,
                "doi": self.INTERACTIONS_DOI,
                "method": "get_interactions",
            },
            {
                "dataset": "locations",
                "description": (
                    "Species-location interactions at country and first "
                    "administrative division level (2014)"
                ),
                "url": self.LOCATION_INTERACTIONS_URL,
                "doi": self.LOCATIONS_DOI,
                "method": "get_locations",
            },
            {
                "dataset": "raw_2022",
                "description": (
                    "Updated raw organism interactions with NCBI taxonomic "
                    "identifiers (2022)"
                ),
                "url": self.RAW_INTERACTIONS_2022_URL,
                "doi": "",
                "method": "get_raw_interactions_2022",
            },
        ]
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Record retrieval
    # ------------------------------------------------------------------
    def get_interactions(
        self,
        cargo: str | list[str] | None = None,
        carrier: str | list[str] | None = None,
        cargo_classification: str | list[str] | None = None,
        carrier_classification: str | list[str] | None = None,
        has_publications: bool | None = None,
        has_sequences: bool | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Get species-species interaction records with optional filtering.

        All name filters are case-insensitive.

        Args:
            cargo: Cargo species name(s), e.g. pathogens or parasites.
            carrier: Carrier species name(s), e.g. hosts or vectors.
            cargo_classification: Cargo organism classification(s), e.g.
                ``"Virus"``, ``"Bacteria"``, ``"Fungi"``, ``"Protozoa"``.
            carrier_classification: Carrier organism classification(s),
                e.g. ``"Mammals"``, ``"Aves"``, ``"Higher Plants"``.
            has_publications: If True, keep only records with at least one
                publication; if False, only records without.
            has_sequences: If True, keep only records with at least one
                NCBI sequence; if False, only records without.
            use_cache: Whether to use the on-disk cache.

        Returns
        -------
        pd.DataFrame
            Filtered species-species interaction records.

        Example:
            >>> eid2 = EID2Accessor()
            >>> # Virus interactions with humans supported by publications
            >>> df = eid2.get_interactions(
            ...     carrier="human",
            ...     cargo_classification="Virus",
            ...     has_publications=True,
            ... )
        """
        df = self._load_interactions(use_cache=use_cache)
        if df.empty:
            return df

        df = self._filter_values(df, "cargo", cargo)
        df = self._filter_values(df, "carrier", carrier)
        df = self._filter_values(df, "cargo_classification", cargo_classification)
        df = self._filter_values(df, "carrier_classification", carrier_classification)

        if has_publications is True and "publications_count" in df.columns:
            df = df[df["publications_count"] > 0]
        elif has_publications is False and "publications_count" in df.columns:
            df = df[df["publications_count"].fillna(0) == 0]

        if has_sequences is True and "sequences_count" in df.columns:
            df = df[df["sequences_count"] > 0]
        elif has_sequences is False and "sequences_count" in df.columns:
            df = df[df["sequences_count"].fillna(0) == 0]

        logger.info("Retrieved %d EID2 interaction records", len(df))
        return df.reset_index(drop=True)

    def get_locations(
        self,
        species: str | list[str] | None = None,
        classification: str | list[str] | None = None,
        country: str | list[str] | None = None,
        region: str | list[str] | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Get species-location records with optional filtering.

        All filters are case-insensitive. ``country`` and ``region`` use
        the free-text GeoNames values found in the dataset (lower case).

        Args:
            species: Species name(s).
            classification: Species classification(s), e.g. ``"Virus"``,
                ``"Mammals"``.
            country: Country name(s), e.g. ``"brazil"``.
            region: First administrative division name(s), e.g.
                ``"sao paulo"``.
            use_cache: Whether to use the on-disk cache.

        Returns
        -------
        pd.DataFrame
            Filtered species-location records.

        Example:
            >>> eid2 = EID2Accessor()
            >>> # Viruses recorded in Brazil
            >>> df = eid2.get_locations(country="brazil", classification="Virus")
        """
        df = self._load_locations(use_cache=use_cache)
        if df.empty:
            return df

        df = self._filter_values(df, "species", species)
        df = self._filter_values(df, "species_classification", classification)
        df = self._filter_values(df, "country", country)
        df = self._filter_values(df, "region", region)

        logger.info("Retrieved %d EID2 location records", len(df))
        return df.reset_index(drop=True)

    def get_raw_interactions_2022(
        self,
        cargo: str | list[str] | None = None,
        carrier: str | list[str] | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Get the updated raw organism interactions dataset (2022).

        Contains the same cargo-carrier pairs as the 2014 interactions
        snapshot, updated with NCBI taxonomic identifiers
        (``cargo_tax_id`` / ``carrier_tax_id``) and NCBI rank and class
        information. The file is ~50 MB; the result is cached on disk.

        Args:
            cargo: Cargo species name(s).
            carrier: Carrier species name(s).
            use_cache: Whether to use the on-disk cache.

        Returns
        -------
        pd.DataFrame
            Raw organism interaction records with taxonomic IDs.
        """
        df = self._load_raw_2022(use_cache=use_cache)
        if df.empty:
            return df

        df = self._filter_values(df, "cargo", cargo)
        df = self._filter_values(df, "carrier", carrier)

        logger.info("Retrieved %d EID2 raw 2022 interaction records", len(df))
        return df.reset_index(drop=True)

    def _filter_values(
        self,
        df: pd.DataFrame,
        column: str,
        values: str | list[str] | None,
    ) -> pd.DataFrame:
        """Apply a case-insensitive equality filter against a column."""
        if values is None or column not in df.columns or df.empty:
            return df
        if isinstance(values, str):
            values = [values]
        wanted = [str(v).strip().casefold() for v in values if v is not None]
        if not wanted:
            return df
        mask = df[column].astype("string").str.strip().str.casefold().isin(wanted)
        return df[mask]

    # ------------------------------------------------------------------
    # Derived listings
    # ------------------------------------------------------------------
    def list_regions(
        self,
        country: str | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        List first administrative divisions covered by EID2.

        Args:
            country: Optional country filter (GeoNames free text).
            use_cache: Whether to use the on-disk cache.

        Returns
        -------
        pd.DataFrame
            One row per country/region pair with the number of records
            and unique species recorded.
        """
        df = self.get_locations(country=country, use_cache=use_cache)
        if df.empty or "region" not in df.columns:
            return pd.DataFrame(
                columns=["country", "region", "record_count", "unique_species"]
            )
        clean = df.dropna(subset=["region"])
        grouped = (
            clean.groupby(["country", "region"], dropna=False)
            .agg(
                record_count=("species", "size"),
                unique_species=("species", "nunique"),
            )
            .reset_index()
            .sort_values(
                ["record_count", "country", "region"],
                ascending=[False, True, True],
            )
            .reset_index(drop=True)
        )
        return grouped

    def list_species(
        self,
        classification: str | None = None,
        role: str | list[str] | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        List unique species in the species-species interactions dataset.

        Args:
            classification: Optional organism classification filter, e.g.
                ``"Virus"``, ``"Mammals"``.
            role: Restrict to ``"cargo"`` and/or ``"carrier"`` roles.
                Defaults to both.
            use_cache: Whether to use the on-disk cache.

        Returns
        -------
        pd.DataFrame
            One row per species with its role(s), classification and
            interaction record count.
        """
        df = self._load_interactions(use_cache=use_cache)
        if df.empty:
            return pd.DataFrame(
                columns=["species", "role", "classification", "record_count"]
            )
        if role is None:
            roles = ["cargo", "carrier"]
        elif isinstance(role, str):
            roles = [role]
        else:
            roles = list(role)
        frames = []
        for role_name in roles:
            col = role_name  # "cargo" / "carrier"
            class_col = f"{col}_classification"
            if col not in df.columns:
                continue
            part = df.dropna(subset=[col])
            agg = part.groupby(col).size().reset_index(name="record_count")
            agg = agg.rename(columns={col: "species"})
            agg.insert(1, "role", role_name)
            if class_col in part.columns:
                classes = (
                    part.dropna(subset=[class_col])
                    .groupby(col)[class_col]
                    .agg(lambda s: ", ".join(sorted(set(s.astype(str)))))
                )
                agg = agg.merge(
                    classes.rename("classification"),
                    left_on="species",
                    right_index=True,
                    how="left",
                )
            else:
                agg["classification"] = pd.NA
            frames.append(agg)
        if not frames:
            return pd.DataFrame(
                columns=["species", "role", "classification", "record_count"]
            )
        result = pd.concat(frames, ignore_index=True)
        result = self._filter_values(result, "classification", classification)
        return result.sort_values(
            ["record_count", "species"], ascending=[False, True]
        ).reset_index(drop=True)

    def list_classifications(self, use_cache: bool = True) -> pd.DataFrame:
        """
        Summarise organism classifications across cargos and carriers.

        Returns
        -------
        pd.DataFrame
            One row per classification with cargo/carrier interaction
            record counts and unique species tallies.
        """
        df = self._load_interactions(use_cache=use_cache)
        if df.empty:
            return pd.DataFrame()
        records: dict[str, dict[str, int]] = {}
        for role in ("cargo", "carrier"):
            class_col = f"{role}_classification"
            if class_col not in df.columns:
                continue
            clean = df.dropna(subset=[class_col])
            for class_name, group in clean.groupby(class_col):
                entry = records.setdefault(
                    str(class_name),
                    {
                        "cargo_records": 0,
                        "carrier_records": 0,
                        "unique_cargos": 0,
                        "unique_carriers": 0,
                    },
                )
                entry[f"{role}_records"] += len(group)
                entry[f"unique_{role}s"] += group[role].dropna().nunique()
        if not records:
            return pd.DataFrame()
        summary = pd.DataFrame.from_dict(records, orient="index")
        summary.index.name = "classification"
        return (
            summary.reset_index()
            .sort_values(["cargo_records", "carrier_records"], ascending=False)
            .reset_index(drop=True)
        )

    # ------------------------------------------------------------------
    # Aggregation / search helpers
    # ------------------------------------------------------------------
    def get_summary_statistics(self, use_cache: bool = True) -> pd.DataFrame:
        """
        Compute high-level summary statistics for the EID2 datasets.

        Returns
        -------
        pd.DataFrame
            A one-row DataFrame with totals for interactions, species,
            locations, countries and evidence links.
        """
        interactions = self._load_interactions(use_cache=use_cache)
        locations = self._load_locations(use_cache=use_cache)
        stats: dict[str, Any] = {
            "interaction_records": len(interactions),
            "unique_cargos": interactions["cargo"].dropna().nunique()
            if "cargo" in interactions.columns
            else 0,
            "unique_carriers": interactions["carrier"].dropna().nunique()
            if "carrier" in interactions.columns
            else 0,
            "location_records": len(locations),
            "unique_species_locations": locations["species"].dropna().nunique()
            if "species" in locations.columns
            else 0,
            "unique_countries": locations["country"].dropna().nunique()
            if "country" in locations.columns
            else 0,
            "unique_regions": locations["region"].dropna().nunique()
            if "region" in locations.columns
            else 0,
            "interaction_sequences": pd.to_numeric(
                interactions["sequences_count"], errors="coerce"
            ).sum()
            if "sequences_count" in interactions.columns
            else 0,
            "interaction_publications": pd.to_numeric(
                interactions["publications_count"], errors="coerce"
            ).sum()
            if "publications_count" in interactions.columns
            else 0,
        }
        return pd.DataFrame([stats])

    def search_records(
        self,
        query: str,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Search species names in the interactions dataset for a substring.

        Args:
            query: Search term (matched against cargo and carrier names).
            use_cache: Whether to use the on-disk cache.

        Returns
        -------
        pd.DataFrame
            Interaction records whose cargo or carrier name matches.
        """
        df = self._load_interactions(use_cache=use_cache)
        if df.empty or not query:
            return df
        name_cols = [c for c in ("cargo", "carrier") if c in df.columns]
        if not name_cols:
            return df
        mask = pd.Series(False, index=df.index)
        for col in name_cols:
            mask = mask | df[col].astype("string").str.contains(
                query, case=False, na=False
            )
        return df[mask].reset_index(drop=True)


# ----------------------------------------------------------------------
# Convenience functions
# ----------------------------------------------------------------------
def get_interactions(
    cargo: str | list[str] | None = None,
    carrier: str | list[str] | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """Convenience function to fetch EID2 species-species interactions."""
    return EID2Accessor().get_interactions(
        cargo=cargo, carrier=carrier, use_cache=use_cache
    )


def get_locations(
    species: str | list[str] | None = None,
    country: str | list[str] | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """Convenience function to fetch EID2 species-location records."""
    return EID2Accessor().get_locations(
        species=species, country=country, use_cache=use_cache
    )


def list_species(
    classification: str | None = None, use_cache: bool = True
) -> pd.DataFrame:
    """Convenience function to list unique EID2 species."""
    return EID2Accessor().list_species(
        classification=classification, use_cache=use_cache
    )
