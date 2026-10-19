"""
China CDC Data Accessor

Comprehensive accessor for official mainland China surveillance data:

- China CDC Weekly (journal): notifiable infectious disease reports via
  the CrossRef-indexed articles and their PDFs
- CNIC (Chinese National Influenza Center): weekly influenza
  surveillance reports (ILI%, laboratory positivity by type/subtype)
- NDCPA (National Disease Control and Prevention Administration) monthly
  notifiable disease overviews, mirrored on chinacdc.cn, including the
  priority-monitored non-notifiable diseases
- Monthly national COVID-19 situation reports (chinacdc.cn)
- Weekly national sentinel surveillance of acute respiratory infections
  (全国急性呼吸道传染病哨点监测情况): ILI consultation share (national +
  South/North), per-pathogen PCR positivity for outpatients with
  influenza-like illness and hospitalised SARI cases, top-3 pathogens by
  region and age group

Supports:
- Article discovery via the CrossRef API (the journal site is
  JavaScript-rendered)
- Downloading article/report PDFs and parsing their tables (pdfplumber)
- Scraping the server-rendered chinacdc.cn and CNIC listing pages
- Parsing HTML tables directly from article pages

Data Sources:
- China CDC Weekly: http://weekly.chinacdc.cn/
- CNIC weekly reports: https://ivdc.chinacdc.cn/cnic/en/Surveillance/WeeklyReport/
- Monthly notifiable disease overviews: https://www.chinacdc.cn/jksj/jksj01/
- Monthly COVID-19 situation reports: https://www.chinacdc.cn/jksj/xgbdyq/
- Weekly respiratory sentinel surveillance:
  https://www.chinacdc.cn/jksj/jksj04_14275/

Update Frequency:
- CNIC weekly influenza reports
- Weekly respiratory sentinel surveillance (published Thursdays,
  archive from week 46/2024)
- Monthly notifiable disease and COVID-19 summaries
- Annual epidemiological reports

License: Open Access (official government publications)

Author: Flávio Codeço Coelho
License: MIT
"""

import io
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import ClassVar
from urllib.parse import urljoin

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

#: Chinese → English pathogen names used in the weekly national sentinel
#: surveillance of acute respiratory infections
#: (全国急性呼吸道传染病哨点监测情况).
RESPIRATORY_PATHOGEN_MAP: dict[str, str] = {
    "新型冠状病毒": "SARS-CoV-2",
    "流感病毒": "Influenza",
    "呼吸道合胞病毒": "RSV",
    "腺病毒": "Adenovirus",
    "人偏肺病毒": "Human metapneumovirus",
    "副流感病毒": "Parainfluenza",
    "普通冠状病毒": "Seasonal coronavirus",
    "博卡病毒": "Bocavirus",
    "鼻病毒": "Rhinovirus",
    "肠道病毒": "Enterovirus",
    "肺炎支原体": "Mycoplasma pneumoniae",
}

#: Circled rank markers used in the sentinel surveillance top-pathogen
#: tables (①/②/③ = first/second/third most common pathogen).
_SENTINEL_RANK_MARKERS: dict[str, int] = {"①": 1, "②": 2, "③": 3, "④": 4}

#: Age-group labels used in the sentinel surveillance age table
#: (``0～4岁``, ``5～14岁``, ``15～59岁``, ``60岁及以上``).
_SENTINEL_AGE_PATTERN = re.compile(r"^(\d+[～~]\d+岁|\d+岁及以上)$")


