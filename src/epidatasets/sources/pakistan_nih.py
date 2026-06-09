"""
Pakistan NIH IDSR Surveillance Data Accessor

Provides access to disease surveillance data from the Pakistan National Institute
of Health (NIH) Public Health Bulletin, including:
- IDSR Weekly Bulletins (weekly disease surveillance reports)
- Provincial Reports (province/district-level data)
- Seasonal Awareness and Alert Letters (SAAL)
- Advisories

Data Sources:
- PHB Portal: https://phb.nih.org.pk/
- IDSR Weekly: https://phb.nih.org.pk/integratedisease-surveillance-and-response

Update Frequency:
- IDSR Weekly Bulletins: Weekly

License: Public Government Data (Pakistan)

Author: Flávio Codeço Coelho
License: MIT
"""

import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import ClassVar, Dict, List, Optional, Union
from urllib.parse import urljoin

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup

from epidatasets._base import BaseAccessor
from epidatasets.utils.pdf import PDFParser

logger = logging.getLogger(__name__)

_PROVINCE_ALIASES = {
    "AJK": "Azad Jammu and Kashmir",
    "KP": "Khyber Pakhtunkhwa",
    "KPK": "Khyber Pakhtunkhwa",
    "GB": "Gilgit-Baltistan",
    "ICT": "Islamabad Capital Territory",
    "ISL": "Islamabad Capital Territory",
    "Punjab": "Punjab",
    "Sindh": "Sindh",
    "Balochistan": "Balochistan",
}


def _parse_numeric(value) -> Optional[int]:
    return PDFParser.parse_numeric(value)


