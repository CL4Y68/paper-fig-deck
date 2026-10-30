# Agent 安装与调用指南

让一台新机器 / 一个新的 AI agent 从克隆到交付 PPTX 的完整步骤。
装好后，agent 的每篇任务只有三步：**填 content.json → 跑一条命令 → 看 VERIFY**。

## 0. 前提

- Python ≥ 3.10（agent 机器的任意发行版）
- 主流程不依赖 PowerPoint；仅以下两项需要（Windows）：
  - `measure_*.py` 重测正文盒行数容量（pywin32 + 本机 PowerPoint COM）
  - 原生图表/表格导出的 PPT 重排质量最好（装 PowerPoint 兜底）
- 后端工具链：推荐 [PPT Master](https://github.com/hugohe3/ppt-master)（MIT），见第 2 节

## 1. 装项目

```bash
git clone <paper-fig-deck 仓库地址>
cd paper-fig-deck
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt    # Linux/macOS 用 .venv/bin/pip
```

## 2. 装后端（推荐 PPT Master）

```bash
git clone https://github.com/hugohe3/ppt-master   # 放本机任意位置
```

给 agent 的运行环境设两个变量（脚本也支持不配变量、自动发现常见安装位置）：

| 变量 | 指向 |
|---|---|
| `PPTMASTER_DIR` | ppt-master 根目录（须含 `scripts/svg_quality_checker.py`） |
| `SKILL_SCRIPTS_DIR` | 它的 `scripts/` 目录（`kit.py` 取文本宽度估算器） |

换其他 PPT skill / 工具链：按主 README「后端工具」节的接口契约表对接
（宽度估算 / SVG→PPTX 导出 / 质量门禁 / 备注拆分 / 原生表标记，共 5 项能力）。

## 3. 每篇论文一个 workdir（数据全部本地，**不入库**）

```
<workdir>/
  论文.pdf       ← 源 PDF（版权材料，只留本地）
  content.json   ← agent 的智力活：按 pipeline/content_rules.md 逐图提炼
  figures.json   ← 图表裁剪清单（pipeline/extract_figures.py 生成）
  images/        ← 裁剪 JPEG ≤900KB（pipeline/prep_images.py 生成）
```

`content.json` 关键 schema（细则见 `pipeline/content_rules.md`）：

```jsonc
{
  "paper": {
    "title_zh": "...", "journal": "...", "authors_short": "...", "doi": "...",
    "abstract_zh": "...", "conclusion_zh": "...",
    "intro_lines": [["背景与研究现状","..."],["提出问题","..."], ...],       // 可选
    "methods_zh": "...",                                                      // 可选
    "mainline": [["Fig 1","它证明了什么"],["Table 1","..."], ...],          // 总览页；与 figures 顺序对齐
    "message": "三十秒读法一句话", "takeaway_good": "...", "if_rebuild": "..."  // 可选，备注增强
  },
  "figures": [
    { "kind": "figure", "id": "fig1", "img": "fig01.jpg",
      "slides": [ { "reading_point": "...", "what": "...", "body": "...",
                     "quote": "...", "quote_ref": "p. 3" } ] },
    { "kind": "table", "id": "table1", ... }
  ]
}
```

## 4. 一键调用

```powershell
<venv-python> <repo>/pipeline/run_pipeline.py <workdir> --name <交付名> [--desktop-dir <交付目录>] [--no-export]
```

9 步顺序坑已固化在驱动里（删旧 notes → 生成 SVG → 讲稿 → 拆分 → compact →
原生表 stamp → 门禁 → 导出+后处理 → PPTX 校验+交付拷贝）；门禁 blocking>0 直接拒导出。

## 5. agent 跑完查什么

1. 输出末尾 `VERIFY slides=N notes=N overflow=0`，且 **slides == notes**（每页有讲稿）
2. 双栏主线总览页、长正文页：把该页 SVG 包一层 HTML，浏览器 CDP 开 `file://`
   + 截图亲眼看（重叠 / 截断 / 对齐）；Edge 等浏览器 CLI 直截截图不可靠（横幅/空白帧）
3. 改字后重跑同一命令即可（项目目录自动复用，SVG/notes 全量重生成）

## 6. 版权红线（务必写进 agent 系统提示词）

- 源 PDF、`content.json`/`figures.json`、裁剪图、交付 PPTX **只留本地，永不提交**
- 公开仓库（含 git 历史）不得出现**任何**文献信息：作者/期刊/卷期/DOI/材料名/
  篇内数值——**OA 的也不行**
- agent 回复用户时不复述论文原文片段；数据核对用本地文件完成

## 7. 何时重测（measure_*）

换字体 / 正文盒宽 / 行距后，跑 `measure_lines.py` + `measure_capacity.py`
（需 pywin32 + 本机 PowerPoint 渲染）重测正文盒行数上限，再更新生成器；
**禁止凭行数直觉定上限**。

## 8. 粘给 agent 的启动提示词（模板）

> 用 `<repo>/pipeline/run_pipeline.py` 把这篇论文做成逐图精讲 PPTX。
> 先按 `pipeline/content_rules.md` 为 `<workdir>/content.json` 逐图提炼：
> 数字与原文逐字一致、引文精简、标注页码；`mainline` 每图/表一句「它证明了什么」。
> 然后运行 `<venv-python> <repo>/pipeline/run_pipeline.py <workdir> --name 逐图精讲`，
> 确认 VERIFY 行 slides==notes 且 overflow=0，再用浏览器 CDP 截图亲眼看主线总览页与长正文页。
> 内容数据与 PPTX 只留本地；任何文献信息（含 OA）不得提交到公开仓库。
