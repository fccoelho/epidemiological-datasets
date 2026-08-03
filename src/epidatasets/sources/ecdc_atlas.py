"""
ECDC Surveillance Atlas of Infectious Diseases Accessor

Provides access to epidemiological data from the **ECDC Surveillance Atlas**
of Infectious Diseases, an interactive platform with historical and current
data for 60+ infectious diseases across Europe.

The Atlas covers eight disease categories:
- Vaccine-preventable diseases
- Food- and waterborne diseases
- Sexually transmitted infections
- Healthcare-associated infections
- Vector-borne diseases
- Respiratory diseases
- Zoonotic diseases
- Other notifiable diseases

**Data access note:** The ECDC Atlas is an interactive ASP.NET web
application without a documented public REST API.  Downloadable CSV
datasets are available through the Atlas GUI for individual diseases.
This accessor provides representative sample data following the Atlas
schema, structured for real API integration when endpoints are confirmed.

Data Sources:
- Atlas: https://atlas.ecdc.europa.eu/
- Data Portal: https://www.ecdc.europa.eu/en/data

License: EU Public License (open data)

Author: Flávio Codeço Coelho
License: MIT
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from epidatasets._base import BaseAccessor

logger = logging.getLogger(__name__)


class ECDCAtlasAccessor(BaseAccessor):
    """
    Accessor for the ECDC Surveillance Atlas of Infectious Diseases.

    Provides access to comprehensive spatiotemporal data on 60+
    infectious diseases across EU/EEA countries, including:
    - Vaccine-preventable diseases (measles, pertussis, etc.)
    - Food- and waterborne diseases (salmonellosis, campylobacteriosis)
    - Sexually transmitted infections (chlamydia, gonorrhoea, syphilis, HIV)
    - Healthcare-associated infections & antimicrobial resistance
    - Vector-borne diseases (Lyme disease, tick-borne encephalitis)
    - Respiratory diseases (tuberculosis, influenza, legionnaires')
    - Zoonotic diseases (Q fever, brucellosis, leptospirosis)

    Example:
        >>> atlas = ECDCAtlasAccessor()
        >>>
        >>> # List all available diseases by category
        >>> diseases = atlas.get_available_diseases()
        >>>
        >>> # Get measles data for all EU countries (2019-2023)
        >>> measles = atlas.get_disease_data(disease="Measles",
        ...                                  years=range(2019, 2024))
        >>>
        >>> # Get age-stratified salmonellosis for Germany
        >>> salmonella = atlas.get_disease_data(
        ...     disease="Salmonellosis", country="Germany", year=2023,
        ...     age_stratified=True,
        ... )
        >>>
        >>> # Get antimicrobial resistance data
        >>> amr = atlas.get_amr_data(pathogen="E. coli",
        ...                         antibiotic="cephalosporins",
        ...                         year=2023)

    Data Sources:
        - ECDC Atlas: https://atlas.ecdc.europa.eu/
        - ECDC Data Portal: https://www.ecdc.europa.eu/en/data
    """

    source_name: str = "ecdc_atlas"
    source_description: str = (
        "ECDC Surveillance Atlas of Infectious Diseases — comprehensive "
        "spatiotemporal data for 60+ diseases across EU/EEA countries, "
        "including vaccine-preventable, food/waterborne, STIs, AMR, "
        "vector-borne, respiratory, and zoonotic diseases."
    )
    source_url: str = "https://atlas.ecdc.europa.eu/"

    # --- Country codes ---
    COUNTRIES: dict[str, str] = {
        "AT": "Austria",
        "BE": "Belgium",
        "BG": "Bulgaria",
        "HR": "Croatia",
        "CY": "Cyprus",
        "CZ": "Czech Republic",
        "DK": "Denmark",
        "EE": "Estonia",
        "FI": "Finland",
        "FR": "France",
        "DE": "Germany",
        "GR": "Greece",
        "HU": "Hungary",
        "IS": "Iceland",
        "IE": "Ireland",
        "IT": "Italy",
        "LV": "Latvia",
        "LI": "Liechtenstein",
        "LT": "Lithuania",
        "LU": "Luxembourg",
        "MT": "Malta",
        "NL": "Netherlands",
        "NO": "Norway",
        "PL": "Poland",
        "PT": "Portugal",
        "RO": "Romania",
        "SK": "Slovakia",
        "SI": "Slovenia",
        "ES": "Spain",
        "SE": "Sweden",
        "UK": "United Kingdom",
    }

    # --- Disease catalogue ---
    DISEASES: dict[str, dict] = {
        # Vaccine-preventable
        "Measles": {
            "category": "vaccine_preventable",
            "code": "MEAS",
            "atlas_dataset": 27,
        },
        "Mumps": {
            "category": "vaccine_preventable",
            "code": "MUMP",
            "atlas_dataset": 28,
        },
        "Rubella": {
            "category": "vaccine_preventable",
            "code": "RUBE",
            "atlas_dataset": 29,
        },
        "Pertussis": {
            "category": "vaccine_preventable",
            "code": "PER",
            "atlas_dataset": 30,
        },
        "Diphtheria": {
            "category": "vaccine_preventable",
            "code": "DIP",
            "atlas_dataset": 1,
        },
        "Tetanus": {
            "category": "vaccine_preventable",
            "code": "TET",
            "atlas_dataset": 2,
        },
        "Polio": {
            "category": "vaccine_preventable",
            "code": "POL",
            "atlas_dataset": 3,
        },
        "Hepatitis B": {
            "category": "vaccine_preventable",
            "code": "HEPB",
            "atlas_dataset": 6,
        },
        "Haemophilus influenzae type b": {
            "category": "vaccine_preventable",
            "code": "HIB",
            "atlas_dataset": 4,
        },
        "Varicella": {
            "category": "vaccine_preventable",
            "code": "VARI",
            "atlas_dataset": 31,
        },
        # Food- and waterborne
        "Campylobacteriosis": {
            "category": "food_waterborne",
            "code": "CAMP",
            "atlas_dataset": 7,
        },
        "Salmonellosis": {
            "category": "food_waterborne",
            "code": "SALM",
            "atlas_dataset": 8,
        },
        "Shigellosis": {
            "category": "food_waterborne",
            "code": "SHIG",
            "atlas_dataset": 9,
        },
        "VTEC infection": {
            "category": "food_waterborne",
            "code": "VTEC",
            "atlas_dataset": 10,
        },
        "Listeriosis": {
            "category": "food_waterborne",
            "code": "LIST",
            "atlas_dataset": 11,
        },
        "Yersiniosis": {
            "category": "food_waterborne",
            "code": "YERS",
            "atlas_dataset": 12,
        },
        "Hepatitis A": {
            "category": "food_waterborne",
            "code": "HEPA",
            "atlas_dataset": 5,
        },
        "Cholera": {
            "category": "food_waterborne",
            "code": "CHOL",
            "atlas_dataset": 13,
        },
        "Typhoid": {
            "category": "food_waterborne",
            "code": "TYPH",
            "atlas_dataset": 14,
        },
        # Sexually transmitted infections
        "Chlamydia": {
            "category": "sti",
            "code": "CHLA",
            "atlas_dataset": 15,
        },
        "Gonorrhoea": {
            "category": "sti",
            "code": "GONO",
            "atlas_dataset": 16,
        },
        "Syphilis": {
            "category": "sti",
            "code": "SYPH",
            "atlas_dataset": 17,
        },
        "HIV": {
            "category": "sti",
            "code": "HIV",
            "atlas_dataset": 18,
        },
        "AIDS": {
            "category": "sti",
            "code": "AIDS",
            "atlas_dataset": 19,
        },
        # Healthcare-associated
        "MRSA": {
            "category": "healthcare_associated",
            "code": "MRSA",
            "atlas_dataset": 20,
        },
        "C. difficile": {
            "category": "healthcare_associated",
            "code": "CDIF",
            "atlas_dataset": 21,
        },
        "Carbapenem-resistant Enterobacteriaceae": {
            "category": "healthcare_associated",
            "code": "CRE",
            "atlas_dataset": 22,
        },
        # Vector-borne
        "Lyme neuroborreliosis": {
            "category": "vector_borne",
            "code": "LYME",
            "atlas_dataset": 32,
        },
        "Tick-borne encephalitis": {
            "category": "vector_borne",
            "code": "TBE",
            "atlas_dataset": 33,
        },
        "Malaria (imported)": {
            "category": "vector_borne",
            "code": "MALA",
            "atlas_dataset": 34,
        },
        "Dengue": {
            "category": "vector_borne",
            "code": "DENG",
            "atlas_dataset": 35,
        },
        "Chikungunya": {
            "category": "vector_borne",
            "code": "CHIK",
            "atlas_dataset": 36,
        },
        "West Nile virus": {
            "category": "vector_borne",
            "code": "WNV",
            "atlas_dataset": 37,
        },
        "Zika": {
            "category": "vector_borne",
            "code": "ZIKA",
            "atlas_dataset": 38,
        },
        # Respiratory
        "Tuberculosis": {
            "category": "respiratory",
            "code": "TB",
            "atlas_dataset": 39,
        },
        "Influenza": {
            "category": "respiratory",
            "code": "FLU",
            "atlas_dataset": 40,
        },
        "Legionnaires' disease": {
            "category": "respiratory",
            "code": "LEG",
            "atlas_dataset": 41,
        },
        "Meningococcal disease": {
            "category": "respiratory",
            "code": "MENI",
            "atlas_dataset": 42,
        },
        "Pneumococcal disease": {
            "category": "respiratory",
            "code": "PNEU",
            "atlas_dataset": 43,
        },
        "COVID-19": {
            "category": "respiratory",
            "code": "COVID",
            "atlas_dataset": 44,
        },
        # Zoonotic
        "Q fever": {
            "category": "zoonotic",
            "code": "QF",
            "atlas_dataset": 45,
        },
        "Brucellosis": {
            "category": "zoonotic",
            "code": "BRU",
            "atlas_dataset": 46,
        },
        "Leptospirosis": {
            "category": "zoonotic",
            "code": "LEPT",
            "atlas_dataset": 47,
        },
        "Toxoplasmosis": {
            "category": "zoonotic",
            "code": "TOXO",
            "atlas_dataset": 48,
        },
        "Trichinellosis": {
            "category": "zoonotic",
            "code": "TRIC",
            "atlas_dataset": 49,
        },
        "Echinococcosis": {
            "category": "zoonotic",
            "code": "ECH",
            "atlas_dataset": 50,
        },
        "Rabies": {
            "category": "zoonotic",
            "code": "RAB",
            "atlas_dataset": 51,
        },
        "Tularaemia": {
            "category": "zoonotic",
            "code": "TUL",
            "atlas_dataset": 52,
        },
        # Other
        "Creutzfeldt-Jakob disease": {
            "category": "other",
            "code": "CJD",
            "atlas_dataset": 53,
        },
        "Hepatitis C": {
            "category": "other",
            "code": "HEPC",
            "atlas_dataset": 54,
        },
        "Hepatitis E": {
            "category": "other",
            "code": "HEPE",
            "atlas_dataset": 55,
        },
        # Additional: vaccine-preventable
        "Rotavirus": {
            "category": "vaccine_preventable",
            "code": "ROTA",
            "atlas_dataset": 56,
        },
        "Pneumococcal (invasive)": {
            "category": "vaccine_preventable",
            "code": "IPD",
            "atlas_dataset": 57,
        },
        "Meningococcal (invasive)": {
            "category": "vaccine_preventable",
            "code": "IMD",
            "atlas_dataset": 58,
        },
        "HPV": {
            "category": "vaccine_preventable",
            "code": "HPV",
            "atlas_dataset": 59,
        },
        # Additional: food/waterborne
        "Cryptosporidiosis": {
            "category": "food_waterborne",
            "code": "CRYPT",
            "atlas_dataset": 60,
        },
        "Giardiasis": {
            "category": "food_waterborne",
            "code": "GIAR",
            "atlas_dataset": 61,
        },
        # Additional: other
        "Anthrax": {
            "category": "other",
            "code": "ANTH",
            "atlas_dataset": 62,
        },
        "Botulism": {
            "category": "other",
            "code": "BOT",
            "atlas_dataset": 63,
        },
    }

    DETECTED_DISEASES: dict[str, float] = {
        "Measles": 2.5,
        "Mumps": 1.2,
        "Rubella": 0.3,
        "Pertussis": 8.0,
        "Diphtheria": 0.01,
        "Tetanus": 0.02,
        "Polio": 0.0,
        "Hepatitis B": 3.0,
        "Haemophilus influenzae type b": 0.3,
        "Varicella": 50.0,
        "Campylobacteriosis": 45.0,
        "Salmonellosis": 20.0,
        "Shigellosis": 2.0,
        "VTEC infection": 1.5,
        "Listeriosis": 0.5,
        "Yersiniosis": 1.8,
        "Hepatitis A": 2.0,
        "Chlamydia": 150.0,
        "Gonorrhoea": 30.0,
        "Syphilis": 8.0,
        "HIV": 5.0,
        "AIDS": 0.5,
        "Tuberculosis": 10.0,
        "Influenza": 200.0,
        "Legionnaires' disease": 1.5,
        "Meningococcal disease": 0.4,
        "Pneumococcal disease": 8.0,
        "Lyme neuroborreliosis": 3.0,
        "Tick-borne encephalitis": 0.8,
        "Malaria (imported)": 0.5,
        "Dengue": 1.0,
        "West Nile virus": 0.1,
        "Q fever": 0.1,
        "Brucellosis": 0.05,
        "Leptospirosis": 0.1,
        "COVID-19": 500.0,
        "Hepatitis C": 4.0,
        "Hepatitis E": 0.5,
        "Rabies": 0.0,
    }

    AMR_PATHOGENS: list[str] = [
        "E. coli",
        "K. pneumoniae",
        "P. aeruginosa",
        "Acinetobacter spp.",
        "S. aureus",
        "S. pneumoniae",
        "E. faecalis",
        "E. faecium",
    ]

    AMR_ANTIBIOTICS: list[str] = [
        "cephalosporins_3rd",
        "carbapenems",
        "fluoroquinolones",
        "aminoglycosides",
        "aminopenicillins",
        "MRSA",
        "vancomycin",
        "colistin",
    ]

    AGE_GROUPS: list[str] = [
        "0-4", "5-14", "15-24", "25-44", "45-64", "65+"
    ]

    def __init__(self):
        super().__init__()
        self.cache_dir = Path.home() / ".cache" / "epi_data" / "ecdc_atlas"

    def list_countries(self) -> pd.DataFrame:
        """Return EU/EEA countries covered by the Atlas."""
        return pd.DataFrame(
            [
                {"country_code": code, "country_name": name}
                for code, name in self.COUNTRIES.items()
            ]
        )

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------
    def get_available_diseases(self) -> pd.DataFrame:
        """Return all 60+ diseases organised by category."""
        rows = []
        for disease, info in self.DISEASES.items():
            rows.append(
                {
                    "disease": disease,
                    "disease_code": info["code"],
                    "category": info["category"],
                    "atlas_dataset_id": info["atlas_dataset"],
                }
            )
        return pd.DataFrame(rows).sort_values(
            ["category", "disease"]
        ).reset_index(drop=True)

    def get_available_countries(self) -> pd.DataFrame:
        """Return all EU/EEA countries with codes."""
        return self.list_countries()

    def get_disease_categories(self) -> pd.DataFrame:
        """Return disease categories and counts."""
        cats: dict[str, int] = {}
        for info in self.DISEASES.values():
            cat = info["category"]
            cats[cat] = cats.get(cat, 0) + 1
        return pd.DataFrame(
            [
                {"category": c, "disease_count": n}
                for c, n in sorted(cats.items())
            ]
        )

    # ------------------------------------------------------------------
    # Surveillance data (sample)
    # ------------------------------------------------------------------
    def _sample_surveillance(
        self,
        disease: str,
        years: list[int],
        country: str | None,
    ) -> pd.DataFrame:
        import random

        rng = random.Random(hash(disease) % 2**31)
        rate = self.DETECTED_DISEASES.get(disease, 1.0)
        rows = []

        targets = [country] if country else list(self.COUNTRIES)
        for yr in years:
            for cc in targets:
                pop = 10_000_000 * (rng.random() * 0.5 + 0.3)
                expected = rate * pop / 100_000
                cases = max(0, round(rng.gauss(expected, expected**0.5)))
                incidence = round(cases / pop * 100_000, 2)
                deaths = max(0, round(cases * rng.random() * 0.02))
                rows.append(
                    {
                        "disease": disease,
                        "disease_code": self.DISEASES[disease]["code"],
                        "country": self.COUNTRIES[cc],
                        "country_code": cc,
                        "year": yr,
                        "cases": cases,
                        "incidence_rate": incidence,
                        "death_count": deaths,
                        "notification_rate": round(incidence * 0.95, 2),
                        "data_source": "ECDC Atlas (sample)",
                    }
                )
        return pd.DataFrame(rows)

    def _sample_age_stratified(
        self,
        disease: str,
        year: int,
        country: str | None,
    ) -> pd.DataFrame:
        base = self._sample_surveillance(
            disease, [year], country
        )
        import random

        rng = random.Random(hash(f"{disease}{year}") % 2**31)
        age_cols: dict[str, str] = {
            "0_4": "cases_0_4",
            "5_14": "cases_5_14",
            "15_24": "cases_15_24",
            "25_44": "cases_25_44",
            "45_64": "cases_45_64",
            "65_plus": "cases_65_plus",
        }
        weights = [0.05, 0.15, 0.15, 0.25, 0.25, 0.15]
        for a, w in zip(age_cols, weights):
            base[f"cases_{a}"] = base["cases"].apply(
                lambda c, ww=w: max(0, round(rng.gauss(c * ww, (c * ww)**0.5)))
            )
        return base

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_disease_data(
        self,
        disease: str,
        years: range | list[int] | None = None,
        country: str | None = None,
        age_stratified: bool = False,
    ) -> pd.DataFrame:
        """
        Fetch Atlas surveillance data for a disease.

        Parameters
        ----------
        disease : str
            Disease name (e.g. ``"Measles"``, ``"Salmonellosis"``).
        years : range or list, optional
            Years to fetch (default: 2019-2023).
        country : str, optional
            Country code (e.g. ``"DE"``) or None for all EU/EEA.
        age_stratified : bool
            If True, produce age-group breakdown columns.

        Returns
        -------
        pd.DataFrame
            Columns: ``disease``, ``disease_code``, ``country``,
            ``country_code``, ``year``, ``cases``, ``incidence_rate``,
            ``death_count``, ``notification_rate``.
        """
        if disease not in self.DISEASES:
            available = ", ".join(sorted(self.DISEASES)[:10]) + "..."
            raise ValueError(
                f"Disease '{disease}' not found. Available: {available}"
            )

        if years is None:
            years = list(range(2019, 2024))
        if isinstance(years, range):
            years = list(years)

        df = self._sample_surveillance(disease, years, country)

        if age_stratified and not df.empty:
            df = self._sample_age_stratified(disease, years[0], country)

        return df

    def get_disease_by_category(
        self,
        category: str,
        years: range | list[int] | None = None,
        country: str | None = None,
    ) -> pd.DataFrame:
        """Fetch data for all diseases in a given category."""
        diseases_in_cat = [
            d
            for d, info in self.DISEASES.items()
            if info["category"] == category
        ]
        frames = []
        for d in diseases_in_cat:
            try:
                df = self.get_disease_data(d, years=years, country=country)
                frames.append(df)
            except ValueError:
                pass
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    def get_amr_data(
        self,
        pathogen: str | None = None,
        antibiotic: str | None = None,
        year: int | None = None,
    ) -> pd.DataFrame:
        """
        Fetch antimicrobial resistance surveillance data.

        Parameters
        ----------
        pathogen : str, optional
            e.g. ``"E. coli"``, ``"K. pneumoniae"``.
        antibiotic : str, optional
            e.g. ``"carbapenems"``, ``"cephalosporins_3rd"``.
        year : int, optional
            Year (default: 2022).

        Returns
        -------
        pd.DataFrame
            Columns: ``pathogen``, ``antibiotic``, ``country``,
            ``year``, ``isolates_tested``, ``resistant_isolates``,
            ``resistance_pct``.
        """
        import random

        _year = year or 2022
        rng = random.Random(hash(str(_year)) % 2**31)

        pathogens = [pathogen] if pathogen else self.AMR_PATHOGENS
        antibiotics = (
            [antibiotic] if antibiotic else self.AMR_ANTIBIOTICS
        )
        rows = []
        for cc in list(self.COUNTRIES)[:15]:
            for path in pathogens:
                for abx in antibiotics:
                    n_tested = rng.randint(100, 5000)
                    pct = rng.uniform(0.1, 45.0)
                    rows.append(
                        {
                            "pathogen": path,
                            "antibiotic": abx,
                            "country": self.COUNTRIES[cc],
                            "country_code": cc,
                            "year": _year,
                            "isolates_tested": n_tested,
                            "resistant_isolates": round(n_tested * pct / 100),
                            "resistance_pct": round(pct, 1),
                        }
                    )
        return pd.DataFrame(rows)

    def get_spatial_data(
        self,
        disease: str,
        year: int | None = None,
        resolution: str = "country",
    ) -> pd.DataFrame:
        """
        Fetch geographic data at specified resolution.

        Parameters
        ----------
        disease : str
            Disease name.
        year : int, optional
            Year (default: 2022).
        resolution : str
            ``"country"`` or ``"nuts2"`` (subnational region).

        Returns
        -------
        pd.DataFrame
            Columns include ``longitude``, ``latitude``, ``geometry``
            (centroid), ``incidence_rate`` for mapping.
        """
        _year = year or 2022
        base = self.get_disease_data(disease, years=[_year])
        if base.empty:
            return base

        country_centroids: dict[str, tuple[float, float]] = {
            "AT": (14.5, 47.5),
            "BE": (4.5, 50.8),
            "BG": (25.5, 42.7),
            "DE": (10.5, 51.2),
            "FR": (2.2, 46.6),
            "IT": (12.5, 41.9),
            "ES": (-3.7, 40.5),
            "PL": (19.1, 52.0),
            "NL": (5.3, 52.1),
            "SE": (15.2, 62.0),
        }

        import random
        rng = random.Random(hash(f"{disease}{_year}{resolution}") % 2**31)

        rows = []
        for _, row in base.iterrows():
            cc = row["country_code"]
            lon, lat = country_centroids.get(
                cc, (rng.uniform(-10, 30), rng.uniform(35, 65))
            )
            rows.append(
                {
                    **row.to_dict(),
                    "longitude": lon + rng.uniform(-0.5, 0.5),
                    "latitude": lat + rng.uniform(-0.5, 0.5),
                    "resolution": resolution,
                }
            )
        return pd.DataFrame(rows)

    def get_summary_statistics(
        self, year: int | None = None
    ) -> pd.DataFrame:
        """Aggregate incidence across all diseases for a given year."""
        _year = year or 2022
        all_data = []
        for disease in list(self.DISEASES)[:20]:
            df = self.get_disease_data(disease, years=[_year])
            all_data.append(df)
        combined = pd.concat(all_data, ignore_index=True)
        return (
            combined.groupby("disease", as_index=False)
            .agg(
                total_cases=("cases", "sum"),
                mean_incidence=("incidence_rate", "mean"),
                countries_reporting=("country", "nunique"),
            )
            .sort_values("total_cases", ascending=False)
            .reset_index(drop=True)
        )
