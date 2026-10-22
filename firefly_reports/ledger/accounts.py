"""Firefly account -> ledger account resolution (normalisation, overrides, fallbacks)."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

from firefly_reports.ledger.errors import AccountCollisionError
from firefly_reports.ledger.labels import LedgerLabels
from firefly_reports.ledger.mapping import LedgerConfig

OPENING_BALANCES = "Equity:Opening-Balances"
RECONCILIATION = "Equity:Reconciliation"
IMPORTS = "Equity:Imports"
CASH = "Assets:Cash"

# Letters NFKD cannot decompose.
_TRANSLIT = str.maketrans(
    {
        "ß": "ss",
        "ø": "o",
        "Ø": "O",
        "æ": "ae",
        "Æ": "AE",
        "œ": "oe",
        "Œ": "OE",
        "đ": "d",
        "Đ": "D",
        "ł": "l",
        "Ł": "L",
    }
)

# Firefly account type (lowercased) -> account kind.
_KIND_BY_TYPE = {
    "asset account": "asset",
    "default account": "asset",
    "cash account": "cash",
    "expense account": "expense",
    "beneficiary account": "expense",
    "revenue account": "income",
    "loan": "liability",
    "debt": "liability",
    "mortgage": "liability",
    "liability credit account": "opening",
    "liability credit": "opening",
    "import account": "import",
    "credit card": "asset",
    "initial balance account": "opening",
    "initial balance": "opening",
    "reconciliation account": "reconciliation",
    "reconciliation": "reconciliation",
}
_ROOT_BY_KIND = {
    "asset": "Assets",
    "expense": "Expenses",
    "income": "Income",
    "liability": "Liabilities",
}
# Root expected from the account type, used to warn about cross-root name mappings.
_EXPECTED_ROOT = {
    **_ROOT_BY_KIND,
    "opening": "Equity",
    "reconciliation": "Equity",
    "import": "Equity",
    "cash": "Assets",
}
# Firefly's placeholder for transactions without a counterpart.
_PLACEHOLDER_NAMES = {"(no name)", "(empty)", ""}


def normalize_component(text: str) -> str:
    """Turn free text into one valid Beancount account component ('' if impossible).

    Accents are transliterated, anything that is not a letter or digit becomes a
    dash, and the first letter is capitalised (components must start with an
    uppercase letter or a digit).
    """
    text = unicodedata.normalize("NFKD", text.translate(_TRANSLIT))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    return text


def classify(firefly_type: str | None) -> str:
    """Account kind for a Firefly account type string ('unknown' if not recognised)."""
    return _KIND_BY_TYPE.get((firefly_type or "").strip().lower(), "unknown")


@dataclass(frozen=True)
class Resolution:
    """How one Firefly account was mapped.

    *origin* is one of ``explicit`` (``accounts`` entry), ``investment``,
    ``special`` (opening balance / reconciliation / import / cash), ``fallback`` or
    ``auto`` (normalised name).
    """

    name: str
    firefly_type: str
    kind: str
    account: str
    origin: str


@dataclass(frozen=True)
class CategoryUse:
    """How one Firefly category was mapped for one direction (*lane*: expense/income).

    *origin* is ``explicit`` (listed in the mapping), ``fallback`` (no category, an
    unusable name or ``fallback.strict``) or ``auto`` (normalised name). *splits*
    counts the splits that used it; the uncategorised bucket has ``name == ""``.
    """

    lane: str
    name: str
    account: str
    origin: str
    splits: int


# Account kinds whose Firefly accounts are classification targets rather than real accounts.
_COUNTERPART_KINDS = ("expense", "income", "unknown")


class AccountResolver:
    """Resolves Firefly accounts to ledger accounts and tracks name collisions.

    Precedence: explicit ``accounts`` entry (numeric id first, then name) >
    ``investment_accounts`` > special accounts (cash / opening balance /
    reconciliation / import) > fallback (strict mode or empty name) > normalised name.
    Collisions between automatically generated names are collected and raised
    by ``raise_on_collisions`` (never silent). Explicit name mappings that land
    in a root different from the one expected for the account type are kept but
    reported by ``warnings`` (one per account).
    """

    def __init__(self, config: LedgerConfig, labels: LedgerLabels) -> None:
        self._config = config
        self._investment_root = config.investment_root or labels.investment_root
        self._fallback = {
            "expense": config.fallback_expense or labels.fallback_expense,
            "income": config.fallback_income or labels.fallback_income,
        }
        # ledger account -> {firefly identity: explicit?}
        self._seen: dict[str, dict[tuple[str, str], bool]] = {}
        self._resolutions: dict[tuple[str, str], Resolution] = {}
        self._warnings: list[tuple[str, str, str]] = []
        self._warned: set[tuple[str, str]] = set()
        self._category_splits: Counter[tuple[str, str]] = Counter()

    def _record(
        self, account: str, kind: str, name: str, origin: str, firefly_type: str | None
    ) -> str:
        self._seen.setdefault(account, {})[(kind, name)] = origin != "auto"
        self._resolutions[(kind, name)] = Resolution(
            name=name,
            firefly_type=(firefly_type or "").strip(),
            kind=kind,
            account=account,
            origin=origin,
        )
        return account

    def resolve(
        self,
        name: str | None,
        firefly_type: str | None,
        account_id: object = None,
        side: str = "destination",
    ) -> str:
        """Return the ledger account for a Firefly account.

        *side* ('source' or 'destination') only decides which fallback applies
        to account types we do not recognise.
        """
        clean = (name or "").strip()
        kind = classify(firefly_type)
        # An explicit entry matches by numeric id before by name: ids are unique,
        # names can be shared by several account types.
        candidates: list[tuple[str, str]] = []
        if account_id not in (None, ""):
            candidates.append((str(account_id), "id"))
        if clean:
            candidates.append((clean, "name"))

        for key, matched_by in candidates:
            if key in self._config.accounts:
                account = self._config.accounts[key]
                if matched_by == "name":
                    self._warn_on_cross_root(clean, firefly_type, kind, account)
                return self._record(account, kind, clean, "explicit", firefly_type)

        if kind == "asset":
            for key, _ in candidates:
                broker = self._config.investment_accounts.get(key)
                if broker:
                    component = normalize_component(broker) or "Broker"
                    account = f"{self._investment_root}:{component}:Cash"
                    return self._record(account, kind, clean, "investment", firefly_type)

        if kind == "opening":
            return self._record(OPENING_BALANCES, kind, clean, "special", firefly_type)
        if kind == "reconciliation":
            return self._record(RECONCILIATION, kind, clean, "special", firefly_type)
        if kind == "import":
            # Firefly's technical counterpart for imported transactions, not a real account.
            return self._record(IMPORTS, kind, clean, "special", firefly_type)
        if kind == "cash":
            return self._record(CASH, kind, clean, "special", firefly_type)

        if kind == "unknown":
            kind = "expense" if side == "destination" else "income"
        fallback_kind = kind if kind in self._fallback else None
        if fallback_kind and (self._config.fallback_strict or clean.lower() in _PLACEHOLDER_NAMES):
            return self._record(
                self._fallback[fallback_kind], kind, clean, "fallback", firefly_type
            )

        component = normalize_component(clean) if clean.lower() not in _PLACEHOLDER_NAMES else ""
        if not component:
            # Asset/liability without a usable name: park it in the matching fallback root.
            component = "Unnamed"
        return self._record(f"{_ROOT_BY_KIND[kind]}:{component}", kind, clean, "auto", firefly_type)

    def resolutions(self) -> list[Resolution]:
        """Every Firefly account seen so far (categories excluded), by ledger account then name."""
        accounts = (r for r in self._resolutions.values() if not r.kind.startswith("category-"))
        return sorted(accounts, key=lambda r: (r.account, r.name))

    @property
    def classify_by(self) -> str:
        return self._config.classify_by

    @staticmethod
    def is_counterpart(firefly_type: str | None) -> bool:
        """True for expense/revenue accounts (and types we do not recognise)."""
        return classify(firefly_type) in _COUNTERPART_KINDS

    @staticmethod
    def lane(firefly_type: str | None, side: str) -> str:
        """``expense`` or ``income`` for a counterpart account; unknown types follow *side*."""
        kind = classify(firefly_type)
        if kind in ("expense", "income"):
            return kind
        return "expense" if side == "destination" else "income"

    def resolve_category(self, name: str | None, lane: str) -> str:
        """Ledger account for a Firefly category used as an expense or income."""
        clean = (name or "").strip()
        kind = f"category-{lane}"
        self._category_splits[(lane, clean)] += 1
        mapping = (
            self._config.categories_expense if lane == "expense" else self._config.categories_income
        )
        if clean in mapping:
            return self._record(mapping[clean], kind, clean, "explicit", "category")
        fallback = self._fallback[lane]
        if not clean or clean.lower() in _PLACEHOLDER_NAMES or self._config.fallback_strict:
            return self._record(fallback, kind, clean, "fallback", "category")
        component = normalize_component(clean)
        if not component:
            return self._record(fallback, kind, clean, "fallback", "category")
        root = _ROOT_BY_KIND[lane]
        return self._record(f"{root}:{component}", kind, clean, "auto", "category")

    def category_uses(self) -> list[CategoryUse]:
        """Every category seen so far: by lane, then most used first, then name."""
        uses = [
            CategoryUse(
                lane=r.kind.removeprefix("category-"),
                name=r.name,
                account=r.account,
                origin=r.origin,
                splits=self._category_splits[(r.kind.removeprefix("category-"), r.name)],
            )
            for r in self._resolutions.values()
            if r.kind.startswith("category-")
        ]
        return sorted(uses, key=lambda u: (u.lane, -u.splits, u.name))

    def unmapped_categories(self) -> list[CategoryUse]:
        """Named categories seen in the data that the mapping does not list for their lane."""
        return [u for u in self.category_uses() if u.name and u.origin != "explicit"]

    def unused_category_keys(self) -> list[tuple[str, str]]:
        """Mapping keys (lane, name) never seen in the data, e.g. after a rename in Firefly."""
        seen = set(self._category_splits)
        keys = [("expense", k) for k in self._config.categories_expense]
        keys += [("income", k) for k in self._config.categories_income]
        return sorted(key for key in keys if key not in seen)

    def warnings(self) -> list[tuple[str, str, str]]:
        """(name, firefly type, account) of explicit *name* mappings whose root
        differs from the one expected for the account type. One entry per
        account; the mapping itself stays valid."""
        return list(self._warnings)

    def _warn_on_cross_root(
        self, name: str, firefly_type: str | None, kind: str, account: str
    ) -> None:
        expected = _EXPECTED_ROOT.get(kind)
        identity = (kind, name)
        if not expected or identity in self._warned:
            return
        if account.split(":", 1)[0] != expected:
            self._warned.add(identity)
            self._warnings.append((name, (firefly_type or "").strip(), account))

    def collisions(self) -> dict[str, list[str]]:
        """Ledger account -> original Firefly names, for auto-generated name clashes."""
        out: dict[str, list[str]] = {}
        for account, identities in sorted(self._seen.items()):
            if len(identities) > 1 and not all(identities.values()):
                out[account] = sorted(name for _, name in identities)
        return out

    def raise_on_collisions(self) -> None:
        clashes = self.collisions()
        if clashes:
            details = "\n".join(
                f"  {account}  <-  " + ", ".join(repr(n) for n in names)
                for account, names in clashes.items()
            )
            raise AccountCollisionError("ledger.err_collision", details=details)
