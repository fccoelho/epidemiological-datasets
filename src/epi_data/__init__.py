"""
Epidemiological Datasets Repository.

A curated collection of openly accessible epidemiological datasets
with Python access scripts.

Example
-------
    >>> from epi_data.sources import PySUS, WHO
    >>> pysus = PySUS()
    >>> data = pysus.fetch_data(disease='dengue', year=2023)
"""

__version__ = "0.1.0"
__author__ = "Flávio Codeço Coelho"
__email__ = "fccoelho@gmail.com"

# Import main classes for convenience
# These will be available as: from epi_data import PySUS
try:
    from epi_data.sources.ecdc import ECDC
    from epi_data.sources.pysus import PySUS
    from epi_data.sources.who import WHO
    from epi_data.sources.world_bank import WorldBank
except ImportError:
    # Sources may not be fully implemented yet
    pass

__all__ = [
    "PySUS",
    "WHO",
    "WorldBank",
    "ECDC",
]
