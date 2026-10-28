"""Download everything a run needs from Firefly III (the 1.x calls, in the 1.x order)."""

from __future__ import annotations

import logging
import time
from typing import Any

from firefly_reports.reports import events
from firefly_reports.reports.events import Progress
from firefly_reports.reports.filters import apply_global_filters
from firefly_reports.reports.spec import FireflySource, ReportContext, SourceData

log = logging.getLogger(__name__)


def _filtered(transactions: list[dict[str, Any]], ctx: ReportContext) -> list[dict[str, Any]]:
    f = ctx.options.filters
    return apply_global_filters(
        transactions,
        accounts_include=list(f.accounts_include),
        accounts_exclude=list(f.accounts_exclude),
        categories_include=list(f.categories_include),
        categories_exclude=list(f.categories_exclude),
        show_transfers=f.show_transfers,
        show_reconciled_only=f.reconciled_only,
    )


def fetch_source_data(client: FireflySource, ctx: ReportContext, progress: Progress) -> SourceData:
    """Fetch the data of one run; *progress* receives the ``fetch.*`` events."""
    period, opts = ctx.period, ctx.options
    start, end = period.start, period.end
    progress(events.FETCH_START)
    t0 = time.monotonic()

    # -- Current period transactions
    transactions = client.get_transactions(start, end)
    log.debug("get_transactions: %.2fs, %d tx", time.monotonic() - t0, len(transactions))
    progress(events.FETCH_TRANSACTIONS, count=len(transactions), start=start, end=end)

    # -- Previous year transactions (YoY: year mode only)
    transactions_prev: list[dict[str, Any]] = []
    if period.year_mode:
        prev = period.previous
        transactions_prev = client.get_transactions(prev.start, prev.end)
        log.debug("transactions_prev: %d tx", len(transactions_prev))
        progress(
            events.FETCH_TRANSACTIONS_PREV,
            count=len(transactions_prev),
            start=prev.start,
            end=prev.end,
        )

    # -- Global filters
    f = opts.filters
    if f.is_active():
        before = len(transactions)
        transactions = _filtered(transactions, ctx)
        transactions_prev = _filtered(transactions_prev, ctx)
        progress(events.FETCH_FILTERS, before=before, after=len(transactions))

    # -- Asset accounts
    accounts = client.get_asset_accounts()
    if f.accounts_include or f.accounts_exclude:
        accounts = [
            a
            for a in accounts
            if (not f.accounts_include or str(a.get("id", "")) in f.accounts_include)
            and str(a.get("id", "")) not in f.accounts_exclude
        ]
    log.debug("asset_accounts: %d", len(accounts))
    progress(events.FETCH_ACCOUNTS, count=len(accounts))

    # -- Liabilities
    liabilities = client.get_liability_accounts()
    log.debug("liability_accounts: %d", len(liabilities))
    progress(events.FETCH_LIABILITIES, count=len(liabilities))

    # -- Transactions per account (account statements)
    account_transactions: dict[str, list[dict[str, Any]]] = {}
    for acc in accounts:
        acc_id = str(acc.get("id", ""))
        account_transactions[acc_id] = client.get_account_transactions(int(acc_id), start, end)
    log.debug("txn_by_account: %d accounts", len(account_transactions))
    progress(events.FETCH_STATEMENTS, count=len(accounts))

    # -- Transactions per liability
    liability_transactions: dict[str, list[dict[str, Any]]] = {}
    for acc in liabilities:
        acc_id = str(acc.get("id", ""))
        liability_transactions[acc_id] = client.get_liability_transactions(int(acc_id), start, end)

    # -- Budgets
    budgets = client.get_budgets()
    budget_limits: dict[str, list[dict[str, Any]]] = {}
    for b in budgets:
        bid = str(b.get("id", ""))
        budget_limits[bid] = client.get_budget_limits(bid, start, end)
    log.debug("budgets: %d", len(budgets))
    progress(events.FETCH_BUDGETS, count=len(budgets))

    # -- Bills
    bills = client.get_bills()
    bill_transactions: dict[str, list[dict[str, Any]]] = {}
    for bill in bills:
        bid = str(bill.get("id", ""))
        bill_transactions[bid] = client.get_bill_transactions(bid, start, end)
    log.debug("bills: %d", len(bills))
    progress(events.FETCH_BILLS, count=len(bills))

    # -- Piggy banks
    piggy_banks = client.get_piggy_banks()
    log.debug("piggy_banks: %d", len(piggy_banks))
    progress(events.FETCH_PIGGY_BANKS, count=len(piggy_banks))

    # -- Instance info (summary report)
    about = client.get_about()
    about_user = client.get_about_user()
    log.debug("about: version=%s", about.get("version", "?"))

    # -- Historical data (year mode only, if not legacy)
    history: dict[int, dict[str, Any]] = {}
    if period.year_mode and not opts.legacy:
        progress(events.FETCH_HISTORY, years=opts.historical_years)
        for i in range(opts.historical_years):  # include the selected year itself
            y = start.year - i
            progress(events.FETCH_HISTORY_YEAR, year=y)
            totals = client.get_annual_totals(y)
            cats = client.get_top_categories_for_year(y)
            history[y] = {
                "total_income": totals["income"],
                "total_expense": totals["expense"],
                "net_savings": totals["income"] - totals["expense"],
                "top_categories": cats,
            }

    # -- Transaction links (with deep-fetch of unknown linked transactions if enabled)
    links = client.get_transaction_links()
    log.debug("transaction_links: %d", len(links))
    linked_extra: list[dict[str, Any]] = []
    if opts.fetch_links:
        linked_ids = set()
        for lnk in links:
            if lnk.get("inward_id"):
                linked_ids.add(str(lnk["inward_id"]))
            if lnk.get("outward_id"):
                linked_ids.add(str(lnk["outward_id"]))
        known_ids = {str(tx.get("id") or tx.get("transaction_journal_id")) for tx in transactions}
        missing_ids = [tid for tid in linked_ids if tid and tid not in known_ids]
        if missing_ids:
            progress(events.FETCH_LINKS_DEEP, count=len(missing_ids))
            linked_extra = client.fetch_link_details(missing_ids)

    progress(events.FETCH_DONE, seconds=time.monotonic() - t0)
    return SourceData(
        transactions=transactions,
        transactions_prev=transactions_prev,
        accounts=accounts,
        liabilities=liabilities,
        account_transactions=account_transactions,
        liability_transactions=liability_transactions,
        budgets=budgets,
        budget_limits=budget_limits,
        bills=bills,
        bill_transactions=bill_transactions,
        piggy_banks=piggy_banks,
        about=about,
        about_user=about_user,
        links=links,
        linked_extra=linked_extra,
        history=history,
    )
