# -*- coding: utf-8 -*-
"""content_schema.py — dependency-free validator for a workdir's content.json.

Why this exists: every field in `content.json` is consumed by a generator that
indexes it directly (`spec["num"]`, `s["quote_ref"]`, …). Without an up-front
check a typo surfaces as a bare `KeyError` deep inside a 9-step run — or worse,
as a silently blank panel that only the visual QA catches. Validating at step 0
turns that into a one-line message naming the exact field.

Severity model:
  error   — the pipeline cannot build a correct deck from this file
  warning — it will build, but the result is probably not what the author wants
            (over-long body that auto-splits, mainline shorter than figures, …)

The checks mirror `pipeline/gen_all.py` + `pipeline/gen_notes.py` exactly; if
you teach the generator a new field, teach the validator here too.

Usage:
  python content_schema.py <workdir|content.json> [--stage authoring|build]
  python content_schema.py --write-json-schema pipeline/schema/content.schema.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any, NamedTuple

import layout

SCHEMA_VERSION = "2"
SUPPORTED_VERSIONS = ("1", "2")
FIGURE_KINDS = ("figure", "scheme", "table")

PAPER_REQUIRED = (
    "title_zh", "journal", "authors_short", "doi",
    "abstract_zh", "conclusion_zh", "title_page_img",
)
FIGURE_SLIDE_REQUIRED = ("reading_point", "what", "body", "quote", "quote_ref")
TABLE_SLIDE_REQUIRED = ("reading_point", "table_note", "quote", "quote_ref")

# Soft caps: over these the page still builds, but a human should re-read it.
BODY_CHARS_WARN = 1400        # ~4 rendered figure pages at 14 lines x 34 chars
QUOTE_CHARS_WARN = 110        # guidance for the hard line-count cap below
CELL_CHARS_WARN = 24          # a table cell wider than this collides in 730 px
READING_POINT_CHARS_WARN = 14  # the panel title must fit one line (~14 CJK chars)
TABLE_ROWS_MAX = 8            # header + 7 body rows (layout.TABLE_MAX_ROWS)


def _est_lines(text: str, maxw: float) -> tuple[int, bool]:
    """``(line count, exact)`` under the renderer's own width model.

    ``exact=False`` when only the approximate model is available (no ppt-master
    on this machine, e.g. CI): callers downgrade the verdict to a warning,
    because refusing a deck on a model the renderer will not use is a false
    positive.
    """
    try:
        import kit  # sibling module; shares layout.py with deck.py
        exact = kit.backend_status().state == "ppt-master"
        return len(kit.wrap(text, layout.BODY_PX, maxw)), exact
    except Exception:  # pragma: no cover - only when kit cannot load
        em = sum(1.0 if ord(ch) > 0x2E80 else 0.62 for ch in text) * layout.BODY_PX
        return max(1, -(-int(em) // int(maxw))), False


def _too_long(need: int, limit: int, path: str, msg: str, err, warn, exact: bool) -> None:
    """Report an over-long field: error on the real model, warning otherwise."""
    if need <= limit:
        return
    (err if exact else warn)(
        path, msg + ("" if exact else " [approximate width model: verify on a "
                                      "machine with ppt-master installed]"))



class Issue(NamedTuple):
    path: str
    message: str
    severity: str      # "error" | "warning"

    def __str__(self) -> str:
        return f"[{self.severity}] {self.path}: {self.message}"


def _s(value: Any) -> bool:
    """Non-empty string after stripping."""
    return isinstance(value, str) and bool(value.strip())


def _pair(value: Any) -> bool:
    return (isinstance(value, (list, tuple)) and len(value) == 2
            and _s(value[0]) and _s(value[1]))


def _int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def validate(content: Any, *, stage: str = "authoring") -> list[Issue]:
    """Return every problem found, errors first. Empty list == ready to build.

    stage="authoring": the file is being written, `paper.ppt_project` may be absent.
    stage="build":     about to generate; the project pointer must exist.
    """
    issues: list[Issue] = []

    def err(path: str, msg: str) -> None:
        issues.append(Issue(path, msg, "error"))

    def warn(path: str, msg: str) -> None:
        issues.append(Issue(path, msg, "warning"))

    if not isinstance(content, dict):
        err("$", "content.json must be a JSON object")
        return issues

    version = str(content.get("schema_version", "1"))
    if "schema_version" not in content:
        warn("schema_version", f"missing; assuming \"1\" (current is \"{SCHEMA_VERSION}\")")
    elif version not in SUPPORTED_VERSIONS:
        err("schema_version", f"unsupported version {version!r}; "
                              f"supported: {', '.join(SUPPORTED_VERSIONS)}")

    paper = content.get("paper")
    if not isinstance(paper, dict):
        err("paper", "missing required object")
        return issues

    for key in PAPER_REQUIRED:
        if not _s(paper.get(key)):
            err(f"paper.{key}", "required non-empty string")
    if stage == "build" and not _s(paper.get("ppt_project")):
        err("paper.ppt_project", "required at build stage (run_pipeline fills it in)")

    for key in ("title_en", "kicker", "footer", "abstract_src", "conclusion_src",
                "methods_src", "message", "takeaway_good", "if_rebuild",
                "ppt_project", "project_prefix", "keywords_en"):
        if key in paper and not isinstance(paper[key], str):
            err(f"paper.{key}", "must be a string")

    if "intro_lines" in paper:
        lines = paper["intro_lines"]
        if not isinstance(lines, list) or not lines:
            err("paper.intro_lines", "must be a non-empty array of [label, text] pairs")
        else:
            for i, item in enumerate(lines):
                if not _pair(item):
                    err(f"paper.intro_lines[{i}]", "must be [label, text] with both non-empty")
            if len(lines) > 5:
                warn("paper.intro_lines", f"{len(lines)} lines render on one page; "
                                          "the five-line analysis expects <= 5")

    if "mainline" in paper:
        mainline = paper["mainline"]
        if not isinstance(mainline, list) or not mainline:
            err("paper.mainline", "must be a non-empty array of [ref, claim] pairs")
        else:
            for i, item in enumerate(mainline):
                if not _pair(item):
                    err(f"paper.mainline[{i}]", "must be [ref, claim] with both non-empty")
            if len(mainline) > 9 and len(mainline) > 22:
                warn("paper.mainline", "more than 22 rows will not fit the two-column page")

    if "title_crop" in paper:
        tc = paper["title_crop"]
        if not isinstance(tc, dict):
            err("paper.title_crop", "must be an object")
        else:
            if not _s(tc.get("pdf")):
                err("paper.title_crop.pdf", "required absolute path to the source PDF")
            if not _int(tc.get("page")):
                err("paper.title_crop.page", "required 1-based page number")
            rect = tc.get("rect")
            if not (isinstance(rect, list) and len(rect) == 4
                    and all(isinstance(v, (int, float)) for v in rect)):
                err("paper.title_crop.rect", "required [x0, y0, x1, y1] numbers")
            if not _s(tc.get("out")):
                err("paper.title_crop.out", "required output image file name")

    figures = content.get("figures")
    if not isinstance(figures, list) or not figures:
        err("figures", "must be a non-empty array")
        return _sorted(issues)

    for i, fig in enumerate(figures):
        path = f"figures[{i}]"
        if not isinstance(fig, dict):
            err(path, "must be an object")
            continue
        kind = fig.get("kind", "figure")
        if kind not in FIGURE_KINDS:
            err(f"{path}.kind", f"must be one of {', '.join(FIGURE_KINDS)}")
            continue
        if kind == "table":
            _validate_table(fig, path, err, warn)
        else:
            _validate_figure(fig, path, err, warn)

    mainline = paper.get("mainline") if isinstance(paper, dict) else None
    if isinstance(mainline, list) and mainline and len(mainline) != len(figures):
        warn("paper.mainline",
             f"{len(mainline)} claims for {len(figures)} figure specs; "
             "unmatched specs lose their 【主线】 note")

    return _sorted(issues)


def _validate_figure(fig: dict, path: str, err, warn) -> None:
    if not _int(fig.get("num")):
        err(f"{path}.num", "required positive integer (figure number)")
    if "img" in fig and not _s(fig["img"]):
        err(f"{path}.img", "must be a non-empty file name when present")
    slides = fig.get("slides")
    if not isinstance(slides, list) or not slides:
        err(f"{path}.slides", "must be a non-empty array")
        return
    for j, slide in enumerate(slides):
        sp = f"{path}.slides[{j}]"
        if not isinstance(slide, dict):
            err(sp, "must be an object")
            continue
        for key in FIGURE_SLIDE_REQUIRED:
            if not _s(slide.get(key)):
                err(f"{sp}.{key}", "required non-empty string")
        body = slide.get("body")
        if isinstance(body, str) and len(body) > BODY_CHARS_WARN:
            warn(f"{sp}.body", f"{len(body)} chars will auto-split into "
                               f"{-(-len(body) // 400)}+ pages — consider one idea per slide")
        quote = slide.get("quote")
        if isinstance(quote, str) and quote.strip():
            need, exact = _est_lines(quote, layout.PANEL_W_INNER)
            _too_long(need, layout.QUOTE_MAX_LINES, f"{sp}.quote",
                      f"needs {need} lines at {layout.PANEL_W_INNER} px; the quote band "
                      f"shows at most {layout.QUOTE_MAX_LINES} — the page must not clip a "
                      f"citation, so quote a shorter complete sentence "
                      f"(about {QUOTE_CHARS_WARN} chars)", err, warn, exact)
        rp = slide.get("reading_point")
        if isinstance(rp, str) and rp.strip():
            need, exact = _est_lines(rp, layout.PANEL_W_INNER)
            _too_long(need, 1, f"{sp}.reading_point",
                      "the panel title is one line and must not be truncated "
                      f"(~{READING_POINT_CHARS_WARN} CJK chars at {layout.PANEL_W_INNER} px)",
                      err, warn, exact)
        if not _s(slide.get("what")):
            err(f"{sp}.what", "required (one-line reading instruction)")


def _validate_table(fig: dict, path: str, err, warn) -> None:
    slides = fig.get("slides")
    if not isinstance(slides, list) or not slides:
        err(f"{path}.slides", "must be a non-empty array")
        return
    if len(slides) > 1:
        warn(f"{path}.slides", f"{len(slides)} entries; only slides[0] is rendered")
    slide = slides[0]
    if not isinstance(slide, dict):
        err(f"{path}.slides[0]", "must be an object")
        return
    sp = f"{path}.slides[0]"
    for key in TABLE_SLIDE_REQUIRED:
        if not _s(slide.get(key)):
            err(f"{sp}.{key}", "required non-empty string")
    rp = slide.get("reading_point")
    if isinstance(rp, str) and rp.strip():
        need, exact = _est_lines(rp, layout.NOTE_PANEL_W)
        _too_long(need, 1, f"{sp}.reading_point",
                  "the note-column title is one line and must not be truncated "
                  f"(~{READING_POINT_CHARS_WARN} CJK chars at {layout.NOTE_PANEL_W} px)",
                  err, warn, exact)
    quote = slide.get("quote")
    if isinstance(quote, str) and quote.strip():
        need, exact = _est_lines(quote, layout.NOTE_PANEL_W)
        _too_long(need, layout.QUOTE_MAX_LINES, f"{sp}.quote",
                  f"needs {need} lines at {layout.NOTE_PANEL_W} px; the note column shows "
                  f"at most {layout.QUOTE_MAX_LINES} — the page must not clip a citation, "
                  "so quote a shorter complete sentence", err, warn, exact)

    rows = slide.get("table_rows")
    headers = slide.get("headers")
    if not isinstance(rows, list) or not rows:
        err(f"{sp}.table_rows", "must be a non-empty array of rows")
        return
    if headers is not None and (not isinstance(headers, list) or not headers):
        err(f"{sp}.headers", "must be a non-empty array when present")
        return
    ncol = len(headers) if isinstance(headers, list) else len(rows[0])
    if ncol < 1 or ncol > 6:
        err(f"{sp}.headers", f"{ncol} columns will not fit 730 px; use 1-6")
    if len(rows) + 1 > TABLE_ROWS_MAX:
        err(f"{sp}.table_rows", f"{len(rows)} body rows + header exceeds "
                                f"{TABLE_ROWS_MAX} (48 px each)")
    for r, row in enumerate(rows):
        rp = f"{sp}.table_rows[{r}]"
        if not isinstance(row, (list, tuple)):
            err(rp, "must be an array of cell strings")
            continue
        if len(row) != ncol:
            err(rp, f"{len(row)} cells for {ncol} columns")
        for c, cell in enumerate(row):
            if not isinstance(cell, str):
                err(f"{rp}[{c}]", "cell must be a string")
            elif len(cell) > CELL_CHARS_WARN:
                warn(f"{rp}[{c}]", f"{len(cell)} chars in one cell; "
                                   "the column will be clipped")


def _sorted(issues: list[Issue]) -> list[Issue]:
    return sorted(issues, key=lambda i: (i.severity != "error", i.path))


def errors(issues) -> list[Issue]:
    return [i for i in issues if i.severity == "error"]


def format_issues(issues) -> str:
    return "\n".join(f"  {i}" for i in issues)


def load(path: str | pathlib.Path) -> dict:
    p = pathlib.Path(path)
    if p.is_dir():
        p = p / "content.json"
    return json.loads(p.read_text(encoding="utf-8"))


def json_schema() -> dict:
    """A JSON Schema (draft-07 subset) matching this validator, for editors/agents."""
    pair = {"type": "array", "minItems": 2, "maxItems": 2,
            "items": {"type": "string", "minLength": 1}}

    def nonempty_str(desc=""):
        return {"type": "string", "minLength": 1, **({"description": desc} if desc else {})}

    figure_slide = {
        "type": "object",
        "required": list(FIGURE_SLIDE_REQUIRED),
        "properties": {
            "reading_point": nonempty_str("读点题名（右面板标题）"),
            "what": nonempty_str("一句读图指令"),
            "body": nonempty_str("正文段落（自动拆续页）"),
            "quote": nonempty_str("原文引用（逐字摘录；最多 3 行，超长在第 0 步报 error）"),
            "quote_ref": nonempty_str("页码/章节标注"),
        },
        "additionalProperties": True,
    }
    table_slide = {
        "type": "object",
        "required": list(TABLE_SLIDE_REQUIRED) + ["table_rows"],
        "properties": {
            "reading_point": nonempty_str(),
            "table_note": nonempty_str("右栏说明文字"),
            "quote": nonempty_str(),
            "quote_ref": nonempty_str(),
            "headers": {"type": "array", "minItems": 1, "maxItems": 6,
                        "items": {"type": "string"}},
            "table_rows": {
                "type": "array", "minItems": 1, "maxItems": TABLE_ROWS_MAX - 1,
                "items": {"type": "array", "minItems": 1, "maxItems": 6,
                          "items": {"type": "string"}},
            },
        },
        "additionalProperties": True,
    }
    figure = {
        "type": "object",
        "required": ["num", "slides"],
        "properties": {
            "kind": {"enum": list(FIGURE_KINDS)},
            "num": {"type": "integer", "minimum": 1},
            "img": {"type": "string", "minLength": 1},
            "arguing": {"type": "string"},
            "critique": {"type": "string"},
            "slides": {"type": "array", "minItems": 1, "items": figure_slide},
        },
        "additionalProperties": True,
    }
    table = {
        "type": "object",
        "required": ["kind", "slides"],
        "properties": {
            "kind": {"const": "table"},
            "title": {"type": "string"},
            "arguing": {"type": "string"},
            "critique": {"type": "string"},
            "slides": {"type": "array", "minItems": 1, "maxItems": 1,
                       "items": table_slide},
        },
        "additionalProperties": True,
    }
    paper = {
        "type": "object",
        "required": list(PAPER_REQUIRED),
        "properties": {
            "title_zh": nonempty_str(),
            "title_en": {"type": "string"},
            "journal": nonempty_str(),
            "authors_short": nonempty_str(),
            "doi": nonempty_str(),
            "abstract_zh": nonempty_str(),
            "abstract_src": {"type": "string"},
            "conclusion_zh": nonempty_str(),
            "conclusion_src": {"type": "string"},
            "methods_zh": {"type": "string"},
            "methods_src": {"type": "string"},
            "keywords_en": {"type": "string"},
            "kicker": {"type": "string"},
            "footer": {"type": "string"},
            "message": {"type": "string"},
            "takeaway_good": {"type": "string"},
            "if_rebuild": {"type": "string"},
            "project_prefix": {"type": "string"},
            "ppt_project": {"type": "string"},
            "intro_lines": {"type": "array", "minItems": 1, "items": pair},
            "mainline": {"type": "array", "minItems": 1, "items": pair},
            "title_page_img": nonempty_str("封面图文件名（projects images/ 内）"),
            "title_crop": {
                "type": "object",
                "required": ["pdf", "page", "rect", "out"],
                "properties": {
                    "pdf": {"type": "string", "minLength": 1},
                    "page": {"type": "integer", "minimum": 1},
                    "rect": {"type": "array", "minItems": 4, "maxItems": 4,
                             "items": {"type": "number"}},
                    "out": {"type": "string", "minLength": 1},
                    "z": {"type": "number", "exclusiveMinimum": 0},
                },
                "additionalProperties": True,
            },
        },
        "additionalProperties": True,
    }
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "urn:paper-fig-deck:content.schema",
        "title": "paper-fig-deck content.json",
        "description": "Per-paper authoring input for pipeline/gen_all.py. "
                       "Schema version " + SCHEMA_VERSION + ".",
        "type": "object",
        "required": ["paper", "figures"],
        "properties": {
            "schema_version": {"enum": list(SUPPORTED_VERSIONS)},
            "paper": paper,
            "figures": {
                "type": "array", "minItems": 1,
                "items": {"oneOf": [table, figure]},
            },
        },
        "additionalProperties": False,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Validate a workdir's content.json before running the pipeline.")
    ap.add_argument("target", nargs="?", help="workdir or path to content.json")
    ap.add_argument("--stage", choices=("authoring", "build"), default="authoring")
    ap.add_argument("--write-json-schema", metavar="PATH",
                    help="write the JSON Schema mirror and exit")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    if args.write_json_schema:
        out = pathlib.Path(args.write_json_schema)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(json_schema(), ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
        print(f"wrote {out}")
        return 0

    if not args.target:
        ap.error("target is required unless --write-json-schema is given")
    try:
        content = load(args.target)
    except FileNotFoundError:
        print(f"content.json not found under {args.target}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"content.json is not valid JSON: {exc}", file=sys.stderr)
        return 2

    issues = validate(content, stage=args.stage)
    if args.json:
        print(json.dumps([i._asdict() for i in issues], ensure_ascii=False, indent=1))
    elif issues:
        print(format_issues(issues))
    n_err = len(errors(issues))
    print(f"{n_err} error(s), {len(issues) - n_err} warning(s)")
    return 1 if n_err else 0


if __name__ == "__main__":
    raise SystemExit(main())
