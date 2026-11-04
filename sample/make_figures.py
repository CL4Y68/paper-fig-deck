# -*- coding: utf-8 -*-
"""make_figures.py — draw the synthetic sample figures.

Everything here is generated from scratch: no real measurement, no third-party
image, no paper figure. That is deliberate — the public repo must stay free of
literature content, so the only way to ship a runnable example is to invent one.

Usage:  python sample/make_figures.py [outdir]      (default: alongside this file)
        <venv-python> sample/make_figures.py sample/images
"""
from __future__ import annotations

import pathlib
import sys

from PIL import Image, ImageDraw

BG = (255, 255, 255)
INK = (51, 51, 51)
BLUE = (31, 56, 100)
GOLD = (201, 162, 39)
GRAY = (138, 143, 152)
LIGHT = (242, 245, 250)
GRID = (217, 222, 232)

W, H = 900, 620


def _grid(d: ImageDraw.ImageDraw, x0, y0, x1, y1, rows=4, cols=4):
    for i in range(rows + 1):
        y = y0 + (y1 - y0) * i // rows
        d.line([(x0, y), (x1, y)], fill=GRID, width=1)
    for i in range(cols + 1):
        x = x0 + (x1 - x0) * i // cols
        d.line([(x, y0), (x, y1)], fill=GRID, width=1)
    d.rectangle([x0, y0, x1, y1], outline=INK, width=2)


def _panel(d, box, title):
    x0, y0, x1, y1 = box
    d.rectangle([x0, y0, x1, y1], outline=GRID, width=1, fill=BG)
    d.text((x0 + 8, y0 + 6), title, fill=INK)


def fig1(path: pathlib.Path) -> None:
    """(a) quantum yield bars, control vs passivated  (b) grain-size distribution."""
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)

    # (a) bars
    ax = (90, 90, 430, 430)
    _panel(d, (40, 40, 470, 470), "(a) quantum yield (%)")
    _grid(d, *ax, rows=4, cols=2)
    base = ax[3]
    for i, (label, val, color) in enumerate([("control", 12, GRAY), ("passivated", 41, BLUE)]):
        x = ax[0] + 60 + i * 150
        h = int((ax[3] - ax[1]) * val / 50)
        d.rectangle([x, base - h, x + 70, base], fill=color)
        d.text((x + 6, base - h - 18), f"{val}%", fill=INK)
        d.text((x - 4, base + 8), label, fill=INK)
    d.line([ax[0], base, ax[3], base], fill=INK, width=2)
    d.text((62, 26), "yield / %", fill=GRAY)

    # (b) two overlapping-ish distributions as a bar histogram
    bx = (520, 90, 860, 430)
    _panel(d, (470, 40, 890, 470), "(b) grain size (nm)")
    _grid(d, *bx, rows=4, cols=4)
    d.text((512, 26), "counts", fill=GRAY)
    for i, h in enumerate([6, 18, 34, 46, 32, 15, 5]):
        x = bx[0] + 18 + i * 40
        y = bx[3] - int((bx[3] - bx[1]) * h / 50)
        d.rectangle([x, y, x + 26, bx[3]], fill=BLUE)
    for i, h in enumerate([5, 16, 31, 43, 30, 14, 4]):
        x = bx[0] + 22 + i * 40
        y = bx[3] - int((bx[3] - bx[1]) * h / 50)
        d.rectangle([x, y, x + 12, bx[3]], fill=GOLD)
    d.text((bx[0], bx[3] + 8), "40      60      80     100", fill=GRAY)

    d.text((40, 510), "control  (12%)", fill=GRAY)
    d.text((40, 536), "passivated  (41%)", fill=BLUE)
    d.text((40, 562), "synthetic sample data - not a real measurement", fill=GOLD)
    im.save(path, "JPEG", quality=88, optimize=True)


