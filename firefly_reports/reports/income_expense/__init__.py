"""Report: income_expense."""

from typing import Any

from firefly_reports.reports.income_expense.build import from_source
from firefly_reports.reports.spec import (
    ReportContext,
    ReportData,
    ReportSpec,
)


def _filename(ctx: ReportContext) -> str:
    return f"income_expense_{ctx.period.tag}.pdf"


def _pdf(data: ReportData, path: str, legacy: bool = False) -> None:
    from firefly_reports.reports.income_expense.pdf import render_income_expense_pdf

    render_income_expense_pdf(data, path, legacy=legacy)


def _sheet(wb: Any, data: ReportData) -> None:
    from firefly_reports.reports.income_expense.xlsx import write_sheet

    write_sheet(wb, data)


SPEC = ReportSpec(
    key="income_expense",
    build=from_source,
    pdf=_pdf,
    filename=_filename,
    sheet=_sheet,
)
