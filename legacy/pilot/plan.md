# 逐图精讲 PPTX 流水线 — 分步计划

预算约束：每步输出 ≤30K token；每步落盘可验证产物。

## 步骤
- [x] S1 提取+裁剪质检（全部通过，z=4 高清渲染，文件名避开 NTFS 冒号）
- [x] S2 content.json（figures + 1 table；route 串斜杠可读化；fig 自动拆 2–3 页）
- [x] S3 项目素材：figure 图 → JPEG ≤900KB 入项目 images/（z=4 更清晰）
- [x] S4 kit.py + gen_all.py → 32 页 SVG（01_cover, 02_overview, 03..31 内容页, 32_end）
  - 修复：TOK 分词丢 / 等字符 → 加兜底类；image 引用 ../images/ 只留 href；
    data-pptx-bounds 空格形式；总览重叠下移；索引列/tspan 合并
- [x] S5 compact_svg_styles + compact_svg_coordinates --inplace → final gate 32/32 全绿 0/0
- [x] S6 notes/total.md（32 节：读图/要点/原文；end=速查表+延伸问题）→ total_md_split 32/32
- [x] S7 导出 PPTX（--quick-generate --with-notes；需先 --stage final 门禁）
- [x] S8 PPTX 验证：32 slides / 32 notes / media；字号 18pt×474 + 24pt×33（全 ≥18pt）；输出 output/
- [x] S9 视觉抽检（SVG 级：cover/overview/fig01/tab1/fig02 PNG + vision；PPTX 无 LibreOffice，靠门禁+sz 直方图）
- [x] S10 README（项目根）+ advisor-report-decks skill 回写新坑

## 版面参数（宋体+TNR，全部 ≥24px=18pt）
- canvas 1280×720；kicker y44；title 32px y88；金线 y124
- 左图卡 (48,144,568,496)，白卡+meet 图 (64,160,536,464)
- 右面板 (640,144,608,496)：what 标签 y168 + what 行 y196（≤2 行@40）
  body 标签 y284 + 正文 y312 起 40 行距，最多 7 行（>7 自动拆页）
  原文带：hairline y596 + 标签/引用 y612（1 行，溢出截断，notes 载全句）
- 表格页：全宽表 x48 w1184，4 列 320/280/292/292，行高 48，9 行
- 颜色：BLUE #1F3864 / BLUE2 #2E5395 / GOLD #C9A227 / GRAY #595959 / LIGHT #F2F5FA / LINE #D9DEE8
- 宽度估算：import estimate_single_line_text_frame_width（checker 同款，include_headroom=True），贪心折行
- 图片引用：images/figNN.jpg（ASCII 名）；root svg lang="zh-CN"（首页）
- 每页 g 模块：header(48,24,1184,110) / leftcard(48,144,568,496) / panel(640,144,608,496) / footer(48,676,1184,32)，互不重叠
- 页脚：文献精读 · 试点论文 ｜ PNN / 27（24px）

## 已知坑
- ppt-master venv PIL 坏 fork 时代曾需 PYTHONPATH=<repo>/pillow_shim；现 venv 用官方 Pillow（≥11.3.0）已无需 shim
- checker CJK≈1.10em Latin≈0.62em；长中文标签必须缩字号——本次全部 24px 起步，用宽度模型验证
- 多行段落 = 1 个 <text>（首行直接文本）+ <tspan x dy> 续行；兄弟 <text> 会触发 paragraph-like warning 阻断 quick-generate gate
- 文件 >900KB 触发 file-size advisory → JPEG q85 ≤900KB
- PPTX 字体：SVG root font-family="Times New Roman, SimSun, 宋体, serif" → 主题自动 TNR+SimSun
- **TOK 分词正则静默丢弃未覆盖字符**（ASCII `/` 曾全部丢失）→ 必须有 `[^\s]` 单字符兜底类
- **image 引用**：规范 `href="../images/x.jpg"`（相对 svg_output/），只留 href 不留 xlink:href（双引用=blocking）；
  浏览器 file:// 跨目录拦截 → QA 渲染走本地 http.server（127.0.0.1:8765 -d 项目根）
