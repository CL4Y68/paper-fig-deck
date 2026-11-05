# -*- coding: utf-8 -*-
"""kit.py — SVG primitives for the 1280x720 figure-deck layout.

Typography contract: root font-family = Times New Roman + SimSun; every visible
text is >= 24 px (18 pt). Line wrapping reuses the ppt-master checker's own width
estimator (`estimate_single_line_text_frame_width`) so the final gate
(`svg_quality_checker --quick-generate --canonical-authoring`) cannot trip on
width overflow.

Importing this module does NOT require ppt-master: the estimator is resolved
lazily on first use. That keeps the pure layout logic importable — and testable
— on a bare Python install. When no backend is found, `est_w` falls back to an
approximate CJK/Latin model and `backend_status()` reports `approx`; a real
generation run must call `require_backend()` (or `set_strict(True)`) so it can
never silently ship a deck laid out with the wrong width model.
"""
from __future__ import annotations

import html
import os
import pathlib
import re
import sys
from typing import Iterable, NamedTuple

from layout import (  # noqa: F401  (re-exported: older generators import from kit)
    ABSTRACT_MAX_LINES,
    BLUE,
    BLUE2,
    BODY_LEAD,
    BODY_MAX,
    BODY_PX,
    BODY_TOP,
    BODY_ZONE_BOTTOM,
    BODY_ZONE_H,
    CANVAS_H,
    CANVAS_W,
    CONCLUSION_MAX_LINES,
    CONTENT_W,
    COVER_CARD,
    COVER_IMG,
    COVER_KEYWORDS_Y,
    COVER_META_Y,
    COVER_TITLE_Y,
    DARK,
    FAM,
    FIG_MAX_KB,
    FIG_MAX_W_PX,
    FIRST_LINE_INDENT,
    FOOTER_BOUNDS,
    GOLD,
    GRAY,
    HAIRLINE_Y,
    HEADER_BOUNDS,
    IMG_INNER,
    INTRO_MAX_LINES,
    KICKER_PX,
    LEAD_RATIO,
    LEFT_BOUNDS,
    LEFT_CARD,
    LGRAY,
    LIGHT,
    LINE,
    MARGIN_X,
    METHODS_MAX_LINES,
    MIN_PX,
    NOTE_PANEL_W,
    NOTE_PANEL_X0,
    OVERVIEW_COL_W_ONE,
    OVERVIEW_COL_W_TWO,
    OVERVIEW_COL_X,
    OVERVIEW_LEAD,
    OVERVIEW_TWO_COL_THRESHOLD,
    OVERVIEW_Y0,
    PANEL,
    PANEL_BOUNDS,
    PANEL_PAD,
    PANEL_W_INNER,
    PX0,
    QUOTE_LABEL_Y,
    QUOTE_PX,
    QUOTE_Y,
    TABLE_MAX_ROWS,
    TABLE_ROW_H,
    TABLE_W,
    TABLE_X0,
    TABLE_Y0,
    TEXT_LEAD,
    TEXT_TOP,
    TEXT_W,
    TEXT_X0,
    TITLE_PX,
    WHITE,
    body_lead,
    overview_columns,
)

BACKEND_ENV = "SKILL_SCRIPTS_DIR"
PROJECT_ENV = "PPTMASTER_DIR"

_ESTIMATOR_NAME = "estimate_single_line_text_frame_width"


class BackendUnavailable(RuntimeError):
    """Raised when the ppt-master width estimator is required but not found."""


class Backend(NamedTuple):
    state: str                      # "ppt-master" | "approx"
    scripts_dir: str | None
    detail: str


_estimator = None                   # resolved once
_backend = Backend("approx", None, "not resolved yet")
_strict = False


