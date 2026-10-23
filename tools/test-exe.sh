#!/bin/bash
# Build and smoke-test the PyInstaller binary locally (Linux).
# Mirrors the windows-exe job in .github/workflows/release.yml and ci.yml —
# keep the PyInstaller command and the probes in sync (Linux uses ':' as the
# --add-data separator, Windows uses ';').
#
# Usage: ./tools/test-exe.sh
# Requires: pyinstaller installed in .venv (pip install pyinstaller)

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY="${PYTHON:-.venv/bin/python}"
if ! "$PY" -c "import PyInstaller" 2>/dev/null; then
    echo "ERROR: pyinstaller not found. Install it with: $PY -m pip install pyinstaller" >&2
    exit 1
fi

BUILD_DIR="$(mktemp -d)"
trap 'rm -rf "$BUILD_DIR"' EXIT

echo "== Building binary with PyInstaller =="
"$PY" -m PyInstaller --onefile --name firefly-reports --paths . \
    --add-data "$ROOT/firefly_reports/translations:firefly_reports/translations" \
    firefly_reports/__main__.py \
    --distpath "$BUILD_DIR/dist" --workpath "$BUILD_DIR/work" --specpath "$BUILD_DIR/spec" \
    --log-level WARN

EXE="$BUILD_DIR/dist/firefly-reports"

echo "== Probe 1: --help =="
"$EXE" --help >/dev/null

echo "== Probe 2: --help under cp1252 console encoding (Windows legacy codepage) =="
PYTHONIOENCODING=cp1252 "$EXE" --help >/dev/null

echo "== Probe 3: translations bundled (expect connection failure, never missing files) =="
probe_out="$("$EXE" report --year 2025 --url http://127.0.0.1:9 --token dummy 2>&1 || true)"
if echo "$probe_out" | grep -qE "No translation file|FileNotFoundError|_MEI"; then
    echo "FAIL: translations missing from the bundle:" >&2
    echo "$probe_out" >&2
    exit 1
fi

echo "== Probe 4: the 1.x form (no subcommand) still works and warns =="
legacy_out="$("$EXE" --year 2025 --url http://127.0.0.1:9 --token dummy 2>&1 || true)"
if ! echo "$legacy_out" | grep -q "deprecated" || echo "$legacy_out" | grep -qE "No translation file|FileNotFoundError|_MEI"; then
    echo "FAIL: legacy form probe:" >&2
    echo "$legacy_out" >&2
    exit 1
fi

echo "== Probe 5: offline end to end run under a legacy console codepage =="
PYTHONIOENCODING=cp1252 "$EXE" demo --out "$BUILD_DIR/demo" --lang it >/dev/null
pdfs="$(ls "$BUILD_DIR"/demo/*.pdf | wc -l)"
if [ "$pdfs" -ne 27 ]; then
    echo "FAIL: expected 27 PDFs from the demo, got $pdfs" >&2
    exit 1
fi

echo "== Probe 6: --version =="
"$EXE" --version | grep -Eq '^firefly-reports [0-9]+\.[0-9]+\.[0-9]+'

echo "All exe smoke tests passed."
