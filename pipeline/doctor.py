# -*- coding: utf-8 -*-
"""doctor.py — can this machine actually build a deck?

Every check is either required (a real run cannot proceed without it) or optional
(PowerPoint, font files — nice for fidelity, not needed to generate). The point is
to convert the two classic first-run failures into one readable report instead of
a mid-pipeline traceback:

  1. `pip install -r requirements.txt` half-applied (pywin32 on Linux, no Pillow);
  2. ppt-master cloned somewhere the pipeline does not look.

Usage:  python pipeline/doctor.py [--json]
Exit:   0 = all required checks pass, 1 = at least one required check failed.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import pathlib
import platform
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))

OK, WARN, BAD = "ok", "warn", "fail"
MARK = {OK: "[ok]  ", WARN: "[warn]", BAD: "[fail]"}


class Check:
    def __init__(self, name: str, status: str, detail: str = "", required: bool = True):
        self.name, self.status, self.detail, self.required = name, status, detail, required

    def as_dict(self) -> dict:
        return {"name": self.name, "status": self.status,
                "detail": self.detail, "required": self.required}


def check_python() -> Check:
    v = sys.version_info
    detail = f"{platform.python_version()} ({sys.executable})"
    if v < (3, 10):
        return Check("python>=3.10", BAD, detail + " - too old")
    return Check("python>=3.10", OK, detail)


def check_packages() -> list[Check]:
    out = []
    required = {"pymupdf": "PyMuPDF", "pptx": "python-pptx", "PIL": "Pillow", "lxml": "lxml"}
    for module, package in required.items():
        try:
            importlib.import_module(module)
        except Exception as exc:
            out.append(Check(f"package:{package}", BAD,
                             f"import {module} failed ({exc.__class__.__name__}) - "
                             "pip install -r requirements.txt"))
            continue
        version = ""
        try:
            version = getattr(importlib.import_module(module), "__version__", "")
        except Exception:
            pass
        out.append(Check(f"package:{package}", OK, str(version)))
    # pywin32 + PowerPoint are Windows-only and only needed by measure_*
    if sys.platform == "win32":
        try:
            importlib.import_module("win32com.client")
            out.append(Check("package:pywin32", OK, "PowerPoint COM available",
                             required=False))
        except Exception:
            out.append(Check("package:pywin32", WARN,
                             "not installed - measure_* capacity tests unavailable",
                             required=False))
    return out


PPTMASTER_SCRIPTS = (
    "svg_quality_checker.py", "svg_to_pptx.py", "total_md_split.py",
    "compact_svg_styles.py", "compact_svg_coordinates.py",
    "stamp_native_fallbacks.py", "project_manager.py",
)


def check_backend() -> list[Check]:
    out = []
    try:
        import kit
        status = kit.backend_status()
    except Exception as exc:                    # pragma: no cover - import guard
        return [Check("width-model", BAD, f"import kit failed: {exc}")]

    if status.state == "ppt-master":
        out.append(Check("width-model", OK, f"ppt-master @ {status.scripts_dir}"))
    else:
        out.append(Check("width-model", BAD,
                         status.detail + " -- set PPTMASTER_DIR / SKILL_SCRIPTS_DIR"))

    # find_pptmaster() also accepts $PPTMASTER_DIR pointing at the root
    root = None
    if os.environ.get("PPTMASTER_DIR"):
        root = pathlib.Path(os.environ["PPTMASTER_DIR"])
    elif status.scripts_dir:
        root = pathlib.Path(status.scripts_dir).parent
    if root is None:
        out.append(Check("ppt-master scripts", BAD,
                         "not found - git clone https://github.com/hugohe3/ppt-master"))
        return out
    missing = [name for name in PPTMASTER_SCRIPTS
               if not (root / "scripts" / name).exists()]
    if missing:
        out.append(Check("ppt-master scripts", BAD,
                         f"{root / 'scripts'} is missing {', '.join(missing)}"))
    else:
        out.append(Check("ppt-master scripts", OK, f"{len(PPTMASTER_SCRIPTS)} scripts in "
                                                   f"{root / 'scripts'}"))
    projects = [root.parent / "projects", root.parent.parent / "projects"]
    existing = [p for p in projects if p.is_dir()]
    out.append(Check("project root", OK if existing else WARN,
                     ", ".join(str(p) for p in (existing or projects)), required=False))
    return out


def check_fonts() -> Check:
    """Font FILES, not rendering: the deck asks for Times New Roman + SimSun."""
    if sys.platform == "win32":
        fonts = pathlib.Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        need = {"times.ttf": "Times New Roman", "simsun.ttc": "SimSun"}
        missing = [label for name, label in need.items() if not (fonts / name).exists()]
        if missing:
            return Check("fonts", WARN, f"missing font file(s): {', '.join(missing)}",
                         required=False)
        return Check("fonts", OK, "Times New Roman + SimSun present", required=False)
    return Check("fonts", WARN, "not verifiable off Windows - check the exported deck",
                 required=False)


def check_writable() -> Check:
    try:
        probe = HERE / ".doctor-probe"
        probe.write_text("x", encoding="utf-8")
        probe.unlink()
        return Check("write access", OK, str(HERE))
    except Exception as exc:
        return Check("write access", BAD, f"{HERE}: {exc}")


def run_checks() -> list[Check]:
    checks = [check_python()]
    checks += check_packages()
    checks += check_backend()
    checks.append(check_fonts())
    checks.append(check_writable())
    return checks


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Check this machine's deck-building setup.")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    checks = run_checks()
    if args.json:
        print(json.dumps([c.as_dict() for c in checks], ensure_ascii=False, indent=1))
    else:
        for c in checks:
            optional = "" if c.required else "  (optional)"
            print(f"{MARK[c.status]} {c.name:22} {c.detail}{optional}")
    failed = [c for c in checks if c.required and c.status == BAD]
    if not args.json:
        print()
        print("ready to build" if not failed
              else f"{len(failed)} required check(s) failed - see above")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
