"""Label helpers shared by several report builders (account roles, frequencies, liability types)."""

from firefly_reports import i18n

ROLE_ORDER = (
    "defaultAsset",
    "savingsAsset",
    "sharedAsset",
    "ccAsset",
    "cashWalletAsset",
    "other",
)


def account_role_label(role: str, default: str = "") -> str:
    """Translate a Firefly account role; unknown roles fall back to *default* or 'other'."""
    if not role:
        role = "other"
    if role in ROLE_ORDER:
        return str(i18n.t(f"account_roles.{role}"))
    return default or i18n.t("account_roles.other")


_FREQ_KEYS = ("weekly", "monthly", "quarterly", "half-year", "yearly")


def frequency_label(freq: str) -> str:
    """Translate a bill repeat frequency; unknown values pass through unchanged."""
    if freq in _FREQ_KEYS:
        return str(i18n.t(f"frequencies.{freq}"))
    return freq or "—"


_LIAB_TYPES = ("loan", "debt", "mortgage")


def liability_type_label(liab_type: str) -> str:
    """Translate a liability type; unknown types are capitalized, empty becomes 'other'."""
    if liab_type in _LIAB_TYPES:
        return str(i18n.t(f"liability_types.{liab_type}"))
    return liab_type.capitalize() if liab_type else i18n.t("liability_types.other")
