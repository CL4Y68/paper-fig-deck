# -*- coding: utf-8 -*-
"""Shared kit for paper-fig-deck SVG generation (ppt-master quick-generate, flat pages).

Typography contract: root font-family = Times New Roman + SimSun; every visible
text >= 24px (18pt). Line wrapping uses the ppt-master checker's own width
estimator so the final gate (svg_quality_checker --quick-generate --canonical-authoring)
cannot trip on width overflow.
"""
import html
import os
import pathlib
import re
import sys


def _skill_scripts() -> str:
    """Locate the ppt-master scripts/ dir: $SKILL_SCRIPTS_DIR, else auto-discovery
    under <home>/AppData/Local/hermes/profiles/*/skills/productivity/ppt-master."""
    env = os.environ.get("SKILL_SCRIPTS_DIR")
    if env:
        return env
    cands = sorted(pathlib.Path.home().glob(
        r"AppData/Local/hermes/profiles/*/skills/productivity/ppt-master/scripts"))
    for c in cands:
        if (c / "svg_quality_checker.py").exists():
            return str(c)
    raise SystemExit(
        "ppt-master scripts/ dir not found; set SKILL_SCRIPTS_DIR to the dir "
        "containing svg_quality_checker.py")


SKILL_SCRIPTS = _skill_scripts()
sys.path.insert(0, SKILL_SCRIPTS)
from svg_to_pptx.drawingml.elements import estimate_single_line_text_frame_width as _est  # noqa: E402

FAM = "Times New Roman, SimSun, \u5b8b\u4f53, serif"

# colors
BLUE = "#1F3864"
BLUE2 = "#2E5395"
GOLD = "#C9A227"
DARK = "#333333"
GRAY = "#595959"
LGRAY = "#8A8F98"
LIGHT = "#F2F5FA"
LINE = "#D9DEE8"

# layout constants
CANVAS_W, CANVAS_H = 1280, 720
LEFT_CARD = (48, 144, 568, 496)      # x,y,w,h
IMG_INNER = (64, 160, 536, 464)      # image meet box
PANEL = (640, 144, 608, 496)
PX0 = PANEL[0] + 28                  # 668
PANEL_W_INNER = PANEL[2] - 56        # 552
HEADER_BOUNDS = "48 24 1184 110"
LEFT_BOUNDS = "48 144 568 496"
PANEL_BOUNDS = "640 144 608 496"
FOOTER_BOUNDS = "48 676 1184 32"

TOK = re.compile(
    r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]'
    r'|[A-Za-z0-9\.\,\;\:\%\(\)\[\]\-\/\u2013\u2014\u00b0\u2103\u2081\u2082\u2083\u2215\u2261\u2264\u2265\u0394\u03b8\u00d7\u00f7\u2192\u2248\u00b7\u2026\u2018\u2019\u201c\u201d]+'
    r'|[^\s]'
    r'|[ \t]+'
)


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def est_w(text: str, size: int) -> float:
    return _est([{"text": text, "font_size": size, "font_family": FAM}], include_headroom=True)


def wrap(text: str, size: int, maxw: float):
    """Greedy wrap using the checker's own width estimator."""
    lines, cur = [], ""
    for m in TOK.finditer(text):
        tok = m.group(0)
        if cur and not tok.isspace() and est_w(cur + tok, size) > maxw:
            lines.append(cur.rstrip())
            cur = ""
        cur += tok
    if cur.strip():
        lines.append(cur.rstrip())
    lines = [l for l in lines if l]
    # never leave a lone closing punctuation as its own (final) line:
    # pull it up onto the previous line (one-char overhang accepted)
    if len(lines) >= 2 and len(lines[-1]) == 1 and lines[-1] in "。；：！？、，）】》，.;:!?)":
        lines[-2] += lines[-1]
        lines.pop()
    return lines


def mtext(x: int, y: int, text: str, size: int, fill: str, weight: str = None,
          leading: int = None, maxw: float = None, anchor: str = None) -> str:
    """Multi-line <text>: first line direct, continuations as <tspan x dy>.

    Returns (svg, n_lines) via mtext_lines; mtext is the single-line fast path.
    """
    if maxw is None:
        lines = [text]
    else:
        lines = wrap(text, size, maxw)
    svg, _ = _mtext_lines(x, y, lines, size, fill, weight, leading, anchor)
    return svg


