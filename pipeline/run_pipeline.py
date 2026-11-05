# -*- coding: utf-8 -*-
"""One-command pipeline for one paper workdir.

Usage:
    <venv-python> run_pipeline.py <workdir> [--name NAME] [--desktop-dir DIR]
                                  [--project-dir DIR] [--no-export] [--dry-run]
                                  [--skip-validate]

The backend scripts root is located in this order:
  1. $PPTMASTER_DIR (explicit override; must contain scripts/svg_quality_checker.py)
  2. the shared discovery list in kit.py — $SKILL_SCRIPTS_DIR, hermes profile
     skills dirs, and the usual `~/ppt-master`-style install locations

Backend: PPT Master (MIT, https://github.com/hugohe3/ppt-master) is the
recommended toolchain; $PPTMASTER_DIR may point at any equivalent scripts root
that provides the same script names.

Steps (the ordering footguns used to be tribal knowledge):
  0. validate content.json (content_schema) and fail fast, naming the bad field
  1. project lookup via content.json[paper][ppt_project]; auto-init
     (project_manager.py) when the dated project dir is gone, and write the
     fresh path back into content.json — unless that file is tracked by git,
     in which case the writeback is skipped so no local path enters the repo
  2. rm notes/*.md BEFORE total_md_split (its 1:1 check counts stale orphans)
  3. gen_all -> gen_notes -> total_md_split -> compact styles -> compact coords
  4. native-table projects (any kind=="table" figure spec) get
     stamp_native_fallbacks --write AFTER compact and BEFORE the gate
  5. gate: svg_quality_checker --quick-generate --canonical-authoring --stage final
     --json; the report lives at validation/svg_quality_report.json (NOT stdout);
     abort on blocking>0
  6. export: svg_to_pptx --quick-generate --with-notes --reflow-text
     [--native-charts-and-tables]; the fresh export path comes from `ls -t
     exports/*.pptx`, never from parsing stdout (the exporter prints backslash
     Windows paths that grep mangles)
  7. postproc_justify SRC OUT page_roles.json (cx / algn=just / first-line indent)
  8. verify: slide count == note count, 0 shapes off-slide, <a:tbl> count, media
  9. optional delivery copy (e.g. Desktop) with a busy-file warning

--dry-run stops after step 3 using the approximate width model and a throwaway
project dir: it proves the content and the generator work, but the deck is NOT
deliverable.
"""
from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import zipfile

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))

import content_schema  # noqa: E402
import kit  # noqa: E402
from deck import Deck, load_content  # noqa: E402

PY = sys.executable          # must be a venv python with requirements.txt installed


# --------------------------------------------------------------- environment
def find_scripts_dir() -> pathlib.Path:
    """The ppt-master scripts/ dir.

    Both layouts resolve: an older install keeps `<root>/scripts/`, current
    releases nest it under `<root>/skills/ppt-master/scripts/`.
    """
    env = os.environ.get("PPTMASTER_DIR")
    if env:
        found = kit.resolve_scripts_dir(pathlib.Path(env))
        if found:
            return found
        raise SystemExit(
            f"PPTMASTER_DIR={env} has no scripts/svg_quality_checker.py "
            "(looked at <dir>/scripts and <dir>/skills/ppt-master/scripts). "
            "Point it at the cloned repository root: git clone "
            "https://github.com/hugohe3/ppt-master")
    for scripts in kit._candidate_script_dirs():
        if (scripts / "svg_quality_checker.py").exists():
            return scripts
    raise SystemExit(
        "ppt-master scripts dir not found. Set PPTMASTER_DIR to the cloned "
        "repository root (git clone https://github.com/hugohe3/ppt-master).")


