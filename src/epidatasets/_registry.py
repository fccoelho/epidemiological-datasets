"""Plugin registry for epidemiological data sources.

Sources register themselves via ``pyproject.toml`` entry-points under the
``epidatasets.sources`` group.  This module provides helpers to discover
and instantiate them at runtime.
"""

from __future__ import annotations

import importlib
import logging
from importlib.metadata import entry_points
from typing import Any

from epidatasets._base import BaseAccessor

logger = logging.getLogger(__name__)

_EP_GROUP = "epidatasets.sources"

_cache: dict[str, type[BaseAccessor]] | None = None


def _load_entry_points() -> dict[str, type[BaseAccessor]]:
    """Load all registered source entry-points."""
    global _cache
    if _cache is not None:
        return _cache

    eps = entry_points()
    if hasattr(eps, "select"):
        group = eps.select(group=_EP_GROUP)
    else:
        group = eps.get(_EP_GROUP, [])

    result: dict[str, type[BaseAccessor]] = {}
    for ep in group:
        try:
            cls = ep.load()
            result[ep.name] = cls
        except Exception as exc:
            logger.warning("Failed to load entry-point %s: %s", ep.name, exc)

    _cache = result
    return result


def list_sources() -> dict[str, dict[str, str]]:
    """Return metadata for every registered data source.

    Returns
    -------
    dict[str, dict[str, str]]
        Mapping of source name to its metadata dict.
    """
    sources: dict[str, dict[str, str]] = {}
    for name, cls in _load_entry_points().items():
        if cls.source_name:
            sources[name] = {
                "name": cls.source_name,
                "description": cls.source_description,
                "url": cls.source_url,
                "class": cls.__name__,
            }
        else:
            sources[name] = {
                "name": name,
                "description": cls.__doc__ or "",
                "url": "",
                "class": cls.__name__,
            }
    return sources


def get_source(name: str, **kwargs: Any) -> BaseAccessor:
    """Instantiate a data source by its registered name.

    Parameters
    ----------
    name : str
        The source identifier (e.g. ``"who"``, ``"paho"``).
    **kwargs
        Forwarded to the accessor constructor.

    Returns
    -------
    BaseAccessor
        An instance of the requested source.

    Raises
    ------
    KeyError
        If no source is registered under *name*.
    """
    registry = _load_entry_points()
    if name not in registry:
        available = ", ".join(sorted(registry)) or "(none)"
        raise KeyError(
            f"No source registered as {name!r}. Available: {available}"
        )
    return registry[name](**kwargs)


def _register_builtin(cls: type[BaseAccessor]) -> None:
    """Manually register a builtin source class (used before packaging)."""
    global _cache
    if _cache is None:
        _cache = {}
    key = cls.source_name or cls.__name__.replace("Accessor", "").replace(
        "Accessor", ""
    ).lower()
    _cache[key] = cls


def reload_registry() -> None:
    """Force a reload of the entry-point cache."""
    global _cache
    _cache = None
    _load_entry_points()
