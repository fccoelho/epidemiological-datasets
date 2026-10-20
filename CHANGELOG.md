# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.9.0] - 2026-10-20

### Added

- New `swiss_bag` accessor (`SwissBAGAccessor`) for the Swiss Federal Office of Public Health (BAG) Infectious Diseases Dashboard API: 54 topics / 1,600+ series sets (notifiable diseases, sentinel ILI/ARI, respiratory pathogens, wastewater viral load & sequencing, antimicrobial resistance/consumption) with weekly version listing, set metadata discovery, filtered and all-series (`availableSeriesConfigurations` fan-out) tidy series queries with parsed ISO-like `temporal` column, and cached CSV/JSON bulk exports with version override. National + cantonal (26 cantons) coverage since 2023-11. No API key required.
- New `srag` accessor (`SRAGOpenDataSUSAccessor`) for the Brazilian SRAG surveillance line-level dataset (Sivep-Gripe / e-SUS Notifica, 2019–present) on OpenData SUS: per-year resource discovery, streamed downloads with UTF-8/Latin-1 encoding fallback, chunked/lazy reading with composable filters (state, IBGE municipality, epi-week, lab-confirmed pathogen, outcome, age), weekly counts by geography/pathogen, IBGE municipality↔name resolution, frozen-year permanent caching with 24h TTL for the live year. No API key required.
- New `opendengue` accessor (`OpenDengueAccessor`) for the OpenDengue global dengue case count database: versioned GitHub release downloads (national / highest-spatial / highest-temporal extracts), country lookup with exact, ISO3 and fuzzy name matching, admin-level and date-overlap filtering, location time-series, per-country source series summaries, 30-day caching and `OpenDengueDataError`. Includes the mandatory CC BY 4.0 citation helper.
- New `nhs_prescribing` accessor (`NHSPrescribingAccessor`) for NHS England primary care prescribing data: OpenPrescribing REST API (national/CCG/practice spending by BNF code, prescribing quality measures such as antibiotic stewardship, BNF & org code search, practice/CCG geolocations) plus the NHSBSA English Prescribing Dataset (EPD) monthly bulk CSVs with chunked/lazy reading, BNF hierarchy filtering at all levels and per-month timeseries aggregation. Filesystem cache with 7-day TTL (monthly release cycle) and wrapped `NHSPrescribingAPIError` with retry guidance. No API key required.
- New `opendatasus` accessor (`OpenDataSUSAccessor`) for the OpenDataSUS catalog (dadosabertos.saude.gov.br): dataset discovery, metadata and downloads from the Brazilian Ministry of Health open-data portal (CKAN backend via its Next.js frontend).
- New `japan_idwr` accessor (`JapanIDWRAccessor`) for the Japan Infectious Diseases Weekly Report: prefecture-level weekly surveillance for 88 notifiable and 19 sentinel-reporting diseases.
- New `hk_chp` accessor (`HongKongCHPAccessor`) for Hong Kong Centre for Health Protection open data (data.gov.hk): influenza and COVID-19 situation series.
- `china_cdc` accessor extended into comprehensive mainland-China coverage: NDCPA monthly notifiable disease overviews (including priority-monitored non-notifiable diseases), monthly COVID-19 situation reports and CNIC weekly influenza surveillance (sentinel ILI%, laboratory positivity by type/subtype).
- `china_cdc` accessor: weekly national sentinel surveillance of acute respiratory infections (全国急性呼吸道传染病哨点监测情况) — `list_respiratory_sentinel_reports()` (paginated chinacdc.cn archive, week 46/2024–present), `get_respiratory_sentinel_report(year, week)` (ILI consultation share national/South/North, 11-pathogen PCR positivity for outpatient ILI and hospitalised SARI syndromes, top-3 pathogens by region and age group, narrative; HTML cached under `~/.cache/epidatasets/china_cdc/` with 24h TTL), `get_respiratory_sentinel_surveillance(weeks)` (tidy long positivity table) and `get_respiratory_sentinel_ili(weeks)` (weekly ILI share series); module-level Chinese→English `RESPIRATORY_PATHOGEN_MAP`
- New `newsfeeds` module: RSS/news-feed aggregator with geotagging and spatiotemporal visualization (city/country/US-state gazetteers included).
- New `google_earth_engine` accessor (`GoogleEarthEngineAccessor`) for planetary-scale satellite imagery relevant to epidemiological analyses (requires the `earthengine` extra and GEE credentials).
- Example notebooks 42–50: OpenDataSUS catalog, Japan IDWR, Hong Kong CHP, China comprehensive surveillance (extended with the weekly respiratory sentinel section), news-feed spatiotemporal visualization, NHS prescribing, OpenDengue, SRAG and Swiss BAG IDD
- Mocked HTTP tests (CKAN portal, S3, IBGE and GitHub-release servers) with CSV/zip fixtures, plus live smoke tests gated behind `@pytest.mark.external_api`
- Docs pages `sources/nhs_prescribing.md`, `sources/srag.md`, `sources/opendengue.md`, `sources/swiss_bag.md` and README usage examples

### Changed

- Bumped source count to 41 data sources in the README
- Registered the `nhs_prescribing`, `srag`, `opendengue`, `swiss_bag`, `opendatasus`, `japan_idwr` and `google_earth_engine` entry-points in `pyproject.toml` and their exports in `epidatasets.sources`
- `disease_sh` accessor completed: full error handling, caching tests and docs
- `china_cdc`: article discovery now CrossRef-backed with DOI-based PDF URLs
- `gisaid`: uses `input()` instead of `getpass` for the password prompt in Jupyter
- Fixed the loss of `GoogleEarthEngineAccessor`/`JapanIDWR`/`OpenDataSUS` exports in `epidatasets.sources`

