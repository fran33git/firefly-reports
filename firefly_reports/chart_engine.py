"""Matplotlib chart generators for the PDF reports (Agg backend).

All charts share one visual identity: a restrained steel/slate palette,
no chart-junk (top/right spines removed, light grid only), locale-aware
compact number formatting and value labels where space allows.
"""

import io
from typing import Any

import matplotlib

matplotlib.use("Agg")  # Headless backend

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

from firefly_reports import i18n
from firefly_reports.i18n import T, t

# ─────────────────────────────────────────────
# Shared visual identity
# ─────────────────────────────────────────────
INK = "#1A1A1A"  # near-black, matches the PDF palette
MUTED = "#8A8A8A"  # tick labels, secondary text
GRID = "#E0E0E0"  # light grid lines

# Categorical palette (steel/slate family, prints well in B/W)
CATEGORICAL = [
    "#264653",
    "#2A6F97",
    "#468FAF",
    "#61A5C2",
    "#89C2D9",
    "#A9D6E5",
    "#6B7B8C",
    "#9AA7B1",
    "#C4CDD3",
    "#4E6E5D",
]

INCOME = "#2E7D5B"  # muted green
EXPENSE = "#B3564B"  # muted terracotta
NET = "#264653"  # deep slate

_DPI = 200


def _compact(value: float) -> str:
    """Compact number: 12300 -> "12.3k" (en) / "12,3k" (it)."""
    sign = "-" if value < 0 else ""
    a = abs(value)
    if a >= 1_000_000:
        s = f"{a / 1_000_000:.1f}".rstrip("0").rstrip(".") + "M"
    elif a >= 1000:
        s = f"{a / 1000:.1f}".rstrip("0").rstrip(".") + "k"
    else:
        s = f"{a:.0f}"
    if i18n.CURRENT_LANG == "it":
        s = s.replace(".", ",")
    return sign + s


def _fmt_pct(pct: float) -> str:
    s = f"{pct:.1f}"
    if i18n.CURRENT_LANG == "it":
        s = s.replace(".", ",")
    return f"{s}%"


def _short_months(labels: list[str]) -> list[str]:
    """Turn 'YYYY-MM' keys into localized short month names.

    Single-year periods get plain short names ("Jan"); periods spanning
    several years get a year suffix ("Jan '25"). Non-month labels are
    returned unchanged.
    """
    months = T.get("months", {})
    parsed: list[tuple[str, str]] = []
    for lab in labels:
        s = str(lab)
        if len(s) >= 7 and s[4] == "-" and s[5:7] in months:
            parsed.append((s[:4], months[s[5:7]][:3]))
        else:
            return [str(lab) for lab in labels]
    years = {y for y, _ in parsed}
    if len(years) > 1:
        return [f"{name} '{y[2:]}" for y, name in parsed]
    return [name for _, name in parsed]


def _style_ax(ax: Any, x_grid: bool = False) -> None:
    """Apply the shared minimal style to an axes."""
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(GRID)
    ax.grid(axis="x" if x_grid else "y", color=GRID, linewidth=0.6, linestyle="--", alpha=0.9)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED, labelsize=7.5, length=0)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: _compact(v)))


def _set_xticks(ax: Any, labels: list[str]) -> None:
    ax.set_xticks(range(len(labels)))
    if len(labels) > 8:
        ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
    else:
        ax.set_xticklabels(labels)


def _finish(fig: Any) -> io.BytesIO:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf


def _title(ax: Any, title: str) -> None:
    if title:
        ax.set_title(title, fontsize=9, fontweight="bold", color=INK, loc="left", pad=8)


# ─────────────────────────────────────────────
# Chart types
# ─────────────────────────────────────────────
def create_donut_chart(data: dict[str, float], title: str, top_n: int = 8) -> io.BytesIO:
    """Donut chart with center total and a side legend (label · pct).

    Slices beyond ``top_n`` are aggregated into an "Others" slice.
    """
    if not data:
        return _create_placeholder(title)

    items = sorted(data.items(), key=lambda kv: kv[1], reverse=True)
    if len(items) > top_n:
        others = sum(v for _, v in items[top_n - 1 :])
        items = items[: top_n - 1] + [(t("charts.others"), others)]

    values = [v for _, v in items]
    total = sum(values)

    fig, ax = plt.subplots(figsize=(6.9, 3.2), dpi=_DPI)
    wedges, *_ = ax.pie(
        values,
        startangle=90,
        counterclock=False,
        colors=[CATEGORICAL[i % len(CATEGORICAL)] for i in range(len(values))],
        wedgeprops={"width": 0.42, "edgecolor": "white", "linewidth": 1.5},
    )
    ax.text(
        0,
        0.10,
        _compact(total),
        ha="center",
        va="center",
        fontsize=15,
        fontweight="bold",
        color=INK,
    )
    ax.text(0, -0.20, t("charts.total"), ha="center", va="center", fontsize=9, color=MUTED)

    legend_labels = [f"{lab} · {_fmt_pct(v / total * 100 if total else 0)}" for lab, v in items]
    ax.legend(
        wedges,
        legend_labels,
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        frameon=False,
        fontsize=9.5,
        handlelength=1.2,
        handleheight=1.2,
        labelspacing=0.8,
    )
    _title(ax, title)
    return _finish(fig)


