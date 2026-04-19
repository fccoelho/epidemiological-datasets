# Data Sources

Epidatasets provides access to **21 epidemiological data sources** from around the world.

## How Sources Work

Each source inherits from `BaseAccessor` and is registered via Python entry-points. This means:

- Sources are **auto-discovered** at runtime
- Third-party packages can **add new sources** by registering their own entry-points
- You only install dependencies for the sources you need

## Source Registry

```python
from epidatasets import list_sources, get_source

# List all registered sources
sources = list_sources()

# Get a specific source
who = get_source("who")
```

## Available Sources

| Source | Key | Region | Dependencies |
|--------|-----|--------|--------------|
| WHO Global Health Observatory | `who` | Global | `ghoclient` |
| PAHO | `paho` | Americas | None |
| Our World in Data | `owid` | Global | None |
| ECDC Open Data | `ecdc` | Europe | None |
| Eurostat | `eurostat` | Europe | `eurostat` |
| RKI Germany | `rki` | Germany | None |
| UKHSA | `ukhsa` | UK | None |
| Africa CDC | `africa_cdc` | Africa | None |
| China CDC | `china_cdc` | China | `beautifulsoup4` |
| India IDSP | `india_idsp` | India | `beautifulsoup4` |
| Colombia INS | `colombia_ins` | Colombia | None |
| DATASUS (PySUS) | `datasus` | Brazil | `pysus` |
| CDC Open Data | `cdc_opendata` | US | None |
| HealthData.gov | `healthdata_gov` | US | None |
| EpiPulse | `epipulse` | Europe | None |
| RespiCast | `respicast` | Europe | None |
| Global.health | `global_health` | Global | None |
| Malaria Atlas | `malaria_atlas` | Global | None |
| Pathoplexus | `pathoplexus` | Global | `xmltodict` |
| Copernicus CDS | `copernicus_cds` | Global | `cdsapi`, `xarray` |
| InfoDengue | `infodengue` | Brazil | None |
