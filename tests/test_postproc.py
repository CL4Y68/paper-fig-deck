# -*- coding: utf-8 -*-
"""Tests for the PPTX post-processor (pure string surgery, no PowerPoint needed)."""
import json
import zipfile

import postproc_justify as pp

EMU = pp.EMU


def _slide_xml(cx="4000000", algn=None,
               text=("这是一段足够长的正文，用来触发 body frame 的识别逻辑；"
                     "它需要超过四十个字符才会被当成合并后的正文段落处理。")):
    ppr = f'<a:pPr algn="{algn}"/>' if algn else ""
    return (
        '<p:sld xmlns:p="p" xmlns:a="a"><p:cSld><p:spTree>'
        '<p:sp><p:txBody><a:bodyPr wrap="square"/><a:p>'
        f"{ppr}"
        f'<a:r><a:rPr sz="1800"><a:solidFill><a:srgbClr val="333333"/></a:solidFill></a:rPr>'
        f"<a:t>{text}</a:t></a:r></a:p></p:txBody>"
        f'<p:spPr><a:xfrm><a:ext cx="{cx}" cy="100000"/></a:xfrm></p:spPr>'
        "</p:sp></p:spTree></p:cSld></p:sld>"
    )


def test_pilot_fallback_map():
    assert pp.cx_target_pilot(2) == 1184
    assert pp.cx_target_pilot(4) == 1184
    assert pp.cx_target_pilot(6) == 376
    assert pp.cx_target_pilot(10) == 552
    assert pp.cx_target_pilot(28) == 552
    assert pp.cx_target_pilot(29) == 1184
    assert pp.cx_target_pilot(1) is None
    assert pp.cx_target_pilot(99) is None


def test_is_body_frame_detects_a_long_18pt_body():
    assert pp.is_body_frame(_slide_xml())
    # too short -> not a body paragraph
    assert not pp.is_body_frame(_slide_xml(text="短"))
    # wrong size -> some other text box
    assert not pp.is_body_frame(_slide_xml().replace('sz="1800"', 'sz="2400"'))
    # not a reflow frame
    assert not pp.is_body_frame(_slide_xml().replace('wrap="square"', 'wrap="none"'))


def test_patch_frame_restores_width_alignment_and_indent():
    out = pp.patch_frame(_slide_xml(), 552)
    assert f'cx="{552 * EMU}"' in out
    assert 'algn="just"' in out
    assert f'indent="{pp.INDENT}"' in out


def test_patch_frame_replaces_an_existing_alignment():
    out = pp.patch_frame(_slide_xml(algn="l"), 1184)
    assert 'algn="just"' in out
    assert 'algn="l"' not in out


def test_patch_frame_is_idempotent():
    once = pp.patch_frame(_slide_xml(), 552)
    twice = pp.patch_frame(once, 552)
    assert once == twice


def test_patch_frame_without_cx_leaves_the_width_alone():
    out = pp.patch_frame(_slide_xml(cx="123456"), None)
    assert 'cx="123456"' in out
    assert 'algn="just"' in out


def _make_pptx(path, slides):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        for i, xml in enumerate(slides, start=1):
            z.writestr(f"ppt/slides/slide{i}.xml", xml)


def test_main_rewrites_only_body_slides(tmp_path):
    src = tmp_path / "in.pptx"
    dst = tmp_path / "out.pptx"
    roles = tmp_path / "page_roles.json"
    _make_pptx(src, [_slide_xml(), _slide_xml(text="短")])
    roles.write_text(json.dumps({"total": 2, "cx": {"1": 552}}), encoding="utf-8")

    pp.main([str(src), str(dst), str(roles)])

    with zipfile.ZipFile(dst) as z:
        assert "ppt/slides/slide1.xml" in z.namelist()
        first = z.read("ppt/slides/slide1.xml").decode("utf-8")
        second = z.read("ppt/slides/slide2.xml").decode("utf-8")
    assert f'cx="{552 * EMU}"' in first
    assert 'cx="4000000"' in second          # short text untouched
    assert "[Content_Types].xml" in zipfile.ZipFile(dst).namelist()


def test_missing_page_roles_is_an_error(tmp_path):
    """A deck-specific width map has no safe default: fail instead of guessing."""
    src = tmp_path / "in.pptx"
    dst = tmp_path / "out.pptx"
    _make_pptx(src, [_slide_xml()])
    try:
        pp.main([str(src), str(dst)])
    except SystemExit as exc:
        assert "page_roles.json is required" in str(exc)
    else:
        raise AssertionError("expected SystemExit when page_roles.json is missing")
    assert not dst.exists()


def test_pilot_map_is_available_but_opt_in(tmp_path):
    src = tmp_path / "in.pptx"
    dst = tmp_path / "out.pptx"
    _make_pptx(src, [_slide_xml(), _slide_xml()])
    pp.main([str(src), str(dst), "--pilot-map"])
    with zipfile.ZipFile(dst) as z:
        first = z.read("ppt/slides/slide1.xml").decode("utf-8")
        second = z.read("ppt/slides/slide2.xml").decode("utf-8")
    assert 'cx="4000000"' in first          # slide 1 has no pilot width -> untouched
    assert f'cx="{1184 * EMU}"' in second   # slide 2 = full-text page
