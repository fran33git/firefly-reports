"""Report: linkage_audit."""

from firefly_reports.reports.linkage_audit.build import from_source
from firefly_reports.reports.spec import (
    ReportContext,
    ReportData,
    ReportSpec,
)


def _filename(ctx: ReportContext) -> str:
    return f"audit_linkage_{ctx.period.tag}.pdf"


def _pdf(data: ReportData, path: str, legacy: bool = False) -> None:
    from firefly_reports.reports.linkage_audit.pdf import render_linkage_audit_pdf

    render_linkage_audit_pdf(data, path, legacy=legacy)


def _applies(ctx: ReportContext) -> bool:
    return not ctx.options.legacy


def _pdf_enabled(ctx: ReportContext, data: ReportData) -> bool:
    return bool(data["groups"]) or ctx.options.fetch_links


SPEC = ReportSpec(
    key="linkage_audit",
    build=from_source,
    pdf=_pdf,
    filename=_filename,
    applies=_applies,
    pdf_enabled=_pdf_enabled,
)
