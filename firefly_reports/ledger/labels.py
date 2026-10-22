"""Translatable strings used by the ledger writers.

Writers stay free of global i18n state: ``main.py`` builds a ``LedgerLabels``
(from the active language plus optional overrides in the mapping file) and
hands it to them.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, replace

from firefly_reports.i18n import t
from firefly_reports.ledger.errors import ConfigError
from firefly_reports.ledger.model import FIXED_META_KEYS

# Beancount metadata keys: lowercase first letter, then letters/digits/-/_.
META_KEY_RE = re.compile(r"^[a-z][a-zA-Z0-9_-]*$")

OVERRIDABLE = ("category", "budget", "note")
# Written by the writer under a fixed name: no override may collide with them.
RESERVED_KEYS = (*FIXED_META_KEYS, "iban", "payee")


@dataclass(frozen=True)
class LedgerLabels:
    meta_category: str
    meta_budget: str
    meta_note: str
    header_notice: str
    header_generated: str  # contains a {timestamp} placeholder
    fallback_expense: str
    fallback_income: str
    investment_root: str
    # Technical keys: identical in every language (idempotence / debugging).
    meta_firefly_id: str = "firefly_id"
    meta_firefly_group_id: str = "firefly_group_id"

    def __post_init__(self) -> None:
        seen: dict[str, str] = {}
        for name in (
            "meta_category",
            "meta_budget",
            "meta_note",
            "meta_firefly_id",
            "meta_firefly_group_id",
        ):
            value = getattr(self, name)
            if not META_KEY_RE.match(value):
                raise ConfigError("ledger.err_label_key", name=name, value=value)
            if name.removeprefix("meta_") in OVERRIDABLE and value in (
                self.meta_firefly_id,
                self.meta_firefly_group_id,
                *RESERVED_KEYS,
            ):
                raise ConfigError("ledger.err_label_reserved", name=name, value=value)
            if value in seen:
                raise ConfigError(
                    "ledger.err_label_duplicate", name=name, other=seen[value], value=value
                )
            seen[value] = name

    @classmethod
    def from_i18n(cls, overrides: Mapping[str, str] | None = None) -> LedgerLabels:
        """Build labels from the active language, then apply mapping-file overrides."""
        labels = cls(
            meta_category=t("ledger.meta_category"),
            meta_budget=t("ledger.meta_budget"),
            meta_note=t("ledger.meta_note"),
            header_notice=t("ledger.header_notice"),
            header_generated=t("ledger.header_generated"),
            fallback_expense=t("ledger.fallback_expense"),
            fallback_income=t("ledger.fallback_income"),
            investment_root=t("ledger.investment_root"),
        )
        if overrides:
            labels = replace(labels, **{f"meta_{k}": v for k, v in overrides.items()})
        return labels
