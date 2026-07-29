## 1. 依赖与测试地基

- [x] 1.1 `pyproject.toml` 的 `dependencies` 新增 `questionary>=2.1`，执行 `uv sync` 并确认锁文件带入 `questionary`/`prompt_toolkit`/`wcwidth` 三个包
- [x] 1.2 **先落地无头测试地基再往下做**（design Migration Plan 第 1 步）：新增 `tests/test_tool_picker.py`，写一条最小用例——用 `prompt_toolkit.input.create_pipe_input()` + `output=DummyOutput()` 驱动一次 `questionary.checkbox()`，断言按键序列能产出预期返回值；确认可行后再进入第 2 组
- [x] 1.3 在 `tests/test_tool_picker.py` 中实现按键序列辅助函数（如 `keys("space","down","space","enter") -> str`），把 `" \x1b[B \r"` 这类字节流的语义显式化，供后续全部选择器用例复用

## 2. 工具注册表扩容（tool-scaffolding）

- [x] 2.1 `ToolSpec` 新增可选字段 `detection_paths: tuple[str, ...] | None = None`（探测路径组，任一存在即视为探测到）
- [x] 2.2 `AI_TOOLS` 扩到 31 项，逐项按 spec 表格填 id / `skills_dir` / 显示名；`github-copilot` 额外声明 `detection_paths`（`.github/copilot-instructions.md`、`.github/instructions`、`.github/prompts`、`.github/agents`、`.github/skills`、`.github/.mcp.json` 等具体路径），不依赖 `.github/` 目录存在性
- [x] 2.3 在 `scaffold.py`（或 `tools_cli.py`）实现 `tool_is_detected(project_path, tool_id)`：有 `detection_paths` 时按其判定，否则按 `skills_dir` 目录是否存在；**不改动** `tool_is_configured()`（已配置判定仍只看 skill 文件，唯一权威）
- [x] 2.4 `tools_cli.tool_status_label()` 改为复用 `tool_is_detected()`，去掉其内部原有的目录存在性判断，保证探测逻辑只有一处
- [x] 2.5 扩展 `tests/test_tool_registry.py`：遍历 31 项断言 `skills_dir` 与显示名均非空、id 唯一、`skills_dir` 无非预期重复；断言未声明显示名的工具回退为 id
- [x] 2.6 新增探测测试：`.cursor/` 存在 → Cursor 已探测；只有 `.github/`（无 Copilot 文件）→ Copilot **未**探测到；存在 `.github/copilot-instructions.md` → Copilot 已探测到；某工具被探测到但无 skill 文件 → 仍归 created 而非 refreshed

## 3. 参数化命令适配器（tool-scaffolding）

- [x] 3.1 实现参数化适配器（字段：`tool_dir` 默认取 `skills_dir`、`subdir`、`namespaced`、`extension`、`body_format`、可选 `nested`），并把 `hyphenated` 统一由 `namespaced` 推导，消除「命令文件名」与「skill 正文里 `/lpsx:x` 转换」两处各自判断的风险
- [x] 3.2 实现三种 `body_format`：`md_frontmatter`（YAML frontmatter + 正文）、`toml`（TOML 键值）、`heading`（`# <命令名>` 开头、无 frontmatter）
- [x] 3.3 按 spec 表格注册全部 28 个适配器：6 个冒号命名空间（`claude`/`codebuddy`/`crush`/`lingma`/`qoder`/`gemini`）、`commands/` 连字符组（`auggie`/`bob`/`cursor`/`factory`/`iflow`/`junie`/`oh-my-pi`/`opencode`/`roocode`/`trae`）、`qwen`（TOML + 连字符）、`costrict`（`.cospec/loopspec/commands/`）、`prompts/` 组（`amazon-q`/`pi`）、`continue`（`.prompt` 扩展）、`github-copilot` 与 `kiro`（`.prompt.md` 双扩展）、`workflows/` 组（`antigravity`/`kilocode`/`windsurf`）、`cline`（`tool_dir=.clinerules`）
- [x] 3.4 `codex` 保留独立适配器实现（用户全局 `$CODEX_HOME/prompts/`，默认 `~/.codex/prompts`），不并入参数化形态
- [x] 3.5 确认 `forgecode`/`kimi`/`vibe` 三个工具**不注册**适配器，沿用既有「只跳过命令文件、skill 照写」规则
- [x] 3.6 **表驱动测试逐个工具断言完整路径字符串**（不抽查）：31 项的 skill 路径 + 28 项的命令路径；`cline`（skill 在 `.cline/`、命令在 `.clinerules/`）、`costrict`、`github-copilot`、`gemini`/`qwen`（TOML）、`continue`（`.prompt`）各单列一条断言
- [x] 3.7 断言 `cline` 的命令正文以 `# ` 标题开头且不含 `---` frontmatter；断言 `gemini`/`qwen` 的正文是 TOML 而非 Markdown frontmatter
- [x] 3.8 断言同一份 `CommandContent` 在冒号命名工具与连字符命名工具下，正文核心指令一致、仅命令引用命名风格不同（沿用 `lpsx-skills` 既有要求）

## 4. 可搜索多选选择器（tool-picker）

