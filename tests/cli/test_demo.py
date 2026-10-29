"""``firefly-reports demo``: the real pipeline on the built-in sample data."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from firefly_reports.cli import main


@pytest.fixture
def cli(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("firefly_reports.cli._options.load_dotenv", lambda *a, **k: None)
    for var in ("FIREFLY_URL", "FIREFLY_TOKEN", "FIREFLY_LANG", "FIREFLY_LEGACY_REPORT"):
        monkeypatch.delenv(var, raising=False)
    return tmp_path


def _pdfs(out):
    return sorted(p.name for p in out.glob("*.pdf"))


def test_demo_writes_standard_set(cli):
    out = cli / "out"
    assert main(["demo", "--out", str(out)]) == 0
    names = _pdfs(out)
    assert len(names) == 27
    assert not any(n.startswith("audit_log_") for n in names)
    assert "tagged_tax_2025-01-01__2025-12-31.pdf" in names
    assert "yoy_2024_vs_2025.pdf" in names
    assert (out / "firefly_reports_2025-01-01__2025-12-31.xlsx").exists()


def test_demo_legacy_has_audit_log(cli):
    out = cli / "out"
    assert main(["demo", "--out", str(out), "--legacy-report", "--no-excel"]) == 0
    names = _pdfs(out)
    assert any(n.startswith("audit_log_") for n in names)
    assert not any(n.startswith(("summary_", "journal_")) for n in names)
    assert not list(out.glob("*.xlsx"))


def test_demo_year_and_language(cli, capsys):
    out = cli / "out"
    assert main(["demo", "--out", str(out), "--year", "2024", "--lang", "it", "--no-pdf"]) == 0
    assert (out / "firefly_reports_2024-01-01__2024-12-31.xlsx").exists()
    assert not list(out.glob("*.pdf"))
    assert "demo" in capsys.readouterr().out.lower()


def test_demo_default_output_directory_is_output(cli):
    assert main(["demo", "--no-pdf", "--no-excel"]) == 0
    assert (cli / "output").is_dir()


def test_python_m_demo_still_works_with_a_deprecation(tmp_path):
    # The child process does not get pytest's ``pythonpath``: point it at the repo root so the
    # test also passes where the package is not installed (CI).
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2])}
    proc = subprocess.run(
        [sys.executable, "-m", "firefly_reports.demo", "--out", str(tmp_path), "--no-pdf"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    assert "deprecated" in proc.stderr and "firefly-reports demo" in proc.stderr
    assert list(tmp_path.glob("firefly_reports_*.xlsx"))


def test_demo_warns_that_credentials_are_ignored(cli, capsys):
    out = cli / "out"
    assert main(["demo", "--out", str(out), "--no-pdf", "--url", "https://x.invalid"]) == 0
    assert "--url and --token are ignored" in capsys.readouterr().err
    assert main(["demo", "--out", str(out), "--no-pdf"]) == 0
    assert "ignored" not in capsys.readouterr().err
