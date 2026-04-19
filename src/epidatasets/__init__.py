"""
Epidatasets – Python access to epidemiological datasets worldwide.

A curated library of openly accessible epidemiological data sources
with a unified Python interface.  Sources are discovered at runtime via
a pluggable registry.

Example
-------
>>> from epidatasets import get_source, list_sources
>>> list_sources()
{'who': {'name': 'who', 'description': '...', ...}, ...}
>>> who = get_source("who")
>>> who.list_countries()
"""

__version__ = "0.2.0"
__author__ = "Flávio Codeço Coelho"
__email__ = "fccoelho@gmail.com"

from epidatasets._registry import get_source, list_sources, reload_registry

__all__ = [
    "get_source",
    "list_sources",
    "reload_registry",
]
