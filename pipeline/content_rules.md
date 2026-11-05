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

## 9. Quote-band budget (a citation is content, not decoration)

The quote band sits between the y=556 hairline and the footer: label at y=582,
first quote line at y=608, leading 28 px, **at most 3 lines** (552 px column) —
and 3 lines in the 376 px note column of a table page. Everything that fits is
rendered in full; nothing is clipped to one line with an ellipsis.

- `content_schema.py` measures each quote with the renderer's own width model
  and raises an **error** when it needs a 4th line. The fix is always to pick a
  shorter *complete* sentence (or clause), never to let the page show a
  truncated citation. Quotes are verbatim: trim by choosing a shorter span, not
  by rewriting words.
- `reading_point` is a one-line panel title and is validated the same way — a
  title that needs wrapping is an error, not something to shave.
- On a machine without ppt-master only the approximate width model exists, so
  these two checks downgrade to warnings (CI must not block a deck on a model
  the renderer will not use). Verify on a real install before delivery.
- The build log carries `[truncated] N`; N must be 0. A non-zero N means the
  page shows less than `content.json` says — fix the data, do not ship it.

## 10. Introduction is a fixed five-line analysis (not a summary)

Every single-paper deck carries the same five gold labels, in this order:

| # | label | what goes in it |
|---|---|---|
| 1 | 背景与研究现状 | the field's state of the art, with the numbers that make the gap felt |
| 2 | 提出问题 | what the field still cannot answer, stated as a question |
| 3 | 别人的相关工作及问题 | the existing routes and **why each falls short** (not a citation list) |
| 4 | 启发与希望 | the insight that makes a different approach plausible |
| 5 | 本文研究如何展开 | the paper's actual route: evidence chain, controls, transferability |

- The labels and their order are validated at step 0 (`content_schema.INTRO_ROUTE`):
  five entries, exact labels, exact order. Missing a line, renaming it, or merging
  two into "本文方案 / 关键证据 / 结论" is an **error**, not a style choice — line 3
  is what makes the paper's gap visible, and line 5 is what the figure pages then
  cash in.
- Budget per line ~70–110 CJK chars; the whole page must stay ≤14 rendered lines
  (full width 1184 px, first-line indent 48 px, leading 36 px, top y=168).
  Size the copy before building: the deck asserts the line count.
