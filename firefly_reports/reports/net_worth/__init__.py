"""Report: net_worth."""

from typing import Any

from firefly_reports.reports.net_worth.build import from_source
from firefly_reports.reports.spec import (
    ReportContext,
    ReportData,
    ReportSpec,
)


def _filename(ctx: ReportContext) -> str:
    return f"net_worth_{ctx.period.tag}.pdf"


def _pdf(data: ReportData, path: str, legacy: bool = False) -> None:
    from firefly_reports.reports.net_worth.pdf import render_net_worth_pdf

    render_net_worth_pdf(data, path, legacy=legacy)


def _sheet(wb: Any, data: ReportData) -> None:
    from firefly_reports.reports.net_worth.xlsx import write_sheet

    write_sheet(wb, data)


SPEC = ReportSpec(
    key="net_worth",
    build=from_source,
    pdf=_pdf,
    filename=_filename,
    sheet=_sheet,
)
