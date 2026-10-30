# -*- coding: utf-8 -*-
"""Paper figure extraction: captions -> crop regions -> 3x renders -> figures.json + contact sheet.

Run with a Python that has pymupdf:
  python extract_figures.py <pdf> <outdir>
"""
import fitz, json, re, sys, unicodedata, pathlib

CAP_RE = re.compile(
    r'^\s*(Fig(?:ure)?\.?\s*(?:S)?\d+[.:]|[Ss]cheme\s*\d+[.:]|[Tt]able\s*(?:S)?\d+[.:])\s'
)
KIND = lambda m: 'table' if m.group(1).startswith(('Table',)) else (
    'scheme' if m.group(1).startswith(('Scheme',)) else 'figure')

def nfkc(s): return unicodedata.normalize('NFKC', s)

def main(pdf_path, outdir):
    out = pathlib.Path(outdir)
    imgs = out / 'images'
    imgs.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)

    # full text dump with page markers
    with open(out / 'text_full.txt', 'w', encoding='utf-8') as f:
        for i, page in enumerate(doc):
            f.write(f'\n===== PAGE {i+1} =====\n')
            f.write(nfkc(page.get_text('text')))

    # meta
    p0_lines = [l for l in nfkc(doc[0].get_text('text')).splitlines() if l.strip()][:12]
    doi_m = re.search(r'10\.\d{4,9}/\S+', nfkc(doc[0].get_text('text')))
    meta = {'file': pdf_path, 'pages': len(doc), 'doi': doi_m.group(0).rstrip('.,;') if doi_m else None,
            'first_lines': p0_lines}

    figures = []
    missing = []
    for pno, page in enumerate(doc):
        blocks = [b for b in page.get_text('blocks') if b[6] == 0]  # text blocks
        for b in blocks:
            first = nfkc(b[4].splitlines()[0]).strip() if b[4].strip() else ''
            m = CAP_RE.match(first)
            if not m:
                continue
            cap_text = nfkc(' '.join(b[4].split()))
            num_label = first[:24]
            kind = KIND(m)
            cap_top, cap_bottom = b[1], b[3]
            pw, ph = page.rect.width, page.rect.height

            if kind == 'figure' or kind == 'scheme':
                # header bottom: y1 of top text blocks (header + rule)
                header_bottom = 0
                for b2 in blocks:
                    if b2[1] < 55 and b2[3] < 60:
                        header_bottom = max(header_bottom, b2[3])
                # candidates: raster image rects + vector drawing rects ABOVE caption
                cands = []
                for xref in [i[0] for i in page.get_images(full=True)]:
                    try:
                        for r in page.get_image_rects(xref):
                            if r.y1 <= cap_top + 2 and r.y0 >= header_bottom and \
                               r.width > 30 and r.height > 15:
                                cands.append(fitz.Rect(r))
                    except Exception:
                        pass
                try:
                    for d in page.get_drawings():
                        r = d['rect']
                        if r.y1 <= cap_top + 2 and r.y0 >= header_bottom and \
                           r.width > 40 and r.height > 10 and \
                           r.width * r.height < 0.9 * pw * ph:
                            cands.append(fitz.Rect(r))
                except Exception:
                    pass
                # cluster by vertical contiguity (gap <= 15pt), pick cluster touching caption
                cands.sort(key=lambda r: r.y0)
                clusters = []
                for r in cands:
                    placed = False
                    for cl in clusters:
                        if r.y0 <= cl['y1'] + 15:
                            cl['y0'] = min(cl['y0'], r.y0)
                            cl['y1'] = max(cl['y1'], r.y1)
                            cl['x0'] = min(cl['x0'], r.x0)
                            cl['x1'] = max(cl['x1'], r.x1)
                            placed = True
                            break
                    if not placed:
                        clusters.append({'y0': r.y0, 'y1': r.y1, 'x0': r.x0, 'x1': r.x1, 'n': 1})
                touching = [c for c in clusters if c['y1'] >= cap_top - 20]
                chosen = (touching or clusters)[-1] if (touching or clusters) else None
                if chosen:
                    union = fitz.Rect(chosen['x0'], chosen['y0'], chosen['x1'], chosen['y1'])
                    # constrain: never include caption or header; keep figure x-range
                    union = fitz.Rect(max(union.x0, 30), max(union.y0, header_bottom + 1),
                                      min(union.x1, pw - 30), min(union.y1, cap_top + 2))
                    z = 4.0
                    if union.width * z > 2000:
                        z = 2000 / union.width
                else:
                    # fallback A: no vector/raster above -> band between last text block and caption
                    above = [b2 for b2 in blocks if b2[3] <= cap_top + 2 and b2[1] > header_bottom]
                    top = max((a[3] for a in above), default=header_bottom + 1)
                    union = fitz.Rect(60, min(top + 4, cap_top), pw - 60, cap_top + 2)
                    z = 4.0
                    if union.width * z > 2000:
                        z = 2000 / union.width
                union = fitz.Rect(max(0, union.x0 - 4), max(0, union.y0 - 4),
                                  min(pw, union.x1 + 4), min(ph, union.y1 + 6))
                union = fitz.Rect(union.x0, union.y0, union.x1, min(union.y1, cap_top))
                # top edge: never graze body-text lines above the figure.
                # Text may be rendered over the raster's white margin (raster rect
                # extends above the visible plot frame), so clip to the bottom of
                # any text block intersecting the crop x-range.
                tb = max((b2[3] for b2 in blocks
                          if b2[3] <= cap_top + 1 and b2[1] > header_bottom + 5
                          and b2[4].strip()
                          and b2[2] > union.x0 - 5 and b2[0] < union.x1 + 5),
                         default=0)
                if chosen is not None and tb > union.y0 and tb < chosen['y1'] - 10:
                    union = fitz.Rect(union.x0, tb + 1.5, union.x1, union.y1)
                pix = page.get_pixmap(matrix=fitz.Matrix(z, z), clip=union)
                w, h = pix.width, pix.height
                if w > 2000:
                    pix = page.get_pixmap(matrix=fitz.Matrix(z * 2000 / w, z * 2000 / w), clip=union)
                num_clean = re.sub(r'^[Ff]ig(?:ure)?\.?\s*|[Ss]cheme\s*|[Tt]able\s*', '', num_label)
                num_safe = re.sub(r'[\\/:*?"<>| ]', '_', num_clean)[:18]
                fname = f"{kind}_{num_safe}_p{pno+1}.png"
                pix.save(imgs / fname)
                figures.append({
                    'label': num_label, 'kind': kind, 'page': pno + 1,
                    'caption': cap_text[:400], 'image': str(imgs / fname),
                    'crop_bbox': [round(v, 1) for v in (union.x0, union.y0, union.x1, union.y1)],
                    'image_size': [pix.width, pix.height], 'n_cands': len(cands),
                })
            else:  # table: record caption + bbox region, no render
                figures.append({
                    'label': num_label, 'kind': 'table', 'page': pno + 1,
                    'caption': cap_text[:400], 'image': None,
                    'table_caption_bbox': [round(v,1) for v in b[:4]],
                })

    # in-text reference sentences
    refs = {f['label']: [] for f in figures}
    pat_cache = {}
    for f in figures:
        lab = f['label'].split()[0] + ' ' + f['label'].split()[1] if f['label'].split() else f['label']
        core = re.sub(r'^[Ff]ig(?:ure)?\.?\s*', '', lab)
        core = re.sub(r'^[Ss]cheme\s*', '', core)
        core = re.sub(r'^[Tt]able\s*', '', core)
        core = core.rstrip('.').replace(' ', '')
        pat = rf'(?:Fig(?:ure)?\.?\s*(?:S)?{re.escape(core)}(?!\d)|[Ss]cheme\s*{re.escape(core)}(?!\d)|[Tt]able\s*(?:S)?{re.escape(core)}(?!\d))'
        for pno, page in enumerate(doc):
            text = nfkc(page.get_text('text')).replace('\n', ' ')
            for s in re.split(r'(?<=[\.\!\?])\s+', text):
                if re.search(pat, s) and len(s) > 25:
                    refs[f['label']].append({'page': pno + 1, 'sentence': s.strip()[:500]})
    for f in figures:
        f['refs'] = refs.get(f['label'], [])[:4]

    json.dump(meta, open(out / 'meta.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump(figures, open(out / 'figures.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'figures: {len(figures)}  ({sum(1 for f in figures if f["kind"]=="figure")} fig, '
          f'{sum(1 for f in figures if f["kind"]=="scheme")} scheme, '
          f'{sum(1 for f in figures if f["kind"]=="table")} table)')
    for f in figures:
        if f['kind'] in ('figure', 'scheme'):
            print(f'  p{f["page"]:>3}  {f["label"][:22]:<22} cands={f["n_cands"]:>3} '
                  f'{f["image_size"][0]}x{f["image_size"][1]}  refs={len(f["refs"])}')
        else:
            print(f'  p{f["page"]:>3}  {f["label"][:22]:<22} [table] refs={len(f["refs"])}')

    # contact sheets (fitz-only, no PIL): 2 cols, 3 rows per sheet
    imgs_f = [f for f in figures if f.get('image')]
    cw, ch, pad, lab_h = 700, 520, 24, 40
    cols, rows_per_sheet = 2, 3
    per_sheet = cols * rows_per_sheet
    sheet_no = 0
    for start in range(0, len(imgs_f), per_sheet):
        chunk = imgs_f[start:start + per_sheet]
        rows = (len(chunk) + cols - 1) // cols
        W = cols * (cw + pad) + pad
        H = rows * (ch + lab_h + pad) + pad
        sheet = fitz.open()
        sp = sheet.new_page(width=W, height=H)
        sp.draw_rect(fitz.Rect(0, 0, W, H), color=None, fill=(1, 1, 1))
        for i, f in enumerate(chunk):
            r, c = divmod(i, cols)
            x0 = pad + c * (cw + pad)
            y0 = pad + r * (ch + lab_h + pad)
            sp.insert_text((x0, y0 + lab_h - 8), f'{f["label"][:20]} p{f["page"]}',
                           fontsize=16, fontname='helv', color=(0.1, 0.1, 0.9))
            img = fitz.open(f['image'])
            ip = img[0].get_pixmap(matrix=fitz.Matrix(1, 1))
            sc = min(cw / ip.width, ch / ip.height, 1.0)
            iw, ih = int(ip.width * sc), int(ip.height * sc)
            ix, iy = x0 + (cw - iw) // 2, y0 + lab_h + (ch - ih) // 2
            sp.insert_image(fitz.Rect(ix, iy, ix + iw, iy + ih), filename=f['image'])
            img.close()
        sheet_no += 1
        png = sp.get_pixmap(matrix=fitz.Matrix(1, 1))
        sheet_path = out / f'contact_sheet_{sheet_no}.png'
        png.save(sheet_path)
        print('written', sheet_path.name, png.width, 'x', png.height)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
