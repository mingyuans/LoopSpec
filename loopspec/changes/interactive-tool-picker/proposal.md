## Why

`improve-init-display` 把 `init` 的**摘要输出**打磨到了 OpenSpec 的水准，但**交互本身**没动——工具选择仍是「打印编号列表 + 读一行逗号分隔输入」：

```
▌ Workflow home ready at loopspec
Which AI tools should loopspec scaffold skills/commands for?
  1) claude
  2) codex
  ...
Enter comma-separated numbers, 'all', or 'none':
> 1
```

用户对照 OpenSpec 提出的目标形态是两件事：一是 `init` 开场的**欢迎屏**（框定这次 setup 会配置什么、给出 setup 后的 quick start、`Press Enter to select tools...` 收口）；二是**可搜索多选器**（方向键导航、空格勾选、检测到的目录自动预选、显示名而非裸 id、搜索过滤与分页）。当前实现里连工具的显示名都没进列表（只显示 `claude`/`codex` 这种 id），5 个工具的注册表也撑不起搜索与分页。

**这两点都是 `improve-init-display` 明确冻结为 Non-Goal 的决定**（「不实现动画 logo，连静态 banner 也不做」、「不把交互式选择升级为方向键 + 可搜索多选，理由是需要裸终端输入处理或引入新依赖」）。那轮的取舍前提是「不为次要交互引入新依赖」；本轮用户把这套交互本身定为目标，前提随之失效，因此需要一个新 change 显式推翻，而不是在已签核的 change 上偷改。

## What Changes

- **引入 `questionary` 作为交互依赖**（已实测 2.1.1：`checkbox()` 提供 `use_search_filter`、`use_arrow_keys`、`instruction`、`initial_choice`，`Choice(checked=True)` 支持预选；安装带入 `prompt_toolkit` + `wcwidth`，共 3 个包）。这是对 `improve-init-display` 决策 D7「不为次要交互引入新依赖」的**显式推翻**：交互不再是次要项，而是本变更的目标本身。`questionary` 只允许出现在交互路径，`--json` 路径与非 TTY 路径不得依赖它。
- **`init` 新增欢迎屏**：静态文案（标题 + 副标题 → 「This setup will configure:」两条 → 「Quick start after setup:」三条 `/lpsx:*` 命令及其说明 → `Press Enter to select tools...`）加一个**静态色块 logo**（不做逐帧动画）。仅在人类可读且需要交互选择时渲染；`--json`、`--tools` 已显式给定、非 TTY 三种情况下都不出现。
- **工具选择改为可搜索多选器**：方向键/`↑↓` 导航、空格勾选、输入即过滤、回车确认、底部提示行与 `(n available)` 计数；列表项显示**工具显示名**（`Claude Code` 而非 `claude`），并保留 `improve-init-display` 已落地的 `(configured)`/`(detected)` 状态标签。检测到目录的工具在**首次 setup 时自动预选**（对照 OpenSpec 的 `Detected tool directories: ... (pre-selected for first-time setup)`）。
- **工具注册表扩容到 OpenSpec 量级**：从 5 个扩到 31 个（Amazon Q Developer、Antigravity、Auggie、Bob Shell、Claude Code、Cline、Codex、ForgeCode、CodeBuddy、Continue、CoStrict、Crush、Cursor、Factory Droid、Gemini CLI、GitHub Copilot、iFlow、Junie、Kilo Code、Kimi CLI、Kiro、Lingma、Mistral Vibe、Oh My Pi、OpenCode、Pi、Qoder、Qwen Code、RooCode、Trae、Windsurf），每个带 `skills_dir` 与显示名；GitHub Copilot 额外需要**多路径探测**（`.github/` 下若干具体文件/目录任一存在即视为检测到），不能只看目录是否存在。
- **命令适配器按形态归类后批量补齐**：调研 OpenSpec 的 29 个适配器后归纳为几种参数化形态——`<dir>/commands/lpsx-<verb>.md`（多数）、`<dir>/prompts/lpsx-<verb>.md`、`<dir>/workflows/lpsx-<verb>.md`，加 4 个特例（Claude 的 `commands/lpsx/<verb>.md` 冒号命名空间、Gemini 的 `commands/lpsx/<verb>.toml` TOML 正文、Cline 的 `.clinerules/workflows/` 且正文用 `# 标题` 无 frontmatter、GitHub Copilot 的 `.prompt.md` 双扩展名），Codex 继续写用户全局 `$CODEX_HOME/prompts/`。没有适配器的工具沿用既有规则：只跳过命令文件、skill 文件照写。
- **非 TTY 与降级路径保持可用**：拿不到真实终端时（重定向、CI、`--json`）SHALL 退回现有的编号列表或 `none` 语义，不得因为引入 `questionary` 而在非交互环境报错或阻塞。
- **BREAKING（仅交互体验）**：交互式 `init` 的选择方式由「输入编号」变为「方向键 + 空格」。`--tools` 参数语义、`--json` 输出结构、脚手架落盘规则均不变。

