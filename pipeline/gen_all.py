# -*- coding: utf-8 -*-
"""gen_all.py — generalized data-driven SVG generator (paper-fig-deck v4 layout).

Usage: python gen_all.py <workdir>
  <workdir> must contain content.json (paper + figures); SVGs go into
  <content["paper"]["ppt_project"]>/svg_output/, and <workdir>/page_roles.json
  (per-slide cx map for postproc_justify.py) is written alongside.

Page roster (content-driven):
  P01 cover (title-page crop) -> P02 abstract -> [intro if intro_lines]
  -> [methods if methods_zh] -> figures (in content.json order; a figure spec
  auto-splits into （续） pages when body > BODY_MAX lines; a table spec
  renders left table + right note) -> conclusion.

content.json schema:
  paper: {title_zh, title_en, authors_short, journal, doi, keywords_en,
          title_page_img, kicker, footer?, abstract_zh, abstract_src?,
          intro_lines? (list of [label, text]), methods_zh?, methods_src?,
          conclusion_zh, conclusion_src?, ppt_project}
  figures: [ {num, img?, slides:[{reading_point, what, body, quote, quote_ref}]},
             {kind:"table", title?, slides:[{reading_point, what, headers?,
              table_rows, table_note, quote, quote_ref}]} ]
"""
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from kit import (  # noqa: E402
    BLUE, BLUE2, DARK, GOLD, GRAY, LGRAY, LIGHT, LINE,
    CANVAS_W, CANVAS_H, HEADER_BOUNDS, FOOTER_BOUNDS, PX0, PANEL_W_INNER,
    esc, est_w, wrap, mtext, mtext_lines, page_head, page_tail, bg, chrome,
    TOK,
)

import kit  # noqa: E402

BODY_MAX = 14        # MEASURED (measure_capacity.py, PowerPoint COM render + pixel scan, 2026-10-29):
                    # the 552px PPT body box @18pt TNR+SimSun with 48px first-line indent stays clear of the
                    # y556 hairline through 14 lines (ink bottom 552px); 15 lines overflows (584px).
                    # Never pick the cap by line-count intuition - re-measure with measure_capacity.py.
BODY_LEAD = 36       # default leading; tighter leadings auto-computed for long bodies so the SVG zone y212..548 holds