- 生成后跑 compact_svg_styles.py + compact_svg_coordinates.py --inplace 消除 canonical advisories
- svg_quality_checker CLI：项目路径是**位置参数**（非 --project）；JSON 报告需 --json
- 后台 terminal（background=true）不继承 workdir 参数 → 脚本要用绝对路径调用，或先 cd；导出前必须确认 notes/*.md 已生成（gen_notes 失败会被管道吞掉退出码）

## v2 结构改版（用户 2026-10-28 确认，34 页）
- P01 原 title 页裁剪（logo/题目/作者）+ 中文题目 + 原文 Keywords + DOI；P02 中文摘要；
  P03-04 Introduction 五线分析（2 页）；P05..33 逐图讲解（右面板=题名+大段正文，删读什么/关键表述标签，保留原文引用条）；P34 中文结论
- 新增素材 images/p1_title.jpg（256KB）；content.json 增 abstract_zh/conclusion_zh/intro_lines/keywords_en/title_zh/doi 等字段
- 门禁 34/34 全绿；PPTX 34 slides/34 notes/21 media，字号 18pt×390+24pt×34；交付 output/试点_逐图精讲_v2.pptx

## v2.x 精修（用户 2026-10-28 指令：title 截到作者/放大、大段文字首行缩进两字符+两端对齐、
Introduction 小标题内接正文单页铺满、图页尽量一页装下；28 页）
- p1_title 重裁（止于作者行，不含单位）→ 高清 JPEG 入 images/
- 封面白卡放大：image 框 1152×363（y112..475），中文题目 y530/Keywords y568/DOI y640
- kit.wrap 末行孤标点回吸（单独成行的 。；！？ 等并入上一行，超 1 字符宽可接受）
- kit.mtext_lines/mtext 增 indent_px：首行 x+48 且首行 wrap 预算 maxw-48；图页/表注/摘要/结论/Introduction 均用
- Introduction 改单页内联流式：5 个金色粗体小标题+空格+正文 token 流，1136px 满宽、行距 32、
  首行缩进 48，整段 14 行装下（content.json intro_lines 同步精简）
- 图页 BODY_MAX 6→9、行距 40→36（正文区 y212..500，hairline 556 前仍有余量）；表格页同改
- 导出器无 justify/首行缩进映射（text-indent 在 unsupported 列表）→ 后处理
  pilot/postproc_justify.py：按 shape 识别正文（sz=1800+333333+非短文本≥20字符）批量
  a:pPr algn="just"（134 shape/27 页）；首行缩进本身已由 SVG x+48px 烘焙进 shape 偏移，无需再动
- 页码 34→28（intro 2→1、图页合并 cont 减少）；门禁 stage=final 通过；PPTX 28 slides/28 notes/21 media，
  18pt×358+24pt×28；QA 渲染（Edge headless + vision 核验）：封面/摘要/intro/图页/表页/续页/结论 8 页全过
- 交付 output/试点_逐图精讲_v2.pptx（覆盖 34 页旧版）

## v3（用户 2026-10-28 指令：正文不要逐行文本框、要大文本框；加制备方法页；29 页）
- 导出加 `--reflow-text`：同 x 同字号的 tspan 折行流合并为一个 `wrap="square"` 自动换行大文本框
  （默认模式逐行一个 wrap=none 文本框；**逐行 x 偏移会阻止合并** → kit._mtext_lines 改回统一 x 输出，
  首行缩进预算仍 maxw-48（仅影响断行），缩进本身交给 PPTX a:pPr indent）
- 行距统一 36px（abstract/conclusion 40→36，保证 reflow 保守阈值内合并）
- 新增 04_methods 制备方法页（content.json methods_zh/methods_src，译自原文 §2，数值与原文核对一致，
  单段满宽）；图页 05 起，结论 29
- postproc_justify.py v3：识别正文大框（wrap=square+sz1800+333333+≥40字符）→
  ① a:ext cx 恢复版式宽度（图页552/表注376/满宽1136/摘要结论1088 px，9525 EMU/px；
  导出器把框宽收窄到最宽行，PPT 重排会多行越压引用条）② 全段 algn="just" ③ 首段 indent="457200"
- 验证：29 slides/29 notes/21 media，字号 18pt×237+24pt×29；fig/abstract/methods/conclusion/intro 均为单个
  大文本框（a:p=1，无 a:br，全文一段可编辑自动换行）；QA 渲染 04/05/03/06/07/29 六页视觉全过
- 交付 output/试点_逐图精讲_v3.pptx（v2 文件被 PowerPoint 占用锁写，v3 为独立新文件）

## v4（用户 2026-10-28 指令：全文字页右边距=左边距；Introduction 每个小标题新起一行）
- 全文字页（02 摘要/03 Introduction/04 制备方法/29 结论）正文 x=48、maxw 统一 1184
  （块 48..1232，左右边距各 48px 对称；原 1088/1136 右缘不对称）；postproc cx_target 同步改 1184
- Introduction 打包规则：金色小标题 token 遇到时强制断行（小标题永远行首），正文仍接在小标题后
  同行流排（保持"不用另起一行"）；整段 14 行、行距 32，单页装下
- 验证：29 slides/29 notes；slide2/3/4/29 大框 cx=1184px + algn=just + indent=457200；
  行宽实测 1184/1183/1169px 贴满预算；QA 渲染 02/03/04/29 四页视觉全过
- 交付 output/试点_逐图精讲_v4.pptx

## state.json
current_step: S3