- [x] 4.1 在 `tools_cli.py` 实现 `pick_tools(project_path, *, input=None, output=None) -> list[str]`：`questionary.checkbox()` + `use_search_filter=True`、`use_arrow_keys=True`、`use_jk_keys=False`（避免 j/k 与搜索输入冲突）、`instruction` 写明键位、`Choice(title=显示名+状态标注, value=id, checked=预选)`
- [x] 4.2 消息行包含可用工具总数（如 `Select tools to set up (31 available)`）；候选项 title 用显示名 + `(configured)`/`(detected)` 标注
- [x] 4.3 实现预选规则（design D5）：目标根目录下无任何已配置工具 → 预选全部**探测到**的工具，并在选择器上方打一行 `Detected tool directories: <显示名列表> (pre-selected for first-time setup)`；已有配置 → 预选**已配置**的工具；两者皆无 → 不预选
- [x] 4.4 返回值为工具 id 列表，顺序与注册表一致并去重；空选择返回 `[]`（语义等价 `--tools none`）
- [x] 4.5 处理用户中断（design D9）：`ask()` 返回 `None` 或抛 `KeyboardInterrupt` 时按「不配置任何工具」收尾，输出一行说明，不抛栈、不写脚手架
- [x] 4.6 保留既有 `prompt_tools_interactively()` 作为降级实现（供无法启用选择器的场景与既有测试），不删除
- [x] 4.7 选择器测试（全部用 pipe input，无需真终端）：方向键+空格多选返回正确 id；输入字符过滤后勾选生效；不勾选直接回车返回 `[]`；首次 setup 预选探测到的工具且提示行出现；已配置过时预选已配置项；预选项可被空格取消；中断按空列表收尾
- [x] 4.8 断言候选项 title 全部来自注册表常量（遍历 31 个显示名断言不含控制字符），对应 design D8

## 5. 欢迎屏与 init 接入（init-welcome / cli-presentation）

- [x] 5.1 `presentation.py` 新增静态色块 logo 渲染接口，字形与配色进既有语汇表，遵循 ASCII 降级与 `NO_COLOR`/非 TTY 降级；**不提供**任何多帧/循环/定时重绘接口
- [x] 5.2 `presentation.py` 新增 `render_welcome(presenter, ...)`：标题 + 副标题 → `This setup will configure:` 列表（Agent Skills、`/lpsx:*` slash commands）→ `Quick start after setup:` 命令表（`/lpsx:new` / `/lpsx:continue` / `/lpsx:apply` 各带一句用途）→ `Press Enter to select tools...`
- [x] 5.3 `cli.py` 的 `init` 实现 design D3 的**单一判定**：`未显式传 --tools and is_interactive() and not as_json` → 渲染欢迎屏 + 等待回车 + 启动选择器；三者任一不成立 → 走既有路径。判定结果只计算一次，不允许出现「渲染了欢迎屏却没有选择器」的中间态
- [x] 5.4 `tests/test_presentation.py` 补用例：欢迎屏分节顺序与内容；quick start 的命令名与实际生成的命令文件对得上；logo 在非 TTY 下无 ANSI 序列、在 ASCII 编码下降级；呈现模块公开接口中不存在动画类接口

## 6. 契约护栏与回归

- [x] 6.1 断言 `--json` 模式下 stdout 仍可整体 `json.loads()`，且不含欢迎屏任何分节、不含选择器输出、不含 ANSI 序列
- [x] 6.2 断言显式 `--tools claude`（人类可读模式）下输出不含欢迎屏分节、不启动选择器
- [x] 6.3 断言非交互环境下未传 `--tools` 时不渲染欢迎屏、不启动选择器、等价 `--tools none` 且命令成功
- [x] 6.4 确认既有 `tests/test_cli.py` 的 JSON 断言与 `tests/test_tools_arg.py` 的 `--tools` 解析断言**未经修改**即通过（契约零变化的证据）
- [x] 6.5 `--tools all` 现在会写 31 个工具的文件：确认相关测试使用 tmp 目录且隔离 `CODEX_HOME`，不污染开发者真实 `~/.codex/prompts/`

## 7. 收尾

- [x] 7.1 更新 `README.md`：补欢迎屏与选择器的实际形态示例，说明「显式 `--tools` / 非 TTY / `--json` 三种情况下不出现交互」
- [x] 7.2 运行 `make lint`（`ruff check src tests` + `mypy src`）无告警；注意 `questionary`/`prompt_toolkit` 若缺类型标注需按既有 mypy 配置处理
- [x] 7.3 运行 `make test` 全绿（改动前基线 268 个）
- [x] 7.4 抽样人工验收（隔离 `CODEX_HOME`）：TTY 下真实跑一次交互式 `init` 完整走完欢迎屏 → 选择器 → 摘要；再各跑一次 `--json`、显式 `--tools`、重定向到文件（需 `env -u FORCE_COLOR`，否则 rich 会强制终端模式），确认三者都不出现交互
- [x] 7.5 抽样验收落盘正确性：选 `cline`、`gemini`、`github-copilot`、`costrict`、`codex` 五个特例工具真实生成一次，肉眼确认文件路径、扩展名与正文格式符合 spec 表格
