# -*- coding: utf-8 -*-
"""layout.py — the single source of truth for the 1280x720 layout contract.

Everything that decides *where* things land on a page lives here, so the deck
generator, the post-processor and the tests agree on one set of numbers.
`kit.py` re-exports these names for backwards compatibility with older
generators (`from kit import PX0`).

Units: SVG px on a 1280x720 canvas. The exporter maps 1 px -> 9525 EMU
(12192000 / 1280), i.e. 1280 px == 13.333 in == 16:9 at 96 dpi.

Typography floor: every visible text is >= 24 px (18 pt). Do not introduce a
smaller size to make a line fit — shorten the text or split the page.
"""
from __future__ import annotations

# ---------------------------------------------------------------- typography
FAM = "Times New Roman, SimSun, \u5b8b\u4f53, serif"
MIN_PX = 24            # 18 pt floor for every visible glyph
TITLE_PX = 32
KICKER_PX = 24
BODY_PX = 24
QUOTE_PX = 24
LEAD_RATIO = 1.55      # default line advance as a multiple of font size

# ------------------------------------------------------------------- canvas
CANVAS_W, CANVAS_H = 1280, 720
MARGIN_X = 48
CONTENT_W = CANVAS_W - 2 * MARGIN_X          # 1184

# ------------------------------------------------------------------ modules
# Each group carries a data-pptx-bounds attribute; the gate checks that sibling
# modules do not overlap.
HEADER_BOUNDS = "48 24 1184 110"
LEFT_BOUNDS = "48 144 568 496"
PANEL_BOUNDS = "640 144 608 496"
FOOTER_BOUNDS = "48 676 1184 32"

LEFT_CARD = (48, 144, 568, 496)              # x, y, w, h  (white card)
IMG_INNER = (64, 160, 536, 464)              # image "meet" box inside the card
PANEL = (640, 144, 608, 496)                 # right-hand text panel
PANEL_PAD = 28
PX0 = PANEL[0] + PANEL_PAD                   # 668 — panel text origin
PANEL_W_INNER = PANEL[2] - 2 * PANEL_PAD     # 552 — wrap width
FIRST_LINE_INDENT = 48                       # 2 CJK chars at 24 px

# Table page: the table takes the left two-thirds, the note panel the rest.
TABLE_X0, TABLE_Y0 = 48, 160
TABLE_W = 730
TABLE_ROW_H = 48
TABLE_MAX_ROWS = 8                           # header + 7 body rows
NOTE_PANEL_X0 = 828
NOTE_PANEL_W = 376

# Full-width text pages (abstract / methods / conclusion / introduction)
TEXT_X0 = 48
TEXT_W = CONTENT_W
TEXT_TOP = 156
TEXT_LEAD = 36
INTRO_MAX_LINES = 16
ABSTRACT_MAX_LINES = 10
CONCLUSION_MAX_LINES = 10
METHODS_MAX_LINES = 12

# Figure/table body column: y212 .. y548 is the measured safe zone.
BODY_TOP = 212
BODY_ZONE_BOTTOM = 548
BODY_ZONE_H = BODY_ZONE_BOTTOM - BODY_TOP   # 336
# MEASURED (measure_capacity.py, PowerPoint COM render + pixel scan): with
# 18 pt TNR+SimSun, a 48 px first-line indent and the 552 px box, 14 lines put
# the ink bottom at ~552 px — clear of the y556 hairline; 15 lines overflow to
# ~584 px. Never pick this cap by intuition: re-run measure_capacity.py after
# changing font, box width or leading.
BODY_MAX = 14
BODY_LEAD = 36
HAIRLINE_Y = 556
QUOTE_LABEL_Y = 584
QUOTE_Y = 616

# Overview page (one row per figure/table claim)
OVERVIEW_Y0 = 170
OVERVIEW_LEAD = 44
OVERVIEW_TWO_COL_THRESHOLD = 9               # > 9 rows -> two columns
OVERVIEW_COL_W_ONE = CONTENT_W               # 1184
OVERVIEW_COL_W_TWO = 560
OVERVIEW_COL_X = (48, 636)
OVERVIEW_REF_COL = 132                       # fixed label column -> claims align

# Cover page
COVER_CARD = (48, 96, 1184, 395)
COVER_IMG = (64, 112, 1152, 363)
COVER_TITLE_Y = 530
COVER_KEYWORDS_Y = 568
COVER_META_Y = 640

# ------------------------------------------------------------------- colors
BLUE = "#1F3864"
BLUE2 = "#2E5395"
GOLD = "#C9A227"
DARK = "#333333"
GRAY = "#595959"
LGRAY = "#8A8F98"
LIGHT = "#F2F5FA"
LINE = "#D9DEE8"
WHITE = "#FFFFFF"

# ------------------------------------------------------------------- assets
FIG_MAX_W_PX = 2000       # crop render cap
FIG_MAX_KB = 900          # per-image advisory limit enforced by the gate


def body_lead(n_lines: int) -> int:
    """Leading that keeps `n_lines` body lines inside the BODY zone."""
    return min(BODY_LEAD, BODY_ZONE_H // max(n_lines, 1))


def overview_columns(n_specs: int):
    """(column_width, [x origins]) for the mainline overview page."""
    if n_specs > OVERVIEW_TWO_COL_THRESHOLD:
        return OVERVIEW_COL_W_TWO, list(OVERVIEW_COL_X)
    return OVERVIEW_COL_W_ONE, [OVERVIEW_COL_X[0]]


__all__ = [name for name in dir() if not name.startswith("_")]
