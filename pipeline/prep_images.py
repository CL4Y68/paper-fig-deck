# -*- coding: utf-8 -*-
"""prep_images.py — stage crops into the ppt-master project images/ dir.

Usage: <ppt-master-venv-python> prep_images.py <workdir> <projdir>
  <workdir>  contains figures.json (extract_figures.py output) + content.json
  <projdir>  is the ppt-master project dir; images go to <projdir>/images/

- figure crops: workdir/images/<crop>.png -> projdir/images/figNN.jpg
  (NN parsed from the figure label; downscale to <=2000px wide, JPEG q85,
  re-compress to <=900KB if needed)
- title-page crop: content["paper"]["title_crop"] =
  {"pdf": <abs pdf path>, "page": 1, "rect": [x0,y0,x1,y1], "out": "p1_title.jpg",
   "z": 4} -> renders projdir/images/<out> (JPEG q88, <=2000px wide)

Run with the ppt-master venv python (its Pillow).
"""
import json
import pathlib
import re
import sys


def fig_num(label: str) -> int:
    m = re.search(r"(\d+)", label)
    if not m:
        raise SystemExit(f"cannot parse figure number from label: {label!r}")
    return int(m.group(1))


def main():
    if len(sys.argv) < 3:
        raise SystemExit("usage: prep_images.py <workdir> <projdir>")
    D = pathlib.Path(sys.argv[1])
    PROJ = pathlib.Path(sys.argv[2])
    outdir = PROJ / "images"
    outdir.mkdir(parents=True, exist_ok=True)

    import PIL
    from PIL import Image
    print("PIL:", PIL.__version__)

    fs = json.loads((D / "figures.json").read_text(encoding="utf-8"))
    report = []
    for f in fs:
        if f.get("kind") not in ("figure", "scheme") or not f.get("image"):
            continue
        key = fig_num(f["label"])
        p = pathlib.Path(f["image"])
        if not p.is_absolute():
            p = D / p
        im = Image.open(p).convert("RGB")
        w, h = im.size
        if w > 2000:
            im = im.resize((2000, int(h * 2000 / w)), Image.LANCZOS)
        prefix = "sch" if f.get("kind") == "scheme" else "fig"
        out = outdir / f"{prefix}{key:02d}.jpg"
        im.save(out, "JPEG", quality=85, optimize=True)
        kb = out.stat().st_size // 1024
        note = ""
        if kb > 900:
            for q in (80, 75, 70):
                im.save(out, "JPEG", quality=q, optimize=True)
                kb = out.stat().st_size // 1024
                if kb <= 900:
                    break
            note = f" (recompress q{q})"
        report.append((key, str(im.size), kb, note))

    content = json.loads((D / "content.json").read_text(encoding="utf-8"))
    tc = content["paper"].get("title_crop")
    if tc:
        import pymupdf
        doc = pymupdf.open(tc["pdf"])
        page = doc[tc["page"] - 1]
        x0, y0, x1, y1 = tc["rect"]
        z = tc.get("z", 4.0)
        wpt = x1 - x0
        if wpt * z > 2000:
            z = 2000 / wpt
        pix = page.get_pixmap(matrix=pymupdf.Matrix(z, z),
                              clip=pymupdf.Rect(x0, y0, x1, y1))
        out = outdir / tc["out"]
        im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("RGB")
        im.save(out, "JPEG", quality=88, optimize=True)
        print(f"title crop: {out.name} {im.size} {out.stat().st_size // 1024}KB")

    for r in report:
        print(r)
    print("total fig*.jpg:", len(list(outdir.glob("fig*.jpg"))))


if __name__ == "__main__":
    main()
