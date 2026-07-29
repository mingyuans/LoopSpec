# Implementation Report

## Tasks Implemented

全部 39 项，按 tasks.md 声明的顺序（第 1 组的「先落地测试地基」是签核点 1 的硬约束，已遵守）。

**第 1 组 — 依赖与测试地基（3 项）**
- 1.1 `pyproject.toml` 加 `questionary>=2.1`，`uv sync` 带入 `questionary==2.1.1`、`prompt-toolkit==3.0.53`、`wcwidth==0.8.2`——与 `security/pass.md` 核验过的版本完全一致。
- 1.2 新建 `tests/test_tool_picker.py`，`test_pipe_input_drives_questionary_checkbox` 直接对 `questionary` 断言（而非经 loopspec 自己的封装），确认无头驱动可行后才进入第 2 组。
- 1.3 `keys("space","down","enter")` 辅助函数 + `KEYS` 映射表，把 `" \x1b[B\r"` 这类字节流语义化；后续 8 条选择器用例全部复用它。

**第 2 组 — 注册表扩容（6 项）**
- 2.1 `ToolSpec` 加 `detection_paths: tuple[str, ...] | None = None`。
- 2.2 `AI_TOOLS` 扩到 31 项，逐项按 spec 表格填 id/`skills_dir`/显示名；`github-copilot` 声明 6 条 `detection_paths`。
- 2.3 `tool_is_detected()` 实现于 `tools_cli.py`（**不是** `scaffold.py`，见 Deviations 第 1 条）；`tool_is_configured()` 未改一行。
- 2.4 `tool_status_label()` 改为复用 `tool_is_detected()`，删掉其内部原有的 `(project_path / skills_dir).is_dir()` 判断——探测逻辑现在只有一处。
- 2.5 `tests/test_tool_registry.py` 扩为遍历 31 项断言 id 一致性、`skills_dir` 非空且唯一、显示名非空，外加显示名回退为 id 的断言。
- 2.6 探测测试：`.cursor/` → 已探测；只有 `.github/workflows/ci.yml` → Copilot **未**探测到；6 条 `detection_paths` 各自单独参数化断言；`test_detected_but_unconfigured_tool_is_created_not_refreshed` 落在 `test_scaffold.py`，守住 D4 的边界。

**第 3 组 — 参数化命令适配器（8 项）**
- 3.1 `ProjectCommandAdapter`，字段 `tool_dir`/`subdir`/`nested`/`namespaced`/`extension`/`body_format`；`hyphenated` 由 `namespaced` **推导**（`@property`），消除两处各自判断的风险。为此把 `ToolCommandAdapter` Protocol 的 `hyphenated` 从 `ClassVar[bool]` 改为只读 `@property`，使 ClassVar 与 property 两种实现都能满足它。
- 3.2 三种 `body_format`：`md_frontmatter`、`toml`、`heading`，经 `FORMATTERS` 表分派。
- 3.3 28 个适配器全部注册，按形态分组并各带注释。
- 3.4 `codex` 保留独立 `CodexCommandAdapter`（`$CODEX_HOME/prompts/`），未并入参数化形态。
- 3.5 `forgecode`/`kimi`/`vibe` 不注册适配器，`test_tools_without_an_adapter_are_exactly_the_three_expected` 把这条钉住。
- 3.6 `SKILL_PATHS`（31 条）与 `COMMAND_PATHS`（27 条项目内 + codex 单列）两张表，逐项断言**完整路径字符串**；三条「表必须覆盖注册表」的元断言防止表本身漏项。
- 3.7 `cline` 正文以 `# ` 开头且不含 `---`；`gemini`/`qwen` 正文为 TOML；额外用 `tomllib` 实际解析验证可读，并断言正文里的三引号被转义（否则会提前终止多行字符串）。
- 3.8 同一份 `CommandContent` 在两种命名风格下正文核心指令一致；外加 `test_hyphenated_flag_agrees_with_the_command_filename` 遍历 28 个适配器，断言 `hyphenated` 与实际文件名前缀始终一致。

