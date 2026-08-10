"""Shared pytest fixtures for firefly-reports tests.

All fixtures are derived from the mock data in demo.py so tests run
without a live Firefly III instance.
"""

from datetime import date

import pytest

from firefly_reports import i18n


@pytest.fixture(scope="session", autouse=True)
def setup_i18n():
    """Load English translations once for the entire test session."""
    i18n.load("en")


@pytest.fixture
def txn_2025() -> list[dict]:
    """23 transactions spanning Jan-May 2025 (deposits, withdrawals, transfers)."""
    return [
        {
            "type": "deposit",
            "date": "2025-01-15",
            "amount": "3200.00",
            "description": "Invoice #001 - Rossi S.r.l.",
            "source_name": "Rossi S.r.l.",
            "destination_name": "Main Account",
            "category_name": "Professional Fees",
            "budget_name": None,
            "tags": ["invoice", "tax"],
            "notes": "",
            "source_id": "10",
            "destination_id": "1",
        },
        {
            "type": "deposit",
            "date": "2025-02-10",
            "amount": "2800.00",
            "description": "Invoice #002 - Verde SpA",
            "source_name": "Verde SpA",
            "destination_name": "Main Account",
            "category_name": "Professional Fees",
            "budget_name": None,
            "tags": ["invoice"],
            "notes": "",
            "source_id": "11",
            "destination_id": "1",
        },
        {
            "type": "deposit",
            "date": "2025-03-05",
            "amount": "1500.00",
            "description": "Consulting - Startup Blue",
            "source_name": "Startup Blue",
            "destination_name": "Main Account",
            "category_name": "Consulting",
            "budget_name": None,
            "tags": ["consulting"],
            "notes": "",
            "source_id": "12",
            "destination_id": "1",
        },
        {
            "type": "deposit",
            "date": "2025-03-28",
            "amount": "2900.00",
            "description": "Invoice #003 - Rossi S.r.l.",
            "source_name": "Rossi S.r.l.",
            "destination_name": "Main Account",
            "category_name": "Professional Fees",
            "budget_name": None,
            "tags": ["invoice", "tax"],
            "notes": "",
            "source_id": "10",
            "destination_id": "1",
        },
        {
            "type": "deposit",
            "date": "2025-04-12",
            "amount": "3100.00",
            "description": "Invoice #004 - Verde SpA",
            "source_name": "Verde SpA",
            "destination_name": "Main Account",
            "category_name": "Professional Fees",
            "budget_name": None,
            "tags": ["invoice"],
            "notes": "",
            "source_id": "11",
            "destination_id": "1",
        },
        {
            "type": "deposit",
            "date": "2025-05-20",
            "amount": "3050.00",
            "description": "Invoice #005 - Yellow Srl",
            "source_name": "Yellow Srl",
            "destination_name": "Main Account",
            "category_name": "Professional Fees",
            "budget_name": None,
            "tags": ["invoice"],
            "notes": "",
            "source_id": "14",
            "destination_id": "1",
        },
        {
            "type": "withdrawal",
            "date": "2025-01-05",
            "amount": "280.00",
            "description": "Office rent - January",
            "source_name": "Main Account",
            "destination_name": "Landlord",
            "category_name": "Office Rent",
            "budget_name": "Fixed Costs",
            "tags": ["recurring"],
            "notes": "",
            "source_id": "1",
            "destination_id": "20",
        },
        {
            "type": "withdrawal",
            "date": "2025-01-10",
            "amount": "89.00",
            "description": "Adobe Creative Cloud",
            "source_name": "Main Account",
            "destination_name": "Adobe",
            "category_name": "Software & Subscriptions",
            "budget_name": "Operating",
            "tags": ["software"],
            "notes": "",
            "source_id": "1",
            "destination_id": "21",
        },
        {
            "type": "withdrawal",
            "date": "2025-01-22",
            "amount": "650.00",
            "description": "Social security Q1",
            "source_name": "Main Account",
            "destination_name": "INPS",
            "category_name": "Social Security",
            "budget_name": "Tax & Social",
            "tags": ["tax", "inps"],
            "notes": "",
            "source_id": "1",
            "destination_id": "22",
        },
        {
            "type": "withdrawal",
            "date": "2025-02-05",
            "amount": "280.00",
            "description": "Office rent - February",
            "source_name": "Main Account",
            "destination_name": "Landlord",
            "category_name": "Office Rent",
            "budget_name": "Fixed Costs",
            "tags": ["recurring"],
            "notes": "",
            "source_id": "1",
            "destination_id": "20",
        },
        {
            "type": "withdrawal",
            "date": "2025-02-14",
            "amount": "120.00",
            "description": "Technical books and online courses",
            "source_name": "Main Account",
            "destination_name": "Amazon/Udemy",
            "category_name": "Professional Development",
            "budget_name": "Operating",
            "tags": [],
            "notes": "",
            "source_id": "1",
            "destination_id": "23",
        },
        {
            "type": "withdrawal",
            "date": "2025-03-05",
            "amount": "280.00",
            "description": "Office rent - March",
            "source_name": "Main Account",
            "destination_name": "Landlord",
            "category_name": "Office Rent",
            "budget_name": "Fixed Costs",
            "tags": ["recurring"],
            "notes": "",
            "source_id": "1",
            "destination_id": "20",
        },
        {
            "type": "withdrawal",
            "date": "2025-03-15",
            "amount": "320.00",
            "description": "Accountant Q1",
            "source_name": "Main Account",
            "destination_name": "Accountant Studio",
            "category_name": "Professional Consulting",
            "budget_name": "Operating",
            "tags": [],
            "notes": "",
            "source_id": "1",
            "destination_id": "25",
        },
        {
            "type": "withdrawal",
            "date": "2025-03-30",
            "amount": "450.00",
            "description": "Milan business trip",
            "source_name": "Main Account",
            "destination_name": "Various",
            "category_name": "Travel & Transport",
            "budget_name": "Operating",
            "tags": ["tax"],
            "notes": "",
            "source_id": "1",
            "destination_id": "24",
        },
        {
            "type": "withdrawal",
            "date": "2025-04-05",
            "amount": "280.00",
            "description": "Office rent - April",
            "source_name": "Main Account",
            "destination_name": "Landlord",
            "category_name": "Office Rent",
            "budget_name": "Fixed Costs",
            "tags": ["recurring"],
            "notes": "",
            "source_id": "1",
            "destination_id": "20",
        },
        {
            "type": "withdrawal",
            "date": "2025-04-15",
            "amount": "1200.00",
            "description": "Income tax advance",
            "source_name": "Main Account",
            "destination_name": "Tax Agency",
            "category_name": "Income Tax",
            "budget_name": "Tax & Social",
            "tags": ["tax"],
            "notes": "",
            "source_id": "1",
            "destination_id": "26",
        },
        {
            "type": "withdrawal",
            "date": "2025-04-22",
            "amount": "199.00",
            "description": "Annual hosting and domain",
            "source_name": "Main Account",
            "destination_name": "Hetzner Online",
            "category_name": "Software & Subscriptions",
            "budget_name": "Operating",
            "tags": ["software"],
            "notes": "",
            "source_id": "1",
            "destination_id": "27",
        },
        {
            "type": "withdrawal",
            "date": "2025-05-05",
            "amount": "280.00",
            "description": "Office rent - May",
            "source_name": "Main Account",
            "destination_name": "Landlord",
            "category_name": "Office Rent",
            "budget_name": "Fixed Costs",
            "tags": ["recurring"],
            "notes": "",
            "source_id": "1",
            "destination_id": "20",
        },
        {
            "type": "withdrawal",
            "date": "2025-05-18",
            "amount": "155.00",
            "description": "Office supplies",
            "source_name": "Main Account",
            "destination_name": "Amazon",
            "category_name": "Office Supplies",
            "budget_name": "Operating",
            "tags": [],
            "notes": "",
            "source_id": "1",
            "destination_id": "28",
        },
        {
            "type": "transfer",
            "date": "2025-01-31",
            "amount": "500.00",
            "description": "Transfer to savings",
            "source_name": "Main Account",
            "destination_name": "Savings Account",
            "category_name": None,
            "budget_name": None,
            "tags": [],
            "notes": "",
            "source_id": "1",
            "destination_id": "2",
        },
        {
            "type": "transfer",
            "date": "2025-03-31",
            "amount": "500.00",
            "description": "Transfer to savings",
            "source_name": "Main Account",
            "destination_name": "Savings Account",
            "category_name": None,
            "budget_name": None,
            "tags": [],
            "notes": "",
            "source_id": "1",
            "destination_id": "2",
        },
    ]


