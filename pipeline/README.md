# pipeline/ — current-generation shared scripts

Snapshot of the shared generator code used by the multi-paper batches. The
pipeline is **backend-agnostic**: it emits SVG + notes + content data, and any PPT
toolchain that satisfies the interface contract can consume it (see the top-level
README, "后端工具"). The **recommended** backend is
[PPT Master](https://github.com/hugohe3/ppt-master) (MIT, by Hugo He); point
`$PPTMASTER_DIR` at your install (or `$SKILL_SCRIPTS_DIR` at its `scripts/`).

## Files

| file | role |
|---|---|
| `layout.py` | **single source of truth** for the 1280×720 geometry: canvas, module bounds, panel box, measured body cap/leading, colors, table geometry, cover geometry |
| `kit.py` | SVG primitives: tokenizer, gate-accurate width estimator (lazy, with an explicit approximate fallback), `wrap` / `wrap_capped` / `truncate1` / `mtext_lines`, page envelope, header/footer chrome |
| `deck.py` | `Deck` object + `build_slides()`: content.json → page roster → SVG pages for cover / abstract / intro 5-line / mainline overview / methods / figures / tables / conclusion (long bodies auto-split) |
| `content_schema.py` | **dependency-free validator** for `content.json` (errors vs warnings, field paths) + the JSON Schema mirror writer |
| `schema/content.schema.json` | generated JSON Schema, for editors and agents (`python content_schema.py --write-json-schema ...`) |
| `gen_all.py` | stage 3 CLI: render every page into `<project>/svg_output` + `page_roles.json` |
| `gen_notes.py` | stage 4 CLI: `notes/total.md` lecture scripts, one H1 per page (roster from the same `Deck`) |
| `run_pipeline.py` | **one-command driver**: validate → project → notes hygiene → images → SVG → notes → split → compact → native-table stamp → gate → export → postproc → verify → delivery |
| `postproc_justify.py` | stage 7: PPTX post-processing (restores layout width, `algn=just`, first-line indent) |
| `prep_images.py` | stage 2b: figure crops from `figures.json` (**or** already-named files in `images/` with `--from-dir`) → JPEG ≤900 KB in the project |
| `extract_figures.py` | stage 1: figure/table crops from the source PDF (pymupdf) |
| `doctor.py` | environment self-check: packages, PPTMASTER_DIR, the 7 required scripts, fonts, write access |
| `measure_lines.py` / `measure_capacity.py` | measure the real PPT body-box line capacity (PowerPoint COM render + pixel scan) — re-run whenever fonts/box/leading change; never pick the line cap by intuition |
| `content_rules.md` | **authoring methodology** (writer-perspective): the claim–evidence mainline, the three argumentative layers, the overview-page schema (`paper.mainline`), optional per-figure `arguing`/`critique`, and the speaker-note templates |

## Run a paper workdir end to end

    <venv-python> pipeline/run_pipeline.py <workdir> --name <DeliveryName> [--desktop-dir <dir>]

Options: `--dry-run` (approximate width model, no gate/export — not deliverable),
`--no-export` (stop after the gate), `--project-dir` (override `paper.ppt_project`),
`--skip-validate` (bypass step 0 — only for debugging the generator itself).

Notes:
- `run_pipeline.py` auto-inits the dated ppt-master project when the
  `ppt_project` dir in `content.json` has vanished, and writes the fresh path back
  into `content.json`. It locates the new dir from the path
  `project_manager.py init` prints, so a non-standard install layout still works.
- Images are staged into `<project>/images/` automatically: crops from
  `figures.json` when present, otherwise every file in `<workdir>/images/`.
- The measure_* scripts read a local batch workdir (`<batch>/<paper>/content.json`);
  they exist to document the measurement method and to be re-run on demand.

## Where the numbers come from

`layout.BODY_MAX = 14` and `layout.BODY_LEAD = 36` are **measured**, not chosen:
`measure_capacity.py` renders 12/13/14/15-line bodies in the exact export geometry
through PowerPoint COM, pixel-scans the ink bottom against the y556 hairline, and
reports the largest N that fits. Re-run it (and update `layout.py`) after changing
the font, the box width, or the leading.
