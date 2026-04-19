"""
DATASUS Data Accessor using PySUS

This module provides a wrapper around the PySUS library for accessing
Brazilian public health data (DATASUS).

PySUS is developed by the AlertaDengue team and provides access to:
- SINAN: Notifiable diseases surveillance
- SIM: Mortality information system
- SIH: Hospital information system
- SIA: Ambulatory information system
- CNES: Health establishments registry

Repository: https://github.com/AlertaDengue/PySUS
PyPI: https://pypi.org/project/pysus/
"""

import logging
from typing import ClassVar, List, Optional

import pandas as pd

from epidatasets._base import BaseAccessor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataSUSAccessor(BaseAccessor):
    """
    Accessor for Brazilian DATASUS data using PySUS library.

    This is a wrapper around PySUS that provides a standardized interface
    consistent with other accessors in this repository.

    Example:
        >>> accessor = DataSUSAccessor()
        >>> dengue_data = accessor.get_dengue_cases(years=[2023], states=["RJ", "SP"])
        >>> mortality = accessor.get_mortality(years=[2022], states=["MG"])

    Requirements:
        pip install pysus
    """

    source_name: ClassVar[str] = "datasus"
    source_description: ClassVar[str] = "Brazilian DATASUS public health data via PySUS (SINAN, SIM, SIH, SIA, CNES)"
    source_url: ClassVar[str] = "https://github.com/AlertaDengue/PySUS"

    def list_countries(self) -> pd.DataFrame:
        return pd.DataFrame([("BR", "Brazil")], columns=["country_code", "country_name"])

    def __init__(self):
        self._sinan = None
        self._sim = None
        self._sih = None
        self._sia = None
        self._cnes = None

    def _get_sinan(self):
        """Lazy load SINAN module."""
        if self._sinan is None:
            try:
                from pysus.online_data import SINAN

                self._sinan = SINAN
            except ImportError:
                raise ImportError("PySUS is required. Install with: pip install pysus")
        return self._sinan

    def _get_sim(self):
        """Lazy load SIM module."""
        if self._sim is None:
            try:
                from pysus.online_data import SIM

                self._sim = SIM
            except ImportError:
                raise ImportError("PySUS is required. Install with: pip install pysus")
        return self._sim

    def _get_sih(self):
        """Lazy load SIH module."""
        if self._sih is None:
            try:
                from pysus.online_data import SIH

                self._sih = SIH
            except ImportError:
                raise ImportError("PySUS is required. Install with: pip install pysus")
        return self._sih

    def _get_sia(self):
        """Lazy load SIA module."""
        if self._sia is None:
            try:
                from pysus.online_data import SIA

                self._sia = SIA
            except ImportError:
                raise ImportError("PySUS is required. Install with: pip install pysus")
        return self._sia

    def get_dengue_cases(
        self,
        years: List[int],
        states: Optional[List[str]] = None,
        cities: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Download dengue notification data from SINAN.

        Args:
            years: List of years to download (e.g., [2022, 2023])
            states: List of state abbreviations (e.g., ["RJ", "SP", "MG"])
                   If None, downloads all states
            cities: List of city IBGE codes (optional, for filtering)

        Returns
        -------
            DataFrame with dengue case notifications

        Example:
            >>> accessor = DataSUSAccessor()
            >>> df = accessor.get_dengue_cases(years=[2023], states=["RJ"])
            >>> print(f"Total cases: {len(df)}")
        """
        SINAN = self._get_sinan()

        logger.info(f"Downloading dengue data for years {years}...")

        if states:
            dataframes = []
            for state in states:
                for year in years:
                    try:
                        df = SINAN.download(
                            disease="Dengue", years=[year], states=[state]
                        )
                        dataframes.append(df)
                        logger.info(f"Downloaded {len(df)} records for {state} {year}")
                    except Exception as e:
                        logger.warning(f"Failed to download {state} {year}: {e}")

            if dataframes:
                result = pd.concat(dataframes, ignore_index=True)
                logger.info(f"Total records: {len(result)}")
                return result
            else:
                return pd.DataFrame()
        else:
            return SINAN.download(disease="Dengue", years=years)

    def get_malaria_cases(
        self, years: List[int], states: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Download malaria notification data from SINAN.

        Args:
            years: List of years to download
            states: List of state abbreviations

        Returns
        -------
            DataFrame with malaria case notifications
        """
        SINAN = self._get_sinan()

        logger.info(f"Downloading malaria data for years {years}...")

        if states:
            dataframes = []
            for state in states:
                for year in years:
                    try:
                        df = SINAN.download(
                            disease="Malaria", years=[year], states=[state]
                        )
                        dataframes.append(df)
                    except Exception as e:
                        logger.warning(f"Failed to download {state} {year}: {e}")

            if dataframes:
                return pd.concat(dataframes, ignore_index=True)
            else:
                return pd.DataFrame()
        else:
            return SINAN.download(disease="Malaria", years=years)

    def get_chikungunya_cases(
        self, years: List[int], states: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Download chikungunya notification data from SINAN.

        Args:
            years: List of years to download
            states: List of state abbreviations

        Returns
        -------
            DataFrame with chikungunya case notifications
        """
        SINAN = self._get_sinan()

        logger.info(f"Downloading chikungunya data for years {years}...")

        if states:
            dataframes = []
            for state in states:
                for year in years:
                    try:
                        df = SINAN.download(
                            disease="Chikungunya", years=[year], states=[state]
                        )
                        dataframes.append(df)
                    except Exception as e:
                        logger.warning(f"Failed to download {state} {year}: {e}")

            if dataframes:
                return pd.concat(dataframes, ignore_index=True)
            else:
                return pd.DataFrame()
        else:
            return SINAN.download(disease="Chikungunya", years=years)

    def get_zika_cases(
        self, years: List[int], states: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Download Zika notification data from SINAN.

        Args:
            years: List of years to download
            states: List of state abbreviations

        Returns
        -------
            DataFrame with Zika case notifications
        """
        SINAN = self._get_sinan()

        logger.info(f"Downloading Zika data for years {years}...")

        if states:
            dataframes = []
            for state in states:
                for year in years:
                    try:
                        df = SINAN.download(
                            disease="Zika", years=[year], states=[state]
                        )
                        dataframes.append(df)
                    except Exception as e:
                        logger.warning(f"Failed to download {state} {year}: {e}")

            if dataframes:
                return pd.concat(dataframes, ignore_index=True)
            else:
                return pd.DataFrame()
        else:
            return SINAN.download(disease="Zika", years=years)

    def get_mortality(
        self,
        years: List[int],
        states: Optional[List[str]] = None,
        causes: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Download mortality data from SIM.

        Args:
            years: List of years to download
            states: List of state abbreviations
            causes: List of CID-10 cause codes (optional)

        Returns
        -------
            DataFrame with mortality records
        """
        SIM = self._get_sim()

        logger.info(f"Downloading mortality data for years {years}...")

        if states:
            dataframes = []
            for state in states:
                for year in years:
                    try:
                        df = SIM.download(years=[year], states=[state])
                        dataframes.append(df)
                    except Exception as e:
                        logger.warning(f"Failed to download {state} {year}: {e}")

            if dataframes:
                result = pd.concat(dataframes, ignore_index=True)

                # Filter by causes if specified
                if causes:
                    result = result[result["CAUSABAS"].isin(causes)]

                return result
            else:
                return pd.DataFrame()
        else:
            return SIM.download(years=years)

    def get_hospitalizations(
        self,
        years: List[int],
        months: Optional[List[int]] = None,
        states: Optional[List[str]] = None,
        group: str = "RD",
    ) -> pd.DataFrame:
        """
        Download hospitalization data from SIH.

        Args:
            years: List of years to download
            months: List of months (1-12), optional
            states: List of state abbreviations
            group: Data group ("RD"=Reduced, "ER"=Error, "RJ"=Rejected)

        Returns
        -------
            DataFrame with hospitalization records
        """
        SIH = self._get_sih()

        logger.info(f"Downloading hospitalization data for years {years}...")

        if months is None:
            months = list(range(1, 13))

        if states:
            dataframes = []
            for state in states:
                for year in years:
                    for month in months:
                        try:
                            df = SIH.download(
                                years=[year],
                                months=[month],
                                states=[state],
                                group=group,
                            )
                            dataframes.append(df)
                        except Exception as e:
                            logger.warning(
                                f"Failed to download {state} {year}-{month}: {e}"
                            )

            if dataframes:
                return pd.concat(dataframes, ignore_index=True)
            else:
                return pd.DataFrame()
        else:
            dataframes = []
            for year in years:
                for month in months:
                    try:
                        df = SIH.download(years=[year], months=[month], group=group)
                        dataframes.append(df)
                    except Exception as e:
                        logger.warning(f"Failed to download {year}-{month}: {e}")

            if dataframes:
                return pd.concat(dataframes, ignore_index=True)
            else:
                return pd.DataFrame()

    def list_available_diseases(self) -> pd.DataFrame:
        """
        List diseases available in SINAN.

        Returns
        -------
            DataFrame with disease names and codes
        """
        SINAN = self._get_sinan()

        diseases = [
            ("Dengue", "A90"),
            ("Malaria", "B50-B54"),
            ("Chikungunya", "A92.0"),
            ("Zika", "A92.5"),
            ("Yellow Fever", "A95"),
            ("Leishmaniasis", "B55"),
            ("Leptospirosis", "A27"),
            ("Chagas Disease", "B57"),
            ("Schistosomiasis", "B65"),
            ("Tuberculosis", "A15-A19"),
            ("HIV/AIDS", "B20-B24"),
            ("Meningitis", "G00-G03"),
            ("Hepatitis", "B15-B19"),
            ("Foodborne Illness", "A05"),
        ]

        return pd.DataFrame(diseases, columns=["disease_name", "cid10_code"])

    def list_states(self) -> pd.DataFrame:
        """
        List Brazilian states with their abbreviations.

        Returns
        -------
            DataFrame with state names and abbreviations
        """
        states = [
            ("Acre", "AC"),
            ("Alagoas", "AL"),
            ("Amapá", "AP"),
            ("Amazonas", "AM"),
            ("Bahia", "BA"),
            ("Ceará", "CE"),
            ("Distrito Federal", "DF"),
            ("Espírito Santo", "ES"),
            ("Goiás", "GO"),
            ("Maranhão", "MA"),
            ("Mato Grosso", "MT"),
            ("Mato Grosso do Sul", "MS"),
            ("Minas Gerais", "MG"),
            ("Pará", "PA"),
            ("Paraíba", "PB"),
            ("Paraná", "PR"),
            ("Pernambuco", "PE"),
            ("Piauí", "PI"),
            ("Rio de Janeiro", "RJ"),
            ("Rio Grande do Norte", "RN"),
            ("Rio Grande do Sul", "RS"),
            ("Rondônia", "RO"),
            ("Roraima", "RR"),
            ("Santa Catarina", "SC"),
            ("São Paulo", "SP"),
            ("Sergipe", "SE"),
            ("Tocantins", "TO"),
        ]

        return pd.DataFrame(states, columns=["state_name", "state_code"])
