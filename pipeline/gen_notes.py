# -*- coding: utf-8 -*-
"""gen_notes.py — emit notes/total.md (one H1 section per SVG slug) for
total_md_split.py + svg_to_pptx --with-notes.

Usage: python gen_notes.py <workdir>
Notes policy (paper-fig-deck, writer-perspective edition):
- cover: 结构说明 + 三十秒读法（paper.message，若填）
- abstract: 中文摘要 + BMFC 结构注（背景→方法→发现→结论）
- intro（五线）→ overview（论证主线逐图claim，若 mainline）→ methods
- figure page: 【主线】第i/N环 claim（若填）→ 【读图】what → 【要点】body
  → 【论证】arguing（若填，作者如何立论）→ 【批判】critique（若填，证据强度/回避的问题）
  → 【原文（ref）】quote；续页标注「（接上页）」
- table page: 同上，【要点】=table_note
- conclusion: 中文结论 + 结论回响检查（是否回答绪论问题/留展望）
  + 结语两问（paper.takeaway_good / paper.if_rebuild，若填）
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from gen_all import build_slides  # noqa: E402


def slug_for(spec: dict, n: int) -> str:
    if spec["type"] == "table":
        return f"{n:02d}_tab"
    sfx = "_cont" if spec.get("cont") else ""
    pref = "sch" if spec.get("kind") == "scheme" else "fig"
    return f"{n:02d}_{pref}{spec['num']:02d}{sfx}"


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: gen_notes.py <workdir>")
    D = pathlib.Path(sys.argv[1])
    content = json.loads((D / "content.json").read_text(encoding="utf-8"))
    PAPER = content["paper"]
    PROJ = pathlib.Path(PAPER["ppt_project"])
    OUT = PROJ / "notes" / "total.md"

    slides, n_lead = build_slides(content)
    n_figs = sum(1 for s in slides if s["type"] == "fig")
    n_tabs = sum(1 for s in slides if s["type"] == "table")
    has_intro = bool(PAPER.get("intro_lines"))
    has_mainline = bool(PAPER.get("mainline"))
    has_methods = bool(PAPER.get("methods_zh"))
    struct = "原文 title 页 + 中文摘要"
    if has_intro:
        struct += " + Introduction 五线分析"
    if has_mainline:
        struct += " + 论证主线（逐图证明点）"
    if has_methods:
        struct += " + 制备方法"
    struct += (f" + 逐图讲解（{n_figs} 图"
               + (f" + {n_tabs} 表" if n_tabs else "") + "，长文自动拆续页）")
    struct += " + 中文结论。"

    L = ["# 01_cover", ""]
    L.append(f"本篇为逐图精读：{PAPER.get('authors_short', '作者')}（{PAPER.get('journal', '')}）《{PAPER['title_zh']}》。")
    L.append(f"DOI: {PAPER['doi']}；关键词（原文）：{PAPER.get('keywords_en', '（原文无）')}。")
    L.append(f"结构：{struct}")
    if PAPER.get("message"):
        L.append(f"三十秒读法：{PAPER['message']}")
    L.append("")
    L += ["# 02_abstract", "", "【中文摘要】" + PAPER["abstract_zh"],
          PAPER.get("abstract_src", "（译自原文 Abstract）") + "；数字与表述与原文一致。",
          "【BMFC 结构注】按背景（B）→ 材料方法（M）→ 发现（F）→ 结论（C）四要素展开：读时先定位首句的大背景/小背景，再找带数字的发现句，末句为结论与展望。", ""]

    n = 3
    if has_intro:
        L += [f"# {n:02d}_intro", ""]
        for label, text in PAPER["intro_lines"]:
            L.append(f"【{label}】{text}")
        L.append("【写作视角】按「起承转合」检验：背景段是否由大背景收敛到具体体系；问题段是否回答『重要吗、进展到哪步』；本文方案段是否交代『凭什么、怎么解决』。")
        L.append("")
        n += 1
    if has_mainline:
        L += [f"# {n:02d}_overview", ""]
        L.append("本文各图按论证主线排列——每张图是论证链上的一环，读图时先问『这张图证明了什么』，再看它用的证据：")
        for ref, claim in PAPER["mainline"]:
            L.append(f"{ref}：{claim}")
        L.append("")
        n += 1
    if has_methods:
        L += [f"# {n:02d}_methods", "", "【制备方法】" + PAPER["methods_zh"], ""]
        if PAPER.get("methods_src"):
            L[-1] = PAPER["methods_src"]
        L.append("")
        n += 1
    assert n == (n_lead + 1), (n, n_lead)
    for spec in slides:
        slug = slug_for(spec, n)
        L.append(f"# {slug}")
        L.append("")
        if spec.get("claim") and not spec.get("cont"):
            L.append(f"【主线】本文论证第 {spec['ml_index']}/{spec['ml_total']} 环：{spec['claim']}")
        if spec["type"] == "table":
            s0 = spec["data"]["slides"][0]
            L.append(f"【读图】{s0['what']}" + ("（接上页）" if spec.get("cont") else ""))
            L.append(f"【要点】{s0['table_note']}")
        else:
            L.append(f"【读图】{spec['what']}" + ("（接上页）" if spec.get("cont") else ""))
            L.append(f"【要点】{spec['body']}")
        if spec.get("arguing") and not spec.get("cont"):
            L.append(f"【论证】{spec['arguing']}")
        if spec.get("critique") and not spec.get("cont"):
            L.append(f"【批判】{spec['critique']}")
        if spec["type"] == "table":
            qref = spec["data"]["slides"][0]["quote_ref"]
            quote = spec["data"]["slides"][0]["quote"]
        else:
            qref = spec["quote_ref"]
            quote = spec["quote"]
        L.append(f"【原文（{qref}）】{quote}")
        L.append("")
        n += 1
    L += [f"# {n:02d}_conclusion", "", "【中文结论】" + PAPER["conclusion_zh"],
          PAPER.get("conclusion_src", "（译自原文 Conclusions）"),
          "【结论回响检查】结论应直接回答 Introduction「提出问题」一行的问题，并留下展望/遗留问题；若只复述结果则属『结论=摘要』，读时注意区分。"]
    if PAPER.get("takeaway_good"):
        L.append(f"【这篇好在哪】{PAPER['takeaway_good']}")
    if PAPER.get("if_rebuild"):
        L.append(f"【我若重做/扩展】{PAPER['if_rebuild']}")
    L.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L), encoding="utf-8")
    # sanity: every svg slug has a section and vice versa
    svgs = sorted(p.stem for p in (PROJ / "svg_output").glob("*.svg"))
    heads = [l[2:] for l in L if l.startswith("# ")]
    missing = set(svgs) - set(heads)
    extra = set(heads) - set(svgs)
    print(f"wrote {OUT}: {len(heads)} sections; missing={sorted(missing)} extra={sorted(extra)}")
    assert not missing and not extra, "notes/svg mismatch"


if __name__ == "__main__":
    main()
