"""Build every applicable report, plan the output files and write them."""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from firefly_reports.reports import events
from firefly_reports.reports.events import Progress
from firefly_reports.reports.registry import REPORTS
from firefly_reports.reports.spec import ReportContext, ReportData, ReportSpec, SourceData
from firefly_reports.reports.workbook import write_workbook

log = logging.getLogger(__name__)

WORKBOOK = "workbook"


@dataclass(frozen=True)
class PlannedOutput:
    report: str
    kind: Literal["pdf", "xlsx"]
    filename: str


@dataclass(frozen=True)
class GeneratedFile:
    report: str
    kind: Literal["pdf", "xlsx"]
    path: Path


@dataclass(frozen=True)
class FailedFile:
    report: str
    kind: Literal["pdf", "xlsx"]
    filename: str
    error: Exception


def build_all(src: SourceData, ctx: ReportContext) -> dict[str, ReportData]:
    """Run the builders of every report that applies, in registry order; ``None`` is skipped."""
    built: dict[str, ReportData] = {}
    for spec in REPORTS:
        if not spec.applies(ctx):
            continue
        data = spec.build(src, ctx, built)
        if data is None:
            continue
        built[spec.key] = data
    return built


def workbook_filename(ctx: ReportContext) -> str:
    return f"firefly_reports_{ctx.period.tag}.xlsx"


def plan_outputs(built: Mapping[str, ReportData], ctx: ReportContext) -> list[PlannedOutput]:
    """The files a run writes (pure): PDFs in registry order, then the workbook."""
    planned: list[PlannedOutput] = []
    if ctx.options.pdf:
        for spec in REPORTS:
            if spec.pdf is None or spec.key not in built:
                continue
            if spec.pdf_enabled(ctx, built[spec.key]):
                planned.append(PlannedOutput(spec.key, "pdf", spec.filename(ctx)))
    if ctx.options.excel:
        planned.append(PlannedOutput(WORKBOOK, "xlsx", workbook_filename(ctx)))
    return planned


def _render_one(spec: ReportSpec, data: ReportData, path: str, legacy: bool) -> None:
    if spec.pdf is None:
        raise ValueError(f"report {spec.key!r} has no PDF renderer")
    spec.pdf(data, path, legacy=legacy)


def write_outputs(
    built: Mapping[str, ReportData], ctx: ReportContext, out_dir: Path, progress: Progress
) -> tuple[list[GeneratedFile], list[FailedFile]]:
    """Write the planned files; a failing file is logged and reported, never fatal."""
    generated: list[GeneratedFile] = []
    failed: list[FailedFile] = []
    specs = {spec.key: spec for spec in REPORTS}
    legacy = ctx.options.legacy

    if ctx.options.pdf:
        progress(events.WRITE_PDF_START)
    for out in plan_outputs(built, ctx):
        if out.kind != "pdf":
            continue
        t0 = time.monotonic()
        try:
            _render_one(specs[out.report], built[out.report], str(out_dir / out.filename), legacy)
            log.debug("%s: %.2fs", out.filename, time.monotonic() - t0)
            progress(events.WRITE_OK, filename=out.filename)
            generated.append(GeneratedFile(out.report, "pdf", out_dir / out.filename))
        except Exception as exc:
            log.exception("Error generating %s", out.filename)
            progress(events.WRITE_FAIL, filename=out.filename, error=exc)
            failed.append(FailedFile(out.report, "pdf", out.filename, exc))
    if ctx.options.pdf and not ctx.options.tags:
        progress(events.WRITE_SKIPPED, report="tagged", reason="no_tags")

    if ctx.options.excel:
        progress(events.WRITE_XLSX_START)
        name = workbook_filename(ctx)
        path = out_dir / name
        t0 = time.monotonic()
        sheets: list[tuple[Any, ReportData]] = [
            (spec.sheet, built.get(spec.key)) for spec in REPORTS if spec.sheet is not None
        ]
        try:
            write_workbook(sheets, path)
            log.debug("Excel: %.2fs -> %s", time.monotonic() - t0, path)
            progress(events.WRITE_OK, filename=name)
            generated.append(GeneratedFile(WORKBOOK, "xlsx", path))
        except Exception as exc:
            log.exception("Error generating Excel")
            progress(events.WRITE_FAIL, filename=name, error=exc)
            failed.append(FailedFile(WORKBOOK, "xlsx", name, exc))
    return generated, failed
