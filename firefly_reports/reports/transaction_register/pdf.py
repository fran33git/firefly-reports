"""PDF renderers of the transaction_register report."""

from decimal import Decimal
from typing import Any

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from firefly_reports import i18n
from firefly_reports.i18n import t
from firefly_reports.render.fmt import flatten_rows, fmt_date, fmt_num, period_str
from firefly_reports.render.pdf.page import make_doc, page_decorator, title_block
from firefly_reports.render.pdf.palette import (
    DARK,
    LIGHT,
    RULE,
    TOTAL_BG,
)
from firefly_reports.render.pdf.styles import classic_styles, corporate_styles

# ═══════════════════════════════════════════════════
# REPORT 1 — Cash Flow Statement
# (3 pages: Inflows | Outflows | Monthly summary)
# ═══════════════════════════════════════════════════


def _render_legacy_transaction_register(data: dict[str, Any], output_path: str) -> None:
    st = classic_styles()
    period = period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    owner = data["owner"]

    fn = page_decorator(owner, t("titles.transaction_register"), period, landscape_mode=True)
    doc = make_doc(output_path, fn, landscape_mode=True)

    story = []
    story += title_block(
        t("titles.transaction_register"),
        owner,
        period,
        t("pdf.transactions_register").format(count=data["total_transactions"]),
        st,
    )

    # Landscape columns: available width = 26.7 cm (29.7 - 2×1.5)
    # date | description | type | category | amount | running balance
    CW = [2.4 * cm, 9.8 * cm, 2.4 * cm, 5.2 * cm, 3.5 * cm, 3.4 * cm]

    hdr = [
        [
            Paragraph(t("common.date"), st["col_header_l"]),
            Paragraph(t("common.description"), st["col_header_l"]),
            Paragraph(t("common.type"), st["col_header"]),
            Paragraph(t("common.category"), st["col_header_l"]),
            Paragraph(t("common.amount"), st["col_header"]),
            Paragraph(t("common.running_balance"), st["col_header"]),
        ]
    ]
    rows = list(hdr)

    # Flatten grouped data for legacy rendering
    flat_rows = flatten_rows(data["rows"])

    # Group rows by month
    current_month = None
    for r in flat_rows:
        month_key = r["date"][:7]
        if month_key != current_month:
            current_month = month_key
            y, m = month_key.split("-")
            months_it = i18n.current().section("months")
            month_label = f"{months_it.get(m, m)} {y}".upper()
            rows.append(
                [
                    Paragraph(
                        month_label,
                        ParagraphStyle(
                            "mh", fontName="Helvetica-Bold", fontSize=8, textColor=LIGHT
                        ),
                    ),
                    Paragraph("", st["cell_l"]),
                    Paragraph("", st["cell_l"]),
                    Paragraph("", st["cell_l"]),
                    Paragraph("", st["cell_r"]),
                    Paragraph("", st["cell_r"]),
                ]
            )

        amt = r["amount"]
        bal = r["running_balance"]
        amt_str = fmt_num(amt, show_sym=False, parens_neg=True)
        bal_str = fmt_num(bal, show_sym=False, parens_neg=True)

        desc = r["description"]
        if len(desc) > 75:
            desc = desc[:72] + "…"
        cat = r["category"] or "—"
        if len(cat) > 30:
            cat = cat[:27] + "…"

        rows.append(
            [
                Paragraph(r["date"], st["cell_l"]),
                Paragraph(desc, st["cell_l"]),
                Paragraph(r["type"][:3].upper(), st["cell_r"]),
                Paragraph(cat, st["cell_l"]),
                Paragraph(amt_str, st["cell_r"]),
                Paragraph(bal_str, st["cell_r"]),
            ]
        )

    # Grand total row
    rows.append(
        [
            Paragraph("", st["cell_l"]),
            Paragraph(t("pdf.closing_balance_period"), st["total_l"]),
            Paragraph("", st["cell_r"]),
            Paragraph("", st["cell_l"]),
            Paragraph("", st["cell_r"]),
            Paragraph(
                fmt_num(
                    data["rows"][-1]["running_balance"] if data["rows"] else Decimal(0),
                    show_sym=True,
                    sym=sym,
                    parens_neg=True,
                ),
                st["total_r"],
            ),
        ]
    )
    grand_idx = len(rows) - 1

    tbl = Table(rows, colWidths=CW, repeatRows=1)
    cmds = [
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, RULE),
        ("LINEABOVE", (0, grand_idx), (-1, grand_idx), 1.0, DARK),
        ("LINEBELOW", (0, grand_idx), (-1, grand_idx), 0.5, DARK),
        ("BACKGROUND", (0, grand_idx), (-1, grand_idx), TOTAL_BG),
        ("FONTNAME", (0, grand_idx), (-1, grand_idx), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, -2), 8),
    ]
    tbl.setStyle(TableStyle(cmds))
    story.append(tbl)

    story.append(Spacer(1, 0.4 * cm))
    story.append(
        Paragraph(
            t("pdf.total_transactions").format(count=data["total_transactions"])
            + "WIT = Prelievo   DEP = Versamento   TRF = Giroconto",
            st["small"],
        )
    )

    doc.build(story)


