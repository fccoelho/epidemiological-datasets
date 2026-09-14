"""
Hong Kong Centre for Health Protection (CHP) Open Data Accessor

This module provides access to structured surveillance data published by the
Hong Kong Department of Health's Centre for Health Protection through the
data.gov.hk open data portal.

Supports:
- Flu Express figures data: weekly influenza surveillance since 2014
  (sentinel ILI consultation rates, laboratory detections/positivity by
  type and subtype, ILI outbreaks, hospital admission rates, and severe
  influenza cases during influenza seasons)
- COVID-19 daily situation reports (time series frozen since 19 March 2023)

Data Sources:
- Flu Express figures data (CSV):
  https://www.chp.gov.hk/files/misc/flux_data.csv
  via https://data.gov.hk/en-data/dataset/hk-dh-chpsebcddr-flu-express
- COVID-19 situation data (CSV):
  https://www.chp.gov.hk/files/misc/latest_situation_of_reported_cases_covid_19_eng.csv
  via https://data.gov.hk/en-data/dataset/hk-dh-chpsebcddr-novel-infectious-agent

Update Frequency:
- Flu Express: weekly
- COVID-19 situation: daily (updates ceased 19 March 2023)

License: Open data (data.gov.hk terms permit free re-use)

Author: Flávio Codeço Coelho
License: MIT
"""

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import ClassVar

import pandas as pd
import requests

