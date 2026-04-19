# Quick Start

## Listing Available Sources

```python
from epidatasets import list_sources

sources = list_sources()
for name, meta in sources.items():
    print(f"{name}: {meta['description']}")
```

## Getting a Source

```python
from epidatasets import get_source

# Instantiate a source
paho = get_source("paho")

# List countries covered
countries = paho.list_countries()
print(countries.head())

# Get source info
print(paho.info())
```

## Working with Data

```python
from epidatasets import get_source

owid = get_source("owid")

# List available countries
countries = owid.list_countries()

# Get COVID-19 data
covid = owid.get_covid_data(countries=["BRA", "USA"])
```

## Using the CLI

```bash
# List all sources
epidatasets sources

# Get info about a source
epidatasets info who

# List countries for a source
epidatasets countries paho
```
