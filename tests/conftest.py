"""Pytest configuration for epidatasets tests."""

import os

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "external_api: marks tests that call external APIs"
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip external API tests when disabled."""
    skip_external = (
        config.getoption("-m") == "not external_api"
        or os.environ.get("SKIP_EXTERNAL_TESTS", "false").lower() == "true"
    )

    if skip_external:
        skip_marker = pytest.mark.skip(reason="External API tests disabled")
        for item in items:
            if "external_api" in item.keywords:
                item.add_marker(skip_marker)


def requires_external_api(func):
    """Mark test as external API and skip when disabled."""
    func = pytest.mark.external_api(func)
    return pytest.mark.skipif(
        os.getenv("SKIP_EXTERNAL_TESTS", "false").lower() == "true",
        reason="External API tests disabled",
    )(func)


@pytest.fixture(scope="session")
def test_cache_dir(tmp_path_factory):
    """Provide a temporary cache directory for tests."""
    return tmp_path_factory.mktemp("cache")
