# Adding a New Report

This page is a step-by-step guide for developers who want to add a report to firefly-reports. A report
is one package under `firefly_reports/reports/` plus one line in the registry; the pipeline, the CLI,
the demo and the library facade pick it up from there. The page follows a worked example, a small
`goal_deadlines` report (savings goals whose target date falls inside the period), modelled on the
existing `reports/savings_goals/` package. Read [[Architecture]] first for the registry and the
layering rules.

## What a report package contains

| File | Content | Rules |
|---|---|---|
| `__init__.py` | The `SPEC` (`ReportSpec`) and small wrappers that import the renderers lazily | No logic |
| `build.py` | A pure `build_<key>()` returning a plain dict, plus the `from_source(src, ctx, built)` adapter | No I/O; money is `Decimal` via `_d()`; no `render`, `cli`, `os`, `pathlib`, `io`, `reportlab`, `openpyxl`, `matplotlib` or `requests` imports (enforced by `tests/test_architecture.py`) |
| `pdf.py` | `render_<key>_pdf(data, path, legacy=False)` | ReportLab, using the shared blocks in `render/pdf/` |
| `xlsx.py` | `write_sheet(wb, data)`, only if the report has an Excel sheet | openpyxl, using `render/xlsx/` |

Every user-facing string comes from the translation files through `i18n.t()`.

## Step 1: create the package

Copy a small package such as `reports/savings_goals/` and rename it. For the example, create
`firefly_reports/reports/goal_deadlines/`.

### `build.py`

The builder takes plain data and returns a plain dict. The adapter reads what it needs from
`SourceData` (everything fetched for the run) and from the `ReportContext` (period and options).
`built` holds the data of the reports built earlier in the run; use it only for keys you list in
`depends_on`.

```python
"""Builder of the goal_deadlines report (pure: no I/O, Decimal money)."""

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any

from firefly_reports.reports._money import _d
from firefly_reports.reports.spec import ReportContext, ReportData, SourceData


def build_goal_deadlines(
    piggy_banks: list[dict[str, Any]],
    start: date,
    end: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Savings goals whose target date falls inside the period, earliest first."""
    goals = []
    for pb in piggy_banks:
        attrs = pb.get("attributes", pb)
        target_date = (attrs.get("target_date") or "")[:10]
        if not target_date or not start.isoformat() <= target_date <= end.isoformat():
            continue
        target = _d(attrs.get("target_amount", 0))
        current = _d(attrs.get("current_amount", 0))
        goals.append(
            {
                "name": attrs.get("name", ""),
                "target_date": target_date,
                "missing": max(target - current, Decimal("0")),
            }
        )
    goals.sort(key=lambda g: (g["target_date"], g["name"]))
    return {
        "owner": owner_name,
        "period_start": start,
        "period_end": end,
        "currency": currency_symbol,
        "goals": goals,
        "total_missing": sum((g["missing"] for g in goals), Decimal("0")),
    }


def from_source(src: SourceData, ctx: ReportContext, built: Mapping[str, ReportData]) -> ReportData:
    """Registry adapter: build this report from the fetched data and the run context."""
    p, o = ctx.period, ctx.options
    return build_goal_deadlines(src.piggy_banks, p.start, p.end, o.owner, o.currency)
```

If the report needs data that `SourceData` does not have yet, the fetch step
(`reports/fetch.py`), `SourceData` (`reports/spec.py`), the `FireflySource` protocol, `FireflyClient`
and `DemoClient` all have to grow; that is a larger change than a new report.

### `pdf.py`

```python
"""PDF renderer of the goal_deadlines report."""

from typing import Any

from reportlab.lib.units import cm
from reportlab.platypus import Paragraph

from firefly_reports.i18n import t
from firefly_reports.render.fmt import fmt_num, period_str
from firefly_reports.render.pdf.page import make_doc, page_decorator, title_block
from firefly_reports.render.pdf.styles import classic_styles
from firefly_reports.render.pdf.tables import accounting_table


def render_goal_deadlines_pdf(data: dict[str, Any], path: str, legacy: bool = False) -> None:
    st = classic_styles()
    title = t("titles.goal_deadlines")
    period = period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    doc = make_doc(path, page_decorator(data["owner"], title, period))
    story: list[Any] = title_block(title, data["owner"], period, None, st)

    rows = [[Paragraph(t("common.objective"), st["col_header_l"]), "", ""]]
    for g in data["goals"]:
        rows.append(
            [
                Paragraph(g["name"], st["cell_l"]),
                Paragraph(g["target_date"], st["cell_r"]),
                Paragraph(fmt_num(g["missing"], sym=sym), st["cell_r"]),
            ]
        )
    rows.append(
        [
            Paragraph(t("common.total"), st["total_l"]),
            "",
            Paragraph(fmt_num(data["total_missing"], show_sym=True, sym=sym), st["total_r"]),
        ]
    )
    story.append(accounting_table(rows, [9 * cm, 3 * cm, 4 * cm], total_rows=[len(rows) - 1]))
    doc.build(story)
```

The page header and footer print the generation date through `clock.now()`, so tests can freeze it.
Single-letter layout names such as `W`, `H` or `COL_W` are allowed in `reports/*/pdf.py` (ruff `N806`
is ignored there).

### `xlsx.py`

