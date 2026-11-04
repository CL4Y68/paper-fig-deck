# legacy/ — frozen snapshots, do not edit

`legacy/pilot/` is the original pilot batch (first working end-to-end deck). It is
kept because the comments in it record how the layout numbers were discovered, and
because it is a useful diff target when something regresses.

**It is not the pipeline.** The current code lives in `pipeline/`, and the two
differ in behaviour (content-driven rosters, measured line cap, native-table
markers, mainline overview page, explicit `Deck` object). Do not fix bugs here,
and do not copy from here — copy from `pipeline/`.

Linting and tests skip this directory on purpose (`pyproject.toml`).
