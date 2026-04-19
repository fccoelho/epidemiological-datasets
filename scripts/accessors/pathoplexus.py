"""
Pathoplexus API Accessor

Provides access to genomic pathogen data from Pathoplexus.
Pathoplexus is an open-source database for sharing human viral pathogen genomic data,
integrated with INSDC databases (NCBI, ENA, DDBJ).

Data Source: https://pathoplexus.org
API: https://lapis.pathoplexus.org
License: Open Data (CC BY 4.0 for open data, restricted terms for protected data)
Update Frequency: Continuous
Coverage: Global (focus on human viral pathogens)

Supported Organisms:
- dengue: Dengue Virus
- mpox: Mpox Virus
- yellow-fever: Yellow Fever Virus
- west-nile: West Nile Virus
- measles: Measles Virus
- cchf: Crimean-Congo Hemorrhagic Fever Virus
- ebola-zaire: Ebola Zaire Virus
- ebola-sudan: Ebola Sudan Virus
- hmpv: Human Metapneumovirus
- marburg: Marburg Virus
- rsv-a: Respiratory Syncytial Virus A
- rsv-b: Respiratory Syncytial Virus B

Author: Flávio Codeço Coelho
License: MIT
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Union

import pandas as pd
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PathoplexusAccessor:
    """
    Accessor for Pathoplexus API (LAPIS - Lightweight API for Sequences).

    Provides access to genomic sequences, metadata, mutations, and insertions
    for human viral pathogens.

    Example:
        >>> from scripts.accessors.pathoplexus import PathoplexusAccessor
        >>> ppx = PathoplexusAccessor('dengue')
        >>> metadata = ppx.get_metadata(country='Brazil', date_from='2024-01-01')
        >>> count = ppx.count_sequences(country='Brazil')
    """

    BASE_URL = "https://lapis.pathoplexus.org"

    # Supported organisms
    ORGANISMS = {
        'dengue': 'Dengue Virus',
        'mpox': 'Mpox Virus',
        'yellow-fever': 'Yellow Fever Virus',
        'west-nile': 'West Nile Virus',
        'measles': 'Measles Virus',
        'cchf': 'Crimean-Congo Hemorrhagic Fever Virus',
        'ebola-zaire': 'Ebola Zaire Virus',
        'ebola-sudan': 'Ebola Sudan Virus',
        'hmpv': 'Human Metapneumovirus',
        'marburg': 'Marburg Virus',
        'rsv-a': 'Respiratory Syncytial Virus A',
        'rsv-b': 'Respiratory Syncytial Virus B',
    }

    def __init__(
        self,
        organism: str,
        cache_dir: Optional[str] = None,
        cache_ttl: int = 24,
    ):
        """
        Initialize Pathoplexus accessor.

        Args:
            organism: Organism code (e.g., 'dengue', 'mpox')
            cache_dir: Directory to cache downloaded data
            cache_ttl: Cache time-to-live in hours (default: 24)

        Raises:
            ValueError: If organism is not supported
        """
        if organism not in self.ORGANISMS:
            raise ValueError(
                f"Organism '{organism}' not supported. "
                f"Choose from: {list(self.ORGANISMS.keys())}"
            )

        self.organism = organism
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'epidemiological-datasets/1.0',
            'Accept': 'application/json',
        })

        # Setup caching
        self.cache_dir = (
            Path(cache_dir)
            if cache_dir
            else Path.home() / ".cache" / "epi_data" / "pathoplexus"
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_ttl = timedelta(hours=cache_ttl)

        logger.info(f"Initialized Pathoplexus accessor for {self.ORGANISMS[organism]}")

    def _get_cache_path(self, filename: str) -> Path:
        """Return the path to a cache file."""
        # Sanitize filename to avoid path issues
        safe_filename = filename.replace('/', '_').replace('\\', '_')
        return self.cache_dir / f"{self.organism}_{safe_filename}"

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Return True if the cache file exists and is younger than the TTL."""
        if not cache_path.exists():
            return False
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        return datetime.now() - mtime < self._cache_ttl

    def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        use_cache: bool = True,
    ) -> Dict:
        """
        Make API request with optional caching.

        Args:
            endpoint: API endpoint (e.g., 'sample/details')
            params: Query parameters
            use_cache: Whether to use cache

        Returns:
            JSON response as dictionary
        """
        cache_key = f"{endpoint}_{hash(str(params))}.json"
        cache_path = self._get_cache_path(cache_key)

        if use_cache and self._is_cache_valid(cache_path):
            logger.info(f"Loading {endpoint} from cache")
            import json
            return json.loads(cache_path.read_text())

        url = f"{self.BASE_URL}/{self.organism}/{endpoint}"
        logger.info(f"Fetching from {url}")

        try:
            response = self.session.get(url, params=params, timeout=60)
            response.raise_for_status()
            data = response.json()

            if use_cache:
                import json
                cache_path.write_text(json.dumps(data))

            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise RuntimeError(f"Failed to fetch data from Pathoplexus: {e}") from e

    def get_metadata(
        self,
        country: Optional[str] = None,
        admin1: Optional[str] = None,
        admin2: Optional[str] = None,
        city: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        serotype: Optional[str] = None,
        lineage: Optional[str] = None,
        genotype: Optional[str] = None,
        clade: Optional[str] = None,
        data_use_terms: Optional[str] = None,
        host: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        fields: Optional[List[str]] = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Get sample metadata.

        Args:
            country: Country name (e.g., 'Brazil')
            admin1: State/Province (e.g., 'Sao Paulo')
            admin2: Municipality/County
            city: City
            date_from: Collection date start (YYYY-MM-DD)
            date_to: Collection date end (YYYY-MM-DD)
            serotype: Serotype (for dengue: DENV-1, DENV-2, DENV-3, DENV-4)
            lineage: Lineage (e.g., for mpox)
            genotype: Genotype
            clade: Clade
            data_use_terms: 'OPEN' or 'RESTRICTED'
            host: Host species (e.g., 'Homo sapiens')
            limit: Maximum number of results
            offset: Offset for pagination
            fields: Specific fields to return
            use_cache: Whether to use cached data

        Returns:
            DataFrame with metadata
        """
        params = {}

        # Geographic filters
        if country:
            params['geoLocCountry'] = country
        if admin1:
            params['geoLocAdmin1'] = admin1
        if admin2:
            params['geoLocAdmin2'] = admin2
        if city:
            params['geoLocCity'] = city

        # Date filters - LAPIS uses sampleCollectionDateRangeLower/Upper
        # for date range filtering on aggregated and details endpoints
        date_filters = {}
        if date_from:
            date_filters['sampleCollectionDateRangeLowerFrom'] = date_from
        if date_to:
            date_filters['sampleCollectionDateRangeLowerTo'] = date_to

        # Pathogen-specific filters
        if serotype:
            params['serotype'] = serotype
        if lineage:
            params['lineage'] = lineage
        if genotype:
            params['genotype'] = genotype
        if clade:
            params['clade'] = clade

        # Other filters
        if data_use_terms:
            params['dataUseTerms'] = data_use_terms
        if host:
            params['hostNameScientific'] = host
        if limit:
            params['limit'] = limit
        if offset:
            params['offset'] = offset
        if fields:
            params['fields'] = ','.join(fields)

        try:
            data = self._make_request('sample/details', {**params, **date_filters}, use_cache)
            df = pd.DataFrame(data.get('data', []))
        except RuntimeError as e:
            if date_filters and '400' in str(e):
                logger.warning("Date filtering failed on API, fetching all data and filtering locally")
                data = self._make_request('sample/details', params, use_cache)
                df = pd.DataFrame(data.get('data', []))
                if not df.empty and 'sampleCollectionDateRangeLower' in df.columns:
                    df['sampleCollectionDateRangeLower'] = pd.to_datetime(
                        df['sampleCollectionDateRangeLower'], errors='coerce'
                    )
                    if date_from:
                        df = df[df['sampleCollectionDateRangeLower'] >= pd.Timestamp(date_from)]
                    if date_to:
                        df = df[df['sampleCollectionDateRangeLower'] <= pd.Timestamp(date_to)]
            else:
                raise

        return df

    def count_sequences(
        self,
        country: Optional[str] = None,
        admin1: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        serotype: Optional[str] = None,
        lineage: Optional[str] = None,
        data_use_terms: Optional[str] = None,
        **kwargs
    ) -> int:
        """
        Count sequences matching criteria.

        Args:
            country: Country name
            admin1: State/Province
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            serotype: Serotype (for dengue)
            lineage: Lineage
            data_use_terms: 'OPEN' or 'RESTRICTED'
            **kwargs: Additional filters

        Returns:
            Number of matching sequences
        """
        params = {}
        date_filters = {}

        if country:
            params['geoLocCountry'] = country
        if admin1:
            params['geoLocAdmin1'] = admin1
        if date_from:
            date_filters['sampleCollectionDateRangeLowerFrom'] = date_from
        if date_to:
            date_filters['sampleCollectionDateRangeLowerTo'] = date_to
        if serotype:
            params['serotype'] = serotype
        if lineage:
            params['lineage'] = lineage
        if data_use_terms:
            params['dataUseTerms'] = data_use_terms

        params.update(kwargs)

        # Try with date filters first, fallback without if API rejects
        try:
            data = self._make_request('sample/aggregated', {**params, **date_filters}, use_cache=False)
            return data.get('data', [{}])[0].get('count', 0)
        except RuntimeError as e:
            if date_filters and '400' in str(e):
                logger.warning("Date filtering not supported for aggregated endpoint, using details endpoint")
                metadata = self.get_metadata(
                    country=country,
                    admin1=admin1,
                    date_from=date_from,
                    date_to=date_to,
                    serotype=serotype,
                    lineage=lineage,
                    data_use_terms=data_use_terms,
                    **kwargs
                )
                return len(metadata)
            else:
                raise

    def get_sequences(
        self,
        country: Optional[str] = None,
        aligned: bool = True,
        download: bool = False,
        output_file: Optional[str] = None,
        **filters
    ) -> Union[str, pd.DataFrame]:
        """
        Get nucleotide sequences.

        Args:
            country: Country name
            aligned: If True, returns aligned sequences
            download: If True, saves to file
            output_file: Output filename for download
            **filters: Additional filters

        Returns:
            Sequences as string (FASTA) or DataFrame if download=False
        """
        endpoint = (
            'sample/alignedNucleotideSequences'
            if aligned
            else 'sample/unalignedNucleotideSequences'
        )

        params = {}
        if country:
            params['geoLocCountry'] = country
        params.update(filters)

        url = f"{self.BASE_URL}/{self.organism}/{endpoint}"
        logger.info(f"Fetching sequences from {url}")

        try:
            response = self.session.get(url, params=params, timeout=120)
            response.raise_for_status()

            sequences = response.text

            if download and output_file:
                Path(output_file).write_text(sequences)
                logger.info(f"Sequences saved to {output_file}")

            return sequences

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch sequences: {e}")
            raise

    def get_mutations(
        self,
        mutation_type: str = 'nucleotide',
        min_proportion: Optional[float] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
        **filters
    ) -> pd.DataFrame:
        """
        Get mutations data.

        Args:
            mutation_type: 'nucleotide' or 'aminoAcid'
            min_proportion: Minimum proportion (0-1)
            order_by: Field to order by
            limit: Maximum results
            **filters: Additional filters

        Returns:
            DataFrame with mutations
        """
        if mutation_type not in ['nucleotide', 'aminoAcid']:
            raise ValueError("mutation_type must be 'nucleotide' or 'aminoAcid'")

        endpoint = f"sample/{mutation_type}Mutations"
        params = {}

        if min_proportion is not None:
            params['minProportion'] = min_proportion
        if order_by:
            params['orderBy'] = order_by
        if limit:
            params['limit'] = limit

        params.update(filters)

        data = self._make_request(endpoint, params, use_cache=False)
        return pd.DataFrame(data.get('data', []))

    def get_insertions(
        self,
        insertion_type: str = 'nucleotide',
        **filters
    ) -> pd.DataFrame:
        """
        Get insertions data.

        Args:
            insertion_type: 'nucleotide' or 'aminoAcid'
            **filters: Additional filters

        Returns:
            DataFrame with insertions
        """
        if insertion_type not in ['nucleotide', 'aminoAcid']:
            raise ValueError("insertion_type must be 'nucleotide' or 'aminoAcid'")

        endpoint = f"sample/{insertion_type}Insertions"
        data = self._make_request(endpoint, filters, use_cache=False)
        return pd.DataFrame(data.get('data', []))

    def get_brazil_summary(
        self,
        year: int = 2024,
        by_serotype: bool = True,
        by_state: bool = True,
    ) -> Dict:
        """
        Get summary of data for Brazil.

        Convenience method for common use case.

        Args:
            year: Year of analysis
            by_serotype: Include breakdown by serotype (for dengue)
            by_state: Include breakdown by state

        Returns:
            Dictionary with summary statistics
        """
        date_from = f"{year}-01-01"
        date_to = f"{year}-12-31"

        summary = {
            'organism': self.ORGANISMS[self.organism],
            'year': year,
            'total_sequences': 0,
            'by_serotype': {},
            'by_state': {},
            'date_range': {'from': date_from, 'to': date_to},
        }

        # Total count
        try:
            summary['total_sequences'] = self.count_sequences(
                country='Brazil',
                date_from=date_from,
                date_to=date_to,
            )
        except Exception as e:
            logger.error(f"Failed to get total count: {e}")

        # By serotype (only for dengue)
        if by_serotype and self.organism == 'dengue':
            for serotype in ['DENV-1', 'DENV-2', 'DENV-3', 'DENV-4']:
                try:
                    count = self.count_sequences(
                        country='Brazil',
                        serotype=serotype,
                        date_from=date_from,
                        date_to=date_to,
                    )
                    if count > 0:
                        summary['by_serotype'][serotype] = count
                except Exception as e:
                    logger.error(f"Failed to get count for {serotype}: {e}")

        # By state
        if by_state:
            try:
                metadata = self.get_metadata(
                    country='Brazil',
                    date_from=date_from,
                    date_to=date_to,
                    limit=10000,
                    fields=['geoLocAdmin1'],
                )
                if 'geoLocAdmin1' in metadata.columns:
                    state_counts = metadata['geoLocAdmin1'].value_counts().to_dict()
                    summary['by_state'] = state_counts
            except Exception as e:
                logger.error(f"Failed to get state breakdown: {e}")

        return summary

    def list_organisms(self) -> pd.DataFrame:
        """
        List all supported organisms.

        Returns:
            DataFrame with organism codes and names
        """
        return pd.DataFrame(
            [{'code': k, 'name': v} for k, v in self.ORGANISMS.items()]
        )

    def clear_cache(self):
        """Clear all cached data for this organism."""
        import shutil
        cache_path = self.cache_dir / f"{self.organism}_*"
        for file in self.cache_dir.glob(f"{self.organism}_*"):
            file.unlink()
        logger.info(f"Cache cleared for {self.organism}")


# ── Convenience Functions ────────────────────────────────────────────────────


def get_dengue_brazil(
    year: int = 2024,
    state: Optional[str] = None,
    serotype: Optional[str] = None,
) -> pd.DataFrame:
    """
    Convenience function to get dengue metadata for Brazil.

    Args:
        year: Year of data
        state: Brazilian state (e.g., 'Sao Paulo')
        serotype: Dengue serotype (DENV-1, DENV-2, DENV-3, DENV-4)

    Returns:
        DataFrame with dengue metadata
    """
    ppx = PathoplexusAccessor('dengue')
    return ppx.get_metadata(
        country='Brazil',
        admin1=state,
        serotype=serotype,
        date_from=f"{year}-01-01",
        date_to=f"{year}-12-31",
    )


def get_mpox_brazil(year: int = 2024) -> pd.DataFrame:
    """
    Convenience function to get mpox metadata for Brazil.

    Args:
        year: Year of data

    Returns:
        DataFrame with mpox metadata
    """
    ppx = PathoplexusAccessor('mpox')
    return ppx.get_metadata(
        country='Brazil',
        date_from=f"{year}-01-01",
        date_to=f"{year}-12-31",
    )


def get_measles_brazil(year: int = 2024) -> pd.DataFrame:
    """
    Convenience function to get measles metadata for Brazil.

    Args:
        year: Year of data

    Returns:
        DataFrame with measles metadata
    """
    ppx = PathoplexusAccessor('measles')
    return ppx.get_metadata(
        country='Brazil',
        date_from=f"{year}-01-01",
        date_to=f"{year}-12-31",
    )


# ── Main ─────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    # Example usage
    print("Pathoplexus Accessor Demo")
    print("=" * 60)

    # List supported organisms
    ppx = PathoplexusAccessor('dengue')
    print("\nSupported Organisms:")
    print(ppx.list_organisms().to_string(index=False))

    # Get Brazil summary for dengue
    print("\n" + "=" * 60)
    print("Dengue in Brazil (2024):")
    try:
        summary = ppx.get_brazil_summary(year=2024)
        print(f"Total sequences: {summary['total_sequences']}")
        print(f"By serotype: {summary['by_serotype']}")
        print(f"By state (top 5): {dict(list(summary['by_state'].items())[:5])}")
    except Exception as e:
        print(f"Error: {e}")

    # Get sample metadata
    print("\n" + "=" * 60)
    print("Sample metadata (first 5):")
    try:
        metadata = ppx.get_metadata(
            country='Brazil',
            date_from='2024-01-01',
            limit=5,
        )
        print(metadata[['accession', 'geoLocAdmin1', 'sampleCollectionDateRangeLower', 'serotype']].to_string())
    except Exception as e:
        print(f"Error: {e}")
