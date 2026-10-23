"""PDF renderers of the net_worth report."""

from typing import Any

from reportlab.lib.units import cm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    Spacer,
)

from firefly_reports.i18n import t
from firefly_reports.render.fmt import fmt_date, fmt_num
from firefly_reports.render.pdf.page import make_doc, page_decorator, title_block
from firefly_reports.render.pdf.styles import classic_styles, corporate_styles
from firefly_reports.render.pdf.tables import accounting_table

# ═══════════════════════════════════════════════════
# REPORT 1 — Cash Flow Statement
# (3 pages: Inflows | Outflows | Monthly summary)
# ═══════════════════════════════════════════════════


def _render_legacy_net_worth(data: dict[str, Any], output_path: str) -> None:
    st = classic_styles()
    as_of = fmt_date(data["as_of_date"])
    period_label = t("pdf.as_of").format(date=as_of)
    sym = data["currency"]
    owner = data["owner"]

    fn = page_decorator(owner, t("titles.net_worth"), period_label)
    doc = make_doc(output_path, fn)
    story = []

    story += title_block(
        t("titles.net_worth"),
        owner,
        period_label,
        t("pdf.subtitle_net_worth"),
        st,
    )

    CW = [8.5 * cm, 3.5 * cm, 3.0 * cm, 2.9 * cm]  # name | iban | currency | balance

    for group in data["groups"]:
        if not group["accounts"]:
            continue

        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph(group["role_label"].upper(), st["section"]))

        hdr = [
            [
                Paragraph(t("common.account"), st["col_header_l"]),
                Paragraph("IBAN", st["col_header_l"]),
                Paragraph(t("common.currency_col"), st["col_header"]),
                Paragraph(t("common.balance"), st["col_header"]),
            ]
        ]
        rows = list(hdr)
        for i, acc in enumerate(group["accounts"]):
            rows.append(
                [
                    Paragraph(acc["name"], st["cell_l"]),
                    Paragraph(acc["iban_masked"], st["cell_l"]),
                    Paragraph(acc["currency_code"], st["cell_r"]),
                    Paragraph(
                        fmt_num(acc["balance"], show_sym=(i == 0), sym=sym, parens_neg=True),
                        st["cell_r"],
                    ),
                ]
            )
        rows.append(
            [
                Paragraph(t("pdf.subtotal").format(role=group["role_label"]), st["total_l"]),
                Paragraph("", st["cell_l"]),
                Paragraph("", st["cell_r"]),
                Paragraph(
                    fmt_num(group["subtotal"], show_sym=True, sym=sym, parens_neg=True),
                    st["total_r"],
                ),
            ]
        )
        t_idx = len(rows) - 1
        story.append(KeepTogether([accounting_table(rows, CW, total_rows=[t_idx])]))

    # ── Final summary
    story.append(Spacer(1, 0.8 * cm))
    story.append(Paragraph(t("pdf.section_net_worth_summary"), st["section"]))

    CW_s = [13.5 * cm, 4.4 * cm]
    sum_rows = [
        [
            Paragraph(t("common.total_assets"), st["cell_l"]),
            Paragraph(fmt_num(data["total_assets"], show_sym=True, sym=sym), st["cell_r"]),
        ],
        [
            Paragraph(t("common.total_liabilities"), st["cell_l"]),
            Paragraph(
                f"({fmt_num(abs(data['total_liabilities']), show_sym=True, sym=sym)})",
                st["cell_r"],
            ),
        ],
        [
            Paragraph(t("common.net_worth"), st["grand_l"]),
            Paragraph(
                fmt_num(data["net_worth"], show_sym=True, sym=sym, parens_neg=True), st["grand_r"]
            ),
        ],
    ]
    story.append(accounting_table(sum_rows, CW_s, total_rows=[1], grand_rows=[2]))
    story.append(Spacer(1, 0.4 * cm))
    story.append(
        Paragraph(
            t("pdf.net_worth_note").format(date=period_label, count=data["account_count"]),
            st["small"],
        )
    )

    doc.build(story)


