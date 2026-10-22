"""Loader and validator for the ``beancount_map.yaml`` mapping file."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from firefly_reports.ledger.errors import ConfigError
from firefly_reports.ledger.labels import OVERRIDABLE

ACCOUNT_RE = re.compile(r"^(Assets|Liabilities|Equity|Income|Expenses)(:[A-Z0-9][A-Za-z0-9-]*)+$")
CURRENCY_RE = re.compile(r"^[A-Z](?:[A-Z0-9'._-]{0,22}[A-Z0-9])?$")

CLASSIFY_CATEGORY = "category"
CLASSIFY_ACCOUNT = "account"
_CLASSIFY_MODES = (CLASSIFY_CATEGORY, CLASSIFY_ACCOUNT)
_CATEGORY_BLOCKS = {"expense": "Expenses", "income": "Income"}

_TOP_LEVEL_KEYS = (
    "classify_by",
    "accounts",
    "categories",
    "investment_accounts",
    "investment_root",
    "fallback",
    "operating_currency",
    "commodities",
    "labels",
)
_FALLBACK_KEYS = ("expense", "income", "strict")


@dataclass(frozen=True)
class LedgerConfig:
    # Firefly account name (or numeric id) -> ledger account; overrides normalisation.
    accounts: Mapping[str, str] = field(default_factory=dict)
    # Firefly investment account name (or id) -> broker name.
    investment_accounts: Mapping[str, str] = field(default_factory=dict)
    # None -> language default from LedgerLabels.
    investment_root: str | None = None
    fallback_expense: str | None = None
    fallback_income: str | None = None
    # When true, expense/revenue accounts missing from ``accounts`` use the fallback.
    fallback_strict: bool = False
    operating_currency: tuple[str, ...] = ()
    commodities: tuple[str, ...] = ()
    label_overrides: Mapping[str, str] = field(default_factory=dict)
    # Where expense/income accounts come from: the Firefly category or the counterpart account.
    classify_by: str = CLASSIFY_CATEGORY
    # Firefly category name -> ledger account, one mapping per direction.
    categories_expense: Mapping[str, str] = field(default_factory=dict)
    categories_income: Mapping[str, str] = field(default_factory=dict)


def _section(data: Mapping[str, Any], key: str, expected: type, label: str) -> Any:
    value = data.get(key)
    if value is None:
        return expected()
    if not isinstance(value, expected):
        raise ConfigError("ledger.err_config_section", section=key, expected=label)
    return value


def _check_account(value: object, key: str) -> str:
    if not isinstance(value, str) or not ACCOUNT_RE.match(value):
        raise ConfigError("ledger.err_config_account", value=value, key=key)
    return value


def _currencies(values: list[Any]) -> tuple[str, ...]:
    out: list[str] = []
    for v in values:
        cur = str(v).strip().upper()
        if not CURRENCY_RE.match(cur):
            raise ConfigError("ledger.err_config_currency", value=v)
        if cur not in out:
            out.append(cur)
    return tuple(out)


def _str_keys(raw: Mapping[Any, Any], section: str) -> dict[str, Any]:
    """String-keyed copy of *raw*, rejecting keys that collide after ``str()``."""
    out: dict[str, Any] = {}
    for k, v in raw.items():
        key = str(k)
        if key in out:
            raise ConfigError("ledger.err_config_duplicate_key", section=section, key=key)
        out[key] = v
    return out


def _categories(raw: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    """Validate ``categories:`` (blocks ``expense``/``income``); each value needs its root."""
    out: dict[str, dict[str, str]] = {block: {} for block in _CATEGORY_BLOCKS}
    for block, entries in raw.items():
        if block not in _CATEGORY_BLOCKS:
            raise ConfigError(
                "ledger.err_config_block",
                block=block,
                allowed=", ".join(_CATEGORY_BLOCKS),
            )
        if entries is None:
            continue
        if not isinstance(entries, dict):
            raise ConfigError(
                "ledger.err_config_section", section=f"categories.{block}", expected="mapping"
            )
        root = _CATEGORY_BLOCKS[block]
        for name, value in _str_keys(entries, f"categories.{block}").items():
            account = _check_account(value, name)
            if account.split(":", 1)[0] != root:
                raise ConfigError(
                    "ledger.err_config_category_root", key=name, value=account, root=root
                )
            out[block][name] = account
    return out


def parse_ledger_config(data: Mapping[str, Any] | None) -> LedgerConfig:
    """Validate a parsed YAML document and build a ``LedgerConfig``."""
    if data is None:
        return LedgerConfig()
    if not isinstance(data, Mapping):
        raise ConfigError("ledger.err_config_type")
    for key in data:
        if key not in _TOP_LEVEL_KEYS:
            raise ConfigError("ledger.err_config_key", key=key, allowed=", ".join(_TOP_LEVEL_KEYS))

    classify_by = data.get("classify_by", CLASSIFY_CATEGORY)
    if classify_by not in _CLASSIFY_MODES:
        raise ConfigError(
            "ledger.err_config_classify", value=classify_by, allowed=", ".join(_CLASSIFY_MODES)
        )
    categories = _categories(_section(data, "categories", dict, "mapping"))

    accounts_raw = _str_keys(_section(data, "accounts", dict, "mapping"), "accounts")
    accounts = {k: _check_account(v, k) for k, v in accounts_raw.items()}

    invest_raw = _section(data, "investment_accounts", dict, "mapping")
    investment = {}
    for k, v in invest_raw.items():
        if not isinstance(v, str) or not v.strip():
            raise ConfigError("ledger.err_config_broker", key=k)
        investment[str(k)] = v.strip()

    invest_root = data.get("investment_root")
    if invest_root is not None:
        invest_root = _check_account(invest_root, "investment_root")

    fallback = _section(data, "fallback", dict, "mapping")
    for key in fallback:
        if key not in _FALLBACK_KEYS:
            raise ConfigError(
                "ledger.err_config_key",
                key=f"fallback.{key}",
                allowed=", ".join(_FALLBACK_KEYS),
            )
    fb_expense = fallback.get("expense")
    fb_income = fallback.get("income")
    if fb_expense is not None:
        fb_expense = _check_account(fb_expense, "fallback.expense")
    if fb_income is not None:
        fb_income = _check_account(fb_income, "fallback.income")

    operating = _currencies(_section(data, "operating_currency", list, "list"))
    commodities = _currencies(_section(data, "commodities", list, "list"))

    labels_raw = _section(data, "labels", dict, "mapping")
    for key in labels_raw:
        if key not in OVERRIDABLE:
            raise ConfigError(
                "ledger.err_config_key", key=f"labels.{key}", allowed=", ".join(OVERRIDABLE)
            )

    strict = fallback.get("strict", False)
    if not isinstance(strict, bool):
        raise ConfigError("ledger.err_config_bool", key="fallback.strict", value=strict)

    return LedgerConfig(
        accounts=accounts,
        investment_accounts=investment,
        investment_root=invest_root,
        fallback_expense=fb_expense,
        fallback_income=fb_income,
        fallback_strict=strict,
        operating_currency=operating,
        commodities=commodities,
        label_overrides={str(k): str(v) for k, v in labels_raw.items()},
        classify_by=classify_by,
        categories_expense=categories["expense"],
        categories_income=categories["income"],
    )


def load_ledger_config(path: Path | None) -> LedgerConfig:
    """Read *path* (``None`` -> defaults) and return the validated config."""
    if path is None:
        return LedgerConfig()
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ConfigError("ledger.err_config_read", path=path, reason=exc) from exc
    except OSError as exc:
        raise ConfigError("ledger.err_config_read", path=path, reason=exc) from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError("ledger.err_config_yaml", path=path, reason=exc) from exc
    return parse_ledger_config(data)
