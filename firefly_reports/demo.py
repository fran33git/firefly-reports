#!/usr/bin/env python3
"""Demo with mock data — all 26 reports.

Usage:
  python demo.py [--out ./output] [--lang en|it] [--year YYYY] [--debug]
"""
# Run from the firefly_reports/ directory: python demo.py

import argparse
import logging
import time
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import i18n
from data_processor import (
    build_account_statements,
    build_all_tags_report,
    build_audit_log,
    build_bills_report,
    build_budget_vs_actual,
    build_cash_flow,
    build_category_ledger,
    build_cumulative_cashflow,
    build_expense_trend,
    build_historical_report,
    build_income_concentration,
    build_income_expense,
    build_journal,
    build_kpi_scorecard,
    build_liabilities_report,
    build_linkage_report,
    build_liquidity_forecast,
    build_net_worth,
    build_payee_ledger,
    build_performance_forecast,
    build_savings_goals,
    build_summary,
    build_tagged_report,
    build_tax_summary,
    build_transaction_register,
    build_yoy_comparison,
)
from excel_exporter import render_all_xlsx_full
from pdf_exporter import (
    render_account_statements_pdf,
    render_all_tags_pdf,
    render_audit_log_pdf,
    render_bills_pdf,
    render_budget_vs_actual_pdf,
    render_cash_flow_pdf,
    render_category_ledger_pdf,
    render_cumulative_cashflow_pdf,
    render_expense_trend_pdf,
    render_forecast_pdf,
    render_historical_report_pdf,
    render_income_concentration_pdf,
    render_income_expense_dashboard_pdf,
    render_income_expense_pdf,
    render_journal_pdf,
    render_kpi_scorecard_pdf,
    render_kpi_trend_dashboard_pdf,
    render_liabilities_pdf,
    render_linkage_audit_pdf,
    render_liquidity_forecast_pdf,
    render_net_worth_pdf,
    render_payee_ledger_pdf,
    render_savings_goals_pdf,
    render_summary_pdf,
    render_tagged_report_pdf,
    render_tax_summary_pdf,
    render_transaction_register_pdf,
    render_yoy_pdf,
)

# ═══════════════════════════════════════════════════
# MOCK DATA
# ═══════════════════════════════════════════════════

OWNER = "Sample User — Freelancer"
SYM = "€"

