"""Deprecated shim: the CLI lives in ``firefly_reports.cli``. Removed in 3.0."""

import sys

from firefly_reports import i18n
from firefly_reports.cli import main

__all__ = ["main"]

if __name__ == "__main__":
    i18n.load("en")
    print(
        i18n.t("cli.deprecated_module").format(
            old="python -m firefly_reports.main",
            new="firefly-reports (or python -m firefly_reports)",
        ),
        file=sys.stderr,
    )
    sys.exit(main())