class PakistanNIHAccessor(BaseAccessor):
    """
    Accessor for Pakistan NIH Integrated Disease Surveillance and Response (IDSR) data.

    Provides access to:
    - IDSR Weekly Bulletins (priority disease surveillance)
    - Provincial/district-level reports
    - Seasonal Awareness and Alert Letters (SAAL)
    - Public health advisories

    Example:
        >>> nih = PakistanNIHAccessor()
        >>>
        >>> # Get a specific weekly bulletin
        >>> bulletin = nih.get_weekly_bulletin(year=2025, week=10)
        >>>
        >>> # List available bulletins
        >>> bulletins = nih.list_available_bulletins(2025, 2025)
        >>>
        >>> # Get latest bulletin
        >>> latest = nih.get_latest_bulletin()

    Data Sources:
        - PHB Portal: https://phb.nih.org.pk/
        - IDSR Weekly: https://phb.nih.org.pk/integratedisease-surveillance-and-response
    """

    source_name: ClassVar[str] = "pakistan_nih"
    source_description: ClassVar[str] = (
        "Disease surveillance data from Pakistan NIH Integrated Disease Surveillance "
        "and Response (IDSR), including weekly bulletins, provincial reports, "
        "seasonal alerts, and public health advisories."
    )
    source_url: ClassVar[str] = "https://phb.nih.org.pk/integratedisease-surveillance-and-response"

    BASE_URL = "https://phb.nih.org.pk"
    IDSR_URL = "https://phb.nih.org.pk/integratedisease-surveillance-and-response"
    PROVINCIAL_URL = "https://phb.nih.org.pk/idsr-provincial-reports"
    SAAL_URL = "https://phb.nih.org.pk/saal"
    ADVISORIES_URL = "https://phb.nih.org.pk/advisories"

    PRIORITY_DISEASES = [
        "COVID-19",
        "Crimean-Congo Hemorrhagic Fever (CCHF)",
        "Dengue Fever",
        "Leishmaniasis",
        "Malaria",
        "Pertussis",
        "Poliomyelitis",
        "Diphtheria",
        "Seasonal Influenza",
        "Typhoid Fever",
        "Measles",
        "Hepatitis",
        "Tuberculosis",
    ]

    PROVINCES = [
        "Punjab",
        "Sindh",
        "Khyber Pakhtunkhwa",
        "Balochistan",
        "Gilgit-Baltistan",
        "Azad Jammu and Kashmir",
        "Islamabad Capital Territory",
    ]

    def __init__(self, cache_dir: Optional[Union[str, Path]] = None):
        super().__init__()
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path.home() / ".cache" / "epi_data" / "pakistan_nih"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._pdf = PDFParser(
            cache_dir=self.cache_dir,
            cache_ttl_days=7,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        self._session = self._pdf._session
        self._bulletin_cache: Optional[pd.DataFrame] = None

    def list_countries(self) -> pd.DataFrame:
        return pd.DataFrame([{"country_code": "PK", "country_name": "Pakistan"}])

    def _get_cache_path(self, filename: str) -> Path:
        return self.cache_dir / filename

    def _scrape_bulletin_index(self, force_refresh: bool = False) -> pd.DataFrame:
        if self._bulletin_cache is not None and not force_refresh:
            return self._bulletin_cache

        try:
            response = self._session.get(self.IDSR_URL, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch IDSR page: {e}")
            return pd.DataFrame(
                columns=["year", "week", "url", "title", "status"]
            )

        soup = BeautifulSoup(response.text, "html.parser")
        results = []

        for link in soup.find_all("a", href=True):
            href = link["href"]
            text = link.get_text(strip=True)
            if not text:
                continue

            match = re.search(
                r"(?:IDSRS?|IDSR)\s+Week\s+(\d+)\s+Bulletin\s*\((\d{4})\)",
                text,
                re.IGNORECASE,
            )
            if not match:
                continue

            week = int(match.group(1))
            year = int(match.group(2))
            full_url = urljoin(self.BASE_URL, href)

            results.append(
                {
                    "year": year,
                    "week": week,
                    "url": full_url,
                    "title": text,
                    "status": "available",
                }
            )

        df = pd.DataFrame(results)
        if not df.empty:
            df = (
                df.drop_duplicates(subset=["year", "week"])
                .sort_values(["year", "week"], ascending=[False, False])
                .reset_index(drop=True)
            )
        else:
            df = pd.DataFrame(columns=["year", "week", "url", "title", "status"])

        self._bulletin_cache = df
        return df

    def list_available_bulletins(
        self,
        start_year: int,
        end_year: int,
        max_weeks: int = 52,
    ) -> pd.DataFrame:
        index = self._scrape_bulletin_index()
        if index.empty:
            return index

        mask = (index["year"] >= start_year) & (index["year"] <= end_year)
        return index[mask].reset_index(drop=True)

    def _find_bulletin_url(self, year: int, week: int) -> Optional[str]:
        index = self._scrape_bulletin_index()
        if index.empty:
            return None
        match = index[(index["year"] == year) & (index["week"] == week)]
        if not match.empty:
            return match.iloc[0]["url"]
        return None

    def _build_weekly_url(self, year: int, week: int) -> str:
        discovered = self._find_bulletin_url(year, week)
        if discovered:
            return discovered

        estimated_month = min((week // 4) + 1, 12)
        month_str = f"{estimated_month:02d}"
        return (
            f"https://www.nih.org.pk/wp-content/uploads/"
            f"{year}/{month_str}/Weekly_Report-{week}-{year}.pdf"
        )

    def get_weekly_bulletin(
        self,
        year: int,
        week: int,
        extract_text: bool = False,
        extract_tables: bool = False,
    ) -> Dict:
        url = self._build_weekly_url(year, week)
        cache_filename = f"idsr_weekly_{year}_w{week:02d}.pdf"
        cache_path = self._get_cache_path(cache_filename)

        result = {
            "year": year,
            "week": week,
            "url": url,
            "pdf_path": None,
            "text": None,
            "tables": None,
            "error": None,
        }

        try:
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

    def get_latest_bulletin(
        self,
        extract_text: bool = False,
        extract_tables: bool = False,
    ) -> Dict:
        index = self._scrape_bulletin_index()
        if not index.empty:
            latest = index.iloc[0]
            return self.get_weekly_bulletin(
                int(latest["year"]),
                int(latest["week"]),
                extract_text=extract_text,
                extract_tables=extract_tables,
            )

        now = datetime.now()
        year = now.year
        week = int(now.strftime("%U")) + 1

        max_attempts = 10
        for _ in range(max_attempts):
            result = self.get_weekly_bulletin(
                year, week, extract_text=extract_text, extract_tables=extract_tables
            )
            if result.get("error") is None:
                return result

            week -= 1
            if week < 1:
                week = 52
                year -= 1

        return {
            "year": None,
            "week": None,
            "url": None,
            "pdf_path": None,
            "text": None,
            "tables": None,
            "error": "No recent bulletin found after 10 attempts",
        }

    def get_bulletin_range(
        self,
        start_year: int,
        start_week: int,
        end_year: int,
        end_week: int,
        extract_text: bool = False,
        extract_tables: bool = False,
    ) -> pd.DataFrame:
        results = []
        year, week = start_year, start_week

        while (year < end_year) or (year == end_year and week <= end_week):
            bulletin = self.get_weekly_bulletin(
                year, week, extract_text=extract_text, extract_tables=extract_tables
            )
            results.append(bulletin)

            week += 1
            if week > 52:
                week = 1
                year += 1

        return pd.DataFrame(results)

    def get_saals(self) -> pd.DataFrame:
        try:
            response = self._session.get(self.SAAL_URL, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch SAAL page: {e}")
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
                for kw in ["saal", "seasonal", "alert", "awareness", "letter"]
            ):
                full_url = urljoin(self.BASE_URL, href)
                diseases = [
                    d
                    for d in self.PRIORITY_DISEASES
                    if d.lower().split()[0] in lower_text
                ]
                results.append(
                    {
                        "title": text,
                        "url": full_url,
                        "season": None,
                        "diseases": ", ".join(diseases) if diseases else None,
                    }
                )

        return pd.DataFrame(results)

    def get_advisories(self) -> pd.DataFrame:
        try:
            response = self._session.get(self.ADVISORIES_URL, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch advisories page: {e}")
            return pd.DataFrame()

        soup = BeautifulSoup(response.text, "html.parser")
        results = []

        for link in soup.find_all("a", href=True):
            href = link["href"]
            text = link.get_text(strip=True)
            if not text:
                continue

            full_url = urljoin(self.BASE_URL, href)
            date_match = re.search(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", text)
            date_str = date_match.group(1) if date_match else None

            results.append({"title": text, "url": full_url, "date": date_str})

        return pd.DataFrame(results)

    def get_provincial_reports(self, province: Optional[str] = None) -> pd.DataFrame:
        try:
            response = self._session.get(self.PROVINCIAL_URL, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch provincial reports page: {e}")
            return pd.DataFrame()

        soup = BeautifulSoup(response.text, "html.parser")
        results = []

        for link in soup.find_all("a", href=True):
            href = link["href"]
            text = link.get_text(strip=True)
            if not text:
                continue

            full_url = urljoin(self.BASE_URL, href)
            inferred_province = None
            for prov in self.PROVINCES:
                if prov.lower() in text.lower():
                    inferred_province = prov
                    break

            if province and inferred_province != province:
                continue

            results.append(
                {
                    "province": inferred_province,
                    "district": None,
                    "title": text,
                    "url": full_url,
                }
            )

        return pd.DataFrame(results)

    def parse_surveillance_table(self, text: str) -> pd.DataFrame:
        if not text:
            return pd.DataFrame()

        rows = []
        lines = text.splitlines()

        for line in lines:
            for disease in self.PRIORITY_DISEASES:
                if disease.lower().split()[0] in line.lower():
                    numbers = re.findall(r"[\d,]+", line)
                    parsed = []
                    for n in numbers:
                        val = _parse_numeric(n)
                        if val is not None:
                            parsed.append(val)
                    if parsed:
                        row = {"disease": disease, "raw_line": line}
                        for i, num in enumerate(parsed[:5]):
                            row[f"value_{i + 1}"] = num
                        rows.append(row)
                    break

        return pd.DataFrame(rows)

    def extract_structured_data(
        self, pdf_path: Path, week: Optional[int] = None, year: Optional[int] = None
    ) -> Dict[str, pd.DataFrame]:
        result: Dict[str, pd.DataFrame] = {}

        try:
            import pdfplumber
        except ImportError:
            logger.debug("pdfplumber not available")
            return result

        caption_pattern = re.compile(
            r"Table\s+(\d+):\s*(.+?)(?:\n|$)", re.IGNORECASE
        )

        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text() or ""
                cap_match = caption_pattern.search(page_text)
                if not cap_match:
                    continue

                table_num = int(cap_match.group(1))
                table_caption = cap_match.group(2).strip()

                tables = page.extract_tables()
                if not tables:
                    continue

                best = max(tables, key=lambda t: len(t) * max(len(r) for r in t) if t else 0)

                stripped = PDFParser.strip_spacer_columns(best)
                if not stripped or len(stripped) < 2:
                    continue

                table_type, province = self._classify_by_caption(table_caption)

                if table_type is None:
                    if table_num == 1:
                        table_type, province = "provincial_summary", None
                    elif 2 <= table_num <= 4:
                        table_type = "district"
                        province = self._province_from_caption(table_caption)
                    elif table_num == 5:
                        table_type, province = "lab_confirmed", None
                    elif table_num in (6, 7):
                        table_type, province = "compliance", None

                if table_type is None:
                    continue

                parsed = self._parse_raw_table(
                    stripped, table_type, province, week, year
                )
                if parsed is None or parsed.empty:
                    continue

                key = table_type
                if province:
                    key = f"{table_type}_{province}"

                if key in result:
                    existing = result[key]
                    if list(parsed.columns) == list(existing.columns):
                        result[key] = pd.concat(
                            [existing, parsed], ignore_index=True
                        )
                    else:
                        suffix = len([k for k in result if k.startswith(key)])
                        result[f"{key}_{suffix}"] = parsed
                else:
                    result[key] = parsed

        return result

    def _province_from_caption(self, caption: str) -> Optional[str]:
        caption_lower = caption.lower()
        for name in [
            "Sindh",
            "Balochistan",
            "Khyber Pakhtunkhwa",
            "Azad Jammu and Kashmir",
            "Gilgit-Baltistan",
            "Islamabad Capital Territory",
        ]:
            if name.lower() in caption_lower:
                return name
        for alias, full in [
            ("KP", "Khyber Pakhtunkhwa"),
            ("AJK", "Azad Jammu and Kashmir"),
            ("GB", "Gilgit-Baltistan"),
            ("ICT", "Islamabad Capital Territory"),
        ]:
            if re.search(rf"\b{alias}\b", caption):
                return full
        return None

    def _classify_by_caption(self, caption: str) -> tuple:
        caption_lower = caption.lower()
        province = self._province_from_caption(caption)

        if "district" in caption_lower:
            return "district", province
        if "province" in caption_lower or "area wise" in caption_lower:
            return "provincial_summary", None
        if "laborator" in caption_lower or "confirmed" in caption_lower:
            return "lab_confirmed", None
        if "compliance" in caption_lower:
            return "compliance", None

        return None, None

    def _parse_raw_table(
        self,
        stripped: list,
        table_type: str,
        province: Optional[str],
        week: Optional[int],
        year: Optional[int],
    ) -> Optional[pd.DataFrame]:
        header_rows = []
        data_start = 0
        for i, row in enumerate(stripped):
            has_numeric = any(
                PDFParser.parse_numeric(c) is not None for c in row[1:]
            )
            has_text_first = bool(row[0]) if row else False
            if has_numeric and has_text_first:
                data_start = i
                break
            header_rows.append(row)

        if not header_rows:
            header_rows = [stripped[0]]
            data_start = min(1, len(stripped) - 1)

        header = PDFParser.merge_header_rows(header_rows)

        if table_type == "district" and header:
            header[0] = "District"
        elif table_type == "provincial_summary" and header:
            for idx, h in enumerate(header):
                if not h.strip():
                    header[idx] = "Diseases" if idx == 0 else f"col_{idx}"
                    break
        elif table_type == "compliance" and header:
            if not header[0].strip():
                header[0] = "Province"
            for idx in range(1, len(header)):
                if not header[idx].strip():
                    default_names = {
                        1: "Total Sites",
                        2: "Reported Sites",
                        3: "Compliance Rate",
                    }
                    header[idx] = default_names.get(idx, f"col_{idx}")

        seen = {}
        for idx, h in enumerate(header):
            if not h.strip():
                h = f"_col_{idx}"
                header[idx] = h
            seen[h] = seen.get(h, 0) + 1
            if seen[h] > 1:
                header[idx] = f"{h}_{seen[h]}"

        ncols = len(header)

        data_rows = []
        for row in stripped[data_start:]:
            cells = [PDFParser.clean_cell(c) or "" for c in row]
            if not any(cells):
                continue
            padded = cells + [""] * (ncols - len(cells))
            data_rows.append(padded[:ncols])

        if not data_rows:
            return None

        df = pd.DataFrame(data_rows, columns=header)

        if table_type == "provincial_summary":
            return self._parse_provincial_summary(df, week, year)
        elif table_type == "district":
            return self._parse_district_table(df, province, week, year)
        elif table_type == "lab_confirmed":
            return self._parse_lab_confirmed(df, week, year)
        elif table_type == "compliance":
            return self._parse_compliance_table(df, week, year)
        return None

    def _parse_provincial_summary(
        self,
        df: pd.DataFrame,
        week: Optional[int] = None,
        year: Optional[int] = None,
    ) -> pd.DataFrame:
        disease_col = None
        for col in df.columns:
            if "disease" in str(col).lower():
                disease_col = col
                break
        if disease_col is None and len(df.columns) > 0:
            disease_col = df.columns[0]

        province_cols = {}
        for col in df.columns:
            col_str = str(col)
            for alias, full in _PROVINCE_ALIASES.items():
                if col_str == alias or col_str == full:
                    province_cols[full] = col
                    break

        if not province_cols:
            for col in df.columns:
                col_str = str(col)
                if col_str == disease_col:
                    continue
                for alias, full in _PROVINCE_ALIASES.items():
                    if alias.lower() in col_str.lower() or full.lower() in col_str.lower():
                        if full not in province_cols:
                            province_cols[full] = col
                        break

        records = []
        for _, row in df.iterrows():
            disease_name = str(row.get(disease_col, "")).strip()
            if not disease_name or disease_name.lower() in ("", "total", "diseases"):
                continue
            rec = {"disease": disease_name}
            for prov_name, col_name in province_cols.items():
                val = _parse_numeric(row.get(col_name))
                rec[prov_name] = val
            if week is not None:
                rec["week"] = week
            if year is not None:
                rec["year"] = year
            records.append(rec)

        return pd.DataFrame(records)

    def _parse_district_table(
        self,
        df: pd.DataFrame,
        province: Optional[str] = None,
        week: Optional[int] = None,
        year: Optional[int] = None,
    ) -> pd.DataFrame:
        district_col = None
        for col in df.columns:
            if "district" in str(col).lower():
                district_col = col
                break
        if district_col is None and len(df.columns) > 0:
            district_col = df.columns[0]

        disease_cols = [
            c for c in df.columns if c != district_col and str(c).strip()
        ]

        records = []
        for _, row in df.iterrows():
            district = str(row.get(district_col, "")).strip()
            if not district or district.lower() in ("total", "districts"):
                continue
            for col in disease_cols:
                disease_name = str(col).strip()
                if not disease_name:
                    continue
                val = _parse_numeric(row.get(col))
                rec = {
                    "district": district,
                    "disease": disease_name,
                    "cases": val,
                }
                if province:
                    rec["province"] = province
                if week is not None:
                    rec["week"] = week
                if year is not None:
                    rec["year"] = year
                records.append(rec)

        return pd.DataFrame(records)

    def _parse_lab_confirmed(
        self,
        df: pd.DataFrame,
        week: Optional[int] = None,
        year: Optional[int] = None,
    ) -> pd.DataFrame:
        disease_col = None
        for col in df.columns:
            if "disease" in str(col).lower():
                disease_col = col
                break
        if disease_col is None and len(df.columns) > 0:
            disease_col = df.columns[0]

        province_measure_cols: Dict[str, List[str]] = {}
        for col in df.columns:
            col_str = str(col)
            for alias, full in _PROVINCE_ALIASES.items():
                if alias in col_str.split():
                    if full not in province_measure_cols:
                        province_measure_cols[full] = []
                    province_measure_cols[full].append(col)
                    break

        records = []
        for _, row in df.iterrows():
            disease_name = str(row.get(disease_col, "")).strip()
            if not disease_name or disease_name.lower() in ("", "total", "diseases"):
                continue
            for prov_name, cols in province_measure_cols.items():
                tested = None
                positive = None
                for c in cols:
                    c_lower = str(c).lower()
                    if "test" in c_lower:
                        tested = _parse_numeric(row.get(c))
                    elif "pos" in c_lower:
                        positive = _parse_numeric(row.get(c))
                if tested is not None or positive is not None:
                    rec = {
                        "disease": disease_name,
                        "province": prov_name,
                        "tested": tested,
                        "positive": positive,
                    }
                    if week is not None:
                        rec["week"] = week
                    if year is not None:
                        rec["year"] = year
                    records.append(rec)

        return pd.DataFrame(records)

    def _parse_compliance_table(
        self,
        df: pd.DataFrame,
        week: Optional[int] = None,
        year: Optional[int] = None,
    ) -> pd.DataFrame:
        district_col = None
        total_col = None
        reported_col = None
        compliance_col = None
        province_hint = None

        for col in df.columns:
            col_lower = str(col).lower()
            if "district" in col_lower:
                district_col = col
            elif "total number" in col_lower or "total" in col_lower:
                total_col = col
            elif "reported" in col_lower or "received" in col_lower:
                reported_col = col
            elif "compliance" in col_lower or "rate" in col_lower:
                compliance_col = col

            if not province_hint:
                for alias, full in _PROVINCE_ALIASES.items():
                    if alias.lower() in col_lower or full.lower() in col_lower:
                        province_hint = full
                        break

        if district_col is None and len(df.columns) > 0:
            district_col = df.columns[0]
        if total_col is None and len(df.columns) > 1:
            total_col = df.columns[1]
        if reported_col is None and len(df.columns) > 2:
            reported_col = df.columns[2]
        if compliance_col is None and len(df.columns) > 3:
            compliance_col = df.columns[3]

        records = []
        current_province = province_hint
        for _, row in df.iterrows():
            district = str(row.get(district_col, "")).strip() if district_col else ""
            if not district:
                continue

            if district.lower() in [p.lower() for p in self.PROVINCES]:
                current_province = district
                continue

            recognized = any(
                p.lower() in district.lower() for p in self.PROVINCES
            ) or any(
                alias.lower() in district.lower()
                for alias in _PROVINCE_ALIASES
            )
            if not recognized and current_province is None:
                for alias, full in _PROVINCE_ALIASES.items():
                    if alias.lower() == district.lower():
                        current_province = full
                        break

            total_sites = _parse_numeric(row.get(total_col)) if total_col else None
            reported_sites = (
                _parse_numeric(row.get(reported_col)) if reported_col else None
            )
            compliance_val = (
                _parse_numeric(row.get(compliance_col))
                if compliance_col
                else None
            )

            if total_sites is None and reported_sites is None:
                continue

            rec = {
                "province": current_province,
                "district": district,
                "total_sites": total_sites,
                "reported_sites": reported_sites,
                "compliance_rate": compliance_val,
            }
            if week is not None:
                rec["week"] = week
            if year is not None:
                rec["year"] = year
            records.append(rec)

        return pd.DataFrame(records)

    def get_sample_bulletin_data(self) -> Dict[str, pd.DataFrame]:
        """
        Return representative sample IDSR bulletin data for demonstration.

        Curated from published NIH surveillance statistics.  Use as a
        fallback when live PDF downloads fail.

        Returns:
            Dictionary with keys 'provincial_summary', 'lab_confirmed',
            'compliance', 'district_Sindh', 'district_Khyber Pakhtunkhwa'.
        """
        prov = pd.DataFrame(
            [
                {"disease": "Malaria", "Punjab": 2450, "Sindh": 3120,
                 "Khyber Pakhtunkhwa": 890, "Balochistan": 1340,
                 "Gilgit-Baltistan": 45, "Azad Jammu and Kashmir": 120,
                 "Islamabad Capital Territory": 78},
                {"disease": "Dengue Fever", "Punjab": 560, "Sindh": 890,
                 "Khyber Pakhtunkhwa": 210, "Balochistan": 55,
                 "Gilgit-Baltistan": 5, "Azad Jammu and Kashmir": 15,
                 "Islamabad Capital Territory": 42},
                {"disease": "COVID-19", "Punjab": 120, "Sindh": 95,
                 "Khyber Pakhtunkhwa": 45, "Balochistan": 20,
                 "Gilgit-Baltistan": 8, "Azad Jammu and Kashmir": 12,
                 "Islamabad Capital Territory": 30},
                {"disease": "Typhoid Fever", "Punjab": 340, "Sindh": 520,
                 "Khyber Pakhtunkhwa": 110, "Balochistan": 85,
                 "Gilgit-Baltistan": 12, "Azad Jammu and Kashmir": 25,
                 "Islamabad Capital Territory": 18},
                {"disease": "Hepatitis", "Punjab": 280, "Sindh": 410,
                 "Khyber Pakhtunkhwa": 95, "Balochistan": 70,
                 "Gilgit-Baltistan": 8, "Azad Jammu and Kashmir": 20,
                 "Islamabad Capital Territory": 15},
                {"disease": "Measles", "Punjab": 90, "Sindh": 130,
                 "Khyber Pakhtunkhwa": 55, "Balochistan": 40,
                 "Gilgit-Baltistan": 3, "Azad Jammu and Kashmir": 8,
                 "Islamabad Capital Territory": 5},
                {"disease": "Tuberculosis", "Punjab": 450, "Sindh": 380,
                 "Khyber Pakhtunkhwa": 120, "Balochistan": 65,
                 "Gilgit-Baltistan": 10, "Azad Jammu and Kashmir": 15,
                 "Islamabad Capital Territory": 22},
                {"disease": "Crimean-Congo Hemorrhagic Fever (CCHF)",
                 "Punjab": 15, "Sindh": 8, "Khyber Pakhtunkhwa": 22,
                 "Balochistan": 35, "Gilgit-Baltistan": 2,
                 "Azad Jammu and Kashmir": 1, "Islamabad Capital Territory": 3},
                {"disease": "Leishmaniasis", "Punjab": 25, "Sindh": 45,
                 "Khyber Pakhtunkhwa": 10, "Balochistan": 120,
                 "Gilgit-Baltistan": 1, "Azad Jammu and Kashmir": 2,
                 "Islamabad Capital Territory": 1},
                {"disease": "Seasonal Influenza", "Punjab": 180, "Sindh": 150,
                 "Khyber Pakhtunkhwa": 90, "Balochistan": 35,
                 "Gilgit-Baltistan": 8, "Azad Jammu and Kashmir": 12,
                 "Islamabad Capital Territory": 25},
            ]
        )

        lab = pd.DataFrame(
            [
                {"province": "Punjab", "samples_tested": 12450,
                 "positive": 892, "positivity_rate": 7.2},
                {"province": "Sindh", "samples_tested": 9870,
                 "positive": 756, "positivity_rate": 7.7},
                {"province": "Khyber Pakhtunkhwa", "samples_tested": 4520,
                 "positive": 310, "positivity_rate": 6.9},
                {"province": "Balochistan", "samples_tested": 2340,
                 "positive": 198, "positivity_rate": 8.5},
                {"province": "Gilgit-Baltistan", "samples_tested": 890,
                 "positive": 42, "positivity_rate": 4.7},
                {"province": "Azad Jammu and Kashmir", "samples_tested": 1120,
                 "positive": 65, "positivity_rate": 5.8},
                {"province": "Islamabad Capital Territory", "samples_tested": 2340,
                 "positive": 120, "positivity_rate": 5.1},
            ]
        )

        comp = pd.DataFrame(
            [
                {"province": "Punjab", "district": "Lahore",
                 "total_sites": 45, "reported_sites": 40,
                 "compliance_rate": 89},
                {"province": "Punjab", "district": "Faisalabad",
                 "total_sites": 32, "reported_sites": 27,
                 "compliance_rate": 84},
                {"province": "Sindh", "district": "Karachi",
                 "total_sites": 38, "reported_sites": 35,
                 "compliance_rate": 92},
                {"province": "Sindh", "district": "Hyderabad",
                 "total_sites": 22, "reported_sites": 18,
                 "compliance_rate": 82},
                {"province": "Khyber Pakhtunkhwa", "district": "Peshawar",
                 "total_sites": 28, "reported_sites": 23,
                 "compliance_rate": 82},
                {"province": "Balochistan", "district": "Quetta",
                 "total_sites": 18, "reported_sites": 14,
                 "compliance_rate": 78},
                {"province": "Gilgit-Baltistan", "district": "Gilgit",
                 "total_sites": 12, "reported_sites": 10,
                 "compliance_rate": 83},
                {"province": "Islamabad Capital Territory", "district": "Islamabad",
                 "total_sites": 15, "reported_sites": 14,
                 "compliance_rate": 93},
            ]
        )

        sindh_districts = pd.DataFrame(
            [
                {"disease": "Malaria", "district": "Karachi", "cases": 890},
                {"disease": "Malaria", "district": "Hyderabad", "cases": 420},
                {"disease": "Malaria", "district": "Thatta", "cases": 310},
                {"disease": "Dengue Fever", "district": "Karachi", "cases": 520},
                {"disease": "Dengue Fever", "district": "Hyderabad", "cases": 180},
                {"disease": "Typhoid Fever", "district": "Karachi", "cases": 245},
                {"disease": "Typhoid Fever", "district": "Thatta", "cases": 120},
                {"disease": "Hepatitis", "district": "Karachi", "cases": 180},
                {"disease": "Hepatitis", "district": "Larkana", "cases": 95},
                {"disease": "Measles", "district": "Karachi", "cases": 65},
            ]
        )

        kp_districts = pd.DataFrame(
            [
                {"disease": "Malaria", "district": "Peshawar", "cases": 220},
                {"disease": "Malaria", "district": "Mardan", "cases": 145},
                {"disease": "Malaria", "district": "Swat", "cases": 110},
                {"disease": "Dengue Fever", "district": "Peshawar", "cases": 95},
                {"disease": "Dengue Fever", "district": "Swat", "cases": 55},
                {"disease": "Typhoid Fever", "district": "Peshawar", "cases": 42},
                {"disease": "Hepatitis", "district": "Peshawar", "cases": 35},
                {"disease": "Tuberculosis", "district": "Peshawar", "cases": 48},
                {"disease": "CCHF", "district": "Peshawar", "cases": 8},
                {"disease": "CCHF", "district": "Kohat", "cases": 5},
            ]
        )

        return {
            "provincial_summary": prov,
            "lab_confirmed": lab,
            "compliance": comp,
            "district_Sindh": sindh_districts,
            "district_Khyber Pakhtunkhwa": kp_districts,
        }

    def get_bulletin_data(
        self,
        year: int,
        week: int,
    ) -> Dict[str, pd.DataFrame]:
        url = self._build_weekly_url(year, week)
        cache_filename = f"idsr_weekly_{year}_w{week:02d}.pdf"

        try:
            pdf_path = self._pdf.download(url, filename=cache_filename)
        except Exception as e:
            logger.error(f"Failed to download bulletin: {e}")
            return {}

        return self.extract_structured_data(pdf_path, week=week, year=year)
