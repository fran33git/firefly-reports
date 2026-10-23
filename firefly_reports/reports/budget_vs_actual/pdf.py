"""PDF renderers of the budget_vs_actual report."""

from decimal import Decimal
from typing import Any

from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    Spacer,
)

from firefly_reports.i18n import t
from firefly_reports.render.fmt import fmt_num, period_str
from firefly_reports.render.pdf.page import make_doc, page_decorator, title_block
from firefly_reports.render.pdf.styles import classic_styles, corporate_styles
from firefly_reports.render.pdf.tables import accounting_table

# ═══════════════════════════════════════════════════
# REPORT 1 — Cash Flow Statement
# (3 pages: Inflows | Outflows | Monthly summary)
# ═══════════════════════════════════════════════════


def _render_legacy_budget_vs_actual(data: dict[str, Any], output_path: str) -> None:
    st = classic_styles()
    period = period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    fn = page_decorator(data["owner"], t("titles.budget_vs_actual_report"), period)
    doc = make_doc(output_path, fn)
    story = []

    story += title_block(
        t("titles.budget_vs_actual_report"),
        data["owner"],
        period,
        t("pdf.subtitle_budget"),
        st,
    )

    CW = [6.5 * cm, 2.8 * cm, 2.8 * cm, 2.8 * cm, 2.8 * cm]

    hdr = [
        [
            Paragraph(t("common.budget"), st["col_header_l"]),
            Paragraph(t("common.limit"), st["col_header"]),
            Paragraph(t("common.actual"), st["col_header"]),
            Paragraph(t("common.variance"), st["col_header"]),
            Paragraph(t("common.variance_pct"), st["col_header"]),
        ]
    ]
    rows_tbl = list(hdr)

    for i, r in enumerate(data["rows"]):
        is_first = i == 0
        var = r["variance"]
        rows_tbl.append(
            [
                Paragraph(r["budget_name"], st["cell_l"]),
                Paragraph(fmt_num(r["limit"], show_sym=is_first, sym=sym), st["cell_r"]),
                Paragraph(fmt_num(r["actual"], show_sym=is_first, sym=sym), st["cell_r"]),
                Paragraph(fmt_num(var, parens_neg=True, show_sym=is_first, sym=sym), st["cell_r"]),
                Paragraph(f"{r['variance_pct']} %", st["cell_r"]),
            ]
        )

    rows_tbl.append(
        [
            Paragraph(t("pdf.budgeted_total"), st["total_l"]),
            Paragraph(fmt_num(data["total_limit"], show_sym=True, sym=sym), st["total_r"]),
            Paragraph(fmt_num(data["total_actual"], show_sym=True, sym=sym), st["total_r"]),
            Paragraph(
                fmt_num(data["total_variance"], parens_neg=True, show_sym=True, sym=sym),
                st["total_r"],
            ),
            Paragraph("", st["cell_r"]),
        ]
    )
    tot_idx = len(rows_tbl) - 1

    tbl = accounting_table(rows_tbl, CW, total_rows=[tot_idx])
    story.append(tbl)

    if data["unbudgeted_spending"] > 0:
        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph(t("pdf.unbudgeted").upper(), st["section"]))
        ub_rows = [
            [
                Paragraph(t("pdf.unbudgeted"), st["cell_l"]),
                Paragraph(
                    fmt_num(data["unbudgeted_spending"], show_sym=True, sym=sym), st["cell_r"]
                ),
            ],
        ]
        story.append(accounting_table(ub_rows, [13.5 * cm, 4.4 * cm]))

    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(t("pdf.expected_note"), st["small"]))

    doc.build(story)


def _render_modern_budget_vs_actual(data: dict[str, Any], output_path: str) -> None:
    """Modern portrait budget analysis with pace tracking."""
    st = corporate_styles()
    period = period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    owner = data["owner"]

    fn = page_decorator(owner, t("titles.budget_vs_actual_analysis"), period)
    doc = make_doc(output_path, fn)
    story = []

    story += title_block(
        t("titles.budget_vs_actual_analysis"), owner, period, t("excel.sheet_budget").upper(), st
    )

    # Budget | Limit | Actual | Variance | Pace
    # Total width = 17.4 cm
    CW = [6.2 * cm, 2.8 * cm, 2.8 * cm, 2.8 * cm, 2.8 * cm]

    hdr = [
        [
            Paragraph(t("common.budget"), st["col_header_l"]),
            Paragraph(t("common.limit"), st["col_header"]),
            Paragraph(t("common.actual"), st["col_header"]),
            Paragraph(t("common.variance"), st["col_header"]),
            Paragraph(t("common.pace"), st["col_header"]),
        ]
    ]
    rows = list(hdr)

    for i, r in enumerate(data["rows"]):
        is_first = i == 0

        pace_status = r.get("pace_status", "N/A")
        spent_pct = r.get("spent_pct", Decimal("0"))

        # Color coding for pace
        pace_color_hex = "#1A1A1A"  # DARK
        if pace_status == "AHEAD":
            pace_color_hex = "#c0392b"  # Red (spending too fast)
        elif pace_status == "UNDER":
            pace_color_hex = "#27ae60"  # Green (spending slowly)
        elif pace_status == "ON TRACK":
            pace_color_hex = "#2980b9"  # Blue

        pace_key = f"common.pace_{pace_status.lower().replace(' ', '_').replace('/', '')}"
        pace_label = t(pace_key)
        pace_para = Paragraph(
            f"<font color={pace_color_hex}>{pace_label} ({spent_pct}%)</font>", st["cell_r"]
        )

        rows.append(
            [
                Paragraph(r["budget_name"], st["cell_l"]),
                Paragraph(fmt_num(r["limit"], show_sym=is_first, sym=sym), st["cell_r"]),
                Paragraph(fmt_num(r["actual"], show_sym=is_first, sym=sym), st["cell_r"]),
                Paragraph(
                    fmt_num(r["variance"], parens_neg=True, show_sym=is_first, sym=sym),
                    st["cell_r"],
                ),
                pace_para,
            ]
        )

    # Totals
    rows.append(
        [
            Paragraph(t("pdf.budgeted_total"), st["total_l"]),
            Paragraph(fmt_num(data["total_limit"], show_sym=True, sym=sym), st["total_r"]),
            Paragraph(fmt_num(data["total_actual"], show_sym=True, sym=sym), st["total_r"]),
            Paragraph(
                fmt_num(data["total_variance"], parens_neg=True, show_sym=True, sym=sym),
                st["total_r"],
            ),
            Paragraph(f"{data['elapsed_pct']}% ELAPSED", st["cell_r_bold"]),
        ]
    )

    story.append(accounting_table(rows, CW, total_rows=[len(rows) - 1]))

    if data.get("unbudgeted_spending", 0) > 0:
        story.append(Spacer(1, 0.6 * cm))
        story.append(Paragraph(t("pdf.unbudgeted").upper(), st["section"]))
        ub_rows = [
            [
                Paragraph(t("pdf.unbudgeted"), st["cell_l"]),
                Paragraph(
                    fmt_num(data["unbudgeted_spending"], show_sym=True, sym=sym), st["cell_r"]
                ),
            ],
        ]
        story.append(accounting_table(ub_rows, [13.0 * cm, 4.4 * cm]))

    doc.build(story)


def render_budget_vs_actual_pdf(data: dict, path: str, legacy: bool = False):
    if legacy:
        return _render_legacy_budget_vs_actual(data, path)
    return _render_modern_budget_vs_actual(data, path)
