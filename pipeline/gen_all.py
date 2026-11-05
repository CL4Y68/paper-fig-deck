# -*- coding: utf-8 -*-
"""gen_all.py — render one workdir's content.json into SVG pages.

Usage:
    python gen_all.py <workdir> [--project-dir DIR] [--dry-run]

The page roster lives in `deck.py` and the geometry in `layout.py`; this file is
only the CLI. `<workdir>/page_roles.json` (per-slide wrap width, consumed by
postproc_justify) is written alongside.

Backends:
  * normal run  — requires the ppt-master width estimator, i.e. the same model the
    gate uses. That is deliberate: a deck laid out with a different model overflows
    in PowerPoint even though the SVG looked fine.
  * --dry-run   — allows the approximate model and a throwaway project dir
    (`<workdir>/.dryrun`) so the generator can be smoke-tested without ppt-master.
    Never deliver a --dry-run deck.

Page roster (content-driven):
  P01 cover -> P02 abstract -> [intro] -> [overview] -> [methods]
  -> figures/tables in content.json order (a long body auto-splits into （续）)
  -> conclusion.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))

import kit  # noqa: E402
from deck import Deck, load_content, project_dir, write_page_roles  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Generate the SVG pages for one paper workdir.")
    ap.add_argument("workdir", help="directory containing content.json")
    ap.add_argument("--project-dir", metavar="DIR",
                    help="override paper.ppt_project (default: read from content.json)")
    ap.add_argument("--dry-run", action="store_true",
                    help="allow the approximate width model; write to <workdir>/.dryrun")
    args = ap.parse_args(argv)

    wd = pathlib.Path(args.workdir).resolve()
    content = load_content(wd)

    if args.dry_run:
        proj = pathlib.Path(args.project_dir) if args.project_dir else wd / ".dryrun"
    else:
        try:
            kit.require_backend()
        except kit.BackendUnavailable as exc:
            raise SystemExit(
                f"[error] {exc}\n"
                "        Install ppt-master and point PPTMASTER_DIR at it, or pass "
                "--dry-run for an approximate smoke test.") from exc
        proj = (pathlib.Path(args.project_dir) if args.project_dir
                else project_dir(content["paper"]))

    deck = Deck(content, allow_approx=args.dry_run)
    slugs = deck.write(proj)
    roles = write_page_roles(deck, wd, slugs)
    print(f"emitted {len(slugs)} SVGs; TOTAL={deck.total} -> {proj / 'svg_output'}")
    for slug in slugs:
        print(" ", slug)
    print(f"page roles -> {roles}")
    stats = deck.stats()
    if stats["truncated"]:
        print(f"[truncated] {stats['truncated']} rendered field(s) lost text:")
        for loss in stats["losses"]:
            print(f"   {loss['page']} {loss['field']}: -{loss['dropped']} chars")
    else:
        print("[truncated] 0 - every rendered field is complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
