# -*- coding: utf-8 -*-
"""postproc_justify.py — PPTX post-export patch (reflow-aware).

Works on exports produced with `svg_to_pptx.py --reflow-text`: each body
paragraph is one wrap="square" text frame holding a single a:p. This script:

  1. restores the intended wrap width: the exporter sizes the frame to the
     WIDEST actual line, but PowerPoint reflows at the frame width, which
     would produce MORE lines than the SVG layout; set <a:ext cx> back to the
     layout width (per slide, from a page_roles.json sidecar when given);
  2. 两端对齐: a:pPr/@algn="just" on the body frame's paragraph;
  3. 首行缩进两字符: a:pPr/@indent="457200" (36pt = 2 x 18pt CJK chars).

Usage: python postproc_justify.py <src.pptx> <dst.pptx> [page_roles.json]
  page_roles.json: {"total": N, "cx": {"2": 1184, "3": 552, ...}} (svg px).
  Without it, falls back to the pilot slide-number map.
"""
import json
import re
import sys
import zipfile
from pathlib import Path

EMU = 9525          # EMU per SVG px (12192000 / 1280)
INDENT = "457200"   # 36pt

# fallback per-slide wrap width (pilot deck, 29 slides)
def cx_target_pilot(slide_no: int):
    if slide_no in (2, 3, 4, 29):   # full-text pages
        return 1184
    if slide_no == 6:               # table page: note column
        return 376
    if 5 <= slide_no <= 28:         # figure pages
        return 552
    return None


def is_body_frame(blk: str) -> bool:
    """Merged reflow frame carrying a long body paragraph."""
    return (
        'wrap="square"' in blk
        and 'sz="1800"' in blk
        and 'val="333333"' in blk
        and sum(len(t) for t in re.findall(r"<a:t>(.*?)</a:t>", blk, re.S)) >= 40
    )


def patch_frame(blk: str, cx_px: int | None) -> str:
    if cx_px:
        blk = re.sub(
            r'(<a:ext cx=")\d+(\")',
            rf'\g<1>{cx_px * EMU}\2',
            blk, count=1)
    def _ppr(mm):
        ppr = mm.group(0)
        if "algn=" in ppr:
            ppr = re.sub(r'algn="[^"]*"', 'algn="just"', ppr, count=1)
        else:
            ppr = re.sub(r"(<a:pPr\b)", r'\1 algn="just"', ppr, count=1)
        if "indent=" not in ppr:
            ppr = re.sub(r"(<a:pPr\b)", rf'\1 indent="{INDENT}"', ppr, count=1)
        return ppr
    blk = re.sub(r"<a:pPr\b[^>]*(/?)>", _ppr, blk, count=1)
    if "<a:pPr" not in blk.split("</a:p>")[0]:
        blk = blk.replace("<a:p>", f'<a:p><a:pPr algn="just" indent="{INDENT}"/>', 1)
    return blk


def main():
    src, dst = sys.argv[1], sys.argv[2]
    cx_map = None
    if len(sys.argv) > 3:
        cx_map = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))["cx"]

    def cx_for(slide_no: int):
        if cx_map is not None:
            return cx_map.get(str(slide_no))
        return cx_target_pilot(slide_no)

    zin = zipfile.ZipFile(src)
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            m = re.match(r"ppt/slides/slide(\d+)\.xml$", item.filename)
            if not m:
                zout.writestr(item, zin.read(item.filename))
                continue
            slide_no = int(m.group(1))
            cx_px = cx_for(slide_no)
            xml = zin.read(item.filename).decode("utf-8")
            changed = False
            for sm in re.finditer(r"<p:sp>.*?</p:sp>", xml, re.S):
                blk = sm.group(0)
                if is_body_frame(blk):
                    new = patch_frame(blk, cx_px)
                    xml = xml.replace(blk, new, 1)
                    changed = True
            if changed:
                n += 1
            zout.writestr(item, xml.encode("utf-8"))
    print(f"postproc: {n} slides adjusted (cx/algn/indent) -> {dst}")


if __name__ == "__main__":
    main()
