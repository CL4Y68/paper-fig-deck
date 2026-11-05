# -*- coding: utf-8 -*-
"""Tests for the batch driver: manifest parsing, resume, retries, force.

A real batch run takes minutes per paper (gate + export), so these tests inject a
fake runner and only exercise the state machine — that is where a resumable
batch actually breaks.
"""
import json

import pytest

import batch


def _workdirs(tmp_path, names):
    root = tmp_path / "work"
    for name in names:
        d = root / name
        d.mkdir(parents=True)
        (d / "content.json").write_text("{}", encoding="utf-8")
    return root


def _manifest(tmp_path, papers, **extra):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"batch": "test", "papers": papers, **extra},
                               ensure_ascii=False), encoding="utf-8")
    return path


def _fake_pptx(tmp_path, name):
    f = tmp_path / "out" / f"{name}.pptx"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(b"pptx")
    return str(f)


def _ok(tmp_path, entry):
    return batch.Result(True, "VERIFY slides=10 notes=10 overflow=0",
                        _fake_pptx(tmp_path, entry.workdir.name))


def test_batch_builds_everything_then_resumes_without_rebuilding(tmp_path, capsys):
    _workdirs(tmp_path, ["a", "b", "c"])
    man = _manifest(tmp_path, [{"workdir": "work/a"}, {"workdir": "work/b"},
                               {"workdir": "work/c"}])
    calls = []

    def runner(entry, **_kw):
        calls.append(entry.key)
        return _ok(tmp_path, entry)

    assert batch.main([str(man)], runner=runner) == 0
    assert calls == ["work/a", "work/b", "work/c"]
    state = json.loads((tmp_path / "batch_state.json").read_text(encoding="utf-8"))
    assert {r["status"] for r in state["papers"].values()} == {"done"}

    calls.clear()
    assert batch.main([str(man)], runner=runner) == 0
    assert calls == [], "a finished paper must not be rebuilt on a re-run"
    assert "skipped" in capsys.readouterr().out


def test_a_failed_paper_is_retried_while_done_ones_are_skipped(tmp_path):
    _workdirs(tmp_path, ["a", "b"])
    man = _manifest(tmp_path, [{"workdir": "work/a"}, {"workdir": "work/b"}])
    plan = {
        "work/a": [batch.Result(False, error="gate blocking=2")],
        "work/b": [batch.Result(True, "VERIFY slides=4 notes=4 overflow=0",
                                _fake_pptx(tmp_path, "b"))],
    }
    calls = []

    def runner(entry, **_kw):
        calls.append(entry.key)
        if not plan[entry.key]:
            raise AssertionError(f"unexpected rebuild of {entry.key}")
        return plan[entry.key].pop(0)

    assert batch.main([str(man)], runner=runner) == 1
    state = json.loads((tmp_path / "batch_state.json").read_text(encoding="utf-8"))
    assert state["papers"]["work/a"]["status"] == "failed"
    assert "blocking" in state["papers"]["work/a"]["error"]
    assert state["papers"]["work/b"]["status"] == "done"

    # fix the data, re-run: only the failed paper is attempted
    plan["work/a"].append(_ok(tmp_path, batch.Entry("work/a", tmp_path / "work" / "a", None, None)))
    calls.clear()
    assert batch.main([str(man)], runner=runner) == 0
    assert calls == ["work/a"]


def test_retries_give_a_failing_paper_more_attempts(tmp_path):
    _workdirs(tmp_path, ["a"])
    man = _manifest(tmp_path, [{"workdir": "work/a"}])
    results = [batch.Result(False, error="first failure"),
               batch.Result(False, error="second failure")]

    def runner(entry, **_kw):
        return results.pop(0) if results else batch.Result(
            True, "VERIFY slides=1 notes=1 overflow=0", _fake_pptx(tmp_path, "a"))

    assert batch.main([str(man), "--retries", "2"], runner=runner) == 0
    state = json.loads((tmp_path / "batch_state.json").read_text(encoding="utf-8"))
    assert state["papers"]["work/a"]["attempts"] == 3


def test_force_rebuilds_finished_papers(tmp_path):
    _workdirs(tmp_path, ["a"])
    man = _manifest(tmp_path, [{"workdir": "work/a"}])
    calls = []

    def runner(entry, **_kw):
        calls.append(entry.key)
        return _ok(tmp_path, entry)

    assert batch.main([str(man)], runner=runner) == 0
    calls.clear()
    assert batch.main([str(man), "--force"], runner=runner) == 0
    assert calls == ["work/a"]


def test_a_deleted_delivery_is_rebuilt(tmp_path):
    _workdirs(tmp_path, ["a"])
    man = _manifest(tmp_path, [{"workdir": "work/a"}])
    calls = []

    def runner(entry, **_kw):
        calls.append(entry.key)
        return _ok(tmp_path, entry)

    assert batch.main([str(man)], runner=runner) == 0
    state = json.loads((tmp_path / "batch_state.json").read_text(encoding="utf-8"))
    import os
    os.remove(state["papers"]["work/a"]["pptx"])

    calls.clear()
    assert batch.main([str(man)], runner=runner) == 0
    assert calls == ["work/a"], "a done record whose PPTX vanished is not finished"


