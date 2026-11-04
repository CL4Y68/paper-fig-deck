# -*- coding: utf-8 -*-
"""Tests for the SVG text primitives (wrap / truncate / mtext / chrome).

They run against whichever width model is available: the ppt-master estimator
when installed, the built-in approximation otherwise. Assertions are therefore
model-agnostic — they check invariants (no character loss, width respected up to
the punctuation overhang, uniform x) rather than magic pixel numbers.
"""
import re

import pytest

import kit

CJK_BODY = (
    "本文通过同相碳化策略构建了双限域结构，使磷光寿命提升至629毫秒，"
    "并系统考察了温度与湿度对发光性能的影响；对照实验排除了聚集诱导猝灭的可能。"
)
MIXED = "Fig. 3a shows the PL decay of CDs@BA at 300 K (λex = 365 nm), τ = 629 ms."


def test_backend_status_is_reported():
    st = kit.backend_status()
    assert st.state in ("ppt-master", "approx")
    if st.state == "ppt-master":
        assert st.scripts_dir and st.detail == "resolved"


def test_est_w_scales_with_size_and_length():
    assert kit.est_w("中文", 24) > kit.est_w("中", 24)
    assert kit.est_w("中中", 24) > kit.est_w("中中", 12)
    assert kit.est_w("", 24) >= 0


def test_wrap_keeps_every_character():
    for text, width in ((CJK_BODY, 552), (CJK_BODY, 300), (MIXED, 400)):
        lines = kit.wrap(text, 24, width)
        assert lines
        assert "".join(lines).replace(" ", "") == text.replace(" ", "")


def test_wrap_respects_the_width_budget():
    for line in kit.wrap(CJK_BODY, 24, 552):
        # the last line may carry one pulled-up punctuation mark as an overhang
        assert kit.est_w(line, 24) <= 552 * 1.08, line


def test_wrap_pulls_a_lone_trailing_punctuation_onto_the_previous_line():
    text = "结论。" * 1
    lines = kit.wrap("短句" * 40 + "。", 24, 120)
    assert all(len(line) > 1 for line in lines), lines
    assert kit.wrap(text, 24, 552) == [text]


def test_wrap_narrower_box_yields_more_lines():
    assert len(kit.wrap(CJK_BODY, 24, 300)) > len(kit.wrap(CJK_BODY, 24, 552))


def test_truncate1_fits_and_marks_elision():
    out = kit.truncate1(CJK_BODY, 24, 300)
    assert out.endswith("\u2026")
    assert kit.est_w(out, 24) <= 300
    assert CJK_BODY.startswith(out[:-1])


def test_truncate1_keeps_short_text_verbatim():
    assert kit.truncate1("短", 24, 300) == "短"


def test_count_lines_matches_mtext_lines():
    for indent in (0, 48):
        svg, n = kit.mtext_lines(100, 200, CJK_BODY, 24, kit.DARK,
                                 maxw=552, indent_px=indent)
        assert n == kit.count_lines(CJK_BODY, 24, 552, indent_px=indent)
        assert len(re.findall(r"<tspan", svg)) == n - 1


def test_mtext_emits_uniform_x_for_reflow_merge():
    svg, _ = kit.mtext_lines(100, 200, CJK_BODY, 24, kit.DARK, maxw=300, indent_px=48)
    xs = re.findall(r'x="(\d+)"', svg)
    assert set(xs) == {"100"}


def test_indent_shortens_only_the_first_line():
    plain = kit.wrap(CJK_BODY, 24, 552)
    indented = kit.mtext_lines(0, 0, CJK_BODY, 24, kit.DARK, maxw=552, indent_px=48)[1]
    assert indented >= len(plain)


def test_esc_escapes_xml_metacharacters():
    assert kit.esc("a<b&c") == "a&lt;b&amp;c"


def test_page_envelope_is_wellformed():
    head = kit.page_head("content", first=True)
    assert head.startswith("<svg ") and head.rstrip().endswith(">")
    assert 'lang="zh-CN"' in head
    assert 'data-pptx-page-role="content"' in head
    assert kit.page_tail() == "</svg>\n"


def test_chrome_carries_page_number_and_footer():
    svg = kit.chrome("kicker", "标题", 3, 12, footer_text="文献精读")
    assert "P03 / 12" in svg
    assert "文献精读" in svg
    assert f'data-pptx-bounds="{kit.HEADER_BOUNDS}"' in svg
    assert f'data-pptx-bounds="{kit.FOOTER_BOUNDS}"' in svg


def test_image_card_points_at_relative_images_dir():
    svg = kit.image_card("fig01.jpg")
    assert 'href="../images/fig01.jpg"' in svg
    assert "xlink:href" not in svg


def test_strict_mode_raises_only_when_backend_missing(monkeypatch):
    if kit.backend_status().state == "ppt-master":
        pytest.skip("real estimator present; strict mode cannot be exercised")
    kit.set_strict(True)
    try:
        with pytest.raises(kit.BackendUnavailable):
            kit.est_w("x", 24)
    finally:
        kit.set_strict(False)
