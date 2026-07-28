## Why

目前 `loopspec init` 只初始化 workflow home（`config.yaml`/`schemas/`/`changes/`），用户如果想让 Claude Code、Codex、OpenCode 等 AI 编程工具直接会用 `loopspec` 主循环（`new → status → instructions → rollback → archive`），必须自己手写 skill/slash command 文件，体验割裂。OpenSpec 项目已经验证了一套成熟做法：`init` 时询问用户在用哪些 AI 工具，按工具规则把对应的 skill/命令文件写入 `.claude/`、`.codex/`、`.opencode/` 等目录，让用户装完就能直接用 `/lpsx:new` 之类的 slash command 驱动 `loopspec`。本变更把这套机制移植过来，缩小到 loopspec 实际需要的范围。

## What Changes

- 新增 AI 工具注册表：内置支持 Claude Code（`claude`）、Codex（`codex`）、OpenCode（`opencode`）、Cursor（`cursor`）、Windsurf（`windsurf`）五个工具，每个工具声明 `skillsDir`（如 `.claude`）与可选的命令适配器（`ToolCommandAdapter`：给定 command id 返回文件路径 + 格式化后的文件内容）；注册表按工具 id 索引，便于后续扩展新工具。
- 新增 4 个内置 skill/命令模板，与 `loopspec` CLI 命令一一对应：`loopspec-new`（→ `loopspec new` + `loopspec status`）、`loopspec-continue`（→ 读取 `loopspec status` 的 `nextSteps` 并执行其中指定的命令）、`loopspec-archive`（→ `loopspec archive`）、`loopspec-bulk-archive`（→ `loopspec bulk-archive`）；每个模板产出一份 SKILL.md 正文，供所有工具复用（"一份正文，多个工具适配"模式）。
- 扩展 `loopspec init`：新增 `--tools <all|none|逗号分隔的工具 id 列表>` 参数；未传且终端可交互时，弹出简单的编号多选提示让用户勾选工具；非交互且未传 `--tools` 时默认等价于 `--tools none`（不做任何工具脚手架，保持现有 `loopspec init` 行为不变，向后兼容）。
- 为每个选中的工具写入：`<skillsDir>/skills/<template-name>/SKILL.md`（4 份，工具通用路径规则）；若该工具注册了命令适配器，额外写入其命令文件（Claude Code 用 `.claude/commands/lpsx/<verb>.md` 冒号命名空间 `/lpsx:<verb>`；Codex 写入全局 `$CODEX_HOME/prompts/lpsx-<verb>.md`；OpenCode/Cursor/Windsurf 写入 `.<tool>/commands/lpsx-<verb>.md` 连字符命名 `/lpsx-<verb>`，并把正文中出现的 `/lpsx:x` 引用改写为 `/lpsx-x`）；若工具没有注册命令适配器，跳过命令文件生成但仍写入 skill 文件，并在响应中提示"该工具无命令适配器"。
- 重新运行 `init` 时对已选工具的 skill/命令文件**始终覆盖重写**（不做增量 diff、不逐文件确认），与 OpenSpec 的行为保持一致；不引入任何持久化"已选工具"清单文件，工具是否已配置永远通过扫描文件系统（对应 skill 文件是否存在）实时判定。

## Capabilities

### New Capabilities
- `tool-scaffolding`: AI 工具注册表（工具 id → skillsDir → 可选命令适配器）、命令适配器接口与 Claude Code/Codex/OpenCode/Cursor/Windsurf 五个具体实现、`init` 的工具选择交互与 `--tools` 参数解析、始终覆盖重写的写入语义、无适配器工具的优雅跳过。
- `lpsx-skills`: `loopspec-new`/`loopspec-continue`/`loopspec-archive`/`loopspec-bulk-archive` 四份 skill/命令正文模板内容，以及冒号命名（`/lpsx:x`）与连字符命名（`/lpsx-x`）之间的引用转换规则。

### Modified Capabilities
- `loopspec-cli`: `loopspec init` 的需求新增 `--tools` 参数与交互式工具选择行为（原有的 `config.yaml`/`schemas/`/`changes/` 初始化行为不变）。

## Impact

- `src/loopspec/` 新增模块：工具注册表与命令适配器（如 `tool_registry.py`）、skill/命令模板内容（如 `skill_templates.py`）、脚手架写入编排（如 `scaffold.py`）。
- `src/loopspec/cli.py` 的 `init` 命令签名新增 `--tools` 选项与交互式选择分支。
- 用户项目侧新增目录：按所选工具在 `<project>/.claude/`、`.codex/`、`.opencode/`、`.cursor/`、`.windsurf/` 下写入 `skills/<name>/SKILL.md`（全部工具通用）与各自风格的命令文件（Codex 写到用户全局 `$CODEX_HOME/prompts/`，不在项目目录内）。
- 不影响 `loopspec` 现有的 workflow-schema/artifact-state/gate-rollback/change-memory/change-archiving 能力；`loopspec init` 在未传 `--tools` 且非交互时行为与当前版本完全一致，无破坏性变更。
