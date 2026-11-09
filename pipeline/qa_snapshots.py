# -*- coding: utf-8 -*-
"""qa_snapshots.py — deterministic visual-QA helpers for a built ppt-master project.

The quality gate proves coordinates, not pixels: CJK glyphs render wider than
estimates, and a tspan stacking bug passes every bounds check. The final visual
pass is cheap IF the deterministic parts are scripted; this tool is those parts.
Screenshots themselves are taken by the agent's own browser tool (CDP wrapper,
Edge CLI, ...), so the script stays backend-agnostic and public-safe.

Sub-commands
------------
make <project-dir>
    Wrap the key slides (cover, overview, first/last figure page, conclusion)
    in `<project>/qa/<slug>.qa.html` shells and print the screenshot file names
    the agent must drop into `<project>/qa/<slug>.png`.
    A bare `file://…<slug>.svg` is NOT navigable in most browser engines —
    it must be wrapped in an HTML shell; that wrapper is what make writes.

assemble <project-dir> [--out SHEET]
    Combine the agent-dropped `qa/<slug>.png` shots into one labelled contact
    sheet (default `qa/sheet.png`). Refuses to build when every shot is
    byte-identical — that is the stale/blank-capture signature, not a deck.

Usage (ppt-master venv python has Pillow):
    <venv-python> qa_snapshots.py make <project-dir>
    # agent: screenshot each printed .qa.html -> qa/<slug>.png
    <venv-python> qa_snapshots.py assemble <project-dir>
    # agent: one vision pass over qa/sheet.png
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))

# --------------------------------------------------------------------------- picking

_HTML = ('<html><head><meta charset="utf-8"></head>'
         '<body style="margin:0">\n{svg}\n</body></html>\n')


def _slugs(project: pathlib.Path) -> list[str]:
    out = project / "svg_output"
    if not out.is_dir():
        raise SystemExit(f"no svg_output/ under {project} — run the pipeline first")
    return sorted(p.stem for p in out.glob("*.svg"))


def pick_key_slugs(slugs: list[str]) -> list[str]:
    """Cover + overview + first/last figure-family page + conclusion (deduped)."""
    figs = [s for s in slugs if re.match(r"^\d+_(fig|sch|table|tbl)\d", s)]
    by_role = {
        "cover": _first(slugs, r"^01_"),
        "overview": _first(slugs, r"_overview$"),
        "first_fig": figs[0] if figs else None,
        "last_fig": figs[-1] if figs else None,
        "conclusion": _first(slugs, r"_conclusion$"),
    }
    seen: set[str] = set()
    deduped: list[str] = []
    for s in by_role.values():
        if s and s not in seen:
            seen.add(s)
            deduped.append(s)
    return deduped


def _first(slugs: list[str], pat: str):
    for s in slugs:
        if re.search(pat, s):
            return s
    return None


def cmd_make(project: pathlib.Path, args) -> int:
    qa = project / "qa"
    qa.mkdir(exist_ok=True)
    picked = pick_key_slugs(_slugs(project))
    if not picked:
        raise SystemExit("no key slides found in svg_output/ — nothing to wrap")
    for slug in picked:
        svg = (project / "svg_output" / f"{slug}.svg").read_text(encoding="utf-8")
        (qa / f"{slug}.qa.html").write_text(_HTML.format(svg=svg), encoding="utf-8")
    print("wrap ok — screenshot each page, then drop the PNG into the printed names:")
    for slug in picked:
        print(f"  {qa / f'{slug}.qa.html'}  ->  {qa / f'{slug}.png'}")
    return 0


# --------------------------------------------------------------------------- assembling

def cmd_assemble(project: pathlib.Path, args) -> int:
    from PIL import Image, ImageDraw

    qa = project / "qa"
    shots = {p.stem: p for p in qa.glob("*.png") if p.stem != "sheet"}
    if not shots:
        raise SystemExit(f"no qa/*.png screenshots in {qa} — run `make` + browser shots first")
    digests = {hashlib.sha1(p.read_bytes()).hexdigest() for p in shots.values()}
    if len(shots) > 1 and len(digests) == 1:
        raise SystemExit(
            f"all {len(shots)} shots are byte-identical — stale or blank capture, "
            "check the browser before assembling")
    cell_w, cell_h, cap = 640, 360, 22
    per_row = 2
    rows = (len(shots) + per_row - 1) // per_row
    sheet = Image.new("RGB", (per_row * cell_w, rows * (cell_h + cap)), "white")
    for i, (name, path) in enumerate(sorted(shots.items())):
        im = Image.open(path).convert("RGB")
        if im.size[0] > cell_w:
            im = im.resize((cell_w, int(im.size[1] * cell_w / im.size[0])),
                           Image.Resampling.LANCZOS)
        r, c = divmod(i, per_row)
        x0, y0 = c * cell_w, r * (cell_h + cap)
        sheet.paste(im, (x0, y0 + cap))
        dr = ImageDraw.Draw(sheet)
        dr.rectangle([x0, y0, x0 + cell_w - 1, y0 + cap - 1], fill=(29, 78, 216))
        dr.text((x0 + 6, y0 + 4), f"{name}  [sheet chrome — ignore labels]",
                fill="white")
    out = pathlib.Path(args.out) if args.out else qa / "sheet.png"
    sheet.save(out)
    print(f"sheet ok -> {out}  ({len(shots)} cells: {', '.join(sorted(shots))})")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        "qa_snapshots.py — visual-QA helpers: wrap key slides, assemble contact sheets")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("make", help="wrap key slides in .qa.html shells")
    m.add_argument("project")
    m.set_defaults(fn=cmd_make)
    a = sub.add_parser("assemble", help="combine qa/*.png into a contact sheet")
    a.add_argument("project")
    a.add_argument("--out", default=None)
    a.set_defaults(fn=cmd_assemble)
    args = ap.parse_args(argv)
    return args.fn(pathlib.Path(args.project), args)


if __name__ == "__main__":
    raise SystemExit(main())
