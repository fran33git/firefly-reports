"""Money coercion shared by every report builder."""

from decimal import ROUND_HALF_UP, Decimal
from typing import Any


def _d(value: Any) -> Decimal:
    """Coerce a value to Decimal with 2 decimal places, returning 0.00 on failure."""
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("0.00")
