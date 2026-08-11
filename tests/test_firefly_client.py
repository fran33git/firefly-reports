"""Tests for FireflyClient using responses (HTTP mock library)."""

import pytest
import responses as rsps_lib
from requests.exceptions import HTTPError

from firefly_reports.firefly_client import FireflyClient, _dec, _redact

BASE = "https://firefly.test"
TOKEN = "test-token-abc"


@pytest.fixture
def client():
    return FireflyClient(BASE, TOKEN)


# ---------- _redact ----------


def test_redact_bearer_token():
    assert _redact("Bearer secret123") == "Bearer ***REDACTED***"


def test_redact_leaves_non_token_strings():
    assert _redact("plain text") == "plain text"


# ---------- get_transactions ----------


@rsps_lib.activate
def test_get_transactions_single_page(client):
    rsps_lib.add(
        rsps_lib.GET,
        f"{BASE}/api/v1/transactions",
        json={
            "data": [
                {
                    "id": "1",
                    "attributes": {
                        "group_title": None,
                        "transactions": [
                            {"type": "withdrawal", "amount": "50.00", "date": "2025-01-10"},
                        ],
                    },
                }
            ],
            "meta": {"pagination": {"total_pages": 1, "current_page": 1}},
        },
    )
    result = client.get_transactions(
        __import__("datetime").date(2025, 1, 1),
        __import__("datetime").date(2025, 1, 31),
    )
    assert len(result) == 1
    assert result[0]["type"] == "withdrawal"
    assert result[0]["group_id"] == "1"


@rsps_lib.activate
def test_get_transactions_pagination(client):
    """Two-page response should be merged into a single flat list."""
    page1 = {
        "data": [
            {
                "id": "1",
                "attributes": {
                    "group_title": None,
                    "transactions": [{"type": "deposit", "amount": "100.00"}],
                },
            },
        ],
        "meta": {"pagination": {"total_pages": 2, "current_page": 1}},
    }
    page2 = {
        "data": [
            {
                "id": "2",
                "attributes": {
                    "group_title": None,
                    "transactions": [{"type": "withdrawal", "amount": "30.00"}],
                },
            },
        ],
        "meta": {"pagination": {"total_pages": 2, "current_page": 2}},
    }
    rsps_lib.add(rsps_lib.GET, f"{BASE}/api/v1/transactions", json=page1)
    rsps_lib.add(rsps_lib.GET, f"{BASE}/api/v1/transactions", json=page2)

    result = client.get_transactions(
        __import__("datetime").date(2025, 1, 1),
        __import__("datetime").date(2025, 12, 31),
    )
    assert len(result) == 2
    assert result[0]["type"] == "deposit"
    assert result[1]["type"] == "withdrawal"


@rsps_lib.activate
def test_get_transactions_flattens_splits(client):
    """A transaction group with two splits should produce two dicts."""
    rsps_lib.add(
        rsps_lib.GET,
        f"{BASE}/api/v1/transactions",
        json={
            "data": [
                {
                    "id": "99",
                    "attributes": {
                        "group_title": "Split tx",
                        "transactions": [
                            {"type": "withdrawal", "amount": "20.00"},
                            {"type": "withdrawal", "amount": "30.00"},
                        ],
                    },
                }
            ],
            "meta": {"pagination": {"total_pages": 1}},
        },
    )
    result = client.get_transactions(
        __import__("datetime").date(2025, 1, 1),
        __import__("datetime").date(2025, 1, 31),
    )
    assert len(result) == 2
    assert all(tx["group_id"] == "99" for tx in result)


# ---------- HTTP error handling ----------


@rsps_lib.activate
def test_http_401_raises(client):
    rsps_lib.add(rsps_lib.GET, f"{BASE}/api/v1/transactions", status=401)
    with pytest.raises(HTTPError):
        client.get_transactions(
            __import__("datetime").date(2025, 1, 1),
            __import__("datetime").date(2025, 1, 31),
        )


