"""Builder of the savings_goals report (pure: no I/O, Decimal money)."""

from datetime import date
from decimal import Decimal
from typing import Any

from firefly_reports.reports._money import _d


def build_savings_goals(
    piggy_banks: list[dict[str, Any]],
    as_of: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Return savings goal progress for each piggy bank."""
    as_of_date = as_of
    from datetime import datetime

    goals = []
    total_saved = Decimal("0")
    total_target = Decimal("0")

    for pb in piggy_banks:
        attrs = pb.get("attributes", pb)

        target = _d(attrs.get("target_amount", 0))
        current = _d(attrs.get("current_amount", 0))
        pct = (current / target * 100).quantize(Decimal("0.1")) if target else Decimal("0")
        remaining = max(target - current, Decimal("0"))

        # monthly amount needed to reach the goal by the target date
        target_date_str = attrs.get("target_date") or ""
        monthly_needed = Decimal("0")
        months_left = None
        if target_date_str and remaining > 0:
            try:
                td = datetime.strptime(target_date_str[:10], "%Y-%m-%d").date()
                delta_months = max(
                    (td.year - as_of_date.year) * 12 + (td.month - as_of_date.month), 1
                )
                months_left = delta_months
                monthly_needed = (remaining / delta_months).quantize(Decimal("0.01"))
            except Exception:  # nosec B110
                pass

        # Linked account name: current API exposes `accounts[]` (v6.2+);
        # fall back to the legacy `account_name` / `account.name` fields.
        pb_accounts = attrs.get("accounts") or []
        account_name = (
            (pb_accounts[0].get("name", "") if pb_accounts else "")
            or attrs.get("account_name")
            or attrs.get("account", {}).get("name", "")
        )

        goals.append(
            {
                "name": attrs.get("name", ""),
                "target": target,
                "current": current,
                "remaining": remaining,
                "pct": pct,
                "start_date": (attrs.get("start_date") or "")[:10],
                "target_date": target_date_str[:10],
                "months_left": months_left,
                "monthly_needed": monthly_needed,
                "account_name": account_name,
                "notes": (attrs.get("notes") or "").strip()[:60],
            }
        )
        total_saved += current
        total_target += target

    goals.sort(key=lambda g: g["pct"], reverse=True)

    overall_pct = (
        (total_saved / total_target * 100).quantize(Decimal("0.1"))
        if total_target
        else Decimal("0")
    )

    return {
        "owner": owner_name,
        "as_of_date": as_of_date,
        "currency": currency_symbol,
        "goals": goals,
        "total_saved": total_saved,
        "total_target": total_target,
        "overall_pct": overall_pct,
        "goal_count": len(goals),
    }
