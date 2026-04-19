"""Validation helpers for epidemiological data queries."""

from __future__ import annotations

from datetime import datetime


def validate_year_range(start_year: int, end_year: int) -> None:
    """Validate a year range for data queries.

    Parameters
    ----------
    start_year : int
        Start year.
    end_year : int
        End year.

    Raises
    ------
    ValueError
        If the year range is invalid.
    """
    current_year = datetime.now().year

    if start_year > end_year:
        raise ValueError(f"Start year {start_year} must be <= end year {end_year}")

    if end_year > current_year + 1:
        raise ValueError(f"End year {end_year} cannot be > {current_year + 1}")

    if start_year < 1900:
        raise ValueError(f"Start year {start_year} seems too early")