def _mtext_lines(x, y, lines, size, fill, weight, leading, anchor=None, indent_px=0):
    leading = leading or int(round(size * 1.55))
    weight_attr = f' font-weight="{weight}"' if weight else ""
    anchor_attr = f' text-anchor="{anchor}"' if anchor else ""
    # All lines emit at the SAME x: the exporter's reflow-merge needs uniform x
    # to fuse the paragraph into one editable wrap="square" text frame. The
    # first-line 2-char indent is applied in PPTX via a:pPr indent (postproc).
    x1 = x
    out = (f'<text x="{x1}" y="{y}" font-size="{size}" fill="{fill}"{weight_attr}{anchor_attr}>'
           f'{esc(lines[0])}')
    for ln in lines[1:]:
        out += f'\n<tspan x="{x}" dy="{leading}">{esc(ln)}</tspan>'
    out += "</text>"
    return out, len(lines)


def mtext_lines(x, y, text, size, fill, weight=None, leading=None, maxw=None, anchor=None, indent_px=0):
    """Wrap then emit; returns (svg, n_lines) so callers can zone-check.

    indent_px: first-line indent (first line starts at x+indent_px and wraps at
    maxw-indent_px); continuation lines start at x with full maxw.
    """
    if maxw is None:
        lines = [text]
    elif indent_px:
        first_budget = maxw - indent_px
        if est_w(text, size) <= first_budget:
            lines = [text]
        else:
            # first line: token-level greedy at first_budget; rest: normal wrap
            first_parts, cur = [], ""
            for m in TOK.finditer(text):
                tok = m.group(0)
                if cur and not tok.isspace() and est_w(cur + tok, size) > first_budget:
                    break
                cur += tok
            first_parts.append(cur.rstrip())
            rest = text[len(cur.rstrip()):].lstrip()
            lines = first_parts + (wrap(rest, size, maxw) if rest else [])
    else:
        lines = wrap(text, size, maxw)
    svg, n = _mtext_lines(x, y, lines, size, fill, weight, leading, anchor, indent_px)
    return svg, n


def page_head(role: str, first: bool = False) -> str:
    lang = ' lang="zh-CN"' if first else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{CANVAS_W}" height="{CANVAS_H}" viewBox="0 0 {CANVAS_W} {CANVAS_H}"{lang} '
            f'data-pptx-page-role="{role}" font-family="{FAM}">')


def page_tail() -> str:
    return "</svg>\n"


def bg() -> str:
    return f'<rect id="bg" data-pptx-role="background" x="0" y="0" width="{CANVAS_W}" height="{CANVAS_H}" fill="#FFFFFF"/>'


def chrome(kicker: str, title: str, pageno: int, total: int) -> str:
    header = (f'<g id="header" data-pptx-bounds="{HEADER_BOUNDS}">'
              f'<text x="48" y="56" font-size="24" fill="{GRAY}">{esc(kicker)}</text>'
              f'<text x="48" y="102" font-size="32" font-weight="bold" fill="{BLUE}">{esc(title)}</text>'
              f'<rect x="48" y="122" width="120" height="4" fill="{GOLD}"/>'
              f"</g>")
    footer = (f'<g id="footer" data-pptx-bounds="{FOOTER_BOUNDS}">'
              f'<text x="48" y="700" font-size="24" fill="{LGRAY}">{esc(kicker)}</text>'
              f'<text x="1232" y="700" font-size="24" fill="{LGRAY}" text-anchor="end">P{pageno:02d} / {total}</text>'
              f"</g>")
    return header + footer


def image_card(img_name: str) -> str:
    x, y, w, h = IMG_INNER
    card = (f'<g id="leftcard" data-pptx-bounds="{LEFT_BOUNDS}">'
            f'<rect x="{LEFT_CARD[0]}" y="{LEFT_CARD[1]}" width="{LEFT_CARD[2]}" height="{LEFT_CARD[3]}" '
            f'fill="#FFFFFF" stroke="{LINE}" stroke-width="1.5"/>'
            f'<image x="{x}" y="{y}" width="{w}" height="{h}" '
            f'preserveAspectRatio="xMidYMid meet" href="../images/{img_name}"/>'
            f"</g>")
    return card


def label_line(y: int, label: str) -> str:
    return f'<text x="{PX0}" y="{y}" font-size="24" font-weight="bold" fill="{GOLD}">{esc(label)}</text>'


def hairline(y: int, x0: int = PX0, w: int = PANEL_W_INNER) -> str:
    return f'<rect x="{x0}" y="{y}" width="{w}" height="1" fill="{LINE}"/>'
