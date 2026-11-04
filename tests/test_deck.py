# -*- coding: utf-8 -*-
"""Tests for the deck builder: roster, slugs, page geometry, SVG invariants."""
import json
import pathlib
import re

import pytest

import deck
import kit
import layout

SAMPLE = pathlib.Path(__file__).resolve().parents[1] / "sample" / "content.json"


@pytest.fixture(scope="module")
def content():
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def built(content):
    d = deck.Deck(content, allow_approx=True)
    return d, d.pages()


def test_roster_matches_the_page_count(content, built):
    d, pages = built
    n_fig = sum(1 for s in d.slides if s["type"] == "fig")
    n_tab = sum(1 for s in d.slides if s["type"] == "table")
    assert n_fig + n_tab == len(d.slides)
    assert len(pages) == d.total
    assert d.total == d.n_lead + len(d.slides) + 1


def test_page_numbers_are_contiguous(built):
    _d, pages = built
    assert [p for p, _s, _x in pages] == list(range(1, len(pages) + 1))


def test_slugs_are_unique_and_well_formed(built):
    _d, pages = built
    slugs = [s for _p, s, _x in pages]
    assert len(set(slugs)) == len(slugs)
    for slug in slugs:
        assert re.fullmatch(r"\d{2}_[a-z0-9_]+", slug), slug


def test_lead_pages_follow_the_documented_order(content):
    d = deck.Deck(content, allow_approx=True)
    slugs = [s for _p, s, _x in d.pages()]
    assert slugs[0] == "01_cover"
    assert slugs[1] == "02_abstract"
    lead = ["intro", "overview", "methods"]
    present = [name for name in lead if any(s.endswith(name) for s in slugs)]
    got = [s.split("_", 1)[1] for s in slugs[2:2 + len(present)]]
    assert got == present, (got, present)


def test_build_slides_is_pure(content):
    first, _ = deck.build_slides(content)
    second, _ = deck.build_slides(content)
    assert first == second
    # and it must not mutate the input
    assert "pageno" not in content["figures"][0]


def test_each_body_chunk_fits_the_measured_cap(content):
    slides, _ = deck.build_slides(content)
    for spec in slides:
        if spec["type"] == "fig":
            assert deck.body_lines(spec["body"]) <= layout.BODY_MAX


def test_split_body_keeps_all_text():
    text = "这是一个句子。" * 60
    chunks = deck.split_body(text)
    assert len(chunks) > 1
    assert "".join(chunks).replace(" ", "") == text.replace(" ", "")


def test_split_body_returns_short_text_unchanged():
    assert deck.split_body("短句。") == ["短句。"]


def test_split_body_respects_an_explicit_cap():
    text = "这是一个句子。" * 60
    for chunk in deck.split_body(text, max_lines=5):
        assert deck.body_lines(chunk) <= 5


def test_continuation_pages_are_flagged(content):
    d = deck.Deck(content, allow_approx=True)
    conts = [s for s in d.slides if s.get("cont")]
    assert conts, "sample should exercise the auto-split path"
    for spec in conts:
        assert spec["type"] == "fig"


def test_every_page_is_a_well_formed_svg_with_the_documented_roles(built):
    _d, pages = built
    for _pageno, slug, svg in pages:
        assert svg.startswith("<svg ") and svg.endswith("</svg>\n"), slug
        assert 'data-pptx-page-role="' in svg, slug
        assert f'width="{layout.CANVAS_W}"' in svg and f'height="{layout.CANVAS_H}"' in svg


def test_figure_pages_carry_card_panel_and_quote_band(built):
    _d, pages = built
    figs = [(s, x) for _p, s, x in pages if re.match(r"\d+_(fig|sch)\d+", s)]
    assert figs
    for slug, svg in figs:
        assert 'id="leftcard"' in svg, slug
        assert 'id="panel"' in svg, slug
        assert f'x="{layout.PX0}" y="{layout.HAIRLINE_Y}"' in svg.replace("y=", "y="), slug
        assert "../images/" in svg, slug
        assert "\u539f\u6587\uff08" in svg, slug        # 原文（ref）


def test_table_page_has_semantic_table_metadata(built):
    _d, pages = built
    tabs = [(s, x) for _p, s, x in pages if s.endswith("_tab")]
    assert tabs
    for _slug, svg in tabs:
        assert 'data-pptx-replace-with="table"' in svg
        assert "ppt-master.semantic-table.v2" in svg
        assert "<metadata" in svg


def test_no_text_below_the_typography_floor(built):
    _d, pages = built
    sizes = {int(m) for _p, _s, x in pages for m in re.findall(r'font-size="(\d+)"', x)}
    assert sizes and min(sizes) >= layout.MIN_PX, sizes


def test_every_page_has_a_footer_with_its_number(built):
    d, pages = built
    for pageno, slug, svg in pages:
        assert f"P{pageno:02d} / {d.total}" in svg, slug


def test_layout_constants_are_the_rendered_ones(built):
    """The panel origin/width in the SVG must equal layout.py, not a stray literal."""
    d, _pages = built
    svg = d.fig(next(s for s in d.slides if s["type"] == "fig"))
    assert f'<g id="panel" data-pptx-bounds="{layout.PANEL_BOUNDS}">' in svg
    assert f'<text x="{layout.PX0}" y="180"' in svg


def test_page_roles_map_widths_by_page_type(built):
    d, pages = built
    roles = d.page_roles([s for _p, s, _x in pages])
    assert roles["total"] == d.total
    for pageno, slug, _svg in pages:
        cx = roles["cx"][str(pageno)]
        if re.match(r"\d+_(fig|sch)\d+", slug):
            assert cx == layout.PANEL_W_INNER
        elif slug.endswith("_tab"):
            assert cx == layout.NOTE_PANEL_W
        else:
            assert cx == layout.CONTENT_W


def test_write_creates_svg_output_and_clears_stale_pages(built, tmp_path):
    d, pages = built
    out = tmp_path / "svg_output"
    out.mkdir()
    (out / "99_stale.svg").write_text("<svg/>", encoding="utf-8")
    slugs = d.write(tmp_path)
    assert len(slugs) == len(pages)
    assert not (out / "99_stale.svg").exists()
    assert sorted(p.name for p in out.glob("*.svg")) == sorted(f"{s}.svg" for s in slugs)


def test_two_decks_do_not_share_state(content):
    """Regression for the old PAPER_/KICK globals."""
    a = json.loads(json.dumps(content))
    b = json.loads(json.dumps(content))
    a["paper"]["title_zh"] = "甲"
    b["paper"]["title_zh"] = "乙"
    da, db = deck.Deck(a, allow_approx=True), deck.Deck(b, allow_approx=True)
    assert "甲" in da.cover() and "乙" not in da.cover()
    assert "乙" in db.cover() and "甲" not in db.cover()


def test_missing_project_pointer_explains_itself():
    with pytest.raises(SystemExit) as exc:
        deck.project_dir({})
    assert "run_pipeline" in str(exc.value)


def test_allow_approx_controls_strict_mode(content):
    if kit.backend_status().state == "ppt-master":
        pytest.skip("real estimator present")
    deck.Deck(content, allow_approx=False)     # no est_w call yet -> fine
    with pytest.raises(kit.BackendUnavailable):
        deck.Deck(content, allow_approx=False).pages()
    deck.Deck(content, allow_approx=True).pages()
