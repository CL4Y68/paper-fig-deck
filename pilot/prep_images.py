
import os, sys, json, pathlib
import PIL
print("PIL:", PIL.__version__)
from PIL import Image
d = pathlib.Path(__file__).parent
proj = os.environ.get("PPT_MASTER_PROJECT")
if not proj:
    raise SystemExit("set PPT_MASTER_PROJECT to the ppt-master project dir")
outdir = pathlib.Path(proj) / "images"
outdir.mkdir(parents=True, exist_ok=True)
fs = json.load(open(d / "figures.json", encoding="utf-8"))
report = []
for f in fs:
    if f["kind"] != "figure" or not f.get("image"):
        continue
    key = int(f["label"].replace("Figure", "").split(".")[0].strip())
    src = f["image"].replace("\\", "/")
    p = pathlib.Path(d) / src
    im = Image.open(p).convert("RGB")
    w, h = im.size
    if w > 2000:
        im = im.resize((2000, int(h * 2000 / w)), Image.LANCZOS)
    out = outdir / f"fig{key:02d}.jpg"
    im.save(out, "JPEG", quality=85, optimize=True)
    kb = out.stat().st_size // 1024
    report.append((key, str(im.size), kb))
    if kb > 900:
        # re-compress lower
        for q in (80, 75, 70):
            im.save(out, "JPEG", quality=q, optimize=True)
            kb = out.stat().st_size // 1024
            if kb <= 900:
                break
        report[-1] = (key, str(im.size), kb, "recompress q" + str(q))
for r in report:
    print(r)
print("total files:", len(list(outdir.glob('fig*.jpg'))))
