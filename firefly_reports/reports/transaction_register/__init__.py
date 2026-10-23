"""Report: transaction_register."""

from typing import Any

from firefly_reports.reports.spec import (
    ReportContext,
    ReportData,
    ReportSpec,
)
from firefly_reports.reports.transaction_register.build import from_source


def _filename(ctx: ReportContext) -> str:
    return f"transaction_register_{ctx.period.tag}.pdf"


def _pdf(data: ReportData, path: str, legacy: bool = False) -> None:
    from firefly_reports.reports.transaction_register.pdf import render_transaction_register_pdf

    render_transaction_register_pdf(data, path, legacy=legacy)


def _sheet(wb: Any, data: ReportData) -> None:
    from firefly_reports.reports.transaction_register.xlsx import write_sheet

    write_sheet(wb, data)


SPEC = ReportSpec(
    key="transaction_register",
    build=from_source,
    pdf=_pdf,
    filename=_filename,
    sheet=_sheet,
)
