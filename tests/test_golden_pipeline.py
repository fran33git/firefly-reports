"""The CLI report pipeline end to end (DemoClient, frozen clock), pinned by golden snapshots."""

import pytest

from tests.golden.harness import run_pipeline
from tests.golden.snapshot import assert_golden

SCENARIOS = [
    ("year_full", ["--year", "2025", "--tags", "tax", "--all-tags", "--fetch-links"]),
    ("range_legacy", ["--start", "2025-01-01", "--end", "2025-06-30", "--legacy-report"]),
    ("year_it", ["--lang", "it", "--year", "2025"]),
]
CREDS = ["--url", "https://demo.invalid", "--token", "x"]


@pytest.mark.golden
@pytest.mark.parametrize(("scenario", "argv"), SCENARIOS)
def test_pipeline_matches_golden(scenario, argv, tmp_path):
    run = run_pipeline(tmp_path / "out", [*CREDS, *argv])
    assert run.exit_code == 0
    assert_golden(f"pipeline/{scenario}", run.as_dict())


def test_pipeline_scenarios_cover_the_mode_switches(tmp_path):
    full = run_pipeline(tmp_path / "a" / "out", [*CREDS, *SCENARIOS[0][1]])
    legacy = run_pipeline(tmp_path / "b" / "out", [*CREDS, *SCENARIOS[1][1]])
    assert not any(f.startswith("audit_log_") for f in full.files)
    assert any(f.startswith("summary_") for f in full.files)
    assert sum(f.endswith(".pdf") for f in full.files) == 27
    assert any(f.startswith("audit_log_") for f in legacy.files)
    assert not any(f.startswith(("summary_", "yoy_")) for f in legacy.files)
