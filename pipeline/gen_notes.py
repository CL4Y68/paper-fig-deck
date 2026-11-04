# -*- coding: utf-8 -*-
"""gen_notes.py — emit notes/total.md (one H1 section per SVG slug).

Usage:
    python gen_notes.py <workdir> [--project-dir DIR] [--out PATH] [--dry-run]

The section list comes from `Deck.slug_list()`, i.e. the same roster that produced
the SVGs, so `total_md_split.py` always sees N sections for N pages (that script
hard-fails on a mismatch).

Notes policy (writer-perspective edition):
- cover: 结构说明 + 三十秒读法（paper.message，若填）
- abstract: 中文摘要 + BMFC 结构注（背景→方法→发现→结论）
- intro（五线）→ overview（论证主线逐图 claim，若 mainline）→ methods
- figure page: 【主线】第i/N环 claim（若填）→ 【读图】what → 【要点】body
  → 【论证】arguing（若填）→ 【批判】critique（若填）→ 【原文（ref）】quote；
  续页标注「（接上页）」
- table page: 同上，【要点】= table_note
- conclusion: 中文结论 + 结论回响检查 + 结语两问
"""
from __future__ import annotations

import argparse
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))

from deck import Deck, load_content, project_dir  # noqa: E402


def _structure_line(deck: Deck) -> str:
    paper = deck.paper
    n_fig = sum(1 for s in deck.slides if s["type"] == "fig")
    n_tab = sum(1 for s in deck.slides if s["type"] == "table")
    struct = "原文 title 页 + 中文摘要"
    if paper.get("intro_lines"):
        struct += " + Introduction 五线分析"
    if paper.get("mainline"):
        struct += " + 论证主线（逐图证明点）"
    if paper.get("methods_zh"):
        struct += " + 制备方法"
    struct += (f" + 逐图讲解（{n_fig} 图"
               + (f" + {n_tab} 表" if n_tab else "") + "，长文自动拆续页）")
    return struct + " + 中文结论。"


def cover_notes(deck: Deck) -> list[str]:
    p = deck.paper
    out = [f"本篇为逐图精读：{p.get('authors_short', '作者')}"
           f"（{p.get('journal', '')}）《{p['title_zh']}》。",
           f"DOI: {p['doi']}；关键词（原文）：{p.get('keywords_en', '（原文无）')}。",
           f"结构：{_structure_line(deck)}"]
    if p.get("message"):
        out.append(f"三十秒读法：{p['message']}")
    return out


def abstract_notes(deck: Deck) -> list[str]:
    p = deck.paper
    return ["【中文摘要】" + p["abstract_zh"],
            p.get("abstract_src", "（译自原文 Abstract）") + "；数字与表述与原文一致。",
            "【BMFC 结构注】按背景（B）→ 材料方法（M）→ 发现（F）→ 结论（C）"
            "四要素展开：读时先定位首句的大背景/小背景，再找带数字的发现句，"
            "末句为结论与展望。"]


def intro_notes(deck: Deck) -> list[str]:
    out = [f"【{label}】{text}" for label, text in deck.paper["intro_lines"]]
    out.append("【写作视角】按「起承转合」检验：背景段是否由大背景收敛到具体体系；"
               "问题段是否回答『重要吗、进展到哪步』；本文方案段是否交代『凭什么、"
               "怎么解决』。")
    return out


def overview_notes(deck: Deck) -> list[str]:
    out = ["本文各图按论证主线排列——每张图是论证链上的一环，读图时先问"
           "『这张图证明了什么』，再看它用的证据："]
    out += [f"{ref}：{claim}" for ref, claim in deck.paper["mainline"]]
    return out


def methods_notes(deck: Deck) -> list[str]:
    p = deck.paper
    src = p.get("methods_src")
    return [src] if src else ["【制备方法】" + p["methods_zh"]]


def content_notes(spec: dict) -> list[str]:
    out = []
    if spec.get("claim") and not spec.get("cont"):
        out.append(f"【主线】本文论证第 {spec['ml_index']}/{spec['ml_total']} 环："
                   f"{spec['claim']}")
    cont = "（接上页）" if spec.get("cont") else ""
    if spec["type"] == "table":
        s0 = spec["data"]["slides"][0]
        out.append(f"【读图】{s0['what']}{cont}")
        out.append(f"【要点】{s0['table_note']}")
        quote, quote_ref = s0["quote"], s0["quote_ref"]
    else:
        out.append(f"【读图】{spec['what']}{cont}")
        out.append(f"【要点】{spec['body']}")
        quote, quote_ref = spec["quote"], spec["quote_ref"]
    if spec.get("arguing") and not spec.get("cont"):
        out.append(f"【论证】{spec['arguing']}")
    if spec.get("critique") and not spec.get("cont"):
        out.append(f"【批判】{spec['critique']}")
    out.append(f"【原文（{quote_ref}）】{quote}")
    return out


def conclusion_notes(deck: Deck) -> list[str]:
    p = deck.paper
    out = ["【中文结论】" + p["conclusion_zh"],
           p.get("conclusion_src", "（译自原文 Conclusions）"),
           "【结论回响检查】结论应直接回答 Introduction「提出问题」一行的问题，"
           "并留下展望/遗留问题；若只复述结果则属『结论=摘要』，读时注意区分。"]
    if p.get("takeaway_good"):
        out.append(f"【这篇好在哪】{p['takeaway_good']}")
    if p.get("if_rebuild"):
        out.append(f"【我若重做/扩展】{p['if_rebuild']}")
    return out


def build_notes(deck: Deck) -> list[str]:
    """Markdown lines for notes/total.md, one H1 per page."""
    by_page = {spec["pageno"]: spec for spec in deck.slides}
    lines: list[str] = []
    for pageno, slug, _builder in deck._plan():
        lines += [f"# {slug}", ""]
        if slug == "01_cover":
            lines += cover_notes(deck)
        elif slug == "02_abstract":
            lines += abstract_notes(deck)
        elif slug.endswith("_intro"):
            lines += intro_notes(deck)
        elif slug.endswith("_overview"):
            lines += overview_notes(deck)
        elif slug.endswith("_methods"):
            lines += methods_notes(deck)
        elif slug.endswith("_conclusion"):
            lines += conclusion_notes(deck)
        else:
            lines += content_notes(by_page[pageno])
        lines.append("")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Write notes/total.md for one workdir.")
    ap.add_argument("workdir", help="directory containing content.json")
    ap.add_argument("--project-dir", metavar="DIR",
                    help="override paper.ppt_project")
    ap.add_argument("--out", metavar="PATH", help="explicit output file")
    ap.add_argument("--dry-run", action="store_true",
                    help="allow the approximate width model")
    args = ap.parse_args(argv)

    wd = pathlib.Path(args.workdir).resolve()
    content = load_content(wd)
    deck = Deck(content, allow_approx=args.dry_run)

    if args.out:
        out = pathlib.Path(args.out)
    elif args.dry_run:
        proj = pathlib.Path(args.project_dir) if args.project_dir else wd / ".dryrun"
        out = proj / "notes" / "total.md"
    else:
        proj = (pathlib.Path(args.project_dir) if args.project_dir
                else project_dir(content["paper"]))
        out = proj / "notes" / "total.md"
    lines = build_notes(deck)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")

    heads = [line[2:] for line in lines if line.startswith("# ")]
    slugs = deck.slug_list()
    missing, extra = set(slugs) - set(heads), set(heads) - set(slugs)
    print(f"wrote {out}: {len(heads)} sections")
    assert not missing and not extra, f"notes/svg mismatch: missing={sorted(missing)} extra={sorted(extra)}"
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
