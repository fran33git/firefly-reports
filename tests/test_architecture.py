"""Layering rules, checked on the source (AST): imports and side effects stay where they belong."""

import ast
from pathlib import Path

PKG = Path(__file__).parent.parent / "firefly_reports"

PURE_MODULES = (
    "reports/_money.py",
    "reports/_labels.py",
    "reports/filters.py",
    "reports/options.py",
    "reports/spec.py",
)
FORBIDDEN_IN_PURE = (
    "reportlab",
    "openpyxl",
    "matplotlib",
    "requests",
    "os",
    "pathlib",
    "io",
    "firefly_reports.render",
    "firefly_reports.cli",
)


def _sources():
    return [p for p in PKG.rglob("*.py") if ".venv" not in p.parts]


def _rel(path: Path) -> str:
    return path.relative_to(PKG).as_posix()


def _imports(path: Path) -> set[str]:
    """Absolute module names imported anywhere in the file (also inside functions)."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
            found.update(f"{node.module}.{alias.name}" for alias in node.names)
    return found


def _matches(imported: set[str], forbidden: tuple[str, ...]) -> set[str]:
    return {i for i in imported for f in forbidden if i == f or i.startswith(f + ".")}


def test_requests_only_in_client_api_and_cli():
    allowed = {"firefly_client.py", "api.py"}
    for path in _sources():
        rel = _rel(path)
        if rel in allowed or rel.startswith("cli/"):
            continue
        assert not _matches(_imports(path), ("requests",)), rel


def test_builders_are_pure():
    pure = [PKG / m for m in PURE_MODULES] + list(PKG.glob("reports/*/build.py"))
    assert len(pure) > 20
    for path in pure:
        assert not _matches(_imports(path), FORBIDDEN_IN_PURE), _rel(path)


def test_render_does_not_import_reports_api_cli_ledger():
    forbidden = (
        "firefly_reports.reports",
        "firefly_reports.api",
        "firefly_reports.cli",
        "firefly_reports.ledger",
    )
    for path in PKG.glob("render/**/*.py"):
        assert not _matches(_imports(path), forbidden), _rel(path)


def test_ledger_does_not_import_reports_render_cli():
    forbidden = (
        "firefly_reports.reports",
        "firefly_reports.render",
        "firefly_reports.cli",
        "firefly_reports.api",
    )
    for path in PKG.glob("ledger/**/*.py"):
        assert not _matches(_imports(path), forbidden), _rel(path)


def test_nothing_imports_cli_or_main():
    allowed = {"__main__.py", "main.py", "demo/__main__.py"}
    for path in _sources():
        rel = _rel(path)
        if rel in allowed or rel.startswith("cli/"):
            continue
        assert not _matches(_imports(path), ("firefly_reports.cli", "firefly_reports.main")), rel


def test_no_print_exit_input_outside_cli():
    allowed = {"main.py", "__main__.py", "demo/__main__.py", "ledger/export.py"}  # grandfathered
    for path in _sources():
        rel = _rel(path)
        if rel in allowed or rel.startswith("cli/"):
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {"print", "input", "exit"}, f"{rel}:{node.lineno}"
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "exit"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "sys"
            ):
                raise AssertionError(f"{rel}:{node.lineno} sys.exit")


def test_no_dynamic_imports():
    """PyInstaller follows static imports only."""
    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == "__import__":
                raise AssertionError(f"{_rel(path)}:{node.lineno}")
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in node.names] + [getattr(node, "module", None) or ""]
                assert "importlib" not in names, f"{_rel(path)}:{node.lineno}"


def test_registry_imports_every_report_package():
    from firefly_reports.reports.registry import REPORTS

    packages = {p.parent.name for p in PKG.glob("reports/*/__init__.py")}
    assert packages == {spec.key for spec in REPORTS}


def test_no_transitional_shims_left():
    for name in ("data_processor.py", "pdf_exporter.py", "excel_exporter.py"):
        assert not (PKG / name).exists(), name
