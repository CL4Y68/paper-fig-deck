# -*- coding: utf-8 -*-
"""Tests for the layout contract: geometry must not overlap, type stays >= 18pt."""
import layout


def _rect(bounds: str):
    x, y, w, h = (int(v) for v in bounds.split())
    return x, y, w, h


def _overlaps(a, b) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def test_canvas_is_16_9():
    assert layout.CANVAS_W / layout.CANVAS_H == 16 / 9
    assert layout.CANVAS_W * 9525 == 12192000   # exact PPTX slide width in EMU


def test_page_modules_do_not_overlap():
    modules = {
        "header": _rect(layout.HEADER_BOUNDS),
        "left": _rect(layout.LEFT_BOUNDS),
        "panel": _rect(layout.PANEL_BOUNDS),
        "footer": _rect(layout.FOOTER_BOUNDS),
    }
    names = list(modules)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            assert not _overlaps(modules[a], modules[b]), f"{a} overlaps {b}"


def test_every_module_is_inside_the_canvas():
    for name in ("HEADER_BOUNDS", "LEFT_BOUNDS", "PANEL_BOUNDS", "FOOTER_BOUNDS"):
        x, y, w, h = _rect(getattr(layout, name))
        assert x >= 0 and y >= 0
        assert x + w <= layout.CANVAS_W and y + h <= layout.CANVAS_H


def test_image_box_sits_inside_its_card():
    cx, cy, cw, ch = layout.LEFT_CARD
    ix, iy, iw, ih = layout.IMG_INNER
    assert cx <= ix and cy <= iy
    assert ix + iw <= cx + cw and iy + ih <= cy + ch
    assert (ix - cx) == (cx + cw) - (ix + iw)     # horizontally centred
    assert (iy - cy) == (cy + ch) - (iy + ih)     # vertically centred


def test_panel_text_stays_inside_the_panel():
    px, py, pw, ph = layout.PANEL
    assert px < layout.PX0 < px + pw
    assert layout.PX0 + layout.PANEL_W_INNER <= px + pw
    assert layout.PANEL_W_INNER + 2 * layout.PANEL_PAD == pw


def test_quote_band_fits_below_the_body_zone():
    assert layout.BODY_TOP < layout.BODY_ZONE_BOTTOM < layout.HAIRLINE_Y
    assert layout.HAIRLINE_Y < layout.QUOTE_LABEL_Y < layout.QUOTE_Y
    assert layout.QUOTE_Y < layout.PANEL[1] + layout.PANEL[3]


def test_no_font_size_below_the_18pt_floor():
    sizes = [layout.MIN_PX, layout.KICKER_PX, layout.BODY_PX,
             layout.QUOTE_PX, layout.TITLE_PX]
    assert min(sizes) >= 24
    assert layout.MIN_PX == 24


def test_body_lead_never_exceeds_the_zone():
    for n in range(1, layout.BODY_MAX + 1):
        lead = layout.body_lead(n)
        assert lead >= 12
        assert lead * n <= layout.BODY_ZONE_H
    assert layout.body_lead(1) == layout.BODY_LEAD


def test_overview_switches_to_two_columns_above_threshold():
    w1, cols1 = layout.overview_columns(layout.OVERVIEW_TWO_COL_THRESHOLD)
    w2, cols2 = layout.overview_columns(layout.OVERVIEW_TWO_COL_THRESHOLD + 1)
    assert (w1, len(cols1)) == (layout.OVERVIEW_COL_W_ONE, 1)
    assert (w2, len(cols2)) == (layout.OVERVIEW_COL_W_TWO, 2)
    assert cols2[1] + w2 <= layout.CANVAS_W
