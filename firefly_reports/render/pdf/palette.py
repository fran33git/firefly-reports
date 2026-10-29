"""Strict monochrome palette of the PDF reports."""

from reportlab.lib import colors

BLACK = colors.HexColor("#000000")
DARK = colors.HexColor("#1A1A1A")
MID = colors.HexColor("#4A4A4A")
LIGHT = colors.HexColor("#888888")
RULE = colors.HexColor("#CCCCCC")  # thin rule line
TOTAL_BG = colors.HexColor("#F2F2F2")  # total row background (very light grey)

# Semantic chart colours (kept in sync with render.charts)
C_INCOME = "#2E7D5B"
C_EXPENSE = "#B3564B"
C_INK = "#1A1A1A"