# ── 2025 transactions (Jan–May)
TXN_2025 = [
    {
        "type": "deposit",
        "date": "2025-01-15",
        "amount": "3200.00",
        "description": "Invoice #001 - Rossi LLC",
        "source_name": "Rossi LLC",
        "destination_name": "BankX Checking",
        "category_name": "Professional Fees",
        "budget_name": None,
        "tags": ["invoice", "tax"],
        "notes": "",
        "source_id": "10",
        "destination_id": "1",
    },
    {
        "type": "transfer",
        "date": "2025-01-20",
        "amount": "500.00",
        "description": "Emergency fund transfer",
        "source_name": "BankX Checking",
        "destination_name": "BankX Savings",
        "category_name": None,
        "source_id": "1",
        "destination_id": "2",
    },
    {
        "type": "transfer",
        "date": "2025-01-25",
        "amount": "520.00",
        "description": "Mortgage payment - January",
        "source_name": "BankX Checking",
        "destination_name": "Home Mortgage",
        "category_name": "Home",
        "source_id": "1",
        "destination_id": "30",
    },
    # ── Split transaction example: one group, three splits (withholdings)
    {
        "type": "withdrawal",
        "date": "2025-03-15",
        "amount": "557.44",
        "description": "Tax withholdings",
        "source_name": "BankX Checking",
        "destination_name": "Tax Authority",
        "category_name": "Taxes & Contributions",
        "group_id": "g-split-1",
        "group_title": "Payroll withholdings - March 2025",
        "source_id": "1",
        "destination_id": "40",
    },
    {
        "type": "withdrawal",
        "date": "2025-03-15",
        "amount": "220.74",
        "description": "Supplementary benefit installment recovery",
        "source_name": "BankX Checking",
        "destination_name": "Tax Authority",
        "category_name": "Taxes & Contributions",
        "group_id": "g-split-1",
        "group_title": "Payroll withholdings - March 2025",
        "source_id": "1",
        "destination_id": "40",
    },
    {
        "type": "withdrawal",
        "date": "2025-03-15",
        "amount": "1.90",
        "description": "Other withholdings",
        "source_name": "BankX Checking",
        "destination_name": "Tax Authority",
        "category_name": "Taxes & Contributions",
        "group_id": "g-split-1",
        "group_title": "Payroll withholdings - March 2025",
        "source_id": "1",
        "destination_id": "40",
    },
    {
        "type": "deposit",
        "date": "2025-02-10",
        "amount": "2800.00",
        "description": "Invoice #002 - Verde Inc.",
        "source_name": "Verde Inc.",
        "destination_name": "BankX Checking",
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
        "description": "Consulting - Blue Startup",
        "source_name": "Blue Startup",
        "destination_name": "BankX Checking",
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
        "description": "Invoice #003 - Rossi LLC",
        "source_name": "Rossi LLC",
        "destination_name": "BankX Checking",
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
        "description": "Invoice #004 - Verde Inc.",
        "source_name": "Verde Inc.",
        "destination_name": "BankX Checking",
        "category_name": "Professional Fees",
        "budget_name": None,
        "tags": ["invoice"],
        "notes": "",
        "source_id": "11",
        "destination_id": "1",
    },
    {
        "type": "deposit",
        "date": "2025-05-08",
        "amount": "450.00",
        "description": "Travel expense reimbursement",
        "source_name": "Rossi LLC",
        "destination_name": "BankX Checking",
        "category_name": "Reimbursements",
        "budget_name": None,
        "tags": ["reimbursement"],
        "notes": "",
        "source_id": "10",
        "destination_id": "1",
    },
    {
        "type": "deposit",
        "date": "2025-05-20",
        "amount": "3050.00",
        "description": "Invoice #005 - Giallo Ltd",
        "source_name": "Giallo Ltd",
        "destination_name": "BankX Checking",
        "category_name": "Professional Fees",
        "budget_name": None,
        "tags": ["invoice"],
        "notes": "",
        "source_id": "14",
        "destination_id": "1",
    },
    # Linkage/Reimbursement pair
    {
        "id": "500",
        "type": "withdrawal",
        "date": "2025-02-15",
        "amount": "150.00",
        "description": "Travel expense advance",
        "source_name": "BankX Checking",
        "destination_name": "Rome Hotel",
        "category_name": "Travel & Transport",
    },
    {
        "id": "501",
        "type": "deposit",
        "date": "2025-03-10",
        "amount": "150.00",
        "description": "Travel expense reimbursement",
        "source_name": "Rossi LLC",
        "destination_name": "BankX Checking",
        "category_name": "Reimbursements",
    },
    {
        "type": "withdrawal",
        "date": "2025-01-05",
        "amount": "280.00",
        "description": "Office rent - January",
        "source_name": "BankX Checking",
        "destination_name": "Office Landlord",
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
        "source_name": "BankX Checking",
        "destination_name": "Adobe Systems",
        "category_name": "Software & Subscriptions",
        "budget_name": "Operating Expenses",
        "tags": ["software"],
        "notes": "",
        "source_id": "1",
        "destination_id": "21",
    },
    {
        "type": "withdrawal",
        "date": "2025-01-22",
        "amount": "650.00",
        "description": "Social security contributions Q1",
        "source_name": "BankX Checking",
        "destination_name": "Social Security",
        "category_name": "Social Security Contributions",
        "budget_name": "Tax & Social Security",
        "tags": ["tax", "social-security"],
        "notes": "",
        "source_id": "1",
        "destination_id": "22",
    },
    {
        "type": "withdrawal",
        "date": "2025-02-05",
        "amount": "280.00",
        "description": "Office rent - February",
        "source_name": "BankX Checking",
        "destination_name": "Office Landlord",
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
        "source_name": "BankX Checking",
        "destination_name": "Amazon/Udemy",
        "category_name": "Professional Training",
        "budget_name": "Operating Expenses",
        "tags": [],
        "notes": "",
        "source_id": "1",
        "destination_id": "23",
    },
    {
        "type": "withdrawal",
        "date": "2025-02-28",
        "amount": "85.00",
        "description": "Fuel and tolls",
        "source_name": "BankX Checking",
        "destination_name": "Various",
        "category_name": "Travel & Transport",
        "budget_name": "Operating Expenses",
        "tags": [],
        "notes": "",
        "source_id": "1",
        "destination_id": "24",
    },
    {
        "type": "withdrawal",
        "date": "2025-03-05",
        "amount": "280.00",
        "description": "Office rent - March",
        "source_name": "BankX Checking",
        "destination_name": "Office Landlord",
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
        "description": "Accountant fees Q1",
        "source_name": "BankX Checking",
        "destination_name": "Bianchi & Partners",
        "category_name": "Accountant Fees",
        "budget_name": "Operating Expenses",
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
        "source_name": "BankX Checking",
        "destination_name": "Various",
        "category_name": "Travel & Transport",
        "budget_name": "Operating Expenses",
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
        "source_name": "BankX Checking",
        "destination_name": "Office Landlord",
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
        "source_name": "BankX Checking",
        "destination_name": "Tax Authority",
        "category_name": "Taxes",
        "budget_name": "Tax & Social Security",
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
        "source_name": "BankX Checking",
        "destination_name": "Hetzner Online",
        "category_name": "Software & Subscriptions",
        "budget_name": "Operating Expenses",
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
        "source_name": "BankX Checking",
        "destination_name": "Office Landlord",
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
        "source_name": "BankX Checking",
        "destination_name": "Amazon",
        "category_name": "Office Supplies",
        "budget_name": "Operating Expenses",
        "tags": [],
        "notes": "",
        "source_id": "1",
        "destination_id": "28",
    },
    {
        "type": "transfer",
        "date": "2025-01-31",
        "amount": "500.00",
        "description": "Transfer to savings account",
        "source_name": "BankX Checking",
        "destination_name": "BankX Savings",
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
        "description": "Transfer to savings account",
        "source_name": "BankX Checking",
        "destination_name": "BankX Savings",
        "category_name": None,
        "budget_name": None,
        "tags": [],
        "notes": "",
        "source_id": "1",
        "destination_id": "2",
    },
]

