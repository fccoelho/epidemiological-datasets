"""
China CDC Weekly Data Accessor

This module provides access to surveillance data from China CDC Weekly,
the official publication of the Chinese Center for Disease Control and Prevention.
Includes notifiable infectious diseases, influenza surveillance, and weekly reports.

Supports:
- Scraping volume/issue listings from the website
- Downloading individual article PDFs
- Parsing PDF tables (notifiable disease reports) using pdfplumber
- Parsing HTML tables directly from article pages
- CSV table downloads when available

Data Sources:
- China CDC Weekly: http://weekly.chinacdc.cn/
- Chinese CDC: https://www.chinacdc.cn/
- Notifiable diseases surveillance system
- ILI (Influenza-like Illness) surveillance network

Update Frequency:
- Weekly surveillance reports
- Monthly notifiable disease summaries
- Annual epidemiological reports

License: Open Access (journal articles)

Author: Flávio Codeço Coelho
License: MIT
"""

import io
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import ClassVar

import pandas as pd
import requests
from bs4 import BeautifulSoup

from epidatasets._base import BaseAccessor
from epidatasets.utils.pdf import PDFParser

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_DISEASE_NAME_MAP = {
    "Plague": "Plague",
    "Cholera": "Cholera",
    "SARS-CoV": "SARS",
    "Acquired immune deficiency syndrome": "AIDS",
    "Hepatitis": "Viral_Hepatitis",
    "Hepatitis A": "Viral_Hepatitis_A",
    "Hepatitis B": "Viral_Hepatitis_B",
    "Hepatitis C": "Viral_Hepatitis_C",
    "Hepatitis D": "Viral_Hepatitis_D",
    "Hepatitis E": "Viral_Hepatitis_E",
    "Other hepatitis": "Viral_Hepatitis_Other",
    "Poliomyelitis": "Polio",
    "Human infection with H5N1 virus": "Human_Avian_Influenza",
    "Measles": "Measles",
    "Epidemic hemorrhagic fever": "Epidemic_Hemorrhagic_Fever",
    "Rabies": "Rabies",
    "Japanese encephalitis": "Japanese_Encephalitis",
    "Dengue": "Dengue",
    "Anthrax": "Anthrax",
    "Dysentery": "Dysentery",
    "Tuberculosis": "TB",
    "Typhoid fever and paratyphoid fever": "Typhoid_Paratyphoid",
    "Meningococcal meningitis": "Meningococcal_Meningitis",
    "Pertussis": "Pertussis",
    "Diphtheria": "Diphtheria",
    "Neonatal tetanus": "Neonatal_Tetanus",
    "Scarlet fever": "Scarlet_Fever",
    "Brucellosis": "Brucellosis",
    "Gonorrhea": "Gonorrhea",
    "Syphilis": "Syphilis",
    "Leptospirosis": "Leptospirosis",
    "Schistosomiasis": "Schistosomiasis",
    "Malaria": "Malaria",
    "Human infection with H7N9 virus": "H7N9",
    "Monkey pox": "Monkeypox",
    "Influenza": "Influenza",
    "Mumps": "Mumps",
    "Rubella": "Rubella",
    "Acute hemorrhagic conjunctivitis": "Acute_Hemorrhagic_Conjunctivitis",
    "Leprosy": "Leprosy",
    "Typhus": "Epidemic_Enteritis",
    "Kala azar": "Kala_Azar",
    "Echinococcosis": "Echinococcosis",
    "Filariasis": "Filariasis",
    "Infectious diarrhea": "Infectious_Diarrhea",
    "Hand, foot and mouth disease": "Hand_Foot_Mouth",
    "COVID-19": "COVID_19",
    "Novel coronavirus pneumonia": "COVID_19",
}


