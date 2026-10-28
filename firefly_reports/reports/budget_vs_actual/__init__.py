"""Report: budget_vs_actual."""

from typing import Any

from firefly_reports.reports.budget_vs_actual.build import from_source
from firefly_reports.reports.spec import (
    ReportContext,
    ReportData,
    ReportSpec,
)


def _filename(ctx: ReportContext) -> str:
    return f"budget_vs_actual_{ctx.period.tag}.pdf"


def _pdf(data: ReportData, path: str, legacy: bool = False) -> None:
    from firefly_reports.reports.budget_vs_actual.pdf import render_budget_vs_actual_pdf

    render_budget_vs_actual_pdf(data, path, legacy=legacy)


def _sheet(wb: Any, data: ReportData) -> None:
    from firefly_reports.reports.budget_vs_actual.xlsx import write_sheet

    write_sheet(wb, data)


SPEC = ReportSpec(
    key="budget_vs_actual",
    build=from_source,
    pdf=_pdf,
    filename=_filename,
    sheet=_sheet,
)
