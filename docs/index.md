# Epidemiological Datasets Documentation

Welcome to the documentation for the Epidemiological Datasets Repository!

## Overview

This project provides unified, easy-to-use Python interfaces for accessing public health data from multiple international sources.

## Quick Links

- [Installation](installation.md)
- [Quick Start](quickstart.md)
- [API Reference](api/)
- [Examples](../examples/)

## Data Sources

### 🇧🇷 PySUS - Brazilian Health Data

Access Brazil's public health data through DATASUS.

```python
from epi_data.sources import PySUS
source = PySUS()
data = source.fetch_disease("dengue", year=2023, state="RJ")
```

### 🌍 WHO - Global Health Observatory

World Health Organization global health indicators.

```python
from epi_data.sources import WHO
source = WHO()
data = source.get_indicator("WHOSIS_000001", countries=["BRA", "USA"])
```

### 🏦 World Bank - Health Indicators

Health, nutrition, and population statistics.

```python
from epi_data.sources import WorldBank
source = WorldBank()
data = source.get_indicator("SH.XPD.CHEX.GD.ZS", countries=["BRA"])
```

### 🇪🇺 ECDC - European Surveillance

European Centre for Disease Prevention and Control.

```python
from epi_data.sources import ECDC
source = ECDC()
data = source.get_covid_cases(countries=["DE", "FR", "IT"])
```

## Contributing

We welcome contributions! Please see our [Contributing Guide](../CONTRIBUTING.md).
