"""
Robert Koch Institute (RKI) Data Accessor

This module provides access to infectious disease surveillance data from Germany's
Robert Koch Institute (RKI), including:
- COVID-19 surveillance and nowcasting data
- Influenza weekly reports
- Notifiable infectious diseases (Meldepflichtige Krankheiten)
- Vaccination coverage data
- Antimicrobial resistance surveillance

Data Sources:
- RKI GitHub: https://github.com/robert-koch-institut
- COVID-19 Dashboard: https://corona.rki.de/
- Surveillance reports: https://www.rki.de/EN/Content/infections/epidemiology/data.html

Update Frequency:
- COVID-19: Daily
- Influenza: Weekly
- Notifiable diseases: Weekly/Monthly (varies by disease)
- Vaccination: Monthly/Quarterly

License: Open Data (dl-de/by-2-0)

Author: Flávio Codeço Coelho
License: MIT
"""

import logging
from datetime import datetime
from typing import List, Optional, Tuple

import pandas as pd
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RKIGermanyAccessor:
    """
    Accessor for Robert Koch Institute (RKI) data from Germany.

    Provides access to:
    - COVID-19 cases, deaths, hospitalizations
    - Influenza surveillance (AGI Sentinel system)
    - Notifiable infectious diseases
    - Vaccination coverage
    - Antimicrobial resistance data

    Example:
        >>> rki = RKIGermanyAccessor()
        >>>
        >>> # Get COVID-19 data
        >>> covid = rki.get_covid_cases(
        ...     states=["Berlin", "Bayern"],
        ...     date_range=("2022-01-01", "2022-12-31")
        ... )
        >>>
        >>> # Get influenza surveillance
        >>> flu = rki.get_influenza_data(seasons=["2022/23", "2023/24"])
        >>>
        >>> # Get notifiable diseases
        >>> measles = rki.get_notifiable_disease("Measles", years=[2022, 2023])

    Data Sources:
        - RKI GitHub: https://github.com/robert-koch-institut
        - SurvStat@RKI 2.0: https://survstat.rki.de/
        - COVID-19 Nowcasting: https://github.com/robert-koch-institut/SARS-CoV-2-Nowcasting_und_-R-Schaetzung
    """

    # GitHub base URL for RKI data
    GITHUB_BASE = "https://raw.githubusercontent.com/robert-koch-institut"

    # RKI data repositories
    REPOS = {
        "covid_nowcast": "SARS-CoV-2-Nowcasting_und_-R-Schaetzung",
        "influenza": "Influenza-Wochenberichte",
        "covid_cases": "SARS-CoV-2-Infektionen_in_Deutschland",
        "covid_hosp": "COVID-19-Hospitalisierungen_in_Deutschland",
        "covid_impf": "COVID-19-Impfungen_in_Deutschland",
    }

    # German federal states (Bundesländer)
    STATES = {
        "DE-BW": "Baden-Württemberg",
        "DE-BY": "Bayern",
        "DE-BE": "Berlin",
        "DE-BB": "Brandenburg",
        "DE-HB": "Bremen",
        "DE-HH": "Hamburg",
        "DE-HE": "Hessen",
        "DE-MV": "Mecklenburg-Vorpommern",
        "DE-NI": "Niedersachsen",
        "DE-NW": "Nordrhein-Westfalen",
        "DE-RP": "Rheinland-Pfalz",
        "DE-SL": "Saarland",
        "DE-SN": "Sachsen",
        "DE-ST": "Sachsen-Anhalt",
        "DE-SH": "Schleswig-Holstein",
        "DE-TH": "Thüringen",
        "DE": "Deutschland (Germany)",
    }

    # Notifiable infectious diseases (Ausgewählte meldepflichtige Krankheiten)
    NOTIFIABLE_DISEASES = {
        "Measles": {"code": "A33-A35", "name_de": "Masern"},
        "Mumps": {"code": "A36", "name_de": "Mumps"},
        "Rubella": {"code": "A37", "name_de": "Röteln"},
        "Pertussis": {"code": "A37.0", "name_de": "Keuchhusten"},
        "Varicella": {"code": "B01", "name_de": "Windpoxen"},
        "Meningococcus": {"code": "A39", "name_de": "Meningokokken"},
        "Hepatitis_A": {"code": "B15", "name_de": "Hepatitis A"},
        "Hepatitis_B": {"code": "B16", "name_de": "Hepatitis B"},
        "Salmonellosis": {"code": "A02", "name_de": "Salmonellose"},
        "Campylobacter": {"code": "A04.5", "name_de": "Campylobacter"},
        "Yersiniosis": {"code": "A04.6", "name_de": "Yersiniose"},
        "Shigellosis": {"code": "A03", "name_de": "Shigellose"},
        "EHEC": {"code": "A04.3", "name_de": "EHEC"},
        "Listeria": {"code": "A32", "name_de": "Listeriose"},
        "Tuberculosis": {"code": "A15-A19", "name_de": "Tuberkulose"},
        "Lyme": {"code": "A69.2", "name_de": "Lyme-Borreliose"},
        "TBE": {"code": "A84.1", "name_de": "FSME (TBE)"},
        "Malaria": {"code": "B50-B54", "name_de": "Malaria"},
        "Dengue": {"code": "A90", "name_de": "Dengue"},
        "Zika": {"code": "A92.5", "name_de": "Zika"},
        "West_Nile": {"code": "A92.3", "name_de": "West-Nil"},
        "HIV": {"code": "B20-B24", "name_de": "HIV"},
        "Syphilis": {"code": "A50-A53", "name_de": "Syphilis"},
        "Gonorrhea": {"code": "A54", "name_de": "Gonorrhö"},
        "Chlamydia": {"code": "A55-A56", "name_de": "Chlamydien"},
    }

    # Age groups used in RKI data
    AGE_GROUPS = [
        "A00-A04", "A05-A14", "A15-A34", "A35-A59", "A60-A79", "A80+", "unknown"
    ]

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize RKI accessor.

        Args:
            cache_dir: Directory to cache downloaded data (optional)
        """
        self.cache_dir = cache_dir
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": "RKI-Data-Accessor/1.0 (Research Purpose)",
                "Accept": "text/csv, application/json",
            }
        )
        self._cache = {}

    def list_states(self) -> pd.DataFrame:
        """
        List German federal states (Bundesländer).

        Returns
        -------
            DataFrame with state codes and names
        """
        return pd.DataFrame(
            [(code, name) for code, name in self.STATES.items()],
            columns=["state_code", "state_name"],
        )

    def list_notifiable_diseases(self) -> pd.DataFrame:
        """
        List notifiable infectious diseases.

        Returns
        -------
            DataFrame with disease codes and names
        """
        data = []
        for code, info in self.NOTIFIABLE_DISEASES.items():
            data.append(
                {
                    "disease_code": code,
                    "disease_name_en": info["code"],
                    "disease_name_de": info["name_de"],
                }
            )
        return pd.DataFrame(data)

    def get_covid_cases(
        self,
        states: Optional[List[str]] = None,
        age_groups: Optional[List[str]] = None,
        date_range: Optional[Tuple[str, str]] = None,
    ) -> pd.DataFrame:
        """
        Get COVID-19 case data from RKI.

        Note: RKI's main dataset is stored via Git LFS and very large.
        This method fetches the Nowcasting/R estimation dataset instead,
        which provides aggregated case estimates.

        Args:
            states: List of state codes (e.g., ["DE-BY", "DE-BE"]). Use ["DE"] for national.
            age_groups: List of age groups (e.g., ["A00-A04", "A60-A79"])
            date_range: Tuple of (start_date, end_date) in 'YYYY-MM-DD' format

        Returns
        -------
            DataFrame with COVID-19 case data
        """
        logger.info(
            f"Fetching COVID-19 cases for states={states}, date_range={date_range}"
        )

        # Main case data file is Git LFS (very large)
        # Use Nowcasting data which includes case estimates
        url = f"{self.GITHUB_BASE}/{self.REPOS['covid_nowcast']}/main/Nowcast_R_aktuell.csv"

        try:
            response = self._session.get(url, timeout=60)
            response.raise_for_status()

            # Check if it's Git LFS pointer
            if response.text.startswith("version https://git-lfs.github.com"):
                logger.warning(
                    "COVID-19 case data is stored via Git LFS. "
                    "Use get_covid_nowcast() for aggregated data, or download "
                    "full data from https://github.com/robert-koch-institut/"
                )
                return pd.DataFrame()

            df = pd.read_csv(
                pd.io.common.StringIO(response.text),
                parse_dates=["Datum"],
            )

            # Filter by date range
            if date_range:
                start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
                df = df[(df["Datum"] >= start) & (df["Datum"] <= end)]

            # Filter by states (if state column exists)
            if states and "Bundesland" in df.columns:
                valid_states = [self.STATES.get(s, s) for s in states]
                df = df[df["Bundesland"].isin(valid_states)]

            # Rename columns for clarity
            column_map = {
                "Datum": "date",
                "PS_COVID_Faelle": "cases_nowcast",
                "UG_PI_COVID_Faelle": "cases_lower_ci",
                "OG_PI_COVID_Faelle": "cases_upper_ci",
                "PS_COVID_Faelle_ma4": "cases_nowcast_ma4",
                "UG_PI_COVID_Faelle_ma4": "cases_ma4_lower_ci",
                "OG_PI_COVID_Faelle_ma4": "cases_ma4_upper_ci",
                "PS_7_Tage_R_Wert": "r_value",
                "UG_PI_7_Tage_R_Wert": "r_lower_ci",
                "OG_PI_7_Tage_R_Wert": "r_upper_ci",
            }
            df = df.rename(columns=column_map)

            logger.info(f"Retrieved {len(df)} COVID-19 case records")
            return df

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch COVID-19 cases: {e}")
            return pd.DataFrame()

    def get_covid_hospitalizations(
        self,
        states: Optional[List[str]] = None,
        date_range: Optional[Tuple[str, str]] = None,
    ) -> pd.DataFrame:
        """
        Get COVID-19 hospitalization data from RKI.

        Args:
            states: List of state codes
            date_range: Tuple of (start_date, end_date)

        Returns
        -------
            DataFrame with hospitalization data
        """
        logger.info(
            f"Fetching COVID-19 hospitalizations for states={states}"
        )

        url = f"{self.GITHUB_BASE}/{self.REPOS['covid_hosp']}/main/Aktuell_Deutschland_COVID-19-Hospitalisierungen.csv"

        try:
            response = self._session.get(url, timeout=60)
            response.raise_for_status()

            df = pd.read_csv(
                pd.io.common.StringIO(response.text),
                parse_dates=["Datum"],
            )

            # Filter by date
            if date_range:
                start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
                df = df[(df["Datum"] >= start) & (df["Datum"] <= end)]

            # Filter by states
            if states:
                valid_states = [self.STATES.get(s, s) for s in states]
                df = df[df["Bundesland"].isin(valid_states)]

            logger.info(f"Retrieved {len(df)} hospitalization records")
            return df

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch hospitalization data: {e}")
            return pd.DataFrame()

    def get_covid_nowcast(
        self,
        date_range: Optional[Tuple[str, str]] = None,
    ) -> pd.DataFrame:
        """
        Get COVID-19 nowcasting estimates (7-day incidence R).

        Args:
            date_range: Tuple of (start_date, end_date)

        Returns
        -------
            DataFrame with nowcasting data including R estimates
        """
        logger.info("Fetching COVID-19 nowcasting data")

        url = f"{self.GITHUB_BASE}/{self.REPOS['covid_nowcast']}/main/Nowcast_R_aktuell.csv"

        try:
            response = self._session.get(url, timeout=60)
            response.raise_for_status()

            df = pd.read_csv(
                pd.io.common.StringIO(response.text),
                parse_dates=["Datum"],
            )

            # Filter by date
            if date_range:
                start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
                df = df[(df["Datum"] >= start) & (df["Datum"] <= end)]

            logger.info(f"Retrieved {len(df)} nowcast records")
            return df

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch nowcast data: {e}")
            return pd.DataFrame()

    def get_covid_vaccinations(
        self,
        states: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Get COVID-19 vaccination data from RKI.

        Args:
            states: List of state codes

        Returns
        -------
            DataFrame with vaccination data
        """
        logger.info(f"Fetching COVID-19 vaccination data for states={states}")

        url = f"{self.GITHUB_BASE}/{self.REPOS['covid_impf']}/main/Aktuell_Deutschland_Bundeslaender_COVID-19-Impfungen.csv"

        try:
            response = self._session.get(url, timeout=60)
            response.raise_for_status()

            df = pd.read_csv(pd.io.common.StringIO(response.text))

            # Filter by states
            if states:
                valid_states = [self.STATES.get(s, s) for s in states]
                df = df[df["Bundesland"].isin(valid_states)]

            logger.info(f"Retrieved {len(df)} vaccination records")
            return df

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch vaccination data: {e}")
            return pd.DataFrame()

    def get_influenza_data(
        self,
        seasons: Optional[List[str]] = None,
        states: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Get influenza surveillance data from RKI weekly reports.

        Args:
            seasons: List of influenza seasons (e.g., ["2022/23", "2023/24"])
            states: List of state codes (not all data available at state level)

        Returns
        -------
            DataFrame with influenza surveillance data
        """
        logger.info(f"Fetching influenza data for seasons={seasons}")

        # Current and recent seasons
        if seasons is None:
            current_year = datetime.now().year
            seasons = [f"{current_year-1}/{str(current_year)[2:]}", f"{current_year}/{str(current_year+1)[2:]}"]

        all_data = []

        for season in seasons:
            # Try to fetch data for each season
            # Note: RKI influenza data structure varies by season
            url = f"{self.GITHUB_BASE}/{self.REPOS['influenza']}/main/{season.replace('/', '-')}/data.csv"

            try:
                response = self._session.get(url, timeout=30)
                response.raise_for_status()
                df = pd.read_csv(pd.io.common.StringIO(response.text))
                df["season"] = season
                all_data.append(df)
            except requests.exceptions.RequestException:
                logger.warning(f"Could not fetch influenza data for season {season}")
                continue

        if all_data:
            combined = pd.concat(all_data, ignore_index=True)
            logger.info(f"Retrieved {len(combined)} influenza records")
            return combined
        else:
            logger.warning("No influenza data retrieved")
            return pd.DataFrame()

    def get_notifiable_disease(
        self,
        disease: str,
        years: Optional[List[int]] = None,
        states: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Get data for a specific notifiable disease.

        Args:
            disease: Disease code (e.g., "Measles", "Pertussis")
            years: List of years (e.g., [2022, 2023])
            states: List of state codes

        Returns
        -------
            DataFrame with disease case data
        """
        if disease not in self.NOTIFIABLE_DISEASES:
            valid = list(self.NOTIFIABLE_DISEASES.keys())
            logger.error(f"Invalid disease code '{disease}'. Valid codes: {valid}")
            return pd.DataFrame()

        logger.info(f"Fetching data for {disease}, years={years}, states={states}")

        # SurvStat@RKI data requires API access or manual download
        # This is a placeholder for the expected data structure

        data = []
        years_list = years if years else [datetime.now().year]
        states_list = states if states else ["DE"]

        for year in years_list:
            for state in states_list:
                record = {
                    "disease_code": disease,
                    "disease_name_en": disease,
                    "disease_name_de": self.NOTIFIABLE_DISEASES[disease]["name_de"],
                    "icd10_code": self.NOTIFIABLE_DISEASES[disease]["code"],
                    "year": year,
                    "state_code": state,
                    "state_name": self.STATES.get(state, state),
                    "cases": None,
                    "cases_male": None,
                    "cases_female": None,
                    "cases_unknown_sex": None,
                    "deaths": None,
                    "incidence_per_100k": None,
                    "data_source": "SurvStat@RKI 2.0",
                    "note": "Data requires SurvStat@RKI API access or manual export",
                }
                data.append(record)

        logger.warning(
            "Notifiable disease data requires SurvStat@RKI 2.0 access. "
            "Visit https://survstat.rki.de/ for manual data export."
        )
        return pd.DataFrame(data)

    def get_vaccination_coverage(
        self,
        vaccines: List[str],
        birth_cohorts: Optional[List[int]] = None,
    ) -> pd.DataFrame:
        """
        Get vaccination coverage data for Germany.

        Args:
            vaccines: List of vaccine names (e.g., ["MMR", "DTP"])
            birth_cohorts: List of birth years (e.g., [2015, 2016, 2017])

        Returns
        -------
            DataFrame with vaccination coverage percentages
        """
        logger.info(f"Fetching vaccination coverage for vaccines={vaccines}")

        # RKI vaccination coverage data is available via:
        # - https://www.rki.de/DE/Content/Infekt/Impfen/Impfstatus/Impfstatus_node.html
        # - SurvStat@RKI

        data = []
        for vaccine in vaccines:
            record = {
                "vaccine": vaccine,
                "birth_cohort": birth_cohorts[0] if birth_cohorts else None,
                "coverage_1dose_percent": None,
                "coverage_complete_percent": None,
                "data_year": datetime.now().year - 1,
                "data_source": "RKI Impfquoten",
                "note": "Data requires RKI vaccination coverage reports",
            }
            data.append(record)

        logger.warning(
            "Vaccination coverage data requires RKI reports. "
            "See https://www.rki.de/impfquoten"
        )
        return pd.DataFrame(data)

    def get_amr_surveillance(
        self,
        years: Optional[List[int]] = None,
    ) -> pd.DataFrame:
        """
        Get antimicrobial resistance (AMR) surveillance data.

        Args:
            years: List of years

        Returns
        -------
            DataFrame with AMR surveillance data
        """
        logger.info(f"Fetching AMR surveillance for years={years}")

        # ESPAUR-style data for Germany
        # https://www.rki.de/EN/Content/infections/antibiotic_resistance/antibiotic_resistance_node.html

        data = []
        years_list = years if years else [datetime.now().year - 1]

        for year in years_list:
            record = {
                "year": year,
                "pathogen": None,
                "antibiotic": None,
                "resistance_rate_percent": None,
                "n_isolates": None,
                "n_resistant": None,
                "setting": "Hospital",  # or "Community"
                "data_source": "GERMAP (RKI)",
                "note": "Data requires GERMAP report access",
            }
            data.append(record)

        logger.warning(
            "AMR data requires GERMAP reports. "
            "See https://www.rki.de/GERMAP"
        )
        return pd.DataFrame(data)

    def get_summary_stats(
        self,
        year: int,
        state: str = "DE",
    ) -> pd.DataFrame:
        """
        Get summary statistics for a given year.

        Args:
            year: Year to summarize
            state: State code (default: Germany total)

        Returns
        -------
            DataFrame with summary statistics
        """
        summary_data = []

        # COVID-19 summary
        covid = self.get_covid_cases(
            states=[state],
            date_range=(f"{year}-01-01", f"{year}-12-31")
        )

        if not covid.empty:
            summary_data.append({
                "metric": "COVID-19 cases",
                "value": covid["cases"].sum(),
                "year": year,
                "state": state,
            })

        return pd.DataFrame(summary_data)


def main():
    """
    Example usage of RKIGermanyAccessor.
    """
    print("=" * 70)
    print("Robert Koch Institute (RKI) Germany Data Accessor")
    print("=" * 70)

    rki = RKIGermanyAccessor()

    # List states
    print("\n🇩🇪 German Federal States (Bundesländer):")
    states = rki.list_states()
    print(f"Total states: {len(states)}")
    print("\nFirst 5 states:")
    print(states.head().to_string(index=False))

    # List notifiable diseases
    print("\n🦠 Notifiable Infectious Diseases (sample):")
    diseases = rki.list_notifiable_diseases()
    print(diseases.head(10).to_string(index=False))

    # Fetch COVID-19 data example
    print("\n📊 Fetching COVID-19 data (last 30 days)...")
    from datetime import timedelta
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    covid = rki.get_covid_cases(
        states=["DE-BE", "DE-BY"],  # Berlin and Bavaria
        date_range=(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
    )

    if not covid.empty:
        print(f"Retrieved {len(covid)} COVID-19 records")
        print("\nSample data:")
        print(covid[["state_name", "report_date", "cases", "deaths"]].head())
    else:
        print("No COVID-19 data retrieved (check internet connection)")

    # Show API examples
    print("\n📋 Example Usage:")
    print("  rki = RKIGermanyAccessor()")
    print("  covid = rki.get_covid_cases(")
    print("      states=['DE-BE', 'DE-BY'],")
    print("      date_range=('2023-01-01', '2023-12-31')")
    print("  )")
    print("  nowcast = rki.get_covid_nowcast()")
    print("  flu = rki.get_influenza_data(seasons=['2023/24'])")
    print("  measles = rki.get_notifiable_disease('Measles', years=[2023])")
    print("  vacc = rki.get_vaccination_coverage(['MMR', 'DTP'])")

    print("\n✅ RKI Germany accessor ready to use!")


if __name__ == "__main__":
    main()