# ── 2024 transactions (previous year, for YoY)
TXN_2024 = [
    {
        "type": "deposit",
        "date": "2024-02-10",
        "amount": "2600.00",
        "description": "Invoice - Rossi LLC",
        "source_name": "Rossi LLC",
        "destination_name": "BankX Checking",
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
        "description": "Invoice - Verde Inc.",
        "source_name": "Verde Inc.",
        "destination_name": "BankX Checking",
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
        "description": "Invoice - Rossi LLC",
        "source_name": "Rossi LLC",
        "destination_name": "BankX Checking",
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
        "description": "Invoice - Verde Inc.",
        "source_name": "Verde Inc.",
        "destination_name": "BankX Checking",
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
        "source_name": "BankX Checking",
        "destination_name": "Office Landlord",
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
        "description": "Social security contributions",
        "source_name": "BankX Checking",
        "destination_name": "Social Security",
        "category_name": "Social Security Contributions",
        "budget_name": "Tax & Social Security",
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
        "source_name": "BankX Checking",
        "destination_name": "Tax Authority",
        "category_name": "Taxes",
        "budget_name": "Tax & Social Security",
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
        "source_name": "BankX Checking",
        "destination_name": "Adobe",
        "category_name": "Software & Subscriptions",
        "budget_name": "Operating Expenses",
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
        "source_name": "BankX Checking",
        "destination_name": "Udemy",
        "category_name": "Professional Training",
        "budget_name": "Operating Expenses",
        "tags": [],
        "notes": "",
        "source_id": "1",
        "destination_id": "23",
    },
]

# ── Asset accounts
ACCOUNTS = [
    {
        "id": "1",
        "attributes": {
            "name": "BankX Checking",
            "account_role": "defaultAsset",
            "current_balance": "8432.50",
            "iban": "IT60X0542811101000000123456",
            "currency_code": "EUR",
            "active": True,
            "notes": "Main account",
        },
    },
    {
        "id": "2",
        "attributes": {
            "name": "BankX Savings",
            "account_role": "savingsAsset",
            "current_balance": "12150.00",
            "iban": "IT60X0542811101000000789012",
            "currency_code": "EUR",
            "active": True,
            "notes": "Emergency fund",
        },
    },
    {
        "id": "3",
        "attributes": {
            "name": "Visa Credit Card",
            "account_role": "ccAsset",
            "current_balance": "-340.00",
            "iban": "",
            "currency_code": "EUR",
            "active": True,
            "notes": "€2,000 limit",
        },
    },
    {
        "id": "4",
        "attributes": {
            "name": "Cash Wallet",
            "account_role": "cashWalletAsset",
            "current_balance": "150.00",
            "iban": "",
            "currency_code": "EUR",
            "active": True,
            "notes": "",
        },
    },
]

