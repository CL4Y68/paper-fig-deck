# -*- coding: utf-8 -*-
"""Backend layout compatibility.

ppt-master moved its pipeline scripts from `<repo>/scripts/` to
`<repo>/skills/ppt-master/scripts/`. A fresh clone (what a new machine gets) and
an older skill install must both resolve, or `doctor` fails on exactly the
machine that followed the README.
"""
import pathlib

import doctor
import kit
import run_pipeline

SCRIPTS = ("svg_quality_checker.py", "svg_to_pptx.py", "total_md_split.py",
           "compact_svg_styles.py", "compact_svg_coordinates.py",
           "stamp_native_fallbacks.py", "project_manager.py")


def _fake_scripts(scripts_dir: pathlib.Path) -> pathlib.Path:
    scripts_dir.mkdir(parents=True, exist_ok=True)
    for name in SCRIPTS:
        (scripts_dir / name).write_text("", encoding="utf-8")
    return scripts_dir


def test_old_layout_resolves(tmp_path):
    root = tmp_path / "ppt-master"
    scripts = _fake_scripts(root / "scripts")
    assert kit.resolve_scripts_dir(root) == scripts


def test_new_layout_resolves(tmp_path):
    """Current upstream: <repo>/skills/ppt-master/scripts/."""
    root = tmp_path / "ppt-master"
    scripts = _fake_scripts(root / "skills" / "ppt-master" / "scripts")
    assert kit.resolve_scripts_dir(root) == scripts


def test_scripts_dir_itself_resolves(tmp_path):
    scripts = _fake_scripts(tmp_path / "scripts")
    assert kit.resolve_scripts_dir(scripts) == scripts


def test_unknown_layout_returns_none(tmp_path):
    (tmp_path / "random").mkdir()
    assert kit.resolve_scripts_dir(tmp_path) is None


def test_find_scripts_dir_accepts_the_repo_root(monkeypatch, tmp_path):
    root = tmp_path / "ppt-master"
    scripts = _fake_scripts(root / "skills" / "ppt-master" / "scripts")
    monkeypatch.setenv("PPTMASTER_DIR", str(root))
    assert run_pipeline.find_scripts_dir() == scripts


def test_find_scripts_dir_rejects_a_root_without_scripts(monkeypatch, tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    monkeypatch.setenv("PPTMASTER_DIR", str(root))
    try:
        run_pipeline.find_scripts_dir()
    except SystemExit as exc:
        assert "skills/ppt-master/scripts" in str(exc)
    else:
        raise AssertionError("expected SystemExit for a root without scripts/")


def test_doctor_accepts_the_new_layout(monkeypatch, tmp_path):
    root = tmp_path / "ppt-master"
    scripts = _fake_scripts(root / "skills" / "ppt-master" / "scripts")
    monkeypatch.setenv("PPTMASTER_DIR", str(root))
    monkeypatch.setattr(kit, "backend_status",
                        lambda: kit.Backend("ppt-master", str(scripts), "resolved"))
    checks = doctor.check_backend()
    named = [c for c in checks if c.name == "ppt-master scripts"][0]
    assert named.status == doctor.OK, named.detail


def test_doctor_explains_where_it_looked(monkeypatch, tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    monkeypatch.setenv("PPTMASTER_DIR", str(root))
    monkeypatch.setattr(kit, "backend_status",
                        lambda: kit.Backend("ppt-master", None, "resolved"))
    checks = doctor.check_backend()
    named = [c for c in checks if c.name == "ppt-master scripts"][0]
    assert named.status == doctor.BAD
    assert "skills/ppt-master/scripts" in named.detail


def test_project_roots_cover_the_new_layout(tmp_path):
    """<repo>/projects must be found when scripts live two levels deeper."""
    root = tmp_path / "repo"
    scripts = _fake_scripts(root / "skills" / "ppt-master" / "scripts")
    built = root / "projects" / "figdeck-demo_ppt169_20260101"
    built.mkdir(parents=True)
    found = run_pipeline._init_project_paths(scripts, "figdeck", "demo")
    assert any(pathlib.Path(p) == built for p in found), found
