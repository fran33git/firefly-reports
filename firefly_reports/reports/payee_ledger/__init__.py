"""Report: payee_ledger."""

from firefly_reports.reports.payee_ledger.build import from_source
from firefly_reports.reports.spec import (
    ReportContext,
    ReportData,
    ReportSpec,
)


def _filename(ctx: ReportContext) -> str:
    return f"ledger_payee_{ctx.period.tag}.pdf"


def _pdf(data: ReportData, path: str, legacy: bool = False) -> None:
    from firefly_reports.reports.payee_ledger.pdf import render_payee_ledger_pdf

    render_payee_ledger_pdf(data, path, legacy=legacy)


def _applies(ctx: ReportContext) -> bool:
    return not ctx.options.legacy


SPEC = ReportSpec(
    key="payee_ledger",
    build=from_source,
    pdf=_pdf,
    filename=_filename,
    applies=_applies,
)
