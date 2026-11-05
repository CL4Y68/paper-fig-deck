---
name: paper-fig-deck
description: "科研论文 PDF → 逐图讲解 PPTX（含讲稿备注、质量门禁）。做逐图 deck、跑 run_pipeline、看 VERIFY 时使用。"
---

# paper-fig-deck

论文 PDF → 逐图/表讲解 PPTX 的 agent 技能。执行引擎是 **paper-fig-deck 仓库里的
Python 流水线**（gated SVG → 可编辑 18pt+ PPTX + 逐页讲稿）。本技能只做三件事：
**定位/安装 → 驱动 → 验收**。不复制代码、不手改输出 SVG。

## 0. 定位仓库

```bash
git clone <本仓库> <repo>        # <repo> 即仓库根目录，下称 <repo>
```

若本技能是从 agent 的 skills 目录加载的（仓库被拷走了），先用上面命令重新定位
`<repo>`；后端工具链 PPT Master（hugohe3/ppt-master，MIT）按
`<repo>/docs/agent-install.md` §2 的自动发现顺序寻找或显式设 `PPTMASTER_DIR`。

## 1. 安装与自检

完整步骤（venv、依赖、ppt-master、环境变量）见 `<repo>/docs/agent-install.md`
§1–§3。装完跑一次自检，`fail` 项必须先补：

```bash
<venv-python> <repo>/pipeline/doctor.py          # [ok]/[warn]/[fail] 每行一项；--json 给机器读
```

## 2. 每篇论文三步（数据全部本地，**永不入库**）

1. **数据**：一个本地 workdir：`content.json` + `images/`（裁剪图，用
   `<repo>/pipeline/extract_figures.py` 从源 PDF 生成）或 PDF + `figures.json`。
   字段规范：`<repo>/pipeline/schema/content.schema.json`（IDE 补全 / agent 自检）；
   方法论（讲稿语气、读点写法、行数上限、BMFC）：`<repo>/pipeline/content_rules.md`。
2. **一条命令**（10 步链全自动化：第 0 步校验 → 图片入项目 → SVG → 讲稿 →
   拆分 → compact → 原生表 stamp → 门禁 → 导出+后处理 → PPTX 校验）：

   ```bash
   <venv-python> <repo>/pipeline/run_pipeline.py <workdir> --name <交付名>
   ```

3. **验收**：日志尾部必须出现 `VERIFY slides=N notes=N overflow=0` 且
   slides == notes；主线总览页 / 长正文页把该页 SVG 包一层 HTML，用浏览器
   CDP 截图亲眼看一次（重叠 / 截断 / 对齐）。

## 硬规则（违反 = 废品）

- `content_schema.py` 报 **error** 时禁止硬跑；warning 要逐条确认是"接受"还是"要改"
- 正文行数上限是**实测值**（当前 14 行）：换字体/盒宽/行距必须重跑
  `<repo>` 的 `measure_lines.py` + `measure_capacity.py`，**禁止凭直觉改**
- 门禁 `blocking>0` 时导出被拒——改 `content.json` 或生成参数，**不要手改输出 SVG**
- `mainline` 条目 >9 自动双栏；读点题名将自动截断，正文靠行数上限控制
- 数值（配方量、材料参数）一律照抄 `content.json`，写进讲稿前与源文件核对
- 版权红线（`<repo>/docs/agent-install.md` §8）：源 PDF / content.json / 裁剪图 /
  交付 PPTX 只留本地；公开仓库（含 git 历史）不得出现任何文献信息（**OA 也不行**）

## 出错先看这里（完整表：`<repo>/docs/agent-install.md` §7）

| 症状 | 处理 |
|---|---|
| doctor: `no ppt-master scripts/ dir found` | 设 `PPTMASTER_DIR`（须含 `scripts/svg_quality_checker.py`） |
| gate: `External image not found` | 确认 workdir 有 `images/` 或 `figures.json`；驱动会自动 stage |
| 第 0 步 `figures[i].slides[j].xxx` | 按字段路径补 `content.json`；`--json` 便于脚本处理 |
| gate: `exceeds … horizontal axis` | 缩短读点题名/正文文案（不要动版面） |
| `VERIFY … overflow>0` | 检查 `page_roles.json` 与正文框宽；改 content 不 hand-edit SVG |

更多：`<repo>/pipeline/README.md`（脚本详解）、`<repo>/docs/agent-install.md`
§5–§10（一键调用选项、排错、版权、重测、启动提示词模板）。
