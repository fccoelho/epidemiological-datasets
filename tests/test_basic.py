#!/usr/bin/env python3
"""
Basic tests that don't require external dependencies.
These should always pass and run quickly.
"""

from pathlib import Path


class TestRepositoryStructure:
    """Test repository structure and file organization."""
    
    def test_scripts_directory_exists(self):
        """Check that scripts directory exists."""
        repo_root = Path(__file__).parent.parent
        scripts_dir = repo_root / "scripts" / "accessors"
        assert scripts_dir.exists(), f"Scripts directory not found: {scripts_dir}"
    
    def test_accessors_directory_has_files(self):
        """Check that accessors directory contains Python files."""
        repo_root = Path(__file__).parent.parent
        accessors_dir = repo_root / "scripts" / "accessors"
        
        if accessors_dir.exists():
            py_files = list(accessors_dir.glob("*.py"))
            assert len(py_files) > 0, "No Python files in accessors directory"
    
    def test_readme_exists(self):
        """Check that README.md exists."""
        repo_root = Path(__file__).parent.parent
        readme = repo_root / "README.md"
        assert readme.exists(), "README.md not found"
    
    def test_pyproject_exists(self):
        """Check that pyproject.toml exists."""
        repo_root = Path(__file__).parent.parent
        pyproject = repo_root / "pyproject.toml"
        assert pyproject.exists(), "pyproject.toml not found"


class TestImports:
    """Test that basic imports work."""
    
    def test_pandas_import(self):
        """Check that pandas can be imported."""
        import pandas as pd
        assert pd is not None
    
    def test_numpy_import(self):
        """Check that numpy can be imported."""
        import numpy as np
        assert np is not None
    
    def test_requests_import(self):
        """Check that requests can be imported."""
        try:
            import requests
            assert requests is not None
        except ImportError:
            pytest.skip("requests not installed")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