## [0.8.0] - 2026-08-03

### Added

- New `gisaid` accessor (`GISAIDAccessor`) for all 5 GISAID genomic surveillance databases (EpiCoV, EpiFlu, EpiPox, EpiRSV, EpiArbo) via Playwright browser automation with interactive credential prompts, query/metadata/sequence downloads, disk caching and rate limiting (requires the `gisaid` extra)
- New `gmpd` accessor (`GMPDAccessor`) for the Global Mammal Parasite Database: wild mammal host–parasite associations

## [0.7.0] - 2026-07-13

### Added

- New `disease_sh` accessor (`DiseaseShAccessor`) for the disease.sh open API — global/country/state COVID-19 totals, historical time series with date-range filtering, vaccine coverage, and US CDC influenza surveillance (ILINet, Public Health Lab, Clinical Lab). No API key required.
- New `demas` accessor (`DemasAccessor`) for the DEMAS Portal de Dados Abertos do SUS (Brazilian Ministry of Health) — 80+ public health datasets (arboviroses, vacinação, CNES, SISAGUA, vigilância ambiental, saúde indígena) via Swagger-based dataset discovery and paginated data fetching. No API key required.
- Example notebook for the disease.sh accessor (`32_disease_sh_COVID19_Influenza.ipynb`)
- Example notebook for the DEMAS accessor (`33_DEMAS_Dados_Abertos_SUS.ipynb`)
- Mocked HTTP tests for both accessors using the `responses` library

### Changed

- Bumped source count to 32 data sources in the docs index and README
- Registered `disease_sh` and `demas` entry-points and keywords in `pyproject.toml`
- Synced `__init__.py` runtime `__version__` with the package version

## [0.5.0] - 2026-06-22

### Added

- New `nz_health` accessor (`NZHealthAccessor`) for New Zealand health statistics from Stats NZ and Health NZ | Te Whatu Ora (mortality, life tables, hospital events, immunisation coverage)
- Shared `PDFParser` utility reused across PDF-based accessors
- Example notebook for the InfoDengue accessor (`18_InfoDengue_Brazilian_Arbovirus_Surveillance.ipynb`)
- Example notebook for the NZ Health accessor (`25_New_Zealand_Health_Data.ipynb`)

### Changed

- Moved `pdfplumber` to core dependencies
- Refactored 4 accessors to use the shared `PDFParser`
- Updated README to reflect 24 data sources and the implemented NZ Health accessor
- Expanded mkdocs navigation to include all example notebooks

### Fixed

- Eurostat country/year filtering, invalid indicator codes, and notebook visualization
- Colombia INS bulletin URLs
- RespiCast data source and fetching mechanism

## [0.3.1] - 2026-04-20

### Fixed

- Changed `ghoclient` dependency from git URL to PyPI version constraint (`>=1.0.4`)

## [0.3.0] - 2026-04-20

### Removed

- Deleted redundant `scripts/` directory (24 files) fully superseded by `src/epidatasets/`
- Deleted duplicate `examples/` directory (content preserved in `docs/examples/`)
- Deleted stale `issues/` directory (5 issue-tracking markdown files)
- Added `coverage.xml` to `.gitignore`

### Changed

- Flattened `docs/docs/` into `docs/` to remove unnecessary nesting
- Explicitly listed all 27 example notebooks in mkdocs navigation

### Fixed

- Fixed outdated `scripts.accessors.*` docstring references in 6 source files
- Fixed outdated `scripts.accessors.*` imports in 3 example notebooks
- Repaired broken notebooks: added missing `outputs` fields, fixed malformed JSON
- Fixed `PAOHAccessor` -> `PAHOAccessor` typo in docs/sources/paho.md

### Added

- GitHub Actions workflow for Python package publishing

## [0.2.0] - 2026-04-19

### Changed

- **Package renamed** from `epidemiological-datasets` / `epi_data` to **`epidatasets`**
- Consolidated all 21 data source accessors into `src/epidatasets/sources/`
- All accessors now inherit from `BaseAccessor` abstract base class
- Sources are discovered at runtime via pluggable entry-points registry
- Utilities split into focused submodules (`cache`, `rate_limit`, `geo`, `validation`, `io`)
- Heavy dependencies made optional (`[who]`, `[brazil]`, `[eurostat]`, `[climate]`, `[geo]`, `[viz]`, `[genomics]`, `[cli]`, `[worldbank]`, `[all]`)
- CI workflow updated for new package structure

### Added

- `BaseAccessor` ABC with `source_name`, `source_description`, `source_url` class variables
- Plugin registry (`_registry.py`) with `get_source()`, `list_sources()`, `reload_registry()`
- CLI: `epidatasets sources`, `epidatasets info <source>`, `epidatasets countries <source>`
- 21 entry-points registered in `pyproject.toml`
- MkDocs documentation with `mkdocs-jupyter` and `mkdocstrings` (32 doc pages)
- `.readthedocs.yaml` for ReadTheDocs integration
- Per-source API documentation stubs
- `test_registry.py` for plugin registry tests
- `test_utils.py` for utility module tests

### Removed

- Old `src/epi_data/` package (replaced by `src/epidatasets/`)
- `indexdir/` (empty directory)
- `main()` functions and `__main__` blocks from accessor scripts

## [0.1.0] - 2024-03-14

### Added
- Initial release with scripts-based accessors for 21 data sources
- Project documentation
- Repository structure, CI, issue templates
- Example Jupyter notebooks

[Unreleased]: https://github.com/fccoelho/epidemiological-datasets/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/fccoelho/epidemiological-datasets/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/fccoelho/epidemiological-datasets/releases/tag/v0.1.0