# ------------------------------------------------------------------- helpers
def run(cmd, *, quiet: bool = False) -> subprocess.CompletedProcess:
    """Run a step; on failure print the tail of its output instead of swallowing it."""
    cmd = [str(c) for c in cmd]
    print("$", " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if not quiet and r.stdout.strip():
        print(_tail(r.stdout))
    if r.returncode != 0:
        if r.stderr.strip():
            print("[stderr]", _tail(r.stderr))
        raise SystemExit(f"step failed (exit {r.returncode}): {cmd[1:3]}")
    return r


def _tail(text: str, n: int = 3000) -> str:
    text = text.rstrip()
    return text if len(text) <= n else "…\n" + text[-n:]


def has_native_tables(content: dict) -> bool:
    return any(f.get("kind") == "table" for f in content.get("figures", []))


def _init_project_paths(scripts: pathlib.Path, prefix: str, name: str) -> list[str]:
    """Every place ppt-master may have put the new project, most likely first.

    `scripts` is the scripts/ dir, so `<scripts>.parent` is the skill root (old
    layout) or `<repo>/skills/ppt-master` (current layout) and the repo/projects
    dir sits up to three levels above it.
    """
    roots = [scripts.parent, scripts.parent.parent, scripts.parent.parent.parent,
             pathlib.Path.cwd()]
    candidates = [root / "projects" for root in roots]
    out = []
    for root in candidates:
        if root.is_dir():
            out += glob.glob(str(root / f"{prefix}-{name}_ppt169_*"))
    return out


def _is_version_controlled(path: pathlib.Path) -> bool:
    """True when `path` is tracked by a git repo (e.g. the bundled sample).

    Writing the absolute project path back into a tracked content.json would be
    a leak: a machine-specific path (and a whole-file reformat) lands in the
    commit, and the deck then points at a directory that only exists on the
    machine that built it. Untracked per-paper workdirs still get the writeback.
    """
    try:
        r = subprocess.run(["git", "-C", str(path.parent), "ls-files",
                            "--error-unmatch", path.name],
                           capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0


def _today_project(scripts: pathlib.Path, prefix: str, name: str,
                   tag: str) -> pathlib.Path | None:
    """Today's project for this workdir, when one already exists.

    A tracked content.json never caches the path (_is_version_controlled), so a
    second run on the same day would otherwise die on project_manager's name
    clash instead of regenerating into the directory it already built.
    """
    want = f"{prefix}-{name}_ppt169_{tag}"
    hits = [pathlib.Path(p) for p in _init_project_paths(scripts, prefix, name)]
    hits = [p for p in hits if p.name.startswith(want) and (p / "svg_output").is_dir()]
    if not hits:
        return None
    return max(hits, key=lambda p: p.stat().st_mtime)


def _store_project(content_path: pathlib.Path, content: dict, proj: pathlib.Path) -> None:
    """Cache the project path in the workdir - never in a version-controlled file."""
    content["paper"]["ppt_project"] = str(proj)
    if _is_version_controlled(content_path):
        print("  content.json is tracked by git: ppt_project writeback skipped "
              f"(kept the repo free of local paths); project for this run = {proj}")
        return
    content_path.write_text(json.dumps(content, ensure_ascii=False, indent=1),
                            encoding="utf-8")


def ensure_project(content_path: pathlib.Path, wd: pathlib.Path,
                   scripts: pathlib.Path) -> pathlib.Path:
    """Return the project dir, re-initialising it when the stored path is gone."""
    content = json.loads(content_path.read_text(encoding="utf-8"))
    stored = content["paper"].get("ppt_project", "")
    pdir = pathlib.Path(stored) if stored else None
    if pdir and pdir.is_dir() and (pdir / "svg_output").exists():
        return pdir

    prefix = content["paper"].get("project_prefix", "figdeck")
    tag = datetime.date.today().strftime("%Y%m%d")
    proj = _today_project(scripts, prefix, wd.name, tag)
    if proj is not None:
        print(f"  reusing today's project for this workdir: {proj}")
    else:
        r = run([PY, scripts / "project_manager.py", "init",
                 f"{prefix}-{wd.name}_ppt169_{tag}", "--format", "ppt169",
                 "--quick-generate"], quiet=True)

        # The project root is install-dependent (ppt-master derives it from its
        # own module path), so trust the path the tool prints, then scan.
        for line in r.stdout.splitlines():
            if line.startswith("Project created:"):
                candidate = pathlib.Path(line.split(":", 1)[1].strip())
                if candidate.is_dir():
                    proj = candidate
                    break
        if proj is None:
            found = _init_project_paths(scripts, prefix, wd.name)
            if not found:
                raise SystemExit(
                    "project_manager init did not create a project dir; looked "
                    f"under {[str(p) for p in (scripts.parent, scripts.parent.parent)]}")
            proj = pathlib.Path(max(found, key=lambda p: pathlib.Path(p).stat().st_mtime))

    _store_project(content_path, content, proj)
    return proj


def verify_pptx(path: pathlib.Path) -> dict:
    """Slide/notes/overflow/native-table/media audit of a built deck."""
    from pptx import Presentation

    prs = Presentation(str(path))
    W, H = prs.slide_width, prs.slide_height
    stats = {"slides": 0, "notes": 0, "overflow": 0}

    def walk(shapes):
        for shape in shapes:
            try:
                left, top, width, height = shape.left, shape.top, shape.width, shape.height
            except Exception:
                continue
            if left is None:
                continue
            if left < -1 or top < -1 or left + width > W + 1 or top + height > H + 1:
                stats["overflow"] += 1
            if shape.shape_type == 6:            # group
                walk(shape.shapes)

    for slide in prs.slides:
        stats["slides"] += 1
        walk(slide.shapes)
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame.text.strip():
            stats["notes"] += 1

    with zipfile.ZipFile(str(path)) as z:
        stats["native_tbl"] = sum(
            len(re.findall(r"<a:tbl>", z.read(name).decode("utf-8", "ignore")))
            for name in z.namelist() if name.startswith("ppt/slides/"))
        stats["media"] = len([n for n in z.namelist() if n.startswith("ppt/media/")])
    return stats


def validate_content(content: dict, *, stage: str) -> list[str]:
    """Print validator findings; return the error messages (empty == go)."""
    issues = content_schema.validate(content, stage=stage)
    if issues:
        print(content_schema.format_issues(issues))
        print(f"validation: {len(content_schema.errors(issues))} error(s), "
              f"{len(issues) - len(content_schema.errors(issues))} warning(s)")
    return [i.message for i in content_schema.errors(issues)]


# ---------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Build one paper's figure-by-figure PPTX end to end.")
    ap.add_argument("workdir", help="directory containing content.json")
    ap.add_argument("--name", help="delivery file basename (default: <workdir>)")
    ap.add_argument("--desktop-dir", help="copy the delivery PPTX here when done")
    ap.add_argument("--project-dir", help="override paper.ppt_project")
    ap.add_argument("--no-export", action="store_true", help="stop after the gate")
    ap.add_argument("--dry-run", action="store_true",
                    help="validate + generate SVGs/notes with the approximate model, "
                         "then stop (not deliverable)")
    ap.add_argument("--skip-validate", action="store_true",
                    help="skip the step-0 content.json validation")
    args = ap.parse_args(argv)

    wd = pathlib.Path(args.workdir).resolve()
    content_path = wd / "content.json"
    if not content_path.exists():
        raise SystemExit(f"no content.json in {wd}")
    content = load_content(wd)

    # 0) fail fast on a malformed content.json ------------------------------
    # stage="authoring": paper.ppt_project is filled in below by ensure_project,
    # so requiring it here would be a chicken-and-egg failure.
    if not args.skip_validate:
        errors = validate_content(content, stage="authoring")
        if errors:
            raise SystemExit(f"content.json has {len(errors)} error(s) - fix before building")
    else:
        print("[skip] step 0 validation disabled")

    if args.dry_run:
        proj = pathlib.Path(args.project_dir) if args.project_dir else wd / ".dryrun"
        deck = Deck(content, allow_approx=True)
        slugs = deck.write(proj)
        print(f"[dry-run] {len(slugs)} SVGs -> {proj / 'svg_output'}")
        run([PY, HERE / "gen_notes.py", wd, "--dry-run", "--project-dir", proj])
        print("[dry-run] OK — content and generator agree. This deck is NOT deliverable:\n"
              "           the approximate width model was used and no gate/export ran.")
        return 0

    SK = find_scripts_dir()
    native = has_native_tables(content)

    # 1) project ------------------------------------------------------------
    if args.project_dir:
        proj = pathlib.Path(args.project_dir)
    else:
        proj = ensure_project(content_path, wd, SK)
    print(f"[1/9] project -> {proj}")

    # 2) notes hygiene ------------------------------------------------------
    stale = glob.glob(str(proj / "notes" / "*.md"))
    for f in stale:
        pathlib.Path(f).unlink()
    print(f"[2/9] cleared {len(stale)} stale note file(s)")

    # 2b) images: crops from figures.json, or already-named files in images/
    if (wd / "figures.json").exists():
        run([PY, HERE / "prep_images.py", wd, proj], quiet=True)
        print("[2/9] figure crops staged from figures.json")
    elif (wd / "images").is_dir():
        run([PY, HERE / "prep_images.py", wd, proj, "--from-dir"], quiet=True)
        print("[2/9] images staged from workdir/images")
    else:
        print("[2/9] WARNING: no figures.json and no images/ - the deck will "
              "reference missing figures unless the project images/ dir is populated")

    # 3) generate -----------------------------------------------------------
    gen = run([PY, HERE / "gen_all.py", wd, "--project-dir", proj])
    if "[truncated] 0" not in gen.stdout:
        print("  WARNING: a rendered field lost text — see the [truncated] lines above")
    run([PY, HERE / "gen_notes.py", wd, "--project-dir", proj])
    run([PY, SK / "total_md_split.py", proj])
    run([PY, SK / "compact_svg_styles.py", proj / "svg_output", "--inplace"])
    run([PY, SK / "compact_svg_coordinates.py", proj / "svg_output",
         "--inplace", "--keep-native-frames"])

    # 4) native-table fallback binding (AFTER compact rewrites the SVGs) ----
    if native:
        run([PY, SK / "stamp_native_fallbacks.py", proj / "svg_output", "--write"])
        print("[4/9] native table markers bound")
    else:
        print("[4/9] no table specs - skipped")

    # 5) gate (the checker exits non-zero on blocking; read the report) -----
    subprocess.run([str(c) for c in [PY, SK / "svg_quality_checker.py", proj,
                                     "--quick-generate", "--canonical-authoring",
                                     "--stage", "final", "--json"]],
                   capture_output=True)
    report_path = proj / "validation" / "svg_quality_report.json"
    if not report_path.exists():
        raise SystemExit(f"gate produced no report at {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    blocking = report["categories"]["blocking"].get("issues", [])
    if blocking:
        for issue in blocking[:10]:
            print("  BLOCKING:", issue.get("file"), "|", (issue.get("message") or "")[:120])
        more = f" (+{len(blocking) - 10} more)" if len(blocking) > 10 else ""
        raise SystemExit(f"gate blocking={len(blocking)}{more} - fix before exporting")
    warn_issues = [i for cat in ("introduced", "inherited")
                   for i in report["categories"].get(cat, {}).get("issues", [])]
    n_warn = report["summary"].get("warnings", len(warn_issues))
    if warn_issues:
        # "clean" is a claim, not a label: only say it when nothing is flagged.
        print(f"[5/9] gate passed with {n_warn} warning(s) — read them before delivery:")
        for issue in warn_issues[:8]:
            print(f"   {issue.get('file')}: {(issue.get('message') or '')[:150]}")
        if len(warn_issues) > 8:
            print(f"   (+{len(warn_issues) - 8} more in validation/svg_quality_report.json)")
    else:
        print(f"[5/9] gate clean (blocking=0, warnings={n_warn})")
    if args.no_export:
        print("--no-export: stopping after the gate")
        return 0

    # 6) export -------------------------------------------------------------
    flags = ["--quick-generate", "--with-notes", "--reflow-text"]
    if native:
        flags.append("--native-charts-and-tables")
    run([PY, SK / "svg_to_pptx.py", proj, *flags], quiet=True)
    exports = glob.glob(str(proj / "exports" / "*.pptx"))
    if not exports:
        raise SystemExit("no export found in exports/")
    src = pathlib.Path(max(exports, key=lambda p: pathlib.Path(p).stat().st_mtime))
    out = wd.parent / "output" / f"{args.name or wd.name}_逐图精讲.pptx"
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"[6/9] exported -> {src.name}")

    # 7) postproc -----------------------------------------------------------
    run([PY, HERE / "postproc_justify.py", src, out, wd / "page_roles.json"])
    print(f"[7/9] post-processed -> {out}")

    # 8) verify -------------------------------------------------------------
    stats = verify_pptx(out)
    print(f"[8/9] VERIFY slides={stats['slides']} notes={stats['notes']} "
          f"overflow={stats['overflow']} native_tbl={stats['native_tbl']} "
          f"media={stats['media']}")
    assert stats["notes"] == stats["slides"], "notes/slide mismatch"
    assert stats["overflow"] == 0, f"{stats['overflow']} shapes off-slide"
    if native:
        assert stats["native_tbl"] > 0, "native tables requested but no <a:tbl> in PPTX"

    # 9) delivery -----------------------------------------------------------
    if args.desktop_dir:
        try:
            shutil.copy2(str(out), args.desktop_dir)
            print(f"[9/9] copied to {args.desktop_dir}")
        except PermissionError:
            print(f"[9/9] WARNING: {args.desktop_dir} busy (deck open?) - "
                  f"file stays in {out.parent}")
    else:
        print(f"[9/9] delivery -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
