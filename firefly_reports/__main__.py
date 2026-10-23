"""``python -m firefly_reports`` and the PyInstaller entry point."""

import sys

from firefly_reports.cli import main

if __name__ == "__main__":
    sys.exit(main())
