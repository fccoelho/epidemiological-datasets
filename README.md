# 🌍 Epidemiological Datasets

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9%2B-blue.svg?logo=python&logoColor=white" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT">
  <img src="https://img.shields.io/badge/Code%20Style-Black-black.svg" alt="Code style: Black">
</p>

<p align="center">
  <a href="https://github.com/fccoelho/epidemiological-datasets/issues">
    <img src="https://img.shields.io/github/issues/fccoelho/epidemiological-datasets.svg?style=flat-square&logo=github" alt="Open Issues">
  </a>
  <a href="https://github.com/fccoelho/epidemiological-datasets/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22">
    <img src="https://img.shields.io/github/issues/fccoelho/epidemiological-datasets/help%20wanted?style=flat-square&logo=github&color=orange" alt="Help Wanted">
  </a>
  <a href="https://github.com/fccoelho/epidemiological-datasets/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22">
    <img src="https://img.shields.io/github/issues/fccoelho/epidemiological-datasets/good%20first%20issue?style=flat-square&logo=github&color=brightgreen" alt="Good First Issue">
  </a>
  <a href="https://github.com/fccoelho/epidemiological-datasets/issues?q=is%3Aissue+is%3Aopen+label%3A%22data+source%22">
    <img src="https://img.shields.io/github/issues/fccoelho/epidemiological-datasets/data%20source?style=flat-square&logo=github&color=blue" alt="Data Source Requests">
  </a>
</p>

<p align="center">
  <a href="https://github.com/fccoelho/epidemiological-datasets/actions/workflows/ci.yml">
    <img src="https://github.com/fccoelho/epidemiological-datasets/workflows/CI/badge.svg" alt="CI Status">
  </a>
  <a href="https://codecov.io/gh/fccoelho/epidemiological-datasets">
    <img src="https://codecov.io/gh/fccoelho/epidemiological-datasets/branch/main/graph/badge.svg" alt="Code Coverage">
  </a>
</p>

<p align="center">
  <img src="https://img.shields.io/github/stars/fccoelho/epidemiological-datasets?style=social" alt="Stars">
  <img src="https://img.shields.io/github/forks/fccoelho/epidemiological-datasets?style=social" alt="Forks">
  <img src="https://img.shields.io/github/contributors/fccoelho/epidemiological-datasets?style=flat-square" alt="Contributors">
</p>

> A curated collection of openly accessible epidemiological datasets from around the world, with Python tools for easy access and analysis.

## 📋 Table of Contents

