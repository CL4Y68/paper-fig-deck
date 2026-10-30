"""Definitive PPT-line-capacity measurement for the figure-page body box.

Takes one long body (>=15 estimator lines) from a paper workdir's
content.json, truncates it at the estimator's own line boundaries into
12/13/14/15-line prefixes, renders each in the exact export geometry
(box 668,212 w552; 18pt TNR+SimSun; hairline at y556) via PowerPoint COM,
pixel-measures, and prints the largest N that stays clear of the hairline.
That N is the BODY_MAX to use in gen_all.py.

Usage:
    python measure_capacity.py <paper_workdir> [fig_num]
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from gen_all import _body_lines  # noqa: E402

from measure_lines import (EMU, build_body_box, render_pngs, ink_bottom,  # noqa: E402
                           get_body, HAIR_Y)
import json


def find_long_body(wd: Path, fig_num=None, need=15):
    """A figure body whose estimator count is >= need (explicit or first match)."""
    if fig_num is not None:
        body = get_body(wd, fig_num)
        assert _body_lines(body) >= need, f"fig {fig_num} body has <{need} est lines"
        return body
    c = json.loads((wd / "content.json").read_text(encoding="utf-8"))
    for f in c.get("figures", []):
        for s in f.get("slides", []):
            if s.get("body") and _body_lines(s["body"]) >= need:
                return s["body"]
    raise SystemExit(f"no body with >={need} est lines found in {wd}/content.json")


def prefixes_for(body, n_max):
    # for each target n, binary-search the longest prefix the estimator
    # counts as <= n lines -> the text that actually renders as n lines
    out = []
    for n in range(12, n_max + 1):
        lo, hi = n * 15, len(body)
        best = body
        while lo <= hi:
            mid = (lo + hi) // 2
            if _body_lines(body[:mid]) <= n:
                best, lo = body[:mid], mid + 1
            else:
                hi = mid - 1
        out.append((n, _body_lines(best), best))
    return out


def main():
    from pptx import Presentation
    from pptx.util import Emu

    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    wd = Path(sys.argv[1])
    fig_num = int(sys.argv[2]) if len(sys.argv) > 2 else None
    body = find_long_body(wd, fig_num)
    cases = prefixes_for(body, 15)

    prs = Presentation()
    prs.slide_width = Emu(1280 * EMU)
    prs.slide_height = Emu(720 * EMU)
    blank = prs.slide_layouts[6]
    for _n, _est, text in cases:
        build_body_box(prs, blank, text)
    outdir = HERE / "measure_out"
    outdir.mkdir(exist_ok=True)
    pptx = outdir / "cap_test.pptx"
    prs.save(pptx)
    png_dir = outdir / "cap_png"
    png_dir.mkdir(exist_ok=True)
    for f in png_dir.glob("slide*.png"):
        f.unlink()
    render_pngs(pptx, png_dir)
    fits = {}
    for i, (n, est, _text) in enumerate(cases, 1):
        bottom = ink_bottom(png_dir / f"slide{i}.png")
        ok = bottom is not None and bottom < HAIR_Y - 2
        fits[i] = (n, est, bottom, ok)
        print(f"target {n:>2} lines: text_bottom={bottom:.0f}px -> {'FITS' if ok else 'OVERFLOW'}")
    biggest = max((v for v in fits.values() if v[3]), key=lambda v: v[0], default=None)
    print("=> max PPT lines that stay clear of the y556 hairline:",
          biggest[0] if biggest else "none")
    return biggest


if __name__ == "__main__":
    main()
