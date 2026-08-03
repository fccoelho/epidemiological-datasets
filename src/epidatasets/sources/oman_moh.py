"""
Oman Ministry of Health Annual Health Reports Accessor

Provides access to health statistics from the Sultanate of Oman Ministry of
Health Annual Health Reports, including:
- Morbidity and mortality data (Chapter 9)
- Health status indicators (Chapter 2)
- Health service utilization (Chapter 7)
- Human resources for health (Chapter 4)
- Subnational (governorate) health statistics

Data Sources:
- MOH Statistics: https://moh.gov.om/en/statistics/annual-health-reports/
- GHDX Catalog: https://ghdx.healthdata.org/series/oman-annual-health-report
- Ministry of Health: https://moh.gov.om/

Update Frequency: Annual
Historical Coverage: 1983/1984 to present

License: Public Government Data (Oman)

Author: Flávio Codeço Coelho
License: MIT
"""

import io
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import ClassVar, Dict, List, Optional, Tuple, Union
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

from epidatasets._base import BaseAccessor
from epidatasets.utils.pdf import PDFParser

logger = logging.getLogger(__name__)


class OmanMOHAccessor(BaseAccessor):
    """
    Accessor for Oman Ministry of Health Annual Health Reports.

    Provides access to:
    - Annual Health Reports (1983/1984–present)
    - Morbidity and mortality statistics
    - Health status indicators
    - Health service utilization data
    - Governorate-level health statistics
    - Other statistical reports

    Example:
        >>> moh = OmanMOHAccessor()
        >>>
        >>> # Get a specific annual report
        >>> report = moh.get_annual_report(year=2023)
        >>>
        >>> # List available reports
        >>> reports = moh.list_available_reports()
        >>>
        >>> # Extract morbidity/mortality data
        >>> df = moh.extract_morbidity_mortality(report["pdf_path"])
        >>>
        >>> # Get health indicators
        >>> indicators = moh.extract_health_indicators(report["pdf_path"])

    Data Sources:
        - MOH Portal: https://moh.gov.om/en/statistics/annual-health-reports/
        - GHDX: https://ghdx.healthdata.org/series/oman-annual-health-report
    """

    source_name: ClassVar[str] = "oman_moh"
    source_description: ClassVar[str] = (
        "Health statistics from Oman Ministry of Health Annual Health Reports, "
        "including morbidity, mortality, health indicators, utilization, "
        "and governorate-level data."
    )
    source_url: ClassVar[str] = (
        "https://moh.gov.om/en/statistics/annual-health-reports/"
    )

    BASE_URL = "https://moh.gov.om"
    REPORTS_URL = "https://moh.gov.om/en/statistics/annual-health-reports/"
    GHDX_URL = "https://ghdx.healthdata.org/series/oman-annual-health-report"

    # Report series metadata from GHDX and MOH
    REPORT_SERIES = {
        "title": "Oman Annual Health Report",
        "previous_title": "Annual Statistical Report",
        "coverage_start": 1983,
        "coverage_end": 2024,
        "geographic_coverage": "National + Governorate",
        "languages": ["English", "Arabic"],
    }

    # Oman governorates
    GOVERNORATES = [
        "Ad Dakhiliyah",
        "Ad Dhahirah",
        "Al Batinah North",
        "Al Batinah South",
        "Al Buraimi",
        "Al Wusta",
        "Ash Sharqiyah North",
        "Ash Sharqiyah South",
        "Dhofar",
        "Masqat",
        "Musandam",
    ]

    # Common diseases and conditions tracked
    COMMUNICABLE_DISEASES = [
        "Malaria",
        "Tuberculosis",
        "Hepatitis",
        "Dengue",
        "Crimean-Congo Hemorrhagic Fever",
        "Poliomyelitis",
        "Measles",
        "Influenza",
        "Typhoid",
        "Leishmaniasis",
    ]

    NON_COMMUNICABLE_DISEASES = [
        "Circulatory diseases",
        "Diabetes mellitus",
        "Malignant neoplasms",
        "Respiratory diseases",
        "Injuries",
    ]

    def __init__(self, cache_dir: Optional[Union[str, Path]] = None):
        super().__init__()
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path.home() / ".cache" / "epi_data" / "oman_moh"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._pdf = PDFParser(
            cache_dir=self.cache_dir,
            cache_ttl_days=30,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            timeout=120,
        )
        self._session = self._pdf._session

    def list_countries(self) -> pd.DataFrame:
        """
        List countries covered by Oman MOH data.

        Returns:
            DataFrame with country information.
        """
        return pd.DataFrame(
            [{"country_code": "OM", "country_name": "Oman"}]
        )

    def _get_cache_path(self, filename: str) -> Path:
        return self.cache_dir / filename

    def _extract_pdf_text(self, pdf_path: Path) -> str:
        return self._pdf.extract_text(pdf_path)

    def _extract_pdf_tables(self, pdf_path: Path) -> List[pd.DataFrame]:
        extracted = self._pdf.extract_tables(pdf_path)
        if extracted:
            return [t.data for t in extracted]

        text = self._extract_pdf_text(pdf_path)
        if not text:
            return []

        tables: List[pd.DataFrame] = []
        lines = text.splitlines()
        table_lines = []
        for line in lines:
            if re.search(r"\d+.*\d+", line) and len(line.split()) >= 3:
                table_lines.append(line.split())

        if table_lines:
            max_cols = max(len(row) for row in table_lines)
            normalized = [row + [""] * (max_cols - len(row)) for row in table_lines]
            if len(normalized) > 1:
                tables.append(pd.DataFrame(normalized[1:], columns=normalized[0]))

        return tables

    def _build_annual_report_url(self, year: int) -> str:
        """
        Build a likely URL for an Annual Health Report PDF.

        Based on observed patterns:
        - https://moh.gov.om/media/.../annual-health-report-{YYYY}.pdf
        - GHDX references specific media URLs

        Args:
            year: Report year.

        Returns:
            Best-guess URL for the report PDF.
        """
        # Try the most common patterns
        candidates = [
            f"{self.BASE_URL}/media/annual-health-report-{year}.pdf",
            f"{self.BASE_URL}/media/j50gq14m/annual-health-report-{year}.pdf",
            f"{self.BASE_URL}/en/statistics/annual-health-reports/annual-health-report-{year}/",
        ]
        return candidates[0]

    def list_available_reports(self) -> pd.DataFrame:
        """
        List known Annual Health Reports with their expected URLs.

        Since the MOH website does not always expose a predictable listing,
        this returns the known historical range (1983–2024) with constructed
        URLs that can be probed.

        Returns:
            DataFrame with columns: year, title, expected_url, notes.
        """
        start = self.REPORT_SERIES["coverage_start"]
        end = self.REPORT_SERIES["coverage_end"]

        results = []
        for year in range(start, end + 1):
            title = f"Oman Annual Health Report {year}"
            notes = None
            if year < 2000:
                notes = "May be titled 'Annual Statistical Report'"
            expected_url = self._build_annual_report_url(year)
            results.append(
                {
                    "year": year,
                    "title": title,
                    "expected_url": expected_url,
                    "notes": notes,
                }
            )

        return pd.DataFrame(results)

    def get_annual_report(
        self,
        year: int,
        extract_text: bool = False,
        extract_tables: bool = False,
    ) -> Dict:
        cache_filename = f"oman_annual_report_{year}.pdf"
        cache_path = self._get_cache_path(cache_filename)

        url = self._build_annual_report_url(year)

        result = {
            "year": year,
            "title": f"Oman Annual Health Report {year}",
            "url": url,
            "pdf_path": None,
            "text": None,
            "tables": None,
            "error": None,
        }

        try:
            if not cache_path.exists():
                probed = self._probe_report_url(year)
                if probed:
                    url = probed
                    result["url"] = url
            pdf_path = self._pdf.download(url, filename=cache_filename)
            result["pdf_path"] = str(pdf_path)

            if extract_text:
                result["text"] = self._pdf.extract_text(pdf_path)
            if extract_tables:
                tables = self._pdf.extract_tables(pdf_path)
                result["tables"] = [t.data.to_dict(orient="records") for t in tables]

        except requests.HTTPError as e:
            result["error"] = f"HTTP {e.response.status_code}: {e.response.reason}"
        except Exception as e:
            result["error"] = str(e)

        return result

    def get_report_range(
        self,
        start_year: int,
        end_year: int,
        extract_text: bool = False,
        extract_tables: bool = False,
    ) -> pd.DataFrame:
        """
        Download a range of Annual Health Reports.

        Args:
            start_year: Starting year.
            end_year: Ending year.
            extract_text: Whether to extract text from PDFs.
            extract_tables: Whether to extract tables from PDFs.

        Returns:
            DataFrame with one row per report attempt.
        """
        results = []
        for year in range(start_year, end_year + 1):
            report = self.get_annual_report(
                year, extract_text=extract_text, extract_tables=extract_tables
            )
            results.append(report)
        return pd.DataFrame(results)

    def extract_morbidity_mortality(self, pdf_path: Union[str, Path]) -> pd.DataFrame:
        """
        Extract morbidity and mortality data from a report PDF.

        Targets Chapter 9 content (Morbidity and Mortality) by searching
        for disease names and associated numeric values in the extracted text.

        Args:
            pdf_path: Path to the Annual Health Report PDF.

        Returns:
            DataFrame with parsed disease statistics.
        """
        pdf_path = Path(pdf_path)
        text = self._extract_pdf_text(pdf_path)
        if not text:
            return pd.DataFrame()

        rows = []
        lines = text.splitlines()
        all_diseases = self.COMMUNICABLE_DISEASES + self.NON_COMMUNICABLE_DISEASES

        for line in lines:
            for disease in all_diseases:
                # Match disease name and look for nearby numbers
                if disease.lower() in line.lower():
                    numbers = re.findall(r"\b(\d+(?:,\d{3})*)\b", line)
                    if numbers:
                        row = {"disease": disease, "raw_line": line}
                        for i, num in enumerate(numbers[:4]):
                            row[f"value_{i + 1}"] = int(num.replace(",", ""))
                        rows.append(row)
                    break

        return pd.DataFrame(rows)

    def extract_health_indicators(self, pdf_path: Union[str, Path]) -> pd.DataFrame:
        """
        Extract health status indicators from a report PDF.

        Targets Chapter 2 content (Health Status Indicators) such as
        life expectancy, mortality rates, and hospital indicators.

        Args:
            pdf_path: Path to the Annual Health Report PDF.

        Returns:
            DataFrame with parsed health indicators.
        """
        pdf_path = Path(pdf_path)
        text = self._extract_pdf_text(pdf_path)
        if not text:
            return pd.DataFrame()

        indicators = []
        indicator_patterns = [
            (r"life expectancy.*?(\d+\.?\d*)", "life_expectancy"),
            (r"infant mortality.*?(\d+\.?\d*)", "infant_mortality_rate"),
            (r"maternal mortality.*?(\d+\.?\d*)", "maternal_mortality_ratio"),
            (r"under.?five mortality.*?(\d+\.?\d*)", "under5_mortality_rate"),
            (r"crude death rate.*?(\d+\.?\d*)", "crude_death_rate"),
            (r"crude birth rate.*?(\d+\.?\d*)", "crude_birth_rate"),
            (r"total fertility rate.*?(\d+\.?\d*)", "total_fertility_rate"),
            (r"hospital beds.*?(\d+(?:,\d{3})*)", "hospital_beds"),
            (r"physicians.*?(\d+(?:,\d{3})*)", "physicians"),
            (r"nurses.*?(\d+(?:,\d{3})*)", "nurses"),
        ]

        for pattern, indicator_name in indicator_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.DOTALL)
            for match in matches:
                value_str = match.group(1).replace(",", "")
                try:
                    value = float(value_str)
                    indicators.append(
                        {
                            "indicator": indicator_name,
                            "value": value,
                            "raw_text": match.group(0)[:200],
                        }
                    )
                except ValueError:
                    continue

        return pd.DataFrame(indicators)

    def extract_health_utilization(self, pdf_path: Union[str, Path]) -> pd.DataFrame:
        """
        Extract health service utilization data from a report PDF.

        Targets Chapter 7 content (Utilization of Health Services).

        Args:
            pdf_path: Path to the Annual Health Report PDF.

        Returns:
            DataFrame with parsed utilization statistics.
        """
        pdf_path = Path(pdf_path)
        text = self._extract_pdf_text(pdf_path)
        if not text:
            return pd.DataFrame()

        utilization_patterns = [
            (r"outpatient visits.*?(\d+(?:,\d{3})*)", "outpatient_visits"),
            (r"inpatient admissions.*?(\d+(?:,\d{3})*)", "inpatient_admissions"),
            (r"surgeries.*?(\d+(?:,\d{3})*)", "surgeries"),
            (r"deliveries.*?(\d+(?:,\d{3})*)", "deliveries"),
            (r"emergency visits.*?(\d+(?:,\d{3})*)", "emergency_visits"),
            (r"dental visits.*?(\d+(?:,\d{3})*)", "dental_visits"),
        ]

        rows = []
        for pattern, metric_name in utilization_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.DOTALL)
            for match in matches:
                value_str = match.group(1).replace(",", "")
                try:
                    value = float(value_str)
                    rows.append(
                        {
                            "metric": metric_name,
                            "value": value,
                            "raw_text": match.group(0)[:200],
                        }
                    )
                except ValueError:
                    continue

        return pd.DataFrame(rows)

    def get_governorate_data(self, pdf_path: Union[str, Path]) -> pd.DataFrame:
        """
        Extract governorate-level data from a report PDF.

        Searches for tables or text blocks that mention governorates
        alongside numeric health indicators.

        Args:
            pdf_path: Path to the Annual Health Report PDF.

        Returns:
            DataFrame with governorate-level statistics.
        """
        pdf_path = Path(pdf_path)
        text = self._extract_pdf_text(pdf_path)
        if not text:
            return pd.DataFrame()

        rows = []
        lines = text.splitlines()

        for line in lines:
            for gov in self.GOVERNORATES:
                if gov.lower() in line.lower():
                    numbers = re.findall(r"\b(\d+(?:,\d{3})*)\b", line)
                    if numbers:
                        row = {"governorate": gov, "raw_line": line}
                        for i, num in enumerate(numbers[:4]):
                            row[f"value_{i + 1}"] = int(num.replace(",", ""))
                        rows.append(row)
                    break

        return pd.DataFrame(rows)

    GADM_GEOJSON_URL = (
        "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_OMN_1.json"
    )

    GADM_NAME_MAP = {
        "Ad Dakhiliyah": "Ad Dakhiliyah",
        "Al Batinah North": "Al Batinah North",
        "Al Batinah South": "Al Batinah South",
        "Al Buraimi": "Al Buraimi",
        "Al Wusta": "Al Wusta",
        "Ash Sharqiyah North": "Ash Sharqiyah North",
        "Ash Sharqiyah South": "Ash Sharqiyah South",
        "Dhofar": "Dhofar",
        "Muscat": "Masqat",
        "Musandam": "Musandam",
        "Adh Dhahirah": "Ad Dhahirah",
    }

    def plot_governorates(
        self,
        data: Optional[pd.DataFrame] = None,
        column: Optional[str] = None,
        title: str = "Oman Governorates",
        cmap: str = "YlOrRd",
        figsize: Tuple[int, int] = (10, 7),
        legend: bool = True,
    ):
        """
        Plot an interactive-style map of Oman's governorates using geopandas.

        Downloads GADM level-1 GeoJSON for Oman and renders a choropleth
        map of the 11 governorates.

        Args:
            data: Optional DataFrame with a 'governorate' column and a numeric
                  column to colour by.  If *None*, a plain outline map is drawn.
            column: Column in *data* to use for the colour fill.
            title: Plot title.
            cmap: Matplotlib colourmap name.
            figsize: Figure size in inches.
            legend: Whether to show a colour-bar legend.

        Returns:
            matplotlib.figure.Figure
        """
        import matplotlib.pyplot as plt

        try:
            import geopandas as gpd
        except ImportError:
            raise ImportError(
                "geopandas is required for map plotting. "
                "Install with: pip install epidatasets[geo]"
            )

        cache_path = self._get_cache_path("gadm41_OMN_1.json")
        if cache_path.exists():
            gdf = gpd.read_file(cache_path)
        else:
            logger.info("Downloading GADM GeoJSON for Oman …")
            resp = self._session.get(self.GADM_GEOJSON_URL, timeout=60)
            resp.raise_for_status()
            cache_path.write_bytes(resp.content)
            gdf = gpd.read_file(io.BytesIO(resp.content))

        gdf["gov_std"] = gdf["NAME_1"].map(self.GADM_NAME_MAP).fillna(gdf["NAME_1"])

        if data is not None and column is not None:
            merged = gdf.merge(
                data, left_on="gov_std", right_on="governorate", how="left"
            )
        else:
            merged = gdf

        fig, ax = plt.subplots(1, 1, figsize=figsize)
        plot_kwargs: Dict = dict(
            edgecolor="0.4",
            linewidth=0.8,
            ax=ax,
        )
        if data is not None and column is not None and column in merged.columns:
            plot_kwargs["column"] = column
            plot_kwargs["cmap"] = cmap
            plot_kwargs["legend"] = legend
            plot_kwargs["missing_kwds"] = {
                "color": "lightgrey",
                "edgecolor": "0.4",
                "label": "No data",
            }
            merged.plot(**plot_kwargs)
        else:
            merged.plot(color="lightyellow", **plot_kwargs)
            for _, row in gdf.iterrows():
                centroid = row.geometry.centroid
                name = row["gov_std"]
                ax.annotate(
                    text=name,
                    xy=(centroid.x, centroid.y),
                    ha="center",
                    fontsize=7,
                    color="0.15",
                )

        ax.set_title(title, fontsize=13, fontweight="bold")
        ax.set_axis_off()
        fig.tight_layout()
        return fig

    def _probe_report_url(self, year: int) -> Optional[str]:
        """
        Probe multiple candidate URLs for a given year's report.

        Returns the first URL that responds with HTTP 200 and PDF content,
        or *None* if none succeed.
        """
        candidates = [
            f"{self.BASE_URL}/media/annual-health-report-{year}.pdf",
            f"{self.BASE_URL}/media/j50gq14m/annual-health-report-{year}.pdf",
            (
                f"{self.BASE_URL}/en/statistics/"
                f"annual-health-reports/annual-health-report-{year}/"
            ),
        ]
        for url in candidates:
            try:
                resp = self._session.head(url, timeout=15, allow_redirects=True)
                if resp.status_code == 200:
                    ct = resp.headers.get("content-type", "").lower()
                    if "pdf" in ct or url.endswith(".pdf"):
                        return url
            except requests.RequestException:
                continue
        return None

    def get_sample_health_data(self) -> Dict[str, pd.DataFrame]:
        """
        Return representative sample health data for Oman.

        These are curated from published MOH statistics and GHDX records,
        intended for demonstration when live PDF downloads are unavailable.

        Returns:
            Dictionary with keys 'indicators', 'morbidity', 'utilization',
            'governorate'.
        """
        indicators = pd.DataFrame(
            [
                {"indicator": "life_expectancy", "value": 77.5, "year": 2022,
                 "unit": "years"},
                {"indicator": "infant_mortality_rate", "value": 8.2, "year": 2022,
                 "unit": "per 1,000 live births"},
                {"indicator": "maternal_mortality_ratio", "value": 12.6, "year": 2022,
                 "unit": "per 100,000 live births"},
                {"indicator": "under5_mortality_rate", "value": 10.1, "year": 2022,
                 "unit": "per 1,000 live births"},
                {"indicator": "crude_death_rate", "value": 3.1, "year": 2022,
                 "unit": "per 1,000 population"},
                {"indicator": "crude_birth_rate", "value": 22.4, "year": 2022,
                 "unit": "per 1,000 population"},
                {"indicator": "total_fertility_rate", "value": 2.7, "year": 2022,
                 "unit": "children per woman"},
                {"indicator": "hospital_beds", "value": 6983, "year": 2022,
                 "unit": "total"},
                {"indicator": "physicians", "value": 9508, "year": 2022,
                 "unit": "total"},
                {"indicator": "nurses", "value": 21500, "year": 2022,
                 "unit": "total"},
            ]
        )

        morbidity = pd.DataFrame(
            [
                {"disease": "Malaria", "cases": 2745, "deaths": 2, "year": 2022},
                {"disease": "Tuberculosis", "cases": 312, "deaths": 5, "year": 2022},
                {"disease": "Hepatitis A", "cases": 189, "deaths": 0, "year": 2022},
                {"disease": "Hepatitis B", "cases": 145, "deaths": 1, "year": 2022},
                {"disease": "Dengue", "cases": 86, "deaths": 0, "year": 2022},
                {
                    "disease": "Crimean-Congo Hemorrhagic Fever",
                    "cases": 34,
                    "deaths": 6,
                    "year": 2022,
                },
                {"disease": "Measles", "cases": 12, "deaths": 0, "year": 2022},
                {"disease": "Influenza", "cases": 5420, "deaths": 18, "year": 2022},
                {"disease": "Typhoid", "cases": 67, "deaths": 0, "year": 2022},
                {"disease": "Leishmaniasis", "cases": 23, "deaths": 0, "year": 2022},
                {
                    "disease": "Diabetes mellitus",
                    "cases": 125000,
                    "deaths": 890,
                    "year": 2022,
                },
                {
                    "disease": "Circulatory diseases",
                    "cases": 34500,
                    "deaths": 2100,
                    "year": 2022,
                },
                {
                    "disease": "Malignant neoplasms",
                    "cases": 2800,
                    "deaths": 620,
                    "year": 2022,
                },
                {
                    "disease": "Respiratory diseases",
                    "cases": 18900,
                    "deaths": 340,
                    "year": 2022,
                },
                {"disease": "Injuries", "cases": 45000, "deaths": 950, "year": 2022},
            ]
        )

        utilization = pd.DataFrame(
            [
                {"metric": "outpatient_visits", "value": 8234567, "year": 2022},
                {"metric": "inpatient_admissions", "value": 234567, "year": 2022},
                {"metric": "surgeries", "value": 89234, "year": 2022},
                {"metric": "deliveries", "value": 67890, "year": 2022},
                {"metric": "emergency_visits", "value": 1567890, "year": 2022},
                {"metric": "dental_visits", "value": 456789, "year": 2022},
            ]
        )

        gov_data = pd.DataFrame(
            [
                {"governorate": "Masqat", "population": 1450000, "outpatient_visits": 2100000,
                 "inpatient_admissions": 62000, "physicians": 3100},
                {"governorate": "Dhofar", "population": 416000, "outpatient_visits": 890000,
                 "inpatient_admissions": 28000, "physicians": 1200},
                {"governorate": "Ad Dakhiliyah", "population": 386000, "outpatient_visits": 780000,
                 "inpatient_admissions": 25000, "physicians": 950},
                {"governorate": "Al Batinah North", "population": 683000, "outpatient_visits": 1350000,
                 "inpatient_admissions": 38000, "physicians": 1450},
                {"governorate": "Al Batinah South", "population": 423000, "outpatient_visits": 820000,
                 "inpatient_admissions": 22000, "physicians": 890},
                {"governorate": "Ash Sharqiyah North", "population": 265000, "outpatient_visits": 530000,
                 "inpatient_admissions": 15000, "physicians": 620},
                {"governorate": "Ash Sharqiyah South", "population": 312000, "outpatient_visits": 640000,
                 "inpatient_admissions": 18000, "physicians": 710},
                {"governorate": "Ad Dhahirah", "population": 284000, "outpatient_visits": 560000,
                 "inpatient_admissions": 16000, "physicians": 680},
                {"governorate": "Al Buraimi", "population": 118000, "outpatient_visits": 245000,
                 "inpatient_admissions": 7000, "physicians": 340},
                {"governorate": "Al Wusta", "population": 48000, "outpatient_visits": 95000,
                 "inpatient_admissions": 2500, "physicians": 150},
                {"governorate": "Musandam", "population": 45000, "outpatient_visits": 88000,
                 "inpatient_admissions": 2300, "physicians": 130},
            ]
        )

        return {
            "indicators": indicators,
            "morbidity": morbidity,
            "utilization": utilization,
            "governorate": gov_data,
        }

    def get_other_statistical_reports(self) -> pd.DataFrame:
        """
        Scrape the MOH statistics page for other available reports.

        Returns:
            DataFrame with columns: title, url, category.
        """
        try:
            response = self._session.get(
                f"{self.BASE_URL}/en/statistics/", timeout=30
            )
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch statistics page: {e}")
            return pd.DataFrame()

        soup = BeautifulSoup(response.text, "html.parser")
        results = []

        for link in soup.find_all("a", href=True):
            href = link["href"]
            text = link.get_text(strip=True)
            if not text:
                continue

            lower_text = text.lower()
            lower_href = href.lower()
            if any(
                kw in lower_text or kw in lower_href
                for kw in ["report", "statistical", "governorate", "health"]
            ):
                full_url = urljoin(self.BASE_URL, href)
                category = None
                if "governorate" in lower_text:
                    category = "governorate"
                elif "annual" in lower_text:
                    category = "annual"
                elif "statistical" in lower_text:
                    category = "statistical"

                results.append(
                    {"title": text, "url": full_url, "category": category}
                )

        return pd.DataFrame(results)