def test_only_limits_the_run_and_its_state(tmp_path):
    _workdirs(tmp_path, ["a", "b"])
    man = _manifest(tmp_path, [{"workdir": "work/a"}, {"workdir": "work/b"}])
    calls = []

    def runner(entry, **_kw):
        calls.append(entry.key)
        return _ok(tmp_path, entry)

    assert batch.main([str(man), "--only", "work/b"], runner=runner) == 0
    assert calls == ["work/b"]
    state = json.loads((tmp_path / "batch_state.json").read_text(encoding="utf-8"))
    assert set(state["papers"]) == {"work/b"}


def test_manifest_rejects_two_workdirs_with_the_same_name(tmp_path):
    (tmp_path / "x").mkdir()
    (tmp_path / "y").mkdir()
    for parent in ("x", "y"):
        d = tmp_path / parent / "same"
        d.mkdir()
        (d / "content.json").write_text("{}", encoding="utf-8")
    man = _manifest(tmp_path, [{"workdir": "x/same"}, {"workdir": "y/same"}])
    with pytest.raises(SystemExit) as exc:
        batch.load_manifest(man)
    assert "share the directory name" in str(exc.value)


def test_manifest_rejects_a_workdir_without_content_json(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    man = _manifest(tmp_path, [{"workdir": "empty"}])
    with pytest.raises(SystemExit) as exc:
        batch.load_manifest(man)
    assert "content.json" in str(exc.value)


def test_corrupt_state_starts_fresh_instead_of_crashing(tmp_path, capsys):
    _workdirs(tmp_path, ["a"])
    man = _manifest(tmp_path, [{"workdir": "work/a"}])
    (tmp_path / "batch_state.json").write_text("{not json", encoding="utf-8")

    def runner(entry, **_kw):
        return _ok(tmp_path, entry)

    assert batch.main([str(man)], runner=runner) == 0
    assert "unreadable" in capsys.readouterr().out


def test_entries_dropped_from_the_manifest_keep_their_history(tmp_path, capsys):
    _workdirs(tmp_path, ["a", "b"])
    man = _manifest(tmp_path, [{"workdir": "work/a"}, {"workdir": "work/b"}])

    def runner(entry, **_kw):
        return _ok(tmp_path, entry)

    assert batch.main([str(man)], runner=runner) == 0
    _manifest(tmp_path, [{"workdir": "work/a"}])      # b removed
    assert batch.main([str(man)], runner=runner) == 0
    state = json.loads((tmp_path / "batch_state.json").read_text(encoding="utf-8"))
    assert "work/b" in state["papers"], "history must not be silently deleted"
    assert "not in the manifest" in capsys.readouterr().out


def test_verification_must_report_zero_overflow():
    """A run that exits 0 but reports overflow is a failure, not a delivery."""
    import subprocess

    class Fake:
        returncode = 0
        stdout = "ran fine\n[8/9] VERIFY slides=10 notes=10 overflow=2\n"
        stderr = ""

    original = subprocess.run
    subprocess.run = lambda *a, **k: Fake()
    try:
        entry = batch.Entry("k", __import__("pathlib").Path("."), None, None)
        result = batch.run_subprocess(entry)
    finally:
        subprocess.run = original
    assert not result.ok
    assert "overflow=2" in result.error


def test_pptx_path_falls_back_to_step_7(monkeypatch):
    """Without --desktop-dir there is no step-9 'copied to' line; the step-7
    'post-processed ->' path is the delivery."""
    import subprocess

    class Fake:
        returncode = 0
        stdout = ("[7/9] post-processed -> C:/out/alpha_逐图精讲.pptx\n"
                  "[8/9] VERIFY slides=10 notes=10 overflow=0\n")
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: Fake())
    entry = batch.Entry("k", __import__("pathlib").Path("."), None, None)
    result = batch.run_subprocess(entry)
    assert result.ok
    assert result.pptx and result.pptx.endswith("alpha_逐图精讲.pptx")


def test_step_9_copy_wins_over_step_7(monkeypatch):
    import subprocess

    class Fake:
        returncode = 0
        stdout = ("[7/9] post-processed -> C:/out/alpha.pptx\n"
                  "[8/9] VERIFY slides=1 notes=1 overflow=0\n"
                  "[9/9] copied to C:/Desktop/alpha.pptx\n")
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: Fake())
    entry = batch.Entry("k", __import__("pathlib").Path("."), None, None)
    assert batch.run_subprocess(entry).pptx == "C:/Desktop/alpha.pptx"


def test_editing_content_json_invalidates_a_finished_build(tmp_path):
    """A `done` record must not hide an edited paper behind an old delivery."""
    _workdirs(tmp_path, ["a"])
    man = _manifest(tmp_path, [{"workdir": "work/a"}])
    calls = []

    def runner(entry, **_kw):
        calls.append(entry.key)
        return _ok(tmp_path, entry)

    assert batch.main([str(man)], runner=runner) == 0
    calls.clear()
    assert batch.main([str(man)], runner=runner) == 0
    assert calls == []

    (tmp_path / "work" / "a" / "content.json").write_text('{"paper": {}}', encoding="utf-8")
    calls.clear()
    assert batch.main([str(man)], runner=runner) == 0
    assert calls == ["work/a"], "an edited content.json must trigger a rebuild"


def test_content_sig_changes_with_the_bytes(tmp_path):
    _workdirs(tmp_path, ["a"])
    wd = tmp_path / "work" / "a"
    first = batch.content_sig(wd)
    (wd / "content.json").write_text('{"x": 1}', encoding="utf-8")
    assert batch.content_sig(wd) != first
    assert batch.content_sig(tmp_path / "missing") == ""