**第 4 组 — 可搜索多选选择器（8 项）**
- 4.1 `pick_tools(project_path, *, input=None, output=None, print_fn=print)`，`use_search_filter=True`/`use_arrow_keys=True`/`use_jk_keys=False`/`instruction`/`Choice(title=显示名+状态标注, value=id, checked=预选)`。
- 4.2 消息行 `Select tools to set up (31 available)`，计数由 `len(AI_TOOLS)` 推导而非写死。
- 4.3 `_preselected()` 实现 D5 分流，首次 setup 打出 `Detected tool directories: ... (pre-selected for first-time setup)`。
- 4.4 返回值按注册表顺序去重；空选择返回 `[]`。
- 4.5 `KeyboardInterrupt` → 打印 `INTERRUPT_NOTICE` 并返回 `[]`；`if not answer` 同时兜住 `None`。
- 4.6 `prompt_tools_interactively()` 完整保留（其 10 条既有测试未改动即通过）。
- 4.7 9 条选择器用例，全部 pipe input：多选、过滤后勾选、空选、注册表顺序、首次预选 + 提示行、预选可取消、二次运行按已配置预选、无探测无配置不预选、Ctrl+C 收尾。
- 4.8 遍历 31 个显示名断言无控制字符、无标记构造（`[]`/`<>`），并断言候选项 title 不含路径。

**第 5 组 — 欢迎屏与 init 接入（4 项）**
- 5.1 `LOGO_UNICODE`/`LOGO_ASCII`（各 3 行、统一 39 列）进语汇表，`Presenter.logo_lines()` 返回 `list[Text]`；`logo` 配色进 `STYLES`；ASCII 降级并入既有 `encoding_supports` 探测（采样串现在含 logo 字符）。无任何多帧/重绘接口。
- 5.2 `render_welcome(presenter)`：logo → 标题/副标题 → `This setup will configure:` → `Quick start after setup:`（命令列对齐）→ `Press Enter to select tools...`。
- 5.3 `init` 的单一判定：`tools is None and presenter is not None and is_interactive()`，唯一分支调用 `_welcome_and_pick()`——欢迎屏与选择器封在同一个函数里，结构上无法只出现一个。
- 5.4 12 条呈现测试：分节顺序、configure 清单、quick start 命令与用途、**quick start 只列 init 实际写入的命令**、结尾指向选择器、logo 只渲染一次且无光标控制、ASCII 降级、有终端时才带颜色、两版行数与行宽一致、公开接口无动画类名称。

**第 6 组 — 契约护栏（5 项）**
- 6.1 `--json` 整体 `json.loads()` 通过，且不含欢迎屏 5 个标记、选择器 3 个标记、ANSI 序列。
- 6.2 显式 `--tools claude` 无交互（用 monkeypatch 让 `pick_tools` 一旦被调用就 `pytest.fail`）；`all`/`none` 各参数化一条同样断言。
- 6.3 非交互未传 `--tools`：无欢迎屏、无选择器、不写脚手架、命令成功且 `Config:` 仍在。
- 6.4 见下方 Tests and Checks 的护栏证据。
- 6.5 `isolated_codex_home` 改为 `autouse=True`。

**第 7 组 — 收尾（5 项）**
- 7.1 README 新增「Picking tools interactively」小节（含真实渲染示例），并改写 Quick start 里"支持 5 个工具 / 编号提示"的过时描述。
- 7.2/7.3 见 Tests and Checks。
- 7.4/7.5 真实执行，见 Tests and Checks 的「人工验收」。

## Files Changed

**源码**
- `src/loopspec/tool_registry.py` — `ToolSpec.detection_paths`；`AI_TOOLS` 5 → 31；`ToolCommandAdapter.hyphenated` 改只读 property；新增 `ProjectCommandAdapter`、`FORMATTERS` 与三个 `_format_*`；`ClaudeCommandAdapter`/`HyphenatedProjectCommandAdapter` 被参数化形态取代；`COMMAND_ADAPTERS` 5 → 28。
- `src/loopspec/tools_cli.py` — 新增 `tool_is_detected()`、`_preselected()`、`pick_tools()`、`PICKER_INSTRUCTION`、`INTERRUPT_NOTICE`；`tool_status_label()` 改为复用探测函数。
- `src/loopspec/presentation.py` — `LOGO_UNICODE`/`LOGO_ASCII`、`STYLES["logo"]`、`Presenter.logo`/`logo_lines()`、`WELCOME_*` 常量、`render_welcome()`。
- `src/loopspec/cli.py` — `_welcome_and_pick()`；`init` 的单一判定；导入 `render_welcome`/`pick_tools`（`prompt_tools_interactively` 不再由 cli 导入，函数本身保留）。

