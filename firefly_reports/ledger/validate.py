"""Optional validation of the generated file with ``bean-check``."""

from __future__ import annotations

import shutil
import subprocess  # nosec B404 - fixed argv, no shell
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ValidationResult:
    available: bool
    ok: bool
    # Error blocks as printed by bean-check (one string per problem).
    problems: tuple[str, ...] = ()


def _split_problems(output: str) -> tuple[str, ...]:
    """Group bean-check output into one block per error (blank-line separated)."""
    blocks = [b.strip() for b in output.replace("\r\n", "\n").split("\n\n")]
    return tuple(b for b in blocks if b)


def run_bean_check(path: Path, timeout: float = 300) -> ValidationResult:
    """Run ``bean-check`` on *path* if it is installed."""
    exe = shutil.which("bean-check")
    if exe is None:
        return ValidationResult(available=False, ok=False)
    proc = subprocess.run(  # nosec B603 - exe resolved via shutil.which, argv is a list
        [exe, str(path)],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if proc.returncode == 0:
        return ValidationResult(available=True, ok=True)
    return ValidationResult(
        available=True, ok=False, problems=_split_problems(proc.stdout + proc.stderr)
    )
