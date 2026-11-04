# Agent 安装与调用指南

让一台新机器 / 一个新的 AI agent 从克隆到交付 PPTX 的完整步骤。
装好后，每篇论文只有三步：**填 content.json → 跑一条命令 → 看 VERIFY**。

## 0. 前提

- Python ≥ 3.10（任意发行版；主流程不需要 PowerPoint）
- 仅以下两项需要 Windows + PowerPoint：
  - `measure_*.py` 重测正文盒行数容量（pywin32 + PowerPoint COM）
  - 原生图表/表格导出的重排质量最好（装 PowerPoint 兜底）
- 后端工具链：推荐 [PPT Master](https://github.com/hugohe3/ppt-master)（MIT），见第 2 节
- 字体：Times New Roman + 宋体（Windows 自带；其他平台需自行安装，否则导出的 PPT 会替换字体）

## 1. 装项目

```bash
git clone <本仓库>
cd paper-fig-deck
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt       # Linux/macOS: .venv/bin/pip
```

`requirements.txt` 里 `pywin32` 带 `sys_platform == "win32"` 标记，Linux/macOS 上直接装、不会失败。

开发/CI 另装 `requirements-dev.txt`（pytest + ruff）。

## 2. 装后端（推荐 PPT Master）

```bash
git clone https://github.com/hugohe3/ppt-master   # 放本机任意位置
```

给 agent 的运行环境设变量：

| 变量 | 指向 | 必需 |
|---|---|---|
| `PPTMASTER_DIR` | ppt-master 根目录（须含 `scripts/svg_quality_checker.py`） | 是（或能被自动发现） |
| `SKILL_SCRIPTS_DIR` | 它的 `scripts/` 目录（`kit.py` 取宽度估算器） | 否，缺省从 `PPTMASTER_DIR` 推导 |

自动发现顺序（无需设变量时可以命中）：`$SKILL_SCRIPTS_DIR` → `$PPTMASTER_DIR/scripts`
→ `<home>/…/hermes/profiles/*/skills/productivity/ppt-master/scripts`
→ `~/ppt-master`、`~/tools/ppt-master`、`~/repos/ppt-master` 等常见位置 → 当前目录下的 `ppt-master/`。

换其他 PPT 工具链：按主 README「后端工具」节的接口契约表对接
（宽度估算 / SVG→PPTX 导出 / 质量门禁 / 备注拆分 / 原生表标记，共 5 项能力）。

## 3. 自检

```bash
<venv-python> pipeline/doctor.py
```

输出每项一行 `[ok] / [warn] / [fail]`；`fail` 的项就是必须先补的（缺包、找不到 ppt-master
scripts、无写权限）。`--json` 给机器读。

## 4. 每篇论文一个 workdir（数据全部本地，**不入库**）

```
<workdir>/
  论文.pdf       ← 源 PDF（版权材料，只留本地）
  content.json   ← agent 的智力活：按 pipeline/content_rules.md 逐图提炼
  figures.json   ← 可选：图表裁剪清单（extract_figures.py 生成）
  images/        ← 图片：figures.json 模式的裁剪结果，或直接放已命名的 jpg/png
```

图片两种来源都可以，`run_pipeline.py` 会自动 stage 进项目：

- 有 `figures.json` → 按图表编号压成 `figNN.jpg` / `schNN.jpg`
- 只有 `images/` → 文件名原样保留（`content.json` / `paper.title_page_img` 直接引用）

`content.json` 关键 schema（可校验版本：`schema_version: "2"`；细则见
`pipeline/content_rules.md`，机器可读版见 `pipeline/schema/content.schema.json`）：

```jsonc
{
  "schema_version": "2",
  "paper": {
    "title_zh": "...", "journal": "...", "authors_short": "...", "doi": "...",
    "title_page_img": "p1_title.jpg",              // 项目 images/ 内的封面图
    "abstract_zh": "...", "abstract_src": "（译自原文 Abstract）",
    "conclusion_zh": "...", "conclusion_src": "（译自原文 Conclusions）",
    "intro_lines": [["背景与研究现状","..."], ["提出问题","..."], ["本文方案","..."],
                    ["关键证据","..."], ["结论与影响","..."]],     // 可选，≤5 行
    "methods_zh": "...", "methods_src": "...",                       // 可选
    "mainline": [["Fig 1","它证明了什么"], ["Table 1","..."]],        // 总览页，与 figures 顺序对齐
    "message": "三十秒读法", "takeaway_good": "...", "if_rebuild": "...",  // 可选，备注增强
    "title_crop": {"pdf": "<abs path>", "page": 1, "rect": [x0,y0,x1,y1], "out": "p1_title.jpg"},  // 可选
    "project_prefix": "figdeck",                   // 可选，项目目录名前缀
    "ppt_project": ""                              // 由 run_pipeline 自动填写
  },
  "figures": [
    { "kind": "figure", "num": 1, "img": "fig01.jpg",
      "arguing": "可选：作者这一步如何立论", "critique": "可选：证据强度/回避的问题",
      "slides": [ { "reading_point": "...", "what": "...", "body": "...",
                    "quote": "...", "quote_ref": "p. 3" } ] },
    { "kind": "table", "title": "Table 1 ...",
      "slides": [ { "reading_point": "...", "table_note": "...",
                    "headers": ["项","值"], "table_rows": [["a","b"]],
                    "quote": "...", "quote_ref": "p. 7" } ] }
  ]
}
```

先校验，再生成（第 0 步流水线会自动做，单独跑更快）：

```bash
<venv-python> pipeline/content_schema.py <workdir>            # 退出码 1 = 有 error
<venv-python> pipeline/content_schema.py <workdir> --json     # 机器可读
```

校验器区分 **error**（建不出正确页面）与 **warning**（建得出但大概率不是你想要的：
正文会拆很多页、mainline 与 figures 数量不一致、表格单元格过宽……），并给出字段路径。

## 5. 一键调用

```powershell
<venv-python> <repo>/pipeline/run_pipeline.py <workdir> --name <交付名> [options]
```

| 选项 | 作用 |
|---|---|
| `--name` | 交付文件名（默认 `<workdir>`）→ `<workdir>/../output/<name>_逐图精讲.pptx` |
| `--desktop-dir` | 完成后把 PPTX 复制过去（文件被占用时只警告，不失败） |
| `--project-dir` | 覆盖 `content.json[paper][ppt_project]` |
| `--no-export` | 门禁通过就停（快速迭代文案时用） |
| `--dry-run` | 只做校验 + SVG + 讲稿，用近似宽度模型写 `sample/.dryrun`；**不可交付** |
| `--skip-validate` | 跳过第 0 步校验（只在调试生成器本身时用） |

10 步顺序的坑已固化在驱动里（校验 → 删旧 notes → 图片入项目 → SVG → 讲稿 → 拆分 →
compact → 原生表 stamp → 门禁 → 导出+后处理 → PPTX 校验+交付）；门禁 blocking>0 直接拒导出。

## 6. agent 跑完查什么

1. 输出尾部 `[8/9] VERIFY slides=N notes=N overflow=0`，且 **slides == notes**（每页有讲稿）
2. 双栏主线总览页、长正文页：把该页 SVG 包一层 HTML，浏览器 CDP 开 `file://`
   + 截图亲眼看（重叠 / 截断 / 对齐）；Edge 等浏览器 CLI 直接截屏不可靠（横幅 / 空白帧）
3. 改字后重跑同一命令即可（项目目录自动复用，SVG / notes 全量重生成）

## 7. 排错

| 症状 | 原因 | 处理 |
|---|---|---|
| `[error] … no ppt-master scripts/ dir found` | 后端没装或路径不对 | 设 `PPTMASTER_DIR`；跑 `doctor.py` 看它找到哪 |
| 第 0 步报 `figures[i].slides[j].xxx` | content.json 字段缺失/类型错 | 按路径补；`--json` 便于脚本处理 |
| gate `BLOCKING: … invalid image source: External image not found` | 图片没进项目 `images/` | 确认 workdir 有 `images/` 或 `figures.json`；驱动会自动 stage |
| gate `BLOCKING: … exceeds <g id="panel"> … horizontal axis` | 读点题名/文字超出面板 | 缩短文案（读点题名已自动截断，正文靠行数上限控制） |
| `gate blocking=N` | 版面越界 / 图文重叠 | 按打印出的文件名与 message 改 `content.json`，别改 SVG |
| `notes/svg mismatch` | 讲稿与页面没 1:1 | 驱动会先删旧 notes 再重生成；手工跑时也要先清 `notes/*.md` |
| `VERIFY … overflow>0` | PPTX 里有形状出界 | 通常是正文框宽被改；检查 `page_roles.json` 与 `postproc_justify` |
| Linux 上 `pip install pywin32` 失败 | 老 requirements 没有平台标记 | 已修：`pywin32>=306; sys_platform == "win32"` |

## 8. 版权红线（务必写进 agent 系统提示词）

- 源 PDF、`content.json`/`figures.json`、裁剪图、交付 PPTX **只留本地，永不提交**
- 公开仓库（含 git 历史）不得出现**任何**文献信息：作者/期刊/卷期/DOI/材料名/
  篇内数值 —— **OA 的也不行**
- agent 回复用户时不复述论文原文片段；数据核对用本地文件完成
- 需要放进仓库的演示材料只能用纯合成内容（见 `sample/`）

## 9. 何时重测（measure_*）

换字体 / 正文盒宽 / 行距后，跑 `measure_lines.py` + `measure_capacity.py`
（需 pywin32 + 本机 PowerPoint 渲染）重测正文盒行数上限，把结果写回
`pipeline/layout.py` 的 `BODY_MAX` / `BODY_LEAD`；**禁止凭行数直觉定上限**。

## 10. 粘给 agent 的启动提示词（模板）

> 用 `<repo>/pipeline/run_pipeline.py` 把这篇论文做成逐图精讲 PPTX。
> 先跑 `<venv-python> pipeline/doctor.py` 确认环境；再按 `pipeline/content_rules.md`
> 为 `<workdir>/content.json` 逐图提炼（`schema_version: "2"`）：数字与原文逐字一致、
> 引文精简、标注页码；`mainline` 每图/表一句「它证明了什么」。
> 用 `pipeline/content_schema.py` 校验到 0 error 后，运行
> `<venv-python> pipeline/run_pipeline.py <workdir> --name 逐图精讲`。
> 确认 `VERIFY` 行 slides==notes 且 overflow=0，再用浏览器 CDP 截图亲眼看主线总览页与长正文页。
> 内容数据与 PPTX 只留本地；任何文献信息（含 OA）不得提交到公开仓库。
