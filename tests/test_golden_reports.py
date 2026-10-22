"""Characterization snapshots of report data, PDF documents and the Excel workbook.

Regenerate on purpose with ``FIREFLY_UPDATE_GOLDEN=1 pytest -m golden`` and name the
reason in the commit message.
"""

import json

import pytest

from tests.golden import snapshot
from tests.golden.harness import build_demo_suite, render_demo_suite
from tests.golden.snapshot import (
    assert_golden,
    story_recorder,
    to_jsonable,
    xlsx_snapshot,
)

LANGS = ["en", "it"]


@pytest.mark.golden
@pytest.mark.parametrize("lang", LANGS)
def test_builders_match_golden(lang):
    assert_golden(f"data/{lang}/builders", to_jsonable(build_demo_suite(lang)))


@pytest.mark.golden
@pytest.mark.parametrize("lang", LANGS)
def test_pdf_stories_match_golden(lang, tmp_path):
    with story_recorder() as stories:
        paths = render_demo_suite(tmp_path, lang)
    assert len([p for p in paths if p.suffix == ".pdf"]) == 28
    assert len(stories) == 28
    for snap in stories:
        assert_golden(f"pdf/{lang}/{snap.stem}", snap.as_dict(), digest_only=(lang == "it"))


@pytest.mark.golden
@pytest.mark.parametrize("lang", LANGS)
def test_workbook_matches_golden(lang, tmp_path):
    paths = render_demo_suite(tmp_path, lang)
    xlsx = next(p for p in paths if p.suffix == ".xlsx")
    assert_golden(f"xlsx/{lang}/workbook", xlsx_snapshot(xlsx))


def test_assert_golden_detects_a_changed_value(tmp_path, monkeypatch):
    monkeypatch.setattr(snapshot, "GOLDEN_ROOT", tmp_path)
    monkeypatch.setenv(snapshot.UPDATE_ENV, "1")
    assert_golden("x/sample", {"a": [1, {"b": "D:1.00"}]})
    assert_golden("x/digest", {"a": 1}, digest_only=True)
    monkeypatch.delenv(snapshot.UPDATE_ENV)
    assert_golden("x/sample", {"a": [1, {"b": "D:1.00"}]})
    assert_golden("x/digest", {"a": 1}, digest_only=True)
    with pytest.raises(AssertionError, match=r"\$\.a\[1\]\.b"):
        assert_golden("x/sample", {"a": [1, {"b": "D:1.01"}]})
    with pytest.raises(AssertionError, match="digest differs"):
        assert_golden("x/digest", {"a": 2}, digest_only=True)
    with pytest.raises(AssertionError, match="golden file missing"):
        assert_golden("x/absent", {})
    assert json.loads((tmp_path / "x/sample.json").read_text()) == {"a": [1, {"b": "D:1.00"}]}


def test_to_jsonable_tags_money_dates_and_floats():
    from datetime import date
    from decimal import Decimal

    out = to_jsonable({"d": Decimal("1.50"), "f": 1.5, "t": date(2025, 1, 2), "l": (1, 2)})
    assert out == {"d": "D:1.50", "f": "F:1.5", "t": "date:2025-01-02", "l": [1, 2]}
