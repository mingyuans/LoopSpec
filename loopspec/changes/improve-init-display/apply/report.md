# Implementation Report

## Tasks Implemented

全部 6 组 29 项，按 Migration Plan 的顺序落地（`presentation.py` → `scaffold.py` → `init` 渲染器 → 交互标签 → 契约护栏 → 收尾）。

- **第 1 组 呈现层基础（1.1–1.8）**：新增 `src/loopspec/presentation.py`。字形表 `✔ ✖ ⚠ • ▌` 与 ASCII 降级 `ok x ! - |`，按 `console.file.encoding` 能否编码这些字形自动选择；语义化辅助 `heading()`/`success()`/`failure()`/`warning()`/`ready()`/`dim()`/`bullet()`/`link()`/`indented()`；`Console` 可注入；`stage()` 在 TTY 下用 `console.status()` 转圈、非 TTY 下直接留完成行。**D10 采用「构造 `Text` 对象」方案而非 `escape()`**：所有辅助返回 `rich.text.Text`，rich 对 `Text` 不做 markup 解析，因此转义是结构性的、调用方无从绕过，也不存在 security 门禁提醒的重复转义问题；控制字符统一改写成可见的 `\xNN`。模块 docstring 写明了「仅人类可读路径可用」与所选方案，`render_init_summary()` 签名不含 `as_json`。
- **第 2 组 Created/Refreshed（2.1–2.3）**：`scaffold.py` 新增 `tool_is_configured()`，`scaffold_tools()` 在写第一个文件**之前**据此把工具分入 `ScaffoldResult.created` / `.refreshed`（**纯新增字段**，既有 `written_files`/`skipped_command_generation` 未改名未删除）。
- **第 3 组 init 摘要（3.1–3.8）**：`render_init_summary()` 按 D4 固定行序渲染；聚合计数行 `N skills and M commands in .claude, .codex`（skill 数按路径是否以 `SKILL.md` 结尾统计）；`Config:` 行区分 `(schema: ...)` 与 `(exists)`；链接用手工空格对齐（`Learn more: ` / `Feedback:   `）。`cli.py` 的 `init` 在人类模式走渲染器、JSON 模式仍走 `_emit()`，**`_emit()` 本身未改动**；进度接入为 `▌ Workflow home ready at <path>` 与逐工具 `✔ Setup complete for <显示名>`（为此把 `scaffold_tools` 改成逐工具调用再合并结果）。`ToolSpec` 新增 `display_name` 与 `label` 属性（`claude` → `Claude Code` 等，带 id 兜底）。3.8 已确认：渲染器全部经由 `Presenter` 辅助，无一处 `console.print(f"...")` 直拼用户可控内容。
- **第 4 组 交互标签（4.1–4.3）**：`prompt_tools_interactively(project_path=None, ...)` 为每项加 `(configured)`（已有 skill 文件）/`(detected)`（有目录无 skill 文件）/无标签；解析完选择后额外打印 `Selected: claude (refresh), codex`，把「即将覆盖谁」在写入前说清楚。状态探测复用第 2 组的 `tool_is_configured()`，无第二套判定。`project_path=None` 时不加标签，既有 4 个调用点无需改动。
- **第 5 组 契约护栏（5.1–5.4）**：`tests/test_cli.py` 新增 9 条——`--json` 的 stdout 整体可 `json.loads()` 且无 ANSI/进度行；人类输出不含 `scaffoldedFiles` 等字段名与 `{'`/`['` 容器 repr；不含任何文件路径；Created→Refreshed 切换；Config 新建/已存在两态；收尾段落与链接；无工具时不打重启提示；含 `[red]` 的路径原样输出；被聚合掉的明细仍可从 `--json` 完整取回。
- **第 6 组 收尾（6.1–6.3）**：README 贴了真实输出示例并说明聚合/降级行为；`make lint` + `make test` 全绿；隔离环境人工验收 6 项全过（见下）。

## Files Changed

新增：
- `src/loopspec/presentation.py`
- `tests/test_presentation.py`（27 条）