def _body_lead(n_lines: int) -> int:
    """SVG leading so n body lines stay inside zone y212..548 (336px available)."""
    return min(BODY_LEAD, 336 // max(n_lines, 1))
KICK = ""
PAPER_ = {}


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


def _body_lines(text: str) -> int:
    """Line count exactly as mtext_lines renders it (first-line indent 48px,
    continuation lines full PANEL_W_INNER) — must match fig_slide rendering."""
    _, n = mtext_lines(0, 0, text, 24, DARK, leading=BODY_LEAD, maxw=PANEL_W_INNER, indent_px=48)
    return n


def split_body(body_text: str):
    """Split into chunks each rendering to <= BODY_MAX lines (indent-aware)."""
    if _body_lines(body_text) <= BODY_MAX:
        return [body_text]
    parts = re.split(r"(?<=[。；])", body_text)
    chunks, cur = [], ""
    for p in parts:
        if cur and _body_lines(cur + p) > BODY_MAX:
            chunks.append(cur)
            cur = p
        else:
            cur += p
    if cur:
        chunks.append(cur)
    fixed = []
    for c in chunks:
        if _body_lines(c) <= BODY_MAX:
            fixed.append(c)
            continue
        subs = re.split(r"(?<=[，、])", c)
        cur2 = ""
        for s in subs:
            if cur2 and _body_lines(cur2 + s) > BODY_MAX:
                fixed.append(cur2)
                cur2 = s
            else:
                cur2 += s
        if cur2:
            fixed.append(cur2)
    for c in fixed:
        n = _body_lines(c)
        assert n <= BODY_MAX, f"chunk still too long ({n} lines): {c[:40]}…"
    return fixed


# ---------------- page builders ----------------

def fig_slide(spec: dict, pageno: int, total: int) -> str:
    title = f"Fig. {spec['num']}" + ("（续）" if spec.get("cont") else "")
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
    # NOTE: uniform x keeps the exporter reflow-merge eligible; the 2-char
    # first-line indent is applied to the merged PPTX box by postproc.
    bn = _body_lines(spec["body"])
    bsvg, bn = mtext_lines(PX0, 212, spec["body"], 24, DARK,
                           leading=_body_lead(bn),
                           maxw=PANEL_W_INNER, indent_px=48)
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
    out.append(chrome(KICK, spec.get("title", "Table"), pageno, total))
    headers = s.get("headers") or ["项", "值"]
    rows = s.get("table_rows") or []
    ncol = len(headers)
    total_w = 730
    first_w = int(total_w * 0.34) if ncol > 1 else total_w
    rest_w = (total_w - first_w) // max(ncol - 1, 1) if ncol > 1 else 0
    cols = [(0, first_w, "start")] + [(first_w + rest_w * i, rest_w, "middle") for i in range(ncol - 1)]
    X0, Y0, RH = 48, 160, 48
    assert len(rows) + 1 <= 8, f"too many table rows: {len(rows)}"
    # Native-table marker: semantic-table.v2 metadata (see ai-agent-intro 12_matrix).
    # data-pptx-fallback-sha256 is bound afterwards by stamp_native_fallbacks.py --write.
    def _cell(text, fill, color, bold, align):
        return json.dumps({
            "text": text, "fill": fill, "color": color, "bold": bold,
            "align": align, "valign": "middle", "font_size": 18,
        }, ensure_ascii=False)

    meta_cols = [
        _cell(htxt, LIGHT, BLUE, True, "l" if i == 0 else "ctr")
        for i, htxt in enumerate(headers)
    ]
    meta_rows = [
        [_cell(val, "#FFFFFF", DARK, False, "l" if i == 0 else "ctr")
         for i, val in enumerate(row)]
        for row in rows
    ]
    tbl_h = RH * (len(rows) + 1)
    meta_payload = json.dumps({
        "schema": "ppt-master.semantic-table.v2",
        "x": X0, "y": Y0, "width": total_w, "height": tbl_h,
        "name": "tabgroup",
        "columns": [json.loads(c) for c in meta_cols],
        "rows": [[json.loads(c) for c in row] for row in meta_rows],
        "column_widths": [first_w] + [rest_w] * (ncol - 1),
        "row_heights": [RH] * (len(rows) + 1),
    }, ensure_ascii=False)
    cells = [f'<g id="tabgroup" data-pptx-replace-with="table" '
             f'data-pptx-bounds="{X0} {Y0} {total_w} {tbl_h}">']
    cells.append(f'<metadata type="application/json">{meta_payload}</metadata>')
    cells.append(f'<rect x="{X0}" y="{Y0}" width="{total_w}" height="{RH}" fill="{LIGHT}"/>')
    for (off, w, al), htxt in zip(cols, headers):
        tx = X0 + off + (w // 2 if al == "middle" else 12)
        anchor = ' text-anchor="middle"' if al == "middle" else ""
        cells.append(f'<text x="{tx}" y="{Y0 + 31}" font-size="24" font-weight="bold" fill="{BLUE}"{anchor}>{esc(htxt)}</text>')
    for ri, row in enumerate(rows):
        ry = Y0 + RH * (ri + 1)
        cells.append(f'<rect x="{X0}" y="{ry}" width="{total_w}" height="{RH - 1}" fill="#FFFFFF" stroke="{LINE}" stroke-width="1"/>')
        for (off, w, al), val in zip(cols, row):
            tx = X0 + off + (w // 2 if al == "middle" else 12)
            anchor = ' text-anchor="middle"' if al == "middle" else ""
            cells.append(f'<text x="{tx}" y="{ry + 31}" font-size="24" fill="{DARK}"{anchor}>{esc(val)}</text>')
    cells.append(f'<rect x="{X0}" y="{Y0}" width="{total_w}" height="{RH * (len(rows) + 1)}" fill="none" stroke="{LINE}" stroke-width="1.5"/>')
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
    """Single-page Introduction analysis: every gold label starts a NEW line;
    the body then flows on the label's line (label + space + 正文), wrapping
    at MAXW. First line budget MAXW-IND (PPT first-line indent lands there);
    continuation lines start at X (uniform x keeps the reflow-merge eligible).
    """
    out = [page_head("content")]
    out.append(bg())
    out.append(chrome(KICK, "Introduction 分析", pageno, total))
    X, Y0, MAXW, LEAD, IND = 48, 156, 1184, 32, 48
    toks = []
    for label, text in PAPER_["intro_lines"]:
        toks.append(("L", label + " "))
        for m in TOK.finditer(text):
            toks.append(("T", m.group(0)))
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
            b = budget0 if not lines else budget
            if cur and cur_w + w > b:
                while cur and cur[-1][0] == "T" and len(cur) > 1:
                    cur.pop()
                    break
                lines.append(cur)
                cur, cur_w = [("T", tk)], w
            else:
                cur.append((st, tk))
                cur_w += w
    if cur:
        lines.append(cur)
    assert len(lines) <= 16, f"intro needs {len(lines)} lines > 16: condense intro_lines"

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


def overview_page(pageno: int, total: int) -> str:
    """C1: 论证主线总览页 — one line per figure/table spec:
    gold ref label (Fig N / Scheme N / Table N) + dark claim (what it proves).
    Two columns when >9 specs. Each row is its own <g data-pptx-bounds> module
    with one <text> (proven pattern: same as figure-page label rows) so export
    placement is deterministic and no paragraph-run warnings fire; postproc
    never touches these (small single-line boxes, not merged body frames)."""
    out = [page_head("content")]
    out.append(bg())
    out.append(chrome(KICK, "论证主线：每张图证明什么", pageno, total))
    specs = PAPER_.get("mainline") or []
    n = len(specs)
    two_col = n > 9
    col_w = 560 if two_col else 1184
    lead = 44
    y0 = 170
    cols = ([specs[: (n + 1) // 2], specs[(n + 1) // 2 :]] if two_col else [specs])
    cx_pos = [48, 636] if two_col else [48]
    for ci, col in enumerate(cols):
        x = cx_pos[ci]
        for ri, (ref, claim) in enumerate(col):
            yy = y0 + ri * lead
            refw = est_w(ref + "　", 24)
            claim_t = truncate1(claim, 24, col_w - refw)
            out.append(
                f'<g id="ovrow{ci}_{ri:02d}" data-pptx-bounds="{x} {yy - 30} {col_w} 40">'
                f'<text x="{x}" y="{yy}" font-size="24" fill="{DARK}">'
                f'<tspan fill="{GOLD}" font-weight="bold">{esc(ref)}</tspan>'
                f'<tspan x="{x + int(refw)}" fill="{DARK}">{esc(claim_t)}</tspan>'
                f"</text></g>"
            )
    out.append(page_tail())
    return "".join(out)


def abstract_slide(pageno: int, total: int) -> str:
    out = [page_head("content")]
    out.append(bg())
    out.append(chrome(KICK, "摘要（中文）", pageno, total))
    a = [f'<g id="absgroup" data-pptx-bounds="48 144 1184 512">']
    n = len(wrap(PAPER_["abstract_zh"], 24, 1184))
    assert n <= 10, f"abstract_zh too long: {n} lines"
    a.append(mtext_lines(48, 200, PAPER_["abstract_zh"], 24, DARK, leading=36, maxw=1184, indent_px=48)[0])
    a.append(f'<text x="48" y="612" font-size="24" fill="{LGRAY}">{esc(PAPER_.get("abstract_src", "（译自原文 Abstract）"))}</text>')
    a.append("</g>")
    out.append("".join(a))
    out.append(page_tail())
    return "".join(out)


def conclusion_slide(pageno: int, total: int) -> str:
    out = [page_head("ending")]
    out.append(bg())
    out.append(chrome(KICK, "结论（中文）", pageno, total))
    c = [f'<g id="cong" data-pptx-bounds="48 144 1184 512">']
    n = len(wrap(PAPER_["conclusion_zh"], 24, 1184))
    assert n <= 10, f"conclusion_zh too long: {n} lines"
    c.append(mtext_lines(48, 200, PAPER_["conclusion_zh"], 24, DARK, leading=36, maxw=1184, indent_px=48)[0])
    c.append(f'<text x="48" y="612" font-size="24" fill="{LGRAY}">{esc(PAPER_.get("conclusion_src", "（译自原文 Conclusions）"))}</text>')
    c.append("</g>")
    out.append("".join(c))
    out.append(page_tail())
    return "".join(out)


def methods_page(pageno: int, total: int) -> str:
    out = [page_head("content")]
    out.append(bg())
    out.append(chrome(KICK, "制备方法（Materials and Methods）", pageno, total))
    g = [f'<g id="methodsg" data-pptx-bounds="48 144 1184 512">']
    n = len(wrap(PAPER_["methods_zh"], 24, 1184))
    assert n <= 12, f"methods_zh too long: {n} lines"
    svg, _ = mtext_lines(48, 156, PAPER_["methods_zh"], 24, DARK, leading=36,
                         maxw=1184, indent_px=48)
    g.append(svg)
    if PAPER_.get("methods_src"):
        g.append(f'<text x="48" y="612" font-size="24" fill="{LGRAY}">{esc(PAPER_["methods_src"])}</text>')
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
             f'href="../images/{PAPER_["title_page_img"]}"/>')
    c.append(f'<text x="48" y="530" font-size="32" font-weight="bold" fill="{BLUE}">{esc(PAPER_["title_zh"])}</text>')
    if PAPER_.get("keywords_en"):
        c.append(mtext(48, 568, "Keywords: " + PAPER_["keywords_en"], 24, GRAY, leading=36, maxw=1088))
    c.append(f'<text x="48" y="640" font-size="24" fill="{GRAY}">DOI: {PAPER_["doi"]} · {esc(PAPER_["journal"])} · {esc(PAPER_["authors_short"])}</text>')
    c.append("</g>")
    out.append("".join(c))
    out.append(chrome_footer_only(pageno, total))
    out.append(page_tail())
    return "".join(out)


def chrome_footer_only(pageno: int, total: int) -> str:
    return (f'<g id="footer" data-pptx-bounds="{FOOTER_BOUNDS}">'
            f'<text x="1232" y="700" font-size="24" fill="{LGRAY}" text-anchor="end">P{pageno:02d} / {total}</text>'
            f"</g>")


# ---------------- main ----------------

def build_slides(content: dict):
    """Roster shared by main() and gen_notes: figure/table specs in content
    order, body chunks pre-split, pageno assigned after the lead pages."""
    global PAPER_
    PAPER_ = content["paper"]
    slides = []
    mainline = PAPER_.get("mainline") or []
    for fi, f in enumerate(content["figures"]):
        claim = mainline[fi][1] if fi < len(mainline) else None
        if f.get("kind") == "table":
            slides.append({"type": "table", "data": f, "pageno": None,
                           "claim": claim, "critique": f.get("critique"),
                           "arguing": f.get("arguing"),
                           "ml_index": fi + 1, "ml_total": len(mainline) or len(content["figures"])})
            continue
        sub = f["slides"]
        for si, s in enumerate(sub):
            chunks = split_body(s["body"])
            for ci, ch in enumerate(chunks):
                slides.append({
                    "type": "fig", "kind": f.get("kind", "figure"), "num": f["num"],
                    "img": f.get("img", f"fig{f['num']:02d}.jpg"),
                    "reading_point": s["reading_point"], "what": s["what"],
                    "body": ch, "quote": s["quote"], "quote_ref": s["quote_ref"],
                    "cont": (si > 0) or (ci > 0),
                    "claim": claim, "critique": f.get("critique"),
                    "arguing": f.get("arguing"),
                    "ml_index": fi + 1, "ml_total": len(mainline) or len(content["figures"]),
                })
    n_lead = (2
              + (1 if PAPER_.get("intro_lines") else 0)
              + (1 if PAPER_.get("mainline") else 0)
              + (1 if PAPER_.get("methods_zh") else 0))
    for i, s in enumerate(slides):
        s["pageno"] = n_lead + 1 + i
    return slides, n_lead


def main():
    global KICK, PAPER_
    if len(sys.argv) < 2:
        raise SystemExit("usage: gen_all.py <workdir>")
    D = pathlib.Path(sys.argv[1])
    content = json.loads((D / "content.json").read_text(encoding="utf-8"))
    PAPER_ = content["paper"]
    KICK = PAPER_.get("kicker") or "文献精读"
    kit.FOOTER_TEXT = PAPER_.get("footer", KICK)
    PROJ = pathlib.Path(PAPER_["ppt_project"])
    OUT = PROJ / "svg_output"
    OUT.mkdir(parents=True, exist_ok=True)

    slides, n_lead = build_slides(content)
    TOTAL = n_lead + len(slides) + 1

    for old in OUT.glob("*.svg"):
        old.unlink()
    files = []
    files.append(("01_cover", cover_slide(1, TOTAL)))
    files.append(("02_abstract", abstract_slide(2, TOTAL)))
    n = 3
    if PAPER_.get("intro_lines"):
        files.append((f"{n:02d}_intro", intro_page(n, TOTAL)))
        n += 1
    if PAPER_.get("mainline"):
        files.append((f"{n:02d}_overview", overview_page(n, TOTAL)))
        n += 1
    if PAPER_.get("methods_zh"):
        files.append((f"{n:02d}_methods", methods_page(n, TOTAL)))
        n += 1
    assert n == (n_lead + 1), (n, n_lead)
    for s in slides:
        pno = s["pageno"]
        if s["type"] == "table":
            files.append((f"{pno:02d}_tab", table_slide(s["data"], pno, TOTAL)))
        else:
            sfx = "_cont" if s.get("cont") else ""
            pref = "sch" if s.get("kind") == "scheme" else "fig"
            files.append((f"{pno:02d}_{pref}{s['num']:02d}{sfx}", fig_slide(s, pno, TOTAL)))
    files.append((f"{TOTAL:02d}_conclusion", conclusion_slide(TOTAL, TOTAL)))

    for slug, svg in files:
        (OUT / f"{slug}.svg").write_text(svg, encoding="utf-8")

    cx = {}
    for i, (slug, _) in enumerate(files, start=1):
        if re.match(r"\d+_(fig|sch)\d+(_cont)?$", slug):
            cx[i] = 552
        elif "_tab" in slug:
            cx[i] = 376
        else:
            cx[i] = 1184
    (D / "page_roles.json").write_text(json.dumps(
        {"total": TOTAL, "cx": {str(k): v for k, v in cx.items()}},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"emitted {len(files)} SVGs; TOTAL={TOTAL} -> {OUT}")
    for slug, _ in files:
        print(" ", slug)


if __name__ == "__main__":
    main()
