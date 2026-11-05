# -*- coding: utf-8 -*-
"""Tests for the environment self-check (doctor.py).

doctor is the first command a new machine runs, so its report shape and its
exit code are part of the contract: a required failure must exit 1 and name the
thing to fix.
"""
import json
import pathlib

import doctor
import kit


def test_python_version_check_passes():
    check = doctor.check_python()
    assert check.name == "python>=3.10"
    assert check.status == doctor.OK
    assert check.required is True


def test_required_packages_are_importable():
    checks = doctor.check_packages()
    assert checks
    bad = [c for c in checks if c.status == doctor.BAD]
    assert not bad, [c.name for c in bad]


def test_fonts_are_optional_not_blocking():
    check = doctor.check_fonts()
    assert check.status in (doctor.OK, doctor.WARN)
    assert check.required is False


def test_write_access_probe_does_not_leave_a_file():
    check = doctor.check_writable()
    assert check.status == doctor.OK
    assert not (pathlib.Path(doctor.__file__).parent / ".doctor-probe").exists()


def test_missing_backend_is_a_required_failure(monkeypatch):
    monkeypatch.delenv("PPTMASTER_DIR", raising=False)
    monkeypatch.delenv("SKILL_SCRIPTS_DIR", raising=False)
    monkeypatch.setattr(kit, "backend_status",
                        lambda: kit.Backend("approx", None, "no ppt-master here"))
    checks = doctor.check_backend()
    assert checks[0].name == "width-model"
    assert checks[0].status == doctor.BAD
    assert checks[0].required is True
    assert "PPTMASTER_DIR" in checks[0].detail


def test_backend_script_check_names_the_missing_files(monkeypatch, tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "svg_to_pptx.py").write_text("", encoding="utf-8")
    monkeypatch.setenv("PPTMASTER_DIR", str(tmp_path))
    monkeypatch.setattr(kit, "backend_status",
                        lambda: kit.Backend("ppt-master", str(scripts), "resolved"))
    checks = doctor.check_backend()
    named = [c for c in checks if c.name == "ppt-master scripts"][0]
    assert named.status == doctor.BAD
    assert "svg_quality_checker.py" in named.detail


def test_full_report_is_json_and_drives_the_exit_code(capsys):
    rc = doctor.main(["--json"])
    report = json.loads(capsys.readouterr().out)
    assert isinstance(report, list) and report
    for item in report:
        assert {"name", "status", "detail", "required"} <= set(item)
    failed = [i for i in report if i["required"] and i["status"] == doctor.BAD]
    assert rc == (1 if failed else 0)


def test_human_report_lists_every_check(capsys):
    doctor.main([])
    out = capsys.readouterr().out
    assert "[ok]" in out
    assert "ready to build" in out or "required check(s) failed" in out
