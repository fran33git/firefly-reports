"""Report: savings_goals."""

from typing import Any

from firefly_reports.reports.savings_goals.build import from_source
from firefly_reports.reports.spec import (
    ReportContext,
    ReportData,
    ReportSpec,
)


def _filename(ctx: ReportContext) -> str:
    return f"savings_goals_{ctx.period.tag}.pdf"


def _pdf(data: ReportData, path: str, legacy: bool = False) -> None:
    from firefly_reports.reports.savings_goals.pdf import render_savings_goals_pdf

    render_savings_goals_pdf(data, path, legacy=legacy)


def _sheet(wb: Any, data: ReportData) -> None:
    from firefly_reports.reports.savings_goals.xlsx import write_sheet

    write_sheet(wb, data)


SPEC = ReportSpec(
    key="savings_goals",
    build=from_source,
    pdf=_pdf,
    filename=_filename,
    sheet=_sheet,
)