def _candidate_script_dirs() -> Iterable[pathlib.Path]:
    """Places a ppt-master scripts/ dir may live, most specific first."""
    env = os.environ.get(BACKEND_ENV)
    if env:
        yield pathlib.Path(env)
    proj = os.environ.get(PROJECT_ENV)
    if proj:
        yield pathlib.Path(proj) / "scripts"
    home = pathlib.Path.home()
    # Hermes skill installs: per-profile skills dirs under the platform data root.
    for base in (os.environ.get("LOCALAPPDATA"), os.environ.get("XDG_DATA_HOME")):
        if base and pathlib.Path(base).is_dir():
            yield from sorted(pathlib.Path(base).glob(
                "hermes/profiles/*/skills/productivity/ppt-master/scripts"))
    yield from sorted(home.glob(".hermes/profiles/*/skills/productivity/ppt-master/scripts"))
    for rel in ("ppt-master", "tools/ppt-master", "repos/ppt-master",
                "src/ppt-master", "Documents/ppt-master", "Desktop/ppt-master"):
        yield home / rel / "scripts"
    here = pathlib.Path(__file__).resolve().parent
    yield here.parent / "ppt-master" / "scripts"
    yield here.parent.parent / "ppt-master" / "scripts"
    yield pathlib.Path.cwd() / "ppt-master" / "scripts"


def _resolve_estimator():
    """Import the checker's width model, or return None with the reason recorded."""
    global _estimator, _backend
    if _estimator is not None:
        return _estimator
    if os.environ.get("PAPER_FIG_DECK_NO_BACKEND"):
        # Test/CI hook: behave exactly like a machine without ppt-master, even on
        # one that has it installed. Lets the approximate path be exercised.
        _backend = Backend("approx", None, "disabled by PAPER_FIG_DECK_NO_BACKEND")
        return None
    tried = []
    for cand in _candidate_script_dirs():
        if not (cand / "svg_quality_checker.py").exists():
            tried.append(str(cand))
            continue
        try:
            if str(cand) not in sys.path:
                sys.path.insert(0, str(cand))
            from svg_to_pptx.drawingml.elements import (  # type: ignore
                estimate_single_line_text_frame_width as fn,
            )
        except Exception as exc:                    # pragma: no cover - env specific
            tried.append(f"{cand} ({exc.__class__.__name__}: {exc})")
            continue
        _estimator = fn
        _backend = Backend("ppt-master", str(cand), "resolved")
        return fn
    _backend = Backend(
        "approx", None,
        "no ppt-master scripts/ dir found; set "
        f"{BACKEND_ENV} (a dir containing svg_quality_checker.py). Tried: "
        + ", ".join(tried[-3:] or ["(nothing)"]),
    )
    return None


def backend_status() -> Backend:
    """Report which width model `est_w` will use (resolves on first call)."""
    _resolve_estimator()
    return _backend


def set_strict(strict: bool) -> None:
    """When strict, `est_w` raises instead of falling back to the approximate model."""
    global _strict
    _strict = strict


def require_backend() -> Backend:
    """Fail loudly if the real estimator is missing (generation must be gated)."""
    _resolve_estimator()
    if _estimator is None:
        raise BackendUnavailable(_backend.detail)
    return _backend


# ------------------------------------------------------------------ measuring
_CJK_OR_FULLWIDTH = re.compile(r"[\u2e80-\u9fff\u3000-\u303f\uff00-\uffef]")


def approx_w(text: str, size: int) -> float:
    """Coarse CJK/Latin advance model used only when ppt-master is absent.

    Mirrors the checker's ballpark (CJK ~1.10 em, Latin ~0.62 em) so tests and
    dry runs behave sanely; it is NOT gate-accurate — never ship a deck laid out
    with this model.
    """
    total = 0.0
    for ch in text:
        total += 1.10 if _CJK_OR_FULLWIDTH.match(ch) else 0.62
    return total * size * 1.02


def est_w(text: str, size: int) -> float:
    """Single-line advance width in px, using the gate's own model when available."""
    fn = _resolve_estimator()
    if fn is not None:
        return fn([{"text": text, "font_size": size, "font_family": FAM}],
                  include_headroom=True)
    if _strict:
        raise BackendUnavailable(_backend.detail)
    return approx_w(text, size)


# ------------------------------------------------------------------ tokenizer
TOK = re.compile(
    r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]'
    r'|[A-Za-z0-9\.\,\;\:\%\(\)\[\]\-\/\u2013\u2014\u00b0\u2103'
    r'\u2081\u2082\u2083\u2215\u2261\u2264\u2265\u0394\u03b8\u00d7\u00f7'
    r'\u2192\u2248\u00b7\u2026\u2018\u2019\u201c\u201d]+'
    r'|[^\s]'
    r'|[ \t]+'
)