def _render_modern_net_worth(data: dict[str, Any], output_path: str) -> None:
    """Modern portrait net worth statement with update tracking."""
    st = corporate_styles()
    as_of = fmt_date(data["as_of_date"])
    period_label = t("pdf.as_of").format(date=as_of)
    sym = data["currency"]
    owner = data["owner"]

    fn = page_decorator(owner, t("titles.net_worth"), period_label)
    doc = make_doc(output_path, fn)
    story = []

    story += title_block(
        t("titles.net_worth"),
        owner,
        period_label,
        t("titles.corporate_wealth"),
        st,
    )

    # Name | IBAN | Last Update | Balance
    # available 17.4cm
    CW = [7.0 * cm, 4.0 * cm, 3.4 * cm, 3.0 * cm]

    for group in data["groups"]:
        if not group["accounts"]:
            continue

        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph(group["role_label"].upper(), st["section"]))

        hdr = [
            [
                Paragraph(t("common.account"), st["col_header_l"]),
                Paragraph("IBAN", st["col_header_l"]),
                Paragraph(t("common.last_update"), st["col_header"]),
                Paragraph(t("common.balance"), st["col_header"]),
            ]
        ]
        rows = list(hdr)
        for i, acc in enumerate(group["accounts"]):
            updated_at = acc.get("updated_at") or "—"
            if updated_at and len(updated_at) > 10:
                updated_at = updated_at[:10]

            rows.append(
                [
                    Paragraph(acc["name"], st["cell_l"]),
                    Paragraph(acc["iban_masked"], st["cell_l"]),
                    Paragraph(updated_at, st["cell_r"]),
                    Paragraph(
                        fmt_num(acc["balance"], show_sym=(i == 0), sym=sym, parens_neg=True),
                        st["cell_r"],
                    ),
                ]
            )
        rows.append(
            [
                Paragraph(t("pdf.subtotal").format(role=group["role_label"]), st["total_l"]),
                Paragraph("", st["cell_l"]),
                Paragraph("", st["cell_r"]),
                Paragraph(
                    fmt_num(group["subtotal"], show_sym=True, sym=sym, parens_neg=True),
                    st["total_r"],
                ),
            ]
        )
        t_idx = len(rows) - 1
        story.append(KeepTogether([accounting_table(rows, CW, total_rows=[t_idx])]))

    # ── Final summary
    story.append(Spacer(1, 1.0 * cm))
    story.append(Paragraph(t("pdf.section_net_worth_summary"), st["section"]))

    CW_s = [13.0 * cm, 4.4 * cm]
    sum_rows = [
        [
            Paragraph(t("common.total_assets"), st["cell_l"]),
            Paragraph(fmt_num(data["total_assets"], show_sym=True, sym=sym), st["cell_r"]),
        ],
        [
            Paragraph(t("common.total_liabilities"), st["cell_l"]),
            Paragraph(
                f"({fmt_num(abs(data['total_liabilities']), show_sym=True, sym=sym)})",
                st["cell_r"],
            ),
        ],
        [
            Paragraph(t("common.net_worth"), st["grand_l"]),
            Paragraph(
                fmt_num(data["net_worth"], show_sym=True, sym=sym, parens_neg=True), st["grand_r"]
            ),
        ],
    ]
    story.append(accounting_table(sum_rows, CW_s, total_rows=[1], grand_rows=[2]))
    story.append(Spacer(1, 0.5 * cm))
    story.append(
        Paragraph(
            t("pdf.net_worth_note").format(date=period_label, count=data["account_count"]),
            st["small"],
        )
    )

    doc.build(story)


def render_net_worth_pdf(data: dict, path: str, legacy: bool = False) -> None:
    if legacy:
        return _render_legacy_net_worth(data, path)
    return _render_modern_net_worth(data, path)
