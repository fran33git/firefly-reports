#!/usr/bin/env python3
"""Local A/B harness: prove a refactor leaves the report output byte-identical.

    python tools/ab_snapshot.py write DIR      # record SHA-256 of every PDF + the workbook JSON
    python tools/ab_snapshot.py compare DIR    # recompute and diff against DIR

Not a test: PDF bytes are only reproducible inside one environment (same reportlab,
matplotlib, Python). Runs the demo suite (en, it) and the pipeline scenarios offline with
``reportlab.rl_config.invariant = 1`` and the clock frozen.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("MPLBACKEND", "Agg")

from reportlab import rl_config  # noqa: E402

rl_config.invariant = 1

from tests.golden.harness import render_demo_suite, run_pipeline  # noqa: E402
from tests.golden.snapshot import xlsx_snapshot  # noqa: E402
from tests.test_golden_pipeline import CREDS, SCENARIOS  # noqa: E402

MANIFEST = "manifest.json"


def _hash_dir(prefix: str, directory: Path, into: dict[str, str]) -> None:
    for path in sorted(directory.iterdir()):
        if path.suffix == ".pdf":
            into[f"{prefix}/{path.name}"] = hashlib.sha256(path.read_bytes()).hexdigest()
        elif path.suffix == ".xlsx":
            text = json.dumps(xlsx_snapshot(path), ensure_ascii=False)
            into[f"{prefix}/{path.name}"] = hashlib.sha256(text.encode("utf-8")).hexdigest()


def collect() -> dict[str, str]:
    result: dict[str, str] = {}
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        for lang in ("en", "it"):
            out = base / f"suite-{lang}"
            out.mkdir()
            render_demo_suite(out, lang)
            _hash_dir(f"suite/{lang}", out, result)
        for scenario, argv in SCENARIOS:
            out = base / scenario / "out"
            run_pipeline(out, [*CREDS, *argv])
            _hash_dir(f"pipeline/{scenario}", out, result)
    return result


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] not in ("write", "compare"):
        print(__doc__)
        return 2
    mode, directory = argv[0], Path(argv[1])
    current = collect()
    manifest = directory / MANIFEST
    if mode == "write":
        directory.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps(current, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(f"A/B: baseline written ({len(current)} files) -> {manifest}")
        return 0
    baseline = json.loads(manifest.read_text(encoding="utf-8"))
    differing = sorted(
        k for k in baseline.keys() | current.keys() if baseline.get(k) != current.get(k)
    )
    if differing:
        print(f"A/B: {len(differing)} differ")
        for name in differing:
            print(f"  {name}")
        return 1
    print(f"A/B: identical ({len(current)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
