# -*- coding: utf-8 -*-
"""deck.py — content.json -> page roster -> SVG pages.

This module replaces the module-level mutable globals (`PAPER_`, `KICK`,
`kit.FOOTER_TEXT`) that the older generator relied on. Everything a page builder
needs now arrives through a `Deck` instance, which means:

  * two decks can be built in one process (tests, batch runs) without leaking
    state into each other;
  * `build_slides()` is a pure function of content.json, so the roster used by
    the SVG generator and the speaker-note writer can never drift;
  * the layout numbers all come from `layout.py`, so a font/box change is one
    edit instead of a grep.

Page roster (content-driven):
  P01 cover -> P02 abstract -> [intro] -> [overview] -> [methods]
  -> figures/tables in content.json order (long bodies auto-split into （续）)
  -> conclusion.
"""
from __future__ import annotations

import json
import pathlib
import re
from typing import Any, Callable

import kit
import layout

# One entry of the page roster. A plain dict keeps the schema obvious in
# content.json terms; the keys are documented here once.
#   type           "fig" | "table"
#   kind           "figure" | "scheme"        (fig only)
#   num, img       figure number and image file name (fig only)
#   reading_point  panel title
#   what           one-line reading instruction (notes)
#   body           body chunk for this page (fig only)
#   quote, quote_ref
#   cont           continuation page of a split body
#   claim          this spec's line in paper.mainline (None when unmatched)
#   critique, arguing   optional author's-argument notes
#   ml_index, ml_total  position in the claim-evidence chain
#   pageno         1-based slide number
#   data           raw content.json entry (table only)
SlideSpec = dict[str, Any]


# ------------------------------------------------------------------ splitting
def body_lines(text: str) -> int:
    """Rendered line count exactly as `kit.mtext_lines` would produce it."""
    return kit.count_lines(text, layout.BODY_PX, layout.PANEL_W_INNER,
                           indent_px=layout.FIRST_LINE_INDENT)


def split_body(body_text: str, max_lines: int | None = None) -> list[str]:
    """Split a body paragraph into chunks that each render to <= max_lines.

    Preference order: sentence boundaries (。；) first, clause boundaries (，、)
    only when a single sentence is itself too long. A chunk that still overflows
    is an authoring bug, not something to silently shrink — assert.
    """
    cap = max_lines or layout.BODY_MAX
    if body_lines(body_text) <= cap:
        return [body_text]

    chunks, cur = [], ""
    for part in re.split(r"(?<=[。；])", body_text):
        if cur and body_lines(cur + part) > cap:
            chunks.append(cur)
            cur = part
        else:
            cur += part
    if cur:
        chunks.append(cur)

    fixed: list[str] = []
    for chunk in chunks:
        if body_lines(chunk) <= cap:
            fixed.append(chunk)
            continue
        cur2 = ""
        for piece in re.split(r"(?<=[，、])", chunk):
            if cur2 and body_lines(cur2 + piece) > cap:
                fixed.append(cur2)
                cur2 = piece
            else:
                cur2 += piece
        if cur2:
            fixed.append(cur2)

    for chunk in fixed:
        n = body_lines(chunk)
        assert n <= cap, f"body chunk still overflows ({n} > {cap}): {chunk[:40]}…"
    return fixed