@rsps_lib.activate
def test_http_500_raises(client):
    rsps_lib.add(rsps_lib.GET, f"{BASE}/api/v1/transactions", status=500)
    with pytest.raises(HTTPError):
        client.get_transactions(
            __import__("datetime").date(2025, 1, 1),
            __import__("datetime").date(2025, 1, 31),
        )


# ---------- get_asset_accounts ----------


@rsps_lib.activate
def test_get_asset_accounts_returns_list(client):
    rsps_lib.add(
        rsps_lib.GET,
        f"{BASE}/api/v1/accounts",
        json={
            "data": [
                {"id": "1", "attributes": {"name": "Checking", "type": "asset"}},
            ],
            "meta": {"pagination": {"total_pages": 1}},
        },
    )
    result = client.get_asset_accounts()
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["id"] == "1"


# ---------- Annual Aggregates ----------


@rsps_lib.activate
def test_get_annual_totals(client):
    # Mock deposits
    rsps_lib.add(
        rsps_lib.GET,
        f"{BASE}/api/v1/transactions",
        json={
            "data": [
                {
                    "id": "1",
                    "attributes": {
                        "transactions": [
                            {"type": "deposit", "amount": "1000.00"},
                        ],
                    },
                }
            ],
            "meta": {"pagination": {"total_pages": 1}},
        },
        match=[
            rsps_lib.matchers.query_param_matcher(
                {
                    "start": "2025-01-01",
                    "end": "2025-12-31",
                    "type": "deposit",
                    "limit": 100,
                    "page": 1,
                }
            )
        ],
    )
    # Mock withdrawals
    rsps_lib.add(
        rsps_lib.GET,
        f"{BASE}/api/v1/transactions",
        json={
            "data": [
                {
                    "id": "2",
                    "attributes": {
                        "transactions": [
                            {"type": "withdrawal", "amount": "400.00"},
                            {"type": "withdrawal", "amount": "100.00"},
                        ],
                    },
                }
            ],
            "meta": {"pagination": {"total_pages": 1}},
        },
        match=[
            rsps_lib.matchers.query_param_matcher(
                {
                    "start": "2025-01-01",
                    "end": "2025-12-31",
                    "type": "withdrawal",
                    "limit": 100,
                    "page": 1,
                }
            )
        ],
    )

    from decimal import Decimal

    result = client.get_annual_totals(2025)
    assert result["income"] == Decimal("1000.00")
    assert result["expense"] == Decimal("500.00")
    assert result["net"] == Decimal("500.00")


@rsps_lib.activate
def test_get_top_categories_for_year(client):
    rsps_lib.add(
        rsps_lib.GET,
        f"{BASE}/api/v1/transactions",
        json={
            "data": [
                {
                    "id": "1",
                    "attributes": {
                        "transactions": [
                            {"type": "withdrawal", "amount": "50.00", "category_name": "Food"},
                            {"type": "withdrawal", "amount": "30.00", "category_name": "Transport"},
                            {"type": "withdrawal", "amount": "20.00", "category_name": "Food"},
                        ],
                    },
                }
            ],
            "meta": {"pagination": {"total_pages": 1}},
        },
        match=[
            rsps_lib.matchers.query_param_matcher(
                {
                    "start": "2025-01-01",
                    "end": "2025-12-31",
                    "type": "withdrawal",
                    "limit": 100,
                    "page": 1,
                }
            )
        ],
    )

    from decimal import Decimal

    result = client.get_top_categories_for_year(2025, limit=2)
    assert len(result) == 2
    assert result[0]["category"] == "Food"
    assert result[0]["amount"] == Decimal("70.00")
    assert result[1]["category"] == "Transport"
    assert result[1]["amount"] == Decimal("30.00")


# ---------- get_budget_limits ----------


