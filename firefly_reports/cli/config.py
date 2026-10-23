"""Config file loader for firefly-reports."""

from __future__ import annotations

import difflib
import tomllib
from pathlib import Path
from typing import Any

CONFIG_FILE = Path("./firefly-reports.toml")

# Every key the CLI reads; ``None`` marks a top-level value, a set a ``[section]``.
KNOWN_KEYS: dict[str, frozenset[str] | None] = {
    "url": None,
    "token": None,
    "owner": None,
    "currency": None,
    "lang": None,
    "legacy_report": None,
    "out": None,
    "tags": None,
    "year": None,
    "reports": frozenset({"fetch_links", "all_tags_report", "historical_years", "link_delay"}),
    "filters": frozenset(
        {
            "accounts_include",
            "accounts_exclude",
            "categories_include",
            "categories_exclude",
            "show_transfers",
            "reconciled_only",
            "fiscal_year_start",
        }
    ),
    "tax": frozenset({"deductible_keywords"}),
    "export": frozenset({"out", "layout", "classify_by", "map"}),
}


def unknown_keys(config: dict[str, Any]) -> list[tuple[str, str | None]]:
    """Keys of *config* that nothing reads, as ``(dotted key, closest known key or None)``."""
    found: list[tuple[str, str | None]] = []
    for key, value in config.items():
        if key not in KNOWN_KEYS:
            close = difflib.get_close_matches(key, KNOWN_KEYS, n=1)
            found.append((key, close[0] if close else None))
        elif KNOWN_KEYS[key] is not None and isinstance(value, dict):
            known = KNOWN_KEYS[key] or frozenset()
            for sub in value:
                if sub not in known:
                    close = difflib.get_close_matches(sub, known, n=1)
                    found.append((f"{key}.{sub}", f"{key}.{close[0]}" if close else None))
    return found


def load_config() -> dict[str, Any]:
    """Load ./firefly-reports.toml from the current working directory.

    Supported keys in the TOML file:
      - url: Firefly III base URL
      - token: Personal Access Token
      - owner: Account owner name
      - currency: Currency symbol
      - lang: Output language (en/it)
      - legacy_report: Use legacy PDF styles (boolean)
      - out: Output directory of ``report``
      - tags: List of tags for the tagged report
      - year: Default full calendar year
      - [reports]: fetch_links, all_tags_report, historical_years, link_delay
      - [filters]: accounts_include/exclude, categories_include/exclude, show_transfers,
        reconciled_only, fiscal_year_start
      - [tax]: deductible_keywords
      - [export]: out, layout, classify_by, map (defaults for ``export beancount``)

    ``KNOWN_KEYS`` is the authoritative list; anything else is reported by ``unknown_keys``.

    Returns an empty dict when the file does not exist.
    Propagates tomllib.TOMLDecodeError on malformed TOML — callers are
    responsible for handling parse errors.
    """
    if not CONFIG_FILE.exists():
        return {}
    with CONFIG_FILE.open("rb") as fh:
        return tomllib.load(fh)
