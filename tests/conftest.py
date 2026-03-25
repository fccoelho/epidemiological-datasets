#!/usr/bin/env python3
"""Pytest configuration for epidemiological-datasets tests."""

import os

import pytest


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "external_api: marks tests that call external APIs"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection."""
    # Check if external API tests should be skipped
    skip_external = (
        config.getoption("-m") == "not external_api" or
        os.environ.get("SKIP_EXTERNAL_TESTS", "false").lower() == "true"
    )

    if skip_external:
        skip_marker = pytest.mark.skip(reason="External API tests disabled")
        for item in items:
            if "external_api" in item.keywords:
                item.add_marker(skip_marker)


# Fixture for shared test resources
@pytest.fixture(scope="session")
def test_cache_dir(tmp_path_factory):
    """Provide a temporary cache directory for tests."""
    return tmp_path_factory.mktemp("cache")


@pytest.fixture(scope="session")
def sample_data_dir():
    """Provide path to sample data directory."""
    from pathlib import Path
    return Path(__file__).parent / "fixtures"
