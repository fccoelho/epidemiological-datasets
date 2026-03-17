"""Pytest configuration and fixtures."""

import pandas as pd
import pytest


@pytest.fixture
def sample_dataframe():
    """Return a sample DataFrame for testing."""
    return pd.DataFrame(
        {
            "country": ["BRA", "USA", "IND"],
            "year": [2023, 2023, 2023],
            "value": [100, 200, 300],
        }
    )


@pytest.fixture
def mock_api_response():
    """Return a mock API response."""
    return {
        "data": [
            {"country": "BRA", "year": 2023, "value": 100},
            {"country": "USA", "year": 2023, "value": 200},
        ]
    }
