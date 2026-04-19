"""File-based cache for API responses."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class CacheManager:
    """Simple file-based cache for API responses.

    Parameters
    ----------
    cache_dir : str
        Path to the directory where cached files are stored.
    """

    def __init__(self, cache_dir: str = ".cache") -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

    def _get_cache_path(self, key: str) -> Path:
        safe_key = key.replace("/", "_").replace(":", "_")
        return self.cache_dir / f"{safe_key}.json"

    def get(self, key: str, max_age_hours: int = 24) -> Optional[dict[str, Any]]:
        """Retrieve cached data if it exists and is not expired.

        Parameters
        ----------
        key : str
            Cache key.
        max_age_hours : int
            Maximum age of cache in hours.

        Returns
        -------
        dict or None
            Cached data or ``None`` if missing / expired.
        """
        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            return None

        mod_time = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age_hours = (datetime.now() - mod_time).total_seconds() / 3600

        if age_hours > max_age_hours:
            return None

        with open(cache_path) as f:
            return json.load(f)

    def set(self, key: str, data: dict[str, Any]) -> None:
        """Store data in cache.

        Parameters
        ----------
        key : str
            Cache key.
        data : dict
            Data to cache.
        """
        cache_path = self._get_cache_path(key)
        with open(cache_path, "w") as f:
            json.dump(data, f, indent=2)

    def clear(self) -> None:
        """Clear all cached data."""
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()
