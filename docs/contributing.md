# Contributing

We welcome contributions! Please see the [Contributing Guide](https://github.com/fccoelho/epidemiological-datasets/blob/main/CONTRIBUTING.md) on GitHub.

## Adding a New Data Source

1. Create a new module in `src/epidatasets/sources/`
2. Inherit from `BaseAccessor`
3. Implement `list_countries()` and your data methods
4. Register the entry-point in `pyproject.toml`
5. Add tests
6. Submit a PR

### Example

```python
from typing import ClassVar
from epidatasets._base import BaseAccessor
import pandas as pd

class MyAccessor(BaseAccessor):
    source_name: ClassVar[str] = "my_source"
    source_description: ClassVar[str] = "My data source"
    source_url: ClassVar[str] = "https://example.com"

    def list_countries(self) -> pd.DataFrame:
        return pd.DataFrame([
            {"country_code": "US", "country_name": "United States"}
        ])
```
