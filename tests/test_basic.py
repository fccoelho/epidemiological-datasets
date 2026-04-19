"""Basic repository structure tests."""

from pathlib import Path

import pytest


class TestRepositoryStructure:
    def test_package_directory(self):
        pkg = Path(__file__).parent.parent / "src" / "epidatasets"
        assert pkg.exists()

    def test_sources_directory(self):
        sources = Path(__file__).parent.parent / "src" / "epidatasets" / "sources"
        assert sources.exists()

    def test_accessors_have_files(self):
        sources = Path(__file__).parent.parent / "src" / "epidatasets" / "sources"
        py_files = list(sources.glob("*.py"))
        assert len(py_files) > 10

    def test_readme_exists(self):
        readme = Path(__file__).parent.parent / "README.md"
        assert readme.exists()

    def test_pyproject_exists(self):
        pyproject = Path(__file__).parent.parent / "pyproject.toml"
        assert pyproject.exists()
