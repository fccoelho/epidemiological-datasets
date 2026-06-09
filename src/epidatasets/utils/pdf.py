"""
Shared PDF Parser for Epidemiological Data Sources

Provides a reusable PDFParser class for downloading, caching, and extracting
text, tables, and metadata from PDF documents. Designed to be composed into
data source accessors.

Supports:
- PDF download with configurable caching (TTL-based)
- Text extraction via pypdf
- Table extraction via pdfplumber with smart header detection
- Document metadata extraction (title, author, dates)
- Cell cleaning, numeric parsing, multi-row header merging

Usage::

    from epidatasets.utils.pdf import PDFParser

    parser = PDFParser(cache_dir="~/.cache/epidatasets/my_source", cache_ttl_days=7)

    # Download
    pdf_path = parser.download("https://example.com/report.pdf")

    # Extract text
    text = parser.extract_text(pdf_path)

    # Extract tables with metadata
    tables = parser.extract_tables(pdf_path)
    for t in tables:
        print(f"Page {t.page_number}: {t.caption}")
        print(t.data.head())

    # Get metadata
    meta = parser.extract_metadata(pdf_path, source_url="https://example.com/report.pdf")
    print(meta.title, meta.page_count)

Author: Flávio Codeço Coelho
License: MIT
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)


@dataclass
class ExtractedTable:
    """A table extracted from a PDF page."""

    page_number: int
    data: pd.DataFrame
    caption: str | None = None
    raw_data: list[list[str | None]] = field(default_factory=list, repr=False)

    def __len__(self) -> int:
        return len(self.data)

    def __repr__(self) -> str:
        cap = f", caption={self.caption!r}" if self.caption else ""
        return (
            f"ExtractedTable(page={self.page_number}, "
            f"rows={len(self.data)}, cols={len(self.data.columns)}{cap})"
        )


@dataclass
class PDFMetadata:
    """Metadata extracted from a PDF document."""

    title: str | None = None
    author: str | None = None
    creation_date: str | None = None
    page_count: int = 0
    source_url: str | None = None


class PDFParser:
    """
    Shared PDF parser for epidemiological data sources.

    Handles downloading, caching, text extraction, and table extraction
    from PDF documents. Designed to be composed into data source accessors.

    Args:
        cache_dir: Directory for caching downloaded PDFs.
        cache_ttl_days: Time-to-live for cached files in days.
        user_agent: User-Agent header for HTTP requests.
        timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        cache_ttl_days: int = 7,
        user_agent: str | None = None,
        timeout: int = 60,
    ):
        if cache_dir is None:
            cache_dir = Path.home() / ".cache" / "epidatasets" / "pdf"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = timedelta(days=cache_ttl_days)
        self.timeout = timeout

        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": user_agent
                or "epidatasets PDF Parser/1.0 (Research Purpose)"
            }
        )

    # ------------------------------------------------------------------
    # Download & Cache
    # ------------------------------------------------------------------

    def download(self, url: str, filename: str | None = None) -> Path:
        """
        Download a PDF from URL with caching.

        Args:
            url: URL to download from.
            filename: Optional filename for cache. Auto-derived from URL.

        Returns:
            Path to cached/downloaded file.

        Raises:
            ValueError: If URL does not return a PDF.
            requests.HTTPError: If download fails.
        """
        if filename is None:
            filename = url.rsplit("/", 1)[-1] or "document.pdf"
            filename = re.sub(r"[^\w.\-]", "_", filename)

        cache_path = self.cache_dir / filename

        if self._is_cache_valid(cache_path):
            logger.info(f"Using cached PDF: {cache_path}")
            return cache_path

        logger.info(f"Downloading PDF from: {url}")
        response = self._session.get(url, timeout=self.timeout, stream=True)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "").lower()
        content = response.content
        if "pdf" not in content_type and not content.startswith(b"%PDF"):
            raise ValueError(
                f"URL does not point to a PDF (content-type: {content_type}): {url}"
            )

        cache_path.write_bytes(content)
        logger.info(f"Saved PDF to cache: {cache_path}")
        return cache_path

    def _is_cache_valid(self, path: Path) -> bool:
        if not path.exists():
            return False
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        return datetime.now() - mtime < self.cache_ttl

    # ------------------------------------------------------------------
    # Text Extraction
    # ------------------------------------------------------------------

    def extract_text(
        self, pdf_path: str | Path, pages: range | list[int] | None = None
    ) -> str:
        """
        Extract text from PDF pages.

        Args:
            pdf_path: Path to PDF file.
            pages: Optional 0-indexed page indices. None = all pages.

        Returns:
            Extracted text joined by newlines.
        """
        try:
            from pypdf import PdfReader
        except ImportError:
            logger.warning("pypdf not available. Install with: pip install pypdf")
            return ""

        reader = PdfReader(str(pdf_path))
        page_indices = pages if pages is not None else range(len(reader.pages))

        texts = []
        for i in page_indices:
            if 0 <= i < len(reader.pages):
                text = reader.pages[i].extract_text()
                if text:
                    texts.append(text)

        return "\n".join(texts)

    # ------------------------------------------------------------------
    # Table Extraction
    # ------------------------------------------------------------------

    def extract_tables(
        self,
        pdf_path: str | Path,
        pages: range | list[int] | None = None,
        detect_captions: bool = True,
        clean_cells: bool = True,
        merge_headers: bool = True,
        drop_empty_rows: bool = True,
        min_rows: int = 2,
    ) -> list[ExtractedTable]:
        """
        Extract tables from PDF with metadata.

        Args:
            pdf_path: Path to PDF file.
            pages: Optional 1-indexed page numbers. None = all pages.
            detect_captions: Search for table captions in surrounding text.
            clean_cells: Normalize cell values (whitespace, empty).
            merge_headers: Merge multi-row headers.
            drop_empty_rows: Drop all-NaN rows.
            min_rows: Minimum rows for a valid table.

        Returns:
            List of ExtractedTable objects.
        """
        try:
            import pdfplumber
        except ImportError:
            logger.warning(
                "pdfplumber not available. Install with: pip install pdfplumber"
            )
            return []

        results: list[ExtractedTable] = []

        with pdfplumber.open(str(pdf_path)) as pdf:
            target_pages = pages or range(1, len(pdf.pages) + 1)

            for page_idx in target_pages:
                if page_idx < 1 or page_idx > len(pdf.pages):
                    continue

                page = pdf.pages[page_idx - 1]
                raw_tables = page.extract_tables()

                if not raw_tables:
                    continue

                page_text = page.extract_text() or ""
                captions = (
                    self.find_captions(page_text) if detect_captions else []
                )

                for table_idx, raw_table in enumerate(raw_tables):
                    if not raw_table or len(raw_table) < min_rows:
                        continue

                    working = raw_table

                    if clean_cells:
                        working = [
                            [self.clean_cell(cell) for cell in row]
                            for row in working
                        ]

                    working = self.strip_spacer_columns(working)

                    header_rows, data_rows = self._split_header_data(working)

                    if merge_headers and len(header_rows) > 1:
                        headers = self.merge_header_rows(header_rows)
                    elif header_rows:
                        headers = [
                            str(c) if c else f"col_{i}"
                            for i, c in enumerate(header_rows[0])
                        ]
                    else:
                        headers = [
                            f"col_{i}"
                            for i in range(
                                max(len(r) for r in data_rows) if data_rows else 0
                            )
                        ]

                    if data_rows and headers:
                        max_cols = max(
                            len(headers), max(len(r) for r in data_rows)
                        )
                        headers = headers + [
                            f"col_{i}" for i in range(len(headers), max_cols)
                        ]
                        padded = [
                            r + [None] * (max_cols - len(r)) for r in data_rows
                        ]
                        df = pd.DataFrame(padded, columns=headers)
                    else:
                        df = pd.DataFrame(working)

                    if drop_empty_rows:
                        df = df.dropna(how="all").reset_index(drop=True)

                    if df.empty:
                        continue

                    caption = None
                    if table_idx < len(captions):
                        caption = captions[table_idx]

                    results.append(
                        ExtractedTable(
                            page_number=page_idx,
                            caption=caption,
                            data=df,
                            raw_data=working,
                        )
                    )

        logger.info(
            f"Extracted {len(results)} table(s) from {Path(pdf_path).name}"
        )
        return results

    def _split_header_data(
        self, table: list[list[str | None]]
    ) -> tuple[list[list[str | None]], list[list[str | None]]]:
        """Split table into header rows and data rows."""
        if not table:
            return [], []

        header_rows: list[list[str | None]] = []
        data_start = 0

        for i, row in enumerate(table):
            has_numeric = any(
                self.parse_numeric(c) is not None for c in row[1:] if c
            )
            has_text_first = bool(row[0]) if row else False
            if has_numeric and has_text_first:
                data_start = i
                break
            header_rows.append(row)

        if not header_rows:
            header_rows = [table[0]]
            data_start = min(1, len(table) - 1)

        return header_rows, table[data_start:]

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def extract_metadata(
        self, pdf_path: str | Path, source_url: str | None = None
    ) -> PDFMetadata:
        """
        Extract document-level metadata.

        Args:
            pdf_path: Path to PDF file.
            source_url: Original URL of the PDF (for reference).

        Returns:
            PDFMetadata with available fields populated.
        """
        try:
            from pypdf import PdfReader
        except ImportError:
            return PDFMetadata(source_url=source_url)

        reader = PdfReader(str(pdf_path))
        meta = reader.metadata or {}

        return PDFMetadata(
            title=meta.get("/Title"),
            author=meta.get("/Author"),
            creation_date=meta.get("/CreationDate"),
            page_count=len(reader.pages),
            source_url=source_url,
        )

    # ------------------------------------------------------------------
    # Static utility methods
    # ------------------------------------------------------------------

    @staticmethod
    def clean_cell(value) -> str | None:
        """Clean a table cell value."""
        if value is None:
            return None
        s = str(value).strip()
        s = re.sub(r"\s+", " ", s)
        return s if s else None

    @staticmethod
    def parse_numeric(value, default=None):
        """Parse a cell value to a number (int or float).

        Handles NR, -, N/A, comma-separated, parenthesized negatives.
        """
        if value is None:
            return default
        text = str(value).strip()
        if not text or text in ("NR", "-", "N/A", "na", "NA", "...", "—", "–"):
            return default
        cleaned = text.replace(",", "").replace(" ", "").strip()
        match = re.match(r"[−\-]?\(?(\d[\d.]*)\)?", cleaned)
        if match:
            try:
                val = float(match.group(1))
                return int(val) if val == int(val) else val
            except ValueError:
                return default
        return default

    @staticmethod
    def strip_spacer_columns(
        table: list[list], threshold: float = 0.15
    ) -> list[list]:
        """Remove columns where fewer than *threshold*% of rows have content."""
        if not table:
            return table
        ncols = max(len(r) for r in table)
        nrows = len(table)
        min_non_empty = max(3, int(nrows * threshold))
        keep = []
        for col_idx in range(ncols):
            non_empty = 0
            for row in table:
                val = row[col_idx] if col_idx < len(row) else None
                if val is not None and str(val).strip():
                    non_empty += 1
            if non_empty >= min_non_empty:
                keep.append(col_idx)
        if not keep:
            return table
        return [
            [row[c] if c < len(row) else None for c in keep] for row in table
        ]

    @staticmethod
    def merge_header_rows(rows: list[list]) -> list[str]:
        """Merge multi-row header cells by joining fragments with spaces."""
        if not rows:
            return []
        ncols = max(len(r) for r in rows)
        merged = []
        for col_idx in range(ncols):
            fragments = []
            for row in rows:
                val = row[col_idx] if col_idx < len(row) else None
                if val is not None and str(val).strip():
                    fragments.append(str(val).strip())
            merged.append(" ".join(fragments).strip() if fragments else "")
        return merged

    @staticmethod
    def find_captions(text: str) -> list[str]:
        """Find table captions like 'Table N: description' in page text."""
        pattern = re.compile(
            r"[Tt]able\s+(\d+)[.:]\s*(.+?)(?:\n|$)", re.IGNORECASE
        )
        return [m.group(2).strip() for m in pattern.finditer(text)]
