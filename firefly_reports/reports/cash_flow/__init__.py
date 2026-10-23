"""Report: cash_flow."""

from typing import Any

from firefly_reports.reports.cash_flow.build import from_source
from firefly_reports.reports.spec import (
    ReportContext,
    ReportData,
    ReportSpec,
)


def _filename(ctx: ReportContext) -> str:
    return f"cash_flow_{ctx.period.tag}.pdf"


def _pdf(data: ReportData, path: str, legacy: bool = False) -> None:
    from firefly_reports.reports.cash_flow.pdf import render_cash_flow_pdf

    render_cash_flow_pdf(data, path, legacy=legacy)


def _sheet(wb: Any, data: ReportData) -> None:
    from firefly_reports.reports.cash_flow.xlsx import write_sheet

    write_sheet(wb, data)


SPEC = ReportSpec(
    key="cash_flow",
    build=from_source,
    pdf=_pdf,
    filename=_filename,
    sheet=_sheet,
)
