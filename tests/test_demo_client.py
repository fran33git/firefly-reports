"""DemoClient serves the demo data offline, in the shape the pipeline expects."""

from datetime import date
from decimal import Decimal

from firefly_reports.demo.client import DemoClient


def test_demo_client_filters_transactions_by_period():
    c = DemoClient()
    txs = c.get_transactions(date(2025, 1, 1), date(2025, 12, 31))
    assert txs and all("2025-01-01" <= t["date"][:10] <= "2025-12-31" for t in txs)
    assert c.get_transactions(date(2024, 1, 1), date(2024, 12, 31))  # TXN_2024 served for YoY


def test_demo_client_is_offline_and_deterministic():
    assert DemoClient().get_asset_accounts() == DemoClient().get_asset_accounts()
    assert DemoClient().get_annual_totals(2025)["income"] == Decimal("52000.00")


def test_demo_client_history_and_unknown_year():
    c = DemoClient()
    assert [x["category"] for x in c.get_top_categories_for_year(2024)] == ["Rent", "Groceries"]
    assert c.get_top_categories_for_year(1999) == []
    assert c.get_annual_totals(1999)["net"] == Decimal("0")


def test_demo_client_account_transactions_match_either_side():
    c = DemoClient()
    txs = c.get_account_transactions(1, date(2025, 1, 1), date(2025, 12, 31))
    assert txs and all("1" in (t["source_id"], t["destination_id"]) for t in txs)
