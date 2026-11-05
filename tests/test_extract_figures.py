# -*- coding: utf-8 -*-
"""Tests for the PDF figure extractor, driven by a synthetic PDF.

The extractor is the entry point of every real batch and the piece most exposed
to messy input, so it is exercised on a fitz-generated document (no copyrighted
material involved).
"""
import json
import pathlib

import fitz
import pytest

import extract_figures as ef


@pytest.fixture()
def synthetic_pdf(tmp_path):
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((72, 120), "Synthetic Layered Emitter Study", fontsize=18)
    p1.insert_text((72, 150), "A. Example et al.  doi:10.0000/jss.2026.0001", fontsize=10)
    p1.insert_text((72, 180), "Abstract: a synthetic document built for the tests.", fontsize=10)

    p2 = doc.new_page()
    p2.draw_rect(fitz.Rect(72, 90, 520, 400), color=(0, 0, 0), fill=(0.82, 0.87, 0.95))
    p2.insert_text((72, 430), "Figure 1. Synthetic test figure caption for the extractor.",
                   fontsize=10)
    p2.insert_text((72, 470), "Figure 1 shows the passivated films of this synthetic example.",
                   fontsize=10)

    path = tmp_path / "paper.pdf"
    doc.save(str(path))
    doc.close()
    return path


def _run(pdf, out):
    ef.main(str(pdf), str(out))
    return json.loads((out / "figures.json").read_text(encoding="utf-8"))


def test_caption_is_detected_and_cropped(synthetic_pdf, tmp_path):
    out = tmp_path / "work"
    figs = _run(synthetic_pdf, out)
    assert len(figs) == 1, figs
    fig = figs[0]
    assert fig["kind"] == "figure"
    assert fig["page"] == 2
    assert fig["label"].startswith("Figure 1")
    image = pathlib.Path(fig["image"])
    assert image.exists() and image.stat().st_size > 0
    assert fig["image_size"][0] > 200 and fig["image_size"][1] > 100
    # the crop must not swallow the caption line
    assert fig["crop_bbox"][3] <= 430


def test_text_dump_and_meta(synthetic_pdf, tmp_path):
    out = tmp_path / "work2"
    _run(synthetic_pdf, out)
    text = (out / "text_full.txt").read_text(encoding="utf-8")
    assert "PAGE 1" in text and "PAGE 2" in text
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert meta["pages"] == 2
    assert meta["doi"] == "10.0000/jss.2026.0001"


def test_in_text_reference_is_collected(synthetic_pdf, tmp_path):
    out = tmp_path / "work3"
    figs = _run(synthetic_pdf, out)
    assert figs[0]["refs"], "the in-text 'Figure 1 shows …' sentence should be collected"


def test_contact_sheet_is_written(synthetic_pdf, tmp_path):
    out = tmp_path / "work4"
    _run(synthetic_pdf, out)
    sheets = list(out.glob("contact_sheet_*.png"))
    assert sheets and sheets[0].stat().st_size > 0


def test_a_pdf_without_captions_yields_no_figures(tmp_path):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 120), "A paper with body text only, no captions at all.", fontsize=11)
    pdf = tmp_path / "plain.pdf"
    doc.save(str(pdf))
    doc.close()
    out = tmp_path / "work5"
    assert _run(pdf, out) == []