class ChinaCDCAccessor(BaseAccessor):
    """
    Accessor for China CDC Weekly surveillance data.

    Provides access to:
    - Notifiable infectious diseases (38 categories)
    - Influenza surveillance (ILI%)
    - Weekly surveillance summaries
    - COVID-19 updates
    - Weekly multi-pathogen respiratory sentinel surveillance
      (ILI consultation share, per-pathogen positivity for ILI and
      SARI syndromes, top-3 pathogens by region and age group)
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
        "Mainland China surveillance data: China CDC Weekly notifiable "
        "disease reports, NDCPA monthly disease overviews (incl. "
        "priority-monitored non-notifiable diseases), CNIC weekly "
        "influenza surveillance, weekly multi-pathogen respiratory "
        "sentinel surveillance (ILI/SARI positivity) and monthly "
        "COVID-19 reports"
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
    #: Chinese National Influenza Center (CNIC) English portal.
    CNIC_URL = "https://ivdc.chinacdc.cn/cnic/en/"
    #: CNIC weekly influenza surveillance report listing (server-rendered).
    CNIC_WEEKLY_REPORTS_URL = (
        "https://ivdc.chinacdc.cn/cnic/en/Surveillance/WeeklyReport/"
    )
    #: National Disease Control and Prevention Administration (NDCPA)
    #: monthly notifiable disease overviews (official portal;
    #: JavaScript-rendered, kept for reference/fallback).
    NDCPA_URL = "https://www.ndcpa.gov.cn/jbkzzx/yqxxxw"
    #: Server-rendered mirror of the monthly notifiable disease overviews
    #: (primary scrape target for :meth:`list_monthly_overviews`).
    NDCPA_MIRROR_URL = "https://www.chinacdc.cn/jksj/jksj01/"
    #: Server-rendered archive of monthly COVID-19 situation reports.
    NDCPA_COVID_MIRROR_URL = "https://www.chinacdc.cn/jksj/xgbdyq/"
    #: Server-rendered archive of the weekly national sentinel
    #: surveillance of acute respiratory infections
    #: (全国急性呼吸道传染病哨点监测情况; weekly, published on Thursdays).
    SENTINEL_MIRROR_URL = "https://www.chinacdc.cn/jksj/jksj04_14275/"

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
        "COVID_19": {"cn": "新型冠状病毒感染", "category": "Class B"},
        "Novel_Subtype_Influenza": {
            "cn": "人感染新亚型流感",
            "category": "Class B",
        },
        "Dysentery": {"cn": "细菌性和阿米巴性痢疾", "category": "Class B"},
        "Monkeypox": {"cn": "猴痘", "category": "Class B"},
        "Chikungunya": {"cn": "基孔肯雅热", "category": "Class B"},
        "SFTS": {"cn": "发热伴血小板减少综合征", "category": "Class B"},
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

    #: Priority-monitored diseases that are **not** part of the statutory
    #: notifiable classes (A/B/C) but are published in the monthly NDCPA
    #: overviews under "重点监测的其他传染病" (published since Jan 2026;
    #: the monitored list may change over time).
    NON_NOTIFIABLE_PRIORITY_DISEASES = {
        "MERS": {"cn": "中东呼吸综合征", "en": "Middle East Respiratory Syndrome"},
        "Ebola": {"cn": "埃博拉出血热", "en": "Ebola Virus Disease"},
        "Zika": {"cn": "寨卡病毒病", "en": "Zika Virus Disease"},
        "Lassa_Fever": {"cn": "拉沙热", "en": "Lassa Fever"},
        "Chickenpox": {"cn": "水痘", "en": "Chickenpox"},
        "Liver_Fluke": {
            "cn": "肝吸虫病",
            "en": "Liver Fluke Disease (Clonorchiasis)",
        },
        "Streptococcus_Suis": {
            "cn": "人感染猪链球菌病",
            "en": "Human Streptococcus Suis Infection",
        },
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

    # ------------------------------------------------------------------
    # CNIC weekly influenza surveillance
    # ------------------------------------------------------------------

    def list_cnic_weekly_reports(
        self,
        year: int | None = None,
        max_pages: int | None = None,
    ) -> pd.DataFrame:
        """
        List CNIC weekly influenza surveillance reports.

        Scrapes the server-rendered English listing at
        :attr:`CNIC_WEEKLY_REPORTS_URL` (paginated ``index_N.htm`` pages).

        Args:
            year: Only include reports published for this year.
            max_pages: Optional cap on the number of listing pages fetched.

        Returns:
            DataFrame with ``year``, ``week``, ``title``, ``report_date``
            and ``url`` columns, sorted by year and week.
        """
        reports: list[dict] = []
        page = 0
        total_pages: int | None = None
        base = self.CNIC_WEEKLY_REPORTS_URL

        while True:
            if max_pages is not None and page >= max_pages:
                break
            url = base if page == 0 else urljoin(base, f"index_{page}.htm")
            resp = self._session.get(url, timeout=self._request_timeout)
            if resp.status_code != 200:
                break
            soup = BeautifulSoup(resp.content, "html.parser")
            items = soup.select("div.erji_list1 ul li")
            if not items:
                break

            reached_older_year = False
            for li in items:
                a_tag = li.select_one("span.span_01 a")
                if a_tag is None:
                    continue
                title = a_tag.get_text(strip=True)
                m = re.search(r"Week\s+(\d+)\s+(\d{4})", title)
                if not m:
                    # e.g. "Overview v1.0" informational entries
                    continue
                week = int(m.group(1))
                rpt_year = int(m.group(2))
                if year is not None:
                    if rpt_year > year:
                        continue
                    if rpt_year < year:
                        reached_older_year = True
                        break
                report_date = None
                date_span = li.select_one("span.span_02")
                if date_span is not None:
                    dm = re.search(
                        r"\((\d{2})-(\d{2})\)",
                        date_span.get_text(strip=True),
                    )
                    if dm:
                        report_date = (
                            f"{rpt_year}-{dm.group(1)}-{dm.group(2)}"
                        )
                reports.append(
                    {
                        "year": rpt_year,
                        "week": week,
                        "title": title,
                        "report_date": report_date,
                        "url": urljoin(url, str(a_tag.get("href", ""))),
                    }
                )

            if reached_older_year:
                break
            if total_pages is None:
                tm = re.search(r"countPage\s*=\s*(\d+)", resp.text)
                total_pages = int(tm.group(1)) if tm else 1
            page += 1
            if page >= total_pages:
                break

        if not reports:
            logger.warning("No CNIC weekly reports found")
            return pd.DataFrame(
                columns=["year", "week", "title", "report_date", "url"]
            )
        df = (
            pd.DataFrame(reports)
            .drop_duplicates(subset=["year", "week"])
            .sort_values(["year", "week"])
            .reset_index(drop=True)
        )
        logger.info(f"Found {len(df)} CNIC weekly reports")
        return df

    def _fetch_cnic_report_details(self, url: str) -> dict:
        """
        Fetch a CNIC weekly report landing page and extract metadata.

        Returns a dict with ``title``, ``period``, ``published_date``,
        ``pdf_url``, ``pdf_name`` and ``summary`` keys.
        """
        resp = self._session.get(url, timeout=self._request_timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")

        h3 = soup.find("h3")
        title = h3.get_text(strip=True) if h3 is not None else None

        page_text = soup.get_text("\n", strip=True)

        period = None
        pm = re.search(
            r"([A-Z][a-z]+ \d+(?:\s+to\s+\d+)?,\s*\d{4}\s*\(Week\s*\d+\))",
            page_text,
        )
        if pm:
            period = re.sub(r"\s+", " ", pm.group(1))

        published_date = None
        dm = re.search(r"Date time[：:]\s*(\d{4}-\d{2}-\d{2})", page_text)
        if dm:
            published_date = dm.group(1)

        pdf_url = None
        pdf_name = None
        for a_tag in soup.find_all("a", href=True):
            href = str(a_tag.get("href", ""))
            if ".pdf" in href.lower():
                pdf_url = urljoin(url, href)
                pdf_name = a_tag.get_text(strip=True) or None
                break

        summary = None
        summary_div = soup.select_one("div.trs_editor_view")
        if summary_div is not None:
            summary = re.sub(
                r"\s+", " ", summary_div.get_text(" ", strip=True)
            )
        return {
            "title": title,
            "period": period,
            "published_date": published_date,
            "pdf_url": pdf_url,
            "pdf_name": pdf_name,
            "summary": summary,
        }

    @staticmethod
    def parse_cnic_weekly_pdf(pdf_path: str | Path) -> dict:
        """
        Parse a CNIC weekly influenza surveillance report PDF.

        Extracts the sentinel ILI consultation percentages for the
        southern and northern provinces, the laboratory surveillance
        totals, the Table 1 type/subtype breakdown and the ILI outbreak
        count from the report text layer.

        Args:
            pdf_path: Path to a downloaded CNIC weekly report PDF.

        Returns:
            Dict of extracted values; keys are ``None`` when absent.
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        text = PDFParser().extract_text(pdf_path)
        result: dict = {
            "week": None,
            "year": None,
            "period": None,
            "ili_percent_south": None,
            "ili_percent_north": None,
            "ili_percent_last_week_south": None,
            "ili_percent_last_week_north": None,
            "specimens_tested_south": None,
            "specimens_tested_north": None,
            "specimens_tested_total": None,
            "positive_south": None,
            "positivity_south": None,
            "positive_north": None,
            "positivity_north": None,
            "positive_total": None,
            "positivity_total": None,
            "by_type": {},
            "ili_outbreaks": None,
        }

        pm = re.search(
            r"([A-Z][a-z]+ \d+(?:\s+to\s+\d+)?,\s*(\d{4}))\s*"
            r"\(Week\s*(\d+)\)",
            text,
        )
        if pm:
            result["period"] = re.sub(r"\s+", " ", pm.group(1))
            result["year"] = int(pm.group(2))
            result["week"] = int(pm.group(3))
        wm = re.search(
            r"Surveillance Report\s*\|\s*Week\s*(\d+)", text
        )
        if result["week"] is None and wm:
            result["week"] = int(wm.group(1))

        def _region_ili(region: str) -> tuple[float | None, float | None]:
            m = re.search(
                rf"in {region} provinces was\s+([\d.]+)%"
                rf"(.*?)(?=During week|Figure \d+\.|\Z)",
                text,
                re.DOTALL,
            )
            if m is None:
                return None, None
            current = float(m.group(1))
            last = None
            lm = re.search(
                r"than the last\s+week\s*\(([\d.]+)%\)", m.group(2)
            )
            if lm:
                last = float(lm.group(1))
            return current, last

        (
            result["ili_percent_south"],
            result["ili_percent_last_week_south"],
        ) = _region_ili("southern")
        (
            result["ili_percent_north"],
            result["ili_percent_last_week_north"],
        ) = _region_ili("northern")

        om = re.search(
            r"There (?:were|was)\s+(\d+)\s+ILI outbreaks", text
        )
        if om:
            result["ili_outbreaks"] = int(om.group(1))

        # Table 1 (text layer): three cells per row; each cell is either
        # a plain count or ``count(percent%)`` (the closing paren may be
        # full-width).
        cell = r"([\d,]+)(?:\(([\d.]+)%[)）])?"

        sm = re.search(
            r"No\.\s*of specimens tested\s+([\d,]+)\s+([\d,]+)"
            r"\s+([\d,]+)\s*$",
            text,
            re.MULTILINE,
        )
        if sm:
            result["specimens_tested_south"] = int(
                sm.group(1).replace(",", "")
            )
            result["specimens_tested_north"] = int(
                sm.group(2).replace(",", "")
            )
            result["specimens_tested_total"] = int(
                sm.group(3).replace(",", "")
            )

        posm = re.search(
            rf"No\.\s*of positive specimens\s*(?:\(%\))?\s+"
            rf"{cell}\s+{cell}\s+{cell}\s*$",
            text,
            re.MULTILINE,
        )
        if posm:
            for key, count, pct in (
                ("south", posm.group(1), posm.group(2)),
                ("north", posm.group(3), posm.group(4)),
                ("total", posm.group(5), posm.group(6)),
            ):
                result[f"positive_{key}"] = int(count.replace(",", ""))
                result[f"positivity_{key}"] = (
                    float(pct) if pct else None
                )

        labels = [
            "Influenza A",
            "Influenza B",
            "A(H1N1)pdm09",
            "A(H3N2)",
            "A (subtype not determined)",
            "B (lineage not determined)",
            "Victoria",
            "Yamagata",
        ]
        for label in labels:
            m = re.search(
                rf"^{re.escape(label)}\s+{cell}\s+{cell}\s+{cell}\s*$",
                text,
                re.MULTILINE,
            )
            if m is None:
                continue
            result["by_type"][label] = {
                "south_count": int(m.group(1).replace(",", "")),
                "south_pct": float(m.group(2)) if m.group(2) else None,
                "north_count": int(m.group(3).replace(",", "")),
                "north_pct": float(m.group(4)) if m.group(4) else None,
                "total_count": int(m.group(5).replace(",", "")),
                "total_pct": float(m.group(6)) if m.group(6) else None,
            }

        return result

    def get_influenza_surveillance(
        self,
        weeks: list[int] | None = None,
        year: int | None = None,
        provinces: list[str] | None = None,
    ) -> pd.DataFrame:
        """
        Get weekly influenza surveillance data for mainland China from the
        Chinese National Influenza Center (CNIC).

        For each weekly report the landing page is scraped for the PDF
        link; the PDF is downloaded (TTL-cached) and parsed for sentinel
        ILI% (southern/northern provinces), laboratory detections and
        positivity, and ILI outbreak counts.

        Args:
            weeks: Optional list of surveillance week numbers (1-53).
            year: Year of the reports (default: current year).
            provinces: Optional region filter — ``"south"``/``"southern"``
                and/or ``"north"``/``"northern"``. Restricts the ILI
                columns returned to the requested regions.

        Returns:
            DataFrame with one row per weekly report: ``year``, ``week``,
            ``period``, ``ili_percent_south``, ``ili_percent_north``,
            ``ili_percent_last_week_south/north``, ``specimens_tested``,
            ``positive_detections``, ``positivity_rate``, ``ili_outbreaks``,
            ``by_type`` (dict with the Table 1 breakdown), ``summary``,
            ``report_url``, ``pdf_url``, ``data_source`` and ``note``.
        """
        year = year or datetime.now().year
        week_filter = set(weeks) if weeks else None
        region_filter = (
            {str(p).lower() for p in provinces} if provinces else None
        )

        logger.info(f"Fetching CNIC influenza surveillance for year={year}")
        listings = self.list_cnic_weekly_reports(year=year)
        if listings.empty:
            return pd.DataFrame()

        rows: list[dict] = []
        for _, rpt in listings.iterrows():
            if week_filter is not None and rpt["week"] not in week_filter:
                continue
            row = {
                "year": rpt["year"],
                "week": rpt["week"],
                "period": None,
                "ili_percent_south": None,
                "ili_percent_north": None,
                "ili_percent_last_week_south": None,
                "ili_percent_last_week_north": None,
                "specimens_tested": None,
                "positive_detections": None,
                "positivity_rate": None,
                "ili_outbreaks": None,
                "by_type": None,
                "summary": None,
                "report_url": rpt["url"],
                "pdf_url": None,
                "data_source": "CNIC (Chinese National Influenza Center)",
                "note": None,
            }
            try:
                details = self._fetch_cnic_report_details(rpt["url"])
                row["period"] = details.get("period")
                row["summary"] = details.get("summary")
                row["pdf_url"] = details.get("pdf_url")
                if not details.get("pdf_url"):
                    row["note"] = "no PDF link on report page"
                    rows.append(row)
                    continue
                path = self.download_pdf(details["pdf_url"])
                parsed = self.parse_cnic_weekly_pdf(path)
                if row["period"] is None:
                    row["period"] = parsed.get("period")
                for key in (
                    "ili_percent_south",
                    "ili_percent_north",
                    "ili_percent_last_week_south",
                    "ili_percent_last_week_north",
                    "ili_outbreaks",
                    "by_type",
                ):
                    row[key] = parsed.get(key)
                row["specimens_tested"] = parsed.get(
                    "specimens_tested_total"
                )
                row["positive_detections"] = parsed.get("positive_total")
                row["positivity_rate"] = parsed.get("positivity_total")
            except Exception as exc:
                logger.error(
                    f"Failed to parse CNIC report {rpt['year']} week "
                    f"{rpt['week']}: {exc}"
                )
                row["note"] = f"parsing failed: {exc}"
            rows.append(row)

        df = pd.DataFrame(rows)
        if df.empty or region_filter is None:
            return df

        keep_south = bool(region_filter & {"south", "southern"})
        keep_north = bool(region_filter & {"north", "northern"})
        drop_cols = []
        if not keep_south:
            drop_cols += [c for c in df.columns if c.endswith("_south")]
        if not keep_north:
            drop_cols += [c for c in df.columns if c.endswith("_north")]
        return df.drop(columns=drop_cols)

    # ------------------------------------------------------------------
    # NDCPA monthly notifiable disease overviews
    # ------------------------------------------------------------------

    #: Section subtotal rows in the monthly overview tables, mapped to
    #: normalized scope names.
    OVERVIEW_SECTION_HEADERS = {
        "甲乙丙类传染病总计": "notifiable_total",
        "甲乙类传染病合计": "class_ab_subtotal",
        "丙类传染病合计": "class_c_subtotal",
        "重点监测的其他传染病合计": "monitored_subtotal",
    }

    #: Disease codes reported as sub-rows of an aggregate disease (e.g.
    #: the hepatitis types under 病毒性肝炎).
    SUBITEM_DISEASE_CODES = frozenset(
        {
            "Viral_Hepatitis_A",
            "Viral_Hepatitis_B",
            "Viral_Hepatitis_C",
            "Viral_Hepatitis_D",
            "Viral_Hepatitis_E",
            "Viral_Hepatitis_Other",
        }
    )

    def _scrape_chinacdc_listing(
        self,
        base_url: str,
        year: int | None = None,
        max_pages: int | None = None,
        period_pattern: str = r"(\d{4})年(\d{1,2})月",
        period_columns: tuple[str, str] = ("year", "month"),
    ) -> pd.DataFrame:
        """
        Scrape a chinacdc.cn ``健康数据`` listing page.

        The monthly notifiable disease overviews, the monthly COVID-19
        situation reports and the weekly respiratory sentinel surveillance
        share the same listing layout (``ul.xw_list`` entries,
        ``index_N.html`` pagination). Entry titles contain the report
        period as ``YYYY年M月`` (monthly sections) or
        ``YYYY年第N周`` (weekly sections).

        Args:
            base_url: Listing URL (e.g. :attr:`NDCPA_MIRROR_URL`).
            year: Only include entries for this year.
            max_pages: Optional cap on listing pages fetched.
            period_pattern: Regex with two capture groups (period, number)
                matched against the entry title to extract the report
                period.
            period_columns: Names for the two period columns derived from
                ``period_pattern`` (e.g. ``("year", "month")`` or
                ``("year", "week")``).

        Returns:
            DataFrame with the two period columns plus ``title``,
            ``published_date`` and ``url``, sorted by period.
        """
        entries: list[dict] = []
        page = 0

        while True:
            if max_pages is not None and page >= max_pages:
                break
            url = (
                base_url
                if page == 0
                else urljoin(base_url, f"index_{page}.html")
            )
            resp = self._session.get(url, timeout=self._request_timeout)
            if resp.status_code != 200:
                break
            soup = BeautifulSoup(resp.content, "html.parser")
            links = soup.select("ul.xw_list li dl dd a[href]")
            if not links:
                break

            reached_older_year = False
            for a_tag in links:
                title = a_tag.get_text(" ", strip=True)
                published_date = None
                date_span = a_tag.find("span")
                if date_span is not None:
                    span_text = date_span.get_text(strip=True)
                    dm = re.search(r"(\d{4}-\d{2}-\d{2})", span_text)
                    if dm:
                        published_date = dm.group(1)
                    title = title.replace(span_text, " ").strip()
                ym = re.search(period_pattern, title)
                if ym is None:
                    continue
                entry_year = int(ym.group(1))
                if year is not None:
                    if entry_year > year:
                        continue
                    if entry_year < year:
                        reached_older_year = True
                        break
                entries.append(
                    {
                        period_columns[0]: entry_year,
                        period_columns[1]: int(ym.group(2)),
                        "title": title,
                        "published_date": published_date,
                        "url": urljoin(url, str(a_tag["href"])),
                    }
                )

            if reached_older_year:
                break
            page += 1
            if f"index_{page}.html" not in resp.text:
                break

        if not entries:
            logger.warning(f"No listing entries found at {base_url}")
            return pd.DataFrame(
                columns=[
                    *period_columns,
                    "title",
                    "published_date",
                    "url",
                ]
            )
        df = (
            pd.DataFrame(entries)
            .drop_duplicates(subset=list(period_columns))
            .sort_values(list(period_columns))
            .reset_index(drop=True)
        )
        logger.info(f"Found {len(df)} listing entries at {base_url}")
        return df

    def list_monthly_overviews(
        self,
        year: int | None = None,
        max_pages: int | None = None,
    ) -> pd.DataFrame:
        """
        List the monthly national notifiable infectious disease overviews
        (全国法定传染病疫情概况).

        Uses the server-rendered chinacdc.cn mirror of the NDCPA monthly
        overviews (see :attr:`NDCPA_MIRROR_URL`; the official NDCPA
        portal at :attr:`NDCPA_URL` renders client-side).

        Args:
            year: Only include overviews for this year.
            max_pages: Optional cap on listing pages fetched.

        Returns:
            DataFrame with ``year``, ``month``, ``title``,
            ``published_date`` and ``url`` columns.
        """
        logger.info("Listing monthly notifiable disease overviews")
        df = self._scrape_chinacdc_listing(
            self.NDCPA_MIRROR_URL, year=year, max_pages=max_pages
        )
        logger.info(f"Found {len(df)} monthly overviews")
        return df

    @staticmethod
    def _clean_overview_label(label: str) -> str:
        """Normalize a table label (strip indentation and footnote digits)."""
        label = label.replace("\u3000", " ").strip()
        label = re.sub(r"[\d\s]+$", "", label)
        return label.strip()

    @staticmethod
    def _overview_to_int(val) -> int | None:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        s = str(val).replace(",", "").replace("，", "").strip()
        try:
            return int(s)
        except ValueError:
            return None

    def _parse_overview_page(
        self, url: str
    ) -> tuple[list[dict], dict]:
        """
        Fetch a monthly overview page and extract the per-disease table.

        Handles both real HTML tables and TRS-editor text layouts.

        Returns:
            Tuple of ``(records, summary)`` where *records* are
            disease-level dicts (``disease_cn``, ``cases``, ``deaths``,
            ``section``) and *summary* maps scope names to
            ``{"cases", "deaths"}`` subtotals.
        """
        resp = self._session.get(url, timeout=self._request_timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")

        triplets: list[tuple[str, str, str]] = []

        # 1) real HTML tables
        dfs: list[pd.DataFrame] = []
        for table in soup.find_all("table"):
            try:
                dfs.extend(
                    pd.read_html(io.StringIO(str(table)), flavor="lxml")
                )
            except ValueError:
                continue

        target = None
        for df in dfs:
            cols_text = " ".join(str(c) for c in df.columns)
            first_col = df.iloc[:, 0].astype(str)
            if "病名" in cols_text or first_col.str.contains("鼠疫").any():
                target = df
                break

        if target is not None:
            for _, r in target.iterrows():
                cells = [str(c).strip() for c in r.tolist()]
                if len(cells) < 3 or cells[0] in ("", "nan"):
                    continue
                if "病名" in cells[0] or "发病数" in cells[0]:
                    continue
                triplets.append((cells[0], cells[1], cells[2]))
        else:
            # 2) text-line fallback (values on consecutive lines)
            lines = [
                ln.strip()
                for ln in soup.get_text("\n", strip=True).split("\n")
                if ln.strip()
            ]
            n = len(lines)
            i = 0
            numeric = re.compile(r"^[\d,]+$")
            while i < n:
                name = self._clean_overview_label(lines[i])
                if (
                    name
                    and not numeric.fullmatch(name)
                    and re.search(r"[\u4e00-\u9fff]", name)
                    and len(name) <= 40
                    and i + 2 < n
                    and numeric.fullmatch(lines[i + 1])
                    and numeric.fullmatch(lines[i + 2])
                ):
                    triplets.append((lines[i], lines[i + 1], lines[i + 2]))
                    i += 3
                else:
                    i += 1

        records: list[dict] = []
        summary: dict = {}
        section: str | None = None
        for name_raw, cases_raw, deaths_raw in triplets:
            name = self._clean_overview_label(name_raw)
            section_key = self.OVERVIEW_SECTION_HEADERS.get(name)
            if section_key:
                summary[section_key] = {
                    "cases": self._overview_to_int(cases_raw),
                    "deaths": self._overview_to_int(deaths_raw),
                }
                section = section_key
                continue
            if not re.search(r"[\u4e00-\u9fff]", name):
                continue
            records.append(
                {
                    "disease_code": _CN_NAME_TO_CODE.get(name, name),
                    "disease_cn": name,
                    "cases": self._overview_to_int(cases_raw),
                    "deaths": self._overview_to_int(deaths_raw),
                    "section": section,
                }
            )
        return records, summary

    def get_monthly_overview(self, year: int, month: int) -> pd.DataFrame:
        """
        Get the official per-disease monthly notifiable disease table for
        mainland China (NDCPA monthly overview, via the chinacdc.cn
        mirror).

        Includes the statutory Class A/B/C diseases plus, when published,
        the priority-monitored non-notifiable diseases (see
        :attr:`NON_NOTIFIABLE_PRIORITY_DISEASES`).

        Args:
            year: Year (e.g. 2026).
            month: Month (1-12).

        Returns:
            DataFrame with columns ``year``, ``month``, ``disease_code``,
            ``disease_cn``, ``cases``, ``deaths``, ``category``,
            ``is_subitem`` and ``source_url``. ``disease_code`` falls back
            to the Chinese name for diseases outside the known maps.
        """
        listings = self.list_monthly_overviews(year)
        if listings.empty:
            return pd.DataFrame()
        match = listings[listings["month"] == month]
        if match.empty:
            logger.warning(
                f"No monthly overview found for {year}-{month:02d}"
            )
            return pd.DataFrame()

        url = match.iloc[0]["url"]
        records, _summary = self._parse_overview_page(url)
        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        df["year"] = year
        df["month"] = month

        def _category(row) -> str | None:
            info = self.NOTIFIABLE_DISEASES.get(row["disease_code"])
            if info is not None:
                return info["category"]
            return {
                "class_ab_subtotal": "Class B",
                "class_c_subtotal": "Class C",
                "monitored_subtotal": "Monitored (non-notifiable)",
            }.get(row["section"])

        df["category"] = df.apply(_category, axis=1)
        df["is_subitem"] = df["disease_code"].isin(
            self.SUBITEM_DISEASE_CODES
        )
        df["source_url"] = url
        cols = [
            "year",
            "month",
            "disease_code",
            "disease_cn",
            "cases",
            "deaths",
            "category",
            "is_subitem",
            "source_url",
        ]
        logger.info(f"Parsed {len(df)} disease rows for {year}-{month:02d}")
        return df[cols]

    def get_monthly_summary(self, year: int, month: int) -> pd.DataFrame:
        """
        Get the summary of a monthly notifiable disease overview: totals
        and subtotals per scope plus the most reported diseases.

        Args:
            year: Year (e.g. 2026).
            month: Month (1-12).

        Returns:
            DataFrame with one row per scope (``notifiable_total``,
            ``class_ab``, ``class_c``, ``monitored``) and columns
            ``cases``, ``deaths`` and ``top_diseases`` (Chinese names of
            the most reported diseases in that scope, when applicable).
        """
        listings = self.list_monthly_overviews(year)
        if listings.empty:
            return pd.DataFrame()
        match = listings[listings["month"] == month]
        if match.empty:
            return pd.DataFrame()

        url = match.iloc[0]["url"]
        records, summary = self._parse_overview_page(url)
        records_df = pd.DataFrame(records)

        def _top_diseases(scope: str, n: int) -> str | None:
            if records_df.empty:
                return None
            sec = f"{scope}_subtotal"
            rows = records_df[records_df["section"] == sec]
            # exclude subtype sub-rows (e.g. hepatitis types) so only
            # top-level diseases are ranked
            rows = rows[~rows["disease_code"].isin(self.SUBITEM_DISEASE_CODES)]
            rows = rows.sort_values("cases", ascending=False).head(n)
            if rows.empty:
                return None
            return "、".join(rows["disease_cn"].tolist())

        scopes = [
            ("notifiable_total", summary.get("notifiable_total"), None, 0),
            ("class_ab", summary.get("class_ab_subtotal"), "class_ab_subtotal", 5),
            ("class_c", summary.get("class_c_subtotal"), "class_c_subtotal", 3),
            (
                "monitored",
                summary.get("monitored_subtotal"),
                "monitored_subtotal",
                0,
            ),
        ]
        rows_out = []
        for scope, totals, _section, top_n in scopes:
            if totals is None:
                continue
            rows_out.append(
                {
                    "year": year,
                    "month": month,
                    "scope": scope,
                    "cases": totals.get("cases"),
                    "deaths": totals.get("deaths"),
                    "top_diseases": (
                        _top_diseases(scope, top_n) if top_n else None
                    ),
                    "source_url": url,
                }
            )
        return pd.DataFrame(rows_out)

    def get_annual_summary(self, year: int) -> pd.DataFrame:
        """
        Build an annual summary of notifiable diseases by aggregating all
        available monthly overviews for *year*.

        Returns:
            DataFrame with ``disease_code``, ``disease_cn``,
            ``category``, ``total_cases``, ``total_deaths`` and
            ``months_reported``.
        """
        logger.info(f"Building annual overview summary for {year}")
        listings = self.list_monthly_overviews(year)
        if listings.empty:
            logger.warning(f"No monthly overviews available for {year}")
            return pd.DataFrame()

        frames: list[pd.DataFrame] = []
        for _, rpt in listings.iterrows():
            try:
                records, _summary = self._parse_overview_page(rpt["url"])
            except Exception as exc:
                logger.error(
                    f"Failed to parse overview for {year}-"
                    f"{rpt['month']:02d}: {exc}"
                )
                continue
            if records:
                frames.append(pd.DataFrame(records))

        if not frames:
            return pd.DataFrame()

        monthly = pd.concat(frames, ignore_index=True)
        agg = (
            monthly.groupby(["disease_code", "disease_cn"], dropna=False)
            .agg(
                total_cases=("cases", "sum"),
                total_deaths=("deaths", "sum"),
                months_reported=("disease_cn", "count"),
            )
            .reset_index()
        )

        def _category(code) -> str | None:
            info = self.NOTIFIABLE_DISEASES.get(code)
            if info is not None:
                return info["category"]
            return "Monitored (non-notifiable)"

        agg["category"] = agg["disease_code"].apply(_category)
        agg["year"] = year
        return agg[
            [
                "year",
                "disease_code",
                "disease_cn",
                "category",
                "total_cases",
                "total_deaths",
                "months_reported",
            ]
        ]

    # ------------------------------------------------------------------
    # Monthly COVID-19 situation reports
    # ------------------------------------------------------------------

    def list_covid_monthly_reports(
        self,
        year: int | None = None,
        max_pages: int | None = None,
    ) -> pd.DataFrame:
        """
        List the monthly national COVID-19 situation reports
        (全国新型冠状病毒感染疫情情况) published on chinacdc.cn.

        Args:
            year: Only include reports for this year.
            max_pages: Optional cap on listing pages fetched.

        Returns:
            DataFrame with ``year``, ``month``, ``title``,
            ``published_date`` and ``url`` columns.
        """
        logger.info("Listing monthly COVID-19 situation reports")
        return self._scrape_chinacdc_listing(
            self.NDCPA_COVID_MIRROR_URL, year=year, max_pages=max_pages
        )

    @staticmethod
    def _extract_cn_count(pattern: str, text: str) -> int | None:
        """
        Extract a Chinese-language count (supporting ``万`` myriads, e.g.
        ``7.9万``) from *text* using *pattern* with one capture group.
        """
        m = re.search(pattern, text)
        if m is None:
            return None
        val = m.group(1)
        try:
            num = float(val.replace("万", ""))
        except ValueError:
            return None
        return int(num * 10000) if "万" in val else int(num)

    def get_covid_updates(
        self,
        date_range: tuple[str, str] | None = None,
    ) -> pd.DataFrame:
        """
        Get the monthly national COVID-19 situation reports from China CDC
        (chinacdc.cn).

        Each monthly report is scraped for the headline counts: new
        confirmed cases, severe cases and deaths. Reported values using
        the ``万`` (10k) unit are converted to absolute counts.

        Args:
            date_range: Optional ``(start, end)`` date strings
                (``YYYY-MM-DD``) filtering on the publication dates.

        Returns:
            DataFrame with ``year``, ``month``, ``new_cases``,
            ``severe_cases``, ``new_deaths``, ``title``, ``url``,
            ``data_source`` and ``note``. Values are ``None`` when not
            stated in the report text.
        """
        logger.info("Fetching monthly COVID-19 updates from chinacdc.cn")
        listings = self._scrape_chinacdc_listing(
            self.NDCPA_COVID_MIRROR_URL
        )
        if listings.empty:
            logger.warning("No monthly COVID-19 reports found")
            return pd.DataFrame()

        if date_range is not None:
            start, end = date_range
            published = pd.to_datetime(
                listings["published_date"], errors="coerce"
            )
            listings = listings[
                (published >= pd.Timestamp(start))
                & (published <= pd.Timestamp(end))
            ]
            if listings.empty:
                return pd.DataFrame()

        rows: list[dict] = []
        for _, rpt in listings.iterrows():
            row = {
                "year": rpt["year"],
                "month": rpt["month"],
                "new_cases": None,
                "severe_cases": None,
                "new_deaths": None,
                "title": rpt["title"],
                "url": rpt["url"],
                "data_source": "China CDC (chinacdc.cn)",
                "note": None,
            }
            try:
                resp = self._session.get(
                    rpt["url"], timeout=self._request_timeout
                )
                resp.raise_for_status()
                soup = BeautifulSoup(resp.content, "html.parser")
                # headline numbers sit in separate tags (e.g. styled
                # spans), so strip all whitespace before matching
                text = re.sub(r"\s+", "", soup.get_text())
                row["new_cases"] = self._extract_cn_count(
                    r"新增确诊病例([\d.]+万?)例", text
                )
                row["severe_cases"] = self._extract_cn_count(
                    r"重症病例([\d.]+万?)例", text
                )
                row["new_deaths"] = self._extract_cn_count(
                    r"死亡病例([\d.]+万?)例", text
                )
                if row["new_cases"] is None:
                    row["note"] = "headline counts not found in report text"
            except Exception as exc:
                logger.error(
                    f"Failed to parse COVID report {rpt['year']}-"
                    f"{rpt['month']:02d}: {exc}"
                )
                row["note"] = f"parsing failed: {exc}"
            rows.append(row)

        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Weekly sentinel surveillance of acute respiratory infections
    # ------------------------------------------------------------------

    def list_respiratory_sentinel_reports(
        self,
        year: int | None = None,
        max_pages: int | None = None,
    ) -> pd.DataFrame:
        """
        List the weekly national sentinel surveillance reports of acute
        respiratory infections (全国急性呼吸道传染病哨点监测情况).

        Scrapes the server-rendered chinacdc.cn archive at
        :attr:`SENTINEL_MIRROR_URL` (paginated ``index_N.html`` pages).
        Reports are published weekly, on Thursdays; the archive reaches
        back to week 46/2024.

        Args:
            year: Only include reports for this year.
            max_pages: Optional cap on listing pages fetched.

        Returns:
            DataFrame with ``year``, ``week``, ``title``, ``publish_date``
            and ``url`` columns, sorted by year/week.
        """
        logger.info(
            "Listing weekly respiratory sentinel surveillance reports"
        )
        df = self._scrape_chinacdc_listing(
            self.SENTINEL_MIRROR_URL,
            year=year,
            max_pages=max_pages,
            period_pattern=r"(\d{4})年第(\d{1,2})周",
            period_columns=("year", "week"),
        )
        return df.rename(columns={"published_date": "publish_date"})

    def _fetch_html_cached(
        self,
        url: str,
        cache_name: str,
        ttl_hours: float = 24.0,
    ) -> bytes:
        """
        Fetch a page with a simple filesystem cache under
        :attr:`cache_dir` (TTL in hours; chinacdc.cn articles are
        immutable once published, the TTL only bounds re-validation).
        """
        cache_path = Path(self.cache_dir) / cache_name
        if cache_path.exists() and (
            time.time() - cache_path.stat().st_mtime
        ) < ttl_hours * 3600:
            logger.debug(f"Cache hit: {cache_path.name}")
            return cache_path.read_bytes()
        resp = self._session.get(url, timeout=self._request_timeout)
        resp.raise_for_status()
        cache_path.write_bytes(resp.content)
        return resp.content

    def _get_sentinel_article_url(self, year: int, week: int) -> str:
        """
        Resolve the article URL for a given surveillance year/week from
        the listing (article URLs embed an opaque numeric id, so they are
        always resolved rather than constructed).
        """
        reports = self.list_respiratory_sentinel_reports(year=year)
        if reports.empty:
            raise ValueError(
                f"No respiratory sentinel reports found for {year}"
            )
        match = reports[reports["week"] == week]
        if match.empty:
            raise ValueError(
                f"No respiratory sentinel report found for "
                f"{year} week {week}"
            )
        return str(match.iloc[0]["url"])

    @staticmethod
    def _sentinel_to_float(val: str | None) -> float | None:
        """Parse a sentinel table value (``+2.4``/``-1.6``/``0``/``''``)."""
        if val is None:
            return None
        val = val.strip().replace("+", "")
        if not val:
            return None
        try:
            return float(val)
        except ValueError:
            return None

    @staticmethod
    def _split_cell_groups(
        cells: list[str],
    ) -> tuple[list[str], list[str]]:
        """
        Split a sentinel table row's value cells into the outpatient
        ILI and hospitalised SARI halves. The halves are separated by an
        empty spacer cell; when the spacer is absent, the row is split
        in half. Empty cells (missing values) stay ``NaN``-mapped later.
        """
        for i, cell in enumerate(cells):
            if cell == "":
                return cells[:i], cells[i + 1 :]
        half = (len(cells) + 1) // 2
        return cells[:half], cells[half:]

    @staticmethod
    def _split_ranked_pathogen(text: str) -> tuple[int | None, str]:
        """Split a ``①鼻病毒``-style cell into rank and pathogen name."""
        for mark, rank in _SENTINEL_RANK_MARKERS.items():
            if text.startswith(mark):
                return rank, text[len(mark) :].strip()
        return None, text.strip()

    @staticmethod
    def _normalize_sentinel_age_group(label: str) -> str:
        """Translate a Chinese age-group label (``0～4岁`` → ``0-4``)."""
        m = re.match(r"^(\d+)[～~](\d+)岁$", label)
        if m:
            return f"{m.group(1)}-{m.group(2)}"
        m = re.match(r"^(\d+)岁及以上$", label)
        if m:
            return f"{m.group(1)}+"
        return label

    @staticmethod
    def _parse_sentinel_positivity_table(table) -> pd.DataFrame:
        """
        Parse the per-pathogen positivity table (表1) of a sentinel
        surveillance report.

        Returns a DataFrame with ``pathogen_cn``, ``pathogen`` (English),
        and positivity/change columns for both syndromes.
        """
        rows: list[dict] = []
        for tr in table.find_all("tr"):
            cells = [
                c.get_text(strip=True) for c in tr.find_all(["td", "th"])
            ]
            if len(cells) < 3 or not cells[0]:
                continue
            pathogen_cn = cells[0]
            if pathogen_cn == "病原体" or re.match(r"^第\d+周", pathogen_cn):
                continue
            ili, sari = ChinaCDCAccessor._split_cell_groups(cells[1:])
            rows.append(
                {
                    "pathogen_cn": pathogen_cn,
                    "pathogen": RESPIRATORY_PATHOGEN_MAP.get(
                        pathogen_cn, pathogen_cn
                    ),
                    "ili_positivity_pct": (
                        ChinaCDCAccessor._sentinel_to_float(ili[0])
                        if ili
                        else None
                    ),
                    "ili_change_vs_previous_week": (
                        ChinaCDCAccessor._sentinel_to_float(ili[1])
                        if len(ili) > 1
                        else None
                    ),
                    "sari_positivity_pct": (
                        ChinaCDCAccessor._sentinel_to_float(sari[0])
                        if sari
                        else None
                    ),
                    "sari_change_vs_previous_week": (
                        ChinaCDCAccessor._sentinel_to_float(sari[1])
                        if len(sari) > 1
                        else None
                    ),
                }
            )
        return pd.DataFrame(rows)

    @staticmethod
    def _parse_sentinel_top3_region_table(table) -> pd.DataFrame:
        """
        Parse the top-3 pathogens by region table (表2; South/North).

        Returns a long-format DataFrame with ``region`` (``south``/
        ``north``), ``syndrome``, ``rank``, ``pathogen_cn`` and
        ``pathogen``.
        """
        region_keys = {"南方省份": "south", "北方省份": "north"}
        rows: list[dict] = []
        for tr in table.find_all("tr"):
            cells = [
                c.get_text(strip=True) for c in tr.find_all(["td", "th"])
            ]
            if len(cells) < 3 or cells[0] not in region_keys:
                continue
            region = region_keys[cells[0]]
            ili, sari = ChinaCDCAccessor._split_cell_groups(cells[1:])
            for syndrome, names in (
                ("ili_consultation", ili),
                ("sari_hospitalised", sari),
            ):
                for rank, raw in enumerate(names, start=1):
                    # ties are printed as a single 、-joined cell
                    for name in raw.split("、"):
                        if not name:
                            continue
                        rows.append(
                            {
                                "region": region,
                                "syndrome": syndrome,
                                "rank": rank,
                                "pathogen_cn": name,
                                "pathogen": RESPIRATORY_PATHOGEN_MAP.get(
                                    name, name
                                ),
                            }
                        )
        return pd.DataFrame(
            rows,
            columns=[
                "region",
                "syndrome",
                "rank",
                "pathogen_cn",
                "pathogen",
            ],
        )

    @staticmethod
    def _parse_sentinel_top3_age_table(table) -> pd.DataFrame:
        """
        Parse the top-3 pathogens by age group table (表3; 0-4, 5-14,
        15-59, 60+).

        Uses ``pandas.read_html`` so the ``rowspan`` age labels are
        expanded onto every rank row.

        Returns a long-format DataFrame with ``age_group``, ``syndrome``,
        ``rank``, ``pathogen_cn`` and ``pathogen``.
        """
        try:
            dfs = pd.read_html(io.StringIO(str(table)), flavor="lxml")
        except ValueError:
            return []
        if not dfs:
            return []

        rows: list[dict] = []
        for _, r in dfs[0].iterrows():
            values = [
                str(v).strip()
                for v in r.tolist()
                if not pd.isna(v) and str(v).strip() and str(v).strip() != "nan"
            ]
            if len(values) < 3:
                continue
            if not _SENTINEL_AGE_PATTERN.match(values[0]):
                continue  # header row
            age_group = ChinaCDCAccessor._normalize_sentinel_age_group(
                values[0]
            )
            for syndrome, raw in zip(
                ("ili_consultation", "sari_hospitalised"),
                values[1:3],
                strict=True,
            ):
                rank, name = ChinaCDCAccessor._split_ranked_pathogen(raw)
                if not name:
                    continue
                rows.append(
                    {
                        "age_group": age_group,
                        "syndrome": syndrome,
                        "rank": rank,
                        "pathogen_cn": name,
                        "pathogen": RESPIRATORY_PATHOGEN_MAP.get(
                            name, name
                        ),
                    }
                )
        return pd.DataFrame(
            rows,
            columns=[
                "age_group",
                "syndrome",
                "rank",
                "pathogen_cn",
                "pathogen",
            ],
        )

    @staticmethod
    def _parse_sentinel_article(soup) -> dict:
        """
        Parse a sentinel surveillance report article page (week metadata,
        ILI consultation shares, positivity/top-pathogen tables and the
        qualitative narrative).
        """
        report: dict = {
            "year": None,
            "week": None,
            "title": None,
            "publish_date": None,
            "ili_percent_national": None,
            "ili_percent_south": None,
            "ili_percent_north": None,
            "sentinel_hospitals": None,
            "positivity": pd.DataFrame(),
            "top_pathogens_by_region": pd.DataFrame(),
            "top_pathogens_by_age": pd.DataFrame(),
            "narrative": None,
        }

        flat = re.sub(r"\s+", "", soup.get_text())

        h5 = soup.find("h5")
        title = h5.get_text(strip=True) if h5 is not None else None
        if title:
            report["title"] = title
        tm = re.search(r"(\d{4})年第(\d{1,2})周", title or flat)
        if tm:
            report["year"] = int(tm.group(1))
            report["week"] = int(tm.group(2))

        dm = re.search(r"时间[：:]\s*(\d{4}-\d{2}-\d{2})", flat)
        if dm:
            report["publish_date"] = dm.group(1)

        im = re.search(r"（流感样病例百分比）为([\d.]+)%", flat)
        if im:
            report["ili_percent_national"] = float(im.group(1))
        sm = re.search(
            r"南方省份（([\d.]+)%）(?:高于|低于)北方省份（([\d.]+)%）", flat
        )
        if sm:
            report["ili_percent_south"] = float(sm.group(1))
            report["ili_percent_north"] = float(sm.group(2))

        hm = re.search(r"(\d+)家开展呼吸道多病原监测的哨点医院", flat)
        if hm:
            report["sentinel_hospitals"] = int(hm.group(1))

        # the qualitative commentary follows the 分析及健康提示 heading
        content = soup.select_one("div.trs_editor_view") or soup
        content_text = re.sub(r"\s+", "", content.get_text())
        marker = content_text.find("二、分析及健康提示")
        if marker >= 0:
            report["narrative"] = content_text[
                marker + len("二、分析及健康提示") :
            ]

        for table in soup.find_all("table"):
            first_row = table.find("tr")
            if first_row is None:
                continue
            header = (
                first_row.find(["td", "th"]).get_text(strip=True)
                if first_row.find(["td", "th"]) is not None
                else ""
            )
            if header == "病原体" and report["positivity"].empty:
                report["positivity"] = (
                    ChinaCDCAccessor._parse_sentinel_positivity_table(table)
                )
            elif header == "省份" and report["top_pathogens_by_region"].empty:
                report["top_pathogens_by_region"] = (
                    ChinaCDCAccessor._parse_sentinel_top3_region_table(table)
                )
            elif header == "年龄组" and report["top_pathogens_by_age"].empty:
                report["top_pathogens_by_age"] = (
                    ChinaCDCAccessor._parse_sentinel_top3_age_table(table)
                )

        return report

    def get_respiratory_sentinel_report(self, year: int, week: int) -> dict:
        """
        Fetch and parse one weekly national sentinel surveillance report
        of acute respiratory infections (全国急性呼吸道传染病哨点监测情况).

        The report covers the ILI share of outpatient consultations
        (national value plus a South/North split) and, for outpatients
        with influenza-like illness and hospitalised patients with severe
        acute respiratory infection (SARI), the PCR positivity for 11
        respiratory pathogens, the top-3 pathogens by region and by age
        group, and a qualitative narrative. The article HTML is cached
        under :attr:`cache_dir` with a 24h TTL.

        Args:
            year: Surveillance year (e.g. 2026).
            week: Surveillance week number (e.g. 41).

        Returns:
            Dict with ``year``, ``week``, ``title``, ``publish_date``,
            ``url``, ``ili_percent_national``, ``ili_percent_south``,
            ``ili_percent_north``, ``sentinel_hospitals``,
            ``positivity`` (DataFrame: ``pathogen_cn``, ``pathogen``,
            ``ili_positivity_pct``, ``ili_change_vs_previous_week``,
            ``sari_positivity_pct``, ``sari_change_vs_previous_week``),
            ``top_pathogens_by_region`` (DataFrame), ``top_pathogens_by_age``
            (DataFrame) and ``narrative``.
        """
        url = self._get_sentinel_article_url(year, week)
        logger.info(f"Fetching respiratory sentinel report {year} w{week}")
        html = self._fetch_html_cached(
            url, f"sentinel_{Path(url).stem}.html"
        )
        report = self._parse_sentinel_article(
            BeautifulSoup(html, "html.parser")
        )
        report["url"] = url
        if report["year"] is None:
            report["year"] = year
        if report["week"] is None:
            report["week"] = week
        return report

    def get_respiratory_sentinel_surveillance(
        self, weeks: int = 8
    ) -> pd.DataFrame:
        """
        Build a tidy long table of pathogen positivity from the most
        recent sentinel surveillance reports.

        Each report is fetched (TTL-cached under :attr:`cache_dir`) and
        parsed; the per-pathogen positivity for the outpatient ILI and
        hospitalised SARI syndromes is stacked into one long DataFrame.

        Args:
            weeks: Number of most-recent reports to aggregate
                (default: 8).

        Returns:
            DataFrame with ``year``, ``week``, ``publish_date``,
            ``syndrome`` (``ili_consultation``|``sari_hospitalised``),
            ``pathogen`` (English name), ``positivity_pct`` and
            ``change_vs_previous_week``.
        """
        columns = [
            "year",
            "week",
            "publish_date",
            "syndrome",
            "pathogen",
            "positivity_pct",
            "change_vs_previous_week",
        ]
        reports = self.list_respiratory_sentinel_reports()
        if reports.empty:
            return pd.DataFrame(columns=columns)

        frames: list[pd.DataFrame] = []
        for _, rpt in reports.tail(max(1, int(weeks))).iterrows():
            try:
                rep = self.get_respiratory_sentinel_report(
                    int(rpt["year"]), int(rpt["week"])
                )
            except Exception as exc:
                logger.error(
                    f"Failed to parse sentinel report {rpt['year']} week "
                    f"{rpt['week']}: {exc}"
                )
                continue
            pos = rep["positivity"]
            if pos.empty:
                continue
            for syndrome, pct_col, delta_col in (
                (
                    "ili_consultation",
                    "ili_positivity_pct",
                    "ili_change_vs_previous_week",
                ),
                (
                    "sari_hospitalised",
                    "sari_positivity_pct",
                    "sari_change_vs_previous_week",
                ),
            ):
                part = pos[["pathogen", pct_col, delta_col]].copy()
                part.columns = [
                    "pathogen",
                    "positivity_pct",
                    "change_vs_previous_week",
                ]
                part.insert(0, "syndrome", syndrome)
                part.insert(0, "publish_date", rep["publish_date"])
                part.insert(0, "week", rep["week"])
                part.insert(0, "year", rep["year"])
                frames.append(part)

        if not frames:
            return pd.DataFrame(columns=columns)
        return pd.concat(frames, ignore_index=True)[columns]

    def get_respiratory_sentinel_ili(self, weeks: int = 52) -> pd.DataFrame:
        """
        Build the weekly ILI consultation-share series (流感样病例百分比)
        from the sentinel surveillance reports.

        Args:
            weeks: Number of most-recent reports to aggregate
                (default: 52, i.e. one year of weekly values).

        Returns:
            DataFrame with ``year``, ``week``, ``publish_date``,
            ``ili_percent_national``, ``ili_percent_south`` and
            ``ili_percent_north``.
        """
        columns = [
            "year",
            "week",
            "publish_date",
            "ili_percent_national",
            "ili_percent_south",
            "ili_percent_north",
        ]
        reports = self.list_respiratory_sentinel_reports()
        if reports.empty:
            return pd.DataFrame(columns=columns)

        rows: list[dict] = []
        for _, rpt in reports.tail(max(1, int(weeks))).iterrows():
            try:
                rep = self.get_respiratory_sentinel_report(
                    int(rpt["year"]), int(rpt["week"])
                )
            except Exception as exc:
                logger.error(
                    f"Failed to parse sentinel report {rpt['year']} week "
                    f"{rpt['week']}: {exc}"
                )
                continue
            rows.append(
                {
                    "year": rep["year"],
                    "week": rep["week"],
                    "publish_date": rep["publish_date"],
                    "ili_percent_national": rep["ili_percent_national"],
                    "ili_percent_south": rep["ili_percent_south"],
                    "ili_percent_north": rep["ili_percent_north"],
                }
            )
        if not rows:
            return pd.DataFrame(columns=columns)
        return pd.DataFrame(rows, columns=columns)

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


# Reverse mapping of Chinese disease names (as printed in the NDCPA /
# China CDC monthly overview tables) to canonical disease codes. Built
# from the class-level dictionaries plus aliases observed in the official
# tables (hepatitis subtype breakdowns and historical names).
_CN_NAME_TO_CODE: dict[str, str] = {
    info["cn"]: code
    for code, info in ChinaCDCAccessor.NOTIFIABLE_DISEASES.items()
}
for _code, _info in ChinaCDCAccessor.NON_NOTIFIABLE_PRIORITY_DISEASES.items():
    _CN_NAME_TO_CODE.setdefault(_info["cn"], _code)
_CN_NAME_TO_CODE.update(
    {
        "新型冠状病毒肺炎": "COVID_19",
        "甲型肝炎": "Viral_Hepatitis_A",
        "乙型肝炎": "Viral_Hepatitis_B",
        "丙型肝炎": "Viral_Hepatitis_C",
        "丁型肝炎": "Viral_Hepatitis_D",
        "戊型肝炎": "Viral_Hepatitis_E",
        "未分型肝炎": "Viral_Hepatitis_Other",
        "伤寒和副伤寒": "Typhoid_Paratyphoid",
        "其他感染性腹泻病": "Infectious_Diarrhea",
        "感染性腹泻病": "Infectious_Diarrhea",
        "斑疹伤寒": "Epidemic_Enteritis",
        "肾综合征出血热": "Epidemic_Hemorrhagic_Fever",
        "内脏利什曼病": "Kala_Azar",
    }
)