@rsps_lib.activate
def test_get_budget_limits_paginates(client):
    """Budget limits are paginated: all pages must be merged."""
    page1 = {
        "data": [{"id": "1", "attributes": {"amount": "500.00"}}],
        "meta": {"pagination": {"total_pages": 2, "current_page": 1}},
    }
    page2 = {
        "data": [{"id": "2", "attributes": {"amount": "300.00"}}],
        "meta": {"pagination": {"total_pages": 2, "current_page": 2}},
    }
    rsps_lib.add(rsps_lib.GET, f"{BASE}/api/v1/budgets/5/limits", json=page1)
    rsps_lib.add(rsps_lib.GET, f"{BASE}/api/v1/budgets/5/limits", json=page2)

    from datetime import date

    result = client.get_budget_limits("5", date(2025, 1, 1), date(2025, 12, 31))
    assert len(result) == 2
    assert result[0]["id"] == "1"
    assert result[1]["id"] == "2"


# ---------- transaction links ----------


@rsps_lib.activate
def test_get_transaction_links_resolves_type_names(client):
    rsps_lib.add(
        rsps_lib.GET,
        f"{BASE}/api/v1/link-types",
        json={
            "data": [{"id": "9", "attributes": {"name": "Reimbursement"}}],
            "meta": {"pagination": {"total_pages": 1}},
        },
    )
    rsps_lib.add(
        rsps_lib.GET,
        f"{BASE}/api/v1/transaction-links",
        json={
            "data": [
                {
                    "id": "1",
                    "attributes": {
                        "link_type_id": "9",
                        "inward_id": "501",
                        "outward_id": "500",
                        "notes": None,
                    },
                }
            ],
            "meta": {"pagination": {"total_pages": 1}},
        },
    )
    links = client.get_transaction_links()
    assert links == [
        {
            "id": "1",
            "link_type_id": "9",
            "link_type_name": "Reimbursement",
            "inward_id": "501",
            "outward_id": "500",
            "notes": "",
        }
    ]


@rsps_lib.activate
def test_get_transaction_journal_by_id(client):
    rsps_lib.add(
        rsps_lib.GET,
        f"{BASE}/api/v1/transaction-journals/101",
        json={
            "data": {
                "id": "101",
                "attributes": {
                    "type": "deposit",
                    "amount": "50.00",
                    "date": "2025-01-15T00:00:00+01:00",
                    "description": "Dinner Reimbursement",
                },
            }
        },
    )
    journal = client.get_transaction_journal_by_id("101")
    assert journal["transaction_journal_id"] == "101"
    assert journal["type"] == "deposit"
    assert journal["description"] == "Dinner Reimbursement"


# ---------- get_about / get_about_user ----------


@rsps_lib.activate
def test_get_about(client):
    rsps_lib.add(
        rsps_lib.GET,
        f"{BASE}/api/v1/about",
        json={
            "data": {
                "version": "6.2.10",
                "api_version": "2.1.0",
                "os": "Linux",
                "php_version": "8.3.9",
                "driver": "mysql",
            }
        },
    )
    result = client.get_about()
    assert result["version"] == "6.2.10"
    assert result["php_version"] == "8.3.9"


@rsps_lib.activate
def test_get_about_user(client):
    rsps_lib.add(
        rsps_lib.GET,
        f"{BASE}/api/v1/about/user",
        json={"data": {"attributes": {"email": "test@example.com", "role": "owner"}}},
    )
    result = client.get_about_user()
    assert result["email"] == "test@example.com"
    assert result["role"] == "owner"


@rsps_lib.activate
def test_get_about_unexpected_shape(client):
    rsps_lib.add(rsps_lib.GET, f"{BASE}/api/v1/about", json={"data": []})
    assert client.get_about() == {}


@rsps_lib.activate
def test_get_about_http_error_returns_empty(client):
    rsps_lib.add(rsps_lib.GET, f"{BASE}/api/v1/about", status=500)
    assert client.get_about() == {}


@rsps_lib.activate
def test_get_about_user_http_error_returns_empty(client):
    rsps_lib.add(rsps_lib.GET, f"{BASE}/api/v1/about/user", status=500)
    assert client.get_about_user() == {}


