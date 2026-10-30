# pipeline/ — current-generation shared scripts

Snapshot of the shared generator code used by the multi-paper batches
(`pilot/` holds the original frozen pilot snapshot; this folder is the
evolved line: content-driven rosters, five-line Introduction analysis,
measured body-line cap, native-table markers, postproc roles, and the
writer-perspective mainline overview page).

The pipeline is **backend-agnostic**: it emits SVG + notes + content data,
and any PPT toolchain that satisfies the interface contract can consume it
(see the top-level README, "后端工具"). The **recommended** backend is
[PPT Master](https://github.com/hugohe3/ppt-master) (MIT, by Hugo He);
point `$PPTMASTER_DIR` / `$SKILL_SCRIPTS_DIR` at your install.

| file | role |
|---|---|
| `kit.py` | shared layout (24px wrap model, tokenizer, colors, page chrome) |
| `gen_all.py` | stage 3: SVG pages from `content.json` (cover/abstract/intro 5-line/methods/figures/tables/conclusion; body auto-splits at the measured cap) |
| `gen_notes.py` | stage 4: `notes/total.md` lecture scripts (imports the roster from `gen_all`) |
| `postproc_justify.py` | stage 5: PPTX post-processing (restores layout width, `algn=just`, first-line indent) |
| `extract_figures.py` | stage 1: figure/table crops from the source PDF (pymupdf) |
| `prep_images.py` | crops → JPEG ≤900KB into the ppt-master project |
| `run_pipeline.py` | **one-command driver** (9 steps incl. native-table stamp + gate + export + PPTX verify + delivery copy) |
| `measure_lines.py` / `measure_capacity.py` | measure the real PPT body-box line capacity (PowerPoint COM render + pixel scan) — re-run whenever fonts/box/leading change; never pick the line cap by intuition |
| `content_rules.md` | **authoring methodology** (writer-perspective): the claim–evidence mainline, the three argumentative layers, the overview-page schema (`paper.mainline`), optional per-figure `arguing`/`critique`, and the speaker-note templates — how to fill `content.json` so a deck reads as the author's argument |

Run a paper workdir end-to-end:

    <ppt-master-venv-python> pipeline/run_pipeline.py <workdir> --name <DeliveryName> [--desktop-dir <dir>]

Notes:
- `run_pipeline.py` auto-inits the dated ppt-master project when the
  `ppt_project` dir in `content.json` has vanished, and writes the fresh path
  back into `content.json`.
- The measure_* scripts read a local batch workdir (`<batch>/<paper>/content.json`);
  they exist to document the measurement method and to be re-run on demand.
