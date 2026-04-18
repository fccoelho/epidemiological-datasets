"""
InfoDengue API Accessor (via Mosqlimate)

Provides access to epidemiological data from the InfoDengue project,
which monitors dengue, chikungunya, and Zika cases in Brazil.

Data Source: https://info.dengue.mat.br/
API: https://api.mosqlimate.org/
Documentation: https://api.mosqlimate.org/docs/

Requires API key for access.

Author: Flávio Codeço Coelho
License: MIT
"""

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Union

import pandas as pd
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class InfoDengueAPI:
    """
    Accessor for InfoDengue data via Mosqlimate API.
    
    Provides access to epidemiological surveillance data for
    arbovirus diseases in Brazil.
    
    Example:
        >>> from infodengue_api import InfoDengueAPI
        >>> api = InfoDengueAPI()  # Uses API key from environment
        >>> df = api.get_cases(disease='dengue', year=2024, uf='SP')
    """
    
    BASE_URL = "https://api.mosqlimate.org/api"
    
    # Supported diseases
    DISEASES = {
        'dengue': 'Dengue',
        'chikungunya': 'Chikungunya',
        'zika': 'Zika',
    }
    
    # Brazilian states mapping
    STATES = {
        'AC': 'Acre', 'AL': 'Alagoas', 'AP': 'Amapá', 'AM': 'Amazonas',
        'BA': 'Bahia', 'CE': 'Ceará', 'DF': 'Distrito Federal', 'ES': 'Espírito Santo',
        'GO': 'Goiás', 'MA': 'Maranhão', 'MT': 'Mato Grosso', 'MS': 'Mato Grosso do Sul',
        'MG': 'Minas Gerais', 'PA': 'Pará', 'PB': 'Paraíba', 'PR': 'Paraná',
        'PE': 'Pernambuco', 'PI': 'Piauí', 'RJ': 'Rio de Janeiro', 'RN': 'Rio Grande do Norte',
        'RS': 'Rio Grande do Sul', 'RO': 'Rondônia', 'RR': 'Roraima', 'SC': 'Santa Catarina',
        'SP': 'São Paulo', 'SE': 'Sergipe', 'TO': 'Tocantins',
    }
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        cache_dir: Optional[str] = None,
        cache_ttl: int = 24,
    ):
        """
        Initialize InfoDengue API accessor.
        
        Args:
            api_key: Mosqlimate API key. If None, tries to load from
                    environment variable MOSQLIMATE_API_KEY or config file.
            cache_dir: Directory to cache downloaded data
            cache_ttl: Cache time-to-live in hours (default: 24)
        """
        # Get API key
        self.api_key = api_key or self._load_api_key()
        if not self.api_key:
            raise ValueError(
                "API key is required. Set MOSQLIMATE_API_KEY environment variable "
                "or provide api_key parameter."
            )
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'epidemiological-datasets/1.0',
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.api_key}',
        })
        
        # Setup caching
        self.cache_dir = (
            Path(cache_dir)
            if cache_dir
            else Path.home() / ".cache" / "epi_data" / "infodengue"
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_ttl = timedelta(hours=cache_ttl)
        
        logger.info("Initialized InfoDengue API accessor")
    
    def _load_api_key(self) -> Optional[str]:
        """Load API key from environment or config file."""
        # Try environment variable first
        api_key = os.getenv('MOSQLIMATE_API_KEY')
        if api_key:
            return api_key
        
        # Try config file
        config_paths = [
            Path.home() / ".nanobot" / "config" / "mosqlimate.env",
            Path.home() / ".config" / "epi_data" / "mosqlimate.env",
            Path(".env"),
        ]
        
        for config_path in config_paths:
            if config_path.exists():
                try:
                    with open(config_path) as f:
                        for line in f:
                            if line.startswith('MOSQLIMATE_API_KEY='):
                                return line.split('=', 1)[1].strip()
                except Exception as e:
                    logger.warning(f"Failed to read config from {config_path}: {e}")
        
        return None
    
    def _get_cache_path(self, filename: str) -> Path:
        """Return the path to a cache file."""
        safe_filename = filename.replace('/', '_').replace('\\', '_')
        return self.cache_dir / safe_filename
    
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
            endpoint: API endpoint
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
        
        url = f"{self.BASE_URL}/{endpoint}"
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
            raise RuntimeError(f"Failed to fetch data from InfoDengue API: {e}") from e
    
    def get_cases(
        self,
        disease: str = 'dengue',
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        uf: Optional[str] = None,
        geocode: Optional[int] = None,
        page: int = 1,
        per_page: int = 100,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Get disease case data from InfoDengue.
        
        Args:
            disease: Disease code ('dengue', 'chikungunya', 'zika')
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            uf: Brazilian state abbreviation (e.g., 'SP', 'RJ')
            geocode: IBGE municipality code
            page: Page number for pagination
            per_page: Items per page (max 100)
            use_cache: Whether to use cached data
            
        Returns:
            DataFrame with case data
        """
        if disease not in self.DISEASES:
            raise ValueError(
                f"Disease '{disease}' not supported. "
                f"Choose from: {list(self.DISEASES.keys())}"
            )
        
        params = {
            'disease': disease,
            'page': page,
            'per_page': min(per_page, 100),
        }
        
        if start_date:
            params['start'] = start_date
        if end_date:
            params['end'] = end_date
        if uf:
            params['uf'] = uf.upper()
        if geocode:
            params['geocode'] = geocode
        
        data = self._make_request('datastore/infodengue/', params, use_cache)
        
        # Extract results
        if 'items' in data:
            return pd.DataFrame(data['items'])
        elif 'results' in data:
            return pd.DataFrame(data['results'])
        else:
            return pd.DataFrame(data) if isinstance(data, list) else pd.DataFrame()
    
    def get_cases_brazil(
        self,
        disease: str = 'dengue',
        year: int = 2024,
    ) -> pd.DataFrame:
        """
        Get aggregated case data for Brazil.
        
        Convenience method to fetch all data for a given year.
        
        Args:
            disease: Disease code
            year: Year to fetch
            
        Returns:
            DataFrame with aggregated case data
        """
        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"
        
        all_data = []
        page = 1
        
        while True:
            logger.info(f"Fetching page {page}...")
            df = self.get_cases(
                disease=disease,
                start_date=start_date,
                end_date=end_date,
                page=page,
                per_page=100,
            )
            
            if df.empty:
                break
            
            all_data.append(df)
            
            # Check if we got less than max results
            if len(df) < 100:
                break
            
            page += 1
            
            # Safety limit
            if page > 100:
                logger.warning("Reached maximum page limit")
                break
        
        if all_data:
            combined = pd.concat(all_data, ignore_index=True)
            logger.info(f"Fetched {len(combined)} total records")
            return combined
        
        return pd.DataFrame()
    
    def get_states(self) -> pd.DataFrame:
        """
        Get list of Brazilian states.
        
        Returns:
            DataFrame with state codes and names
        """
        return pd.DataFrame([
            {'code': k, 'name': v} for k, v in self.STATES.items()
        ])
    
    def get_diseases(self) -> pd.DataFrame:
        """
        Get list of supported diseases.
        
        Returns:
            DataFrame with disease codes and names
        """
        return pd.DataFrame([
            {'code': k, 'name': v} for k, v in self.DISEASES.items()
        ])
    
    def clear_cache(self):
        """Clear all cached data."""
        import shutil
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Cache cleared")


# ── Convenience Functions ────────────────────────────────────────────────────


def get_dengue_cases(
    uf: Optional[str] = None,
    year: int = 2024,
    api_key: Optional[str] = None,
) -> pd.DataFrame:
    """
    Convenience function to get dengue cases.
    
    Args:
        uf: State abbreviation (e.g., 'SP')
        year: Year to fetch
        api_key: API key (optional)
        
    Returns:
        DataFrame with dengue cases
    """
    api = InfoDengueAPI(api_key=api_key)
    return api.get_cases_brazil(disease='dengue', year=year)


# ── Main ─────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    print("InfoDengue API Accessor Demo")
    print("=" * 60)
    
    try:
        # Initialize API
        api = InfoDengueAPI()
        print("✅ API initialized successfully")
        
        # List supported diseases
        print("\nSupported diseases:")
        print(api.get_diseases().to_string(index=False))
        
        # Try to fetch some data
        print("\nFetching sample dengue data for 2024...")
        df = api.get_cases(disease='dengue', start_date='2024-01-01', end_date='2024-01-31', per_page=10)
        
        if not df.empty:
            print(f"✅ Fetched {len(df)} records")
            print(f"\nColumns: {', '.join(df.columns.tolist()[:10])}")
            print("\nFirst few rows:")
            print(df.head(3).to_string())
        else:
            print("⚠️ No data returned (API may require additional permissions)")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