## Capabilities

### New Capabilities
- `init-welcome`: `init` 欢迎屏的内容契约与渲染条件——静态文案的分节结构（configure 清单、quick start 命令表、Press Enter 收口）、静态色块 logo、以及「仅在人类可读且将进入交互选择时渲染」的触发条件与各类降级行为。
- `tool-picker`: 可搜索多选工具选择器的行为契约——键位（导航/勾选/过滤/确认）、显示名与状态标签的呈现、检测目录的首次预选规则、可用计数与分页、确认后的返回值语义，以及非 TTY/无法交互时的降级路径。

### Modified Capabilities
- `tool-scaffolding`: 工具注册表由 5 个扩到 31 个，每项新增显示名；新增「多路径探测」的检测规则（GitHub Copilot）；命令适配器的形态归类与 4 个特例的落盘规则。
- `loopspec-cli`: `loopspec init` 的需求补充欢迎屏与可搜索多选器的交互要求，并明确 `--tools` 显式给定时跳过交互、非 TTY 时降级的行为。
- `cli-presentation`: 呈现语汇需容纳静态 logo 色块与交互组件；同时明确 `questionary`/`prompt_toolkit` 的输出不经由 `presentation.py` 的转义出口，因此工具显示名等插值内容需要独立的安全约束（承接 D10 的同类风险）。

## Impact

- 依赖：`pyproject.toml` 新增 `questionary>=2.1`（实测带入 `prompt_toolkit`、`wcwidth`）。这推翻了 `improve-init-display` 的 D7 取舍，需在本轮 design 中重新论证并由 `security` 门禁复核依赖来源。
- `src/loopspec/tool_registry.py`：`AI_TOOLS` 扩到 31 项并补显示名；新增可选的多路径探测字段；`COMMAND_ADAPTERS` 按归纳出的参数化形态重写并补齐 29 个适配器。
- `src/loopspec/tools_cli.py`：新增基于 `questionary` 的多选器，保留编号列表作为降级路径；预选逻辑复用 `scaffold.tool_is_configured()` 与目录探测。
- `src/loopspec/presentation.py`：新增欢迎屏渲染与静态 logo 色块。
- `src/loopspec/cli.py`：`init` 在进入交互选择前渲染欢迎屏。
- 测试：多选器需要可注入的输入/输出以便非交互测试（`questionary` 支持传入 `prompt_toolkit` 的 `input`/`output`，需在 design 中确认具体注入方式）；注册表扩容需要覆盖「每个工具的 skill 路径与命令路径」的表驱动测试；既有 `--json` 断言与 `--tools` 解析测试作为契约护栏不应改动。
- 文档：README 的 `init` 示例需补欢迎屏与多选器的形态说明。
- 非目标：不做逐帧动画 logo；不改 `--tools` 的参数语法；不把这套交互推广到 `status`/`instructions` 等其余命令；不为 31 个工具逐一做人工验收（改为表驱动自动化断言 + 抽样人工验收）。
