## 📋 Description

<!-- Provide a brief description of the changes in this PR -->

Brief description of what this PR does and why it's needed.

## 🎯 Type of Change

<!-- Mark the relevant option with an [x] -->

- [ ] 🐛 Bug fix (non-breaking change which fixes an issue)
- [ ] ✨ New feature (non-breaking change which adds functionality)
- [ ] 🌍 New data source
- [ ] 💥 Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] 📝 Documentation update
- [ ] 🎨 Code style/formatting
- [ ] ♻️ Refactoring (no functional changes)
- [ ] ⚡ Performance improvement
- [ ] ✅ Test additions/improvements
- [ ] 🔧 Build/CI configuration

## 🔗 Related Issues

<!-- Link to any related issues using "Fixes #123" or "Closes #456" -->

Fixes #(issue number)
Related to #(issue number)

## 🧪 Testing

<!-- Describe the tests you ran and how to reproduce them -->

- [ ] Tests added for new functionality
- [ ] Tests pass locally (`pytest`)
- [ ] Code coverage maintained or improved
- [ ] Tested on sample data

**Test commands:**
```bash
# Run specific tests
pytest tests/test_<module>.py -v

# Run with coverage
pytest --cov=epi_data --cov-report=html

# Run all tests
pytest
```

## 📊 Data Source Details (if applicable)

<!-- Fill this section if adding a new data source -->

- **Name**: 
- **URL**: 
- **Geographic Coverage**: 
- **Update Frequency**: 
- **Authentication Required**: Yes/No

**Example usage:**
```python
from epi_data.sources import NewSource

source = NewSource()
data = source.fetch_data(country='BRA', year=2023)
```

## 📚 Documentation

- [ ] README.md updated (if applicable)
- [ ] Docstrings added/updated
- [ ] Example notebook created (for new data sources)
- [ ] CHANGELOG.md updated
- [ ] API documentation updated (if applicable)

## ✅ Checklist

### Code Quality
- [ ] Code follows the project's style guidelines (`black`, `ruff`)
- [ ] Self-review of code completed
- [ ] Code is well-commented, particularly in hard-to-understand areas
- [ ] No new warnings generated (`ruff check .`)
- [ ] Type hints added where appropriate (`mypy`)

### Functionality
- [ ] Code works as expected
- [ ] Edge cases handled appropriately
- [ ] Error messages are user-friendly
- [ ] No hardcoded credentials or sensitive data

### Performance
- [ ] Efficient data retrieval (caching where appropriate)
- [ ] Reasonable memory usage for large datasets
- [ ] No unnecessary API calls

### Compatibility
- [ ] Works on Python 3.9, 3.10, 3.11, 3.12
- [ ] No breaking changes to existing API
- [ ] Backward compatibility maintained

## 📸 Screenshots (if applicable)

<!-- Add screenshots for UI changes or data visualizations -->

## 🌍 Impact Assessment

<!-- Describe the impact of your changes -->

**Who will benefit:**
- Researchers studying...
- Public health professionals...
- Data scientists...

**Breaking changes:**
- None / List any breaking changes

**Migration guide:**
- Not applicable / Describe steps if breaking changes exist

## 🔄 Testing Evidence

<!-- Provide evidence that your changes work -->

```python
# Paste output of successful tests or example usage
>>> from epi_data.sources import PySUS
>>> source = PySUS()
>>> data = source.fetch_data(disease='dengue', year=2023, state='RJ')
>>> print(len(data))
15000
>>> print(data.columns.tolist())
['date', 'cases', 'deaths', 'state', 'municipality']
```

## 🙋 Questions for Reviewers

<!-- Optional: Ask specific questions for reviewers to consider -->

1. 
2. 

## 📎 Additional Notes

<!-- Any additional information that might be helpful -->

---

**Thank you for your contribution!** 🎉

By submitting this PR, you agree to follow our [Code of Conduct](https://github.com/fccoelho/epidemiological-datasets/blob/main/CODE_OF_CONDUCT.md).
