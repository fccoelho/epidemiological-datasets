"""Tests for the shared PDFParser utility."""

from pathlib import Path

import pandas as pd
import pytest

from epidatasets.utils.pdf import ExtractedTable, PDFMetadata, PDFParser

FIXTURES = Path(__file__).parent / "fixtures"
PAKISTAN_PDF = FIXTURES / "pakistan_nih" / "Weekly_Report-51-2024.pdf"
OMAN_PDF = FIXTURES / "oman_moh" / "annual_health_report_2023.pdf"


# ------------------------------------------------------------------
# Static methods (no fixtures needed)
# ------------------------------------------------------------------


class TestCleanCell:
    def test_none(self):
        assert PDFParser.clean_cell(None) is None

    def test_whitespace_only(self):
        assert PDFParser.clean_cell("   ") is None

    def test_normalizes_inner_whitespace(self):
        assert PDFParser.clean_cell("  hello   world  ") == "hello world"

    def test_strips(self):
        assert PDFParser.clean_cell("  abc  ") == "abc"

    def test_number_string(self):
        assert PDFParser.clean_cell("123") == "123"


class TestParseNumeric:
    def test_none(self):
        assert PDFParser.parse_numeric(None) is None

    def test_empty(self):
        assert PDFParser.parse_numeric("") is None

    def test_dash(self):
        assert PDFParser.parse_numeric("-") is None

    def test_na(self):
        assert PDFParser.parse_numeric("N/A") is None

    def test_nr(self):
        assert PDFParser.parse_numeric("NR") is None

    def test_integer(self):
        assert PDFParser.parse_numeric("42") == 42

    def test_float(self):
        assert PDFParser.parse_numeric("3.14") == 3.14

    def test_comma_separated(self):
        assert PDFParser.parse_numeric("1,234") == 1234

    def test_negative(self):
        assert PDFParser.parse_numeric("-5") == 5

    def test_parenthesized_negative(self):
        assert PDFParser.parse_numeric("(7)") == 7

    def test_default_value(self):
        assert PDFParser.parse_numeric("abc", default=0) == 0

    def test_ellipsis(self):
        assert PDFParser.parse_numeric("...") is None


class TestStripSpacerColumns:
    def test_empty(self):
        assert PDFParser.strip_spacer_columns([]) == []

    def test_removes_sparse_columns(self):
        table = [
            ["A", "", "1"],
            ["B", "", "2"],
            ["C", "", "3"],
            ["D", "", "4"],
        ]
        result = PDFParser.strip_spacer_columns(table)
        assert len(result[0]) == 2
        assert result[0][0] == "A"
        assert result[0][1] == "1"

    def test_keeps_valid_columns(self):
        table = [
            ["A", "X", "1"],
            ["B", "Y", "2"],
            ["C", "Z", "3"],
        ]
        result = PDFParser.strip_spacer_columns(table)
        assert len(result[0]) == 3


class TestMergeHeaderRows:
    def test_empty(self):
        assert PDFParser.merge_header_rows([]) == []

    def test_single_row(self):
        rows = [["A", "B", "C"]]
        assert PDFParser.merge_header_rows(rows) == ["A", "B", "C"]

    def test_multi_row(self):
        rows = [
            ["Province", "", "Cases"],
            ["", "District", ""],
        ]
        assert PDFParser.merge_header_rows(rows) == [
            "Province",
            "District",
            "Cases",
        ]


class TestFindCaptions:
    def test_no_captions(self):
        assert PDFParser.find_captions("No tables here") == []

    def test_single_caption(self):
        text = "Some text\nTable 1: Disease summary\nMore text"
        captions = PDFParser.find_captions(text)
        assert len(captions) == 1
        assert "Disease summary" in captions[0]

    def test_multiple_captions(self):
        text = "Table 1: First\nTable 2: Second\nTable 3: Third"
        captions = PDFParser.find_captions(text)
        assert len(captions) == 3


# ------------------------------------------------------------------
# Integration tests with real PDFs
# ------------------------------------------------------------------


@pytest.mark.skipif(not PAKISTAN_PDF.exists(), reason="Pakistan PDF fixture not found")
class TestExtractTextPakistan:
    def test_extracts_text(self):
        parser = PDFParser()
        text = parser.extract_text(PAKISTAN_PDF)
        assert len(text) > 100

    def test_specific_pages(self):
        parser = PDFParser()
        text = parser.extract_text(PAKISTAN_PDF, pages=[0])
        assert len(text) > 0


@pytest.mark.skipif(not PAKISTAN_PDF.exists(), reason="Pakistan PDF fixture not found")
class TestExtractTablesPakistan:
    def test_extracts_tables(self):
        parser = PDFParser()
        tables = parser.extract_tables(PAKISTAN_PDF)
        assert len(tables) > 0
        for t in tables:
            assert isinstance(t, ExtractedTable)
            assert isinstance(t.data, pd.DataFrame)
            assert t.page_number >= 1

    def test_table_has_data(self):
        parser = PDFParser()
        tables = parser.extract_tables(PAKISTAN_PDF)
        total_rows = sum(len(t.data) for t in tables)
        assert total_rows > 0


@pytest.mark.skipif(not OMAN_PDF.exists(), reason="Oman PDF fixture not found")
class TestExtractTextOman:
    def test_extracts_text(self):
        parser = PDFParser()
        text = parser.extract_text(OMAN_PDF)
        assert len(text) > 100


@pytest.mark.skipif(not OMAN_PDF.exists(), reason="Oman PDF fixture not found")
class TestExtractTablesOman:
    def test_returns_list(self):
        parser = PDFParser()
        tables = parser.extract_tables(OMAN_PDF)
        assert isinstance(tables, list)


class TestExtractMetadata:
    @pytest.mark.skipif(not PAKISTAN_PDF.exists(), reason="Pakistan PDF fixture not found")
    def test_metadata_pakistan(self):
        parser = PDFParser()
        meta = parser.extract_metadata(PAKISTAN_PDF, source_url="https://example.com")
        assert isinstance(meta, PDFMetadata)
        assert meta.page_count > 0
        assert meta.source_url == "https://example.com"


class TestPDFParserInit:
    def test_default_cache_dir(self):
        parser = PDFParser()
        assert parser.cache_dir.exists()

    def test_custom_cache_dir(self, tmp_path):
        parser = PDFParser(cache_dir=tmp_path / "pdf_cache")
        assert (tmp_path / "pdf_cache").exists()

    def test_session_headers(self):
        parser = PDFParser(user_agent="TestAgent/1.0")
        assert parser._session.headers["User-Agent"] == "TestAgent/1.0"


class TestExtractedTableDataclass:
    def test_len(self):
        df = pd.DataFrame({"a": [1, 2, 3]})
        t = ExtractedTable(page_number=1, data=df)
        assert len(t) == 3

    def test_repr(self):
        df = pd.DataFrame({"a": [1]})
        t = ExtractedTable(page_number=1, data=df, caption="Test")
        r = repr(t)
        assert "page=1" in r
        assert "rows=1" in r
        assert "caption='Test'" in r

    def test_repr_no_caption(self):
        df = pd.DataFrame({"a": [1]})
        t = ExtractedTable(page_number=2, data=df)
        r = repr(t)
        assert "caption" not in r


class TestPDFMetadataDataclass:
    def test_defaults(self):
        m = PDFMetadata()
        assert m.title is None
        assert m.page_count == 0

    def test_with_values(self):
        m = PDFMetadata(title="Test", author="Me", page_count=5)
        assert m.title == "Test"
        assert m.author == "Me"
        assert m.page_count == 5
