# -*- coding: utf-8 -*-
"""batch.py — run run_pipeline over many workdirs, resumable.

One paper per run is fine for a single deck; a library of papers needs a driver
that survives an interruption. This is that driver: a manifest lists the
workdirs, a state file records what finished, and a re-run continues where the
last one stopped instead of rebuilding everything.

Usage:
    python batch.py <manifest.json> [--state FILE] [--force] [--retries N]
                    [--only NAME ...] [--no-export] [--dry-run] [--json]

manifest.json:
    {
      "batch": "lit7-2026-11",                  # optional label for reports
      "desktop_dir": "~/Desktop/汇报",           # optional default per paper
      "papers": [
        {"workdir": "lit7/aphen2024", "name": "Aphen2024_Fibers_逐图精讲"},
        {"workdir": "lit7/chen2024"}            # name defaults to the dir name
      ]
    }

State (default `<manifest dir>/batch_state.json`):
    {"batch": ..., "updated": ...,
     "papers": {"lit7/aphen2024": {"name": ..., "status": "done|failed|running",
                                   "attempts": 1, "pptx": "...", "verify": "...",
                                   "error": null, "finished_at": ...}}}

Resume rules:
  * `done` and the recorded PPTX still exists -> skipped (nothing is rebuilt);
  * `failed` / `pending` -> retried (attempts + 1), `--retries N` adds retries;
  * `--force` rebuilds every paper regardless of state;
  * entries removed from the manifest keep their history and are reported as
    "dropped" (their state is never silently deleted).

Why not parallel: each paper owns a project dir, but the backend scripts write
caches inside their own install; serial is the honest default until that is
proven safe. One paper per ~1-2 minutes makes a 10-paper batch a coffee break.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import time
from typing import Callable, NamedTuple

HERE = pathlib.Path(__file__).parent
RUN_PIPELINE = HERE / "run_pipeline.py"

VERIFY_RE = re.compile(r"VERIFY slides=(\d+) notes=(\d+) overflow=(\d+)")
COPY_RE = re.compile(r"copied to (.+)$")      # step 9 (only with --desktop-dir)
POST_RE = re.compile(r"post-processed -> (.+)$")  # step 7, always runs


class Entry(NamedTuple):
    key: str                    # stable id: manifest-relative workdir string
    workdir: pathlib.Path
    name: str | None
    desktop: pathlib.Path | None


class Result(NamedTuple):
    ok: bool
    verify: str = ""
    pptx: str | None = None
    error: str | None = None


# --------------------------------------------------------------------- manifest
def load_manifest(path: pathlib.Path) -> tuple[str, pathlib.Path | None, list[Entry]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"[error] manifest not found: {path}") from None
    except json.JSONDecodeError as exc:
        raise SystemExit(f"[error] manifest is not valid JSON ({path}): {exc}") from None
    if not isinstance(data, dict):
        raise SystemExit("[error] manifest must be a JSON object with a `papers` array")
    papers = data.get("papers")
    if not isinstance(papers, list) or not papers:
        raise SystemExit("[error] manifest needs a non-empty `papers` array")

    base = path.parent
    default_desktop = data.get("desktop_dir")
    if default_desktop:
        default_desktop = pathlib.Path(os.path.expanduser(str(default_desktop)))

    entries: list[Entry] = []
    seen: dict[str, str] = {}
    for i, item in enumerate(papers):
        if not isinstance(item, dict) or not item.get("workdir"):
            raise SystemExit(f"[error] papers[{i}] needs a `workdir`")
        raw = str(item["workdir"])
        wd = pathlib.Path(os.path.expanduser(raw))
        if not wd.is_absolute():
            wd = (base / wd).resolve()
        if not wd.is_dir():
            raise SystemExit(f"[error] papers[{i}].workdir does not exist: {wd}")
        if not (wd / "content.json").is_file():
            raise SystemExit(f"[error] papers[{i}].workdir has no content.json: {wd}")
        desktop = item.get("desktop_dir")
        if desktop:
            desktop = pathlib.Path(os.path.expanduser(str(desktop)))
        entries.append(Entry(key=raw, workdir=wd, name=item.get("name") or None,
                             desktop=desktop or default_desktop))
        # Two workdirs with the same directory name would share one ppt-master
        # project (the driver keys projects on the workdir name) and the second
        # build would overwrite the first one's SVGs.
        if wd.name in seen:
            raise SystemExit(
                f"[error] workdirs {seen[wd.name]!r} and {raw!r} share the directory "
                f"name {wd.name!r}; the backend keys projects on that name — rename "
                "one of them")
        seen[wd.name] = raw

    return str(data.get("batch") or path.stem), default_desktop, entries


# ------------------------------------------------------------------------ state
def load_state(path: pathlib.Path) -> dict:
    if not path.exists():
        return {"papers": {}}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"[warn] state file is unreadable, starting fresh: {path}")
        return {"papers": {}}
    state.setdefault("papers", {})
    return state


def save_state(path: pathlib.Path, state: dict) -> None:
    """Atomic write: a crash mid-save must not lose the whole batch history."""
    state["updated"] = datetime.datetime.now().isoformat(timespec="seconds")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def content_sig(workdir: pathlib.Path) -> str:
    """Fingerprint of the authored data, so an edit invalidates a finished build."""
    try:
        data = (workdir / "content.json").read_bytes()
    except OSError:
        return ""
    return f"{len(data)}:{hashlib.sha256(data).hexdigest()[:16]}"


def is_finished(record: dict, workdir: pathlib.Path | None = None) -> bool:
    """`done` counts only while its PPTX is on disk AND content.json is unchanged.

    Without the fingerprint an edited paper would be silently skipped and the old
    deck would stay on disk — the batch would report "nothing to do" while the
    data had moved on.
    """
    pptx = record.get("pptx")
    if record.get("status") != "done" or not pptx or not pathlib.Path(pptx).exists():
        return False
    if workdir is not None and record.get("content_sig") != content_sig(workdir):
        return False
    return True


# ---------------------------------------------------------------------- runner
def _desktop_arg(entry: Entry) -> list[str]:
    return ["--desktop-dir", str(entry.desktop)] if entry.desktop else []


def run_subprocess(entry: Entry, *, no_export: bool = False,
                   dry_run: bool = False) -> Result:
    """Run one paper in a child process; the parent survives a hard failure."""
    cmd = [sys.executable, str(RUN_PIPELINE), str(entry.workdir)]
    if entry.name:
        cmd += ["--name", entry.name]
    cmd += _desktop_arg(entry)
    if no_export:
        cmd.append("--no-export")
    if dry_run:
        cmd.append("--dry-run")
    proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    out = (proc.stdout or "") + (proc.stderr or "")
    lines = out.splitlines()
    verify = next((ln.strip() for ln in lines if "VERIFY" in ln), "")
    # The delivered PPTX lives at step 7's path; step 9 only exists when a
    # --desktop-dir copy was requested, so it wins when present.
    pptx = None
    for line in lines:
        for rx in (POST_RE, COPY_RE):
            m = rx.search(line)
            if m:
                pptx = m.group(1).strip()
    if dry_run:
        return Result(ok=proc.returncode == 0,
                      error=None if proc.returncode == 0 else _first_error(lines))
    if proc.returncode != 0:
        return Result(ok=False, error=_first_error(lines))
    if not verify or "overflow=0" not in verify:
        bad = verify or "no VERIFY line"
        return Result(ok=False, verify=verify, pptx=pptx,
                      error=f"verification failed: {bad}")
    return Result(ok=True, verify=verify, pptx=pptx)


def _first_error(lines: list[str]) -> str:
    for line in lines:
        low = line.lower()
        if any(tag in low for tag in ("error", "blocking", "failed", "traceback",
                                      "exceed", "required")):
            return line.strip()[:300]
    tail = [ln.strip() for ln in lines if ln.strip()][-3:]
    return " | ".join(tail)[:300] or "no output"


# ------------------------------------------------------------------------ main
def main(argv: list[str] | None = None, *,
         runner: Callable[..., Result] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Run run_pipeline over many workdirs, resumable.")
    ap.add_argument("manifest", help="JSON manifest listing the papers")
    ap.add_argument("--state", help="state file (default: <manifest dir>/batch_state.json)")
    ap.add_argument("--force", action="store_true", help="rebuild even finished papers")
    ap.add_argument("--retries", type=int, default=0,
                    help="extra attempts per paper after the first failure")
    ap.add_argument("--only", nargs="+", metavar="WORKDIR",
                    help="run only these manifest entries (by workdir string)")
    ap.add_argument("--no-export", action="store_true", help="stop after the gate")
    ap.add_argument("--dry-run", action="store_true",
                    help="approximate-model smoke run (not deliverable)")
    ap.add_argument("--json", action="store_true", help="machine-readable summary")
    args = ap.parse_args(argv)

    manifest_path = pathlib.Path(args.manifest).resolve()
    batch_name, _desktop, entries = load_manifest(manifest_path)
    state_path = (pathlib.Path(args.state).resolve() if args.state
                  else manifest_path.parent / "batch_state.json")

    if args.only:
        wanted = set(args.only)
        unknown = wanted - {e.key for e in entries}
        if unknown:
            raise SystemExit(f"[error] --only named entries not in the manifest: "
                             f"{sorted(unknown)}")
        entries = [e for e in entries if e.key in wanted]

    state = load_state(state_path)
    state["batch"] = batch_name
    run = runner or run_subprocess
    started = time.time()

    counts = {"done": 0, "skipped": 0, "failed": 0}
    failures: list[tuple[str, str]] = []

    for i, entry in enumerate(entries, start=1):
        record = state["papers"].get(entry.key, {})
        if not args.force and is_finished(record, entry.workdir):
            counts["skipped"] += 1
            print(f"[{i}/{len(entries)}] {entry.key} — done, skipped "
                  f"({record.get('verify') or 'no verify recorded'})")
            continue

        attempts = int(record.get("attempts", 0))
        result: Result | None = None
        # `--retries N` means N extra attempts IN THIS RUN; a failed paper always
        # gets one fresh attempt on the next invocation.
        for _ in range(max(args.retries, 0) + 1):
            attempts += 1
            print(f"[{i}/{len(entries)}] {entry.key} — building (attempt {attempts})")
            result = run(entry, no_export=args.no_export, dry_run=args.dry_run)
            if result.ok:
                break
            print(f"    ✗ {result.error}")

        verified = result.ok if result else False
        state["papers"][entry.key] = {
            "name": entry.name or entry.workdir.name,
            "status": "done" if verified else "failed",
            "attempts": attempts,
            "pptx": result.pptx if result else None,
            "verify": (result.verify if result else "") or "",
            "error": None if verified else ((result.error if result else "") or "not run"),
            "content_sig": content_sig(entry.workdir),
            "finished_at": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        # Save after EVERY paper: that is what makes an interrupted batch resumable.
        save_state(state_path, state)

        if verified:
            counts["done"] += 1
            print(f"    ✓ {result.verify or 'ok'}")
        else:
            counts["failed"] += 1
            failures.append((entry.key, state["papers"][entry.key]["error"]))

    # entries that vanished from the manifest still carry history
    current = {e.key for e in entries}
    dropped = sorted(set(state["papers"]) - current)

    elapsed = int(time.time() - started)
    summary = {"batch": batch_name, "state": str(state_path),
               "done": counts["done"], "skipped": counts["skipped"],
               "failed": counts["failed"], "dropped": dropped,
               "elapsed_s": elapsed, "failures": failures}
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=1))
    else:
        print(f"\n[batch] {counts['done']} built, {counts['skipped']} skipped, "
              f"{counts['failed']} failed (of {len(entries)}) in {elapsed}s")
        print(f"        state -> {state_path}")
        if failures:
            print("        failures:")
            for key, err in failures:
                print(f"          - {key}: {err}")
            print("        fix the data, then re-run the same command: finished "
                  "papers are skipped.")
        if dropped:
            print(f"        not in the manifest any more (kept in state): "
                  f"{', '.join(dropped)}")
    return 1 if counts["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
