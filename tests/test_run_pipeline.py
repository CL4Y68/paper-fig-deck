# -*- coding: utf-8 -*-
"""Guards for the driver's content.json writeback.

Step 1 of the pipeline caches the ppt-master project path inside the workdir's
content.json. That is handy for a local per-paper workdir, but a tracked
content.json (the bundled `sample/`) must stay machine-independent: an absolute
path there leaks the builder's layout into a public repo and reformats the file.
"""
import json
import pathlib
import re

import run_pipeline

ROOT = pathlib.Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "sample" / "content.json"


def test_tracked_content_json_is_detected():
    assert run_pipeline._is_version_controlled(SAMPLE) is True


def test_untracked_content_json_is_not_detected(tmp_path):
    stray = tmp_path / "content.json"
    stray.write_text("{}", encoding="utf-8")
    assert run_pipeline._is_version_controlled(stray) is False


def test_missing_file_is_not_detected(tmp_path):
    assert run_pipeline._is_version_controlled(tmp_path / "nope.json") is False


def test_bundled_sample_stays_machine_independent():
    content = json.loads(SAMPLE.read_text(encoding="utf-8"))
    assert "ppt_project" not in content["paper"], (
        "sample/content.json carries a build-time project path; "
        "restore it with `git checkout -- sample/content.json`")
    text = SAMPLE.read_text(encoding="utf-8")
    assert re.search(r"[A-Za-z]:[\\/]", text) is None, (
        "sample/content.json contains an absolute path")


def _fake_install(tmp_path, project_name):
    """A minimal ppt-master layout: <root>/skills/ppt-master + <root>/skills/projects."""
    scripts = tmp_path / "skills" / "ppt-master" / "scripts"
    scripts.mkdir(parents=True)
    proj = tmp_path / "skills" / "projects" / project_name
    (proj / "svg_output").mkdir(parents=True)
    return scripts, proj


def test_today_project_is_reused(tmp_path):
    tag = "20260101"
    scripts, proj = _fake_install(tmp_path, f"figdeck-demo_ppt169_{tag}")
    assert run_pipeline._today_project(scripts, "figdeck", "demo", tag) == proj


def test_today_project_ignores_other_tags_and_workdirs(tmp_path):
    scripts, _ = _fake_install(tmp_path, "figdeck-demo_ppt169_20251231")
    assert run_pipeline._today_project(scripts, "figdeck", "demo", "20260101") is None
    assert run_pipeline._today_project(scripts, "figdeck", "other", "20251231") is None


def test_today_project_requires_generated_svg(tmp_path):
    scripts, proj = _fake_install(tmp_path, "figdeck-demo_ppt169_20260101")
    (proj / "svg_output").rmdir()
    assert run_pipeline._today_project(scripts, "figdeck", "demo", "20260101") is None
