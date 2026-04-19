"""
China CDC Weekly Data Accessor

This module provides access to surveillance data from China CDC Weekly,
the official publication of the Chinese Center for Disease Control and Prevention.
Includes notifiable infectious diseases, influenza surveillance, and weekly reports.

Data Sources:
- China CDC Weekly: http://weekly.chinacdc.cn/
- Chinese CDC: https://www.chinacdc.cn/
- Notifiable diseases surveillance system
- ILI (Influenza-like Illness) surveillance network

Update Frequency:
- Weekly surveillance reports
- Monthly summaries
- Annual epidemiological reports

License: Open Access (journal articles)

Author: Flávio Codeço Coelho
License: MIT
"""

import logging
import re
from datetime import datetime
from typing import ClassVar, List, Optional, Tuple

import pandas as pd
import requests
from bs4 import BeautifulSoup

from epidatasets._base import BaseAccessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize China CDC accessor.

        Args:
            cache_dir: Directory to cache downloaded data (optional)
        """
        self.cache_dir = cache_dir
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": "China-CDC-Accessor/1.0 (Research Purpose)",
                "Accept": "text/html, application/json",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        self._cache = {}

    def list_notifiable_diseases(self) -> pd.DataFrame:
        """
        List notifiable infectious diseases in China.

        Returns
        -------
            DataFrame with disease information
        """
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
        """
        List Chinese provinces and municipalities.

        Returns
        -------
            DataFrame with province codes and names
        """
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
        """
        List countries covered by this accessor (China).

        Returns
        -------
            DataFrame with country codes and names
        """
        return pd.DataFrame(
            [("CN", "China")],
            columns=["country_code", "country_name"],
        )

    def get_weekly_reports(
        self,
        year: int,
        week: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Get metadata for China CDC Weekly surveillance reports.

        Args:
            year: Year of reports
            week: Specific epidemiological week (1-52/53). If None, returns all.

        Returns
        -------
            DataFrame with report metadata
        """
        logger.info(f"Fetching weekly reports for year {year}, week={week}")

        # Build report URLs for China CDC Weekly
        # Structure: http://weekly.chinacdc.cn/en/article/doi/10.46234/ccdcw{year}{week:03d}

        reports = []

        if week:
            weeks = [week]
        else:
            # Assume 52 weeks (some years have 53)
            weeks = list(range(1, 53))

        for w in weeks:
            doi = f"10.46234/ccdcw{year}{w:03d}"
            url = f"{self.BASE_URL}/en/article/doi/{doi}"

            report = {
                "year": year,
                "week": w,
                "doi": doi,
                "url": url,
                "title_en": f"China CDC Weekly - Week {w}, {year}",
                "title_cn": f"中国疾病预防控制中心周报 - {year}年第{w}周",
                "publication_date": None,
                "data_available": False,
                "note": "Full-text access requires parsing HTML/PDF",
            }
            reports.append(report)

        return pd.DataFrame(reports)

    def get_notifiable_diseases(
        self,
        diseases: Optional[List[str]] = None,
        provinces: Optional[List[str]] = None,
        date_range: Optional[Tuple[str, str]] = None,
    ) -> pd.DataFrame:
        """
        Get notifiable infectious disease data from China CDC Weekly.

        Args:
            diseases: List of disease codes (e.g., ["Influenza", "Dengue"])
            provinces: List of province codes (e.g., ["GD", "BJ"])
            date_range: Tuple of (start_date, end_date) in 'YYYY-MM-DD' format

        Returns
        -------
            DataFrame with disease case data
        """
        # Validate disease codes
        if diseases:
            valid_diseases = [d for d in diseases if d in self.NOTIFIABLE_DISEASES]
            if not valid_diseases:
                logger.error(f"No valid disease codes. Valid: {list(self.NOTIFIABLE_DISEASES.keys())}")
                return pd.DataFrame()
            diseases = valid_diseases

        # Validate provinces
        if provinces:
            valid_provinces = [p for p in provinces if p in self.PROVINCES]
            if not valid_provinces:
                logger.error(f"No valid province codes. Valid: {list(self.PROVINCES.keys())}")
                return pd.DataFrame()
            provinces = valid_provinces

        logger.info(
            f"Fetching notifiable disease data: diseases={diseases}, provinces={provinces}"
        )

        # China CDC Weekly publishes notifiable disease summaries
        # These are typically in tables within the weekly PDFs

        data = []
        disease_list = diseases if diseases else list(self.NOTIFIABLE_DISEASES.keys())[:5]
        province_list = provinces if provinces else list(self.PROVINCES.keys())

        for disease in disease_list:
            for province in province_list:
                record = {
                    "disease_code": disease,
                    "disease_name_cn": self.NOTIFIABLE_DISEASES[disease]["cn"],
                    "disease_category": self.NOTIFIABLE_DISEASES[disease]["category"],
                    "province_code": province,
                    "province_name": self.PROVINCES[province]["name"],
                    "cases": None,
                    "deaths": None,
                    "date": date_range[0] if date_range else None,
                    "data_source": "China CDC Weekly",
                    "note": "Data requires weekly report parsing",
                }
                data.append(record)

        logger.warning(
            "Notifiable disease data requires parsing China CDC Weekly PDFs. "
            "Weekly reports are available at http://weekly.chinacdc.cn/"
        )
        return pd.DataFrame(data)

    def get_influenza_surveillance(
        self,
        weeks: Optional[List[int]] = None,
        year: Optional[int] = None,
        provinces: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Get influenza surveillance data (ILI%) from China CDC Weekly.

        Args:
            weeks: List of epidemiological weeks (1-52)
            year: Year (default: current)
            provinces: List of province codes for regional data

        Returns
        -------
            DataFrame with ILI surveillance data
        """
        year = year or datetime.now().year
        weeks = weeks or list(range(1, 53))

        logger.info(f"Fetching influenza surveillance for year={year}, weeks={len(weeks)}")

        # ILI data is published in weekly reports
        # ILI% = (Number of ILI cases / Total outpatients) × 100

        data = []
        for week in weeks:
            record = {
                "year": year,
                "week": week,
                "ili_percent": None,
                "ili_cases": None,
                "total_outpatients": None,
                "virus_detected": None,
                "ah3n2": None,
                "h1n1": None,
                "b_victoria": None,
                "b_yamagata": None,
                "data_source": "China CDC Weekly / CNIC",
                "note": "ILI data requires weekly report parsing",
            }
            data.append(record)

        logger.warning(
            "Influenza surveillance data requires parsing weekly reports. "
            "CNIC also provides data at http://www.chinacdc.cn/cnic/"
        )
        return pd.DataFrame(data)

    def get_covid_updates(
        self,
        date_range: Optional[Tuple[str, str]] = None,
    ) -> pd.DataFrame:
        """
        Get COVID-19 updates from China CDC Weekly.

        Args:
            date_range: Tuple of (start_date, end_date)

        Returns
        -------
            DataFrame with COVID-19 data
        """
        logger.info("Fetching COVID-19 updates")

        # COVID-19 data is published in weekly summaries
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
        vaccines: List[str],
        year: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Get vaccination coverage data for China.

        Args:
            vaccines: List of vaccines (e.g., ["EPI", "COVID-19"])
            year: Year (default: current)

        Returns
        -------
            DataFrame with vaccination coverage
        """
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

        logger.warning(
            "Vaccination data requires parsing China CDC Weekly reports."
        )
        return pd.DataFrame(data)

    def search_articles(
        self,
        query: str,
        year: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Search for articles in China CDC Weekly.

        Args:
            query: Search query
            year: Filter by year

        Returns
        -------
            DataFrame with article metadata
        """
        logger.info(f"Searching for '{query}' in China CDC Weekly")

        # China CDC Weekly has a searchable archive
        # This is a placeholder for web scraping functionality

        articles = []
        article = {
            "title": None,
            "authors": None,
            "doi": None,
            "url": None,
            "publication_date": None,
            "abstract": None,
            "keywords": None,
            "data_available": False,
            "note": "Article search requires web scraping",
        }
        articles.append(article)

        logger.warning(
            "Article search requires scraping http://weekly.chinacdc.cn/"
        )
        return pd.DataFrame(articles)

    def parse_weekly_report(
        self,
        year: int,
        week: int,
    ) -> pd.DataFrame:
        """
        Parse a specific weekly report for disease data tables.

        Args:
            year: Report year
            week: Epidemiological week

        Returns
        -------
            DataFrame with parsed disease data
        """
        logger.info(f"Parsing weekly report for {year} week {week}")

        url = f"{self.BASE_URL}/en/article/doi/10.46234/ccdcw{year}{week:03d}"

        try:
            response = self._session.get(url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            # Look for data tables
            tables = soup.find_all("table")

            if not tables:
                logger.warning(f"No tables found in report for {year} week {week}")
                return pd.DataFrame()

            # Parse first table (usually contains disease data)
            dfs = pd.read_html(str(tables[0]))

            if dfs:
                df = dfs[0]
                df["year"] = year
                df["week"] = week
                logger.info(f"Parsed {len(df)} rows from report")
                return df

        except Exception as e:
            logger.error(f"Failed to parse report: {e}")

        return pd.DataFrame()

    def get_summary_by_disease(
        self,
        year: int,
    ) -> pd.DataFrame:
        """
        Get annual summary by disease category.

        Args:
            year: Year to summarize

        Returns
        -------
            DataFrame with disease summaries
        """
        logger.info(f"Generating disease summary for {year}")

        # Aggregate data from weekly reports
        summary = []

        for disease_code in list(self.NOTIFIABLE_DISEASES.keys())[:10]:
            summary.append({
                "disease_code": disease_code,
                "disease_name_cn": self.NOTIFIABLE_DISEASES[disease_code]["cn"],
                "category": self.NOTIFIABLE_DISEASES[disease_code]["category"],
                "year": year,
                "total_cases": None,
                "total_deaths": None,
                "data_source": "China CDC Weekly",
                "note": "Summary requires data aggregation",
            })

        return pd.DataFrame(summary)