def build_slides(content: dict, max_lines: int | None = None) -> tuple[list[SlideSpec], int]:
    """(figure/table slide specs, number of lead pages before them)."""
    paper = content["paper"]
    mainline = paper.get("mainline") or []
    ml_total = len(mainline) or len(content["figures"])
    slides: list[SlideSpec] = []

    for fi, fig in enumerate(content["figures"]):
        claim = mainline[fi][1] if fi < len(mainline) else None
        common = {"claim": claim, "critique": fig.get("critique"),
                  "arguing": fig.get("arguing"), "ml_index": fi + 1,
                  "ml_total": ml_total, "pageno": 0}
        if fig.get("kind") == "table":
            slides.append({"type": "table", "data": fig, **common})
            continue
        for si, slide in enumerate(fig["slides"]):
            for ci, chunk in enumerate(split_body(slide["body"], max_lines)):
                slides.append({
                    "type": "fig",
                    "kind": fig.get("kind", "figure"),
                    "num": fig["num"],
                    "img": fig.get("img", f"fig{fig['num']:02d}.jpg"),
                    "reading_point": slide["reading_point"],
                    "what": slide["what"],
                    "body": chunk,
                    "quote": slide["quote"],
                    "quote_ref": slide["quote_ref"],
                    "cont": (si > 0) or (ci > 0),
                    **common,
                })

    n_lead = (2
              + (1 if paper.get("intro_lines") else 0)
              + (1 if paper.get("mainline") else 0)
              + (1 if paper.get("methods_zh") else 0))
    for i, spec in enumerate(slides):
        spec["pageno"] = n_lead + 1 + i
    return slides, n_lead


def slug_for(spec: SlideSpec, pageno: int) -> str:
    """Stable file name (and notes H1) for one content page."""
    if spec["type"] == "table":
        return f"{pageno:02d}_tab"
    suffix = "_cont" if spec.get("cont") else ""
    prefix = "sch" if spec.get("kind") == "scheme" else "fig"
    return f"{pageno:02d}_{prefix}{spec['num']:02d}{suffix}"