# ── Liabilities
LIABILITIES = [
    {
        "id": "30",
        "attributes": {
            "name": "Home Mortgage",
            "liability_type": "mortgage",
            "current_balance": "-87500.00",
            "interest": "2.30",
            "currency_code": "EUR",
            "notes": "Monthly payment €520 — matures 2041",
        },
    },
]

# ── Budgets mock
BUDGETS = [
    {"id": "101", "attributes": {"name": "Fixed Costs", "auto_budget_amount": "320.00"}},
    {"id": "102", "attributes": {"name": "Operating Expenses", "auto_budget_amount": "800.00"}},
    {
        "id": "103",
        "attributes": {"name": "Tax & Social Security", "auto_budget_amount": "1500.00"},
    },
]
BUDGET_LIMITS: dict[str, list[dict[str, Any]]] = {}  # empty → use auto_budget_amount

# ── Bills mock
BILLS = [
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
            "name": "Hosting Hetzner",
            "amount_min": "180.00",
            "amount_max": "220.00",
            "repeat_freq": "yearly",
            "next_expected_match": "2026-04-22",
            "active": True,
            "notes": "VPS + storage",
        },
    },
    {
        "id": "203",
        "attributes": {
            "name": "Office Rent",
            "amount_min": "280.00",
            "amount_max": "280.00",
            "repeat_freq": "monthly",
            "next_expected_match": "2025-06-05",
            "active": True,
            "notes": "",
        },
    },
    {
        "id": "204",
        "attributes": {
            "name": "Accountant",
            "amount_min": "300.00",
            "amount_max": "350.00",
            "repeat_freq": "quarterly",
            "next_expected_match": "2025-06-15",
            "active": True,
            "notes": "Quarterly consulting",
        },
    },
]
BILL_TXN = {
    "201": [
        {"amount": "89.00", "date": "2025-01-10", "type": "withdrawal", "description": "Adobe CC"},
        {"amount": "89.00", "date": "2025-02-10", "type": "withdrawal", "description": "Adobe CC"},
        {"amount": "89.00", "date": "2025-03-10", "type": "withdrawal", "description": "Adobe CC"},
    ],
    "202": [
        {
            "amount": "199.00",
            "date": "2025-04-22",
            "type": "withdrawal",
            "description": "Hetzner annual",
        }
    ],
    "203": [
        {
            "amount": "280.00",
            "date": "2025-01-05",
            "type": "withdrawal",
            "description": "Rent Jan",
        },
        {
            "amount": "280.00",
            "date": "2025-02-05",
            "type": "withdrawal",
            "description": "Rent Feb",
        },
        {
            "amount": "280.00",
            "date": "2025-03-05",
            "type": "withdrawal",
            "description": "Rent Mar",
        },
        {
            "amount": "280.00",
            "date": "2025-04-05",
            "type": "withdrawal",
            "description": "Rent Apr",
        },
        {
            "amount": "280.00",
            "date": "2025-05-05",
            "type": "withdrawal",
            "description": "Rent May",
        },
    ],
    "204": [
        {
            "amount": "320.00",
            "date": "2025-03-15",
            "type": "withdrawal",
            "description": "Accountant Q1",
        }
    ],
}

