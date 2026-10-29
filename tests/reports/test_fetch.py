"""fetch_source_data: the same Firefly calls as 1.x, in the same order, with filters applied."""

from datetime import date

from firefly_reports.demo.client import DemoClient
from firefly_reports.reports.events import no_progress
from firefly_reports.reports.fetch import fetch_source_data
from firefly_reports.reports.options import GlobalFilters, Period, ReportOptions
from firefly_reports.reports.spec import ReportContext


class Recorder(DemoClient):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.calls: list[tuple] = []
        self._depth = 0

    def __getattribute__(self, name):
        attr = super().__getattribute__(name)
        if name.startswith(("get_", "fetch_")) and callable(attr):

            def spy(*args, **kwargs):
                if self._depth == 0:  # only what the pipeline calls, not internal reuse
                    self.calls.append((name, args))
                self._depth += 1
                try:
                    return attr(*args, **kwargs)
                finally:
                    self._depth -= 1

            return spy
        return attr


def _ctx(period=None, **options):
    period = period or Period.for_year(2025)
    return ReportContext(period, ReportOptions(**options))


def _names(calls):
    out: list[str] = []
    for name, _ in calls:
        if not out or out[-1] != name:
            out.append(name)
    return out


def test_fetch_calls_in_1x_order():
    client = Recorder()
    fetch_source_data(client, _ctx(), no_progress)
    assert _names(client.calls) == [
        "get_transactions",
        "get_asset_accounts",
        "get_liability_accounts",
        "get_account_transactions",
        "get_liability_transactions",
        "get_budgets",
        "get_budget_limits",
        "get_bills",
        "get_bill_transactions",
        "get_piggy_banks",
        "get_about",
        "get_about_user",
        "get_annual_totals",
        "get_top_categories_for_year",
        "get_annual_totals",
        "get_top_categories_for_year",
        "get_annual_totals",
        "get_top_categories_for_year",
        "get_transaction_links",
    ]
    tx_calls = [args for name, args in client.calls if name == "get_transactions"]
    assert tx_calls == [
        (date(2025, 1, 1), date(2025, 12, 31)),
        (date(2024, 1, 1), date(2024, 12, 31)),
    ]


def test_fetch_history_years_follow_the_option_and_skip_legacy_and_range():
    five = Recorder()
    fetch_source_data(five, _ctx(historical_years=5), no_progress)
    assert sum(1 for n, _ in five.calls if n == "get_annual_totals") == 5
    for ctx in (
        _ctx(legacy=True),
        _ctx(Period.between(date(2025, 1, 1), date(2025, 6, 30))),
    ):
        client = Recorder()
        fetch_source_data(client, ctx, no_progress)
        assert not any(n == "get_annual_totals" for n, _ in client.calls)
        assert client.calls[-1][0] == "get_transaction_links"


def test_fetch_history_is_keyed_by_year_newest_first():
    src = fetch_source_data(DemoClient(), _ctx(), no_progress)
    assert list(src.history) == [2025, 2024, 2023]
    assert set(src.history[2025]) == {
        "total_income",
        "total_expense",
        "net_savings",
        "top_categories",
    }


def test_fetch_applies_global_filters_to_both_years():
    client = DemoClient()
    cats = {t["category_name"] for t in client.get_transactions() if t.get("category_name")}
    excluded = sorted(cats)[0]
    ctx = _ctx(filters=GlobalFilters(categories_exclude=(excluded,)))
    src = fetch_source_data(client, ctx, no_progress)
    assert all(t.get("category_name") != excluded for t in src.transactions + src.transactions_prev)
    assert len(src.transactions) < len(
        client.get_transactions(date(2025, 1, 1), date(2025, 12, 31))
    )


def test_fetch_filters_accounts_by_id():
    client = DemoClient()
    ids = [str(a["id"]) for a in client.get_asset_accounts()]
    ctx = _ctx(filters=GlobalFilters(accounts_exclude=(ids[0],)))
    src = fetch_source_data(client, ctx, no_progress)
    assert [str(a["id"]) for a in src.accounts] == ids[1:]
    assert ids[0] not in src.account_transactions


def test_fetch_deep_fetches_only_unknown_link_ids():
    seen: list[list[str]] = []

    class Linked(DemoClient):
        def get_transaction_links(self, resolve_types=True):
            known = self.get_transactions()[0]["id"]
            return [{"inward_id": known, "outward_id": "9999"}]

        def fetch_link_details(self, journal_ids):
            seen.append(list(journal_ids))
            return [{"id": "9999"}]

    src = fetch_source_data(Linked(), _ctx(fetch_links=True), no_progress)
    assert seen == [["9999"]]
    assert src.linked_extra == [{"id": "9999"}]
    quiet = fetch_source_data(Linked(), _ctx(), no_progress)
    assert quiet.linked_extra == [] and len(seen) == 1


def test_fetch_reports_progress_events():
    events: list[str] = []
    fetch_source_data(DemoClient(), _ctx(), lambda event, **f: events.append(event))
    assert events[0] == "fetch.start" and events[-1] == "fetch.done"
    assert "fetch.history_year" in events and "fetch.transactions_prev" in events