TRAILING_PUNCT = "\u3002\uff1b\uff1a\uff01\uff1f\u3001\uff0c\uff09\u3011\u300b\uff0c.;:!?)"


def esc(s: str) -> str:
    """XML-escape text for use inside <text>/<tspan>."""
    return html.escape(s, quote=True)


# --------------------------------------------------------------------- wrap
def wrap(text: str, size: int, maxw: float) -> list[str]:
    """Greedy wrap using the same width model as the gate.

    Never drops characters: ``"".join(wrap(t, s, w)).replace(" ", "")`` equals
    the input with whitespace collapsed.
    """
    lines: list[str] = []
    cur = ""
    for m in TOK.finditer(text):
        tok = m.group(0)
        if cur and not tok.isspace() and est_w(cur + tok, size) > maxw:
            lines.append(cur.rstrip())
            cur = ""
        cur += tok
    if cur.strip():
        lines.append(cur.rstrip())
    lines = [ln for ln in lines if ln]
    # A lone closing punctuation mark must not open a new (final) line: pull it
    # up onto the previous one and accept a one-character overhang.
    if len(lines) >= 2 and len(lines[-1]) == 1 and lines[-1] in TRAILING_PUNCT:
        lines[-2] += lines[-1]
        lines.pop()
    return lines


def truncate1(text: str, size: int, maxw: float) -> str:
    """Truncate to one line with an ellipsis (binary search on the char count)."""
    if est_w(text, size) <= maxw:
        return text
    lo, hi = 0, len(text)
    while lo < hi - 1:
        mid = (lo + hi + 1) // 2
        if est_w(text[:mid] + "\u2026", size) <= maxw:
            lo = mid
        else:
            hi = mid - 1
    return (text[:lo] + "\u2026").rstrip()


def _wrap_indented(text: str, size: int, maxw: float, indent_px: int) -> list[str]:
    """First line narrower by `indent_px`, continuation lines at full width."""
    first_budget = maxw - indent_px
    if est_w(text, size) <= first_budget:
        return [text]
    cur = ""
    for m in TOK.finditer(text):
        tok = m.group(0)
        if cur and not tok.isspace() and est_w(cur + tok, size) > first_budget:
            break
        cur += tok
    first = cur.rstrip()
    rest = text[len(cur.rstrip()):].lstrip()
    return [first] + (wrap(rest, size, maxw) if rest else [])


# -------------------------------------------------------------------- <text>
def _mtext_lines(x, y, lines, size, fill, weight, leading, anchor=None):
    leading = leading or int(round(size * LEAD_RATIO))
    weight_attr = f' font-weight="{weight}"' if weight else ""
    anchor_attr = f' text-anchor="{anchor}"' if anchor else ""
    # All lines emit at the SAME x: the exporter's reflow-merge needs uniform x
    # to fuse the paragraph into one editable wrap="square" text frame. The
    # first-line 2-char indent is applied in PPTX via a:pPr indent (postproc).
    out = (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}"'
           f'{weight_attr}{anchor_attr}>{esc(lines[0])}')
    for ln in lines[1:]:
        out += f'\n<tspan x="{x}" dy="{leading}">{esc(ln)}</tspan>'
    out += "</text>"
    return out, len(lines)


def mtext(x: int, y: int, text: str, size: int, fill: str, weight: str | None = None,
          leading: int | None = None, maxw: float | None = None,
          anchor: str | None = None) -> str:
    """Multi-line <text> element as a string."""
    lines = [text] if maxw is None else wrap(text, size, maxw)
    svg, _ = _mtext_lines(x, y, lines, size, fill, weight, leading, anchor)
    return svg


def mtext_lines(x, y, text, size, fill, weight=None, leading=None, maxw=None,
                anchor=None, indent_px=0):
    """Wrap then emit; returns ``(svg, n_lines)`` so callers can zone-check."""
    if maxw is None:
        lines = [text]
    elif indent_px:
        lines = _wrap_indented(text, size, maxw, indent_px)
    else:
        lines = wrap(text, size, maxw)
    svg, n = _mtext_lines(x, y, lines, size, fill, weight, leading, anchor)
    return svg, n