# ── Piggy banks
PIGGY_BANKS = [
    {
        "id": "301",
        "attributes": {
            "name": "Emergency Fund (6 months)",
            "target_amount": "15000.00",
            "current_amount": "12150.00",
            "start_date": "2023-01-01",
            "target_date": "2025-12-31",
            "accounts": [{"account_id": "2", "name": "BankX Savings"}],
            "notes": "Goal: 6 months of expenses",
        },
    },
    {
        "id": "302",
        "attributes": {
            "name": "New MacBook Pro",
            "target_amount": "2500.00",
            "current_amount": "800.00",
            "start_date": "2025-01-01",
            "target_date": "2025-10-01",
            "accounts": [{"account_id": "2", "name": "BankX Savings"}],
            "notes": "M4 Pro",
        },
    },
    {
        "id": "303",
        "attributes": {
            "name": "Japan Trip",
            "target_amount": "3000.00",
            "current_amount": "600.00",
            "start_date": "2025-01-01",
            "target_date": "2026-03-01",
            "accounts": [{"account_id": "2", "name": "BankX Savings"}],
            "notes": "Tokyo + Kyoto 2 weeks",
        },
    },
]


ABOUT = {
    "version": "6.2.10",
    "api_version": "2.1.0",
    "os": "Linux",
    "php_version": "8.3.9",
}

ABOUT_USER = {"email": "demo@firefly.local", "role": "owner"}


# ── Transaction links (mirrors FireflyClient.get_transaction_links() output:
# GET /api/v1/transaction-links with the link type name resolved via /link-types)
TRANSACTION_LINKS = [
    {
        "id": "l1",
        "link_type_id": "9",
        "link_type_name": "Reimbursement",
        "inward_id": "501",
        "outward_id": "500",
        "notes": "",
    },
]


def _setup_debug_log(debug: bool, out_dir: Path, debug_file: str | None = None) -> logging.Logger:
    logger = logging.getLogger("firefly_reports")
    if not debug:
        logger.addHandler(logging.NullHandler())
        return logger
    logger.setLevel(logging.DEBUG)
    if debug_file:
        log_path = Path(debug_file)
    else:
        from datetime import datetime as _dt

        ts = _dt.now().strftime("%Y%m%d_%H%M%S")
        log_path = out_dir / f"debug_{ts}.log"
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(fh)
    print(f"[*] Debug log: {log_path.resolve()}")
    return logger


def _ensure_ids(txns: list[dict], prefix: str) -> None:
    """Give mock transactions stable group/journal IDs like _flatten_transactions does."""
    for i, tx in enumerate(txns, 1):
        tx.setdefault("group_id", f"{prefix}g{i}")
        tx.setdefault("id", f"{prefix}j{i}")


