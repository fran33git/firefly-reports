"""Help output of the root parser and each subcommand, pinned by golden snapshots."""

import pytest

from tests.golden.harness import run_main
from tests.golden.snapshot import assert_golden


@pytest.mark.golden
@pytest.mark.parametrize(
    ("name", "argv"),
    [
        ("root", ["--help"]),
        ("init", ["init", "--help"]),
        ("export", ["export", "--help"]),
        ("report", ["report", "--help"]),
        ("demo", ["demo", "--help"]),
    ],
)
def test_help_matches_golden(name, argv, tmp_path, monkeypatch):
    monkeypatch.setenv("COLUMNS", "100")
    code, out, _ = run_main(argv, tmp_path)
    assert code == 0
    assert_golden(f"cli/help_{name}", " ".join(out.split()))
