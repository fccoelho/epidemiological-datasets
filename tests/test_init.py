"""Tests for package initialization."""

import epi_data


def test_version():
    """Test that version is defined."""
    assert epi_data.__version__ == "0.1.0"


def test_author():
    """Test that author is defined."""
    assert epi_data.__author__ == "Flávio Codeço Coelho"


def test_email():
    """Test that email is defined."""
    assert epi_data.__email__ == "fccoelho@gmail.com"
