"""The facade end to end on the offline demo data."""

import json
import os
from datetime import date
from pathlib import Path

import pytest
import responses

from firefly_reports import api, i18n
from firefly_reports.demo.client import DemoClient
from firefly_reports.errors import FireflyAPIError
from firefly_reports.reports.options import Period, ReportOptions

YEAR_FULL = json.loads(
    (Path(__file__).parent / "golden" / "pipeline" / "year_full.json").read_text(encoding="utf-8")
)


def test_generate_reports_with_demo_client(tmp_path):
    options = ReportOptions(tags=("tax",), all_tags=True, fetch_links=True)
    result = api.generate_reports(DemoClient(), Period.for_year(2025), options, tmp_path)
    assert result.ok and not result.failures
    assert sorted(f.path.name for f in result.files) == YEAR_FULL["files"]
    assert result.headline.transactions > 0
    assert result.headline.net == result.headline.total_in - result.headline.total_out


def test_build_reports_is_pure(tmp_path):
    src = api.fetch_data(DemoClient(), Period.for_year(2025), ReportOptions())
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        first = api.build_reports(src, Period.for_year(2025), ReportOptions())
        second = api.build_reports(src, Period.for_year(2025), ReportOptions())
        assert list(tmp_path.iterdir()) == []
    finally:
        os.chdir(cwd)
    assert first == second and "cash_flow" in first


@responses.activate
def test_fetch_data_wraps_request_errors():
    responses.add(responses.GET, "https://firefly.invalid/api/v1/transactions", status=500)
    source = api.connect("https://firefly.invalid", "token", request_delay=0)
    with pytest.raises(FireflyAPIError) as excinfo:
        api.fetch_data(source, Period.between(date(2025, 1, 1), date(2025, 1, 31)), ReportOptions())
    import requests

    assert isinstance(excinfo.value.__cause__, requests.HTTPError)
    assert "500" in str(excinfo.value)


def test_options_lang_does_not_leak():
    i18n.load("en")
    src = api.fetch_data(DemoClient(), Period.for_year(2025), ReportOptions())
    built = api.build_reports(src, Period.for_year(2025), ReportOptions(lang="it"))
    assert i18n.current().lang == "en"
    assert built["cash_flow"]["owner"] is not None


def test_available_reports_describe_the_registry():
    infos = {i.key: i for i in api.available_reports()}
    assert len(infos) == 28
    assert infos["yoy"].requires_year and infos["cash_flow"].requires_year is False
    assert infos["audit_log"].mode == "legacy" and infos["journal"].mode == "standard"
    assert infos["cash_flow"].mode == "any"
    assert infos["cash_flow"].formats == frozenset({"pdf", "xlsx"})
    assert infos["journal"].formats == frozenset({"pdf"})


def test_write_reports_reports_progress(tmp_path):
    events: list[str] = []
    options = ReportOptions(excel=False)
    period = Period.for_year(2025)
    built = api.build_reports(api.fetch_data(DemoClient(), period, options), period, options)
    result = api.write_reports(
        built, period, options, tmp_path, progress=lambda event, **f: events.append(event)
    )
    assert result.ok and "write.ok" in events and "write.xlsx_start" not in events
