import io
import os
import subprocess
import sys

from firefly_reports.render.charts import (
    create_area_chart,
    create_bar_chart,
    create_cashflow_combo,
    create_donut_chart,
    create_horizontal_bar_chart,
    create_line_chart,
    create_pie_chart,
)


def test_create_pie_chart_returns_bytesio():
    data = {"Food": 100.0, "Rent": 500.0}
    buf = create_pie_chart(data, "Test Chart")
    assert isinstance(buf, io.BytesIO)
    assert buf.getbuffer().nbytes > 0


def test_create_donut_chart_aggregates_others():
    data = {f"Cat {i}": float(100 - i) for i in range(12)}
    buf = create_donut_chart(data, "Test Donut", top_n=8)
    assert isinstance(buf, io.BytesIO)
    assert buf.getbuffer().nbytes > 0


def test_create_cashflow_combo_returns_bytesio():
    trend = [
        {"month": "2025-01", "income": 1000.0, "expense": 400.0, "net": 600.0},
        {"month": "2025-02", "income": 1200.0, "expense": 900.0, "net": 300.0},
    ]
    buf = create_cashflow_combo(trend, "Test Combo")
    assert isinstance(buf, io.BytesIO)
    assert buf.getbuffer().nbytes > 0


def test_empty_data_returns_placeholder():
    assert create_bar_chart({}, "Empty").getbuffer().nbytes > 0
    assert create_donut_chart({}, "Empty").getbuffer().nbytes > 0
    assert create_cashflow_combo([], "Empty").getbuffer().nbytes > 0


def test_create_bar_chart_returns_bytesio():
    data = {"Jan": 100.0, "Feb": 150.0}
    buf = create_bar_chart(data, "Test Bar Chart")
    assert isinstance(buf, io.BytesIO)
    assert buf.getbuffer().nbytes > 0


def test_create_horizontal_bar_chart_returns_bytesio():
    data = {"Category A": 100.0, "Category B": 150.0}
    buf = create_horizontal_bar_chart(data, "Test Horizontal Bar Chart")
    assert isinstance(buf, io.BytesIO)
    assert buf.getbuffer().nbytes > 0


def test_create_line_chart_returns_bytesio():
    data = {"Jan": 100.0, "Feb": 150.0, "Mar": 120.0}
    buf = create_line_chart(data, "Test Line Chart")
    assert isinstance(buf, io.BytesIO)
    assert buf.getbuffer().nbytes > 0


def test_create_area_chart_returns_bytesio():
    data = {"Jan": 100.0, "Feb": 150.0, "Mar": 120.0}
    buf = create_area_chart(data, "Test Area Chart")
    assert isinstance(buf, io.BytesIO)
    assert buf.getbuffer().nbytes > 0


def test_charts_do_not_touch_the_global_backend(tmp_path):
    code = (
        "import matplotlib; matplotlib.use('svg'); "
        "from firefly_reports.render import charts; charts.create_bar_chart({'a': 1.0}, 't'); "
        "import sys; assert matplotlib.get_backend() == 'svg'; "
        "assert 'matplotlib.pyplot' not in sys.modules"
    )
    env = {**os.environ, "MPLCONFIGDIR": str(tmp_path)}
    subprocess.run([sys.executable, "-c", code], check=True, env=env)