# ---------- get_transaction_by_id ----------


@rsps_lib.activate
def test_get_transaction_by_id(client):
    rsps_lib.add(
        rsps_lib.GET,
        f"{BASE}/api/v1/transactions/42",
        json={
            "data": {
                "id": "42",
                "attributes": {
                    "group_title": "Group",
                    "transactions": [{"type": "withdrawal", "amount": "12.50"}],
                },
            }
        },
    )
    tx = client.get_transaction_by_id("42")
    assert tx["type"] == "withdrawal"
    assert tx["group_id"] == "42"
    assert tx["group_title"] == "Group"


@rsps_lib.activate
def test_get_transaction_by_id_empty_data(client):
    rsps_lib.add(rsps_lib.GET, f"{BASE}/api/v1/transactions/42", json={"data": {}})
    assert client.get_transaction_by_id("42") == {}


@rsps_lib.activate
def test_get_transaction_by_id_no_splits(client):
    rsps_lib.add(
        rsps_lib.GET,
        f"{BASE}/api/v1/transactions/42",
        json={"data": {"id": "42", "attributes": {"transactions": []}}},
    )
    assert client.get_transaction_by_id("42") == {}


# ---------- _get_single 429 retry ----------


@rsps_lib.activate
def test_get_single_retries_on_429():
    """A 429 with Retry-After should trigger one retry before giving up."""
    fast = FireflyClient(BASE, TOKEN, request_delay=0)
    url = f"{BASE}/api/v1/transaction-journals/7"
    rsps_lib.add(rsps_lib.GET, url, status=429, headers={"Retry-After": "0"})
    rsps_lib.add(
        rsps_lib.GET,
        url,
        json={"data": {"id": "7", "attributes": {"type": "deposit", "amount": "5.00"}}},
    )
    journal = fast.get_transaction_journal_by_id("7")
    assert journal["transaction_journal_id"] == "7"
    assert len(rsps_lib.calls) == 2


@rsps_lib.activate
def test_get_single_429_twice_raises():
    """A persistent 429 should raise after the single retry."""
    fast = FireflyClient(BASE, TOKEN, request_delay=0)
    url = f"{BASE}/api/v1/transaction-journals/7"
    rsps_lib.add(rsps_lib.GET, url, status=429)
    rsps_lib.add(rsps_lib.GET, url, status=429)
    with pytest.raises(HTTPError):
        fast.get_transaction_journal_by_id("7")


# ---------- get_transaction_journal_by_id edge ----------


@rsps_lib.activate
def test_get_transaction_journal_by_id_empty_attributes(client):
    rsps_lib.add(
        rsps_lib.GET,
        f"{BASE}/api/v1/transaction-journals/101",
        json={"data": {"id": "101", "attributes": {}}},
    )
    assert client.get_transaction_journal_by_id("101") == {}


# ---------- fetch_link_details ----------


def test_fetch_link_details_empty_list(client):
    assert client.fetch_link_details([]) == []


@rsps_lib.activate
def test_fetch_link_details_success():
    fast = FireflyClient(BASE, TOKEN, request_delay=0)
    for jid in ("1", "2"):
        rsps_lib.add(
            rsps_lib.GET,
            f"{BASE}/api/v1/transaction-journals/{jid}",
            json={"data": {"id": jid, "attributes": {"type": "deposit", "amount": "1.00"}}},
        )
    result = fast.fetch_link_details(["1", "2"])
    assert len(result) == 2
    assert result[0]["transaction_journal_id"] == "1"
    assert result[1]["transaction_journal_id"] == "2"


