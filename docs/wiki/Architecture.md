# Architecture

## Pipeline

The pipeline is strictly linear. Data flows in one direction and modules do not call each other sideways:

```
firefly_client.py  →  data_processor.py  →  pdf_exporter.py
                                          →  excel_exporter.py
```

`main.py` orchestrates the pipeline. `demo.py` is an alternative entry point that substitutes inline mock data for the API client.

## Module map

| Module | Responsibility |
|--------|---------------|
| `firefly_client.py` | HTTP client wrapping the Firefly III v1 REST API; handles pagination, flattening of split transactions, rate-limited deep-fetch for linked transactions |
| `data_processor.py` | 26 `build_*()` pure functions; each accepts flat transaction lists and returns a plain `dict` ready for rendering; zero I/O |
| `pdf_exporter.py` | 28 `render_*_pdf(data, path, legacy=False)` functions using ReportLab; colour constants and header/footer helpers at module level |
| `excel_exporter.py` | `render_all_xlsx_full(data_dict, path)` writes a workbook via openpyxl: 16 core report sheets plus Summary, with Account Statements contributing one sheet per asset account |
| `chart_engine.py` | Matplotlib (Agg) charts for the dashboard PDFs, sharing one visual identity (steel/slate palette, 200 dpi, locale-aware compact labels): donut, bar, line, area and income/expense combo |
| `config.py` | Loads `./firefly-reports.toml` using `tomllib`; returns an empty dict when absent |
| `i18n.py` | Translation singleton; call `i18n.load("en")` once at startup; use `i18n.t("key")` anywhere |
| `main.py` | CLI argument parsing, credential resolution, orchestration of all pipeline steps |
| `demo.py` | Standalone runner with hard-coded mock data; produces all 26 reports without a Firefly III instance |

## Dependency graph

```
main.py ──────────────────────────────────────────────────┐
  │                                                        │
  ├── firefly_client.py                                    │
  │     (no project deps)                                  │
  │                                                        │
  ├── data_processor.py                                    │
  │     (no project deps)                                  ▼
  │                                              config.py, i18n.py
  ├── pdf_exporter.py
  │     └── chart_engine.py
  │
  └── excel_exporter.py
        (no project deps)
```

## Data contract

`firefly_client.py` returns a flat list of dicts, one dict per transaction split. The key fields used by `data_processor.py` are:

| Field | Type | Description |
|-------|------|-------------|
| `type` | str | `"deposit"`, `"withdrawal"`, `"transfer"`, `"opening balance"` |
| `amount` | str | Decimal string, always positive (e.g. `"123.45"`) |
| `date` | str | ISO date string (e.g. `"2025-03-15T00:00:00+00:00"`) |
| `category_name` | str\|None | Category assigned in Firefly III |
| `budget_name` | str\|None | Budget assigned to the transaction |
| `source_name` | str | Name of the source account or payer |
| `destination_name` | str | Name of the destination account or payee |
| `tags` | list[str] | Tags assigned to the transaction |
| `group_id` | str | ID of the transaction group (splits share a group) |
| `reconciled` | bool | Whether the transaction is reconciled |

All monetary arithmetic uses `Decimal` with 2 decimal places via `_d()` in `data_processor.py`. `firefly_client.py` uses the equivalent `_dec()` helper for aggregation methods.

## Adding a report

See [[Adding-a-New-Report|Adding a New Report]].
