# -*- coding: utf-8 -*-
"""Tests for the content.json validator and its JSON Schema mirror."""
import copy
import json
import pathlib

import pytest

import content_schema as cs
import kit
import layout

SAMPLE = pathlib.Path(__file__).resolve().parents[1] / "sample" / "content.json"


@pytest.fixture()
def content():
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


def paths(issues):
    return {i.path for i in issues}


def test_sample_is_clean(content):
    issues = cs.validate(content)
    assert issues == [], cs.format_issues(issues)


def test_sample_needs_a_project_pointer_at_build_stage(content):
    issues = cs.validate(content, stage="build")
    assert paths(cs.errors(issues)) == {"paper.ppt_project"}


def test_missing_paper_is_fatal():
    issues = cs.validate({"figures": []})
    errs = [i for i in cs.errors(issues)]
    assert [i.path for i in errs] == ["paper"]
    assert all(i.severity == "error" for i in errs)


def test_missing_required_paper_field_is_named(content):
    del content["paper"]["doi"]
    errs = cs.errors(cs.validate(content))
    assert [i.path for i in errs] == ["paper.doi"]


def test_blank_string_counts_as_missing(content):
    content["paper"]["journal"] = "   "
    assert "paper.journal" in paths(cs.errors(cs.validate(content)))


def test_figures_must_not_be_empty(content):
    content["figures"] = []
    assert any(i.path == "figures" and i.severity == "error"
               for i in cs.validate(content))


def test_unknown_figure_kind_is_rejected(content):
    content["figures"][0]["kind"] = "photo"
    assert "figures[0].kind" in paths(cs.errors(cs.validate(content)))


def test_figure_needs_a_positive_integer_number(content):
    for bad in (0, -1, "1", None, True):
        c = copy.deepcopy(content)
        c["figures"][1]["num"] = bad
        assert "figures[1].num" in paths(cs.errors(cs.validate(c))), bad


def test_figure_slide_required_fields(content):
    del content["figures"][1]["slides"][0]["quote_ref"]
    assert "figures[1].slides[0].quote_ref" in paths(cs.errors(cs.validate(content)))


def test_long_body_is_only_a_warning(content):
    content["figures"][1]["slides"][0]["body"] = "字" * 2000
    issues = cs.validate(content)
    assert not cs.errors(issues)
    assert "figures[1].slides[0].body" in paths(issues)


def test_table_row_overflow_is_rejected(content):
    table = content["figures"][2]
    row = table["slides"][0]["table_rows"][0]
    table["slides"][0]["table_rows"] = [list(row) for _ in range(9)]
    assert "figures[2].slides[0].table_rows" in paths(cs.errors(cs.validate(content)))


def test_table_column_mismatch_is_rejected(content):
    table = content["figures"][2]["slides"][0]
    table["table_rows"][0] = table["table_rows"][0][:2]
    assert "figures[2].slides[0].table_rows[0]" in paths(cs.errors(cs.validate(content)))


def test_table_without_rows_is_rejected(content):
    del content["figures"][2]["slides"][0]["table_rows"]
    assert "figures[2].slides[0].table_rows" in paths(cs.errors(cs.validate(content)))


def test_mainline_length_mismatch_warns(content):
    content["paper"]["mainline"] = content["paper"]["mainline"][:1]
    issues = cs.validate(content)
    assert "paper.mainline" in paths(issues)
    assert not cs.errors(issues)


def test_intro_line_must_be_a_pair(content):
    content["paper"]["intro_lines"][0] = ["only a label"]
    assert "paper.intro_lines[0]" in paths(cs.errors(cs.validate(content)))


def test_unsupported_schema_version_is_rejected(content):
    content["schema_version"] = "999"
    assert "schema_version" in paths(cs.errors(cs.validate(content)))


def test_missing_schema_version_warns_but_builds(content):
    del content["schema_version"]
    issues = cs.validate(content)
    assert not cs.errors(issues)
    assert "schema_version" in paths(issues)


def test_title_crop_requires_rect_and_page(content):
    content["paper"]["title_crop"] = {"pdf": "x.pdf"}
    errs = paths(cs.errors(cs.validate(content)))
    assert {"paper.title_crop.page", "paper.title_crop.rect",
            "paper.title_crop.out"} <= errs


