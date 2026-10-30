# Content authoring rules — writer-perspective edition

Methodology distilled from academic writing pedagogy (generalized; no source
text included). These rules govern how `content.json` is authored so that a
deck reads as **the author's argument, explained figure by figure**, not as
a catalog of results.

## 1. The claim–evidence chain (core principle)

Every figure in the deck must earn its place by answering one question:
**"What does this figure prove?"** The chain of answers, in figure order,
is the paper's argument (the "main line"). A figure that cannot be phrased
as a claim is a data dump — either rewrite its note around the claim it
serves, or drop it from the deck.

- Figure notes (the body paragraph) open with what the figure is meant to
  show, then the evidence in it, then — only if needed — a one-line
  methodological reservation.
- Prefer active, assertive phrasing ("proves", "rules out", "closes the
  loop") over passive description ("shows that … was observed").

## 2. The three argumentative layers

Most papers stack three layers; check each figure against them:

| Layer | Question | Typical evidence figures |
|---|---|---|
| Direct | Did the stated effect actually happen? | spectra, images, numbers with controls |
| Analysis/mechanism | Why does it happen? | in-situ, isotope, DFT/MD, lifetime |
| Theory/design rule | Can it be predicted or transferred? | calculations, parameter sweeps, "only-if" comparisons |

A deck that stops at layer 1 is a report; decks that carry layer 3 are
the ones worth citing. When authoring `content.json`, tag which layer each
figure serves (optional field `layer`: `direct` / `analysis` / `theory`).

## 3. Overview page (new page type)

`paper.mainline` = list of `[ref, claim]` pairs, **one per figure spec, in
figure order**. The pipeline renders a dedicated overview page listing the
whole chain:

```json
"mainline": [
  ["Fig 1", "scheme: <system> design + how it modulates <target property>"],
  ["Fig 2", "reversal: <property> goes <A> -> <B> under <stimulus>, recovers on release"]
]
```
*(illustrative placeholders — replace with the paper's own figures and numbers)*

Rules:
- Keep each claim short (single line on the slide; CJK decks: ~20 chars for
  two-column layouts, ~40 for one). The ref label must mirror the spec order
  (`Fig N` / `Scheme N` / `Table N`).
- The chain must end on the application or the design rule — if the last
  figure is a method detail, the paper's argument does not close.

## 4. Optional figure-level fields (author's voice)

- `arguing` (str, figure level): how this figure is wired into the argument
  — "what would break if this figure were removed".
- `critique` (str, figure level): evidence-strength reservation — missing
  control, single-point data, extrapolation. Written from the reader's seat,
  not the author's.
- Both appear in speaker notes only; the slide layout is unchanged.

## 5. Speaker-note templates (gen_notes)

| Page | Notes |
|---|---|
| cover | structure line + `paper.message` (30-second "what this paper is") |
| abstract | translated abstract + BMFC note (Background→Method→Finding→Conclusion) |
| intro | five-line analysis + "check that background narrows to the specific system" |
| overview | the full main-line chain, one claim per figure |
| figure | 【main line】i/N claim → 【read】what → 【points】body → 【arguing】 → 【critique】 → 【quote】 |
| conclusion | translated conclusion + echo check (does it answer the intro question?) + `paper.takeaway_good` / `paper.if_rebuild` |

`paper.message`, `takeaway_good`, `if_rebuild` are optional one-liners; the
pipeline omits their note lines when absent, so older `content.json` files
still build unchanged.

## 6. Writing-loop self-checks (course-derived, generalized)

- **Echo test**: the conclusion must answer the question posed by the
  intro's "gap" line. If it re-states results instead, it is an abstract
  clone — flag in `takeaway_good`.
- **Control audit**: for every main claim, note which control figure
  protects it; a claim with no control is a `critique` line waiting to be
  written by someone else.
- **Transfer line**: one line on what the result transfers to *your* own
  system (`if_rebuild`) — the deck becomes a reading tool, not just a
  summary.

## 7. Pipeline behavior changes

- `gen_all.py`: `overview_page()` emits the main-line page when
  `paper.mainline` is present (one `<g>` module per claim row; two columns
  when >9 specs). Page count +1; the page is not a body-wrap frame, so
  post-processing (justify/merge) ignores it.
- `gen_notes.py`: emits the note lines above; 【main line】/【arguing】/
  【critique】 are omitted on continuation pages to avoid repetition.
- Nothing here changes the gate: `blocking` must stay 0. The overview page
  uses the proven label-row export pattern (one `<g data-pptx-bounds>` per
  row), so no new PPTX paragraph-flow warnings.

## 8. Body-cap reminder (measured, unchanged)

Body wrap box = 14 lines at 18pt TNR+SimSun, 552 px, hairline at y=556
(4 px clearance at 14 lines; 15 lines overflow to 584 px). `split_body()`
chunks longer bodies into continuation slides automatically.
