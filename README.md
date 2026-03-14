# 🌍 Epidemiological Datasets

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg)](CONTRIBUTING.md)

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
├── README.md                 # This file
├── CONTRIBUTING.md           # Contribution guidelines
├── LICENSE                   # MIT License
├── datasets/                 # Dataset documentation
│   ├── global/
│   ├── north_america/
│   ├── south_america/
│   ├── europe/
│   ├── africa/
│   ├── asia/
│   └── oceania/
├── scripts/                  # Python access scripts
│   ├── __init__.py
│   ├── utils.py             # Common utilities
│   └── accessors/           # Dataset-specific accessors
│       ├── who.py
│       ├── ecdc.py
│       ├── cdc.py
│       └── ...
├── examples/                # Jupyter notebooks with examples
│   └── README.md
├── tests/                   # Unit tests
│   └── __init__.py
└── requirements.txt         # Python dependencies
```

## 🌐 Available Datasets

### Global 🌍

| Dataset | Description | Update Frequency | Access Level | Script |
|---------|-------------|------------------|--------------|--------|
| [WHO Global Health Observatory](https://www.who.int/data/gho) | Health indicators by country | Annual | Open | `scripts/accessors/who.py` |
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
| [SINAN - Brazil](http://portalsinan.saude.gov.br/) | Brazilian notifiable diseases | Weekly | Open* | `scripts/accessors/sinan.py` |
| [DATASUS](https://datasus.saude.gov.br/) | Brazilian health system data | Weekly | Open* | `scripts/accessors/datasus.py` |
| [PAHO/WHO Regional Data](https://www.paho.org/en/data) | Pan-American health data | Monthly | Open | `scripts/accessors/paho.py` |
| [Chile DEIS](https://deis.minsal.cl/) | Chilean health statistics | Monthly | Open | Planned |
| [Colombia INS](https://www.ins.gov.co/) | Colombian public health data | Weekly | Open | Planned |

> *Note: Some Brazilian datasets may require specific access procedures.

### Europe 🇪🇺

| Dataset | Description | Update Frequency | Access Level | Script |
|---------|-------------|------------------|--------------|--------|
| [ECDC Surveillance Atlas](https://atlas.ecdc.europa.eu/public/index.aspx) | Infectious disease surveillance | Weekly | Open | `scripts/accessors/ecdc.py` |
| [Eurostat Health](https://ec.europa.eu/eurostat/web/health) | EU health statistics | Annual | Open | Planned |
| [UK Health Security Agency](https://www.gov.uk/government/collections/health-protection-data) | UK health data | Weekly | Open | Planned |
| [Robert Koch Institute](https://www.rki.de/EN/Content/infections/epidemiology/data.html) | German surveillance data | Weekly | Open | Planned |

### Africa 🌍

| Dataset | Description | Update Frequency | Access Level | Script |
|---------|-------------|------------------|--------------|--------|
| [WHO Afro Health Observatory](https://www.afro.who.int/health-topics/health-observatory) | African region health data | Annual | Open | Planned |
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

### Installation

```bash
# Clone the repository
git clone https://github.com/fccoelho/epidemiological-datasets.git
cd epidemiological-datasets

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install package in development mode
pip install -e .
```

### Usage Examples

#### Example 1: Access WHO Data

```python
from scripts.accessors import WHOAccessor

# Initialize WHO accessor
who = WHOAccessor()

# Get malaria incidence data by country
malaria_data = who.get_indicator(
    indicator="Malaria incidence (per 1,000 population at risk)",
    years=range(2010, 2023),
    countries=["BRA", "IND", "NGA"]
)

print(malaria_data.head())
```

#### Example 2: Access CDC Data (US)

```python
from scripts.accessors import CDCAccessor

# Initialize CDC accessor
cdc = CDCAccessor()

# Get influenza surveillance data
flu_data = cdc.get_flu_surveillance(
    seasons=["2022-2023", "2023-2024"],
    regions="all"
)

print(flu_data.head())
```

#### Example 3: Brazilian Health Data (DATASUS)

```python
from scripts.accessors import DataSUSAccessor

# Initialize DATASUS accessor
datasus = DataSUSAccessor()

# Get dengue cases by municipality
dengue_data = datasus.get_dengue_cases(
    years=[2022, 2023],
    states=["RJ", "SP", "MG"]
)

print(dengue_data.head())
```

#### Example 4: European CDC Data

```python
from scripts.accessors import ECDCAccessor

# Initialize ECDC accessor
ecdc = ECDCAccessor()

# Get COVID-19 data
covid_data = ecdc.get_covid_data(
    countries=["DEU", "FRA", "ITA"],
    indicators=["cases", "deaths", "hospitalizations"]
)

print(covid_data.head())
```

### Available Scripts

| Script | Status | Description |
|--------|--------|-------------|
| `who.py` | ✅ Implemented | WHO GHO data access |
| `owid.py` | ✅ Implemented | Our World in Data access |
| `cdc.py` | ✅ Implemented | CDC Wonder and Open Data |
| `ecdc.py` | ✅ Implemented | European CDC data |
| `sinan.py` | ✅ Implemented | Brazilian SINAN system |
| `datasus.py` | ✅ Implemented | Brazilian DATASUS |
| `paho.py` | 🔄 Planned | Pan-American Health Organization |
| `worldbank.py` | 🔄 Planned | World Bank health indicators |
| `hdx.py` | 🔄 Planned | Humanitarian Data Exchange |

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:

- Adding new datasets
- Contributing Python access scripts
- Reporting issues
- Suggesting improvements

### Quick Contribution Guide

```bash
# Fork and clone
git clone https://github.com/YOUR_USERNAME/epidemiological-datasets.git

# Create a branch
git checkout -b feature/new-dataset

# Add your changes
git add .
git commit -m "Add dataset: [Name] from [Country/Region]"

# Push and create PR
git push origin feature/new-dataset
```

## 📊 Statistics

- **Datasets documented:** 25+
- **Countries covered:** 50+
- **Python scripts:** 10+
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

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- All data providers who make epidemiological data openly accessible
- Contributors to this repository
- The global public health community

## 📞 Contact

- **Author:** Flávio Codeço Coelho (@fccoelho)
- **Email:** [Your email]
- **Twitter:** [Your Twitter]
- **Website:** https://fccoelho.github.io/

---

**Disclaimer:** This repository is a community effort to catalog open data sources. Please always refer to the original data providers for official statistics and verify data usage terms. The maintainers are not responsible for data quality or availability.