@pytest.fixture
def txn_2024() -> list[dict]:
    """9 transactions from 2024 for year-over-year comparison."""
    return [
        {
            "type": "deposit",
            "date": "2024-02-10",
            "amount": "2600.00",
            "description": "Invoice - Rossi",
            "source_name": "Rossi S.r.l.",
            "destination_name": "Main Account",
            "category_name": "Professional Fees",
            "budget_name": None,
            "tags": [],
            "notes": "",
            "source_id": "10",
            "destination_id": "1",
        },
        {
            "type": "deposit",
            "date": "2024-05-15",
            "amount": "2200.00",
            "description": "Invoice - Verde",
            "source_name": "Verde SpA",
            "destination_name": "Main Account",
            "category_name": "Professional Fees",
            "budget_name": None,
            "tags": [],
            "notes": "",
            "source_id": "11",
            "destination_id": "1",
        },
        {
            "type": "deposit",
            "date": "2024-08-20",
            "amount": "3100.00",
            "description": "Invoice - Rossi",
            "source_name": "Rossi S.r.l.",
            "destination_name": "Main Account",
            "category_name": "Professional Fees",
            "budget_name": None,
            "tags": [],
            "notes": "",
            "source_id": "10",
            "destination_id": "1",
        },
        {
            "type": "deposit",
            "date": "2024-11-05",
            "amount": "2800.00",
            "description": "Invoice - Verde",
            "source_name": "Verde SpA",
            "destination_name": "Main Account",
            "category_name": "Professional Fees",
            "budget_name": None,
            "tags": [],
            "notes": "",
            "source_id": "11",
            "destination_id": "1",
        },
        {
            "type": "withdrawal",
            "date": "2024-01-05",
            "amount": "260.00",
            "description": "Office rent",
            "source_name": "Main Account",
            "destination_name": "Landlord",
            "category_name": "Office Rent",
            "budget_name": "Fixed Costs",
            "tags": [],
            "notes": "",
            "source_id": "1",
            "destination_id": "20",
        },
        {
            "type": "withdrawal",
            "date": "2024-03-15",
            "amount": "580.00",
            "description": "Social security",
            "source_name": "Main Account",
            "destination_name": "INPS",
            "category_name": "Social Security",
            "budget_name": "Tax & Social",
            "tags": [],
            "notes": "",
            "source_id": "1",
            "destination_id": "22",
        },
        {
            "type": "withdrawal",
            "date": "2024-04-10",
            "amount": "900.00",
            "description": "Income tax advance 2024",
            "source_name": "Main Account",
            "destination_name": "Tax Agency",
            "category_name": "Income Tax",
            "budget_name": "Tax & Social",
            "tags": [],
            "notes": "",
            "source_id": "1",
            "destination_id": "26",
        },
        {
            "type": "withdrawal",
            "date": "2024-06-20",
            "amount": "75.00",
            "description": "Adobe CC 2024",
            "source_name": "Main Account",
            "destination_name": "Adobe",
            "category_name": "Software & Subscriptions",
            "budget_name": "Operating",
            "tags": [],
            "notes": "",
            "source_id": "1",
            "destination_id": "21",
        },
        {
            "type": "withdrawal",
            "date": "2024-09-15",
            "amount": "200.00",
            "description": "Training course",
            "source_name": "Main Account",
            "destination_name": "Udemy",
            "category_name": "Professional Development",
            "budget_name": "Operating",
            "tags": [],
            "notes": "",
            "source_id": "1",
            "destination_id": "23",
        },
    ]


