"""Deprecated: ``python -m firefly_reports.demo`` is now ``firefly-reports demo``. Removed in 3.0."""

import sys

from firefly_reports import i18n
from firefly_reports.cli import main

if __name__ == "__main__":
    i18n.load("en")
    print(
        i18n.t("cli.deprecated_module").format(
            old="python -m firefly_reports.demo", new="firefly-reports demo"
        ),
        file=sys.stderr,
    )
    sys.exit(main(["demo", *sys.argv[1:]]))
