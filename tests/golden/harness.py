"""Everything the golden tests know about the current import paths (one place to update)."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest import mock

from firefly_reports import clock, i18n
from firefly_reports.data_processor import (
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
from firefly_reports.demo import data as demo
from firefly_reports.demo.__main__ import main as demo_main
from firefly_reports.demo.client import DemoClient

DEMO_CLOCK = datetime(2026, 1, 15, 12, 0)
YEAR = 2025


def build_demo_suite(lang: str) -> dict[str, Any]:
    """Every builder called with the demo inputs exactly as ``demo.main()`` does."""
    start, end = date(YEAR, 1, 1), date(YEAR, 12, 31)
    prev_start, prev_end = date(YEAR - 1, 1, 1), date(YEAR - 1, 12, 31)
    demo.ensure_ids(demo.TXN_2025, "25-")
    demo.ensure_ids(demo.TXN_2024, "24-")
    o, s = demo.OWNER, demo.SYM
    t25, t24 = demo.TXN_2025, demo.TXN_2024
    i18n.load(lang)
    try:
        with clock.frozen(DEMO_CLOCK):
            kpi = build_kpi_scorecard(t25, demo.ACCOUNTS, demo.LIABILITIES, start, end, o, s)
            hist = {
                YEAR - 2 + i: {
                    "total_income": Decimal(inc),
                    "total_expense": Decimal(exp),
                    "top_categories": [
                        {"category": "Rent", "amount": Decimal("12000.00")},
                        {"category": "Groceries", "amount": Decimal(gro)},
                    ],
                }
                for i, (inc, exp, gro) in enumerate(
                    [
                        ("45000.00", "38000.00", "4000.00"),
                        ("48000.00", "39000.00", "4200.00"),
                        ("52000.00", "41000.00", "4500.00"),
                    ]
                )
            }
            return {
                "cash_flow": build_cash_flow(
                    t25, start, end, o, s, demo.ACCOUNTS, demo.LIABILITIES
                ),
                "income_expense": build_income_expense(t25, start, end, o, s),
                "transaction_register": build_transaction_register(t25, start, end, o, s),
                "net_worth": build_net_worth(demo.ACCOUNTS, end, o, s),
                "account_statements": build_account_statements(
                    demo.ACCOUNTS[:2], {"1": t25}, start, end, o, s
                ),
                "tax_summary": build_tax_summary(
                    t25,
                    YEAR,
                    owner_name=o,
                    currency_symbol=s,
                    deductible_keywords=["accountant", "software", "hardware", "marketing"],
                ),
                "expense_trend": build_expense_trend(t25, start, end, o, s),
                "tagged": build_tagged_report(t25, ["tax"], start, end, o, s),
                "budget_vs_actual": build_budget_vs_actual(
                    demo.BUDGETS, demo.BUDGET_LIMITS, t25, start, end, o, s
                ),
                "bills": build_bills_report(demo.BILLS, demo.BILL_TXN, start, end, o, s),
                "savings_goals": build_savings_goals(demo.PIGGY_BANKS, end, o, s),
                "liabilities": build_liabilities_report(
                    demo.LIABILITIES, {}, end, start, end, o, s
                ),
                "kpi_scorecard": kpi,
                "yoy": build_yoy_comparison(t25, t24, start, end, prev_start, prev_end, o, s),
                "cumulative_cashflow": build_cumulative_cashflow(t25, start, end, o, s),
                "income_concentration": build_income_concentration(t25, start, end, o, s),
                "audit_log": build_audit_log(t25, start, end, o, s),
                "summary": build_summary(
                    t25,
                    demo.ACCOUNTS,
                    demo.LIABILITIES,
                    demo.BUDGETS,
                    demo.BILLS,
                    demo.PIGGY_BANKS,
                    demo.ABOUT,
                    demo.ABOUT_USER,
                    start,
                    end,
                    o,
                    s,
                ),
                "journal": build_journal(t25, start, end, o, s),
                "budget_forecast": build_performance_forecast(
                    demo.BUDGETS, demo.BUDGET_LIMITS, t25, start, end, o, s
                ),
                "category_ledger": build_category_ledger(t25, start, end, o, s),
                "payee_ledger": build_payee_ledger(t25, start, end, o, s),
                "linkage_audit": build_linkage_report(
                    t25, demo.TRANSACTION_LINKS, start, end, o, s
                ),
                "all_tags": build_all_tags_report(t25, start, end, o, s),
                "historical_growth": build_historical_report(hist, o, s),
                "liquidity_forecast": build_liquidity_forecast(
                    current_balance=Decimal("15000.00"),
                    avg_income=kpi["avg_monthly_in"],
                    avg_variable_expense=kpi["avg_monthly_out"],
                    bills=demo.BILLS,
                    end_date=end,
                    owner_name=o,
                    currency_symbol=s,
                ),
            }
    finally:
        i18n.load("en")


def render_demo_suite(out_dir: Path, lang: str) -> list[Path]:
    """Run the demo (all 28 PDFs + the workbook) with the clock frozen; return the files."""
    argv = ["demo", "--out", str(out_dir), "--lang", lang, "--year", str(YEAR)]
    old_argv = sys.argv
    sys.argv = argv
    try:
        with clock.frozen(DEMO_CLOCK), contextlib.redirect_stdout(io.StringIO()):
            demo_main()
    finally:
        sys.argv = old_argv
        i18n.load("en")
    return sorted(out_dir.iterdir())


# ---- CLI pipeline ------------------------------------------------------------------------

CLIENT_PATCH_TARGET = "firefly_reports.cli._options.FireflyClient"
_ENV_VARS = ("FIREFLY_URL", "FIREFLY_TOKEN", "FIREFLY_LANG", "FIREFLY_LEGACY_REPORT")


@dataclass
class PipelineRun:
    files: list[str]
    stdout: list[str]
    digests: dict[str, str]
    exit_code: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "exit_code": self.exit_code,
            "files": self.files,
            "stdout": self.stdout,
            "digests": self.digests,
        }


def normalize_stdout(text: str, out_dir: Path) -> list[str]:
    """Stable console text: paths, timings and the order of the ``OK`` lines neutralized."""
    for variant in {str(out_dir.resolve()), str(out_dir)}:
        text = text.replace(variant, "<OUT>")
    text = re.sub(r"\d+(\.\d+)?s\b", "<T>", text)
    lines = text.splitlines()
    ok_positions = [i for i, line in enumerate(lines) if line.startswith("    OK ")]
    for pos, line in zip(ok_positions, sorted(lines[i] for i in ok_positions), strict=True):
        lines[pos] = line
    return lines


def _digest(payload: object) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_main(argv: list[str], cwd: Path, client: Any = None) -> tuple[int, str, str]:
    """Run ``main()`` offline: DemoClient (or *client*) instead of the API, no .env, clean env."""
    from firefly_reports.cli import main

    cwd.mkdir(parents=True, exist_ok=True)
    out, err = io.StringIO(), io.StringIO()
    old_cwd, old_argv = os.getcwd(), sys.argv
    env = {k: v for k, v in os.environ.items() if k not in _ENV_VARS}
    code = 0
    try:
        os.chdir(cwd)
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch(CLIENT_PATCH_TARGET, side_effect=lambda *a, **k: client or DemoClient()),
            mock.patch("firefly_reports.cli._options.load_dotenv", lambda *a, **k: None),
            clock.frozen(DEMO_CLOCK),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
        ):
            try:
                code = main(argv)
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else 1
    finally:
        os.chdir(old_cwd)
        sys.argv = old_argv
        i18n.load("en")
    return code, out.getvalue(), err.getvalue()


def run_pipeline(out_dir: Path, argv: list[str]) -> PipelineRun:
    """One report run through ``main()``; files and per-file digests of what was produced."""
    from tests.golden.snapshot import story_recorder, xlsx_snapshot

    with story_recorder() as stories:
        code, stdout, _ = run_main([*argv, "--out", str(out_dir)], out_dir.parent)
    by_stem = {s.stem: s for s in stories}
    digests: dict[str, str] = {}
    for path in sorted(out_dir.iterdir()):
        if path.suffix == ".pdf":
            digests[path.name] = _digest(by_stem[path.stem].as_dict())
        elif path.suffix == ".xlsx":
            digests[path.name] = _digest(xlsx_snapshot(path))
    return PipelineRun(
        files=sorted(p.name for p in out_dir.iterdir()),
        stdout=normalize_stdout(stdout, out_dir),
        digests=digests,
        exit_code=code,
    )
