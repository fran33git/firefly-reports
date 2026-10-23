"""Config file loader for firefly-reports."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

CONFIG_FILE = Path("./firefly-reports.toml")


def load_config() -> dict[str, Any]:
    """Load ./firefly-reports.toml from the current working directory.

    Supported keys in the TOML file:
      - url: Firefly III base URL
      - token: Personal Access Token
      - owner: Account owner name
      - currency: Currency symbol
      - lang: Output language (en/it)
      - legacy_report: Use legacy PDF styles (boolean)
      - out: Output directory
      - tags: List of tags for the tagged report
      - reports: Section containing:
          - fetch_links: Fetch full details for linked transactions (boolean)
          - all_tags_report: Generate report for all tags (boolean)
          - historical_years: Number of years for historical analysis (3 or 5)

    Returns an empty dict when the file does not exist.
    Propagates tomllib.TOMLDecodeError on malformed TOML — callers are
    responsible for handling parse errors.
    """
    if not CONFIG_FILE.exists():
        return {}
    with CONFIG_FILE.open("rb") as fh:
        return tomllib.load(fh)
