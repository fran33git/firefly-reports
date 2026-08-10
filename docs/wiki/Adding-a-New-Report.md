# Adding a New Report

Follow this 7-step checklist. Each step is independent and testable.

---

## Step 1: Data processor function

Add `build_<name>()` to `firefly_reports/data_processor.py`:

```python
def build_<name>(
    transactions: list[dict[str, Any]],
    start: date,
    end: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Return <one-line description of what this report shows>."""
    # ... aggregation logic using _d() for all monetary values ...
    return {
        "owner": owner_name,
        "period_start": start,
        "period_end": end,
        "currency": currency_symbol,
        # ... report-specific keys ...
    }
```

Rules:
- Accept only plain Python types as arguments (no I/O, no HTTP calls).
- Return a plain `dict[str, Any]` — never a class or dataclass.
- Use `_d(value)` for every monetary value (returns `Decimal` with 2dp).
- Skip transactions with `type == "opening balance"`.

---

## Step 2: Unit test

Add a test to `tests/test_data_processor.py`:

```python
def test_build_<name>_basic():
    txns = [
        {"type": "withdrawal", "date": "2025-03-01", "amount": "100.00",
         "category_name": "Food", "budget_name": None, "tags": [],
         "source_name": "Bank", "destination_name": "Shop",
         "group_id": "1", "reconciled": False},
    ]
    result = build_<name>(txns, date(2025, 1, 1), date(2025, 12, 31))
    assert result["period_start"] == date(2025, 1, 1)
    # assert the key fields your function returns
```

Run: `pytest tests/test_data_processor.py -v -k "test_build_<name>"` → must pass.

---

## Step 3: PDF renderer

Add `render_<name>_pdf(data, path, legacy=False)` to `firefly_reports/pdf_exporter.py`. Follow the pattern of an existing renderer:

```python
def render_<name>_pdf(data: dict[str, Any], path: str, legacy: bool = False) -> None:
    """Render the <Name> report to a PDF at the given path."""
    doc = SimpleDocTemplate(
        path,
        pagesize=landscape(A4),
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )
    story: list = []
    story.extend(_make_header_footer(data, "<Report Title>"))
    # ... build story elements ...
    doc.build(story)
```

---

## Step 4: Smoke test

Add a smoke test to `tests/test_pdf_exporter.py`:

```python
def test_render_<name>_pdf(tmp_path):
    data = build_<name>(SAMPLE_TRANSACTIONS, date(2025,1,1), date(2025,12,31))
    out = str(tmp_path / "<name>.pdf")
    render_<name>_pdf(data, out)
    assert Path(out).exists()
    assert Path(out).stat().st_size > 1000
```

Run: `pytest tests/test_pdf_exporter.py -v -k "test_render_<name>"` → must pass.

---

## Step 5: Excel sheet

Add a sheet to `render_all_xlsx_full()` in `firefly_reports/excel_exporter.py`:

```python
ws = wb.create_sheet("<Name>")
ws.append(["Date", "Description", "Amount"])  # header row
for row in data["<name>"]["rows"]:
    ws.append([row["date"], row["description"], float(row["amount"])])
```

---

## Step 6: Wire into `demo.py`

Add mock data and a call in `firefly_reports/demo.py`:

```python
<name>_data = build_<name>(TXN_2025, START, END, OWNER, SYM)
_run("render_<name>_pdf", render_<name>_pdf, <name>_data, out_dir / "<name>_{period_tag}.pdf")
```

Run `python -m firefly_reports.demo` and confirm the PDF is created and non-empty.

---

## Step 7: Wire into `main.py` and update docs

In `firefly_reports/main.py`:

1. Add `build_<name>` to the `from firefly_reports.data_processor import (...)` block.
2. Add `render_<name>_pdf` to the `from firefly_reports.pdf_exporter import (...)` block.
3. After the processing block, add: `<name>_data = build_<name>(transactions, start, end, owner, currency)`
4. Add to the `jobs` list: `(render_<name>_pdf, <name>_data, f"<name>_{period_tag}.pdf")`

Then:
- Add the report to the table in `README.md`.
- Add an entry to the `[Unreleased]` section of `CHANGELOG.md`.
- Update the [[Reports-Reference|Reports Reference]] wiki page.

---

## Steps

1. Write the complete file to `docs/wiki/Adding-a-New-Report.md`.
2. Verify it exists.
3. Commit:
   ```bash
   git add docs/wiki/Adding-a-New-Report.md
   git commit -m "docs(wiki): add Adding a New Report page"
   ```