@rsps_lib.activate
def test_fetch_link_details_skips_failures():
    """A failing journal ID should be skipped, not abort the whole fetch."""
    fast = FireflyClient(BASE, TOKEN, request_delay=0)
    rsps_lib.add(
        rsps_lib.GET,
        f"{BASE}/api/v1/transaction-journals/1",
        json={"data": {"id": "1", "attributes": {"type": "deposit", "amount": "1.00"}}},
    )
    rsps_lib.add(rsps_lib.GET, f"{BASE}/api/v1/transaction-journals/2", status=500)
    result = fast.fetch_link_details(["1", "2"])
    assert len(result) == 1
    assert result[0]["transaction_journal_id"] == "1"


# ---------- Insight endpoints ----------


@rsps_lib.activate
def test_get_expense_by_category(client):
    from datetime import date

    rsps_lib.add(
        rsps_lib.GET,
        f"{BASE}/api/v1/insight/expense/category",
        json=[{"id": "1", "name": "Food", "difference": "-100.00"}],
    )
    result = client.get_expense_by_category(date(2025, 1, 1), date(2025, 1, 31))
    assert result == [{"id": "1", "name": "Food", "difference": "-100.00"}]


@rsps_lib.activate
def test_get_expense_by_category_non_list_returns_empty(client):
    from datetime import date

    rsps_lib.add(rsps_lib.GET, f"{BASE}/api/v1/insight/expense/category", json={"data": []})
    assert client.get_expense_by_category(date(2025, 1, 1), date(2025, 1, 31)) == []


@rsps_lib.activate
def test_get_income_by_category(client):
    from datetime import date

    rsps_lib.add(
        rsps_lib.GET,
        f"{BASE}/api/v1/insight/income/category",
        json=[{"id": "2", "name": "Salary", "difference": "2000.00"}],
    )
    result = client.get_income_by_category(date(2025, 1, 1), date(2025, 1, 31))
    assert result[0]["name"] == "Salary"


@rsps_lib.activate
def test_get_expense_total(client):
    from datetime import date

    rsps_lib.add(
        rsps_lib.GET,
        f"{BASE}/api/v1/insight/expense/total",
        json=[{"difference_float": -500.0, "currency_code": "EUR"}],
    )
    result = client.get_expense_total(date(2025, 1, 1), date(2025, 12, 31))
    assert result[0]["difference_float"] == -500.0


@rsps_lib.activate
def test_get_income_total_non_list_returns_empty(client):
    from datetime import date

    rsps_lib.add(rsps_lib.GET, f"{BASE}/api/v1/insight/income/total", json={})
    assert client.get_income_total(date(2025, 1, 1), date(2025, 12, 31)) == []


# ---------- Accounts ----------


@rsps_lib.activate
def test_get_account_transactions(client):
    from datetime import date

    rsps_lib.add(
        rsps_lib.GET,
        f"{BASE}/api/v1/accounts/3/transactions",
        json={
            "data": [
                {
                    "id": "10",
                    "attributes": {
                        "group_title": None,
                        "transactions": [{"type": "withdrawal", "amount": "9.99"}],
                    },
                }
            ],
            "meta": {"pagination": {"total_pages": 1}},
        },
    )
    result = client.get_account_transactions(3, date(2025, 1, 1), date(2025, 1, 31))
    assert len(result) == 1
    assert result[0]["group_id"] == "10"


# ---------- Summary ----------


@rsps_lib.activate
def test_get_summary_basic(client):
    from datetime import date

    rsps_lib.add(
        rsps_lib.GET,
        f"{BASE}/api/v1/summary/basic",
        json={"balance-in-EUR": {"monetary_value": 1234.56}},
    )
    result = client.get_summary_basic(date(2025, 1, 1), date(2025, 1, 31))
    assert result["balance-in-EUR"]["monetary_value"] == 1234.56


# ---------- get_about_user edge ----------


@rsps_lib.activate
def test_get_about_user_unexpected_shape(client):
    rsps_lib.add(rsps_lib.GET, f"{BASE}/api/v1/about/user", json={"data": []})
    assert client.get_about_user() == {}


# ---------- Budgets / Bills / Piggy banks / Liabilities ----------


