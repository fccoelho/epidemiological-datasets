# Contributing to Epidemiological Datasets

Thank you for your interest in contributing! This document provides guidelines for contributing to this repository.

## 🎯 How to Contribute

### 1. Adding New Datasets

To add a new epidemiological dataset:

1. **Check if it already exists** - Search existing issues and the README
2. **Create an issue** describing the dataset:
   - Name of dataset
   - Source URL
   - Geographic coverage
   - Temporal coverage
   - Update frequency
   - Access level (Open/Restricted/API key required)
3. **Submit a pull request** updating the README.md with the new dataset

### 2. Contributing Python Access Scripts

To add a new accessor:

1. Create a new file in `scripts/accessors/` (e.g., `cdc.py`)
2. Follow the template structure:

```python
"""
[Source] Data Accessor

Description of the data source.
"""

import pandas as pd
import requests
from typing import List, Optional


class [Source]Accessor:
    """
    Accessor for [Source] epidemiological data.
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://api.example.com"
    
    def get_data(self, **params) -> pd.DataFrame:
        """
        Fetch data from source.
        
        Returns:
            DataFrame with standardized columns
        """
        # Implementation
        pass
```

3. Update `scripts/accessors/__init__.py` to export your accessor
4. Add unit tests in `tests/`
5. Update the README.md to mark the accessor as "✅ Implemented"

### 3. Reporting Issues

When reporting bugs or issues:

- Use the issue template
- Provide minimal reproducible example
- Include error messages and traceback
- Specify Python version and OS

### 4. Documentation Improvements

- Fix typos and clarify language
- Add examples and use cases
- Improve docstrings
- Translate to other languages (optional)

## 📝 Code Style

### Python Code

- Follow PEP 8
- Use type hints where appropriate
- Write docstrings for all public methods
- Maximum line length: 100 characters
- Use `black` for formatting:
  ```bash
  black scripts/
  ```

### Example Docstring

```python
def get_indicator(
    self,
    indicator: str,
    years: Optional[List[int]] = None
) -> pd.DataFrame:
    """
    Fetch data for a specific indicator.
    
    Args:
        indicator: Indicator code or name
        years: List of years to fetch
        
    Returns:
        DataFrame with standardized columns:
        - country_code: ISO3 country code
        - year: Year of observation
        - value: Numeric value
        
    Raises:
        ValueError: If indicator not found
        requests.HTTPError: If API request fails
        
    Example:
        >>> accessor = WHOAccessor()
        >>> data = accessor.get_indicator("MALARIA", years=[2020, 2021])
    """
```

## 🧪 Testing

Run tests before submitting:

```bash
# Install test dependencies
pip install pytest pytest-asyncio responses

# Run all tests
pytest tests/

# Run with coverage
pytest --cov=scripts tests/
```

### Writing Tests

```python
import pytest
from scripts.accessors import WHOAccessor


class TestWHOAccessor:
    def test_get_indicators_list(self):
        accessor = WHOAccessor()
        indicators = accessor.get_indicators_list()
        assert isinstance(indicators, pd.DataFrame)
        assert len(indicators) > 0
    
    def test_invalid_indicator_raises_error(self):
        accessor = WHOAccessor()
        with pytest.raises(ValueError):
            accessor.get_indicator("INVALID_INDICATOR_12345")
```

## 🔄 Pull Request Process

1. **Fork** the repository
2. **Create a branch**: `git checkout -b feature/your-feature-name`
3. **Make your changes** following the guidelines above
4. **Test your changes** locally
5. **Commit** with a clear message:
   ```
   Add CDC COVID-19 accessor
   
   - Implements CDCAccessor class
   - Adds support for daily case data
   - Includes unit tests
   ```
6. **Push** to your fork: `git push origin feature/your-feature-name`
7. **Create a Pull Request** with:
   - Clear description of changes
   - Link to related issue
   - Checklist of completed items

## 📋 PR Checklist

Before submitting:

- [ ] Code follows style guidelines
- [ ] Tests pass locally
- [ ] Documentation updated
- [ ] README.md updated (if adding dataset/script)
- [ ] Type hints included
- [ ] No hardcoded credentials or API keys
- [ ] Error handling implemented

## 🏷️ Dataset Contribution Template

When adding a new dataset, include:

```markdown
| Dataset | Description | Update Frequency | Access Level | Script |
|---------|-------------|------------------|--------------|--------|
| [Name](URL) | Brief description | Weekly/Monthly/Annual | Open/Restricted/Key | `scripts/accessors/file.py` |

**Additional Details:**
- Geographic coverage: Countries/regions
- Temporal coverage: Date range
- API documentation: URL
- Authentication: None/API Key/Registration required
- Rate limits: Requests per minute/hour
- Data format: JSON/CSV/XML
```

## 💬 Communication

- Be respectful and constructive
- Ask questions in issues before major changes
- Join discussions in existing issues
- Tag maintainers for review: @fccoelho

## 📜 License

By contributing, you agree that your contributions will be licensed under the MIT License.

## 🙏 Recognition

Contributors will be acknowledged in:
- README.md Contributors section
- Release notes
- Project documentation

---

**Thank you for helping make epidemiological data more accessible!** 🌍
