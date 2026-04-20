# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