def _render_modern_transaction_register(data: dict[str, Any], output_path: str) -> None:
    """Modern landscape Transaction Detail Ledger with split grouping (R-INT-06).

    One master row per transaction group; split sub-rows only for groups with
    more than one split. Notes appear as small gray lines under their row.
    """
    st = corporate_styles()
    period = period_str(data["period_start"], data["period_end"])
    sym = data["currency"]
    owner = data["owner"]

    fn = page_decorator(owner, t("titles.transaction_register"), period, landscape_mode=True)
    doc = make_doc(output_path, fn, landscape_mode=True)

    story = []
    story += title_block(
        t("titles.transaction_register"),
        owner,
        period,
        t("pdf.transactions_register").format(count=data["total_transactions"]),
        st,
    )

    # Date | Type | Description | From | To | Category | Budget | Amount | ID
    # Available width = 26.1 cm
    CW = [2.0 * cm, 1.3 * cm, 6.2 * cm, 3.4 * cm, 3.4 * cm, 2.9 * cm, 2.2 * cm, 3.0 * cm, 1.7 * cm]

    hdr = [
        [
            Paragraph(t("common.date"), st["col_header_l"]),
            Paragraph(t("common.type"), st["col_header_l"]),
            Paragraph(t("common.description"), st["col_header_l"]),
            Paragraph(t("common.source"), st["col_header_l"]),
            Paragraph(t("common.destination"), st["col_header_l"]),
            Paragraph(t("common.category"), st["col_header_l"]),
            Paragraph(t("common.budget"), st["col_header_l"]),
            Paragraph(t("common.amount"), st["col_header"]),
            Paragraph(t("common.id"), st["col_header"]),
        ]
    ]
    rows: list[Any] = list(hdr)

    type_badges = {
        "withdrawal": t("pdf.tx_type_w"),
        "deposit": t("pdf.tx_type_d"),
        "transfer": t("pdf.tx_type_t"),
    }

    def _amount_cells(amount: Decimal, split: dict | None, bold: bool) -> list:
        amt_str = fmt_num(amount, show_sym=False, parens_neg=True)
        cells = [Paragraph(f"<b>{amt_str}</b>" if bold else amt_str, st["cell_r"])]
        if split:
            f_amt = split.get("foreign_amount")
            f_curr = split.get("foreign_currency_code")
            if f_amt and f_curr:
                f_str = f"{f_curr} {fmt_num(Decimal(str(f_amt)), show_sym=False)}"
                cells.append(Paragraph(f_str, st["small"]))
        return cells

    def _notes_row(notes: str) -> list | None:
        notes = (notes or "").strip()
        if not notes:
            return None
        if len(notes) > 90:
            notes = notes[:87] + "…"
        return [
            Paragraph("", st["cell_l"]),
            Paragraph("", st["cell_l"]),
            Paragraph(notes, st["split_indent"]),
            Paragraph("", st["cell_l"]),
            Paragraph("", st["cell_l"]),
            Paragraph("", st["cell_l"]),
            Paragraph("", st["cell_l"]),
            Paragraph("", st["cell_r"]),
            Paragraph("", st["small"]),
        ]

    for group in data["rows"]:
        splits = group.get("splits", [])
        single = len(splits) == 1

        tx_type = str(group.get("type") or "")
        badge = type_badges.get(tx_type, tx_type[:1].upper())
        if group.get("reconciled"):
            badge += " R"
        if group.get("has_attachments"):
            badge += " A"

        amount = group["total_abs"] if group["type"] == "transfer" else group["total"]

        date_cells = [Paragraph(fmt_date(group["date"]), st["cell_l"])]
        first_split = splits[0] if splits else {}
        if single:
            book = first_split.get("book_date") or ""
            if book and book != group["date"]:
                date_cells.append(
                    Paragraph(f"{t('common.book_date')}: {fmt_date(book)}", st["small"])
                )

        rows.append(
            [
                date_cells,
                Paragraph(badge, st["cell_l"]),
                Paragraph(f"<b>{group['description']}</b>", st["cell_l"]),
                Paragraph(group["source"], st["cell_l"]),
                Paragraph(group["destination"], st["cell_l"]),
                Paragraph(first_split.get("category") or "—" if single else "", st["cell_l"]),
                Paragraph(first_split.get("budget") or "—" if single else "", st["cell_l"]),
                _amount_cells(amount, first_split if single else None, bold=True),
                Paragraph(f"#{group.get('journal_id', '')}", st["small"]),
            ]
        )

        if single:
            note_row = _notes_row(first_split.get("notes", ""))
            if note_row:
                rows.append(note_row)
        else:
            for split in splits:
                rows.append(
                    [
                        Paragraph("", st["cell_l"]),
                        Paragraph("", st["cell_l"]),
                        Paragraph(f"» {split.get('description') or ''}", st["split_indent"]),
                        Paragraph("", st["cell_l"]),
                        Paragraph("", st["cell_l"]),
                        Paragraph(split.get("category") or "—", st["cell_l"]),
                        Paragraph(split.get("budget") or "—", st["cell_l"]),
                        _amount_cells(split["amount"], split, bold=False),
                        Paragraph(f"#{split.get('id', '')}", st["small"]),
                    ]
                )
                note_row = _notes_row(split.get("notes", ""))
                if note_row:
                    rows.append(note_row)

    tbl = Table(rows, colWidths=CW, repeatRows=1)
    tbl.setStyle(
        TableStyle(
            [
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, RULE),
            ]
        )
    )
    story.append(tbl)

    # Totals by transaction type (R-INT-06)
    totals = data.get("totals_by_type", {})
    if totals:
        story.append(Spacer(1, 0.4 * cm))
        parts = [
            f"{t('common.total_income')}: {fmt_num(totals.get('deposit', Decimal(0)), show_sym=True, sym=sym)}",
            f"{t('common.total_expense')}: {fmt_num(totals.get('withdrawal', Decimal(0)), show_sym=True, sym=sym)}",
            f"{t('pdf.total_transfers')}: {fmt_num(totals.get('transfer', Decimal(0)), show_sym=True, sym=sym)}",
        ]
        story.append(Paragraph(" &nbsp;·&nbsp; ".join(parts), st["cell_l"]))

    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(t("pdf.register_legend"), st["small"]))

    doc.build(story)


def render_transaction_register_pdf(data: dict, path: str, legacy: bool = False) -> None:
    if legacy:
        return _render_legacy_transaction_register(data, path)
    return _render_modern_transaction_register(data, path)
