# Testing

## Running the test suite

```bash
# From the repo root
pytest tests/ -v
```

With coverage:

```bash
pytest tests/ \
  --cov=firefly_reports \
  --cov-report=term-missing \
  --cov-fail-under=60
```

The CI pipeline runs tests on Python 3.11 and 3.12. Coverage must be ≥ 60%.

## Test file map

| Test file | What it covers |
|-----------|---------------|
| `tests/test_firefly_client.py` | `FireflyClient` — pagination, flattening, annual totals, deep-fetch |
| `tests/test_data_processor.py` | All 26 `build_*()` functions — correctness of aggregation logic |
| `tests/test_pdf_exporter.py` | Smoke tests: each `render_*_pdf()` produces a non-empty file |
| `tests/test_excel_exporter.py` | Smoke test: `render_all_xlsx_full()` produces a valid workbook |
| `tests/test_config.py` | Config file loading and missing-file behaviour |
| `tests/test_i18n.py` | Translation loading and fallback |
| `tests/test_chart_engine.py` | Chart generators return non-empty PNG buffers |
| `tests/conftest.py` | Shared fixtures: `FireflyClient` instance, sample transactions |

## Writing a client test

Use the `responses` library to mock HTTP calls:

```python
import responses as rsps_lib
from firefly_reports.firefly_client import FireflyClient

BASE = "https://firefly.test"

@pytest.fixture
def client():
    return FireflyClient(BASE, "test-token")

@rsps_lib.activate
def test_get_transactions_basic(client):
    rsps_lib.add(
        rsps_lib.GET,
        f"{BASE}/api/v1/transactions",
        json={
            "data": [{
                "id": "1",
                "attributes": {
                    "transactions": [
                        {"type": "deposit", "amount": "100.00", "date": "2025-01-15"},
                    ],
                },
            }],
            "meta": {"pagination": {"total_pages": 1}},
        },
        match=[rsps_lib.matchers.query_param_matcher(
            {"start": "2025-01-01", "end": "2025-12-31", "limit": 100, "page": 1}
        )],
    )
    result = client.get_transactions(date(2025, 1, 1), date(2025, 12, 31))
    assert len(result) == 1
    assert result[0]["type"] == "deposit"
```

## Writing a processor test

`data_processor.py` functions are pure — no mocks needed:

```python
from datetime import date
from decimal import Decimal
from firefly_reports.data_processor import build_cash_flow

SAMPLE = [
    {"type": "deposit",    "date": "2025-01-10", "amount": "1000.00",
     "category_name": "Salary", "budget_name": None, "tags": []},
    {"type": "withdrawal", "date": "2025-01-20", "amount": "200.00",
     "category_name": "Rent",   "budget_name": None, "tags": []},
]

def test_build_cash_flow_net():
    result = build_cash_flow(SAMPLE, date(2025,1,1), date(2025,12,31))
    assert result["total_in"]  == Decimal("1000.00")
    assert result["total_out"] == Decimal("200.00")
    assert result["net"]       == Decimal("800.00")
```

Note: always assert `Decimal` values against `Decimal` literals, not `float`.

## Pre-commit checks

The following run automatically on `git commit`:

```bash
ruff check firefly_reports/     # linting
ruff format --check firefly_reports/  # formatting
mypy firefly_reports/           # type checking
```

Run them manually at any time before committing.
