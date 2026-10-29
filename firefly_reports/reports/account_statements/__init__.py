"""Report: account_statements."""

from typing import Any

from firefly_reports.reports.account_statements.build import from_source
from firefly_reports.reports.spec import (
    ReportContext,
    ReportData,
    ReportSpec,
)


def _filename(ctx: ReportContext) -> str:
    return f"account_statements_{ctx.period.tag}.pdf"


def _pdf(data: ReportData, path: str, legacy: bool = False) -> None:
    from firefly_reports.reports.account_statements.pdf import render_account_statements_pdf

    render_account_statements_pdf(data, path, legacy=legacy)


def _sheet(wb: Any, data: ReportData) -> None:
    from firefly_reports.reports.account_statements.xlsx import write_sheet

    write_sheet(wb, data)


SPEC = ReportSpec(
    key="account_statements",
    build=from_source,
    pdf=_pdf,
    filename=_filename,
    sheet=_sheet,
)
