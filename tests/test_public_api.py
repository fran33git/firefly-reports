"""The provisional library facade: names, signatures, version and import cost."""

import inspect
import subprocess
import sys
import tomllib
from pathlib import Path

import firefly_reports

ROOT = Path(__file__).parent.parent

PUBLIC = [
    "ConfigurationError",
    "FailedFile",
    "FireflyAPIError",
    "FireflyReportsError",
    "FireflySource",
    "GeneratedFile",
    "GlobalFilters",
    "Headline",
    "Period",
    "ReportError",
    "ReportInfo",
    "ReportOptions",
    "ReportResult",
    "SourceData",
    "__version__",
    "available_reports",
    "build_reports",
    "connect",
    "fetch_data",
    "generate_reports",
    "write_reports",
]


def test_public_api_snapshot():
    assert sorted(firefly_reports.__all__) == PUBLIC
    for name in PUBLIC:
        assert getattr(firefly_reports, name) is not None


def test_generate_reports_signature_is_pinned():
    assert str(inspect.signature(firefly_reports.generate_reports)) == (
        "(source: 'FireflySource', period: 'Period', options: 'ReportOptions', "
        "out_dir: 'Path', *, progress: 'Progress | None' = None) -> 'ReportResult'"
    )


def test_version_matches_pyproject():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["version"] == firefly_reports.__version__ == "2.0.0"


def test_import_is_light():
    code = (
        "import firefly_reports, sys; "
        "heavy = {'reportlab', 'matplotlib', 'openpyxl', 'requests'} & set(sys.modules); "
        "assert not heavy, heavy"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def test_py_typed_marker_ships():
    assert (ROOT / "firefly_reports" / "py.typed").exists()
