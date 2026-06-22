"""
Malaysia Ministry of Health (MOH) Open Data Accessor

Provides access to public health datasets published by the Ministry of
Health Malaysia and related agencies via the data.gov.my open data portal.

Datasets include:

*Infectious Diseases*
- Daily COVID-19 cases by state
- Daily COVID-19 cases by age group & state
- Sexually transmitted diseases (HIV, AIDS, gonorrhea, syphilis) by state

*Immunisation*
- Infant immunisation coverage (annual, national)

*Healthcare Infrastructure*
- Hospital beds by state, district, and hospital type
- Healthcare staff by state and staff type (doctors, nurses, etc.)

*Health Programmes*
- Daily blood donations by blood type
- Daily organ donation pledges (national and by state)
- Daily PeKaB40 health screenings (national and by state)

Data Sources:
- Portal: https://data.gov.my/data-catalogue?category=healthcare
- API Docs: https://developer.data.gov.my/
- Storage: https://storage.data.gov.my/healthcare/

License: Creative Commons Attribution 4.0 International (CC BY 4.0)

Author: Flávio Codeço Coelho
License: MIT
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import ClassVar

import pandas as pd
import requests

from epidatasets._base import BaseAccessor

logger = logging.getLogger(__name__)


class MalaysiaMOHAccessor(BaseAccessor):
    """
    Accessor for Malaysia MOH open health data from data.gov.my.

    Provides access to 11 datasets covering infectious diseases,
    immunisation, healthcare infrastructure, and health programmes.

    Example:
        >>> moh = MalaysiaMOHAccessor()
        >>>
        >>> # COVID-19 cases by state
        >>> covid = moh.get_covid_cases()
        >>>
        >>> # Hospital beds by state and type
        >>> beds = moh.get_hospital_beds()
        >>>
        >>> # STDs by disease and state
        >>> std = moh.get_std_cases(disease="HIV")

    Data Sources:
        - Portal: https://data.gov.my/data-catalogue?category=healthcare
        - Storage: https://storage.data.gov.my/healthcare/
    """

    source_name: ClassVar[str] = "malaysia_moh"
    source_description: ClassVar[str] = (
        "Public health data from the Ministry of Health Malaysia via "
        "data.gov.my: COVID-19 cases, STDs, immunisation, hospital beds, "
        "healthcare staff, blood donations, organ pledges, and PeKaB40 "
        "health screenings."
    )
    source_url: ClassVar[str] = (
        "https://data.gov.my/data-catalogue?category=healthcare"
    )

    STORAGE_BASE = "https://storage.data.gov.my/healthcare"
    API_BASE = "https://api.data.gov.my/data-catalogue"
    REQUEST_TIMEOUT = 60

    # Dataset IDs (map short name -> storage filename without extension)
    DATASETS: ClassVar[dict[str, str]] = {
        "covid_cases": "covid_cases",
        "covid_cases_age": "covid_cases_age",
        "std_state": "std_state",
        "infant_immunisation": "infant_immunisation",
        "hospital_beds": "hospital_beds",
        "healthcare_staff": "healthcare_staff",
        "blood_donations": "blood_donations",
        "organ_pledges": "organ_pledges",
        "organ_pledges_state": "organ_pledges_state",
        "pekab40_screenings": "pekab40_screenings",
        "pekab40_screenings_state": "pekab40_screenings_state",
    }

    # Malaysian states (including Malaysia for national-level data)
    STATES: ClassVar[list[str]] = [
        "Malaysia",
        "Johor",
        "Kedah",
        "Kelantan",
        "Melaka",
        "Negeri Sembilan",
        "Pahang",
        "Perak",
        "Perlis",
        "Pulau Pinang",
        "Sabah",
        "Sarawak",
        "Selangor",
        "Terengganu",
        "W.P. Kuala Lumpur",
        "W.P. Labuan",
        "W.P. Putrajaya",
    ]

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        timeout: int = REQUEST_TIMEOUT,
    ):
        super().__init__()
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = (
                Path.home() / ".cache" / "epi_data" / "malaysia_moh"
            )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            }
        )

    def list_countries(self) -> pd.DataFrame:
        """Return a single-row DataFrame for Malaysia."""
        return pd.DataFrame(
            [{"country_code": "MY", "country_name": "Malaysia"}]
        )

    def list_states(self) -> pd.DataFrame:
        """Return Malaysian states (including national-level aggregation)."""
        return pd.DataFrame({"state": self.STATES})

    # ------------------------------------------------------------------
    # Core data-fetching helper
    # ------------------------------------------------------------------
    def _fetch_dataset(
        self,
        dataset_id: str,
        use_cache: bool = True,
        cache_ttl_hours: float = 24,
    ) -> pd.DataFrame:
        """Download a dataset parquet file from the storage server.

        Parameters
        ----------
        dataset_id : str
            One of ``self.DATASETS`` keys.
        use_cache : bool
            If True (default), return a cached copy when fresh.
        cache_ttl_hours : float
            Maximum cache age in hours.

        Returns
        -------
        pd.DataFrame
        """
        filename = self.DATASETS.get(dataset_id, dataset_id)
        cache_key = f"{filename}.parquet"
        cache_path = self.cache_dir / cache_key

        if use_cache and self._is_fresh(cache_path, cache_ttl_hours):
            try:
                df = pd.read_parquet(cache_path)
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"], errors="coerce")
                return df
            except Exception:
                pass

        url = f"{self.STORAGE_BASE}/{filename}.parquet"
        try:
            resp = self._session.get(url, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error(
                "MalaysiaMOH: download %s failed: %s", url, exc
            )
            raise RuntimeError(
                f"Failed to download {filename} from data.gov.my: {exc}"
            ) from exc

        cache_path.write_bytes(resp.content)
        df = pd.read_parquet(cache_path)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        return df

    @staticmethod
    def _is_fresh(path: Path, ttl_hours: float) -> bool:
        if not path.exists():
            return False
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        return datetime.now() - mtime < timedelta(hours=ttl_hours)

    # ------------------------------------------------------------------
    # Infectious Diseases
    # ------------------------------------------------------------------
    def get_covid_cases(
        self,
        state: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Fetch daily COVID-19 cases by state.

        Parameters
        ----------
        state : str, optional
            Filter to a specific state (e.g. ``"Selangor"``).  Use
            ``"Malaysia"`` for national-level data.
        start_date, end_date : str, optional
            Date range in ``YYYY-MM-DD`` format.
        use_cache : bool
            If True (default), use locally cached data.

        Returns
        -------
        pd.DataFrame
            Columns: ``date``, ``state``, ``cases_new``, ``cases_import``,
            ``cases_recovered``, ``cases_active``, ``cases_cluster``.
        """
        df = self._fetch_dataset("covid_cases", use_cache=use_cache)
        return _filter_df(df, state=state, start=start_date, end=end_date)

    def get_covid_cases_age(
        self,
        state: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Fetch daily COVID-19 cases by age group and state.

        Returns
        -------
        pd.DataFrame
            Columns: ``date``, ``state``, individual age-bracket columns
            (``cases_0_4``, ``cases_5_11``, …), and aggregate columns
            (``cases_child``, ``cases_adolescent``, ``cases_adult``,
            ``cases_elderly``).
        """
        df = self._fetch_dataset("covid_cases_age", use_cache=use_cache)
        return _filter_df(df, state=state, start=start_date, end=end_date)

    def get_std_cases(
        self,
        disease: str | None = None,
        state: str | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Fetch sexually transmitted disease cases by state (annual).

        Parameters
        ----------
        disease : str, optional
            One of ``"HIV"``, ``"AIDS"``, ``"Chancroid"``, ``"Gonorrhoea"``,
            ``"Syphilis"``.
        state : str, optional
            Filter to a specific state.

        Returns
        -------
        pd.DataFrame
            Columns: ``date``, ``state``, ``disease``, ``cases``,
            ``incidence``.
        """
        df = self._fetch_dataset("std_state", use_cache=use_cache)
        if disease is not None:
            df = df[df["disease"].str.lower() == disease.lower()]
        if state is not None:
            df = df[df["state"] == state]
        return df.reset_index(drop=True)

    # ------------------------------------------------------------------
    # Immunisation
    # ------------------------------------------------------------------
    def get_infant_immunisation(
        self,
        disease: str | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Fetch infant immunisation coverage (annual, national-level).

        Parameters
        ----------
        disease : str, optional
            Filter to a specific vaccine/disease.

        Returns
        -------
        pd.DataFrame
            Columns: ``date``, ``disease``, ``rate``.
        """
        df = self._fetch_dataset(
            "infant_immunisation", use_cache=use_cache
        )
        if disease is not None:
            df = df[df["disease"].str.lower() == disease.lower()]
        return df.reset_index(drop=True)

    # ------------------------------------------------------------------
    # Healthcare Infrastructure
    # ------------------------------------------------------------------
    def get_hospital_beds(
        self,
        state: str | None = None,
        district: str | None = None,
        hospital_type: str | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Fetch hospital beds by state, district, and hospital type.

        Parameters
        ----------
        state : str, optional
            Filter to a specific state (e.g. ``"Selangor"``).
        district : str, optional
            Filter to a specific district.
        hospital_type : str, optional
            One of ``"all"``, ``"hospital_moh"``,
            ``"special_medical_institution"``, ``"hospital_non_moh"``.

        Returns
        -------
        pd.DataFrame
            Columns: ``date``, ``state``, ``district``, ``type``, ``beds``.
        """
        df = self._fetch_dataset("hospital_beds", use_cache=use_cache)
        if state is not None:
            df = df[df["state"] == state]
        if district is not None:
            df = df[df["district"] == district]
        if hospital_type is not None:
            df = df[df["type"] == hospital_type]
        return df.reset_index(drop=True)

    def get_healthcare_staff(
        self,
        state: str | None = None,
        staff_type: str | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Fetch healthcare staff by state and staff type.

        Parameters
        ----------
        state : str, optional
            Filter to a specific state.
        staff_type : str, optional
            One of ``"all"``, ``"doctors"``, ``"dentists"``,
            ``"pharmacists"``, ``"nurses"``, ``"midwives"``,
            ``"medical assistants"``, etc.

        Returns
        -------
        pd.DataFrame
            Columns: ``date``, ``state``, ``type``, ``staff``.
        """
        df = self._fetch_dataset("healthcare_staff", use_cache=use_cache)
        if state is not None:
            df = df[df["state"] == state]
        if staff_type is not None:
            df = df[df["type"] == staff_type]
        return df.reset_index(drop=True)

    # ------------------------------------------------------------------
    # Health Programmes
    # ------------------------------------------------------------------
    def get_blood_donations(
        self,
        blood_type: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Fetch daily blood donations by blood type (national-level).

        Parameters
        ----------
        blood_type : str, optional
            One of ``"A"``, ``"B"``, ``"AB"``, ``"O"``, ``"all"``.
        start_date, end_date : str, optional
            Date range in ``YYYY-MM-DD``.

        Returns
        -------
        pd.DataFrame
            Columns: ``date``, ``blood_type``, ``donations``.
        """
        df = self._fetch_dataset("blood_donations", use_cache=use_cache)
        if blood_type is not None:
            df = df[df["blood_type"] == blood_type]
        return _filter_df(df, start=start_date, end=end_date)

    def get_organ_pledges(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Fetch daily organ donation pledges (national-level).

        Returns
        -------
        pd.DataFrame
            Columns: ``date``, ``pledges``.
        """
        df = self._fetch_dataset("organ_pledges", use_cache=use_cache)
        return _filter_df(df, start=start_date, end=end_date)

    def get_organ_pledges_state(
        self,
        state: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Fetch daily organ donation pledges by state.

        Returns
        -------
        pd.DataFrame
            Columns: ``date``, ``state``, ``pledges``.
        """
        df = self._fetch_dataset(
            "organ_pledges_state", use_cache=use_cache
        )
        return _filter_df(df, state=state, start=start_date, end=end_date)

    def get_pekab40_screenings(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Fetch daily PeKaB40 health screenings (national-level).

        PeKaB40 is a healthcare protection scheme for the bottom 40%
        income group in Malaysia.

        Returns
        -------
        pd.DataFrame
            Columns: ``date``, ``screenings``.
        """
        df = self._fetch_dataset(
            "pekab40_screenings", use_cache=use_cache
        )
        return _filter_df(df, start=start_date, end=end_date)

    def get_pekab40_screenings_state(
        self,
        state: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Fetch daily PeKaB40 health screenings by state.

        Returns
        -------
        pd.DataFrame
            Columns: ``date``, ``state``, ``screenings``.
        """
        df = self._fetch_dataset(
            "pekab40_screenings_state", use_cache=use_cache
        )
        return _filter_df(df, state=state, start=start_date, end=end_date)


def _filter_df(
    df: pd.DataFrame,
    state: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    """Apply optional state and date-range filters."""
    if state is not None and "state" in df.columns:
        df = df[df["state"] == state]
    if start is not None and "date" in df.columns:
        df = df[df["date"] >= pd.Timestamp(start)]
    if end is not None and "date" in df.columns:
        df = df[df["date"] <= pd.Timestamp(end)]
    return df.reset_index(drop=True)
