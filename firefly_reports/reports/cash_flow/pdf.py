"""PDF renderers of the cash_flow report."""

from typing import Any

from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    Spacer,
)

from firefly_reports import i18n
from firefly_reports.i18n import t
from firefly_reports.render.fmt import fmt_num, period_str
from firefly_reports.render.pdf.page import make_doc, page_decorator, title_block
from firefly_reports.render.pdf.styles import classic_styles
from firefly_reports.render.pdf.tables import accounting_table

# ═══════════════════════════════════════════════════
# REPORT 1 — Cash Flow Statement
# (3 pages: Inflows | Outflows | Monthly summary)
# ═══════════════════════════════════════════════════


def _render_legacy_cash_flow(data: dict[str, Any], output_path: str) -> None:
    st = classic_styles()
    period = period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    owner = data["owner"]

    fn = page_decorator(owner, t("titles.cash_flow"), period)
    doc = make_doc(output_path, fn)
    story = []

    # ═══ PAGE 0 — Waterfall by activity (R-INT-03), only when account data available
    wf = data.get("waterfall") or {}
    if wf.get("closing_cash") is not None:
        story += title_block(t("titles.cash_flow"), owner, period, t("pdf.section_waterfall"), st)
        CW0 = [7.4 * cm, 3.4 * cm, 3.4 * cm, 3.2 * cm]
        hdr0 = [
            [
                Paragraph("", st["col_header_l"]),
                Paragraph(t("common.income"), st["col_header"]),
                Paragraph(t("common.expense"), st["col_header"]),
                Paragraph(t("common.net_flow"), st["col_header"]),
            ]
        ]
        rows0 = list(hdr0)
        for sec_key, label_key in (
            ("operating", "pdf.wf_operating"),
            ("investing", "pdf.wf_investing"),
            ("financing", "pdf.wf_financing"),
        ):
            sec = wf[sec_key]
            rows0.append(
                [
                    Paragraph(t(label_key), st["cell_l"]),
                    Paragraph(
                        fmt_num(sec["in"], show_sym=sec_key == "operating", sym=sym), st["cell_r"]
                    ),
                    Paragraph(
                        fmt_num(sec["out"], show_sym=sec_key == "operating", sym=sym), st["cell_r"]
                    ),
                    Paragraph(
                        fmt_num(
                            sec["net"], parens_neg=True, show_sym=sec_key == "operating", sym=sym
                        ),
                        st["cell_r"],
                    ),
                ]
            )
        rows0.append(
            [
                Paragraph(t("pdf.wf_net_change"), st["total_l"]),
                Paragraph("", st["total_r"]),
                Paragraph("", st["total_r"]),
                Paragraph(
                    fmt_num(wf["net_change"], parens_neg=True, show_sym=True, sym=sym),
                    st["total_r"],
                ),
            ]
        )
        rows0.append(
            [
                Paragraph(t("pdf.wf_opening"), st["cell_l"]),
                Paragraph("", st["cell_r"]),
                Paragraph("", st["cell_r"]),
                Paragraph(fmt_num(wf["opening_cash"], parens_neg=True, sym=sym), st["cell_r"]),
            ]
        )
        rows0.append(
            [
                Paragraph(t("pdf.wf_closing"), st["grand_l"]),
                Paragraph("", st["grand_r"]),
                Paragraph("", st["grand_r"]),
                Paragraph(
                    fmt_num(wf["closing_cash"], parens_neg=True, show_sym=True, sym=sym),
                    st["grand_r"],
                ),
            ]
        )
        story.append(
            accounting_table(rows0, CW0, total_rows=[len(rows0) - 3], grand_rows=[len(rows0) - 1])
        )
        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph(t("pdf.wf_note"), st["small"]))
        story.append(PageBreak())

    # ── Column widths: label + amount
    CW = [13.5 * cm, 4.4 * cm]  # [description, amount]

    # ═══ PAGE 1 — Inflows
    story += title_block(t("titles.cash_flow"), owner, period, t("pdf.section_inflows"), st)

    # column headers
    hdr = [
        [Paragraph(t("common.category_item"), st["col_header_l"]), Paragraph(sym, st["col_header"])]
    ]
    rows = list(hdr)
    for i, item in enumerate(data["inflows"]):
        is_first = i == 0
        num_str = fmt_num(item["amount"], show_sym=is_first, sym=sym)
        rows.append(
            [
                Paragraph(item["category"], st["cell_l_ind"]),
                Paragraph(num_str, st["cell_r"]),
            ]
        )

    total_str = fmt_num(data["total_in"], show_sym=True, sym=sym)
    rows.append(
        [
            Paragraph(t("common.total_income"), st["total_l"]),
            Paragraph(total_str, st["total_r"]),
        ]
    )
    total_idx = len(rows) - 1

    tbl = accounting_table(rows, CW, total_rows=[total_idx], grand_rows=[])
    story.append(tbl)
    story.append(Spacer(1, 0.5 * cm))

    # footnote
    story.append(
        Paragraph(
            t("pdf.note_amounts_deposit"),
            st["small"],
        )
    )

    # ═══ PAGE 2 — Outflows
    story.append(PageBreak())
    story += title_block(t("titles.cash_flow"), owner, period, t("pdf.section_outflows"), st)

    hdr2 = [
        [Paragraph(t("common.category_item"), st["col_header_l"]), Paragraph(sym, st["col_header"])]
    ]
    rows2 = list(hdr2)
    for i, item in enumerate(data["outflows"]):
        is_first = i == 0
        num_str = fmt_num(item["amount"], show_sym=is_first, sym=sym)
        rows2.append(
            [
                Paragraph(item["category"], st["cell_l_ind"]),
                Paragraph(num_str, st["cell_r"]),
            ]
        )
    total_str2 = fmt_num(data["total_out"], show_sym=True, sym=sym)
    rows2.append(
        [
            Paragraph(t("common.total_expense"), st["total_l"]),
            Paragraph(total_str2, st["total_r"]),
        ]
    )
    t2_idx = len(rows2) - 1
    tbl2 = accounting_table(rows2, CW, total_rows=[t2_idx])
    story.append(tbl2)
    story.append(Spacer(1, 0.5 * cm))
    story.append(
        Paragraph(
            t("pdf.note_amounts_withdrawal"),
            st["small"],
        )
    )

    # ═══ PAGE 3 — Monthly cash flow + final summary
    story.append(PageBreak())
    story += title_block(t("titles.cash_flow"), owner, period, t("pdf.section_monthly"), st)

    months_it = i18n.current().section("months")

    CW3 = [6.5 * cm, 3.5 * cm, 3.5 * cm, 4.4 * cm]

    if len(data["by_month"]) > 0:
        hdr3 = [
            [
                Paragraph(t("common.month"), st["col_header_l"]),
                Paragraph(t("common.income"), st["col_header"]),
                Paragraph(t("common.expense"), st["col_header"]),
                Paragraph(t("common.net_flow"), st["col_header"]),
            ]
        ]
        rows3 = list(hdr3)
        for i, (mk, vals) in enumerate(data["by_month"].items()):
            y, m = mk.split("-")
            month_label = f"{months_it.get(m, m)} {y}"
            is_first = i == 0
            net = vals["net"]
            net_str = fmt_num(net, show_sym=is_first, sym=sym, parens_neg=True)
            rows3.append(
                [
                    Paragraph(month_label, st["cell_l"]),
                    Paragraph(fmt_num(vals["in"], show_sym=is_first, sym=sym), st["cell_r"]),
                    Paragraph(fmt_num(vals["out"], show_sym=is_first, sym=sym), st["cell_r"]),
                    Paragraph(net_str, st["cell_r"]),
                ]
            )
        tbl3 = accounting_table(rows3, CW3)
        story.append(tbl3)
        story.append(Spacer(1, 0.8 * cm))

    # Final summary
    story.append(Paragraph(t("pdf.section_period_summary"), st["section"]))

    CW_sum = [13.5 * cm, 4.4 * cm]
    sum_rows = [
        [
            Paragraph(t("pdf.total_income_period"), st["cell_l"]),
            Paragraph(fmt_num(data["total_in"], show_sym=True, sym=sym), st["cell_r"]),
        ],
        [
            Paragraph(t("pdf.total_expense_period"), st["cell_l"]),
            Paragraph(f"({fmt_num(data['total_out'], show_sym=True, sym=sym)})", st["cell_r"]),
        ],
        [
            Paragraph(t("pdf.net_flow_period"), st["grand_l"]),
            Paragraph(fmt_num(data["net"], show_sym=True, sym=sym, parens_neg=True), st["grand_r"]),
        ],
    ]
    sum_tbl = accounting_table(sum_rows, CW_sum, total_rows=[1], grand_rows=[2])
    story.append(sum_tbl)

    doc.build(story)


def render_cash_flow_pdf(data: dict, path: str, legacy: bool = False) -> None:
    if legacy:
        return _render_legacy_cash_flow(data, path)
    return _render_legacy_cash_flow(data, path)  # TODO: Modern
