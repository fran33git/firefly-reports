"""Report: bills."""

from typing import Any

from firefly_reports.reports.bills.build import from_source
from firefly_reports.reports.spec import (
    ReportContext,
    ReportData,
    ReportSpec,
)


def _filename(ctx: ReportContext) -> str:
    return f"bills_{ctx.period.tag}.pdf"


def _pdf(data: ReportData, path: str, legacy: bool = False) -> None:
    from firefly_reports.reports.bills.pdf import render_bills_pdf

    render_bills_pdf(data, path, legacy=legacy)


def _sheet(wb: Any, data: ReportData) -> None:
    from firefly_reports.reports.bills.xlsx import write_sheet

    write_sheet(wb, data)


SPEC = ReportSpec(
    key="bills",
    build=from_source,
    pdf=_pdf,
    filename=_filename,
    sheet=_sheet,
)
