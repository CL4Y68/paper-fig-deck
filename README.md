# paper-fig-deck — 文献逐图精讲 PPTX 流水线

把材料/化学/工程方向的科学论文 PDF 转成**逐图精讲 PPTX**：左原图 + 右面板（题名 + 大段正文，宋体 + Times New Roman，全部 ≥18pt，正文首行缩进两字符 + 两端对齐），
页底原文引用条 + 演讲者备注讲稿，兼顾自学与组会汇报。试点为某期刊论文（多篇图表 → **29 页 PPTX**；具体篇目与内容数据在本地 `pilot/` 目录下，按版权要求不入库）。

> **后端工具不限定**：本仓库产出的是「SVG 页面 + 讲稿 + 内容数据」，任何 PPT 生成工具链都可作为后端。
> **推荐 [PPT Master](https://github.com/hugohe3/ppt-master)**（开源，MIT License，by Hugo He / hugohe3）——
> 它的 SVG→PPTX 导出器（自动换行文本框 + 演讲者备注 + 原生图表/表格）与本流水线的版式契约最契合，
> 且 `kit.py` / `run_pipeline.py` 内置了它的自动发现。用其他 PPT skill/工具链时，
> 按下方「后端工具」节的接口契约对接即可。

## 页面结构（v3，内容驱动）

| 页 | 内容 |
|---|---|
| 01 | 原文 title 页裁剪（journal logo + 英文题目 + **作者名**，止于作者行不含单位，放大展示）+ 中文题目 + 原文 Keywords + DOI |
| 02 | 中文摘要（整段，首行缩进两字符 + 两端对齐） |
| 03 | Introduction 五线分析（**单页**：五个金色小标题**各自行首**、正文接在小标题后同行流排，满宽对称排版） |
| 04 | **制备方法**（Materials and Methods：整段，译自原文方法部分，数值与原文核对一致） |
| 04′ | **论证主线总览**（可选：`content.json` 有 `paper.mainline` 时出现）：每图/表一行「ref + 它证明了什么」，>9 项双栏；方法论见 `pipeline/content_rules.md` |
| 05… | 逐图/表讲解（左原图 + 右面板：粗体读点题名 + 大段正文 ≤9 行 + 原文引用条；装不下的图拆「续」页，尽量一页装下） |
| 29 | 中文结论（整段，首行缩进两字符 + 两端对齐） |

**正文排版（v3 起）**：每段正文在 PPTX 里是**一个自动换行的大文本框**（非逐行文本框）；
首行缩进两字符用 `a:pPr indent` 属性实现，两端对齐用 `algn="just"`，均由 `postproc_justify.py` 在导出后批量写入。

## 目录

```
paper-fig-deck/
├── pipeline/              # 现行共享脚本（快照，详见 pipeline/README.md）
│   ├── kit.py / gen_all.py / gen_notes.py / postproc_justify.py
│   ├── extract_figures.py / prep_images.py
│   ├── run_pipeline.py    # 一键驱动（9 步：生成→门禁→导出→后处理→PPTX 校验→交付拷贝）
│   ├── content_rules.md   # 内容创作方法论（论证主线/三层论证/总览页 schema/备注模板）
│   └── measure_*.py      # PPT 正文盒行数容量实测（PowerPoint 渲染 + 像素扫描）
├── pilot/                 # 初代试点快照（frozen，内容数据本地不入库）
│   ├── extract_figures.py # 阶段 1：图表裁剪（pymupdf，z=4 宽≤2000px）
│   ├── prep_images.py     # 图片 → JPEG ≤900KB（入 ppt-master 项目）
│   ├── kit.py             # 共享版式（24px 宽度模型折行、TOK 分词、mtext 首行缩进 indent_px、颜色/版面常量）
│   ├── gen_all.py         # 阶段 3：29 页 SVG（封面/摘要/intro 单页/制备方法/图页/表页/结论；body 超 9 行自动拆页）
│   ├── gen_notes.py       # 阶段 4：notes/total.md（29 节讲稿）
│   ├── postproc_justify.py# 阶段 5：PPTX 后处理（大文本框恢复版式宽度 + algn=just + 首段 indent 两字符）
│   ├── plan.md            # 分步计划、v2/v2.x 变更日志（pilot 历史记录）
│   ├── images/            # 裁剪图（PNG 高清，本地）
│   └── qa*/               # 渲染质检 PNG（本地）
├── docs/
│   └── agent-install.md   # agent 安装与调用指南（给 AI agent 用的完整上手步骤）
└── <批次目录>/             # （本地批次数据，如各论文 workdir；版权原因不入库，
                             #   用 .git/info/exclude 逐机守卫，.gitignore 不写批次名）
```

**本地文件，不入库（版权，勿提交）**：`pilot/content.json` / `figures.json` / `meta.json`（阶段 2 结构化内容，含原文摘录与译文）
与 `output/`（交付 PPTX，含原图裁剪 + 引文片段）——复现时自备论文 PDF 与 JSON 数据。

PPT 工具链工作区（PPT Master 为 `projects/<prefix>_<paper>_ppt169_<日期>/`）：`run_pipeline.py`
自动创建/复用（位置因机器与后端而异，路径写回 content.json 的 `ppt_project` 字段）
（svg_output/ N 个 SVG + images/ + notes/ N 个 md + validation/ 门禁报告，均为本地文件）

## 流水线

1. **裁剪** `extract_figures.py <pdf> <outdir>`：全页渲染 + 候选框收集 → caption 锚点聚簇 → 图区矩形 → z=4（宽≤2000px）渲染 + 联系表人工质检。
2. **内容** `content.json`（**本地文件，不入库**）：人工/AI 按原文逐图提炼，数字与原文逐字一致、标注页码；quote 为精简原文句。
3. **SVG** `gen_all.py` → 项目 `svg_output/`。正文排版规则：首行缩进 48px（两字符 @24px）、行距 36px；
   图页正文上限 = **实测值**（当前 `pipeline/` 为 14 行：`measure_capacity.py` 用 PowerPoint 渲染 + 像素扫描测得
   552px 盒 18pt 宋体装 14 行不压 y556 分隔线、15 行越线；换字体/盒宽/行距须重测，**禁止凭行数直觉定上限**；
   11–14 行时 SVG 行距自适应收紧保持 zone 不越界，PPT 重排不受影响）；
   全文字页（摘要/结论/制备方法/Introduction）x=48、maxw=1184（左右边距各 48px 对称）；
   Introduction 按**五线路线**分析（单页）：背景与研究现状 → 提出问题 → 别人的相关工作及问题 → 启发与希望 → 本文研究如何展开，
   五个金色小标题各自行首、正文接在其后同行流排。
4. **门禁** `compact_svg_styles.py` + `compact_svg_coordinates.py --inplace` 后，
   `svg_quality_checker.py <project> --quick-generate --canonical-authoring --stage final --json`（**必须带 stage final**，否则导出器拒绝 quick-generate）。
   含原生表（kind=table）页的项目：compact 之后、gate 之前必须先 `stamp_native_fallbacks.py <project>/svg_output --write`，
   否则门禁报 blocking（"native table requires semantic table marker"）。
5. **讲稿** `gen_notes.py` → `notes/total.md` → `total_md_split.py <project>`（先删旧 notes/*.md 再跑，与全部 SVG 一一对应）。
6. **导出** `svg_to_pptx.py <project> --quick-generate --with-notes --reflow-text` → `postproc_justify.py <src> <dst> <page_roles.json>` → `output/`。
   `--reflow-text` 把同 x、同字号的折行流合并成**一个自动换行的大文本框**（默认导出会逐行一个文本框）；
   后处理再给该文本框 `algn="just"` + 首段 `indent`（首行缩进两字符），并把它宽度恢复到版式宽度
   （导出器把文本框收窄到最宽行实际宽度，会让 PPT 重排多出一行越界，故按页恢复：图页 552 / 表页 376 / 全文字页 1184）。
   含原生表项目须加 `--native-charts-and-tables`（默认关闭时表格静默退化为 shape 拼贴，PPTX 里无 `<a:tbl>`）；
   导出文件路径用 `ls -t exports/*.pptx | head -1` 取（导出器 stdout 是反斜杠 Windows 路径，grep 会拿到空串导致 postproc 静默 no-op）。
7. **质检** SVG 包一层 HTML 后用浏览器（CDP/截图工具）开 `file://` 逐页渲染 PNG + 视觉审阅。
   注意 CJK 偏宽、卡内大字号文本易顶出重叠，关键页（双栏总览、长正文页）必须渲染后亲眼看。

> **一键**：`python pipeline/run_pipeline.py <workdir> --name <交付名> [--desktop-dir <dir>]`
> 把上述全部顺序坑（删旧 notes、原生表 stamp、gate 拦截、SRC 发现、postproc、PPTX 校验）固化成 9 步；
> gate blocking>0 时直接拒导出。

## 运行环境

- Python：任一含 `requirements.txt` 包（pymupdf、python-pptx、Pillow、lxml、pywin32）的 venv；
  推荐后端 [PPT Master](https://github.com/hugohe3/ppt-master) 的 venv 可直接使用
- 版权材料一律**不入库**：源文献 PDF、论文数据 JSON（content/figures/meta.json）、交付 PPTX（含原图裁剪与引文片段）均只保存在本地。
  复现时自备论文 PDF（版权材料一律本地，不入库），`extract_figures.py` 的第一步输入即本地 PDF 路径
- PIL：venv 已用官方 Pillow（≥11.3.0），无需任何 shim；`measure_*.py` 额外需要 `pywin32`（PowerPoint COM 渲染）
- 终端为 git-bash：`cd` 原生 Windows 路径（C:/…）会失败，脚本一律用**原生路径直接传给 python.exe**，不要 cd

## 后端工具（不限定；推荐 PPT Master）

**推荐后端：[PPT Master](https://github.com/hugohe3/ppt-master)**（开源，MIT License，by Hugo He / hugohe3）：
把文档/主题直接生成为**原生可编辑的 PPTX**（原生形状、图表/表格、演讲者备注、自定义模板），
与本流水线的版式契约（自动换行大文本框、按页备注、原生表）最契合。

仓库代码与后端的耦合点集中在两处，均有环境变量钩子：

| 钩子 | 作用 | 默认行为 |
|---|---|---|
| `$PPTMASTER_DIR` | 指向后端根目录（需含 `scripts/svg_quality_checker.py`） | home 下自动发现 ppt-master 安装 |
| `$SKILL_SCRIPTS_DIR` | 指向后端 `scripts/` 目录（`kit.py` 取文本宽度估算器） | 同上自动发现 |

换成其他 PPT skill / 工具链时，后端需提供同等能力（或自行实现）：

| 能力 | 流水线用途 | PPT Master 对应件 |
|---|---|---|
| 文本宽度估算 | 与门禁用同一宽度模型，折行预测一致 | `svg_to_pptx.drawingml.elements.estimate_single_line_text_frame_width` |
| SVG→PPTX 导出 | 自动换行文本框 + 逐页演讲者备注 + 可选原生图表/表格 | `svg_to_pptx.py --quick-generate --with-notes --reflow-text [--native-charts-and-tables]` |
| 质量门禁 | blocking/warning JSON 报告（溢出/文件大小/标记检查） | `svg_quality_checker.py --json` |
| 备注拆分 | total.md 按 SVG 文件名 1:1 拆成逐页 notes | `total_md_split.py` |
| 原生表标记 | 表页打 native-table marker，否则导出退化为 shape 拼贴 | `stamp_native_fallbacks.py --write` |

非 PPT Master 后端：设上面两个环境变量指向其等价目录；若模块名/CLI 不同，改 `kit.py` 头部 import
与 `run_pipeline.py` 的步骤命令（仅此两处）。

## 调用方法（agent 快速上手）

1. **环境**：装好 `requirements.txt` 的 venv + 后端工具链（推荐 PPT Master，设 `PPTMASTER_DIR` /
   `SKILL_SCRIPTS_DIR` 指向它，见上节）
2. **数据**：每篇一个本地 workdir——源 PDF + `content.json`（按 `pipeline/content_rules.md`
   逐图提炼，agent 的智力活在此）+ 裁剪图（`extract_figures.py` / `prep_images.py` 生成）
3. **调用**：

   ```
   <venv-python> pipeline/run_pipeline.py <workdir> --name <交付名> [--desktop-dir <目录>]
   ```

   9 步顺序坑已固化；门禁 blocking>0 直接拒导出。看输出末尾
   `VERIFY slides=N notes=N overflow=0`（slides==notes 即通过）
4. **亲眼看**：双栏主线总览页 / 长正文页——SVG 包 HTML + 浏览器 CDP 开 `file://` 截图
   检查重叠/截断（浏览器 CLI 直截截图不可靠，勿用）
5. **红线**：文献信息（作者/期刊/DOI/篇内数值，**OA 也不行**）与全部内容数据只留本地，永不提交

完整安装步骤、content.json schema、可粘贴的 agent 启动提示词：`docs/agent-install.md`。

## 版面契约（1280×720 = 16:9）

| 元素 | 参数 |
|---|---|
| 字体 | Times New Roman + 宋体，全部文本 ≥24px（18pt） |
| 左图卡 | (48,144,568,496) 白卡，图 meet 于 (64,160,536,464) |
| 右面板 | (640,144,608,496)：读点题名(1行) → 正文(≤9 行@36px，首行缩进 48px) → hairline y556 → 原文条 |
| 颜色 | BLUE #1F3864 / GOLD #C9A227 / DARK #333 / GRAY #595959 / LGRAY #8A8F98 / LIGHT #F2F5FA |

## 致谢（开源依赖）

本流水线以 **PPT Master**（[hugohe3/ppt-master](https://github.com/hugohe3/ppt-master)，作者 Hugo He，
MIT License）为推荐后端：

> PPT Master — AI generates native PowerPoint from any document. Native shapes,
> transitions, data-backed charts/tables, audio narration from speaker notes.
> © Hugo He · [MIT License](https://opensource.org/licenses/MIT) ·
> [https://github.com/hugohe3/ppt-master](https://github.com/hugohe3/ppt-master)

`kit.py` 的文本宽度估算与 `run_pipeline.py` 的导出/门禁/备注步骤复用了该项目的
`scripts/`（svg_to_pptx、svg_quality_checker、compact_*、total_md_split、stamp_native_fallbacks）。
MIT License 允许再分发，本仓库在此保留其归属声明；`PPTMASTER_DIR` / `SKILL_SCRIPTS_DIR`
指向的本地安装不属于本仓库，按其自身 LICENSE 使用。
