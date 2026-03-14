"""
Epidemiological data accessors.

This package provides standardized access to various epidemiological datasets
from around the world.
"""

from .who import WHOAccessor
# from .cdc import CDCAccessor
# from .ecdc import ECDCAccessor
# from .owid import OWIDAccessor
# from .sinan import SINANAccessor
# from .datasus import DataSUSAccessor

__all__ = [
    "WHOAccessor",
    # "CDCAccessor",
    # "ECDCAccessor",
    # "OWIDAccessor",
    # "SINANAccessor",
    # "DataSUSAccessor",
]

__version__ = "0.1.0"
