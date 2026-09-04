"""Tests for package initialization and version."""

import re

import epidatasets


def test_version():
    # __version__ must be a non-empty semver-style string kept in sync
    # with pyproject.toml (checked in CI by hatchling itself).
    assert isinstance(epidatasets.__version__, str)
    assert re.match(r"^\d+\.\d+", epidatasets.__version__)


def test_author():
    assert epidatasets.__author__ == "Flávio Codeço Coelho"


def test_public_api():
    assert hasattr(epidatasets, "get_source")
    assert hasattr(epidatasets, "list_sources")
    assert hasattr(epidatasets, "reload_registry")