def test_issue_ordering_puts_errors_first(content):
    content["paper"]["doi"] = ""
    content["figures"][1]["slides"][0]["body"] = "字" * 2000
    issues = cs.validate(content)
    assert issues[0].severity == "error"
    assert issues[-1].severity == "warning"


def test_format_issues_is_readable(content):
    content["paper"]["doi"] = ""
    text = cs.format_issues(cs.validate(content))
    assert "[error] paper.doi" in text


def test_json_schema_mirror_accepts_the_sample(content):
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.validate(instance=content, schema=cs.json_schema())


def test_json_schema_mirror_rejects_a_bad_table(content):
    jsonschema = pytest.importorskip("jsonschema")
    content["figures"][2]["slides"][0]["table_rows"] = []
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=content, schema=cs.json_schema())


def test_write_json_schema_cli(tmp_path):
    out = tmp_path / "content.schema.json"
    assert cs.main(["--write-json-schema", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["title"].startswith("paper-fig-deck")


def test_cli_exit_codes(tmp_path):
    good = tmp_path / "good.json"
    good.write_text(SAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    assert cs.main([str(good)]) == 0

    bad = tmp_path / "bad.json"
    bad.write_text("{}", encoding="utf-8")
    assert cs.main([str(bad)]) == 1

    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert cs.main([str(broken)]) == 2


def test_load_accepts_a_workdir_path():
    assert cs.load(SAMPLE.parent)["paper"]["doi"] == "10.0000/jss.2026.0001"


# ------------------------------------------------ quote / title width evidence
def test_sample_quotes_fit_the_quote_band(content):
    """The bundled sample is the reference deck: no quotation may need a 4th line."""
    for fig in content["figures"]:
        width = (layout.NOTE_PANEL_W if fig.get("kind") == "table"
                 else layout.PANEL_W_INNER)
        for slide in fig["slides"]:
            lines = kit.wrap(slide["quote"], layout.BODY_PX, width)
            assert len(lines) <= layout.QUOTE_MAX_LINES, (slide["quote"], len(lines))


def test_over_long_quote_is_an_error_when_the_real_model_is_available(content):
    content["figures"][0]["slides"][0]["quote"] = "word " * 80
    issues = [i for i in cs.validate(content) if i.path.endswith(".quote")]
    assert issues, "an over-long quotation must be reported"
    exact = kit.backend_status().state == "ppt-master"
    # Off-backend we must not block a deck on the approximate model.
    assert issues[0].severity == ("error" if exact else "warning")


def test_over_long_reading_point_is_flagged(content):
    content["figures"][0]["slides"][0]["reading_point"] = (
        "一个明显过长以至于单行面板标题完全放不下的读点题名示例")
    issues = [i for i in cs.validate(content) if i.path.endswith(".reading_point")]
    assert issues, "a title that cannot fit one line must be reported"


# ------------------------------------------- the fixed Introduction five-line route
def test_sample_uses_the_fixed_five_line_route(content):
    labels = [label for label, _text in content["paper"]["intro_lines"]]
    assert labels == list(cs.INTRO_ROUTE)


def test_a_short_introduction_is_an_error(content):
    content["paper"]["intro_lines"] = content["paper"]["intro_lines"][:3]
    issues = cs.errors(cs.validate(content))
    assert "paper.intro_lines" in paths(issues)


def test_a_renamed_introduction_line_is_an_error(content):
    lines = [list(pair) for pair in content["paper"]["intro_lines"]]
    lines[2][0] = "别人的工作"
    content["paper"]["intro_lines"] = lines
    issues = cs.errors(cs.validate(content))
    assert "paper.intro_lines" in paths(issues)


def test_out_of_order_introduction_is_an_error(content):
    lines = [list(pair) for pair in content["paper"]["intro_lines"]]
    lines[1], lines[3] = lines[3], lines[1]
    content["paper"]["intro_lines"] = lines
    issues = cs.errors(cs.validate(content))
    assert "paper.intro_lines" in paths(issues)