# ---------------------------------------------------------------------- deck
class Deck:
    """One paper's deck: page roster plus the SVG page builders."""

    def __init__(self, content: dict, *, allow_approx: bool = False):
        self.content = content
        self.paper = content["paper"]
        self.kick = self.paper.get("kicker") or "文献精读"
        self.footer = self.paper.get("footer", self.kick)
        self.allow_approx = allow_approx
        kit.set_strict(not allow_approx)
        self.slides, self.n_lead = build_slides(content)
        self.total = self.n_lead + len(self.slides) + 1
        # Rendered-text losses: [{"page", "field", "dropped"}]. A non-empty list
        # means a page shows less than content.json says — gen_all prints it and
        # run_pipeline surfaces it in the build log. Never let this be silent.
        self.truncated: list[dict] = []

    # -- truncation bookkeeping -------------------------------------------
    def _note_truncation(self, page: str, field: str, dropped: int) -> None:
        if dropped > 0:
            self.truncated.append({"page": page, "field": field, "dropped": dropped})

    def _title(self, text: str, width: float, page: str) -> str:
        """One-line heading: truncate, but record what got shaved off."""
        out = kit.truncate1(text, layout.BODY_PX, width)
        if out != text:
            self._note_truncation(page, "reading_point", len(text) - len(out.rstrip("\u2026")))
        return out

    def _quote_block(self, x: int, label_y: int, first_y: int, quote: str,
                     quote_ref: str, width: float, page: str) -> str:
        """Source quotation, wrapped to QUOTE_MAX_LINES lines (never one-line clipped).

        Step 0 rejects quotes that need more lines, so `dropped` should be 0 on
        a validated deck; the record is the defence-in-depth for bypasses
        (--skip-validate, hand-edited JSON).
        """
        lines, dropped = kit.wrap_capped(quote, layout.BODY_PX, width,
                                         layout.QUOTE_MAX_LINES)
        self._note_truncation(page, "quote", dropped)
        body = [f'<text x="{x}" y="{label_y}" font-size="{layout.BODY_PX}" '
                f'font-weight="bold" fill="{layout.GRAY}">原文（{kit.esc(quote_ref)}）</text>',
                f'<text x="{x}" y="{first_y}" font-size="{layout.BODY_PX}" '
                f'fill="{layout.LGRAY}">{kit.esc(lines[0])}']
        for line in lines[1:]:
            body.append(f'<tspan x="{x}" dy="{layout.QUOTE_LEAD}">{kit.esc(line)}</tspan>')
        body.append("</text>")
        return "".join(body)

    def stats(self) -> dict:
        """Build statistics for the driver's log line."""
        return {"pages": self.total, "truncated": len(self.truncated),
                "losses": list(self.truncated)}

    # -- shared chrome -----------------------------------------------------
    def _chrome(self, title: str, pageno: int) -> str:
        return kit.chrome(self.kick, title, pageno, self.total, footer_text=self.footer)

    def _footer_only(self, pageno: int) -> str:
        return (f'<g id="footer" data-pptx-bounds="{layout.FOOTER_BOUNDS}">'
                f'<text x="{layout.CANVAS_W - layout.MARGIN_X}" y="700" '
                f'font-size="{layout.KICKER_PX}" fill="{layout.LGRAY}" text-anchor="end">'
                f"P{pageno:02d} / {self.total}</text></g>")

    def _text_page(self, title: str, key: str, pageno: int, *, role: str = "content",
                   top: int = 200, max_lines: int = 10, src_key: str | None = None,
                   gid: str = "textg") -> str:
        """Full-width single-block page (abstract / methods / conclusion)."""
        body = self.paper[key]
        n = kit.count_lines(body, layout.BODY_PX, layout.TEXT_W,
                            indent_px=layout.FIRST_LINE_INDENT)
        assert n <= max_lines, f"{key} too long: {n} lines > {max_lines}"
        svg, _ = kit.mtext_lines(layout.TEXT_X0, top, body, layout.BODY_PX, layout.DARK,
                                 leading=layout.TEXT_LEAD, maxw=layout.TEXT_W,
                                 indent_px=layout.FIRST_LINE_INDENT)
        src = self.paper.get(src_key) if src_key else None
        out = [kit.page_head(role), kit.bg(), self._chrome(title, pageno),
               f'<g id="{gid}" data-pptx-bounds="48 144 1184 512">', svg]
        if src:
            out.append(f'<text x="{layout.TEXT_X0}" y="612" '
                       f'font-size="{layout.BODY_PX}" fill="{layout.LGRAY}">{kit.esc(src)}</text>')
        out.append("</g>")
        out.append(kit.page_tail())
        return "".join(out)

    # -- pages -------------------------------------------------------------
    def cover(self) -> str:
        p = self.paper
        c = ['<g id="covermain" data-pptx-bounds="48 80 1184 580">',
             f'<rect x="{layout.COVER_CARD[0]}" y="{layout.COVER_CARD[1]}" '
             f'width="{layout.COVER_CARD[2]}" height="{layout.COVER_CARD[3]}" '
             f'fill="{layout.WHITE}" stroke="{layout.LINE}" stroke-width="1.5"/>',
             f'<image x="{layout.COVER_IMG[0]}" y="{layout.COVER_IMG[1]}" '
             f'width="{layout.COVER_IMG[2]}" height="{layout.COVER_IMG[3]}" '
             f'preserveAspectRatio="xMidYMid meet" '
             f'href="../images/{p["title_page_img"]}"/>',
             f'<text x="{layout.COVER_CARD[0]}" y="{layout.COVER_TITLE_Y}" '
             f'font-size="{layout.TITLE_PX}" font-weight="bold" fill="{layout.BLUE}">'
             f'{kit.esc(p["title_zh"])}</text>']
        if p.get("keywords_en"):
            c.append(kit.mtext(layout.COVER_CARD[0], layout.COVER_KEYWORDS_Y,
                               "Keywords: " + p["keywords_en"], layout.BODY_PX,
                               layout.GRAY, leading=layout.TEXT_LEAD,
                               maxw=layout.COVER_CARD[2] - 96))
        c.append(f'<text x="{layout.COVER_CARD[0]}" y="{layout.COVER_META_Y}" '
                 f'font-size="{layout.BODY_PX}" fill="{layout.GRAY}">DOI: '
                 f'{kit.esc(p["doi"])} · {kit.esc(p["journal"])} · '
                 f'{kit.esc(p["authors_short"])}</text></g>')
        return "".join([kit.page_head("cover", first=True), kit.bg(), "".join(c),
                        self._footer_only(1), kit.page_tail()])

    def abstract(self) -> str:
        return self._text_page("摘要（中文）", "abstract_zh", 2,
                               top=200, max_lines=layout.ABSTRACT_MAX_LINES,
                               src_key="abstract_src", gid="absgroup")

    def conclusion(self) -> str:
        return self._text_page("结论（中文）", "conclusion_zh", self.total,
                               role="ending", top=200,
                               max_lines=layout.CONCLUSION_MAX_LINES,
                               src_key="conclusion_src", gid="cong")

    def methods(self, pageno: int) -> str:
        page = self._text_page("制备方法（Materials and Methods）", "methods_zh",
                               pageno, top=layout.TEXT_TOP,
                               max_lines=layout.METHODS_MAX_LINES,
                               src_key="methods_src", gid="methodsg")
        return page

    def intro(self, pageno: int) -> str:
        """Single-page Introduction analysis: every gold label starts a new line,
        the body then flows on the label's line, wrapping at the full width."""
        out = [kit.page_head("content"), kit.bg(), self._chrome("Introduction 分析", pageno)]
        x, y0, maxw = layout.TEXT_X0, layout.TEXT_TOP, layout.TEXT_W
        lead, ind = layout.TEXT_LEAD, layout.FIRST_LINE_INDENT

        tokens: list[tuple[str, str]] = []
        for label, text in self.paper["intro_lines"]:
            tokens.append(("L", label + " "))
            for m in kit.TOK.finditer(text):
                tokens.append(("T", m.group(0)))

        lines: list[list[tuple[str, str]]] = []
        cur: list[tuple[str, str]] = []
        cur_w = 0.0
        budget0, budget = maxw - ind, maxw
        for kind, tok in tokens:
            w = kit.est_w(tok, layout.BODY_PX)
            if kind == "L":
                if cur:
                    lines.append(cur)
                    cur, cur_w = [], 0.0
                cur.append((kind, tok))
                cur_w += w
                continue
            limit = budget0 if not lines else budget
            if cur and cur_w + w > limit:
                lines.append(cur)
                cur, cur_w = [(kind, tok)], w
            else:
                cur.append((kind, tok))
                cur_w += w
        if cur:
            lines.append(cur)
        assert len(lines) <= layout.INTRO_MAX_LINES, (
            f"intro needs {len(lines)} lines > {layout.INTRO_MAX_LINES}: condense intro_lines")

        def runs_svg(runs):
            parts, i = [], 0
            while i < len(runs):
                kind, _ = runs[i]
                j = i
                while j + 1 < len(runs) and runs[j + 1][0] == kind:
                    j += 1
                text = "".join(t for _, t in runs[i:j + 1])
                if kind == "L":
                    parts.append(f'<tspan fill="{layout.GOLD}" font-weight="bold">'
                                 f"{kit.esc(text)}</tspan>")
                else:
                    parts.append(f'<tspan fill="{layout.DARK}">{kit.esc(text)}</tspan>')
                i = j + 1
            return "".join(parts)

        body = runs_svg(lines[0])
        for line in lines[1:]:
            body += f'\n<tspan x="{x}" dy="{lead}">{runs_svg(line)}</tspan>'
        out.append(f'<g id="introg" data-pptx-bounds="48 144 1184 512">'
                   f'<text x="{x}" y="{y0}" font-size="{layout.BODY_PX}">{body}</text></g>')
        out.append(kit.page_tail())
        return "".join(out)

    def overview(self, pageno: int) -> str:
        """One row per figure/table spec: gold ref label + the claim it supports."""
        specs = self.paper.get("mainline") or []
        col_w, x_origins = layout.overview_columns(len(specs))
        two_col = len(x_origins) > 1
        out = [kit.page_head("content"), kit.bg(),
               self._chrome("论证主线：每张图证明什么", pageno)]
        half = (len(specs) + 1) // 2
        columns = ([specs[:half], specs[half:]] if two_col else [specs])
        for ci, column in enumerate(columns):
            x = x_origins[ci]
            for ri, (ref, claim) in enumerate(column):
                y = layout.OVERVIEW_Y0 + ri * layout.OVERVIEW_LEAD
                # Fixed label column: every claim starts at the same x, so the
                # rows read as a list instead of a ragged indent. A label wider
                # than the column pushes its own claim right (never overlaps).
                ref_w = kit.est_w(ref + "\u3000", layout.BODY_PX)
                claim_x = x + max(layout.OVERVIEW_REF_COL, int(ref_w) + 8)
                claim_text = kit.truncate1(claim, layout.BODY_PX, x + col_w - claim_x)
                if claim_text != claim:
                    self._note_truncation(f"{pageno:02d}_overview", "mainline claim",
                                          len(claim) - len(claim_text.rstrip("\u2026")))
                out.append(
                    f'<g id="ovrow{ci}_{ri:02d}" '
                    f'data-pptx-bounds="{x} {y - 30} {col_w} 40">'
                    f'<text x="{x}" y="{y}" font-size="{layout.BODY_PX}" fill="{layout.DARK}">'
                    f'<tspan x="{x}" fill="{layout.GOLD}" font-weight="bold">{kit.esc(ref)}</tspan>'
                    f'<tspan x="{claim_x}" fill="{layout.DARK}">{kit.esc(claim_text)}</tspan>'
                    f"</text></g>")
        out.append(kit.page_tail())
        return "".join(out)

    def fig(self, spec: SlideSpec) -> str:
        pageno = spec["pageno"]
        title = f"Fig. {spec['num']}" + ("（续）" if spec.get("cont") else "")
        body = spec["body"]
        n_lines = body_lines(body)
        svg, n = kit.mtext_lines(layout.PX0, layout.BODY_TOP, body, layout.BODY_PX,
                                 layout.DARK, leading=layout.body_lead(n_lines),
                                 maxw=layout.PANEL_W_INNER,
                                 indent_px=layout.FIRST_LINE_INDENT)
        assert n <= layout.BODY_MAX, f"body overflows ({n} lines): {body[:40]}"
        page = slug_for(spec, pageno)
        panel = [
            f'<g id="panel" data-pptx-bounds="{layout.PANEL_BOUNDS}">',
            f'<text x="{layout.PX0}" y="180" font-size="{layout.BODY_PX}" '
            f'font-weight="bold" fill="{layout.DARK}">'
            f'{kit.esc(self._title(spec["reading_point"], layout.PANEL_W_INNER, page))}'
            f"</text>",
            # NOTE: uniform x keeps the exporter reflow-merge eligible; the 2-char
            # first-line indent is applied to the merged PPTX box by postproc.
            svg,
            kit.hairline(layout.HAIRLINE_Y),
            self._quote_block(layout.PX0, layout.QUOTE_LABEL_Y, layout.QUOTE_Y,
                              spec["quote"], spec["quote_ref"],
                              layout.PANEL_W_INNER, page),
            "</g>",
        ]
        return "".join([kit.page_head("content"), kit.bg(), self._chrome(title, pageno),
                        kit.image_card(spec["img"]), "".join(panel), kit.page_tail()])

    def table(self, spec: SlideSpec) -> str:
        pageno = spec["pageno"]
        fig = spec["data"]
        s = fig["slides"][0]
        headers = s.get("headers") or ["项", "值"]
        rows = s.get("table_rows") or []
        ncol = len(headers)
        total_w = layout.TABLE_W
        first_w = int(total_w * 0.34) if ncol > 1 else total_w
        rest_w = (total_w - first_w) // max(ncol - 1, 1) if ncol > 1 else 0
        cols = ([(0, first_w, "start")]
                + [(first_w + rest_w * i, rest_w, "middle") for i in range(ncol - 1)])
        X0, Y0, RH = layout.TABLE_X0, layout.TABLE_Y0, layout.TABLE_ROW_H
        assert len(rows) + 1 <= layout.TABLE_MAX_ROWS, f"too many table rows: {len(rows)}"

        def cell(text, fill, color, bold, align):
            return {"text": text, "fill": fill, "color": color, "bold": bold,
                    "align": align, "valign": "middle", "font_size": 18}

        # Native-table marker: semantic-table.v2 metadata (the exporter turns this
        # group into a real <a:tbl>). data-pptx-fallback-sha256 is bound afterwards
        # by stamp_native_fallbacks.py --write, so this payload must stay stable.
        meta = {
            "schema": "ppt-master.semantic-table.v2",
            "x": X0, "y": Y0, "width": total_w, "height": RH * (len(rows) + 1),
            "name": "tabgroup",
            "columns": [cell(h, layout.LIGHT, layout.BLUE, True, "l" if i == 0 else "ctr")
                        for i, h in enumerate(headers)],
            "rows": [[cell(v, "#FFFFFF", layout.DARK, False, "l" if i == 0 else "ctr")
                      for i, v in enumerate(row)] for row in rows],
            "column_widths": [first_w] + [rest_w] * (ncol - 1),
            "row_heights": [RH] * (len(rows) + 1),
        }
        cells = [f'<g id="tabgroup" data-pptx-replace-with="table" '
                 f'data-pptx-bounds="{X0} {Y0} {total_w} {RH * (len(rows) + 1)}">',
                 f'<metadata type="application/json">'
                 f'{json.dumps(meta, ensure_ascii=False)}</metadata>',
                 f'<rect x="{X0}" y="{Y0}" width="{total_w}" height="{RH}" '
                 f'fill="{layout.LIGHT}"/>']
        for (off, w, align), header in zip(cols, headers):
            tx = X0 + off + (w // 2 if align == "middle" else 12)
            anchor = ' text-anchor="middle"' if align == "middle" else ""
            cells.append(f'<text x="{tx}" y="{Y0 + 31}" font-size="{layout.BODY_PX}" '
                         f'font-weight="bold" fill="{layout.BLUE}"{anchor}>'
                         f'{kit.esc(header)}</text>')
        for ri, row in enumerate(rows):
            ry = Y0 + RH * (ri + 1)
            cells.append(f'<rect x="{X0}" y="{ry}" width="{total_w}" height="{RH - 1}" '
                         f'fill="#FFFFFF" stroke="{layout.LINE}" stroke-width="1"/>')
            for (off, w, align), value in zip(cols, row):
                tx = X0 + off + (w // 2 if align == "middle" else 12)
                anchor = ' text-anchor="middle"' if align == "middle" else ""
                cells.append(f'<text x="{tx}" y="{ry + 31}" font-size="{layout.BODY_PX}" '
                             f'fill="{layout.DARK}"{anchor}>{kit.esc(value)}</text>')
        cells.append(f'<rect x="{X0}" y="{Y0}" width="{total_w}" '
                     f'height="{RH * (len(rows) + 1)}" fill="none" '
                     f'stroke="{layout.LINE}" stroke-width="1.5"/></g>')

        nx, nw = layout.NOTE_PANEL_X0, layout.NOTE_PANEL_W
        note_svg, n_lines = kit.mtext_lines(nx, layout.BODY_TOP, s["table_note"],
                                            layout.BODY_PX, layout.DARK,
                                            leading=layout.BODY_LEAD, maxw=nw,
                                            indent_px=layout.FIRST_LINE_INDENT)
        assert n_lines <= 8, f"table_note overflows ({n_lines} lines): {s['table_note'][:40]}"
        ny = layout.BODY_TOP + layout.BODY_LEAD * n_lines + 36
        page = slug_for(spec, pageno)
        panel = [
            '<g id="panel" data-pptx-bounds="800 144 432 530">',
            f'<text x="{nx}" y="180" font-size="{layout.BODY_PX}" font-weight="bold" '
            f'fill="{layout.DARK}">'
            f'{kit.esc(self._title(s["reading_point"], nw, page))}</text>',
            note_svg,
            f'<rect x="{nx}" y="{ny}" width="{nw}" height="1" fill="{layout.LINE}"/>',
            self._quote_block(nx, ny + 30, ny + 62, s["quote"], s["quote_ref"], nw, page),
            "</g>",
        ]
        return "".join([kit.page_head("content"), kit.bg(),
                        self._chrome(fig.get("title", "Table"), pageno),
                        "".join(cells), "".join(panel), kit.page_tail()])

    # -- rendering ---------------------------------------------------------
    def _plan(self) -> list[tuple[int, str, Callable[[], str]]]:
        """[(pageno, slug, builder)] in presentation order — the one roster."""
        plan: list[tuple[int, str, Callable[[], str]]] = [
            (1, "01_cover", self.cover), (2, "02_abstract", self.abstract)]
        n = 3
        if self.paper.get("intro_lines"):
            plan.append((n, f"{n:02d}_intro", lambda n=n: self.intro(n)))
            n += 1
        if self.paper.get("mainline"):
            plan.append((n, f"{n:02d}_overview", lambda n=n: self.overview(n)))
            n += 1
        if self.paper.get("methods_zh"):
            plan.append((n, f"{n:02d}_methods", lambda n=n: self.methods(n)))
            n += 1
        assert n == self.n_lead + 1, (n, self.n_lead)
        for spec in self.slides:
            pageno = spec["pageno"]
            builder = self.table if spec["type"] == "table" else self.fig
            plan.append((pageno, slug_for(spec, pageno),
                         lambda spec=spec, builder=builder: builder(spec)))
        plan.append((self.total, f"{self.total:02d}_conclusion", self.conclusion))
        return plan

    def slug_list(self) -> list[str]:
        """Slugs in slide order, without rendering anything (for the note writer)."""
        return [slug for _p, slug, _b in self._plan()]

    def pages(self) -> list[tuple[int, str, str]]:
        """[(pageno, slug, svg)] in presentation order."""
        return [(pageno, slug, builder()) for pageno, slug, builder in self._plan()]

    def page_roles(self, slugs: list[str] | None = None) -> dict:
        """cx (SVG px) per 1-based slide number, for postproc_justify."""
        if slugs is None:
            slugs = [slug for _p, slug, _s in self.pages()]
        cx = {}
        for pageno, slug in enumerate(slugs, start=1):
            if re.match(r"\d+_(fig|sch)\d+(_cont)?$", slug):
                cx[pageno] = layout.PANEL_W_INNER
            elif slug.endswith("_tab"):
                cx[pageno] = layout.NOTE_PANEL_W
            else:
                cx[pageno] = layout.CONTENT_W
        return {"total": self.total, "cx": {str(k): v for k, v in cx.items()}}

    def write(self, project_dir: pathlib.Path) -> list[str]:
        """Render every page into <project_dir>/svg_output and return the slugs."""
        out_dir = pathlib.Path(project_dir) / "svg_output"
        out_dir.mkdir(parents=True, exist_ok=True)
        for stale in out_dir.glob("*.svg"):
            stale.unlink()
        slugs = []
        for _pageno, slug, svg in self.pages():
            (out_dir / f"{slug}.svg").write_text(svg, encoding="utf-8")
            slugs.append(slug)
        return slugs


def write_page_roles(deck: Deck, workdir: pathlib.Path,
                     slugs: list[str] | None = None) -> pathlib.Path:
    """Pass `slugs` from a completed write() so the deck is not rendered twice."""
    path = pathlib.Path(workdir) / "page_roles.json"
    path.write_text(json.dumps(deck.page_roles(slugs), ensure_ascii=False, indent=1),
                    encoding="utf-8")
    return path


def project_dir(paper: dict) -> pathlib.Path:
    pd = paper.get("ppt_project")
    if not pd:
        raise SystemExit("[error] paper.ppt_project is empty — run through "
                         "pipeline/run_pipeline.py, which initialises the project "
                         "and writes the path back into content.json")
    return pathlib.Path(pd)


def load_content(workdir: str | pathlib.Path) -> dict:
    return json.loads((pathlib.Path(workdir) / "content.json").read_text(encoding="utf-8"))
