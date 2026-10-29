# Testing

This page explains how the firefly-reports test suite is organised and how to run it: the local gate,
the offline rule, the golden snapshot tests, the A/B harness used while refactoring output code, and
the ledger and packaging tests. It is for developers changing the code; the commands assume a source
checkout with the development venv described in [[Contributing]].

## Running the tests

From the repository root, with the dev tools called through the venv's Python (`python -m <tool>`
keeps working even if the venv was moved and its console scripts have stale shebangs):

```bash
python -m pytest tests -q
```

With the coverage threshold enforced by CI (90%):

```bash
python -m pytest tests -q --cov=firefly_reports --cov-fail-under=90
```

No `PYTHONPATH` is needed: `pyproject.toml` sets `pythonpath = ["."]` and `testpaths = ["tests"]`.
`firefly_reports/demo/data.py` (the sample data) is excluded from coverage. CI runs the suite on
Python 3.11 and 3.12 with `beancount` installed.

Useful selections:

```bash
python -m pytest -m golden                  # only the golden snapshot tests
python -m pytest tests/test_architecture.py # only the layering rules
python -m pytest tests/cli -q               # only the command-line tests
```

## The offline rule

Tests never talk to a Firefly III instance:

- report and CLI tests use `DemoClient` (`firefly_reports/demo/client.py`), an offline implementation of
  the `FireflySource` protocol that serves the sample data;