@pytest.fixture
def accounts() -> list[dict]:
    return [
        {
            "id": "1",
            "attributes": {
                "name": "Main Checking",
                "account_role": "defaultAsset",
                "current_balance": "8432.50",
                "iban": "IT60X0542811101000000123456",
                "currency_code": "EUR",
                "active": True,
                "notes": "Primary account",
            },
        },
        {
            "id": "2",
            "attributes": {
                "name": "Savings Account",
                "account_role": "savingsAsset",
                "current_balance": "12150.00",
                "iban": "",
                "currency_code": "EUR",
                "active": True,
                "notes": "Emergency fund",
            },
        },
        {
            "id": "3",
            "attributes": {
                "name": "Credit Card",
                "account_role": "ccAsset",
                "current_balance": "-340.00",
                "iban": "",
                "currency_code": "EUR",
                "active": True,
                "notes": "Limit EUR 2000",
            },
        },
    ]


@pytest.fixture
def liabilities() -> list[dict]:
    return [
        {
            "id": "30",
            "attributes": {
                "name": "Home Mortgage",
                "liability_type": "mortgage",
                "current_balance": "-87500.00",
                "interest": "2.30",
                "currency_code": "EUR",
                "notes": "Monthly installment EUR 520",
            },
        },
    ]


@pytest.fixture
def budgets() -> list[dict]:
    return [
        {"id": "101", "attributes": {"name": "Fixed Costs", "auto_budget_amount": "320.00"}},
        {"id": "102", "attributes": {"name": "Operating", "auto_budget_amount": "800.00"}},
        {"id": "103", "attributes": {"name": "Tax & Social", "auto_budget_amount": "1500.00"}},
    ]