def wrap_capped(text: str, size: int, maxw: float,
                max_lines: int) -> tuple[list[str], int]:
    """Wrap to at most ``max_lines``; return ``(lines, dropped_chars)``.

    A quotation is content, not decoration: callers MUST surface
    ``dropped_chars`` (``content_schema`` already rejects over-long quotes at
    step 0, so a non-zero value here means the data slipped past validation).
    The last kept line gets an ellipsis so a rendered page can never pretend to
    be a complete sentence.
    """
    lines = wrap(text, size, maxw)
    if len(lines) <= max_lines:
        return lines, 0
    kept = lines[:max_lines]
    dropped = sum(len(ln) for ln in lines[max_lines:])
    last = kept[-1] + "\u2026"
    kept[-1] = last if est_w(last, size) <= maxw else truncate1(last, size, maxw)
    return kept, dropped


def count_lines(text: str, size: int, maxw: float, indent_px: int = 0) -> int:
    """How many lines `mtext_lines` would emit (same model, no XML built)."""
    if indent_px:
        return len(_wrap_indented(text, size, maxw, indent_px))
    return len(wrap(text, size, maxw))


# --------------------------------------------------------------------- pages
def page_head(role: str, first: bool = False) -> str:
    lang = ' lang="zh-CN"' if first else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{CANVAS_W}" height="{CANVAS_H}" viewBox="0 0 {CANVAS_W} {CANVAS_H}"'
            f'{lang} data-pptx-page-role="{role}" font-family="{FAM}">')


def page_tail() -> str:
    return "</svg>\n"


def bg() -> str:
    return (f'<rect id="bg" data-pptx-role="background" x="0" y="0" '
            f'width="{CANVAS_W}" height="{CANVAS_H}" fill="{WHITE}"/>')


FOOTER_TEXT = ""  # legacy module-level default; prefer the footer_text kwarg


def chrome(kicker: str, title: str, pageno: int, total: int,
           footer_text: str | None = None) -> str:
    """Header (kicker + title + rule line) and footer (label + page number)."""
    foot = FOOTER_TEXT if footer_text is None else footer_text
    header = (f'<g id="header" data-pptx-bounds="{HEADER_BOUNDS}">'
              f'<text x="{MARGIN_X}" y="56" font-size="{KICKER_PX}" fill="{GRAY}">{esc(kicker)}</text>'
              f'<text x="{MARGIN_X}" y="102" font-size="{TITLE_PX}" font-weight="bold" '
              f'fill="{BLUE}">{esc(title)}</text>'
              f'<rect x="{MARGIN_X}" y="122" width="120" height="4" fill="{GOLD}"/>'
              f"</g>")
    footer = (f'<g id="footer" data-pptx-bounds="{FOOTER_BOUNDS}">'
              f'<text x="{MARGIN_X}" y="700" font-size="{KICKER_PX}" fill="{LGRAY}">{esc(foot)}</text>'
              f'<text x="{CANVAS_W - MARGIN_X}" y="700" font-size="{KICKER_PX}" fill="{LGRAY}" '
              f'text-anchor="end">P{pageno:02d} / {total}</text>'
              f"</g>")
    return header + footer


def image_card(img_name: str) -> str:
    """White card + figure image (meet) referencing ``../images/<img_name>``."""
    x, y, w, h = IMG_INNER
    return (f'<g id="leftcard" data-pptx-bounds="{LEFT_BOUNDS}">'
            f'<rect x="{LEFT_CARD[0]}" y="{LEFT_CARD[1]}" width="{LEFT_CARD[2]}" '
            f'height="{LEFT_CARD[3]}" fill="{WHITE}" stroke="{LINE}" stroke-width="1.5"/>'
            f'<image x="{x}" y="{y}" width="{w}" height="{h}" '
            f'preserveAspectRatio="xMidYMid meet" href="../images/{img_name}"/>'
            f"</g>")


def label_line(y: int, label: str) -> str:
    return (f'<text x="{PX0}" y="{y}" font-size="{BODY_PX}" font-weight="bold" '
            f'fill="{GOLD}">{esc(label)}</text>')


def hairline(y: int, x0: int = PX0, w: int = PANEL_W_INNER) -> str:
    return f'<rect x="{x0}" y="{y}" width="{w}" height="1" fill="{LINE}"/>'
