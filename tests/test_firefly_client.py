"""Tests for FireflyClient using responses (HTTP mock library)."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "firefly_reports"))

import json
import pytest
import responses as rsps_lib
from requests.exceptions import HTTPError

from firefly_client import FireflyClient, _redact

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
            {"id": "1", "attributes": {"group_title": None,
             "transactions": [{"type": "deposit", "amount": "100.00"}]}},
        ],
        "meta": {"pagination": {"total_pages": 2, "current_page": 1}},
    }
    page2 = {
        "data": [
            {"id": "2", "attributes": {"group_title": None,
             "transactions": [{"type": "withdrawal", "amount": "30.00"}]}},
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
        match=[rsps_lib.matchers.query_param_matcher({"start": "2025-01-01", "end": "2025-12-31", "type": "deposit", "limit": 100, "page": 1})]
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
        match=[rsps_lib.matchers.query_param_matcher({"start": "2025-01-01", "end": "2025-12-31", "type": "withdrawal", "limit": 100, "page": 1})]
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
        match=[rsps_lib.matchers.query_param_matcher({"start": "2025-01-01", "end": "2025-12-31", "type": "withdrawal", "limit": 100, "page": 1})]
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
