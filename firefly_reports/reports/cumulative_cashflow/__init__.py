"""Report: cumulative_cashflow."""

from typing import Any

from firefly_reports.reports.cumulative_cashflow.build import from_source
from firefly_reports.reports.spec import (
    ReportContext,
    ReportData,
    ReportSpec,
)


def _filename(ctx: ReportContext) -> str:
    return f"cumulative_cashflow_{ctx.period.tag}.pdf"


def _pdf(data: ReportData, path: str, legacy: bool = False) -> None:
    from firefly_reports.reports.cumulative_cashflow.pdf import render_cumulative_cashflow_pdf

    render_cumulative_cashflow_pdf(data, path, legacy=legacy)


def _sheet(wb: Any, data: ReportData) -> None:
    from firefly_reports.reports.cumulative_cashflow.xlsx import write_sheet

    write_sheet(wb, data)


SPEC = ReportSpec(
    key="cumulative_cashflow",
    build=from_source,
    pdf=_pdf,
    filename=_filename,
    sheet=_sheet,
)
