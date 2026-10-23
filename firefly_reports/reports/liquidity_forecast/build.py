"""Builder of the liquidity_forecast report (pure: no I/O, Decimal money)."""

from datetime import date
from decimal import Decimal
from typing import Any

from firefly_reports import i18n
from firefly_reports.reports._money import _d


def build_liquidity_forecast(
    current_balance: Decimal,
    avg_income: Decimal,
    avg_variable_expense: Decimal,
    bills: list[dict[str, Any]],
    end_date: date,
    owner_name: str = "",
    currency_symbol: str = "EUR",
) -> dict[str, Any]:
    """Project 6-month liquidity forecast starting from the month after end_date."""
    from dateutil.relativedelta import relativedelta

    months = []
    running_balance = _d(current_balance)
    inc = _d(avg_income)
    var = _d(avg_variable_expense)

    # Forecast starts from the month after end_date
    start_forecast = end_date.replace(day=1) + relativedelta(months=1)

    for i in range(6):
        target_date = start_forecast + relativedelta(months=i)

        # Calculate Monthly Fixed Expense (Bills)
        monthly_fixed = Decimal("0")
        for b in bills:
            attrs = b.get("attributes", b)
            if not attrs.get("active", True):
                continue

            # expected amount
            amount_min = _d(attrs.get("amount_min", 0))
            amount_max = _d(attrs.get("amount_max", 0))
            expected = ((amount_min + amount_max) / 2).quantize(Decimal("0.01"))

            # check if bill hits this month
            freq = attrs.get("repeat_freq")
            next_date_str = attrs.get("next_expected_match")

            hits = False
            if not next_date_str:
                if freq == "monthly":
                    hits = True
            else:
                try:
                    next_date = date.fromisoformat(next_date_str[:10])
                    next_m = next_date.replace(day=1)
                    target_m = target_date.replace(day=1)

                    if freq == "monthly" or freq == "weekly" or next_m == target_m:
                        hits = True
                    elif next_m < target_m:
                        # project forward
                        curr = next_m
                        while curr <= target_m:
                            if curr == target_m:
                                hits = True
                                break
                            if freq == "quarterly":
                                curr += relativedelta(months=3)
                            elif freq == "half-year":
                                curr += relativedelta(months=6)
                            elif freq == "yearly":
                                curr += relativedelta(years=1)
                            else:
                                break
                except Exception:
                    if freq == "monthly":
                        hits = True

            if hits:
                monthly_fixed += expected

        # Accumulate: New Balance = Previous Balance + Income - Fixed - Variable
        outflow = monthly_fixed + var
        running_balance = running_balance + inc - outflow

        month_name = (
            i18n.current()
            .section("months")
            .get(f"{target_date.month:02d}", target_date.strftime("%m"))
        )
        months.append(
            {
                "month": target_date.strftime("%Y-%m"),
                "month_label": f"{month_name} {target_date.year}",
                "inflow": inc,
                "outflow": outflow,
                "fixed_outflow": monthly_fixed,
                "variable_outflow": var,
                "balance": running_balance,
            }
        )

    return {
        "owner": owner_name,
        "currency": currency_symbol,
        "start_date": end_date,
        "forecast_months": months,
        "final_balance": running_balance,
        "avg_income": inc,
        "avg_variable": var,
    }