**测试**
- `tests/test_tool_picker.py`（新增）
- `tests/test_tool_registry.py`
- `tests/test_presentation.py`
- `tests/test_cli.py`
- `tests/test_scaffold.py`

**其他**
- `pyproject.toml`（`questionary>=2.1`）、`uv.lock`、`README.md`
- `loopspec/changes/interactive-tool-picker/tasks.md`（39 个 checkbox）

## Tests and Checks

`make test` — **505 passed in 5.37s**（改动前基线 268，净增 237）。
`make lint` — `ruff check src tests`：`All checks passed!`；`mypy src`：`Success: no issues found in 22 source files`。`questionary`/`prompt_toolkit` 未产生任何缺失类型标注的告警，既有 mypy 配置无需调整。

**契约护栏证据（签核点 3）**
- `tests/test_tools_arg.py`：`git diff HEAD` 输出为**空**——零改动，16 个测试全绿，其中 10 条覆盖 `prompt_tools_interactively` 的降级路径。
- `tests/test_cli.py`：相对本次实现起点，全文只有**一行**被删除：
  `-    assert set(data["toolsConfigured"]) == {"claude", "codex", "opencode", "cursor", "windsurf"}`
  改为 `assert set(data["toolsConfigured"]) == set(AI_TOOLS)`。它断言的是「注册表里有哪些工具」，而注册表扩容正是本变更批准的目标（`specs/tool-scaffolding` 的 MODIFIED 明确要求 31 项）；它不属于签核点 3 所指的 `--tools` 语义、`--json` 结构或落盘规则。改后它断言的是测试自己名字所声称的「覆盖每个已注册工具」，日后扩容不必再动它。其余 JSON 字段名与结构断言全部原样通过。

**人工验收（task 7.4，真实执行）**
没有真终端可用，所以用 stdlib `pty` 建了一个真实伪终端跑完整交互，而不是跳过这一项。项目根预置 `.cursor/`，按键序列为 `Enter` → `claude` → `Space` → `Enter`：

```
exit code: 0
  OK   logo rendered
  OK   welcome title
  OK   configure list
  OK   quick start
  OK   press enter prompt
  OK   detected pre-selection      (Detected tool directories: Cursor (pre-selected for first-time setup))
  OK   picker with count           (Select tools to set up (31 available))
  OK   keybinding hint             (Space toggle)
  OK   summary rendered
```

摘要输出 `Created: Claude Code, Cursor` / `8 skills and 8 commands in .claude, .cursor`——预选的 Cursor 保留、过滤加选的 Claude 生效，正是 D5 的语义。（我脚本里最初写了一条「`.cursor` 应保持未配置」的断言并报 FAIL，那是脚本预期写错：我从未按空格取消 Cursor 的预选，两个工具都被配置才是正确行为。）

另外三条非交互路径各跑一次：
- `--json`：整体 `json.loads()` 通过，`toolsConfigured: []`，无欢迎屏/选择器/ANSI。
- 显式 `--tools claude`：无交互标记，`Created: Claude Code` 正常。
- 未传 `--tools` + stdout 重定向到文件（`env -u FORCE_COLOR`）：无交互、无 ANSI，项目根下无任何工具目录——等价 `--tools none`。

**落盘验收（task 7.5，真实执行）** `--tools cline,gemini,github-copilot,costrict,codex`（隔离 `CODEX_HOME`）：
- `cline` — skill 在 `.cline/skills/`，命令在 `.clinerules/workflows/lpsx-*.md`，正文首行 `# /lpsx-new` 且无 frontmatter；`.cline/workflows/` **不存在**（未误写）。
- `gemini` — `.gemini/commands/lpsx/new.toml`，正文 `description = ...` / `prompt = """..."""`。
- `github-copilot` — `.github/prompts/lpsx-new.prompt.md`，md frontmatter + 连字符命令名。
- `costrict` — `.cospec/loopspec/commands/lpsx-new.md`。
- `codex` — 命令只在 `$CODEX_HOME/prompts/`；`.codex/commands/` **不存在**。

