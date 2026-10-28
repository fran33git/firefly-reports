"""Report: all_tags."""

from firefly_reports.reports.all_tags.build import from_source
from firefly_reports.reports.spec import (
    ReportContext,
    ReportData,
    ReportSpec,
)


def _filename(ctx: ReportContext) -> str:
    return f"ledger_all_tags_{ctx.period.tag}.pdf"


def _pdf(data: ReportData, path: str, legacy: bool = False) -> None:
    from firefly_reports.reports.all_tags.pdf import render_all_tags_pdf

    render_all_tags_pdf(data, path, legacy=legacy)


def _applies(ctx: ReportContext) -> bool:
    return ctx.options.all_tags and not ctx.options.legacy


def _pdf_enabled(ctx: ReportContext, data: ReportData) -> bool:
    return bool(data)


SPEC = ReportSpec(
    key="all_tags",
    build=from_source,
    pdf=_pdf,
    filename=_filename,
    applies=_applies,
    pdf_enabled=_pdf_enabled,
)
