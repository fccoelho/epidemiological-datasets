"""Tests for the plugin registry."""

import pytest

from epidatasets._base import BaseAccessor
from epidatasets._registry import _register_builtin, get_source, list_sources


class TestListSources:
    def test_returns_dict(self):
        sources = list_sources()
        assert isinstance(sources, dict)

    def test_known_sources_present(self):
        sources = list_sources()
        for name in ["who", "paho", "owid", "africa_cdc", "eurostat"]:
            assert name in sources, f"{name} not in registry"

    def test_source_metadata_keys(self):
        sources = list_sources()
        for name, meta in sources.items():
            assert "name" in meta
            assert "description" in meta
            assert "url" in meta
            assert "class" in meta


class TestGetSource:
    def test_get_known_source(self):
        accessor = get_source("paho")
        assert isinstance(accessor, BaseAccessor)

    def test_get_unknown_source_raises(self):
        with pytest.raises(KeyError, match="nonexistent"):
            get_source("nonexistent")

    def test_get_source_returns_correct_class(self):
        from epidatasets.sources.who_ghoclient import WHOAccessor
        accessor = get_source("who")
        assert isinstance(accessor, WHOAccessor)


class TestManualRegistration:
    def test_register_builtin(self):
        class FakeAccessor(BaseAccessor):
            source_name = "fake_test"
            source_description = "Fake"
            source_url = "https://example.com"

            def list_countries(self):
                import pandas as pd
                return pd.DataFrame()

        _register_builtin(FakeAccessor)
        source = get_source("fake_test")
        assert isinstance(source, FakeAccessor)