**未污染真实目录**：`find ~/.codex/prompts -name "lpsx-*" -newermt "-25 minutes"` 全程为空；现存文件时间戳为本次开工前。临时验收目录已清理。

## Deviations from the Design

三处，都记录在此而非默默带过。

1. **`tool_is_detected()` 放在 `tools_cli.py` 而不是 `scaffold.py`。** task 2.3 写的是「`scaffold.py`（或 `tools_cli.py`）」，两者都在授权范围内；选后者是因为 D4 的边界是「探测不参与 created/refreshed 分组」，而把函数放在 `scaffold.py` 之外让这条从结构上成立——scaffold 根本看不到它，而不是靠注释约束。

2. **欢迎屏 quick start 列 `archive` 而非 `apply`。** `specs/init-welcome` 与 task 5.2 都要求覆盖 `new`/`continue`/`apply`，但 loopspec 生成的命令是 `new`/`continue`/`archive`/`bulk-archive`——**没有 `/lpsx:apply`**（`apply` 是 schema 的节点名，不是 slash 命令；`apply` 阶段由 `/lpsx:continue` 驱动）。`/lpsx:apply` 是从 OpenSpec 截图（其确有 `/opsx:apply`）照搬时的疏漏。同一份 spec 另有一条更强的独立要求兼独立 Scenario：「命令名 SHALL 与实际生成的 slash 命令一致 …… SHALL NOT 展示一个用户实际敲不出来的命令名」。按后者实施，并加 `test_welcome_quick_start_only_names_commands_init_actually_writes` 把两者永久绑定。这不是在猜——spec 自己给了裁决规则；但它是一处与 spec 字面文本的偏离，需要复核。

3. **`windsurf` 的命令目录由 `.windsurf/commands/` 改为 `.windsurf/workflows/`。** 这是 `specs/tool-scaffolding` 表格明确要求的（`antigravity`/`kilocode`/`windsurf` 同属 `workflows/` 组），但它改变了 `improve-init-display` 时期的既有行为，因此既有测试 `test_hyphenated_tools_command_path_and_naming`（把 windsurf 与 opencode/cursor 一起断言为 `commands/`）被表驱动的完整路径断言取代。对已经用 loopspec 配过 Windsurf 的用户，旧的 `.windsurf/commands/lpsx-*.md` 不会被自动清理——见 Follow-Ups。

此外两处非偏离但值得记录的实现选择：`ToolCommandAdapter.hyphenated` 由 `ClassVar[bool]` 改为只读 `@property`（为让 `ProjectCommandAdapter` 能推导它，同时不破坏 `CodexCommandAdapter` 的类属性写法）；`isolated_codex_home` fixture 改为 `autouse=True`（task 6.5 要求「不污染开发者真实 `~/.codex/prompts/`」，逐个测试记住 fixture 迟早会漏一个，而漏掉的后果是文件出现在用户 home 目录）。

## Follow-Ups

均为非阻塞，本变更有意不做：

- **旧路径遗留文件无清理机制。** `windsurf` 命令目录变更后，此前配置过 Windsurf 的项目会同时存在 `.windsurf/commands/lpsx-*.md`（陈旧）与 `.windsurf/workflows/lpsx-*.md`（新）。脚手架的既定语义是「无条件覆盖」而非「同步删除」，加清理逻辑超出本变更范围，但值得一个后续变更处理——否则用户会看到两套命令。
- **`security/pass.md` 的 4 条非阻塞观察**原样保留：`CODEX_HOME` 未校验（既有行为）、适配器路径常量约束（已由 tasks 3.6 的完整路径断言事实覆盖）、非中断类异常下的终端状态恢复、依赖版本下界靠 `uv.lock` 固定。
- **delta 尚未应用到 `openspec/specs/`。** 与 `improve-init-display` 同一个悬而未决的问题（loopspec 没有 delta → 主 spec 同步能力）；两轮的 delta 必须按 `improve-init-display` → `interactive-tool-picker` 的顺序应用，反序会丢掉摘要相关段落。
- **`prompt_tools_interactively()` 现在没有生产调用方**，只被测试使用。按 tasks 4.6 明确要求保留（作为降级实现），但它与 `pick_tools()` 的长期共存关系值得日后重新评估。