class ChinaCDCAccessor(BaseAccessor):
    """
    Accessor for China CDC Weekly surveillance data.

    Provides access to:
    - Notifiable infectious diseases (38 categories)
    - Influenza surveillance (ILI%)
    - Weekly surveillance summaries
    - COVID-19 updates
    - Vaccination coverage data

    Example:
        >>> ccdc = ChinaCDCAccessor()
        >>>
        >>> # Get notifiable diseases
        >>> diseases = ccdc.get_notifiable_diseases(
        ...     diseases=["Influenza", "Dengue"],
        ...     date_range=("2023-01-01", "2023-12-31")
        ... )
        >>>
        >>> # Get influenza surveillance
        >>> flu = ccdc.get_influenza_surveillance(weeks=range(1, 53))
        >>>
        >>> # Get weekly report summaries
        >>> reports = ccdc.get_weekly_reports(year=2023)

    Data Sources:
        - China CDC Weekly: http://weekly.chinacdc.cn/
        - CNIC (Chinese National Influenza Center): http://www.chinacdc.cn/cnic/
    """

    source_name: ClassVar[str] = "china_cdc"
    source_description: ClassVar[str] = (
        "China CDC Weekly surveillance data including notifiable infectious diseases, "
        "influenza surveillance, weekly reports, and COVID-19 updates"
    )
    source_url: ClassVar[str] = "http://weekly.chinacdc.cn"

    BASE_URL = "http://weekly.chinacdc.cn"

    #: CrossRef API endpoint indexing China CDC Weekly (open, no auth).
    CROSSREF_URL = "https://api.crossref.org"
    ISSN = "2097-3101"

    #: Verified open-access PDF URL pattern (DOI-based).
    PDF_URL_TEMPLATE = (
        "https://weekly.chinacdc.cn/en/article/pdf/preview/{doi}.pdf"
    )
    CNIC_URL = "http://www.chinacdc.cn/cnic"

    # Notifiable infectious diseases in China (38 categories)
    NOTIFIABLE_DISEASES = {
        "Plague": {"cn": "鼠疫", "category": "Class A"},
        "Cholera": {"cn": "霍乱", "category": "Class A"},
        "SARS": {"cn": "传染性非典型肺炎", "category": "Class B"},
        "AIDS": {"cn": "艾滋病", "category": "Class B"},
        "Viral_Hepatitis": {"cn": "病毒性肝炎", "category": "Class B"},
        "Polio": {"cn": "脊髓灰质炎", "category": "Class B"},
        "Human_Avian_Influenza": {"cn": "人感染高致病性禽流感", "category": "Class B"},
        "Measles": {"cn": "麻疹", "category": "Class B"},
        "H1N1": {"cn": "甲型H1N1流感", "category": "Class B"},
        "Epidemic_Hemorrhagic_Fever": {"cn": "流行性出血热", "category": "Class B"},
        "Rabies": {"cn": "狂犬病", "category": "Class B"},
        "Japanese_Encephalitis": {"cn": "流行性乙型脑炎", "category": "Class B"},
        "Dengue": {"cn": "登革热", "category": "Class B"},
        "Anthrax": {"cn": "炭疽", "category": "Class B"},
        "TB": {"cn": "肺结核", "category": "Class B"},
        "Meningococcal_Meningitis": {"cn": "流行性脑脊髓膜炎", "category": "Class B"},
        "Pertussis": {"cn": "百日咳", "category": "Class B"},
        "Diphtheria": {"cn": "白喉", "category": "Class B"},
        "Neonatal_Tetanus": {"cn": "新生儿破伤风", "category": "Class B"},
        "Scarlet_Fever": {"cn": "猩红热", "category": "Class B"},
        "Brucellosis": {"cn": "布鲁氏菌病", "category": "Class B"},
        "Gonorrhea": {"cn": "淋病", "category": "Class B"},
        "Syphilis": {"cn": "梅毒", "category": "Class B"},
        "Leptospirosis": {"cn": "钩端螺旋体病", "category": "Class B"},
        "Schistosomiasis": {"cn": "血吸虫病", "category": "Class B"},
        "Malaria": {"cn": "疟疾", "category": "Class B"},
        "H7N9": {"cn": "人感染H7N9禽流感", "category": "Class B"},
        "COVID_19": {"cn": "新型冠状病毒肺炎", "category": "Class B"},
        "Influenza": {"cn": "流行性感冒", "category": "Class C"},
        "Mumps": {"cn": "流行性腮腺炎", "category": "Class C"},
        "Rubella": {"cn": "风疹", "category": "Class C"},
        "Acute_Hemorrhagic_Conjunctivitis": {"cn": "急性出血性结膜炎", "category": "Class C"},
        "Leprosy": {"cn": "麻风病", "category": "Class C"},
        "Epidemic_Enteritis": {"cn": "流行性和地方性斑疹伤寒", "category": "Class C"},
        "Kala_Azar": {"cn": "黑热病", "category": "Class C"},
        "Echinococcosis": {"cn": "包虫病", "category": "Class C"},
        "Filariasis": {"cn": "丝虫病", "category": "Class C"},
        "Infectious_Diarrhea": {"cn": "除霍乱、细菌性和阿米巴性痢疾、伤寒和副伤寒以外的感染性腹泻病", "category": "Class C"},
        "Hand_Foot_Mouth": {"cn": "手足口病", "category": "Class C"},
    }

    # Chinese provinces (31 provinces + municipalities)
    PROVINCES = {
        "BJ": {"name": "Beijing", "cn": "北京市"},
        "TJ": {"name": "Tianjin", "cn": "天津市"},
        "HE": {"name": "Hebei", "cn": "河北省"},
        "SX": {"name": "Shanxi", "cn": "山西省"},
        "NM": {"name": "Inner Mongolia", "cn": "内蒙古自治区"},
        "LN": {"name": "Liaoning", "cn": "辽宁省"},
        "JL": {"name": "Jilin", "cn": "吉林省"},
        "HL": {"name": "Heilongjiang", "cn": "黑龙江省"},
        "SH": {"name": "Shanghai", "cn": "上海市"},
        "JS": {"name": "Jiangsu", "cn": "江苏省"},
        "ZJ": {"name": "Zhejiang", "cn": "浙江省"},
        "AH": {"name": "Anhui", "cn": "安徽省"},
        "FJ": {"name": "Fujian", "cn": "福建省"},
        "JX": {"name": "Jiangxi", "cn": "江西省"},
        "SD": {"name": "Shandong", "cn": "山东省"},
        "HA": {"name": "Henan", "cn": "河南省"},
        "HB": {"name": "Hubei", "cn": "湖北省"},
        "HN": {"name": "Hunan", "cn": "湖南省"},
        "GD": {"name": "Guangdong", "cn": "广东省"},
        "GX": {"name": "Guangxi", "cn": "广西壮族自治区"},
        "HI": {"name": "Hainan", "cn": "海南省"},
        "CQ": {"name": "Chongqing", "cn": "重庆市"},
        "SC": {"name": "Sichuan", "cn": "四川省"},
        "GZ": {"name": "Guizhou", "cn": "贵州省"},
        "YN": {"name": "Yunnan", "cn": "云南省"},
        "XZ": {"name": "Tibet", "cn": "西藏自治区"},
        "SN": {"name": "Shaanxi", "cn": "陕西省"},
        "GS": {"name": "Gansu", "cn": "甘肃省"},
        "QH": {"name": "Qinghai", "cn": "青海省"},
        "NX": {"name": "Ningxia", "cn": "宁夏回族自治区"},
        "XJ": {"name": "Xinjiang", "cn": "新疆维吾尔自治区"},
    }

    def __init__(self, cache_dir: str | None = None):
        if cache_dir is None:
            cache_dir = os.path.join(
                os.path.expanduser("~"), ".cache", "epidatasets", "china_cdc"
            )
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "China-CDC-Accessor/2.0 (Research Purpose)"
                ),
                "Accept": "text/html,application/pdf,application/json,*/*",
                "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
            }
        )
        self._request_timeout = 60
        self._pdf = PDFParser(
            cache_dir=Path(self.cache_dir),
            cache_ttl_days=365,
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "China-CDC-Accessor/2.0 (Research Purpose)"
            ),
            timeout=60,
        )

    # ------------------------------------------------------------------
    # Listing helpers
    # ------------------------------------------------------------------

    def list_notifiable_diseases(self) -> pd.DataFrame:
        data = []
        for code, info in self.NOTIFIABLE_DISEASES.items():
            data.append(
                {
                    "disease_code": code,
                    "disease_name_cn": info["cn"],
                    "category": info["category"],
                }
            )
        return pd.DataFrame(data)

    def list_provinces(self) -> pd.DataFrame:
        data = []
        for code, info in self.PROVINCES.items():
            data.append(
                {
                    "province_code": code,
                    "province_name_en": info["name"],
                    "province_name_cn": info["cn"],
                }
            )
        return pd.DataFrame(data)

    def list_countries(self) -> pd.DataFrame:
        return pd.DataFrame(
            [("CN", "China")],
            columns=["country_code", "country_name"],
        )

    # ------------------------------------------------------------------
    # Volume / issue discovery
    # ------------------------------------------------------------------

    def _crossref_search(
        self,
        query: str | None = None,
        year: int | None = None,
        rows: int = 30,
    ) -> pd.DataFrame:
        """
        Query the CrossRef API for China CDC Weekly articles.

        The journal site renders issue listings client-side, so CrossRef is
        the reliable open route for article discovery (ISSN 2097-3101).

        Args:
            query: Free-text bibliographic query. ``None`` lists recent
                articles.
            year: Optional publication year filter.
            rows: Maximum number of results.

        Returns:
            DataFrame with ``doi``, ``title``, ``journal``, ``year``,
            ``url``, and ``pdf_url`` columns.
        """
        params: dict = {
            "rows": str(min(max(1, rows), 1000)),
            "select": "DOI,title,container-title,issued",
        }
        filters = []
        if year is not None:
            filters.append(f"from-pub-date:{year}-01-01")
            filters.append(f"until-pub-date:{year}-12-31")
        if filters:
            params["filter"] = ",".join(filters)
        if query:
            params["query.bibliographic"] = query

        resp = self._session.get(
            f"{self.CROSSREF_URL}/journals/{self.ISSN}/works",
            params=params,
            timeout=self._request_timeout,
        )
        resp.raise_for_status()
        items = resp.json().get("message", {}).get("items", [])

        records: list[dict] = []
        for item in items:
            doi = item.get("DOI", "")
            issued = item.get("issued", {}).get("date-parts", [[None]])
            pub_year = issued[0][0] if issued and issued[0] else None
            records.append(
                {
                    "doi": doi,
                    "title": (item.get("title") or [""])[0],
                    "journal": (item.get("container-title") or [""])[0],
                    "year": pub_year,
                    "url": f"https://doi.org/{doi}",
                    "pdf_url": self.PDF_URL_TEMPLATE.format(doi=doi),
                }
            )
        logger.info(f"CrossRef returned {len(records)} articles")
        return pd.DataFrame(records)

    def get_volume_issues(self, year: int) -> pd.DataFrame:
        """
        Scrape the list of issues for a given *year* from the China CDC Weekly
        volume page.

        .. deprecated::
            The journal site renders issue listings client-side via
            JavaScript, so this scraper usually finds 0 issues. Article
            discovery is now CrossRef-backed: see :meth:`search_articles`,
            :meth:`get_weekly_reports`, and
            :meth:`find_notifiable_disease_reports`.

        Returns a DataFrame with columns ``issue_no``, ``date``, ``title``,
        ``pdf_url``, ``articles`` (list of dicts with title/doi/url).
        """
        url = f"{self.BASE_URL}/en/zcustom/volume/1/{year}"
        logger.info(f"Fetching volume issues from {url}")
        resp = self._session.get(url, timeout=self._request_timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")

        issues = []
        issue_headers = soup.find_all(
            "strong", class_="catalog-strong"
        )
        if not issue_headers:
            issue_headers = soup.find_all(
                "strong", string=re.compile(r"No\.\s*\d+")
            )

        for header in issue_headers:
            header_text = header.get_text(strip=True)
            dm = re.search(r"(\d{4}-\d{2}-\d{2})", header_text)
            date_str = dm.group(1) if dm else None
            nm = re.search(r"No\.\s*(\d+)", header_text)
            issue_no = int(nm.group(1)) if nm else None

            if issue_no is None:
                continue

            title_parts = [header_text]
            parent = header.parent
            if parent:
                full_text = parent.get_text(strip=True)
                extra = full_text.replace(header_text, "").strip()
                if extra:
                    title_parts.append(extra)
            title_text = " - ".join(title_parts)

            pdf_url = None
            container = header.find_next("a", href=re.compile(r"\.pdf"))
            if container:
                href = container["href"]
                if not href.startswith("http"):
                    href = self.BASE_URL + href
                pdf_url = href

            articles = []
            container = parent if parent else header
            ul = container.find_next("ul")
            if ul:
                for li in ul.find_all("li"):
                    a_tag = li.find("a", href=True)
                    if not a_tag:
                        continue
                    art_title = a_tag.get_text(strip=True)
                    art_href = a_tag["href"].strip()
                    if art_href.startswith("//"):
                        art_href = "http:" + art_href
                    elif not art_href.startswith("http"):
                        art_href = self.BASE_URL + art_href
                    doi_match = re.search(r"doi/(10\.46234/\S+)", art_href)
                    doi = doi_match.group(1) if doi_match else None
                    articles.append(
                        {
                            "title": art_title,
                            "doi": doi,
                            "url": art_href,
                        }
                    )

            issues.append(
                {
                    "year": year,
                    "issue_no": issue_no,
                    "date": date_str,
                    "title": title_text,
                    "pdf_url": pdf_url,
                    "articles": articles,
                }
            )

        logger.info(f"Found {len(issues)} issues for {year}")
        return pd.DataFrame(issues)

    def find_notifiable_disease_reports(
        self, year: int
    ) -> pd.DataFrame:
        """
        Find all *Notifiable Infectious Diseases Reports* published in *year*.

        These are the monthly tables of reported cases and deaths.
        Articles are discovered via CrossRef; PDF URLs use the verified
        DOI-based pattern.
        Returns a DataFrame with ``month``, ``doi``, ``url``, ``pdf_url``.
        """
        articles = self._crossref_search(
            query="Reported Cases and Deaths of National Notifiable "
            "Infectious Diseases",
            year=year,
            rows=60,
        )
        reports = []
        for _, art in articles.iterrows():
            title = str(art.get("title") or "")
            if "Notifiable Infectious Diseases" not in title and not (
                "Reported Cases" in title and "National Notifiable" in title
            ):
                continue
            month_match = re.search(
                r"(January|February|March|April|May|June|July|"
                r"August|September|October|November|December)",
                title,
            )
            month_name = month_match.group(1) if month_match else None
            month_num = None
            if month_name:
                try:
                    dt = datetime.strptime(month_name, "%B")
                    month_num = dt.month
                except ValueError:
                    pass

            reports.append(
                {
                    "year": year,
                    "month": month_num,
                    "month_name": month_name,
                    "title": title,
                    "doi": art.get("doi"),
                    "url": art.get("url"),
                    "pdf_url": art.get("pdf_url"),
                }
            )
        reports.sort(key=lambda r: (r["month"] is None, r["month"]))
        logger.info(
            f"Found {len(reports)} notifiable disease reports for {year}"
        )
        return pd.DataFrame(reports)

    # ------------------------------------------------------------------
    # PDF download
    # ------------------------------------------------------------------

    def download_pdf(
        self,
        url: str,
        filename: str | None = None,
    ) -> Path:
        if filename is None:
            filename = url.rsplit("/", 1)[-1]
            if not filename.endswith(".pdf"):
                filename += ".pdf"
        return self._pdf.download(url, filename=filename)

    # ------------------------------------------------------------------
    # PDF parsing
    # ------------------------------------------------------------------

    @staticmethod
    def parse_pdf_tables(
        pdf_path: str | Path,
        pages: list[int] | None = None,
    ) -> list[pd.DataFrame]:
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        parser = PDFParser()
        extracted = parser.extract_tables(pdf_path, pages=pages)
        if not extracted:
            return []

        tables: list[pd.DataFrame] = []
        for t in extracted:
            df = t.data.dropna(how="all")
            tables.append(df)

        logger.info(
            f"Extracted {len(tables)} table(s) from {pdf_path.name}"
        )
        return tables

    @staticmethod
    def parse_pdf_to_disease_table(
        pdf_path: str | Path,
    ) -> pd.DataFrame:
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        rows = ChinaCDCAccessor._parse_pdf_text_lines(pdf_path)
        if rows:
            return pd.DataFrame(rows, columns=["disease_en", "cases", "deaths", "is_subitem"])

        raw_tables = ChinaCDCAccessor.parse_pdf_tables(pdf_path)
        if raw_tables:
            return ChinaCDCAccessor._normalise_table(raw_tables[0])

        return pd.DataFrame()

    @staticmethod
    def _parse_pdf_text_lines(pdf_path: Path) -> list[dict]:
        parser = PDFParser()
        all_text = parser.extract_text(pdf_path)
        if not all_text:
            return []

        rows: list[dict] = []
        header_seen = False
        for line in all_text.split("\n"):
            line = line.strip()
            if not line:
                continue
            if re.search(r"Diseases?\s+Cases\s+Deaths", line, re.IGNORECASE):
                header_seen = True
                continue
            if not header_seen:
                continue
            if line.lower().startswith("total"):
                continue
            if line.startswith("Copyright") or line.startswith("doi:"):
                break
            if line.startswith("Continued"):
                continue

            m = re.match(
                r"^([\s\u3000]*)(.+?)\s+([\d,]+)\s+([\d,]+)\s*$",
                line,
            )
            if m:
                indent = m.group(1)
                disease = m.group(2).strip().rstrip("†§¶*")
                cases = int(m.group(3).replace(",", ""))
                deaths = int(m.group(4).replace(",", ""))
                rows.append(
                    {
                        "disease_en": disease,
                        "cases": cases,
                        "deaths": deaths,
                        "is_subitem": bool(indent),
                    }
                )

        return rows

    @staticmethod
    def _normalise_table(df: pd.DataFrame) -> pd.DataFrame:
        cols = [c.strip().lower() if isinstance(c, str) else str(c) for c in df.columns]
        disease_col = cases_col = deaths_col = None
        for c in cols:
            if "disease" in c:
                disease_col = df.columns[cols.index(c)]
            elif "case" in c:
                cases_col = df.columns[cols.index(c)]
            elif "death" in c:
                deaths_col = df.columns[cols.index(c)]
        if disease_col is None:
            disease_col = df.columns[0]
        if cases_col is None and len(df.columns) > 1:
            cases_col = df.columns[1]
        if deaths_col is None and len(df.columns) > 2:
            deaths_col = df.columns[2]

        result = pd.DataFrame()
        result["disease_en"] = df[disease_col].astype(str).str.strip().str.rstrip("†§¶*")
        result["is_subitem"] = result["disease_en"].str.startswith(("\u3000", " "))
        result["disease_en"] = result["disease_en"].str.strip("\u3000 ")

        def _to_int(val):
            if pd.isna(val) or val is None:
                return None
            s = str(val).replace(",", "").replace("，", "").strip()
            try:
                return int(s)
            except ValueError:
                return None

        if cases_col is not None:
            result["cases"] = df[cases_col].apply(_to_int)
        if deaths_col is not None:
            result["deaths"] = df[deaths_col].apply(_to_int)

        result = result[
            ~result["disease_en"].str.lower().isin(["total", "disease", "diseases", "nan", ""])
        ]
        return result.reset_index(drop=True)

    # ------------------------------------------------------------------
    # HTML table parsing
    # ------------------------------------------------------------------

    def parse_article_html_tables(
        self, url: str
    ) -> list[pd.DataFrame]:
        """
        Parse all tables from a China CDC Weekly article HTML page.

        Args:
            url: Full URL to the article page.

        Returns:
            List of DataFrames.
        """
        logger.info(f"Parsing HTML tables from {url}")
        resp = self._session.get(url, timeout=self._request_timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")

        tables = soup.find_all("table")
        if not tables:
            return []

        dfs = []
        for table in tables:
            try:
                extracted = pd.read_html(io.StringIO(str(table)), flavor="lxml")
                dfs.extend(extracted)
            except ValueError:
                continue

        logger.info(f"Parsed {len(dfs)} HTML table(s)")
        return dfs

    def parse_notifiable_disease_html(
        self, url: str
    ) -> pd.DataFrame:
        """
        Parse the notifiable-disease table from an article HTML page.

        Returns a DataFrame with ``disease_en``, ``cases``, ``deaths``.
        """
        tables = self.parse_article_html_tables(url)
        if not tables:
            return pd.DataFrame()

        disease_table = None
        for tbl in tables:
            cols_lower = [
                str(c).strip().lower() for c in tbl.columns
            ]
            has_disease = any(
                "disease" in c for c in cols_lower
            )
            has_cases = any("case" in c for c in cols_lower)
            if has_disease and has_cases:
                disease_table = tbl
                break

        if disease_table is None:
            disease_table = tables[0]

        first_col = disease_table.columns[0]
        second_col = disease_table.columns[1] if len(disease_table.columns) > 1 else None
        third_col = disease_table.columns[2] if len(disease_table.columns) > 2 else None

        result = pd.DataFrame()
        result["disease_en"] = disease_table[first_col].astype(str).str.strip()
        result["disease_en"] = result["disease_en"].str.rstrip("†§¶*")
        result["is_subitem"] = result["disease_en"].str.startswith(("\u3000", " "))
        result["disease_en"] = result["disease_en"].str.strip("\u3000 ")

        def _to_int(val):
            if pd.isna(val) or val is None:
                return None
            s = str(val).replace(",", "").replace("，", "").strip()
            try:
                return int(s)
            except ValueError:
                return None

        if second_col is not None:
            result["cases"] = disease_table[second_col].apply(_to_int)
        if third_col is not None:
            result["deaths"] = disease_table[third_col].apply(_to_int)

        result = result[
            ~result["disease_en"].str.lower().isin(
                ["total", "disease", "diseases", "nan", ""]
            )
        ]
        result = result.reset_index(drop=True)
        return result

    # ------------------------------------------------------------------
    # High-level data retrieval (now with actual parsing)
    # ------------------------------------------------------------------

    def get_weekly_reports(
        self,
        year: int,
        week: int | None = None,
    ) -> pd.DataFrame:
        """
        Get metadata for China CDC Weekly articles published in *year*
        (discovered via CrossRef).

        Args:
            year: Publication year (e.g. 2024).
            week: Unused (kept for backwards compatibility); the journal
                publishes articles continuously, not strictly per week.

        Returns:
            DataFrame with ``doi``, ``title``, ``journal``, ``year``,
            ``url``, and ``pdf_url`` columns.
        """
        logger.info(f"Fetching weekly reports for year {year}")
        return self._crossref_search(year=year, rows=60)

    def get_notifiable_diseases(
        self,
        year: int,
        month: int | None = None,
        source: str = "pdf",
    ) -> pd.DataFrame:
        """
        Fetch notifiable infectious disease case/death data for a given year
        by parsing the monthly *Reported Cases and Deaths* articles.

        Args:
            year: Year (e.g. 2024).
            month: Month 1-12. If *None*, fetches all available months.
            source: ``"pdf"`` to download and parse PDFs (recommended; the
                    article HTML renders tables client-side so ``"html"``
                    usually finds no tables).

        Returns:
            DataFrame with columns ``year``, ``month``, ``disease_code``,
            ``disease_en``, ``cases``, ``deaths``, ``source_url``.
        """
        reports = self.find_notifiable_disease_reports(year)
        if reports.empty:
            logger.warning(f"No notifiable disease reports found for {year}")
            return pd.DataFrame()

        if month is not None:
            reports = reports[reports["month"] == month]

        all_data: list[pd.DataFrame] = []

        for _, rpt in reports.iterrows():
            rpt_month = rpt["month"]
            rpt_url = rpt.get("url", "")
            pdf_url = rpt.get("pdf_url")

            try:
                if source == "pdf" and pdf_url:
                    path = self.download_pdf(pdf_url)
                    tbl = self.parse_pdf_to_disease_table(path)
                    src = pdf_url
                elif rpt_url:
                    tbl = self.parse_notifiable_disease_html(rpt_url)
                    src = rpt_url
                else:
                    continue

                if tbl.empty:
                    continue

                tbl["year"] = year
                tbl["month"] = rpt_month
                tbl["disease_code"] = tbl["disease_en"].map(
                    _DISEASE_NAME_MAP
                )
                tbl["source_url"] = src
                all_data.append(tbl)
            except Exception as exc:
                logger.error(
                    f"Failed to parse report for {year}-{rpt_month}: {exc}"
                )

        if not all_data:
            return pd.DataFrame()

        result = pd.concat(all_data, ignore_index=True)
        cols = [
            "year",
            "month",
            "disease_code",
            "disease_en",
            "cases",
            "deaths",
            "is_subitem",
            "source_url",
        ]
        result = result[[c for c in cols if c in result.columns]]
        logger.info(
            f"Retrieved {len(result)} disease records for {year}"
        )
        return result

    def get_influenza_surveillance(
        self,
        weeks: list[int] | None = None,
        year: int | None = None,
        provinces: list[str] | None = None,
    ) -> pd.DataFrame:
        year = year or datetime.now().year
        weeks = weeks or list(range(1, 53))

        logger.info(f"Fetching influenza surveillance for year={year}, weeks={len(weeks)}")

        issues = self.get_volume_issues(year)
        flu_articles = []
        for _, row in issues.iterrows():
            for art in row.get("articles", []):
                title = art.get("title", "")
                if "influenza" in title.lower() and (
                    "surveillance" in title.lower()
                    or "ili" in title.lower()
                ):
                    flu_articles.append(art)

        if flu_articles:
            logger.info(
                f"Found {len(flu_articles)} influenza-related articles"
            )

        data = []
        for week in weeks:
            record = {
                "year": year,
                "week": week,
                "ili_percent": None,
                "ili_cases": None,
                "total_outpatients": None,
                "data_source": "China CDC Weekly / CNIC",
                "note": (
                    "ILI data requires weekly report parsing"
                    if not flu_articles
                    else None
                ),
            }
            data.append(record)

        if not flu_articles:
            logger.warning(
                "Influenza surveillance data requires parsing weekly reports. "
                "CNIC also provides data at http://www.chinacdc.cn/cnic/"
            )
        return pd.DataFrame(data)

    def get_covid_updates(
        self,
        date_range: tuple[str, str] | None = None,
    ) -> pd.DataFrame:
        logger.info("Fetching COVID-19 updates")
        data = []
        record = {
            "date": None,
            "new_cases": None,
            "new_deaths": None,
            "active_cases": None,
            "severe_cases": None,
            "data_source": "China CDC Weekly",
            "note": "COVID-19 data requires weekly report parsing",
        }
        data.append(record)

        logger.warning(
            "COVID-19 data requires parsing China CDC Weekly reports. "
            "For current data, see http://weekly.chinacdc.cn/"
        )
        return pd.DataFrame(data)

    def get_vaccination_coverage(
        self,
        vaccines: list[str],
        year: int | None = None,
    ) -> pd.DataFrame:
        year = year or datetime.now().year
        logger.info(f"Fetching vaccination coverage for {vaccines}, year={year}")

        data = []
        for vaccine in vaccines:
            record = {
                "vaccine": vaccine,
                "year": year,
                "coverage_percent": None,
                "doses_administered_millions": None,
                "target_population_millions": None,
                "data_source": "China CDC Weekly",
                "note": "Vaccination data requires report parsing",
            }
            data.append(record)
        return pd.DataFrame(data)

    def search_articles(
        self,
        query: str,
        year: int | None = None,
    ) -> pd.DataFrame:
        """
        Search for China CDC Weekly articles via the CrossRef API.

        Args:
            query: Free-text query matched against titles/bibliographic data.
            year: Optional publication year filter (default: current year).

        Returns:
            DataFrame with ``title``, ``doi``, ``url``, ``pdf_url``,
            ``journal``, and ``year`` columns.
        """
        logger.info(f"Searching for '{query}' in China CDC Weekly (CrossRef)")

        target_year = year or datetime.now().year
        results = self._crossref_search(query=query, year=target_year)

        if results.empty:
            logger.warning(f"No articles found matching '{query}'")
            return pd.DataFrame(
                [
                    {
                        "title": None,
                        "doi": None,
                        "url": None,
                        "pdf_url": None,
                        "year": target_year,
                        "note": f"No articles found matching '{query}'",
                    }
                ]
            )
        return results

    def parse_weekly_report(
        self,
        year: int,
        week: int,
    ) -> pd.DataFrame:
        """
        Parse a specific weekly issue for disease data tables.

        First tries HTML tables, falls back to PDF parsing.
        """
        logger.info(f"Parsing weekly report for {year} week {week}")

        issues = self.get_volume_issues(year)
        match = issues[issues["issue_no"] == week]
        if match.empty:
            logger.warning(
                f"No issue found for {year} week {week}"
            )
            return pd.DataFrame()

        row = match.iloc[0]
        all_tables: list[pd.DataFrame] = []

        for art in row.get("articles", []):
            art_url = art.get("url", "")
            if not art_url:
                continue
            try:
                tables = self.parse_article_html_tables(art_url)
                for tbl in tables:
                    tbl["year"] = year
                    tbl["week"] = week
                    tbl["article_title"] = art.get("title", "")
                all_tables.extend(tables)
            except Exception as exc:
                logger.debug(f"Skipping article {art_url}: {exc}")

        if all_tables:
            return pd.concat(all_tables, ignore_index=True)
        return pd.DataFrame()

    def get_summary_by_disease(
        self,
        year: int,
    ) -> pd.DataFrame:
        """
        Build an annual summary by aggregating monthly notifiable-disease
        reports parsed from the website.
        """
        logger.info(f"Generating disease summary for {year}")
        monthly = self.get_notifiable_diseases(year)
        if monthly.empty:
            logger.warning(
                f"No monthly data available for {year}; "
                "returning static disease list"
            )
            summary = []
            for disease_code in list(self.NOTIFIABLE_DISEASES.keys())[
                :10
            ]:
                summary.append(
                    {
                        "disease_code": disease_code,
                        "disease_name_cn": self.NOTIFIABLE_DISEASES[
                            disease_code
                        ]["cn"],
                        "category": self.NOTIFIABLE_DISEASES[disease_code][
                            "category"
                        ],
                        "year": year,
                        "total_cases": None,
                        "total_deaths": None,
                        "data_source": "China CDC Weekly",
                        "note": "Summary requires data aggregation",
                    }
                )
            return pd.DataFrame(summary)

        agg = (
            monthly.groupby("disease_code")
            .agg(
                total_cases=("cases", "sum"),
                total_deaths=("deaths", "sum"),
                months_reported=("month", "count"),
            )
            .reset_index()
        )
        agg["year"] = year
        agg["data_source"] = "China CDC Weekly"
        return agg