- client and ledger tests mock HTTP with the `responses` library;
- an autouse fixture in `tests/conftest.py` makes `socket.connect()` raise, so a test that escapes its
  mock (for example by picking up a developer's `.env`) fails instead of reaching a real server.

`tests/conftest.py` also loads the English translations (`i18n.load("en")`) and provides the shared
sample data fixtures (`txn_2025`, `accounts`, `budgets`, `bills`, `piggy_banks`, ...).

## Test map

| Location | What it covers |
|---|---|
| `tests/test_architecture.py` | Layering rules checked on the source with `ast`: pure builders, report-agnostic `render/`, independent `ledger/`, where `requests`, `print`, `input` and `sys.exit` may appear, no dynamic imports, every report package registered (see [[Architecture]]) |
| `tests/reports/` | Registry order and dependencies, fetch step, options and periods, pipeline planning and writing, workbook assembly |
| `tests/test_data_processor.py` | The builders of every report (name kept from 1.x) |
| `tests/test_pdf_exporter.py`, `tests/test_excel_exporter.py` | Render smoke tests for every PDF and the workbook (names kept from 1.x) |
| `tests/test_chart_engine.py`, `tests/test_render_fmt.py` | Charts and number/date formatting in `render/` |
| `tests/cli/` | Parser, subcommands, settings precedence (`test_settings.py`), `[export]` settings, `init`, `demo`, the deprecated 1.x form, exit codes |
| `tests/test_config.py` | Loading `firefly-reports.toml` and the unknown-key warnings |
| `tests/test_api.py`, `tests/test_public_api.py` | The library facade: behaviour with `DemoClient`, the exported names, the pinned `generate_reports` signature, cheap package import, `py.typed`, version |
| `tests/test_i18n.py`, `tests/test_clock.py`, `tests/test_errors.py` | Translator, clock seam, translated errors |
| `tests/tlstrust/`, `tests/test_tls_client.py`, `tests/test_tls_loopback.py`, `tests/test_tls_binding_guard.py` | The TLS trust lists (hashes re-derived offline from the certificates in `tests/fixtures/`), the check in `FireflyClient` (block, warn, unchecked, behind an HTTPS proxy) and the guard that fails when the chain stops being readable. They need the `openssl` command |
| `tests/test_firefly_client.py`, `tests/test_demo_client.py` | The REST client (pagination, flattening, deep fetch) and the demo client |
| `tests/test_ledger*.py` | The Beancount export (see [Ledger tests](#ledger-tests)) |
| `tests/test_golden_*.py`, `tests/test_cli_help.py` | Golden snapshots (see below) |
| `tests/test_packaging.py` | Wheel contents, only with `FIREFLY_BUILD_WHEEL=1` |

## Golden tests

Golden tests (marker `golden`) compare the output of the current code with snapshots committed under
`tests/golden/`. They pin:

| Snapshot | Test | Content |
|---|---|---|
| `golden/data/` | `tests/test_golden_reports.py` | The data returned by every builder, as tagged JSON (`Decimal`, floats and dates keep their type visible) |
| `golden/pdf/` | `tests/test_golden_reports.py` | What each PDF asks ReportLab to draw (flowable tree, strings, page count); stored as a digest for Italian |
| `golden/xlsx/` | `tests/test_golden_reports.py` | The workbook cells read back |
| `golden/pipeline/` | `tests/test_golden_pipeline.py` | A full CLI `report` run on `DemoClient`: exit code, file list, normalised stdout, digests (scenarios: full year with tags, links and all tags; date range in legacy mode; full year in Italian) |
| `golden/cli/` | `tests/test_cli_help.py` | The `--help` text of the root parser and of each subcommand |
| `golden/ledger/` | `tests/test_golden_ledger_cli.py` | The Beancount files of `export beancount` for both layouts |

The import paths the goldens need are collected in `tests/golden/harness.py`; it builds the demo suite
with the clock frozen (`clock.frozen`) so the "generated on" dates do not change.

When a change of output is intended, regenerate the snapshots on purpose, review the diff and name the
reason in the commit message:

```bash
FIREFLY_UPDATE_GOLDEN=1 python -m pytest -m golden
git diff --stat tests/golden/
```

The snapshots depend on the versions of ReportLab, openpyxl and matplotlib. Generate them in a venv
built from the lock file (`firefly_reports/requirements.txt`, Python 3.11), as in [[Contributing]], or
they will not match CI.

## A/B harness for output refactors

`tools/ab_snapshot.py` is a local check, not a test: it proves that a refactor leaves the PDFs
byte-identical. It renders the demo suite (English and Italian) and the pipeline scenarios offline with
ReportLab's `invariant` mode and a frozen clock, and records a SHA-256 per PDF (and of the workbook
snapshot).

```bash
python tools/ab_snapshot.py write "$TMPDIR/ab/baseline"    # before the change
python tools/ab_snapshot.py compare "$TMPDIR/ab/baseline"  # after the change
```

PDF bytes are only reproducible inside one environment (same Python and library versions), so the
baseline and the comparison must run in the same venv. Use it only while refactoring output code.

## Ledger tests

The ledger tests (`tests/test_ledger*.py`) are offline: they use the API-shaped payload in
`tests/fixtures/firefly_transactions.json` (plus `firefly_account_types.json`), served through the
`responses` mock or flattened by the real `FireflyClient`. When you add a transaction shape, extend the
fixture (keep the ids unique) and the expected counts.

Tests that call `bean-check` are skipped when it is not installed. CI installs it; install it locally so
they run:

```bash
python -m pip install beancount
python -m pytest tests/test_ledger.py tests/test_ledger_cli.py tests/test_ledger_layout.py -q
```

The invariants to keep: every transaction balances per currency, output is byte-identical across runs
and input orders, and the generated files pass `bean-check` in both `en` and `it`. See
[[Ledger-Architecture|Ledger Architecture]].

## Writing tests

Builders are pure functions, so a builder test needs no mock:

```python
from datetime import date
from decimal import Decimal

from firefly_reports.reports.cash_flow.build import build_cash_flow


def test_build_cash_flow_net():
    txns = [
        {"type": "deposit", "date": "2025-01-10", "amount": "1000.00", "category_name": "Salary"},
        {"type": "withdrawal", "date": "2025-01-20", "amount": "200.00", "category_name": "Rent"},
    ]
    result = build_cash_flow(txns, date(2025, 1, 1), date(2025, 12, 31))
    assert result["total_in"] == Decimal("1000.00")
    assert result["total_out"] == Decimal("200.00")
    assert result["net"] == Decimal("800.00")
```

Always assert money against `Decimal` literals, not floats.

A pipeline or facade test runs offline on `DemoClient`:

```python
from firefly_reports import Period, ReportOptions, generate_reports
from firefly_reports.demo.client import DemoClient


def test_demo_run_writes_the_workbook(tmp_path):
    result = generate_reports(
        DemoClient(), Period.for_year(2025), ReportOptions(pdf=False), tmp_path
    )
    assert result.ok
    assert [f.path.name for f in result.files] == ["firefly_reports_2025-01-01__2025-12-31.xlsx"]
```

A client test mocks HTTP with `responses`:

```python
from datetime import date

import responses

from firefly_reports.firefly_client import FireflyClient

BASE = "https://firefly.test"


@responses.activate
def test_get_transactions_basic():
    responses.add(
        responses.GET,
        f"{BASE}/api/v1/transactions",
        json={
            "data": [
                {
                    "id": "1",
                    "attributes": {
                        "transactions": [
                            {"type": "deposit", "amount": "100.00", "date": "2025-01-15"}
                        ]
                    },
                }
            ],
            "meta": {"pagination": {"total_pages": 1}},
        },
    )
    result = FireflyClient(BASE, "test-token").get_transactions(
        date(2025, 1, 1), date(2025, 12, 31)
    )
    assert len(result) == 1
    assert result[0]["type"] == "deposit"
```

Code that depends on the current date should read it through `firefly_reports.clock`, and tests can
freeze it with `clock.frozen(datetime(...))`.