def create_pie_chart(data: dict[str, float], title: str) -> io.BytesIO:
    """Backward-compatible alias: renders the modern donut chart."""
    return create_donut_chart(data, title)


def create_bar_chart(data: dict[str, float], title: str, color: str = "#2A6F97") -> io.BytesIO:
    """Vertical bars with value labels on top."""
    if not data:
        return _create_placeholder(title)

    labels = _short_months(list(data.keys()))
    values = list(data.values())

    fig, ax = plt.subplots(figsize=(5.0, 2.8), dpi=_DPI)
    bars = ax.bar(range(len(labels)), values, width=0.6, color=color)
    ax.bar_label(bars, labels=[_compact(v) for v in values], padding=2, fontsize=7.5, color=INK)
    ax.margins(y=0.15)
    _style_ax(ax)
    _set_xticks(ax, labels)
    _title(ax, title)
    return _finish(fig)


def create_horizontal_bar_chart(
    data: dict[str, float], title: str, color: str = "#264653"
) -> io.BytesIO:
    """Horizontal bars, largest on top, with value labels at bar end."""
    if not data:
        return _create_placeholder(title)

    labels = list(data.keys())
    values = list(data.values())

    fig, ax = plt.subplots(figsize=(6.9, 2.9), dpi=_DPI)
    bars = ax.barh(range(len(labels)), values, height=0.62, color=color)
    ax.bar_label(bars, labels=[_compact(v) for v in values], padding=3, fontsize=9, color=INK)
    ax.invert_yaxis()  # Labels read top-to-bottom
    ax.margins(x=0.12)
    _style_ax(ax, x_grid=True)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=9.5, color=INK)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: _compact(v)))
    _title(ax, title)
    return _finish(fig)


def create_line_chart(data: dict[str, float], title: str) -> io.BytesIO:
    """Line chart with markers and a subtle area fill."""
    if not data:
        return _create_placeholder(title)

    labels = _short_months(list(data.keys()))
    values = list(data.values())

    fig, ax = plt.subplots(figsize=(6.7, 2.6), dpi=_DPI)
    ax.plot(range(len(labels)), values, marker="o", markersize=3.5, linewidth=1.8, color=NET)
    ax.fill_between(range(len(labels)), values, color=NET, alpha=0.08)
    if any(v < 0 for v in values):
        ax.axhline(0, color=INK, linewidth=0.6)
    ax.margins(x=0.03, y=0.15)
    _style_ax(ax)
    _set_xticks(ax, labels)
    _title(ax, title)
    return _finish(fig)


def create_area_chart(data: dict[str, float], title: str) -> io.BytesIO:
    """Cumulative area chart with a zero baseline."""
    if not data:
        return _create_placeholder(title)

    labels = _short_months(list(data.keys()))
    values = list(data.values())

    fig, ax = plt.subplots(figsize=(6.7, 2.5), dpi=_DPI)
    ax.fill_between(range(len(labels)), values, color="#468FAF", alpha=0.18)
    ax.plot(range(len(labels)), values, color="#2A6F97", linewidth=1.8)
    ax.axhline(0, color=INK, linewidth=0.6)
    ax.margins(x=0.03, y=0.15)
    _style_ax(ax)
    _set_xticks(ax, labels)
    _title(ax, title)
    return _finish(fig)


def create_cashflow_combo(trend: list[dict[str, Any]], title: str) -> io.BytesIO:
    """Monthly income vs expense grouped bars with a net cash flow line.

    ``trend`` is a list of dicts with ``month``, ``income``, ``expense``
    and ``net`` keys (the shape produced by build_kpi_scorecard).
    """
    if not trend:
        return _create_placeholder(title)

    labels = _short_months([str(r["month"]) for r in trend])
    inc = [float(r["income"]) for r in trend]
    exp = [float(r["expense"]) for r in trend]
    net = [float(r["net"]) for r in trend]
    x = list(range(len(labels)))

    fig, ax = plt.subplots(figsize=(6.7, 2.7), dpi=_DPI)
    w = 0.38
    b_inc = ax.bar([i - w / 2 for i in x], inc, width=w, color=INCOME, label=t("charts.income"))
    b_exp = ax.bar([i + w / 2 for i in x], exp, width=w, color=EXPENSE, label=t("charts.expense"))
    (l_net,) = ax.plot(
        x,
        net,
        color=NET,
        marker="o",
        markersize=3.5,
        linewidth=1.6,
        label=t("charts.net"),
        zorder=3,
    )
    ax.axhline(0, color=INK, linewidth=0.6)
    ax.legend(
        handles=[b_inc, b_exp, l_net],
        loc="lower center",
        bbox_to_anchor=(0.5, 1.0),
        ncols=3,
        frameon=False,
        fontsize=7.5,
        handlelength=1.4,
        columnspacing=1.6,
    )
    ax.margins(y=0.12)
    _style_ax(ax)
    _set_xticks(ax, labels)
    return _finish(fig)


def _create_placeholder(title: str) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(5.0, 2.6), dpi=_DPI)
    ax.text(
        0.5,
        0.5,
        t("charts.insufficient_data"),
        ha="center",
        va="center",
        fontsize=9,
        color=MUTED,
    )
    if title:
        ax.set_title(title, fontsize=9, color=MUTED, pad=8)
    ax.axis("off")
    return _finish(fig)