```python
"""Excel sheet of the goal_deadlines report."""

from typing import Any

from openpyxl import Workbook

from firefly_reports.i18n import t
from firefly_reports.render.fmt import period_str
from firefly_reports.render.xlsx.layout import data_row, header_row, title_block, to_number


def write_sheet(wb: Workbook, data: dict[str, Any]) -> None:
    ws = wb.create_sheet(t("excel.sheet_goal_deadlines"))
    period = period_str(data["period_start"], data["period_end"])
    row = title_block(ws, t("titles.goal_deadlines"), data["owner"], period)
    row = header_row(
        ws, row, [t("common.objective"), "", data["currency"]], col_widths=[32, 14, 16]
    )
    for g in data["goals"]:
        row = data_row(ws, row, [g["name"], g["target_date"], to_number(g["missing"])])
    data_row(ws, row, [t("common.total"), "", to_number(data["total_missing"])], is_total=True)
```

Skip this file if the report has no sheet.

### `__init__.py`

The renderers are imported inside the wrappers, so building a report never loads ReportLab or
openpyxl. Set only the `ReportSpec` fields you need:

- `applies=` to build the report only in some runs, for example year mode only
  (`ctx.period.year_mode`) or not in legacy mode (`not ctx.options.legacy`);
- `pdf_enabled=` to skip the PDF once the data is known, as here when no goal is due;
- `depends_on=` with the keys of the reports whose data you read from `built`.

```python
"""Report: goal_deadlines."""

from typing import Any

from firefly_reports.reports.goal_deadlines.build import from_source
from firefly_reports.reports.spec import ReportContext, ReportData, ReportSpec


def _filename(ctx: ReportContext) -> str:
    return f"goal_deadlines_{ctx.period.tag}.pdf"


def _pdf(data: ReportData, path: str, legacy: bool = False) -> None:
    from firefly_reports.reports.goal_deadlines.pdf import render_goal_deadlines_pdf

    render_goal_deadlines_pdf(data, path, legacy=legacy)


def _sheet(wb: Any, data: ReportData) -> None:
    from firefly_reports.reports.goal_deadlines.xlsx import write_sheet

    write_sheet(wb, data)


def _pdf_enabled(ctx: ReportContext, data: ReportData) -> bool:
    return bool(data["goals"])


SPEC = ReportSpec(
    key="goal_deadlines",
    build=from_source,
    pdf=_pdf,
    filename=_filename,
    sheet=_sheet,
    pdf_enabled=_pdf_enabled,
)
```

`ctx.period.tag` expands to `<start>__<end>`, the suffix every report file uses. The output file name
is part of the stable command-line contract: choose it once.

## Step 2: register the report

In `firefly_reports/reports/registry.py`:

1. Add the package to the explicit import list at the top (`from firefly_reports.reports import (...)`).
   Dynamic imports are forbidden because the Windows executable is built with PyInstaller.
2. Add `goal_deadlines.SPEC` to `REPORTS`. The position decides the sheet order in the workbook (reports
   with a sheet come first, in sheet order), the order of the builders and of the PDFs. A report must come
   after every report it `depends_on`; the two dashboard views stay last.

`tests/test_architecture.py::test_registry_imports_every_report_package` fails if a package under
`reports/` is missing from `REPORTS`.

## Step 3: add the strings

Add every new key to **both** `firefly_reports/translations/en.toml` and `firefly_reports/translations/it.toml`.
For the example that means `goal_deadlines` in the `[titles]` section and `sheet_goal_deadlines` in the
`[excel]` section. A missing key does not crash: `t()` falls back to English and then to the key itself,
so a forgotten translation shows up as a raw key in the output.

## Step 4: try it on the demo data

`firefly-reports demo` runs the real pipeline on the built-in sample data, so the new report appears
there without further wiring:

```bash
python -m firefly_reports demo --out "$TMPDIR/demo"
python -m firefly_reports demo --out "$TMPDIR/demo-it" --lang it
```

Check that the PDF is listed with `OK`, open it, and open the workbook. If the report needs a data shape
the sample data lacks, extend `firefly_reports/demo/data.py` (and `demo/client.py` if a new client call
is involved).

## Step 5: tests and goldens

- Add unit tests for the builder in `tests/reports/test_<key>.py`. Builders are pure, so a test only
  needs plain dicts; assert `Decimal` values against `Decimal` literals. Add a render smoke test for the
  PDF (and the sheet) as well; the existing per-report render tests live in `tests/test_pdf_exporter.py`
  and `tests/test_excel_exporter.py`.
- Update the tests that pin the registry and the file set on purpose:
  - `tests/reports/test_registry.py` (number of reports, sheet order, total number of entries);
  - `tests/test_api.py` (number of entries returned by `available_reports()`, files of a demo run);
  - `tests/cli/test_demo.py` (number of PDFs of a demo run);
  - `tests/reports/test_pipeline.py` (planned outputs in year mode);
  - `tests/test_golden_pipeline.py` (number of PDFs in the full-year scenario).
- Add the report to the golden harness, `tests/golden/harness.py`: its builder call in
  `build_demo_suite()` and its PDF in `DEMO_PDFS`, so its data and its PDF are pinned.
- Regenerate the goldens and review the diff before committing:

  ```bash
  FIREFLY_UPDATE_GOLDEN=1 python -m pytest -m golden
  git diff --stat tests/golden/
  ```

  Name the reason for the golden change in the commit message. Goldens depend on the locked dependency
  versions: regenerate them in a venv built from `firefly_reports/requirements.txt` (see [[Testing]]).
- The Windows executable job in `.github/workflows/ci.yml` checks the number of PDFs written by the demo;
  update it too.
- Run the full local gate from [[Contributing]].

## Step 6: user documentation

- Add the report to [[Reports-Reference|Reports Reference]] (name, description, file name, when it is
  generated) and to the report table in `README.md`.
- Add an entry to `CHANGELOG.md`.