@rsps_lib.activate
def test_get_budgets(client):
    rsps_lib.add(
        rsps_lib.GET,
        f"{BASE}/api/v1/budgets",
        json={
            "data": [{"id": "5", "attributes": {"name": "Groceries"}}],
            "meta": {"pagination": {"total_pages": 1}},
        },
    )
    result = client.get_budgets()
    assert result[0]["attributes"]["name"] == "Groceries"


@rsps_lib.activate
def test_get_budget_transactions(client):
    from datetime import date

    rsps_lib.add(
        rsps_lib.GET,
        f"{BASE}/api/v1/budgets/5/transactions",
        json={
            "data": [
                {
                    "id": "20",
                    "attributes": {
                        "group_title": None,
                        "transactions": [{"type": "withdrawal", "amount": "15.00"}],
                    },
                }
            ],
            "meta": {"pagination": {"total_pages": 1}},
        },
    )
    result = client.get_budget_transactions("5", date(2025, 1, 1), date(2025, 1, 31))
    assert len(result) == 1
    assert result[0]["group_id"] == "20"


@rsps_lib.activate
def test_get_bills(client):
    rsps_lib.add(
        rsps_lib.GET,
        f"{BASE}/api/v1/bills",
        json={
            "data": [{"id": "1", "attributes": {"name": "Rent"}}],
            "meta": {"pagination": {"total_pages": 1}},
        },
    )
    result = client.get_bills()
    assert result[0]["attributes"]["name"] == "Rent"


@rsps_lib.activate
def test_get_bill_transactions(client):
    from datetime import date

    rsps_lib.add(
        rsps_lib.GET,
        f"{BASE}/api/v1/bills/1/transactions",
        json={
            "data": [
                {
                    "id": "30",
                    "attributes": {
                        "group_title": None,
                        "transactions": [{"type": "withdrawal", "amount": "800.00"}],
                    },
                }
            ],
            "meta": {"pagination": {"total_pages": 1}},
        },
    )
    result = client.get_bill_transactions("1", date(2025, 1, 1), date(2025, 1, 31))
    assert len(result) == 1
    assert result[0]["group_id"] == "30"


@rsps_lib.activate
def test_get_piggy_banks(client):
    rsps_lib.add(
        rsps_lib.GET,
        f"{BASE}/api/v1/piggy-banks",
        json={
            "data": [{"id": "1", "attributes": {"name": "Holiday"}}],
            "meta": {"pagination": {"total_pages": 1}},
        },
    )
    result = client.get_piggy_banks()
    assert result[0]["attributes"]["name"] == "Holiday"


@rsps_lib.activate
def test_get_liability_accounts(client):
    rsps_lib.add(
        rsps_lib.GET,
        f"{BASE}/api/v1/accounts",
        json={
            "data": [{"id": "7", "attributes": {"name": "Mortgage", "type": "liabilities"}}],
            "meta": {"pagination": {"total_pages": 1}},
        },
    )
    result = client.get_liability_accounts()
    assert result[0]["id"] == "7"


@rsps_lib.activate
def test_get_liability_transactions(client):
    from datetime import date

    rsps_lib.add(
        rsps_lib.GET,
        f"{BASE}/api/v1/accounts/7/transactions",
        json={
            "data": [
                {
                    "id": "40",
                    "attributes": {
                        "group_title": None,
                        "transactions": [{"type": "withdrawal", "amount": "1200.00"}],
                    },
                }
            ],
            "meta": {"pagination": {"total_pages": 1}},
        },
    )
    result = client.get_liability_transactions(7, date(2025, 1, 1), date(2025, 1, 31))
    assert len(result) == 1
    assert result[0]["group_id"] == "40"


# ---------- _dec ----------


def test_dec_invalid_value_returns_zero():
    from decimal import Decimal

    assert _dec("not-a-number") == Decimal("0")


def test_dec_valid_value():
    from decimal import Decimal

    assert _dec("12.34") == Decimal("12.34")
