# 🌍 Epidatasets

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/pypi/v/epidatasets?style=flat-square&logo=pypi&color=blue" alt="PyPI">
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
  <a href="https://epidemiological-datasets.readthedocs.io">
    <img src="https://readthedocs.org/projects/epidemiological-datasets/badge/?version=latest" alt="Documentation">
  </a>
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

<p align="center">
  <strong>Sponsored by</strong><br>
  <a href="https://kwar-ai.com.br" target="_blank">
    <img src="docs/images/kwar-ai-logo.jpg" alt="Kwar-AI" width="200">
  </a><br>
  <em>AI-powered epidemiological intelligence</em>
</p>

---

> A Python library providing unified access to **21 epidemiological data sources** from around the world, with a plugin registry, CLI, and optional extras for specialized data.

## 📋 Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Repository Structure](#repository-structure)
- [Available Datasets](#available-datasets)
  - [Global](#global-)
  - [North America](#north-america-)
  - [South America](#south-america-)
  - [Europe](#europe-)
  - [Africa](#africa-)
  - [Asia](#asia-)
  - [Oceania](#oceania-)
- [CLI Usage](#cli-usage)
- [Usage Examples](#usage-examples)
- [Available Sources](#available-sources)
- [FAQ](#faq)
- [Contributing](#contributing)
- [Related Projects](#related-projects)
- [Citation](#citation)
- [License](#license)

## 🎯 Overview

**epidatasets** provides:

- **Unified interface** — A single `get_source()` API to access 21 data sources worldwide
- **Plugin registry** — Sources are discovered at runtime via `entry_points`, making it easy to extend
- **Optional extras** — Install only the dependencies you need (`pip install epidatasets[who,brazil]`)
- **CLI** — Command-line tool for listing sources, inspecting metadata, and querying countries
- **Caching & rate limiting** — Built-in utilities for responsible API usage
- **Reproducible research** — Standardized access to heterogeneous epidemiological datasets

## 📦 Installation

### From PyPI

```bash
pip install epidatasets
```

### With optional extras

```bash
# WHO Global Health Observatory data
pip install epidatasets[who]

# Brazilian DATASUS/SINAN data via PySUS
pip install epidatasets[brazil]

# Eurostat EU health statistics
pip install epidatasets[eurostat]

# Climate/environmental data (Copernicus CDS)
pip install epidatasets[climate]

# Geospatial visualization
pip install epidatasets[geo]

# Plotting & visualization
pip install epidatasets[viz]

# Genomic data (Pathoplexus)
pip install epidatasets[genomics]

# CLI support
pip install epidatasets[cli]

# World Bank indicators
pip install epidatasets[worldbank]

# Install everything
pip install epidatasets[all]
```

### Development installation

```bash
git clone https://github.com/fccoelho/epidemiological-datasets.git
cd epidemiological-datasets
pip install -e ".[dev,docs]"
```

## 🚀 Quick Start

```python
from epidatasets import get_source, list_sources

# Discover available sources
sources = list_sources()
for name, meta in sorted(sources.items()):
    print(f"{name}: {meta['description']}")

# Get a specific source
paho = get_source("paho")
countries = paho.list_countries()
print(f"PAHO covers {len(countries)} countries")

# Get WHO data (requires: pip install epidatasets[who])
who = get_source("who")
malaria = who.get_indicator(
    indicator="MALARIA_EST_INCIDENCE",
    years=[2020, 2021, 2022],
    countries=["BRA", "IND", "NGA"]
)

# Get OWID COVID-19 data
owid = get_source("owid")
covid = owid.get_covid_data(
    countries=["BRA", "USA", "IND"],
    metrics=["cases", "deaths"]
)
```

## 📁 Repository Structure

```
epidemiological-datasets/
├── src/epidatasets/           # Main Python package
│   ├── __init__.py            # Public API (get_source, list_sources)
│   ├── _base.py               # BaseAccessor ABC
│   ├── _registry.py           # Plugin registry (entry_points)
│   ├── cli.py                 # CLI (typer)
│   ├── sources/               # 21 data source accessors
│   │   ├── __init__.py
│   │   ├── africa_cdc.py
│   │   ├── cdc_opendata.py
│   │   ├── china_cdc.py
│   │   ├── colombia_ins.py
│   │   ├── copernicus_cds.py
│   │   ├── datasus_pysus.py
│   │   ├── ecdc_opendata.py
│   │   ├── epipulse.py
│   │   ├── eurostat.py
│   │   ├── global_health.py
│   │   ├── healthdata_gov.py
│   │   ├── india_idsp.py
│   │   ├── infodengue_api.py
│   │   ├── malaria_atlas.py
│   │   ├── owid.py
│   │   ├── paho.py
│   │   ├── pathoplexus.py
│   │   ├── respicast.py
│   │   ├── rki_germany.py
│   │   ├── ukhsa.py
│   │   └── who_ghoclient.py
│   └── utils/                 # Utilities
│       ├── cache.py           # Caching layer
│       ├── rate_limit.py      # API rate limiting
│       ├── geo.py             # Geospatial helpers
│       ├── validation.py      # Data validation
│       └── io.py              # I/O utilities
├── tests/                     # Test suite
│   ├── sources/
│   ├── utils/
│   ├── conftest.py
│   └── ...
├── docs/                      # MkDocs documentation
│   ├── mkdocs.yml
│   └── docs/
│       ├── index.md
│       ├── installation.md
│       ├── quickstart.md
│       ├── sources/           # Per-source API docs (21 pages)
│       ├── api/               # API reference
│       │   ├── base.md
│       │   ├── registry.md
│       │   ├── cli.md
│       │   └── utils.md
│       └── examples/          # Jupyter notebooks
├── mkdocs.yml                 # Docs config
├── .readthedocs.yaml          # ReadTheDocs config
├── pyproject.toml             # Package configuration
└── README.md
```

## 🌐 Available Datasets

### Global 🌍

| Dataset | Description | Update Frequency | Access Level | Module |
|---------|-------------|------------------|--------------|--------|
| [WHO Global Health Observatory](https://www.who.int/data/gho) | Health indicators by country | Annual | Open | `epidatasets.sources.who_ghoclient` |
| [Our World in Data - Health](https://ourworldindata.org/health) | COVID-19, vaccination, excess mortality | Daily/Weekly | Open | `epidatasets.sources.owid` |
| [Global Health Data Exchange (GHDx)](http://ghdx.healthdata.org/) | Catalog of health datasets | Varies | Varies | Catalog only |
| [HDX (Humanitarian Data Exchange)](https://data.humdata.org/) | Health in crisis contexts | Real-time | Open | Planned |
| [Global.health](https://global.health/) | Pandemic linelist data | Varies | Open | `epidatasets.sources.global_health` |
| [Malaria Atlas Project](https://malariaatlas.org/) | Malaria prevalence & vector data | Annual | Open | `epidatasets.sources.malaria_atlas` |
| [Copernicus Climate Data Store](https://cds.climate.copernicus.eu/) | Environmental & climate data | Varies | Open | `epidatasets.sources.copernicus_cds` |
| [Pathoplexus](https://pathoplexus.org/) | Pathogen genomic data | Continuous | Open | `epidatasets.sources.pathoplexus` |
| [InfoDengue](https://info.dengue.mat.br/) | Dengue surveillance (Brazil) | Weekly | Open | `epidatasets.sources.infodengue_api` |

### North America 🇺🇸🇨🇦🇲🇽

| Dataset | Description | Update Frequency | Access Level | Module |
|---------|-------------|------------------|--------------|--------|
| [CDC Open Data](https://data.cdc.gov/) | CDC datasets portal (COVID-19, Influenza, NNDSS, CDI) | Varies | Open | `epidatasets.sources.cdc_opendata` |
| [HealthData.gov](https://healthdata.gov/) | US health system data | Weekly | Open | `epidatasets.sources.healthdata_gov` |
| [Statistics Canada - Health](https://www.statcan.gc.ca/en/health) | Canadian health data | Quarterly | Open | Planned |

### South America 🌎

| Dataset | Description | Update Frequency | Access Level | Module |
|---------|-------------|------------------|--------------|--------|
| [SINAN / DATASUS - Brazil](http://portalsinan.saude.gov.br/) | Brazilian notifiable diseases & health system data | Weekly | Open* | `epidatasets.sources.datasus_pysus` |
| [PAHO/WHO Regional Data](https://www.paho.org/en/data) | Pan-American health data | Monthly | Open | `epidatasets.sources.paho` |
| [Chile DEIS](https://deis.minsal.cl/) | Chilean health statistics | Monthly | Open | Planned |
| [Colombia INS](https://www.ins.gov.co/) | Colombian public health data (SIVIGILA) | Weekly | Open | `epidatasets.sources.colombia_ins` |

> *Note: DATASUS access requires `pip install epidatasets[brazil]` (installs PySUS).

### Europe 🇪🇺

| Dataset | Description | Update Frequency | Access Level | Module |
|---------|-------------|------------------|--------------|--------|
| [ECDC EpiPulse](https://epipulse.ecdc.europa.eu/) | European surveillance portal (53 countries, 50+ diseases) | Daily/Weekly | Registration | `epidatasets.sources.epipulse` |
| [ECDC Open Data](https://atlas.ecdc.europa.eu/) | Infectious disease surveillance (50+ diseases, 30 countries) | Weekly | Open | `epidatasets.sources.ecdc_opendata` |
| [ECDC RespiCast](https://www.ecdc.europa.eu/en/publications-data/european-respiratory-diseases-forecasting-hub-respicast) | Respiratory disease forecasting hub | Weekly | Open | `epidatasets.sources.respicast` |
| [Eurostat Health](https://ec.europa.eu/eurostat/web/health) | EU health statistics | Annual | Open | `epidatasets.sources.eurostat` |
| [UK Health Security Agency](https://www.gov.uk/government/collections/health-protection-data) | UK health data | Weekly | Open | `epidatasets.sources.ukhsa` |
| [Robert Koch Institute](https://www.rki.de/EN/Content/infections/epidemiology/data.html) | German surveillance data | Weekly | Open | `epidatasets.sources.rki_germany` |

### Africa 🌍

| Dataset | Description | Update Frequency | Access Level | Module |
|---------|-------------|------------------|--------------|--------|
| [WHO Afro Health Observatory](https://www.afro.who.int/health-topics/health-observatory) | African region health data | Annual | Open | `epidatasets.sources.who_ghoclient` |
| [Africa CDC](https://africacdc.org/) | African public health data (55 AU member states) | Weekly | Open | `epidatasets.sources.africa_cdc` |

### Asia 🌏

| Dataset | Description | Update Frequency | Access Level | Module |
|---------|-------------|------------------|--------------|--------|
| [China CDC Weekly](http://weekly.chinacdc.cn/) | Chinese surveillance data | Weekly | Open | `epidatasets.sources.china_cdc` |
| [IDSP India](https://idsp.nic.in/) | Indian disease surveillance | Weekly | Open* | `epidatasets.sources.india_idsp` |
| [NIID Japan](https://www.niid.go.jp/niid/en/) | Japanese infectious disease data | Weekly | Open | Planned |
| [Korea CDC](https://www.kdca.go.kr/) | Korean disease control data | Weekly | Open | Planned |

### Oceania 🇦🇺🇳🇿

| Dataset | Description | Update Frequency | Access Level | Module |
|---------|-------------|------------------|--------------|--------|
| [Australian Institute of Health and Welfare](https://www.aihw.gov.au/) | Australian health data | Annual | Open | Planned |
| [NZ Ministry of Health](https://www.health.govt.nz/nz-health-statistics) | New Zealand health statistics | Annual | Open | Planned |

## 💻 CLI Usage

The `epidatasets` CLI provides quick access from the terminal (requires `pip install epidatasets[cli]`):

```bash
# List all available data sources
epidatasets sources

# Show detailed info about a source
epidatasets info who

# List countries covered by a source
epidatasets countries paho
```

## 💡 Usage Examples

### Example 1: WHO Global Health Data

```python
from epidatasets import get_source

who = get_source("who")

# Get malaria incidence data
data = who.get_indicator(
    indicator="MALARIA_EST_INCIDENCE",
    years=[2020, 2021, 2022],
    countries=["BRA", "IND", "NGA"]
)
print(data.head())
```

### Example 2: PAHO Pan-American Health Data

```python
from epidatasets import get_source

paho = get_source("paho")

# List member countries
countries = paho.list_countries()
print(f"Total countries: {len(countries)}")

# Get immunization coverage
coverage = paho.get_immunization_coverage(
    vaccines=['DTP3', 'MCV1'],
    subregion='Southern Cone',
    years=[2020, 2021, 2022]
)

# Compare health indicators
comparison = paho.compare_countries(
    indicator='LIFE_EXPECTANCY',
    countries=['BRA', 'MEX', 'ARG', 'COL'],
    years=[2019, 2020, 2021]
)
```

### Example 3: Eurostat EU Health Statistics

```python
from epidatasets import get_source

eurostat = get_source("eurostat")

# Healthcare expenditure
expenditure = eurostat.get_healthcare_expenditure(
    countries=['DEU', 'FRA', 'ITA'],
    years=list(range(2015, 2024))
)

# Mortality data by cause
mortality = eurostat.get_mortality_data(
    cause_code='COVID-19',
    countries=['DEU', 'FRA', 'ITA'],
    years=[2020, 2021, 2022]
)

# Life expectancy comparison
life_exp = eurostat.get_life_expectancy(
    countries=['DEU', 'FRA', 'ITA', 'ESP'],
    years=[2019, 2020, 2021]
)
```

### Example 4: Our World in Data

```python
from epidatasets import get_source

owid = get_source("owid")

# COVID-19 data for specific countries
covid = owid.get_covid_data(
    countries=['BRA', 'USA', 'IND'],
    metrics=['cases', 'deaths', 'hospitalizations'],
    start_date='2021-01-01',
    end_date='2021-12-31'
)

# Excess mortality estimates
excess = owid.get_excess_mortality(
    countries=['GBR', 'ITA', 'USA'],
    start_date='2020-03-01'
)

# Global summary
summary = owid.get_global_summary()
```

### Example 5: Brazil DATASUS via PySUS

```python
from epidatasets import get_source

datasus = get_source("datasus")

# Access Brazilian notifiable disease data
dengue = datasus.download(
    disease="Dengue",
    years=[2022, 2023],
    states=["RJ", "SP", "MG"]
)
```

### Example 6: Africa CDC Data

```python
from epidatasets import get_source

africa_cdc = get_source("africa_cdc")

# List all 55 African Union member states
countries = africa_cdc.list_countries()

# Get disease outbreaks
ebola = africa_cdc.get_disease_outbreaks(
    disease='EBOLA',
    countries=['CD', 'UG', 'GN']
)

# Vaccination coverage
vax = africa_cdc.get_vaccination_coverage(
    countries=['NG', 'ET', 'ZA'],
    vaccines=['COVID-19', 'Measles']
)
```

### Example 7: RKI Germany Surveillance

```python
from epidatasets import get_source

rki = get_source("rki")

# COVID-19 nowcasting with R estimates
nowcast = rki.get_covid_nowcast(
    date_range=('2022-01-01', '2022-06-30')
)

# Influenza surveillance
flu = rki.get_influenza_data(seasons=['2022/23', '2023/24'])
```

### Example 8: Multi-source Comparison

```python
from epidatasets import get_source, list_sources

# See all available sources
print(list_sources().keys())

# Compare data across sources
who = get_source("who")
owid = get_source("owid")

who_malaria = who.get_indicator(
    indicator="MALARIA_EST_INCIDENCE",
    years=[2022],
    countries=["BRA"]
)

owid_covid = owid.get_covid_data(
    countries=["BRA"],
    metrics=["cases", "deaths"],
    start_date='2022-01-01',
    end_date='2022-12-31'
)
```

## 📊 Available Sources

| Source Name | Class | Extra | Description |
|-------------|-------|-------|-------------|
| `africa_cdc` | `AfricaCDCAccessor` | — | Africa CDC public health data (55 AU states) |
| `cdc_opendata` | `CDCOpenDataAccessor` | — | US CDC Open Data portal |
| `china_cdc` | `ChinaCDCAccessor` | — | China CDC Weekly surveillance |
| `colombia_ins` | `ColombiaINSAccessor` | — | Colombia INS/SIVIGILA surveillance |
| `copernicus_cds` | `CopernicusCDSAccessor` | `[climate]` | Copernicus Climate Data Store |
| `datasus` | `DataSUSAccessor` | `[brazil]` | Brazilian DATASUS/SINAN (via PySUS) |
| `ecdc` | `ECDCOpenDataAccessor` | — | ECDC infectious disease data |
| `epipulse` | `EpiPulseAccessor` | — | ECDC EpiPulse surveillance portal |
| `eurostat` | `EurostatAccessor` | `[eurostat]` | EU health statistics |
| `global_health` | `GlobalHealthAccessor` | — | Global.health pandemic linelist data |
| `healthdata_gov` | `HealthDataGovAccessor` | — | US HealthData.gov |
| `india_idsp` | `IndiaIDSPAccessor` | — | India IDSP disease surveillance |
| `infodengue` | `InfoDengueAPI` | — | InfoDengue dengue surveillance (Brazil) |
| `malaria_atlas` | `MalariaAtlasAccessor` | — | Malaria Atlas Project data |
| `owid` | `OWIDAccessor` | — | Our World in Data (COVID-19, vaccination) |
| `paho` | `PAHOAccessor` | — | PAHO Pan-American health data |
| `pathoplexus` | `PathoplexusAccessor` | `[genomics]` | Pathoplexus pathogen genomic data |
| `respicast` | `RespiCastAccessor` | — | ECDC respiratory disease forecasting |
| `rki` | `RKIGermanyAccessor` | — | Robert Koch Institute (Germany) |
| `ukhsa` | `UKHSAAccessor` | — | UK Health Security Agency |
| `who` | `WHOAccessor` | `[who]` | WHO Global Health Observatory |

## ❓ FAQ

### What is epidatasets?

A Python library providing a unified interface to 21 epidemiological data sources worldwide, installable via `pip install epidatasets`.

### Do I need to install all optional dependencies?

No. The base install covers most sources. Only install extras for sources that need them (e.g., `pip install epidatasets[who]` for WHO GHO data, `pip install epidatasets[brazil]` for DATASUS).

### How do I discover available sources?

```python
from epidatasets import list_sources
print(list_sources())
```

Or from the CLI: `epidatasets sources`

### Are all dataset accessors fully implemented?

Most accessors provide working data retrieval. Some are structured placeholders for sources that require registration or have limited public APIs. Check the [documentation](https://epidatasets.readthedocs.io) for each source's status.

### Can I contribute a new data source?

Yes! Sources are registered via `entry_points` in `pyproject.toml`. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on adding new accessors.

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

1. **New data source accessors** - Especially from underrepresented regions
2. **Example notebooks** - Jupyter notebooks demonstrating data analysis
3. **Documentation** - Translations, improvements, and API docs
4. **Bug fixes** - Check the [issue tracker](https://github.com/fccoelho/epidemiological-datasets/issues)

### Badges for Contributors

<p align="center">
  <a href="https://github.com/fccoelho/epidemiological-datasets/issues?q=is%3Aopen+is%3Aissue+label%3A%22good%20first%20issue%22">
    <img src="https://img.shields.io/github/issues/fccoelho/epidemiological-datasets/good%20first%20issue?style=for-the-badge&logo=github&color=brightgreen" alt="Good First Issues">
  </a>
  <a href="https://github.com/fccoelho/epidemiological-datasets/issues?q=is%3Aopen+is%3Aissue+label%3A%22help+wanted%22">
    <img src="https://img.shields.io/github/issues/fccoelho/epidemiological-datasets/help%20wanted?style=for-the-badge&logo=github&color=orange" alt="Help Wanted">
  </a>
</p>

## 📚 Related Projects

| Project | Description | Repository |
|---------|-------------|------------|
| **PySUS** | Brazilian health data (DATASUS) | [AlertaDengue/PySUS](https://github.com/AlertaDengue/PySUS) |
| **ghoclient** | WHO Global Health Observatory | [fccoelho/ghoclient](https://github.com/fccoelho/ghoclient) |
| **epigrass** | Epidemic simulation | [EpiGrass/epigrass](https://github.com/EpiGrass/epigrass) |
| **epimodels** | Mathematical epidemiology | [fccoelho/epimodels](https://github.com/fccoelho/epimodels) |

## 📊 Statistics

- **Data sources:** 21 registered (via plugin registry)
- **Countries covered:** 100+
- **Optional extras:** 10 (`who`, `brazil`, `eurostat`, `climate`, `geo`, `viz`, `genomics`, `cli`, `worldbank`, `search`)
- **Example notebooks:** 20+
- **Documentation:** [epidatasets.readthedocs.io](https://epidatasets.readthedocs.io)

## 📚 Citation

If you use this package in your research, please cite:

```bibtex
@misc{fccoelho_epidatasets,
  author = {Coelho, Flávio Codeço},
  title = {Epidatasets: Python Access to Epidemiological Datasets Worldwide},
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

## 💜 Sponsor

<p align="center">
  <b>This project is sponsored by</b>
</p>

<p align="center">
  <a href="https://kwar-ai.com.br" target="_blank">
    <img src="assets/kwar-ai-logo.jpg" alt="Kwar-AI" height="120">
  </a>
</p>

<p align="center">
  <b><a href="https://kwar-ai.com.br">Kwar-AI</a></b> — Intelligence for Epidemiology
</p>

<p align="center">
  AI-powered solutions for disease surveillance and outbreak prediction
</p>

---

## 🙏 Acknowledgments

- **PySUS Contributors** - For making Brazilian health data accessible
- **WHO** - For maintaining the Global Health Observatory
- **All data providers** who make epidemiological data openly accessible
- **Global public health community**

## 📞 Contact

- **Author:** Flávio Codeço Coelho (@fccoelho)
- **Website:** https://fccoelho.github.io/
- **Documentation:** https://epidatasets.readthedocs.io

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
