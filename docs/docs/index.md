# Epidatasets

Python library for accessing epidemiological datasets worldwide.

A curated collection of openly accessible epidemiological data sources with a unified Python interface. Sources are discovered at runtime via a pluggable registry.

## Features

- **21 data sources** covering 100+ countries
- **Plugin registry** -- sources auto-discovered via entry-points
- **Unified API** -- all sources share a common `BaseAccessor` interface
- **Optional dependencies** -- install only what you need
- **CLI** -- query sources from the command line
- **Well-documented** -- API reference, examples, and Jupyter notebooks

## Quick Start

```python
from epidatasets import get_source, list_sources

# See what's available
list_sources()

# Get a source and query it
who = get_source("who")
countries = who.list_countries()
```

## Installation

```bash
pip install epidatasets
```

For specific data sources:

```bash
pip install epidatasets[who]      # WHO GHO data
pip install epidatasets[brazil]   # Brazilian DATASUS data
pip install epidatasets[eurostat] # EU health statistics
pip install epidatasets[all]      # Everything
```

## Supported Sources

| Source | Description | Region |
|--------|-------------|--------|
| WHO | World Health Organization GHO | Global |
| PAHO | Pan American Health Organization | Americas |
| OWID | Our World in Data | Global |
| ECDC | European Centre for Disease Prevention | Europe |
| Eurostat | EU health statistics | Europe |
| RKI | Robert Koch Institute (Germany) | Germany |
| UKHSA | UK Health Security Agency | UK |
| Africa CDC | African Centres for Disease Control | Africa |
| China CDC | China CDC Weekly | China |
| India IDSP | Integrated Disease Surveillance | India |
| Colombia INS | SIVIGILA surveillance | Colombia |
| DATASUS | Brazilian health data | Brazil |
| CDC Open Data | US CDC data portal | US |
| HealthData.gov | US health system data | US |
| EpiPulse | ECDC surveillance portal | Europe |
| RespiCast | Respiratory disease forecasting | Europe |
| Global.health | Pandemic line-list data | Global |
| Malaria Atlas | Malaria data | Global |
| Pathoplexus | Genomic epidemiology | Global |
| Copernicus CDS | Climate data for health | Global |
| InfoDengue | Dengue surveillance (Brazil) | Brazil |

## License

MIT License. See [LICENSE](https://github.com/fccoelho/epidemiological-datasets/blob/main/LICENSE).