def main():
    parser = argparse.ArgumentParser(description="Demo Firefly report generator (mock data)")
    parser.add_argument("--out", default="./output", help="Output directory (default: ./output)")
    parser.add_argument(
        "--lang",
        choices=["en", "it"],
        default="en",
        help="Report language (default: en)",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2025,
        metavar="YYYY",
        help="Full calendar year mode (default: 2025)",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug log to file")
    parser.add_argument(
        "--debug-file",
        default=None,
        metavar="PATH",
        help="Debug log file path (default: <out>/debug_<timestamp>.log)",
    )
    args = parser.parse_args()
    i18n.load(args.lang)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    log = _setup_debug_log(args.debug, out_dir, args.debug_file)

    year = args.year
    start = date(year, 1, 1)
    end = date(year, 12, 31)
    start_prev = date(year - 1, 1, 1)
    end_prev = date(year - 1, 12, 31)
    tag = f"{start}__{end}"

    print("[*] Processing data...")

    _ensure_ids(TXN_2025, "25-")
    _ensure_ids(TXN_2024, "24-")

    # ── Reports 1–8
    cf = build_cash_flow(TXN_2025, start, end, OWNER, SYM, ACCOUNTS, LIABILITIES)
    ie = build_income_expense(TXN_2025, start, end, OWNER, SYM)
    reg = build_transaction_register(TXN_2025, start, end, OWNER, SYM)
    nw = build_net_worth(ACCOUNTS, end, OWNER, SYM)
    stmts = build_account_statements(ACCOUNTS[:2], {"1": TXN_2025}, start, end, OWNER, SYM)
    tax = build_tax_summary(
        TXN_2025,
        year,
        owner_name=OWNER,
        currency_symbol=SYM,
        deductible_keywords=["accountant", "software", "hardware", "marketing"],
    )
    trend = build_expense_trend(TXN_2025, start, end, OWNER, SYM)
    tagged = build_tagged_report(TXN_2025, ["tax"], start, end, OWNER, SYM)

    # ── Reports 9–24 (extended)
    budget = build_budget_vs_actual(BUDGETS, BUDGET_LIMITS, TXN_2025, start, end, OWNER, SYM)
    bills = build_bills_report(BILLS, BILL_TXN, start, end, OWNER, SYM)
    savings = build_savings_goals(PIGGY_BANKS, end, OWNER, SYM)
    liab = build_liabilities_report(LIABILITIES, {}, end, start, end, OWNER, SYM)
    kpi = build_kpi_scorecard(TXN_2025, ACCOUNTS, LIABILITIES, start, end, OWNER, SYM)
    yoy = build_yoy_comparison(TXN_2025, TXN_2024, start, end, start_prev, end_prev, OWNER, SYM)
    cum_cf = build_cumulative_cashflow(TXN_2025, start, end, OWNER, SYM)
    conc = build_income_concentration(TXN_2025, start, end, OWNER, SYM)
    audit = build_audit_log(TXN_2025, start, end, OWNER, SYM)
    summary = build_summary(
        TXN_2025,
        ACCOUNTS,
        LIABILITIES,
        BUDGETS,
        BILLS,
        PIGGY_BANKS,
        ABOUT,
        ABOUT_USER,
        start,
        end,
        OWNER,
        SYM,
    )
    journal = build_journal(TXN_2025, start, end, OWNER, SYM)
    forecast = build_performance_forecast(BUDGETS, BUDGET_LIMITS, TXN_2025, start, end, OWNER, SYM)

    # Phase 6A reports
    cat_ledger = build_category_ledger(TXN_2025, start, end, OWNER, SYM)
    payee_ledger = build_payee_ledger(TXN_2025, start, end, OWNER, SYM)
    linkage = build_linkage_report(TXN_2025, TRANSACTION_LINKS, start, end, OWNER, SYM)
    all_tags = build_all_tags_report(TXN_2025, start, end, OWNER, SYM)

    # Strategic reports (Phase 6B)
    # Mock historical data for 3 years ending at --year
    hist_amounts = [
        ("45000.00", "38000.00", "4000.00"),
        ("48000.00", "39000.00", "4200.00"),
        ("52000.00", "41000.00", "4500.00"),
    ]
    hist_dict = {
        year - 2 + i: {
            "total_income": Decimal(inc),
            "total_expense": Decimal(exp),
            "top_categories": [
                {"category": "Rent", "amount": Decimal("12000.00")},
                {"category": "Groceries", "amount": Decimal(gro)},
            ],
        }
        for i, (inc, exp, gro) in enumerate(hist_amounts)
    }
    hist_report = build_historical_report(hist_dict, OWNER, SYM)

    # Mock balance for forecast
    liquid_assets = Decimal("15000.00")
    liquid_forecast = build_liquidity_forecast(
        current_balance=liquid_assets,
        avg_income=kpi["avg_monthly_in"],
        avg_variable_expense=kpi["avg_monthly_out"],
        bills=BILLS,
        end_date=end,
        owner_name=OWNER,
        currency_symbol=SYM,
    )

    print(f"    KPI: savings rate {kpi['savings_rate']}%")
    print(f"    Income by client: {conc['client_count']} clients")
    print(
        f"    Savings goals: {savings['goal_count']} goals, overall progress {savings['overall_pct']}%"
    )
    print(
        f"    Liabilities: {liab['liability_count']} liabilities, total debt {liab['total_debt']}"
    )

    # ── PDF
    print("\n[*] Generating PDFs...")
    jobs = [
        (render_cash_flow_pdf, cf, f"cash_flow_{tag}.pdf"),
        (render_income_expense_pdf, ie, f"income_expense_{tag}.pdf"),
        (render_transaction_register_pdf, reg, f"transaction_register_{tag}.pdf"),
        (render_net_worth_pdf, nw, f"net_worth_{tag}.pdf"),
        (render_tax_summary_pdf, tax, f"tax_summary_{year}.pdf"),
        (render_expense_trend_pdf, trend, f"expense_trend_{tag}.pdf"),
        (render_tagged_report_pdf, tagged, f"tagged_tax_{tag}.pdf"),
        (render_budget_vs_actual_pdf, budget, f"budget_vs_actual_{tag}.pdf"),
        (render_bills_pdf, bills, f"bills_{tag}.pdf"),
        (render_savings_goals_pdf, savings, f"savings_goals_{tag}.pdf"),
        (render_liabilities_pdf, liab, f"liabilities_{tag}.pdf"),
        (render_kpi_scorecard_pdf, kpi, f"kpi_scorecard_{tag}.pdf"),
        (render_yoy_pdf, yoy, f"yoy_comparison_{year - 1}_vs_{year}.pdf"),
        (render_cumulative_cashflow_pdf, cum_cf, f"cumulative_cashflow_{tag}.pdf"),
        (render_income_concentration_pdf, conc, f"income_concentration_{tag}.pdf"),
        (
            render_income_expense_dashboard_pdf,
            {**ie, "monthly_trend": kpi["monthly_trend"]},
            f"dashboard_income_expense_{tag}.pdf",
        ),
        (render_kpi_trend_dashboard_pdf, kpi, f"dashboard_kpi_trend_{tag}.pdf"),
        (render_audit_log_pdf, audit, f"audit_log_{tag}.pdf"),
        (render_summary_pdf, summary, f"summary_{tag}.pdf"),
        (render_journal_pdf, journal, f"journal_{tag}.pdf"),
        (render_forecast_pdf, forecast, f"budget_forecast_{tag}.pdf"),
        (render_category_ledger_pdf, cat_ledger, f"ledger_category_{tag}.pdf"),
        (render_payee_ledger_pdf, payee_ledger, f"ledger_payee_{tag}.pdf"),
        (render_linkage_audit_pdf, linkage, f"audit_linkage_{tag}.pdf"),
        (render_all_tags_pdf, all_tags, f"ledger_all_tags_{tag}.pdf"),
        (render_historical_report_pdf, hist_report, f"historical_growth_{tag}.pdf"),
        (render_liquidity_forecast_pdf, liquid_forecast, f"liquidity_forecast_{tag}.pdf"),
    ]
    errors = []
    for fn, data_arg, fname in jobs:
        t0 = time.monotonic()
        try:
            fn(data_arg, str(out_dir / fname))
            elapsed = time.monotonic() - t0
            log.debug("%s: %.2fs", fname, elapsed)
            print(f"    OK  {fname}")
        except Exception as e:
            log.exception("Error generating %s", fname)
            print(f"    FAIL {fname}: {e}")
            errors.append(fname)

    # account statements: different signature
    try:
        t0 = time.monotonic()
        render_account_statements_pdf(stmts, str(out_dir / f"account_statements_{tag}.pdf"))
        log.debug("account_statements: %.2fs", time.monotonic() - t0)
        print(f"    OK  account_statements_{tag}.pdf")
    except Exception as e:
        log.exception("Error generating account_statements")
        print(f"    FAIL account_statements_{tag}.pdf: {e}")
        errors.append(f"account_statements_{tag}.pdf")

    # ── Single Excel workbook
    print("\n[*] Generating Excel (17 core sheets)...")
    try:
        t0 = time.monotonic()
        render_all_xlsx_full(
            {
                "cf": cf,
                "ie": ie,
                "reg": reg,
                "net_worth": nw,
                "statements": stmts,
                "tax": tax,
                "trend": trend,
                "tagged": tagged,
                "budget": budget,
                "bills": bills,
                "savings": savings,
                "liabilities": liab,
                "kpi": kpi,
                "yoy": yoy,
                "cumulative_cf": cum_cf,
                "concentration": conc,
                "summary": summary,
            },
            str(out_dir / f"firefly_reports_complete_{tag}.xlsx"),
        )
        log.debug("Excel complete: %.2fs", time.monotonic() - t0)
        print(f"    OK  firefly_reports_complete_{tag}.xlsx")
    except Exception as e:
        log.exception("Error generating Excel")
        print(f"    FAIL firefly_reports_complete_{tag}.xlsx: {e}")
        errors.append(f"firefly_reports_complete_{tag}.xlsx")

    if errors:
        print(f"\n[!] {len(errors)} files failed: {', '.join(errors)}")
        if not args.debug:
            print("    Rerun with --debug for detailed error logs.")
    else:
        print(f"\nDone. Output: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
