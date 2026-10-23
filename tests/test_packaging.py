"""Packaging: every package has an __init__, and (opt-in) the built wheel is complete."""

import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
PKG = ROOT / "firefly_reports"


def test_every_package_has_init():
    """No implicit namespace packages: setuptools would silently drop them from the wheel."""
    for directory in PKG.rglob("*"):
        if not directory.is_dir() or ".venv" in directory.parts or "__pycache__" in directory.parts:
            continue
        if any(p.suffix == ".py" for p in directory.iterdir()):
            assert (directory / "__init__.py").exists(), directory.relative_to(ROOT)


@pytest.mark.skipif(
    os.environ.get("FIREFLY_BUILD_WHEEL") != "1", reason="slow: set FIREFLY_BUILD_WHEEL=1"
)
def test_wheel_contents(tmp_path):
    subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            str(tmp_path),
            str(ROOT),
        ],
        check=True,
        capture_output=True,
    )
    wheel = next(tmp_path.glob("*.whl"))
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()
        entry_points = next(zf.read(n) for n in names if n.endswith("entry_points.txt")).decode()
    for expected in (
        "firefly_reports/translations/en.toml",
        "firefly_reports/translations/it.toml",
        "firefly_reports/py.typed",
        "firefly_reports/cli/__init__.py",
        "firefly_reports/reports/cash_flow/pdf.py",
        "firefly_reports/demo/data.py",
        "firefly_reports/ledger/writers/beancount.py",
    ):
        assert expected in names, expected
    assert not [n for n in names if ".venv" in n or n.startswith("tests/") or "/tests/" in n]
    assert "firefly-reports = firefly_reports.cli:main" in entry_points
