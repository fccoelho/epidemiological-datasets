"""Tests for package initialization and version."""

import epidatasets


def test_version():
    assert epidatasets.__version__ == "0.2.0"


def test_author():
    assert epidatasets.__author__ == "Flávio Codeço Coelho"


def test_public_api():
    assert hasattr(epidatasets, "get_source")
    assert hasattr(epidatasets, "list_sources")
    assert hasattr(epidatasets, "reload_registry")
