"""Firefly III REST API client with transparent pagination."""

import logging
import re
import time
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

import requests


def _dec(value: Any) -> Decimal:
    """Coerce an API amount string/number to Decimal, returning 0 on failure."""
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _redact(value: str) -> str:
    """Replace anything that looks like a Bearer token with a placeholder."""
    return re.sub(r"Bearer\s+\S+", "Bearer ***REDACTED***", value)


class FireflyClient:
    """HTTP client for the Firefly III v1 API."""

    def __init__(
        self,
        base_url: str,
        token: str,
        logger: logging.Logger | None = None,
        request_delay: float = 0.2,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._log = logger or logging.getLogger("firefly_reports.client")
        self._request_delay = request_delay
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.api+json",
                "Content-Type": "application/json",
            }
        )
        self._log.debug(
            "FireflyClient initialised — base_url=%s delay=%.2fs",
            self.base_url,
            self._request_delay,
        )

    def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}/api/v1/{endpoint}"
        self._log.debug("GET %s params=%s", url, params)
        resp = self.session.get(url, params=params, timeout=30)
        self._log.debug("  -> HTTP %d  %d bytes", resp.status_code, len(resp.content))
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        return result

    def _get_paginated(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Fetch all pages and return a flat list of data items."""
        params = dict(params or {})
        params["limit"] = 100
        params["page"] = 1
        results: list[dict[str, Any]] = []
        while True:
            data = self._get(endpoint, params)
            items: list[dict[str, Any]] = data.get("data", [])
            results.extend(items)
            meta = data.get("meta", {}).get("pagination", {})
            total_pages: int = meta.get("total_pages", 1)
            self._log.debug(
                "  page %d/%d -> %d items (total: %d)",
                params["page"],
                total_pages,
                len(items),
                len(results),
            )
            if params["page"] >= total_pages:
                break
            params["page"] += 1
        return results

    def _flatten_transactions(self, raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Flatten grouped transaction items into one dict per split."""
        flat: list[dict[str, Any]] = []
        for item in raw:
            attrs = item.get("attributes", {})
            for tx in attrs.get("transactions", []):
                tx["group_id"] = item["id"]
                tx["group_title"] = attrs.get("group_title")
                tx["updated_at"] = attrs.get("updated_at")
                # Ensure metadata is explicitly present (if available in tx split)
                tx["book_date"] = tx.get("book_date")
                tx["external_id"] = tx.get("external_id")
                tx["reconciled"] = tx.get("reconciled", False)
                tx["has_attachments"] = tx.get("has_attachments", False)
                flat.append(tx)
        return flat

    # ---------- Transactions ----------

    def get_transactions(
        self,
        start: date,
        end: date,
        tx_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return all transactions in [start, end], one dict per split."""
        params: dict[str, Any] = {
            "start": start.isoformat(),
            "end": end.isoformat(),
        }
        if tx_type:
            params["type"] = tx_type
        raw = self._get_paginated("transactions", params)
        return self._flatten_transactions(raw)

    def _get_single(self, endpoint: str) -> dict[str, Any]:
        """GET a single-object endpoint, retrying once on HTTP 429.

        Applies the configured inter-request delay and honors the Retry-After
        header (doubling the request delay as a fallback) before giving up.
        """
        time.sleep(self._request_delay)
        url = f"{self.base_url}/api/v1/{endpoint}"
        resp = self.session.get(url, timeout=30)
        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After", self._request_delay * 2))
            self._log.warning("Rate limited (429) — retrying in %.1fs", retry_after)
            time.sleep(retry_after)
            resp = self.session.get(url, timeout=30)
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        return result

    def get_transaction_by_id(self, tx_id: str) -> dict[str, Any]:
        """Fetch a single transaction group by ID and return its first flattened split."""
        self._log.debug("Fetching transaction detail for ID: %s", tx_id)
        data = self._get_single(f"transactions/{tx_id}")
        item = data.get("data", {})
        if not item:
            return {}
        splits = self._flatten_transactions([item])
        return splits[0] if splits else {}

    def get_transaction_journal_by_id(self, journal_id: str) -> dict[str, Any]:
        """Fetch a single transaction journal (split-level) by ID.

        Returns the journal attributes as a flat dict compatible with the
        output of _flatten_transactions().
        """
        self._log.debug("Fetching transaction journal for ID: %s", journal_id)
        data = self._get_single(f"transaction-journals/{journal_id}")
        item = data.get("data", {})
        attrs: dict[str, Any] = item.get("attributes", {})
        if not attrs:
            return {}
        attrs["transaction_journal_id"] = str(item.get("id", journal_id))
        return attrs

    def fetch_link_details(self, journal_ids: list[str]) -> list[dict[str, Any]]:
        """Fetch details for a list of transaction journal IDs.

        Skips IDs that fail after retry so the caller always gets a partial result
        rather than a full abort. Progress is logged at INFO level every 10 items.
        """
        results: list[dict[str, Any]] = []
        if not journal_ids:
            return results

        total = len(journal_ids)
        self._log.info(
            "Deep-fetching details for %d transaction journals (delay=%.2fs each)...",
            total,
            self._request_delay,
        )
        failed = 0
        for i, journal_id in enumerate(journal_ids, 1):
            if i % 10 == 0 or i == total:
                self._log.info("  deep-fetch progress: %d/%d (failed: %d)", i, total, failed)
            try:
                tx = self.get_transaction_journal_by_id(journal_id)
                if tx:
                    results.append(tx)
            except Exception as e:
                failed += 1
                self._log.error("Failed to fetch transaction journal %s: %s", journal_id, e)

        if failed:
            self._log.warning(
                "Deep-fetch complete: %d/%d retrieved, %d failed", len(results), total, failed
            )
        return results

    # ---------- Transaction Links ----------

    def get_link_types(self) -> dict[str, str]:
        """Return a map of link-type ID -> link-type name."""
        raw = self._get_paginated("link-types")
        return {
            str(item.get("id", "")): str(item.get("attributes", {}).get("name", "")) for item in raw
        }

    def get_transaction_links(self) -> list[dict[str, Any]]:
        """Return all transaction links with the link type name resolved.

        Each item: id, link_type_id, link_type_name, inward_id, outward_id, notes.
        inward_id/outward_id reference transaction journal IDs.
        """
        type_names = self.get_link_types()
        links: list[dict[str, Any]] = []
        for item in self._get_paginated("transaction-links"):
            attrs = item.get("attributes", {})
            lt_id = str(attrs.get("link_type_id", ""))
            links.append(
                {
                    "id": str(item.get("id", "")),
                    "link_type_id": lt_id,
                    "link_type_name": type_names.get(lt_id, ""),
                    "inward_id": str(attrs.get("inward_id", "")),
                    "outward_id": str(attrs.get("outward_id", "")),
                    "notes": attrs.get("notes") or "",
                }
            )
        return links

    # ---------- Insight ----------

    def get_expense_by_category(self, start: date, end: date) -> list[dict[str, Any]]:
        params = {"start": start.isoformat(), "end": end.isoformat()}
        result = self._get("insight/expense/category", params)
        return result if isinstance(result, list) else []

    def get_income_by_category(self, start: date, end: date) -> list[dict[str, Any]]:
        params = {"start": start.isoformat(), "end": end.isoformat()}
        result = self._get("insight/income/category", params)
        return result if isinstance(result, list) else []

    def get_expense_total(self, start: date, end: date) -> list[dict[str, Any]]:
        params = {"start": start.isoformat(), "end": end.isoformat()}
        result = self._get("insight/expense/total", params)
        return result if isinstance(result, list) else []

    def get_income_total(self, start: date, end: date) -> list[dict[str, Any]]:
        params = {"start": start.isoformat(), "end": end.isoformat()}
        result = self._get("insight/income/total", params)
        return result if isinstance(result, list) else []

    # ---------- Accounts ----------

    def get_asset_accounts(self) -> list[dict[str, Any]]:
        return self._get_paginated("accounts", {"type": "asset"})

    def get_account_transactions(
        self, account_id: int, start: date, end: date
    ) -> list[dict[str, Any]]:
        params = {"start": start.isoformat(), "end": end.isoformat()}
        raw = self._get_paginated(f"accounts/{account_id}/transactions", params)
        return self._flatten_transactions(raw)

    # ---------- Summary ----------

    def get_summary_basic(self, start: date, end: date) -> dict[str, Any]:
        params = {"start": start.isoformat(), "end": end.isoformat()}
        return self._get("summary/basic", params)

    # ---------- About ----------

    def get_about(self) -> dict[str, Any]:
        """Return instance info (version, api_version, os, php_version) from /about.

        Unlike most Firefly III API resources, /about is not a JSON:API
        resource — it returns a plain object directly under "data", with no
        "attributes" wrapper (and no timezone field).
        """
        try:
            data = self._get("about")
        except requests.exceptions.RequestException as exc:
            self._log.warning("Could not fetch /about: %s", exc)
            return {}
        attrs = data.get("data", {})
        return attrs if isinstance(attrs, dict) else {}

    def get_about_user(self) -> dict[str, Any]:
        """Return current user info (email, role) from /about/user."""
        try:
            data = self._get("about/user")
        except requests.exceptions.RequestException as exc:
            self._log.warning("Could not fetch /about/user: %s", exc)
            return {}
        attrs = data.get("data", {})
        if not isinstance(attrs, dict):
            return {}
        attributes: dict[str, Any] = attrs.get("attributes", {})
        return attributes if isinstance(attributes, dict) else {}

    # ---------- Annual Aggregates ----------

    def get_annual_totals(self, year: int) -> dict[str, Any]:
        """Fetch basic summary for the whole year by aggregating transactions."""
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        self._log.info("Calculating annual totals for %d...", year)

        income_tx = self.get_transactions(start, end, tx_type="deposit")
        expense_tx = self.get_transactions(start, end, tx_type="withdrawal")

        income = sum(_dec(tx.get("amount", 0)) for tx in income_tx)
        expense = sum(abs(_dec(tx.get("amount", 0))) for tx in expense_tx)

        return {
            "income": income,
            "expense": expense,
            "net": income - expense,
        }

    def get_top_categories_for_year(self, year: int, limit: int = 5) -> list[dict[str, Any]]:
        """Fetch withdrawals for the year and aggregate by category."""
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        self._log.info("Fetching top categories for %d (limit=%d)...", year, limit)
        transactions = self.get_transactions(start, end, tx_type="withdrawal")

        category_totals: dict[str, Decimal] = {}
        for tx in transactions:
            cat_name = tx.get("category_name") or "(no category)"
            amount = abs(_dec(tx.get("amount", 0)))
            category_totals[cat_name] = category_totals.get(cat_name, Decimal("0")) + amount

        sorted_cats = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
        return [{"category": k, "amount": v} for k, v in sorted_cats[:limit]]

    # ---------- Budgets ----------

    def get_budgets(self) -> list[dict[str, Any]]:
        return self._get_paginated("budgets")

    def get_budget_limits(self, budget_id: str, start: date, end: date) -> list[dict[str, Any]]:
        params = {"start": start.isoformat(), "end": end.isoformat()}
        return self._get_paginated(f"budgets/{budget_id}/limits", params)

    def get_budget_transactions(
        self, budget_id: str, start: date, end: date
    ) -> list[dict[str, Any]]:
        params = {"start": start.isoformat(), "end": end.isoformat(), "limit": 100}
        raw = self._get_paginated(f"budgets/{budget_id}/transactions", params)
        return self._flatten_transactions(raw)

    # ---------- Bills ----------

    def get_bills(self) -> list[dict[str, Any]]:
        return self._get_paginated("bills")

    def get_bill_transactions(self, bill_id: str, start: date, end: date) -> list[dict[str, Any]]:
        params = {"start": start.isoformat(), "end": end.isoformat()}
        raw = self._get_paginated(f"bills/{bill_id}/transactions", params)
        return self._flatten_transactions(raw)

    # ---------- Piggy Banks ----------

    def get_piggy_banks(self) -> list[dict[str, Any]]:
        return self._get_paginated("piggy-banks")

    # ---------- Liabilities ----------

    def get_liability_accounts(self) -> list[dict[str, Any]]:
        return self._get_paginated("accounts", {"type": "liabilities"})

    def get_liability_transactions(
        self, account_id: int, start: date, end: date
    ) -> list[dict[str, Any]]:
        params = {"start": start.isoformat(), "end": end.isoformat()}
        raw = self._get_paginated(f"accounts/{account_id}/transactions", params)
        return self._flatten_transactions(raw)
