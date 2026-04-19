# API Reference

## Core API

### `get_source(name, **kwargs)`

Instantiate a data source by name.

```python
from epidatasets import get_source
who = get_source("who")
```

### `list_sources()`

Return metadata for all registered sources.

```python
from epidatasets import list_sources
sources = list_sources()
```

## Base Class

All accessors inherit from `BaseAccessor`.

::: epidatasets._base.BaseAccessor