def fig2(path: pathlib.Path) -> None:
    """(a) transient decay curves  (b) trap-density bars (log scale)."""
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)

    ax = (90, 90, 430, 400)
    _panel(d, (40, 40, 470, 470), "(a) PL decay (norm.)")
    _grid(d, *ax, rows=4, cols=4)
    d.line([ax[0], ax[3], ax[3], ax[3]], fill=INK, width=2)
    d.line([ax[0], ax[1], ax[0], ax[3]], fill=INK, width=2)

    def curve(fn, color):
        pts = []
        n = 90
        for i in range(n + 1):
            x = ax[0] + (ax[3] - ax[0]) * i / n
            t = 4 * i / n
            y = ax[3] - (ax[3] - ax[1]) * fn(t)
            pts.append((x, y))
        d.line(pts, fill=color, width=3)

    curve(lambda t: 0.9 * pow(2.718, -t) + 0.1, BLUE)       # slow, passivated
    curve(lambda t: 0.55 * pow(2.718, -2.6 * t) + 0.08, GOLD)  # fast decay
    d.text((ax[0], ax[3] + 8), "time (arb. u.)", fill=GRAY)
    d.text((ax[0] + 250, ax[1] - 2), "passivated", fill=BLUE)
    d.text((ax[0] + 250, ax[1] + 22), "control", fill=GOLD)

    bx = (520, 90, 860, 400)
    _panel(d, (470, 40, 890, 470), "(b) trap density")
    _grid(d, *bx, rows=3, cols=2)
    base = bx[3]
    for i, (label, power, color) in enumerate([("control", 17, GOLD), ("passivated", 16, BLUE)]):
        x = bx[0] + 60 + i * 150
        h = int((bx[3] - bx[1]) * power / 18)
        d.rectangle([x, base - h, x + 70, base], fill=color)
        d.text((x + 4, base - h - 18), f"1e{power}", fill=INK)
        d.text((x - 4, base + 8), label, fill=INK)
    d.line([bx[0], base, bx[3], base], fill=INK, width=2)
    d.text((514, 26), "cm-3 (est.)", fill=GRAY)

    d.text((40, 510), "one order of magnitude drop after passivation", fill=INK)
    d.text((40, 536), "synthetic sample data - not a real measurement", fill=GOLD)
    im.save(path, "JPEG", quality=88, optimize=True)


def title_page(path: pathlib.Path) -> None:
    """A fake paper header to stand in for the title-page crop."""
    im = Image.new("RGB", (1200, 500), BG)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 1200, 60], fill=BLUE)
    d.text((24, 22), "Journal of Synthetic Studies", fill=BG)
    d.text((24, 100), "Interface passivation as a general route to brighter", fill=INK)
    d.text((24, 130), "layered emitters", fill=INK)
    d.text((24, 200), "A. Example, B. Sample, C. Placeholder", fill=INK)
    d.text((24, 226), "Institute of Synthetic Examples, Example City", fill=GRAY)
    d.text((24, 290), "ABSTRACT", fill=GOLD)
    for i, line in enumerate([
        "Surface traps quench emission in solution-processed layered emitters.",
        "We introduce weak-coordinating anions as a general interface design rule.",
        "The quantum yield rises from 12% to 41% without changing grain morphology.",
        "Trap density drops by an order of magnitude; five substrates reproduce it.",
        "All numbers in this example are synthetic and for pipeline testing only.",
    ]):
        d.text((24, 320 + i * 26), line, fill=INK)
    d.text((24, 470), "DOI: 10.0000/jss.2026.0001", fill=GRAY)
    im.save(path, "JPEG", quality=88, optimize=True)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    out = pathlib.Path(argv[0]) if argv else pathlib.Path(__file__).parent / "images"
    out.mkdir(parents=True, exist_ok=True)
    fig1(out / "fig01.jpg")
    fig2(out / "fig02.jpg")
    title_page(out / "p1_title.jpg")
    for p in sorted(out.glob("*.jpg")):
        print(f"{p}  {p.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
