"""Report: expense_trend."""

from typing import Any

from firefly_reports.reports.expense_trend.build import from_source
from firefly_reports.reports.spec import (
    ReportContext,
    ReportData,
    ReportSpec,
)


def _filename(ctx: ReportContext) -> str:
    return f"expense_trend_{ctx.period.tag}.pdf"


def _pdf(data: ReportData, path: str, legacy: bool = False) -> None:
    from firefly_reports.reports.expense_trend.pdf import render_expense_trend_pdf

    render_expense_trend_pdf(data, path, legacy=legacy)


def _sheet(wb: Any, data: ReportData) -> None:
    from firefly_reports.reports.expense_trend.xlsx import write_sheet

    write_sheet(wb, data)


SPEC = ReportSpec(
    key="expense_trend",
    build=from_source,
    pdf=_pdf,
    filename=_filename,
    sheet=_sheet,
)
