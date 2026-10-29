"""build_all / plan_outputs / write_outputs on the offline demo data."""

from datetime import date

import pytest

from firefly_reports.demo.client import DemoClient
from firefly_reports.reports import pipeline
from firefly_reports.reports.events import no_progress
from firefly_reports.reports.fetch import fetch_source_data
from firefly_reports.reports.options import Period, ReportOptions
from firefly_reports.reports.pipeline import build_all, plan_outputs, write_outputs
from firefly_reports.reports.spec import ReportContext


def _built(ctx):
    return build_all(fetch_source_data(DemoClient(), ctx, no_progress), ctx)


def _pdfs(ctx, built=None):
    built = built if built is not None else _built(ctx)
    return [o.filename for o in plan_outputs(built, ctx) if o.kind == "pdf"]


YEAR = Period.for_year(2025)
RANGE = Period.between(date(2025, 1, 1), date(2025, 6, 30))


def test_plan_outputs_year_mode_standard():
    ctx = ReportContext(YEAR, ReportOptions(tags=("tax",), all_tags=True, fetch_links=True))
    names = _pdfs(ctx)
    assert len(names) == 27
    assert not any(n.startswith("audit_log_") for n in names)
    assert "yoy_2024_vs_2025.pdf" in names and "tax_summary_2025.pdf" in names
    assert "tagged_tax_2025-01-01__2025-12-31.pdf" in names
    assert (
        plan_outputs(_built(ctx), ctx)[-1].filename == "firefly_reports_2025-01-01__2025-12-31.xlsx"
    )


def test_plan_outputs_range_legacy():
    ctx = ReportContext(RANGE, ReportOptions(legacy=True))
    names = _pdfs(ctx)
    assert any(n.startswith("audit_log_") for n in names)
    assert not any(n.startswith(("summary_", "yoy_", "journal_")) for n in names)


def test_plan_outputs_tagged_only_with_tags():
    assert not any(n.startswith("tagged_") for n in _pdfs(ReportContext(YEAR, ReportOptions())))


def test_plan_outputs_linkage_needs_groups_or_fetch_links():
    ctx = ReportContext(YEAR, ReportOptions())
    built = _built(ctx)
    built["linkage_audit"] = {"groups": []}
    assert not any(n.startswith("audit_linkage_") for n in _pdfs(ctx, built))
    fetch_ctx = ReportContext(YEAR, ReportOptions(fetch_links=True))
    assert any(n.startswith("audit_linkage_") for n in _pdfs(fetch_ctx, built))
    built["linkage_audit"] = {"groups": [{"id": 1}]}
    assert any(n.startswith("audit_linkage_") for n in _pdfs(ctx, built))


def test_plan_outputs_no_pdf_no_excel_is_empty():
    ctx = ReportContext(YEAR, ReportOptions(pdf=False, excel=False))
    assert plan_outputs(_built(ctx), ctx) == []


def test_build_all_skips_reports_that_do_not_apply():
    built = _built(ReportContext(RANGE, ReportOptions()))
    assert "yoy" not in built and "historical_growth" not in built
    assert "audit_log" not in built and "summary" in built
    legacy = _built(ReportContext(RANGE, ReportOptions(legacy=True)))
    assert "audit_log" in legacy and "journal" not in legacy


def test_write_outputs_continues_after_a_failure(tmp_path, monkeypatch):
    ctx = ReportContext(YEAR, ReportOptions())
    built = _built(ctx)
    original = pipeline._render_one

    def flaky(spec, data, path, legacy):
        if spec.key == "cash_flow":
            raise RuntimeError("boom")
        return original(spec, data, path, legacy)

    monkeypatch.setattr(pipeline, "_render_one", flaky)
    events: list[tuple] = []
    generated, failed = write_outputs(
        built, ctx, tmp_path, lambda event, **fields: events.append((event, fields))
    )
    assert [f.report for f in failed] == ["cash_flow"]
    assert isinstance(failed[0].error, RuntimeError)
    assert (tmp_path / "income_expense_2025-01-01__2025-12-31.pdf").exists()
    assert any(g.kind == "xlsx" for g in generated)
    assert ("write.skipped", {"report": "tagged", "reason": "no_tags"}) in events


def test_write_outputs_reports_a_workbook_failure(tmp_path, monkeypatch):
    ctx = ReportContext(YEAR, ReportOptions(pdf=False))
    built = _built(ctx)

    def boom(*args, **kwargs):
        raise RuntimeError("xlsx boom")

    monkeypatch.setattr(pipeline, "write_workbook", boom)
    generated, failed = write_outputs(built, ctx, tmp_path, no_progress)
    assert generated == [] and [f.kind for f in failed] == ["xlsx"]


@pytest.mark.parametrize("legacy", [False, True])
def test_write_outputs_writes_every_planned_file(tmp_path, legacy):
    ctx = ReportContext(RANGE, ReportOptions(legacy=legacy, tags=("tax",)))
    built = _built(ctx)
    generated, failed = write_outputs(built, ctx, tmp_path, no_progress)
    assert not failed
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(
        o.filename for o in plan_outputs(built, ctx)
    )
