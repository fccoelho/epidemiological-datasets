# Installation

## Basic Installation

```bash
pip install epidatasets
```

## Optional Extras

Install only the dependencies you need:

```bash
pip install epidatasets[who]        # WHO Global Health Observatory
pip install epidatasets[brazil]     # Brazilian DATASUS/PySUS
pip install epidatasets[eurostat]   # Eurostat EU statistics
pip install epidatasets[climate]    # Copernicus climate data
pip install epidatasets[geo]        # Geospatial tools
pip install epidatasets[viz]        # Visualization libraries
pip install epidatasets[genomics]   # Genomic data tools
pip install epidatasets[cli]        # Command-line interface
pip install epidatasets[worldbank]  # World Bank indicators
```

Install everything:

```bash
pip install epidatasets[all]
```

## Development Installation

```bash
git clone https://github.com/fccoelho/epidemiological-datasets.git
cd epidemiological-datasets
pip install -e ".[dev]"
```

## Requirements

- Python 3.10+
- pandas >= 1.5.0
- numpy >= 1.23.0
- requests >= 2.28.0
