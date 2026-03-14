"""
Data source accessors for epidemiological datasets.

This module provides unified interfaces to various health data sources:
- PySUS: Brazilian health data (DATASUS)
- WHO: World Health Organization Global Health Observatory
- WorldBank: World Bank health indicators
- ECDC: European Centre for Disease Prevention and Control
"""

# These imports will be available when sources are implemented
# from .pysus import PySUS
# from .who import WHO
# from .world_bank import WorldBank
# from .ecdc import ECDC

__all__ = [
    "PySUS",
    "WHO", 
    "WorldBank",
    "ECDC",
]
