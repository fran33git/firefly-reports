"""Accounting-style table builders of the PDF reports."""

from reportlab.platypus import (
    Table,
    TableStyle,
)

from firefly_reports.render.pdf.palette import (
    DARK,
    RULE,
    TOTAL_BG,
)


def rule_line(col_widths: list) -> Table:
    """Full-width thin separator line."""
    tbl = Table([[""] * len(col_widths)], colWidths=col_widths)
    tbl.setStyle(
        TableStyle(
            [
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LINEABOVE", (0, 0), (-1, -1), 0.5, RULE),
            ]
        )
    )
    return tbl


def accounting_table(
    rows: list, col_widths: list, total_rows: list | None = None, grand_rows: list | None = None
) -> Table:
    """
    Build a Table with accounting style:
    - no visible grid
    - thin rule above subtotals
    - very light grey background + bold on totals
    - double rule below grand total
    """
    tbl = Table(rows, colWidths=col_widths)
    total_rows = total_rows or []
    grand_rows = grand_rows or []

    cmds = [
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        # No grid by default
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, RULE),  # thin rule below column headers
    ]

    for r in total_rows:
        cmds += [
            ("LINEABOVE", (0, r), (-1, r), 0.5, RULE),
            ("BACKGROUND", (0, r), (-1, r), TOTAL_BG),
            ("FONTNAME", (0, r), (-1, r), "Helvetica-Bold"),
        ]

    for r in grand_rows:
        cmds += [
            ("LINEABOVE", (0, r), (-1, r), 1.0, DARK),
            ("LINEBELOW", (0, r), (-1, r), 0.5, DARK),
            ("BACKGROUND", (0, r), (-1, r), TOTAL_BG),
            ("FONTNAME", (0, r), (-1, r), "Helvetica-Bold"),
            ("FONTSIZE", (0, r), (-1, r), 9.5),
        ]

    tbl.setStyle(TableStyle(cmds))
    return tbl