- [Overview](#overview)
- [Repository Structure](#repository-structure)
- [Available Datasets](#available-datasets)
  - [Global](#global-)
  - [North America](#north-america-)
  - [South America](#south-america-)
  - [Europe](#europe-)
  - [Africa](#africa-)
  - [Asia](#asia-)
  - [Oceania](#oceania-)
- [Python Scripts](#python-scripts)
  - [Using PySUS](#using-pysus-for-datasus)
  - [Using ghoclient](#using-ghoclient-for-who-data)
- [Installation](#installation)
- [Usage Examples](#usage-examples)
- [Contributing](#contributing)
- [License](#license)

## 🎯 Overview

This repository aims to:

- **Centralize** links to openly accessible epidemiological data sources
- **Standardize** access to heterogeneous datasets through Python scripts
- **Document** data formats, update frequencies, and access requirements
- **Enable** reproducible research in epidemiology and public health

Whether you're studying infectious diseases, chronic conditions, or health systems, this collection provides starting points for data-driven research.

## 📁 Repository Structure

```
epidemiological-datasets/
├── 📁 .github/                 # GitHub templates and workflows
│   ├── 📁 DISCUSSION_TEMPLATE/ # Discussion templates
│   ├── 📁 ISSUE_TEMPLATE/      # Issue templates (bug, feature, data source)
│   ├── 📁 workflows/           # CI/CD workflows
│   └── 📄 pull_request_template.md
├── 📁 data/                    # Cached data (gitignored)
├── 📁 docs/                    # Documentation
│   └── 📄 index.md
├── 📁 examples/                # Example notebooks
│   ├── 📁 notebooks/
│   │   ├── 01_pysus_brazilian_health_data.ipynb
│   │   ├── 02_who_global_health_data.ipynb
│   │   ├── 03_world_bank_health_indicators.ipynb
│   │   ├── 04_ecdc_european_surveillance.ipynb
│   │   ├── 05_multi_source_comparison.ipynb
│   │   ├── 06_PAHO_Pan_American_Data.ipynb
│   │   └── 07_Eurostat_EU_Health_Data.ipynb
│   ├── 📄 README.md
│   └── 📄 requirements.txt
├── 📁 scripts/                 # Python access scripts
│   ├── 📁 accessors/           # Dataset-specific accessors
│   │   ├── datasus_pysus.py    # PySUS wrapper
│   │   ├── who_ghoclient.py    # ghoclient wrapper
│   │   ├── paho.py             # PAHO data accessor
│   │   ├── eurostat.py         # Eurostat accessor
│   │   └── __init__.py
│   ├── 📄 __init__.py
│   └── 📄 utils.py             # Common utilities
├── 📁 src/
│   └── 📁 epi_data/            # Main Python package
│       ├── 📁 sources/         # Data source accessors
│       ├── 📁 utils/           # Utility functions
│       └── 📄 __init__.py
├── 📁 tests/                   # Test suite
│   ├── 📁 sources/
│   ├── 📁 utils/
│   ├── 📄 conftest.py
│   └── 📄 __init__.py
├── 📄 CHANGELOG.md             # Version history
├── 📄 CODE_OF_CONDUCT.md       # Community guidelines
├── 📄 CONTRIBUTING.md          # Contribution guide
├── 📄 LICENSE                  # MIT License
├── 📄 README.md                # This file
├── 📄 pyproject.toml           # Project configuration (UV)
├── 📄 requirements.txt         # Dependencies
└── 📄 requirements-dev.txt     # Dev dependencies
```

## 🌐 Available Datasets

### Global 🌍

| Dataset | Description | Update Frequency | Access Level | Script |
|---------|-------------|------------------|--------------|--------|
| [WHO Global Health Observatory](https://www.who.int/data/gho) | Health indicators by country | Annual | Open | `ghoclient` |
| [Our World in Data - Health](https://ourworldindata.org/health) | Comprehensive health datasets | Weekly | Open | `scripts/accessors/owid.py` |
| [World Bank Health](https://data.worldbank.org/health) | Health, nutrition, and population statistics | Annual | Open | `scripts/accessors/worldbank.py` |
| [Global Health Data Exchange (GHDx)](http://ghdx.healthdata.org/) | Catalog of health datasets | Varies | Varies | Catalog only |
| [HDX (Humanitarian Data Exchange)](https://data.humdata.org/) | Health in crisis contexts | Real-time | Open | `scripts/accessors/hdx.py` |

### North America 🇺🇸🇨🇦🇲🇽

| Dataset | Description | Update Frequency | Access Level | Script |
|---------|-------------|------------------|--------------|--------|
| [CDC Wonder](https://wonder.cdc.gov/) | US health statistics | Weekly | Open | `scripts/accessors/cdc.py` |
| [CDC Open Data](https://data.cdc.gov/) | CDC datasets portal | Varies | Open | `scripts/accessors/cdc_opendata.py` |
| [HealthData.gov](https://healthdata.gov/) | US health system data | Weekly | Open | Planned |
| [Statistics Canada - Health](https://www.statcan.gc.ca/en/health) | Canadian health data | Quarterly | Open | Planned |

### South America 🌎

| Dataset | Description | Update Frequency | Access Level | Script |
|---------|-------------|------------------|--------------|--------|
| [SINAN - Brazil](http://portalsinan.saude.gov.br/) | Brazilian notifiable diseases | Weekly | Open* | `PySUS` |
| [DATASUS](https://datasus.saude.gov.br/) | Brazilian health system data | Weekly | Open* | `PySUS` |
| [SIAD - Brazil](https://siad.mg.gov.br/) | Brazilian health information | Weekly | Open* | `PySUS` |
| [PAHO/WHO Regional Data](https://www.paho.org/en/data) | Pan-American health data | Monthly | Open | `scripts/accessors/paho.py` |
| [Chile DEIS](https://deis.minsal.cl/) | Chilean health statistics | Monthly | Open | Planned |
| [Colombia INS](https://www.ins.gov.co/) | Colombian public health data | Weekly | Open | Planned |

> *Note: PySUS handles authentication and access to DATASUS/SINAN data.

### Europe 🇪🇺

| Dataset | Description | Update Frequency | Access Level | Script |
|---------|-------------|------------------|--------------|--------|
| [ECDC Surveillance Atlas](https://atlas.ecdc.europa.eu/public/index.aspx) | Infectious disease surveillance | Weekly | Open | `scripts/accessors/ecdc.py` |
| [Eurostat Health](https://ec.europa.eu/eurostat/web/health) | EU health statistics | Annual | Open | `scripts/accessors/eurostat.py` |
| [UK Health Security Agency](https://www.gov.uk/government/collections/health-protection-data) | UK health data | Weekly | Open | Planned |
| [Robert Koch Institute](https://www.rki.de/EN/Content/infections/epidemiology/data.html) | German surveillance data | Weekly | Open | Planned |

### Africa 🌍

| Dataset | Description | Update Frequency | Access Level | Script |
|---------|-------------|------------------|--------------|--------|
| [WHO Afro Health Observatory](https://www.afro.who.int/health-topics/health-observatory) | African region health data | Annual | Open | `ghoclient` |
| [DHIS2](https://dhis2.org/) | Health information systems | Real-time | Varies | `scripts/accessors/dhis2.py` |
| [Africa CDC](https://africacdc.org/) | African public health data | Weekly | Open | Planned |

### Asia 🌏

| Dataset | Description | Update Frequency | Access Level | Script |
|---------|-------------|------------------|--------------|--------|
| [China CDC Weekly](http://weekly.chinacdc.cn/) | Chinese surveillance data | Weekly | Open | Planned |
| [IDSP India](https://idsp.nic.in/) | Indian disease surveillance | Weekly | Open* | Planned |
| [NIID Japan](https://www.niid.go.jp/niid/en/) | Japanese infectious disease data | Weekly | Open | Planned |
| [Korea CDC](https://www.kdca.go.kr/) | Korean disease control data | Weekly | Open | Planned |

### Oceania 🇦🇺🇳🇿

| Dataset | Description | Update Frequency | Access Level | Script |
|---------|-------------|------------------|--------------|--------|
| [Australian Institute of Health and Welfare](https://www.aihw.gov.au/) | Australian health data | Annual | Open | Planned |
| [NZ Ministry of Health](https://www.health.govt.nz/nz-health-statistics) | New Zealand health statistics | Annual | Open | Planned |

## 🐍 Python Scripts

### Using PySUS for DATASUS

PySUS is a Python library developed by the AlertaDengue team for accessing Brazilian public health data (DATASUS).

**Installation:**
```bash
pip install pysus
```

**Example usage:**
```python
from pysus.online_data import SINAN, SIM, SIH

# Download dengue cases from SINAN
dengue = SINAN.download(
    disease="Dengue",
    years=[2022, 2023],
    states=["RJ", "SP", "MG"]
)

# Download mortality data from SIM
mortality = SIM.download(
    years=[2021, 2022],
    states=["RJ"]
)

# Hospitalization data from SIH
hospitalizations = SIH.download(
    years=[2023],
    months=[1, 2, 3],
    states=["SP"],
    group="RD"  # AIH Reduced
)
```

**Repository:** [github.com/AlertaDengue/PySUS](https://github.com/AlertaDengue/PySUS)  
**Documentation:** [pysus.readthedocs.io](https://pysus.readthedocs.io)

### Using ghoclient for WHO Data

ghoclient is a Python client for the WHO Global Health Observatory API.

**Installation:**
```bash
pip install ghoclient
```

**Example usage:**
```python
from ghoclient import GHOClient

# Initialize client
client = GHOClient()

# Search for indicators
malaria_indicators = client.search_indicators("malaria")
print(malaria_indicators)

# Get specific indicator data
data = client.get_indicator(
    indicator="MALARIA_EST_INCIDENCE",
    years=[2020, 2021, 2022],
    countries=["BRA", "IND", "NGA"]
)

print(data.head())
```

**Repository:** [github.com/fccoelho/ghoclient](https://github.com/fccoelho/ghoclient)  
**PyPI:** [pypi.org/project/ghoclient](https://pypi.org/project/ghoclient/)

### Using PAHO Accessor for Pan-American Data

The PAHO accessor provides access to health data from the Pan American Health Organization (PAHO), covering all countries in the Americas.

**No installation required** - uses native Python libraries.

**Example usage:**
```python
from accessors import PAHOAccessor

# Initialize accessor
paho = PAHOAccessor()

# List PAHO member countries
countries = paho.list_countries()
print(f"Total countries: {len(countries)}")

# Get immunization coverage for Southern Cone
coverage = paho.get_immunization_coverage(
    vaccines=['DTP3', 'MCV1'],
    subregion='Southern Cone',
    years=[2020, 2021, 2022]
)

# Get malaria data for endemic countries
malaria = paho.get_malaria_incidence(
    countries=['BRA', 'COL', 'PER'],
    years=[2020, 2021, 2022]
)

# Compare health indicators across countries
comparison = paho.compare_countries(
    indicator='LIFE_EXPECTANCY',
    countries=['BRA', 'MEX', 'ARG', 'COL'],
    years=[2019, 2020, 2021]
)
```

**Data Sources:**
- PAHO Data Portal: https://www.paho.org/en/data
- WHO GHO API: https://www.who.int/data/gho
- WHO Immunization API: https://immunizationdata.who.int

### Using Eurostat Accessor for EU Health Data

The Eurostat accessor provides access to European Union health statistics covering 27 EU member states, EFTA countries, and candidate countries.

**Optional installation** for better performance:
```bash
pip install eurostat
```

**Example usage:**
```python
from accessors import EurostatAccessor

# Initialize accessor (uses REST API if eurostat library not installed)
eurostat = EurostatAccessor()

# List EU member countries
countries = eurostat.list_eu_countries()
print(f"Total EU countries: {len(countries)}")

# Get healthcare expenditure data
expenditure = eurostat.get_healthcare_expenditure(
    countries=['DEU', 'FRA', 'ITA'],
    years=list(range(2015, 2024))
)

# Get mortality data by cause
mortality = eurostat.get_mortality_data(
    cause_code='COVID-19',
    countries=['DEU', 'FRA', 'ITA'],
    years=[2020, 2021, 2022]
)

# Get life expectancy
life_exp = eurostat.get_life_expectancy(
    countries=['DEU', 'FRA', 'ITA', 'ESP'],
    years=[2019, 2020, 2021]
)

# Get physician data
physicians = eurostat.get_physicians(
    countries=['DEU', 'FRA'],
    years=[2020, 2021, 2022]
)

# Compare countries
comparison = eurostat.compare_countries(
    indicator_code='demo_mlexpec',
    countries=['DEU', 'FRA', 'ITA', 'ESP'],
    years=[2019, 2020, 2021]
)
```

**Features:**
- 27 EU member states + EFTA + candidate countries
- Healthcare expenditure and financing
- Mortality and causes of death (ICD-10 based)
- Health workforce (physicians, nurses, hospital beds)
- Health determinants (lifestyle, environment)
- Life expectancy and infant mortality
- Self-perceived health status

**Data Sources:**
- Eurostat Health: https://ec.europa.eu/eurostat/web/health
- Eurostat Data Browser: https://ec.europa.eu/eurostat/databrowser
- Eurostat API: https://ec.europa.eu/eurostat/web/sdmx-web-services
- Python Library: https://pypi.org/project/eurostat/

## 📦 Installation

### Standard Installation

```bash
# Clone the repository
git clone https://github.com/fccoelho/epidemiological-datasets.git
cd epidemiological-datasets

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install additional packages for specific sources
pip install pysus ghoclient
```

### Development Installation

```bash
# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

## 💡 Usage Examples

### Example 1: Brazilian Health Data with PySUS

```python
from pysus.online_data import SINAN
import pandas as pd

# Download dengue notification data
df = SINAN.download(
    disease="Dengue",
    years=[2023],
    states=["RJ", "SP"]
)

# Analyze cases by municipality
cases_by_city = df.groupby('ID_MUNICIP').size()
print(cases_by_city.sort_values(ascending=False).head(10))
```

### Example 2: WHO Data with ghoclient

```python
from ghoclient import GHOClient

client = GHOClient()

# Get COVID-19 vaccination data
vaccination = client.get_indicator(
    indicator="COVID19_VACCINATION",
    years=[2021, 2022],
    countries=["BRA", "USA", "GBR"]
)

# Calculate vaccination coverage
for country in vaccination['country'].unique():
    country_data = vaccination[vaccination['country'] == country]
    latest = country_data.loc[country_data['year'].idxmax()]
    print(f"{country}: {latest['value']}% vaccinated in {latest['year']}")
```

### Example 3: Multi-source Analysis

```python
from pysus.online_data import SINAN
from ghoclient import GHOClient
import pandas as pd

# Get Brazilian dengue data
sinan_data = SINAN.download(disease="Dengue", years=[2022])
br_cases = len(sinan_data)

# Get WHO data for comparison
who = GHOClient()
who_data = who.get_indicator(
    indicator="MALARIA_EST_INCIDENCE",
    years=[2022],
    countries=["BRA"]
)

print(f"Brazil Dengue cases (SINAN): {br_cases}")
print(f"Brazil Malaria incidence (WHO): {who_data['value'].values[0]}")
```

## 📊 Available Scripts

| Script | Library Used | Status | Description |
|--------|--------------|--------|-------------|
| `datasus_pysus.py` | **PySUS** | ✅ Available | Wrapper for PySUS with additional utilities |
| `who_ghoclient.py` | **ghoclient** | ✅ Available | Wrapper for ghoclient with pandas integration |
| `paho.py` | Native | ✅ Available | PAHO (Pan American Health Organization) data accessor |
| `eurostat.py` | Native/eurostat | ✅ Available | Eurostat (EU) health statistics accessor |
| `cdc.py` | Native | 🔄 Planned | CDC Wonder and Open Data |
| `ecdc.py` | Native | 🔄 Planned | European CDC data |
| `owid.py` | Native | 🔄 Planned | Our World in Data |
| `worldbank.py` | Native | 🔄 Planned | World Bank health indicators |

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

### Quick Links for Contributors

<p align="center">
  <a href="https://github.com/fccoelho/epidemiological-datasets/contribute">
    <img src="https://img.shields.io/badge/🚀%20Start%20Contributing-orange?style=for-the-badge" alt="Start Contributing">
  </a>
</p>

- 📋 [Contributing Guide](CONTRIBUTING.md) - How to get started
- 🐛 [Report a Bug](https://github.com/fccoelho/epidemiological-datasets/issues/new?template=bug_report.yml)
- 💡 [Request a Feature](https://github.com/fccoelho/epidemiological-datasets/issues/new?template=feature_request.yml)
- 🌍 [Request a Data Source](https://github.com/fccoelho/epidemiological-datasets/issues/new?template=new_data_source.yml)
- 💬 [GitHub Discussions](https://github.com/fccoelho/epidemiological-datasets/discussions) - Ask questions, share ideas

### Priority Contributions

1. **New dataset links** - Especially from underrepresented regions
2. **Python accessors** - For datasets without existing libraries
3. **Examples** - Jupyter notebooks demonstrating data analysis
4. **Documentation** - Translations and improvements

### Badges for Contributors

<p align="center">
  <a href="https://github.com/fccoelho/epidemiological-datasets/issues?q=is%3Aopen+is%3Aissue+label%3A%22good+first+issue%22">
    <img src="https://img.shields.io/github/issues/fccoelho/epidemiological-datasets/good%20first%20issue?style=for-the-badge&logo=github&color=brightgreen" alt="Good First Issues">
  </a>
  <a href="https://github.com/fccoelho/epidemiological-datasets/issues?q=is%3Aopen+is%3Aissue+label%3A%22help+wanted%22">
    <img src="https://img.shields.io/github/issues/fccoelho/epidemiological-datasets/help%20wanted?style=for-the-badge&logo=github&color=orange" alt="Help Wanted">
  </a>
</p>

## 📚 Related Projects

This repository complements the following open-source tools:

| Project | Description | Repository |
|---------|-------------|------------|
| **PySUS** | Brazilian health data (DATASUS) | [AlertaDengue/PySUS](https://github.com/AlertaDengue/PySUS) |
| **ghoclient** | WHO Global Health Observatory | [fccoelho/ghoclient](https://github.com/fccoelho/ghoclient) |
| **epigrass** | Epidemic simulation | [EpiGrass/epigrass](https://github.com/EpiGrass/epigrass) |
| **epimodels** | Mathematical epidemiology | [fccoelho/epimodels](https://github.com/fccoelho/epimodels) |

## 📊 Statistics

- **Datasets documented:** 25+
- **Countries covered:** 50+
- **Python libraries integrated:** 2 (PySUS, ghoclient)
- **Last updated:** 2026-03-14

## 📚 Citation

If you use this repository in your research, please cite:

```bibtex
@misc{fccoelho_epidemiological_datasets,
  author = {Coelho, Flávio Codeço},
  title = {Epidemiological Datasets: A Global Collection},
  year = {2026},
  publisher = {GitHub},
  journal = {GitHub Repository},
  howpublished = {\url{https://github.com/fccoelho/epidemiological-datasets}}
}
```

For PySUS:
```bibtex
@software{pysus,
  author = {AlertaDengue Team},
  title = {PySUS: Tools for Brazilian Public Health Data},
  url = {https://github.com/AlertaDengue/PySUS}
}
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **PySUS Contributors** - For making Brazilian health data accessible
- **WHO** - For maintaining the Global Health Observatory
- **All data providers** who make epidemiological data openly accessible
- **Global public health community**

## 📞 Contact

- **Author:** Flávio Codeço Coelho (@fccoelho)
- **Email:** [Your email]
- **Twitter:** [Your Twitter]
- **Website:** https://fccoelho.github.io/

---

<p align="center">
  <b>Made with ❤️ for the epidemiological research community</b>
</p>

<p align="center">
  <a href="https://github.com/fccoelho/epidemiological-datasets/issues/new?template=bug_report.yml">🐛 Report Bug</a> •
  <a href="https://github.com/fccoelho/epidemiological-datasets/issues/new?template=feature_request.yml">💡 Request Feature</a> •
  <a href="https://github.com/fccoelho/epidemiological-datasets/discussions">💬 Discussions</a>
</p>

---

**Disclaimer:** This repository is a community effort to catalog open data sources. Please always refer to the original data providers for official statistics and verify data usage terms. The maintainers are not responsible for data quality or availability.
