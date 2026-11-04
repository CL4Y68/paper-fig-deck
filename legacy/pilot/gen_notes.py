# -*- coding: utf-8 -*-
"""gen_notes.py — emit notes/total.md (one H1 section per SVG slug) for
total_md_split.py + svg_to_pptx --with-notes.

Notes policy (pilot spec):
- figure page: 【读图】what → 【要点】该页 body chunk → 【原文 p.N】完整引用句
- cont page 标注「接上页」
- framework pages hand-written
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from gen_all import PROJ, PAPER, build_roster  # noqa: E402

OUT = PROJ / "notes" / "total.md"


def slug_for(spec: dict, n: int) -> str:
    if spec["type"] == "table":
        return f"{n:02d}_tab1"
    sfx = "_cont" if spec.get("cont") else ""
    return f"{n:02d}_fig{spec['num']:02d}{sfx}"


def fig_section(slug: str, spec: dict) -> str:
    cont = spec.get("cont")
    L = [f"# {slug}", ""]
    if spec["type"] == "table":
        s0 = spec["data"]["slides"][0]
        L += [
            "左侧为 Table 1 原始数据。",
            f"【备注】{s0['what']}",
            "【要点】具体数值见 Table 1（括号内为重复测定值）。",
            f"【原文（{s0['quote_ref']}）】{s0['quote']}",
        ]
    else:
        L.append(f"【读图】{spec['what']}" + ("（接上页）" if cont else ""))
        L.append(f"【要点】{spec['body']}")
        L.append(f"【原文（{spec['quote_ref']}）】{spec['quote']}")
    L.append("")
    return "\n".join(L) + "\n"


def intro_section(slug: str) -> str:
    L = [f"# {slug}", ""]
    for label, text in PAPER["intro_lines"]:
        L.append(f"【{label}】{text}")
    L.append("")
    return "\n".join(L) + "\n"


def main():
    specs = build_roster()
    sections = [
        "# 01_cover",
        "",
        f"本讲为逐图精讲：《{PAPER['title_zh']}》。",
        f"DOI: {PAPER['doi']}；关键词（原文）：{PAPER['keywords_en']}。",
        "结构：原文 title 页 + 中文摘要 + Introduction 五线分析（单页，小标题后接正文）+ 制备方法 + 逐图讲解（尽量一页装下）+ 中文结论。",
        "",
        "# 02_abstract",
        "",
        "【中文摘要】" + PAPER["abstract_zh"],
        "（译自原文 Abstract，p. 1；数字与表述与原文一致。）",
        "",
    ]
    sections.append(intro_section("03_intro"))
    sections += [
        "# 04_methods",
        "",
        "【制备方法】" + PAPER["methods_zh"],
        PAPER["methods_src"] + " 参数明细见 06_tab1 页（Table 1）。",
        "",
    ]
    n = 5
    for spec in specs:
        slug = slug_for(spec, n)
        sections.append(fig_section(slug, spec))
        n += 1
    sections.append(f"# {n:02d}_conclusion")
    sections += [
        "",
        "【中文结论】" + PAPER["conclusion_zh"],
        "（译自原文 4. Conclusions，p. 17；「unexpectedly large fiber diameters」= 纤维直径意外偏大。）",
        "",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(sections), encoding="utf-8")
    # sanity: every svg slug has a section and vice versa
    svgs = sorted(p.stem for p in (PROJ / "svg_output").glob("*.svg"))
    heads = [l[2:] for l in sections if l.startswith("# ")]
    missing = set(svgs) - set(heads)
    extra = set(heads) - set(svgs)
    print(f"wrote {OUT}: {len(heads)} sections; missing={sorted(missing)} extra={sorted(extra)}")


if __name__ == "__main__":
    main()