from epidatasets._base import BaseAccessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HongKongCHPAccessor(BaseAccessor):
    """
    Accessor for Hong Kong CHP surveillance data via data.gov.hk.

    Provides access to:
    - Flu Express weekly influenza surveillance (ILI rates, laboratory
      detections, outbreaks, hospital admissions, severe cases)
    - COVID-19 daily situation reports (archived; frozen since 2023-03-19)

    Example:
        >>> hk = HongKongCHPAccessor()
        >>>
        >>> # Weekly influenza data for 2024
        >>> flu = hk.get_influenza_data(year=2024)
        >>>
        >>> # ILI consultation rates only
        >>> ili = hk.get_ili_rates(year=2024)
        >>>
        >>> # COVID-19 daily situation (time series, archived)
        >>> covid = hk.get_covid_situation()

    Data Sources:
        - Flu Express: https://data.gov.hk/en-data/dataset/hk-dh-chpsebcddr-flu-express
        - COVID-19: https://data.gov.hk/en-data/dataset/hk-dh-chpsebcddr-novel-infectious-agent
        - CHP resources: https://www.chp.gov.hk/en/resources/29/100148.html
    """

    source_name: ClassVar[str] = "hk_chp"
    source_description: ClassVar[str] = (
        "Hong Kong Centre for Health Protection open data: weekly influenza "
        "surveillance (Flu Express) and COVID-19 situation reports"
    )
    source_url: ClassVar[str] = (
        "https://data.gov.hk/en-data/dataset/hk-dh-chpsebcddr-flu-express"
    )

    #: Flu Express figures data (single CSV, weekly updates, since 2014).
    FLU_EXPRESS_CSV = "https://www.chp.gov.hk/files/misc/flux_data.csv"
    #: Data dictionary for the Flu Express figures data.
    FLU_EXPRESS_DICTIONARY = "https://www.chp.gov.hk/files/pdf/flux_spec_en.pdf"

    #: Daily COVID-19 situation time series (English). Archived 2023-03-19.
    COVID_SITUATION_CSV = (
        "https://www.chp.gov.hk/files/misc/"
        "latest_situation_of_reported_cases_covid_19_eng.csv"
    )
    #: Data dictionary for the COVID-19 datasets.
    COVID_DICTIONARY = "https://www.chp.gov.hk/files/pdf/nid_spec_en.pdf"

    #: Date the COVID-19 data source files were last updated upstream.
    COVID_DATA_FROZEN_ON = "2023-03-19"

    #: Mapping of Flu Express CSV columns to normalized column names
    #: (per the official data dictionary, ``FLU_EXPRESS_DICTIONARY``).
    FLU_COLUMN_MAP = {
        "Year": "year",
        "Week": "week",
        "From": "week_start",
        "To": "week_end",
        "ILI_FMC": "ili_rate_family_medicine_per_1000",
        "ILI_PMP": "ili_rate_private_practitioner_per_1000",
        "H1": "influenza_a_h1_detections",
        "H3": "influenza_a_h3_detections",
        "B": "influenza_b_detections",
        "AandB": "influenza_a_and_b_detections",
        "H1_proportion": "h1_proportion",
        "H3_proportion": "h3_proportion",
        "B_proportion": "b_proportion",
        "AandB_proportion": "influenza_positivity",
        "ILI_School": "ili_outbreaks_schools",
        "ILI_NonSchool": "ili_outbreaks_other_institutions",
        "Adm_0_5": "admission_rate_0_5_per_10000",
        "Adm_6_11": "admission_rate_6_11_per_10000",
        "Adm_12_17": "admission_rate_12_17_per_10000",
        "Adm_18_49": "admission_rate_18_49_per_10000",
        "Adm_50_64": "admission_rate_50_64_per_10000",
        "Adm_65_higher": "admission_rate_65_plus_per_10000",
        "Adm_All": "admission_rate_all_ages_per_10000",
        "ILI_AED": "ili_aed_rate_per_1000",
        "Fever_CCCKG": "fever_rate_child_care_kindergarten",
        "Fever_RCHE": "fever_rate_residential_care_elderly",
        "ILI_CMP": "ili_rate_chinese_medicine_per_1000",
        "SevereCase_0_17": "severe_cases_0_17",
        "SevereCase_18_49": "severe_cases_18_49",
        "SevereCase_50_64": "severe_cases_50_64",
        "SevereCase_65_higher": "severe_cases_65_plus",
    }

    #: Mapping of COVID-19 CSV columns to normalized column names.
    COVID_COLUMN_MAP = {
        "As of date": "date",
        "As of time": "as_of_time",
        "Number of confirmed cases": "confirmed_cases_cumulative",
        "Number of ruled out cases": "ruled_out_cases_cumulative",
        "Number of cases still hospitalised for investigation": (
            "cases_hospitalised_for_investigation"
        ),
        "Number of cases fulfilling the reporting criteria": (
            "cases_fulfilling_reporting_criteria"
        ),
        "Number of death cases": "deaths_cumulative",
        "Number of discharge cases": "discharges_cumulative",
        "Number of probable cases": "probable_cases_cumulative",
        "Number of hospitalised cases in critical condition": (
            "cases_critical_cumulative"
        ),
        "Number of cases tested positive for SARS-CoV-2 virus by nucleic acid tests": (
            "positive_nucleic_acid_cases_cumulative"
        ),
        "Number of cases tested positive for SARS-CoV-2 virus by rapid antigen tests": (
            "positive_rapid_antigen_cases_cumulative"
        ),
        "Number of positive nucleic acid test laboratory detections": (
            "positive_nucleic_acid_lab_detections_cumulative"
        ),
        "Number of death cases related to COVID-19": (
            "covid_related_deaths_cumulative"
        ),
    }

    def __init__(self, cache_dir: str | None = None):
        if cache_dir is None:
            cache_dir = os.path.join(
                os.path.expanduser("~"), ".cache", "epidatasets", "hk_chp"
            )
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "HK-CHP-Accessor/1.0 (Research Purpose)"
                ),
                "Accept": "text/csv,application/csv,*/*",
            }
        )
        self._request_timeout = 60
        self._cache_ttl = timedelta(days=7)

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _get_cache_path(self, url: str) -> Path:
        filename = url.rsplit("/", 1)[-1] or "data.csv"
        return Path(self.cache_dir) / filename

    def _is_cache_valid(self, path: Path) -> bool:
        if not path.exists():
            return False
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        return datetime.now() - mtime < self._cache_ttl

    def _fetch_csv(self, url: str) -> pd.DataFrame:
        """Download (or use cached) CSV from *url* and parse it."""
        cache_path = self._get_cache_path(url)
        if not self._is_cache_valid(cache_path):
            logger.info(f"Downloading CSV from {url}")
            resp = self._session.get(url, timeout=self._request_timeout)
            resp.raise_for_status()
            cache_path.write_bytes(resp.content)
        else:
            logger.info(f"Using cached CSV: {cache_path}")
        return pd.read_csv(cache_path)

    # ------------------------------------------------------------------
    # Listing helpers
    # ------------------------------------------------------------------

    def list_countries(self) -> pd.DataFrame:
        return pd.DataFrame(
            [("HK", "Hong Kong SAR")],
            columns=["country_code", "country_name"],
        )

    # ------------------------------------------------------------------
    # Influenza (Flu Express)
    # ------------------------------------------------------------------

    def get_influenza_data(
        self,
        year: int | None = None,
        weeks: list[int] | None = None,
    ) -> pd.DataFrame:
        """
        Get the Flu Express weekly influenza surveillance data.

        Args:
            year: Filter by year (default: all years, 2014-present).
            weeks: Optional list of ISO-style surveillance week numbers
                (1-53) to filter by.

        Returns:
            DataFrame with one row per surveillance week and normalized
            column names (see ``FLU_COLUMN_MAP``): sentinel ILI
            consultation rates (family medicine, private practitioners and
            Chinese medicine, per 1,000 consultations), laboratory
            detections and positivity proportions by influenza type and
            subtype, ILI outbreak counts, public hospital admission rates
            by age group (per 10,000), A&E ILI syndrome rate, sentinel
            fever proportions, and severe influenza case counts by age
            group.
        """
        df = self._fetch_csv(self.FLU_EXPRESS_CSV)
        df = df.rename(columns=self.FLU_COLUMN_MAP)

        df["year"] = pd.to_numeric(df["year"], errors="coerce")
        df["week"] = pd.to_numeric(df["week"], errors="coerce")
        df["week_start"] = pd.to_datetime(
            df["week_start"], format="%d/%m/%Y", errors="coerce"
        )
        df["week_end"] = pd.to_datetime(
            df["week_end"], format="%d/%m/%Y", errors="coerce"
        )

        if year is not None:
            df = df[df["year"] == year]
        if weeks is not None:
            df = df[df["week"].isin(weeks)]

        df = df.sort_values(["year", "week"]).reset_index(drop=True)
        logger.info(f"Retrieved {len(df)} weekly influenza records")
        return df

    def get_ili_rates(
        self,
        year: int | None = None,
        weeks: list[int] | None = None,
    ) -> pd.DataFrame:
        """
        Get sentinel influenza-like illness (ILI) consultation rates.

        Returns a DataFrame with ``year``, ``week``, ``week_start``,
        ``week_end`` and the sentinel ILI consultation rates (per 1,000
        consultations) for family medicine clinics, private medical
        practitioners, Chinese medicine practitioners and A&E departments.
        """
        df = self.get_influenza_data(year=year, weeks=weeks)
        cols = [
            "year",
            "week",
            "week_start",
            "week_end",
            "ili_rate_family_medicine_per_1000",
            "ili_rate_private_practitioner_per_1000",
            "ili_rate_chinese_medicine_per_1000",
            "ili_aed_rate_per_1000",
        ]
        return df[[c for c in cols if c in df.columns]]

    def get_influenza_positivity(
        self,
        year: int | None = None,
        weeks: list[int] | None = None,
    ) -> pd.DataFrame:
        """
        Get laboratory surveillance of influenza detections.

        Returns a DataFrame with weekly counts of influenza A(H1), A(H3)
        and B detections, overall positivity (proportion of influenza
        A and B among all respiratory specimens) and the per-type
        proportions.
        """
        df = self.get_influenza_data(year=year, weeks=weeks)
        cols = [
            "year",
            "week",
            "week_start",
            "week_end",
            "influenza_a_h1_detections",
            "influenza_a_h3_detections",
            "influenza_b_detections",
            "influenza_a_and_b_detections",
            "h1_proportion",
            "h3_proportion",
            "b_proportion",
            "influenza_positivity",
        ]
        return df[[c for c in cols if c in df.columns]]

    def get_ili_outbreaks(
        self,
        year: int | None = None,
        weeks: list[int] | None = None,
    ) -> pd.DataFrame:
        """
        Get weekly influenza-like illness outbreak reports in schools and
        other institutions (child care centres/kindergartens, primary and
        secondary schools, residential care homes, etc.).
        """
        df = self.get_influenza_data(year=year, weeks=weeks)
        cols = [
            "year",
            "week",
            "week_start",
            "week_end",
            "ili_outbreaks_schools",
            "ili_outbreaks_other_institutions",
        ]
        return df[[c for c in cols if c in df.columns]]

    def get_hospital_admissions(
        self,
        year: int | None = None,
        weeks: list[int] | None = None,
    ) -> pd.DataFrame:
        """
        Get weekly public hospital admission rates with principal
        diagnosis of influenza (per 10,000 people in each age group).
        """
        df = self.get_influenza_data(year=year, weeks=weeks)
        cols = [
            "year",
            "week",
            "week_start",
            "week_end",
            "admission_rate_0_5_per_10000",
            "admission_rate_6_11_per_10000",
            "admission_rate_12_17_per_10000",
            "admission_rate_18_49_per_10000",
            "admission_rate_50_64_per_10000",
            "admission_rate_65_plus_per_10000",
            "admission_rate_all_ages_per_10000",
        ]
        return df[[c for c in cols if c in df.columns]]

    def get_severe_cases(
        self,
        year: int | None = None,
        weeks: list[int] | None = None,
    ) -> pd.DataFrame:
        """
        Get weekly counts of severe influenza cases (ICU admission or
        death) by age group, reported during influenza seasons.
        """
        df = self.get_influenza_data(year=year, weeks=weeks)
        cols = [
            "year",
            "week",
            "week_start",
            "week_end",
            "severe_cases_0_17",
            "severe_cases_18_49",
            "severe_cases_50_64",
            "severe_cases_65_plus",
        ]
        return df[[c for c in cols if c in df.columns]]

    # ------------------------------------------------------------------
    # COVID-19
    # ------------------------------------------------------------------

    def get_covid_situation(
        self,
        date_range: tuple[str, str] | None = None,
    ) -> pd.DataFrame:
        """
        Get the daily COVID-19 situation time series for Hong Kong.

        Cumulative counts include confirmed cases, deaths, discharges,
        hospitalisation indicators and positive detections by test type.

        Args:
            date_range: Optional ``(start, end)`` date strings
                (``YYYY-MM-DD``) to filter the series.

        Returns:
            DataFrame with one row per reporting day and normalized column
            names (see ``COVID_COLUMN_MAP``), plus a ``data_frozen_on``
            note column: the upstream files have not been updated since
            19 March 2023.
        """
        df = self._fetch_csv(self.COVID_SITUATION_CSV)
        df = df.rename(columns=self.COVID_COLUMN_MAP)

        df["date"] = pd.to_datetime(
            df["date"], format="%d/%m/%Y", errors="coerce"
        )
        for col in df.columns:
            if col.endswith("_cumulative") or col in (
                "cases_hospitalised_for_investigation",
                "cases_fulfilling_reporting_criteria",
            ):
                df[col] = pd.to_numeric(df[col], errors="coerce")

        if date_range is not None:
            start, end = date_range
            df = df[
                (df["date"] >= pd.Timestamp(start))
                & (df["date"] <= pd.Timestamp(end))
            ]

        df = df.sort_values("date").reset_index(drop=True)
        df["data_source"] = "HK CHP via data.gov.hk"
        df["note"] = (
            f"Upstream data not updated since {self.COVID_DATA_FROZEN_ON}"
        )
        logger.info(f"Retrieved {len(df)} daily COVID-19 records")
        return df
