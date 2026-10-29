"""Report: category_ledger."""

from firefly_reports.reports.category_ledger.build import from_source
from firefly_reports.reports.spec import (
    ReportContext,
    ReportData,
    ReportSpec,
)


def _filename(ctx: ReportContext) -> str:
    return f"ledger_category_{ctx.period.tag}.pdf"


def _pdf(data: ReportData, path: str, legacy: bool = False) -> None:
    from firefly_reports.reports.category_ledger.pdf import render_category_ledger_pdf

    render_category_ledger_pdf(data, path, legacy=legacy)


def _applies(ctx: ReportContext) -> bool:
    return not ctx.options.legacy


SPEC = ReportSpec(
    key="category_ledger",
    build=from_source,
    pdf=_pdf,
    filename=_filename,
    applies=_applies,
)
