"""Utility modules for epidatasets."""

from epidatasets.utils.cache import CacheManager
from epidatasets.utils.rate_limit import RateLimiter
from epidatasets.utils.geo import standardize_country_code
from epidatasets.utils.validation import validate_year_range
from epidatasets.utils.io import merge_dataframes, save_to_multiple_formats
from epidatasets.utils.pdf import ExtractedTable, PDFMetadata, PDFParser

__all__ = [
    "CacheManager",
    "ExtractedTable",
    "PDFMetadata",
    "PDFParser",
    "RateLimiter",
    "standardize_country_code",
    "validate_year_range",
    "merge_dataframes",
    "save_to_multiple_formats",
]
