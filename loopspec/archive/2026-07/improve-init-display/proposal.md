## Why

`loopspec init` 是新用户接触这个工具的第一条命令，但它的人类可读输出是把喂给 `--json` 的同一个 dict 逐条 `key: value` 转印出来的——包括 Python 的 dict/list repr。实际效果是这样：

```
scaffoldedFiles: {'claude': ['loopspec/.claude/skills/loopspec-new/SKILL.md', ...8 项...], 'codex': [...]}
```

用户看到的是一坨转义过的 Python 字面量，而不是"装好了什么、下一步做什么"。同时 `rich>=13` 早已声明为依赖却从未被 import，等于白背了一个依赖。OpenSpec 已经把同类命令的呈现打磨得很干净（分节摘要、逐阶段进度、Created/Refreshed 区分、Getting started 收尾），本变更把那套呈现语汇移植过来。

## What Changes

- 新增共享呈现模块：基于已有依赖 `rich` 实现统一的输出语汇——字形与配色表（`✔` 绿 / `✖` 红 / `⚠` 黄 / `•` 列表项 / `▌` 结构就绪标记）、章节标题（bold）、次要信息（dim）、URL（cyan）、2 空格缩进、以空行分节（不用框线/表格/emoji），并统一处理 `NO_COLOR` 与非 TTY 降级。
- 重写 `loopspec init` 的人类可读输出，对齐 OpenSpec 的成功摘要结构：`Created:` / `Refreshed:` 工具列表 → 聚合计数行（`N skills and M commands in .claude, .codex`）→ `Config: <path> (schema: ...)` 或 `(exists)` → 无适配器工具的 dim 提示（`Commands skipped for: <ids> (no adapter)`）→ bold `Getting started:` + 首条建议命令 → `Learn more:` / `Feedback:` 链接 → 重启 IDE 提示。**不再逐条罗列文件路径**，改为聚合计数（路径明细仍完整保留在 `--json` 里）。
- 新增逐阶段进度反馈：创建 workflow home 骨架、逐个工具写入脚手架时给出进度与完成行（`✔ Setup complete for Claude Code`）；`--json` 模式下 SHALL 完全不输出进度与装饰，保证机器可解析。
- 工具脚手架新增 **Created / Refreshed 区分**：写入前先探测该工具的 skill 文件是否已存在（沿用既有的"配置状态由文件系统判定"规则），据此把工具分入 created / refreshed 两组并在摘要中分别呈现。
- 交互式工具选择列表补上状态标签：已配置的显示 `(configured)`、被选中且已配置的显示 `(refresh)`、自动探测到目录的显示 `(detected)`，让用户知道自己在新建还是在刷新。
- **BREAKING（仅人类可读输出）**：`init` 的人类可读输出不再是 `--json` 载荷的逐字段转印，改为经过取舍的摘要（聚合计数替代路径明细）。`--json` 输出结构与字段保持完全不变，脚本/Agent 不受影响。

## Capabilities

### New Capabilities
- `cli-presentation`: 人类可读输出的统一呈现规范——字形/配色语汇表、章节与缩进结构、进度反馈规则、`--json` 模式下抑制一切装饰、`NO_COLOR` 与非 TTY 环境的降级行为。

### Modified Capabilities
- `loopspec-cli`: `loopspec init` 需求补充人类可读摘要的结构与内容要求（Created/Refreshed、聚合计数、Config 状态、Getting started 收尾）；「全命令支持结构化 JSON 输出」需求需放宽——原文要求两种模式"信息内容保持一致"，而人类模式现在会用聚合计数替代明细，应改为"呈现同一组事实，但人类模式允许聚合与取舍"。
- `tool-scaffolding`: 脚手架结果新增 created / refreshed 分组的上报要求（判定依据仍是写入前 skill 文件是否存在，与既有"不持久化工具选择"规则一致）。

## Impact

- `src/loopspec/` 新增呈现模块（如 `presentation.py`）；`cli.py` 的 `_emit`/`_fail` 与 `init` 输出路径改写；`scaffold.py` 的 `ScaffoldResult` 增加 created/refreshed 分组；`tools_cli.py` 的交互列表补状态标签。
- 依赖：首次真正启用已声明的 `rich`——这同时落地了 `gated-artifact-workflow` design 里遗留的开放问题（rich 作为强制依赖还是可选），结论为强制依赖、仅用于人类可读路径。
- 测试：新增呈现层单测（含 `NO_COLOR`/非 TTY 降级、created vs refreshed 分组）；既有断言 `--json` 结构的 CLI 测试不应改动，正好作为"JSON 契约未变"的回归护栏。
- 非目标（明确排除，避免范围膨胀）：不实现 OpenSpec 的逐帧动画 ASCII logo（OpenSpec 自身在不可动画环境下也只渲染静态帧）；不把交互式选择升级为方向键/可搜索多选（沿用编号列表，仅补状态标签）；不改造 `status`/`instructions`/`rollback` 等其余命令的人类可读输出（留作后续变更，本次只建立可复用的呈现语汇）。