@pytest.fixture
def budget_limits() -> dict:
    return {}


@pytest.fixture
def bills() -> list[dict]:
    return [
        {
            "id": "201",
            "attributes": {
                "name": "Adobe Creative Cloud",
                "amount_min": "89.00",
                "amount_max": "89.00",
                "repeat_freq": "monthly",
                "next_expected_match": "2025-06-10",
                "active": True,
                "notes": "",
            },
        },
        {
            "id": "202",
            "attributes": {
                "name": "Server Hosting",
                "amount_min": "180.00",
                "amount_max": "220.00",
                "repeat_freq": "yearly",
                "next_expected_match": "2026-04-22",
                "active": True,
                "notes": "VPS + storage",
            },
        },
    ]


@pytest.fixture
def bill_txn() -> dict:
    return {
        "201": [
            {
                "amount": "89.00",
                "date": "2025-01-10",
                "type": "withdrawal",
                "description": "Adobe CC",
            },
            {
                "amount": "89.00",
                "date": "2025-02-10",
                "type": "withdrawal",
                "description": "Adobe CC",
            },
        ],
        "202": [
            {
                "amount": "199.00",
                "date": "2025-04-22",
                "type": "withdrawal",
                "description": "Hosting annual",
            },
        ],
    }


@pytest.fixture
def piggy_banks() -> list[dict]:
    return [
        {
            "id": "301",
            "attributes": {
                "name": "Emergency Fund (6 months)",
                "target_amount": "15000.00",
                "current_amount": "12150.00",
                "start_date": "2023-01-01",
                "target_date": "2025-12-31",
                "accounts": [{"account_id": "2", "name": "Savings Account"}],
                "notes": "6 months of expenses",
            },
        },
        {
            "id": "302",
            "attributes": {
                "name": "New Laptop",
                "target_amount": "2500.00",
                "current_amount": "800.00",
                "start_date": "2025-01-01",
                "target_date": "2025-10-01",
                "accounts": [{"account_id": "2", "name": "Savings Account"}],
                "notes": "",
            },
        },
    ]


@pytest.fixture
def period() -> tuple[date, date]:
    return date(2025, 1, 1), date(2025, 5, 31)


@pytest.fixture
def period_prev() -> tuple[date, date]:
    return date(2024, 1, 1), date(2024, 12, 31)


@pytest.fixture
def owner() -> str:
    return "Test User"


@pytest.fixture
def currency() -> str:
    return "EUR"


@pytest.fixture
def about() -> dict:
    return {
        "version": "6.2.10",
        "api_version": "2.1.0",
        "os": "Linux",
        "php_version": "8.3.9",
    }


@pytest.fixture
def about_user() -> dict:
    return {"email": "test@example.com", "role": "owner"}
