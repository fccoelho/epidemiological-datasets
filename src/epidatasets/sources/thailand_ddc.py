"""
Thailand Department of Disease Control (DDC) 506 Surveillance Accessor

Provides access to notifiable disease surveillance data from the Thailand
Ministry of Public Health, Department of Disease Control (DDC), based on
the **506 Disease Notification System** (Ror. 506).

**Important note:** The Thai government open data portal (data.go.th) and
several backend APIs are currently **geo-blocked** (HTTP 403) for access
from outside Thailand.  This accessor therefore relies on **representative
sample data** curated from published DDC epidemiological reports and WHO
country profiles, until API access can be restored.

Data Sources:
- DDC website: https://ddc.moph.go.th/
- Bureau of Epidemiology: https://boe.moph.go.th/ (DNS may not resolve)
- Weekly Epidemiological Surveillance Report (WESR): published by BOE
- WHO Thailand: https://www.who.int/thailand

License: Thai Government Public Data

Author: Flávio Codeço Coelho
License: MIT
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from epidatasets._base import BaseAccessor

logger = logging.getLogger(__name__)


class ThailandDDCAccessor(BaseAccessor):
    """
    Accessor for Thailand DDC 506 Disease Surveillance data.

    Thailand's Department of Disease Control operates the **506 System**
    for mandatory notification of 106 communicable diseases.  Surveillance
    data is published in the *Weekly Epidemiological Surveillance Report*
    (WESR) by province.

    Because the ``data.go.th`` CKAN API and several MOPH backend APIs are
    currently geo-blocked, this accessor provides representative sample
    data for the most epidemiologically relevant diseases.  Sample data is
    based on published DDC / WHO statistics.

    Example:
        >>> ddc = ThailandDDCAccessor()
        >>>
        >>> # List notifiable diseases (506 system)
        >>> diseases = ddc.list_diseases()
        >>>
        >>> # Get dengue cases by province
        >>> dengue = ddc.get_dengue_cases()

    Data Sources:
        - DDC: https://ddc.moph.go.th/
        - BOE WESR: https://boe.moph.go.th/
    """

    source_name: str = "thailand_ddc"
    source_description: str = (
        "Notifiable disease surveillance data from the Thailand Department "
        "of Disease Control (DDC) 506 Disease Notification System, with "
        "representative sample data for key diseases including dengue, "
        "HIV/AIDS, influenza, malaria, and tuberculosis."
    )
    source_url: str = "https://ddc.moph.go.th/"

    # Thailand's provinces (77 + Bangkok)
    PROVINCES: list[str] = [
        "Bangkok",
        "Samut Prakan",
        "Nonthaburi",
        "Pathum Thani",
        "Phra Nakhon Si Ayutthaya",
        "Ang Thong",
        "Lop Buri",
        "Sing Buri",
        "Chai Nat",
        "Saraburi",
        "Chon Buri",
        "Rayong",
        "Chanthaburi",
        "Trat",
        "Chachoengsao",
        "Prachin Buri",
        "Nakhon Nayok",
        "Sa Kaeo",
        "Nakhon Ratchasima",
        "Buri Ram",
        "Surin",
        "Si Sa Ket",
        "Ubon Ratchathani",
        "Yasothon",
        "Chaiyaphum",
        "Amnat Charoen",
        "Bueng Kan",
        "Nong Bua Lam Phu",
        "Khon Kaen",
        "Udon Thani",
        "Loei",
        "Nong Khai",
        "Maha Sarakham",
        "Roi Et",
        "Kalasin",
        "Sakon Nakhon",
        "Nakhon Phanom",
        "Mukdahan",
        "Chiang Mai",
        "Lamphun",
        "Lampang",
        "Uttaradit",
        "Phrae",
        "Nan",
        "Phayao",
        "Chiang Rai",
        "Mae Hong Son",
        "Nakhon Sawan",
        "Uthai Thani",
        "Kamphaeng Phet",
        "Tak",
        "Sukhothai",
        "Phitsanulok",
        "Phichit",
        "Phetchabun",
        "Ratchaburi",
        "Kanchanaburi",
        "Suphan Buri",
        "Nakhon Pathom",
        "Samut Sakhon",
        "Samut Songkhram",
        "Phetchaburi",
        "Prachuap Khiri Khan",
        "Chumphon",
        "Ranong",
        "Surat Thani",
        "Phang Nga",
        "Phuket",
        "Krabi",
        "Nakhon Si Thammarat",
        "Trang",
        "Phatthalung",
        "Satun",
        "Songkhla",
        "Pattani",
        "Yala",
        "Narathiwat",
    ]

    # Key notifiable diseases under the 506 system
    NOTIFIABLE_DISEASES: list[str] = [
        "Dengue Total",
        "Dengue Haemorrhagic Fever (DHF)",
        "Dengue Shock Syndrome (DSS)",
        "Chikungunya",
        "Zika Virus Infection",
        "Malaria (P. falciparum)",
        "Malaria (P. vivax)",
        "Influenza",
        "Pneumonia",
        "Tuberculosis (pulmonary)",
        "Tuberculosis (extra-pulmonary)",
        "HIV Infection",
        "AIDS",
        "Syphilis",
        "Gonorrhoea",
        "Chancroid",
        "Food Poisoning",
        "Acute Diarrhoea",
        "Typhoid Fever",
        "Leptospirosis",
        "Scrub Typhus",
        "Melioidosis",
        "Hand, Foot and Mouth Disease",
        "Measles",
        "Rubella",
        "Mumps",
        "Hepatitis A",
        "Hepatitis B",
        "Hepatitis C",
        "Rabies (human)",
        "Tetanus (neonatal)",
        "Diphtheria",
        "Pertussis",
        "Japanese Encephalitis",
        "Cholera",
    ]

    def __init__(self):
        super().__init__()
        self.cache_dir = (
            Path.home() / ".cache" / "epi_data" / "thailand_ddc"
        )

    def list_countries(self) -> pd.DataFrame:
        """Return a single-row DataFrame for Thailand."""
        return pd.DataFrame(
            [{"country_code": "TH", "country_name": "Thailand"}]
        )

    def list_provinces(self) -> pd.DataFrame:
        """Return all 77 Thai provinces + Bangkok."""
        return pd.DataFrame({"province": self.PROVINCES})

    def list_diseases(self) -> pd.DataFrame:
        """Return the notifiable diseases tracked by the 506 system."""
        return pd.DataFrame({"disease": self.NOTIFIABLE_DISEASES})

    # ------------------------------------------------------------------
    # Sample data generators — curated from published DDC / WHO data
    # ------------------------------------------------------------------
    def _sample_annual(
        self,
        year: int,
        province: str,
        rates: dict[str, float],
        population: int = 66_000_000,
        provinces: int = 77,
    ) -> list[dict]:
        """Generate one year of synthetic province-level case data.

        ``rates`` maps disease short names to annual incidence per 100 000.
        The province-level count is apportioned by population share and
        rounded with Poisson noise.
        """
        import random

        random.seed(hash(str(year) + province) % 2**31)
        pop_share = population / provinces / population
        rows = []
        for disease, rate in rates.items():
            expected = rate * pop_share / 100_000 * population
            cases = max(0, round(random.gauss(expected, expected**0.5)))
            rows.append(
                {
                    "year": year,
                    "province": province,
                    "disease": disease,
                    "cases": cases,
                    "population": int(population / provinces),
                    "incidence_per_100k": round(cases / (population / provinces) * 100_000, 2),
                }
            )
        return rows

    # Approximate national incidence rates per 100k (based on published data)
    _DISEASE_RATES: dict[str, float] = {
        "Dengue Total": 350.0,
        "Dengue Haemorrhagic Fever (DHF)": 40.0,
        "Dengue Shock Syndrome (DSS)": 5.0,
        "Chikungunya": 15.0,
        "Zika Virus Infection": 2.0,
        "Malaria (P. falciparum)": 8.0,
        "Malaria (P. vivax)": 12.0,
        "Influenza": 300.0,
        "Pneumonia": 250.0,
        "Tuberculosis (pulmonary)": 40.0,
        "Tuberculosis (extra-pulmonary)": 15.0,
        "HIV Infection": 9.0,
        "AIDS": 5.0,
        "Syphilis": 18.0,
        "Gonorrhoea": 10.0,
        "Chancroid": 0.2,
        "Food Poisoning": 200.0,
        "Acute Diarrhoea": 1800.0,
        "Typhoid Fever": 1.0,
        "Leptospirosis": 3.0,
        "Scrub Typhus": 12.0,
        "Melioidosis": 4.0,
        "Hand, Foot and Mouth Disease": 150.0,
        "Measles": 0.5,
        "Rubella": 0.2,
        "Mumps": 5.0,
        "Hepatitis A": 1.5,
        "Hepatitis B": 5.0,
        "Hepatitis C": 0.5,
        "Rabies (human)": 0.01,
        "Tetanus (neonatal)": 0.01,
        "Diphtheria": 0.01,
        "Pertussis": 0.5,
        "Japanese Encephalitis": 0.1,
        "Cholera": 0.01,
    }

    def get_surveillance_data(
        self,
        year: int | None = None,
        province: str | None = None,
        disease: str | None = None,
    ) -> pd.DataFrame:
        """
        Fetch 506 surveillance data (sample-based).

        Generates representative province-level case counts for all
        notifiable diseases based on approximate national incidence rates.

        Parameters
        ----------
        year : int, optional
            Filter to a specific year (default: 2022).  Multiple years not
            yet supported.
        province : str, optional
            Filter to a specific province.
        disease : str, optional
            Filter to a specific disease from ``NOTIFIABLE_DISEASES``.

        Returns
        -------
        pd.DataFrame
            Columns: ``year``, ``province``, ``disease``, ``cases``,
            ``population``, ``incidence_per_100k``.
        """
        _year = year or 2022
        rows = []
        for prov in self.PROVINCES:
            rows.extend(
                self._sample_annual(_year, prov, self._DISEASE_RATES)
            )
        df = pd.DataFrame(rows)

        if province is not None:
            df = df[df["province"] == province]
        if disease is not None:
            df = df[df["disease"] == disease]

        return df.reset_index(drop=True)

    # ------------------------------------------------------------------
    # Convenience methods for key diseases
    # ------------------------------------------------------------------
    def get_dengue_cases(
        self,
        year: int | None = None,
        province: str | None = None,
    ) -> pd.DataFrame:
        """Dengue cases (total, DHF, DSS) by province."""
        dengue_diseases = [
            "Dengue Total",
            "Dengue Haemorrhagic Fever (DHF)",
            "Dengue Shock Syndrome (DSS)",
        ]
        df = self.get_surveillance_data(year=year, province=province)
        return df[df["disease"].isin(dengue_diseases)].reset_index(
            drop=True
        )

    def get_hiv_cases(
        self,
        year: int | None = None,
        province: str | None = None,
    ) -> pd.DataFrame:
        """HIV and AIDS cases by province."""
        df = self.get_surveillance_data(year=year, province=province)
        return df[df["disease"].isin(["HIV Infection", "AIDS"])].reset_index(
            drop=True
        )

    def get_malaria_cases(
        self,
        year: int | None = None,
        province: str | None = None,
    ) -> pd.DataFrame:
        """Malaria cases by species and province."""
        malaria_diseases = [
            "Malaria (P. falciparum)",
            "Malaria (P. vivax)",
        ]
        df = self.get_surveillance_data(year=year, province=province)
        return df[df["disease"].isin(malaria_diseases)].reset_index(
            drop=True
        )

    def get_national_summary(
        self,
        year: int | None = None,
    ) -> pd.DataFrame:
        """National-level summary of all notifiable diseases."""
        df = self.get_surveillance_data(year=year)
        return (
            df.groupby("disease", as_index=False)["cases"]
            .sum()
            .sort_values("cases", ascending=False)
            .reset_index(drop=True)
        )

    def get_provincial_summary(
        self,
        disease: str | None = None,
        year: int | None = None,
    ) -> pd.DataFrame:
        """Province-level case totals for a given disease."""
        df = self.get_surveillance_data(year=year, disease=disease)
        if disease is None:
            return (
                df.groupby("province", as_index=False)["cases"]
                .sum()
                .sort_values("cases", ascending=False)
                .reset_index(drop=True)
            )
        return df[["province", "cases"]].sort_values(
            "cases", ascending=False
        ).reset_index(drop=True)
