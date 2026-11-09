# -*- coding: utf-8 -*-
"""Tests for qa_snapshots.py: key-slug picking, HTML wrapping, sheet assembly."""
import pathlib

import pytest
import qa_snapshots as qsn
from PIL import Image


def _make_project(tmp_path: pathlib.Path, slugs) -> pathlib.Path:
    proj = tmp_path / "proj"
    out = proj / "svg_output"
    out.mkdir(parents=True)
    for s in slugs:
        (out / f"{s}.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720">'
            f'<text x="48" y="60">{s}</text></svg>\n', encoding="utf-8")
    return proj


SLUGS = ["01_cover", "02_abstract", "03_intro", "04_overview",
         "05_fig01", "09_fig02", "10_conclusion"]


def test_pick_key_slugs(tmp_path):
    _make_project(tmp_path, SLUGS)
    picked = qsn.pick_key_slugs(SLUGS)
    assert picked == ["01_cover", "04_overview", "05_fig01", "09_fig02", "10_conclusion"]


def test_pick_key_slugs_no_overview(tmp_path):
    slugs = [s for s in SLUGS if s != "04_overview"]
    picked = qsn.pick_key_slugs(slugs)
    assert picked == ["01_cover", "05_fig01", "09_fig02", "10_conclusion"]


def test_make_wraps_html(tmp_path):
    proj = _make_project(tmp_path, SLUGS)
    rc = qsn.main(["make", str(proj)])
    assert rc == 0
    qa = proj / "qa"
    for slug in qsn.pick_key_slugs(SLUGS):
        html = (qa / f"{slug}.qa.html").read_text(encoding="utf-8")
        assert html.startswith("<html><head><meta charset")
        assert f"<text x=\"48\" y=\"60\">{slug}</text>" in html
        assert html.rstrip().endswith("</html>")


def test_assemble_rejects_blank_capture(tmp_path):
    proj = _make_project(tmp_path, SLUGS)
    qsn.main(["make", str(proj)])
    qa = proj / "qa"
    same = Image.new("RGB", (200, 100), "white")
    same.save(qa / "01_cover.png")
    same.save(qa / "04_overview.png")
    with pytest.raises(SystemExit, match="byte-identical"):
        qsn.main(["assemble", str(proj)])


def test_assemble_builds_sheet(tmp_path):
    proj = _make_project(tmp_path, SLUGS)
    qsn.main(["make", str(proj)])
    qa = proj / "qa"
    for i, slug in enumerate(["01_cover", "04_overview", "10_conclusion"]):
        im = Image.new("RGB", (200, 100), (i * 60, 40, 200))
        im.save(qa / f"{slug}.png")
    rc = qsn.main(["assemble", str(proj)])
    assert rc == 0
    sheet = qa / "sheet.png"
    assert sheet.is_file()
    assert Image.open(sheet).size[0] == 1280  # 2 cells wide


def test_assemble_no_shots(tmp_path):
    proj = _make_project(tmp_path, SLUGS)
    qsn.main(["make", str(proj)])
    with pytest.raises(SystemExit, match=r"no qa/\*.png"):
        qsn.main(["assemble", str(proj)])
