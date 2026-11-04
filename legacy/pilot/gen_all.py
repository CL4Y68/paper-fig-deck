# -*- coding: utf-8 -*-
"""gen_all.py — data-driven SVG generator for the paper-fig-deck pilot.

Reads pilot/content.json + figures.json (local, copyright-protected), emits
every SVG into the ppt-master project's svg_output/. Roster is dynamic:
figure slides auto-split when the key-expression body exceeds 6 lines at 24px.

Run with a Python that has the ppt-master venv packages (pymupdf, lxml):
  python pilot/gen_all.py
The ppt-master project dir is taken from $PPT_MASTER_PROJECT.
"""
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from kit import (  # noqa: E402
    BLUE, BLUE2, DARK, GOLD, GRAY, LGRAY, LIGHT, LINE,
    CANVAS_W, CANVAS_H, HEADER_BOUNDS, FOOTER_BOUNDS, PX0, PANEL_W_INNER,
    esc, est_w, wrap, mtext, mtext_lines, page_head, page_tail, bg, chrome,
    TOK,
)

D = pathlib.Path(__file__).parent
_PROJ = os.environ.get("PPT_MASTER_PROJECT")
if not _PROJ:
    raise SystemExit(
        "set PPT_MASTER_PROJECT to the ppt-master project dir "
        "(the one holding svg_output/ created for this deck)")
PROJ = pathlib.Path(_PROJ)
OUT = PROJ / "svg_output"
BODY_MAX = 9          # 24px body lines per figure slide (zone y212..548 @36 leading)
BODY_LEAD = 36

content = json.loads((D / "content.json").read_text(encoding="utf-8"))
PAPER = content["paper"]
# header kicker is data-driven (local content.json holds the paper metadata);
# the repo itself carries no paper references
KICK = " · ".join(p for p in ["文献精读", PAPER.get("authors_short"), PAPER.get("journal")] if p)
FIGNUM2JPG = {}
_maxfig = max(
    int(f["id"].replace("fig", ""))
    for f in content["figures"]
    if f.get("kind") != "table" and str(f.get("id", "")).startswith("fig")
)
for i in range(1, _maxfig + 1):
    FIGNUM2JPG[i] = f"fig{i:02d}.jpg"


def truncate1(text: str, size: int, maxw: float) -> str:
    if est_w(text, size) <= maxw:
        return text
    lo, hi = 0, len(text)
    while lo < hi - 1:
        mid = (lo + hi + 1) // 2
        if est_w(text[:mid] + "…", size) <= maxw:
            lo = mid
        else:
            hi = mid - 1
    return (text[:lo] + "…").rstrip()


def split_body(body_text: str):
    """Split into chunks each wrapping to <= BODY_MAX lines @24px/552px."""
    if len(wrap(body_text, 24, PANEL_W_INNER)) <= BODY_MAX:
        return [body_text]
    parts = re.split(r"(?<=[。；])", body_text)
    chunks, cur = [], ""
    for p in parts:
        if cur and len(wrap(cur + p, 24, PANEL_W_INNER)) > BODY_MAX:
            chunks.append(cur)
            cur = p
        else:
            cur += p
    if cur:
        chunks.append(cur)
    fixed = []
    for c in chunks:
        if len(wrap(c, 24, PANEL_W_INNER)) <= BODY_MAX:
            fixed.append(c)
            continue
        subs = re.split(r"(?<=[，、])", c)
        cur2 = ""
        for s in subs:
            if cur2 and len(wrap(cur2 + s, 24, PANEL_W_INNER)) > BODY_MAX:
                fixed.append(cur2)
                cur2 = s
            else:
                cur2 += s
        if cur2:
            fixed.append(cur2)
    for c in fixed:
        n = len(wrap(c, 24, PANEL_W_INNER))
        assert n <= BODY_MAX, f"chunk still too long ({n} lines): {c[:40]}…"
    return fixed


# ---------------- page builders ----------------