修改：
- `src/loopspec/cli.py`（`init` 人类模式渲染、逐工具进度、`DEFAULT_SCHEMA_NAME`/`PROJECT_URL`/`ISSUES_URL`、`_display_path`/`_scaffold_with_progress`/`_init_counts`；JSON 载荷新增 `createdTools`/`refreshedTools`）
- `src/loopspec/scaffold.py`（`tool_is_configured()`、`ScaffoldResult.created`/`.refreshed`）
- `src/loopspec/tool_registry.py`（`ToolSpec.display_name` + `label`）
- `src/loopspec/tools_cli.py`（`tool_status_label()`、`_echo_selection()`、`prompt_tools_interactively(project_path=...)`）
- `README.md`（人类输出示例 + 聚合与降级说明）
- `tests/test_cli.py`、`tests/test_scaffold.py`、`tests/test_tools_arg.py`（各自新增用例，既有 JSON 断言未改动）

## Tests and Checks

- `make test`：**268 passed**（改动前基线 221）。新增 47 条：`test_presentation.py` 27、`test_cli.py` 9、`test_tools_arg.py` 7、`test_scaffold.py` 5（含既有 5 条不变）。
- `make lint`：`ruff check src tests` All checks passed；`mypy src` Success: no issues found in 22 source files。（过程中 ruff 报过一次 `I001` 导入排序，已 `--fix`。）
- 5.3 的证据：`tests/test_cli.py` 中既有的 JSON 断言用例**一行未改**即全部通过，本次只在文件末尾追加新用例。
- 6.3 隔离验收（`CODEX_HOME` 指向临时目录）：
  1. 首次 `init --tools claude,codex` → `Created: Claude Code, Codex` ✓
  2. 再跑一次同一命令 → `Refreshed: Claude Code, Codex` ✓
  3. `NO_COLOR=1` 且取消 `FORCE_COLOR` → 输出中 ESC 序列计数 **0** ✓
  4. `PYTHONIOENCODING=ascii` → `| Workflow home ready at ...` / `ok Setup complete for Claude Code` ✓
  5. `--project-root '<tmp>/[red]proj'`，以及把 home 直接放进该目录 → `▌ Workflow home ready at .../[red]proj/wf` 与 `Config: .../[red]proj/wf/config.yaml (schema: secure-spec-driven)` **路径原样显示、无 MarkupError**，且文件确实落在带方括号的目录里 ✓
  6. 开发者真实的 `~/.codex/prompts/` 文件 mtime 仍是本次验收之前的时间戳，未被污染 ✓

## Deviations from the Design

- **D10 的两个可选方案选了后者**：统一构造 `Text` 对象并让 rich 原样渲染，而非在辅助函数内部调用 `rich.markup.escape()`。design 允许二选一，选这个是因为它天然避免 `security/pass.md` Notes 里提醒的「转义只能做一次」陷阱——`Text` 没有二次解析的机会，所以嵌套调用不会出现字面 `\[`；`test_presentation.py` 里保留了一条针对该场景的断言。
- **`init` 的 JSON 载荷新增了 `createdTools`/`refreshedTools` 两个键**。design 承诺的是「既有字段名与结构零变化」，纯新增不破契约（既有 JSON 断言全绿即证），这样 Agent 也能拿到与人类摘要同一组事实。
- **`scaffold_tools()` 由「一次传入全部工具」改为在 `cli.py` 里逐工具调用后合并**。design 只要求逐工具进度行，没规定调用形态；逐工具调用是拿到「每个工具各自完成」时机的最小改法，`scaffold_tools()` 自身签名与语义未变。
- **`getting_started` 会在 home 不是默认 `./loopspec` 时带上 `--home <path>`**。design 只写了 `loopspec new <change-name>`；照抄会给出一条在非默认 home 下跑不通的建议命令，故补上后缀。

## Follow-Ups

- `NO_COLOR=1` 下 rich 仍会输出 `\x1b[1m` 这类**粗体**序列（它只剥离颜色，不剥离样式）。这符合 spec 措辞「不含颜色转义序列」与 D1「依赖 rich 原生行为」，但若将来要求「`NO_COLOR` 下完全无 ANSI」，需要显式关掉样式。
- 本环境导出了 `FORCE_COLOR=1`，rich 会据此强制终端模式——这会让「重定向到文件」看起来仍带 spinner 控制符。验收时需 `env -u FORCE_COLOR` 才能观察到真实的非 TTY 行为，这是环境因素而非代码问题。
- `_emit()` 与 `_fail()` 仍是逐字段转印（含错误输出）。按 D7/Non-Goals 本次刻意不动，其余 8 个命令迁移到这套语汇留作后续变更。
- `security/pass.md` 与 `state.md` 里 round 1 遗留的「25 项」计数：`state.md` 已按 approval 的前置条件更正为 29 项，`security/pass.md` 作为已出具的门禁记录保留原文未改。
