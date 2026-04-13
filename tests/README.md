# 🧪 Test Suite for Epidemiological Datasets

This directory contains tests for the epidemiological data accessors.

## 📁 Test Files

| File | Description |
|------|-------------|
| `test_accessors.py` | Tests for all data accessors (HealthData.gov, Colombia INS, etc.) |

## 🚀 Running Tests

### Run all tests
```bash
pytest tests/
```

### Run only accessor tests
```bash
pytest tests/test_accessors.py -v
```

### Run smoke tests only (fast, no external APIs)
```bash
pytest tests/test_accessors.py::TestSmoke -v
```

### Skip external API tests (for offline development)
```bash
SKIP_EXTERNAL_TESTS=true pytest tests/test_accessors.py -v
```

### Run only offline tests using marker
```bash
pytest tests/ -m "not external_api" -v
```

### Run specific accessor test
```bash
pytest tests/test_accessors.py::TestRKI -v
```

## 🏷️ Test Categories

### Smoke Tests (`TestSmoke`)
- Fast tests that don't require external APIs
- Validate repository structure
- Check file existence
- Run on every PR/push

### External API Tests
- Test actual connections to data sources
- May be slow (5-15 seconds per accessor)
- Can fail if external service is down
- Marked with `@requires_external_api`

## ⚙️ Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SKIP_EXTERNAL_TESTS` | Skip tests that call external APIs | `false` |

## 🔄 CI/CD Integration

Tests run automatically on:
- Every PR to `main` or `develop`
- Every push to `main` or `develop`

### CI Jobs:
1. **test** - Unit tests (fast)
2. **test-accessors** - Accessor tests with external APIs (separate job, may fail gracefully)

## 🛠️ Adding New Tests

When adding a new accessor, create tests following this pattern:

```python
class TestMyNewAccessor:
    """Tests for MyNew accessor"""
    
    @requires_external_api
    def test_initialization(self):
        """Test accessor initializes correctly"""
        from my_new_accessor import MyNewAccessor
        accessor = MyNewAccessor()
        assert accessor is not None
    
    @requires_external_api
    def test_get_data(self):
        """Test fetching data"""
        from my_new_accessor import MyNewAccessor
        accessor = MyNewAccessor()
        df = accessor.get_data()
        assert isinstance(df, pd.DataFrame)
```

## 🐛 Troubleshooting

### Tests failing with timeout
External API tests have timeouts. If failing:
1. Check if service is down
2. Run with `SKIP_EXTERNAL_TESTS=true`
3. Check network connectivity

### Import errors
Make sure you installed the package:
```bash
pip install -e ".[dev]"
```

## 📊 Coverage

Coverage reports are generated in CI and uploaded to Codecov.