def fig_slide(spec: dict, pageno: int, total: int) -> str:
    n = spec["num"]
    title = f"Fig. {n}" + ("（续）" if spec.get("cont") else "")
    out = [page_head("content")]
    out.append(bg())
    out.append(chrome(KICK, title, pageno, total))
    out.append(
        f'<g id="leftcard" data-pptx-bounds="48 144 568 496">'
        f'<rect x="48" y="144" width="568" height="496" fill="#FFFFFF" stroke="{LINE}" stroke-width="1.5"/>'
        f'<image x="64" y="160" width="536" height="464" preserveAspectRatio="xMidYMid meet" '
        f'href="../images/{spec["img"]}"/>'
        f"</g>"
    )
    p = [f'<g id="panel" data-pptx-bounds="640 144 608 496">']
    p.append(f'<text x="{PX0}" y="180" font-size="24" font-weight="bold" fill="{DARK}">{esc(spec["reading_point"])}</text>')
    # NOTE: no per-line x offset (uniform x keeps exporter reflow-merge eligible);
    # the 2-char first-line indent is applied to the merged PPTX box by postproc.
    bsvg, bn = mtext_lines(PX0, 212, spec["body"], 24, DARK, leading=BODY_LEAD, maxw=PANEL_W_INNER, indent_px=48)
    assert bn <= BODY_MAX, f"body overflows: {spec['body'][:40]}"
    p.append(bsvg)
    p.append(f'<rect x="{PX0}" y="556" width="{PANEL_W_INNER}" height="1" fill="{LINE}"/>')
    qlabel = f"原文（{spec['quote_ref']}）"
    p.append(f'<text x="{PX0}" y="584" font-size="24" font-weight="bold" fill="{GRAY}">{esc(qlabel)}</text>')
    p.append(mtext(PX0, 616, truncate1(spec["quote"], 24, PANEL_W_INNER), 24, LGRAY, maxw=PANEL_W_INNER))
    p.append("</g>")
    out.append("".join(p))
    out.append(page_tail())
    return "".join(out)


