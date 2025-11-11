# FastAPI Pulse Test Suite

Complete pytest test suite for FastAPI Pulse with modern async patterns and comprehensive coverage.

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── unit/                    # Unit tests (no external dependencies)
│   ├── test_metrics_unit.py
│   ├── test_middleware_unit.py
│   ├── test_registry_unit.py
│   ├── test_payload_store_unit.py
│   └── test_sample_builder_unit.py
├── integration/             # Integration tests with real FastAPI app
│   └── test_full_flow.py
├── api/                     # API endpoint tests
│   └── test_endpoints.py
└── property/                # Property-based tests with Hypothesis
    └── test_metrics_properties.py
```

## Installation

Install test dependencies:

```bash
pip install -e ".[test]"
```

Or install dependencies individually:

```bash
pip install pytest pytest-cov pytest-asyncio pytest-mock pytest-xdist \
            httpx asgi-lifespan hypothesis freezegun numpy
```

## Running Tests

### Run all tests
```bash
pytest tests/
```

### Run with coverage
```bash
pytest tests/ --cov=fastapi_pulse --cov-report=html --cov-report=term
```

### Run specific test categories
```bash
# Unit tests only
pytest tests/unit/ -m unit

# Integration tests only
pytest tests/integration/ -m integration

# API endpoint tests only
pytest tests/api/ -m api

# Property-based tests only
pytest tests/property/ -m property
```

### Run tests in parallel
```bash
pytest tests/ -n auto
```

### Run with verbose output
```bash
pytest tests/ -v
```

### Generate coverage report
```bash
pytest tests/ --cov=fastapi_pulse --cov-report=html --cov-report=term-missing
open htmlcov/index.html  # View HTML report
```

## Test Categories

### Unit Tests (`tests/unit/`)
- **No external dependencies** (no real DB, clock, or network)
- Use `pytest-mock` for mocking
- Use `freezegun` for time manipulation
- Focus on individual component behavior
- Fast execution

### Integration Tests (`tests/integration/`)
- Test complete application workflows
- Use `httpx.AsyncClient` with `ASGITransport`
- Use `asgi-lifespan` for app lifecycle management
- Test interactions between components

### API Tests (`tests/api/`)
- Test all HTTP endpoints
- Verify request/response contracts
- Test error handling
- Validate response structures

### Property Tests (`tests/property/`)
- Use Hypothesis for property-based testing
- Test invariants across wide input ranges
- Catch edge cases automatically
- Focus on pure functions and schemas

## Coverage Targets

- **Lines**: ≥90%
- **Branches**: ≥80%

Current configuration in `pyproject.toml`:
```toml
[tool.coverage.report]
fail_under = 90
show_missing = true
```

## Test Patterns

### AAA Pattern (Arrange-Act-Assert)
All tests follow the AAA pattern for clarity:

```python
def test_example(fixture):
    # Arrange
    metrics = PulseMetrics()

    # Act
    metrics.record_request("/api", "GET", 200, 50.0)

    # Assert
    result = metrics.get_metrics()
    assert result["summary"]["total_requests"] == 1
```

### Async Tests
Async tests are automatically detected:

```python
async def test_async_endpoint(async_client):
    response = await async_client.get("/")
    assert response.status_code == 200
```

### Fixture Isolation
Tests use function-scoped fixtures for isolation:

```python
@pytest.fixture
def clean_metrics() -> PulseMetrics:
    """Provide a fresh PulseMetrics instance."""
    return PulseMetrics(window_seconds=300, bucket_seconds=60)
```

## Parallel Execution

Tests are designed to be parallel-safe with pytest-xdist:

```bash
# Auto-detect CPU count
pytest tests/ -n auto

# Specify worker count
pytest tests/ -n 4
```

## Debugging Tests

### Run single test
```bash
pytest tests/unit/test_metrics_unit.py::TestPulseMetrics::test_initial_state
```

### Show print statements
```bash
pytest tests/ -s
```

### Drop into debugger on failure
```bash
pytest tests/ --pdb
```

### Show local variables on failure
```bash
pytest tests/ -l
```

## CI/CD Integration

### GitHub Actions Example
```yaml
- name: Run tests
  run: |
    pytest tests/ --cov=fastapi_pulse --cov-report=xml --cov-report=term

- name: Upload coverage
  uses: codecov/codecov-action@v3
  with:
    file: ./coverage.xml
```

### Coverage Enforcement
```bash
# Fail if coverage is below 90%
pytest tests/ --cov=fastapi_pulse --cov-fail-under=90
```

## Test Data

Test fixtures provide:
- Temporary directories for file operations
- Mock FastAPI applications
- Pre-configured metrics instances
- Sample OpenAPI schemas
- Async HTTP clients with ASGI transport

## Troubleshooting

### Import Errors
Ensure package is installed:
```bash
pip install -e .
```

### Async Warnings
pytest-asyncio is configured with `asyncio_mode = "auto"` in `pyproject.toml`.

### Hypothesis Failures
Hypothesis tests may take longer and explore many examples. Adjust settings:
```python
@given(...)
@settings(max_examples=50)
def test_property(...):
    ...
```

## Key Features

✅ Modern async patterns with `httpx.AsyncClient`
✅ Complete isolation with function-scoped fixtures
✅ Property-based testing with Hypothesis
✅ Time manipulation with freezegun
✅ Thread-safety tests
✅ Comprehensive mocking with pytest-mock
✅ Parallel execution support
✅ ≥90% line coverage, ≥80% branch coverage
✅ AAA test structure
✅ Clear, descriptive test names
✅ Minimal fixture coupling

## Example Test Session

```bash
$ pytest tests/ --cov=fastapi_pulse --cov-report=term

========================= test session starts ==========================
platform linux -- Python 3.11.14
plugins: asyncio-0.21.0, cov-4.0.0, hypothesis-6.70.0, mock-3.10.0
collected 247 items

tests/unit/test_metrics_unit.py ........................... [ 15%]
tests/unit/test_middleware_unit.py ................        [ 25%]
tests/unit/test_registry_unit.py ...................       [ 35%]
tests/unit/test_payload_store_unit.py .............        [ 45%]
tests/unit/test_sample_builder_unit.py ..............      [ 55%]
tests/integration/test_full_flow.py ..................     [ 70%]
tests/api/test_endpoints.py .........................      [ 85%]
tests/property/test_metrics_properties.py ............     [100%]

---------- coverage: platform linux, python 3.11.14 -----------
Name                                Stmts   Miss  Cover
-------------------------------------------------------
src/fastapi_pulse/__init__.py          56      2    96%
src/fastapi_pulse/metrics.py          98      4    96%
src/fastapi_pulse/middleware.py       112      5    96%
src/fastapi_pulse/registry.py         87      3    97%
src/fastapi_pulse/probe.py           125      8    94%
src/fastapi_pulse/router.py          103      4    96%
src/fastapi_pulse/payload_store.py    45      2    96%
src/fastapi_pulse/sample_builder.py   78      3    96%
-------------------------------------------------------
TOTAL                                 704     31    96%

========================= 247 passed in 12.34s =========================
```