def table_slide(spec: dict, pageno: int, total: int) -> str:
    s = spec["slides"][0]
    out = [page_head("content")]
    out.append(bg())
    out.append(chrome(KICK, "Table 1", pageno, total))
    cols = [(0, 260, "start"), (260, 150, "middle"), (410, 160, "middle"), (570, 160, "middle")]
    X0, Y0, RH = 48, 160, 48
    cells = [f'<g id="tabgroup" data-pptx-bounds="48 144 740 464">']
    cells.append(f'<rect x="{X0}" y="{Y0}" width="730" height="{RH}" fill="{LIGHT}"/>')
    headers = ["样本", "V / kV", "I / mA", "T / °C"]
    for (off, w, al), htxt in zip(cols, headers):
        tx = X0 + off + (w // 2 if al == "middle" else 12)
        anchor = ' text-anchor="middle"' if al == "middle" else ""
        cells.append(f'<text x="{tx}" y="{Y0 + 31}" font-size="24" font-weight="bold" fill="{BLUE}"{anchor}>{esc(htxt)}</text>')
    for ri, row in enumerate(s["table_rows"]):
        ry = Y0 + RH * (ri + 1)
        cells.append(f'<rect x="{X0}" y="{ry}" width="730" height="{RH - 1}" fill="#FFFFFF" stroke="{LINE}" stroke-width="1"/>')
        for (off, w, al), val in zip(cols, row):
            tx = X0 + off + (w // 2 if al == "middle" else 12)
            anchor = ' text-anchor="middle"' if al == "middle" else ""
            cells.append(f'<text x="{tx}" y="{ry + 31}" font-size="24" fill="{DARK}"{anchor}>{esc(val)}</text>')
    cells.append(f'<rect x="{X0}" y="{Y0}" width="730" height="{RH * (len(s["table_rows"]) + 1)}" fill="none" stroke="{LINE}" stroke-width="1.5"/>')
    cells.append("</g>")
    out.append("".join(cells))
    p = [f'<g id="panel" data-pptx-bounds="800 144 432 496">']
    p.append(f'<text x="828" y="180" font-size="24" font-weight="bold" fill="{DARK}">{esc(s["reading_point"])}</text>')
    nsvg, nn = mtext_lines(828, 212, s["table_note"], 24, DARK, leading=BODY_LEAD, maxw=376, indent_px=48)
    assert nn <= 8, f"table_note overflows: {s['table_note'][:40]}"
    p.append(nsvg)
    ny = 212 + BODY_LEAD * nn + 36
    p.append(f'<rect x="828" y="{ny}" width="376" height="1" fill="{LINE}"/>')
    p.append(f'<text x="828" y="{ny + 30}" font-size="24" font-weight="bold" fill="{GRAY}">原文（{esc(s["quote_ref"])}）</text>')
    p.append(mtext(828, ny + 62, truncate1(s["quote"], 24, 376), 24, LGRAY, maxw=376))
    p.append("</g>")
    out.append("".join(p))
    out.append(page_tail())
    return "".join(out)


def intro_page(pageno: int, total: int) -> str:
    """Single-page Introduction analysis: gold-bold section labels flow inline
    (label + one space + body text), full canvas width, first-line indent."""
    out = [page_head("content")]
    out.append(bg())
    out.append(chrome(KICK, "Introduction 分析", pageno, total))
    X, Y0, MAXW, LEAD, IND = 48, 156, 1184, 32, 48
    # token stream: (style, text) — style: 'L' label, 'T' text
    toks = []
    for label, text in PAPER["intro_lines"]:
        toks.append(("L", label + " "))
        for m in TOK.finditer(text):
            toks.append(("T", m.group(0)))
    # greedy pack: every label starts a NEW line (小标题新起一行); the body then
    # flows on the label's line after one space and wraps at MAXW. First line
    # budget MAXW-IND (PPT first-line indent lands there); continuation lines
    # start at X (uniform x keeps the exporter's reflow-merge eligible).
    lines, cur, cur_w = [], [], 0
    budget0, budget = MAXW - IND, MAXW
    for st, tk in toks:
        w = est_w(tk, 24)
        if st == "L":
            if cur:
                lines.append(cur)
                cur, cur_w = [], 0
            cur.append((st, tk))
            cur_w += w
        else:
            b = budget0 if not lines and not cur else (budget0 if not lines else budget)
            if cur and cur_w + w > b:
                # close current line at a token boundary
                while cur and cur[-1][0] == "T" and len(cur) > 1:
                    _, prev = cur.pop()
                    break
                lines.append(cur)
                cur, cur_w = [("T", tk)], w
            else:
                cur.append((st, tk))
                cur_w += w
    if cur:
        lines.append(cur)
    assert len(lines) <= 16, f"intro needs {len(lines)} lines > 16: condense intro_lines"
    # emit one <text> with styled runs; continuation lines as tspans
    def line_runs_svg(runs):
        parts, i = [], 0
        while i < len(runs):
            st, tk = runs[i]
            j = i
            while j + 1 < len(runs) and runs[j + 1][0] == st:
                j += 1
            txt = "".join(t for _, t in runs[i:j + 1])
            if st == "L":
                parts.append(f'<tspan fill="{GOLD}" font-weight="bold">{esc(txt)}</tspan>')
            else:
                parts.append(f'<tspan fill="{DARK}">{esc(txt)}</tspan>')
            i = j + 1
        return "".join(parts)
    body = line_runs_svg(lines[0])
    for ln in lines[1:]:
        body += f'\n<tspan x="{X}" dy="{LEAD}">{line_runs_svg(ln)}</tspan>'
    g = [f'<g id="introg" data-pptx-bounds="48 144 1184 512">']
    g.append(f'<text x="{X}" y="{Y0}" font-size="24">{body}</text>')
    g.append("</g>")
    out.append("".join(g))
    out.append(page_tail())
    return "".join(out)


def abstract_slide(pageno: int, total: int) -> str:
    out = [page_head("content")]
    out.append(bg())
    out.append(chrome(KICK, "摘要（中文）", pageno, total))
    a = [f'<g id="absgroup" data-pptx-bounds="48 144 1184 512">']
    n = len(wrap(PAPER["abstract_zh"], 24, 1184))
    assert n <= 10, f"abstract_zh too long: {n} lines"
    a.append(mtext_lines(48, 200, PAPER["abstract_zh"], 24, DARK, leading=36, maxw=1184, indent_px=48)[0])
    a.append(f'<text x="48" y="612" font-size="24" fill="{LGRAY}">（译自原文 Abstract，p. 1）</text>')
    a.append("</g>")
    out.append("".join(a))
    out.append(page_tail())
    return "".join(out)


def conclusion_slide(pageno: int, total: int) -> str:
    out = [page_head("ending")]
    out.append(bg())
    out.append(chrome(KICK, "结论（中文）", pageno, total))
    c = [f'<g id="cong" data-pptx-bounds="48 144 1184 512">']
    n = len(wrap(PAPER["conclusion_zh"], 24, 1184))
    assert n <= 10, f"conclusion_zh too long: {n} lines"
    c.append(mtext_lines(48, 200, PAPER["conclusion_zh"], 24, DARK, leading=36, maxw=1184, indent_px=48)[0])
    c.append(f'<text x="48" y="612" font-size="24" fill="{LGRAY}">（译自原文 4. Conclusions，p. 17）</text>')
    c.append("</g>")
    out.append("".join(c))
    out.append(page_tail())
    return "".join(out)


def methods_page(pageno: int, total: int) -> str:
    """Preparation-methods page: one full-width justified paragraph (indent 2 chars)."""
    out = [page_head("content")]
    out.append(bg())
    out.append(chrome(KICK, "制备方法（Materials and Methods）", pageno, total))
    g = [f'<g id="methodsg" data-pptx-bounds="48 144 1184 512">']
    n = len(wrap(PAPER["methods_zh"], 24, 1184))
    assert n <= 12, f"methods_zh too long: {n} lines"
    svg, _ = mtext_lines(48, 156, PAPER["methods_zh"], 24, DARK, leading=36,
                         maxw=1184, indent_px=48)
    g.append(svg)
    g.append(f'<text x="48" y="612" font-size="24" fill="{LGRAY}">{esc(PAPER["methods_src"])}</text>')
    g.append("</g>")
    out.append("".join(g))
    out.append(page_tail())
    return "".join(out)


def cover_slide(pageno: int, total: int) -> str:
    out = [page_head("cover", first=True)]
    out.append(bg())
    c = [f'<g id="covermain" data-pptx-bounds="48 80 1184 580">']
    c.append(f'<rect x="48" y="96" width="1184" height="395" fill="#FFFFFF" stroke="{LINE}" stroke-width="1.5"/>')
    c.append(f'<image x="64" y="112" width="1152" height="363" preserveAspectRatio="xMidYMid meet" '
            f'href="../images/{PAPER["title_page_img"]}"/>')
    c.append(f'<text x="48" y="530" font-size="32" font-weight="bold" fill="{BLUE}">{esc(PAPER["title_zh"])}</text>')
    c.append(mtext(48, 568, "Keywords: " + PAPER["keywords_en"], 24, GRAY, leading=36, maxw=1088))
    c.append(f'<text x="48" y="640" font-size="24" fill="{GRAY}">DOI: {PAPER["doi"]} · {PAPER["journal"]} · {esc(PAPER["authors_short"])}</text>')
    c.append("</g>")
    out.append("".join(c))
    out.append(chrome_footer_only(pageno, total))
    out.append(page_tail())
    return "".join(out)


def chrome_footer_only(pageno: int, total: int) -> str:
    return (f'<g id="footer" data-pptx-bounds="{FOOTER_BOUNDS}">'
            f'<text x="1232" y="700" font-size="24" fill="{LGRAY}" text-anchor="end">P{pageno:02d} / {total}</text>'
            f"</g>")


# ---------------- roster ----------------

def build_roster():
    ro = []
    figs = [f for f in content["figures"] if f.get("kind") != "table"]
    tab = [f for f in content["figures"] if f.get("kind") == "table"][0]
    ro.append(("fig", figs[0]))                      # Fig 1
    ro.append(("tab", tab))                           # Table 1
    for f in figs[1:]:                                # remaining figures
        ro.append(("fig", f))
    slides = []
    for kind, f in ro:
        if kind == "tab":
            slides.append({"type": "table", "data": f, "idx_label": f.get("idx_label", "Table 1")})
            continue
        key = int(f["id"].replace("fig", ""))
        img = FIGNUM2JPG[key]
        sub = f["slides"]
        for si, s in enumerate(sub):
            chunks = split_body(s["body"][0])
            for ci, ch in enumerate(chunks):
                slides.append({
                    "type": "fig", "num": key, "img": img,
                    "reading_point": s["reading_point"], "what": s["what"],
                    "body": ch, "quote": s["quote"], "quote_ref": s["quote_ref"],
                    "cont": (si > 0) or (ci > 0),
                })
        slides[-1]["idx_label"] = f"Fig. {key}  " + f["slides"][0]["reading_point"][:10]
    return slides


slides_roster = build_roster()
TOTAL = 3 + 1 + len(slides_roster) + 1

# ---------------- emit ----------------

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.svg"):
        old.unlink()

    files = []
    files.append(("01_cover", cover_slide(1, TOTAL)))
    files.append(("02_abstract", abstract_slide(2, TOTAL)))
    n = 3
    files.append((f"{n:02d}_intro", intro_page(n, TOTAL)))
    n += 1
    files.append((f"{n:02d}_methods", methods_page(n, TOTAL)))
    n += 1
    for spec in slides_roster:
        if spec["type"] == "table":
            svg = table_slide(spec["data"], n, TOTAL)
            files.append((f"{n:02d}_tab1", svg))
        else:
            svg = fig_slide(spec, n, TOTAL)
            files.append((f"{n:02d}_fig{spec['num']:02d}" + ("_cont" if spec.get("cont") else ""), svg))
        n += 1
    files.append((f"{n:02d}_conclusion", conclusion_slide(n, TOTAL)))

    for slug, svg in files:
        (OUT / f"{slug}.svg").write_text(svg, encoding="utf-8")
    print(f"emitted {len(files)} SVGs; TOTAL={TOTAL}")
    for slug, _ in files:
        print(" ", slug)


if __name__ == "__main__":
    main()
