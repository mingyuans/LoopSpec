## 1. 工具注册表与命令适配器接口（tool-scaffolding）

- [x] 1.1 在 `src/loopspec/tool_registry.py` 中定义 `ToolSpec`（`id`/`skills_dir`）与 `AI_TOOLS` 注册表：内置 `claude`（`.claude`）、`codex`（`.codex`）、`opencode`（`.opencode`）、`cursor`（`.cursor`）、`windsurf`（`.windsurf`）
- [x] 1.2 定义 `CommandContent`（`id`/`name`/`description`/`body`）与 `ToolCommandAdapter` 协议/抽象基类：`get_file_path(command_id) -> Path`、`format_file(content) -> str`
- [x] 1.3 实现 Claude Code 适配器：`.claude/commands/lpsx/<verb>.md`，命令名 `/lpsx:<verb>`，Markdown frontmatter（`name`/`description`）
- [x] 1.4 实现 Codex 适配器：路径为 `$CODEX_HOME/prompts/lpsx-<verb>.md`（`CODEX_HOME` 未设置时使用 `~/.codex/prompts`），命令名 `/lpsx-<verb>`
- [x] 1.5 实现 OpenCode / Cursor / Windsurf 三个适配器：`.<tool>/commands/lpsx-<verb>.md`，命令名 `/lpsx-<verb>`
- [x] 1.6 定义 `COMMAND_ADAPTERS`（工具 id → adapter 实例）注册表，供 v1 的 5 个工具全部注册
- [x] 1.7 编写 `tests/test_tool_registry.py`，覆盖：已注册工具可查询、未注册工具可判定不存在、5 个适配器各自的路径与命令名规则（含 `CODEX_HOME` 覆盖场景）、同一 `CommandContent` 在不同适配器下产出不同 frontmatter 但正文一致

## 2. skill/命令模板内容与命名转换（lpsx-skills）

- [x] 2.1 在 `src/loopspec/skill_templates.py` 中定义 `SkillTemplate`（`name`/`description`/`verb`/`body`）与 4 个内置模板：`loopspec-new`、`loopspec-continue`、`loopspec-archive`、`loopspec-bulk-archive`，正文分别对应 `loopspec new`/`status`、读取 `nextSteps` 循环、`loopspec archive`、`loopspec bulk-archive`
- [x] 2.2 实现命名转换函数 `to_hyphenated(text: str) -> str`：把正文中 `/lpsx:<verb>` 替换为 `/lpsx-<verb>`，只匹配命令引用模式
- [x] 2.3 实现 `generate_skill_content(template) -> str`：组装 SKILL.md 的 YAML frontmatter（`name`/`description`）+ 正文
- [x] 2.4 实现 `generate_command_content(template, apply_hyphen_transform: bool) -> CommandContent`：Claude Code 不转换，其余工具应用 `to_hyphenated`（`adapter` 参数在实现中发现是多余的，`apply_hyphen_transform` 已足够决定转换行为，故简化掉）
- [x] 2.5 编写 `tests/test_skill_templates.py`，覆盖：4 个模板齐全且 `verb` 正确、正文引用对应 CLI 命令、命名转换只改写 `/lpsx:x` 模式不误伤其他文本、Claude Code 保留原始冒号引用而其余工具转换为连字符引用

## 3. 脚手架写入编排

- [x] 3.1 在 `src/loopspec/scaffold.py` 中实现 `scaffold_tools(project_path: Path, tool_ids: list[str]) -> ScaffoldResult`：对每个 `tool_id` 写入 4 个 skill 文件（统一路径规则）；若该工具在 `COMMAND_ADAPTERS` 中注册，额外写入 4 个命令文件；否则记录"已跳过命令文件生成"
- [x] 3.2 保证覆盖重写语义：无论目标文件是否已存在，直接 `write_text` 覆盖，不做增量判断
- [x] 3.3 `ScaffoldResult` 汇总每个工具写入的文件路径列表与被跳过命令生成的工具列表，供 CLI 层组装 JSON 响应
- [x] 3.4 编写 `tests/test_scaffold.py`，覆盖：单工具/多工具写入文件路径正确、重复调用覆盖已有文件不报错、无适配器工具（构造一个测试专用的只注册 `skills_dir` 无适配器的工具）跳过命令文件但 skill 文件正常写入、不产生任何"已选工具"记录文件

## 4. --tools 参数解析与交互式选择

- [x] 4.1 在 `tool_registry.py`（或独立 `tools_cli.py`）中实现 `resolve_tools_arg(raw: str | None) -> list[str]`：解析 `all`/`none`/逗号分隔 id，大小写不敏感，未知 id 抛出携带合法 id 列表的错误
- [x] 4.2 实现交互式选择函数 `prompt_tools_interactively() -> list[str]`：打印编号列表，读取一行输入解析为逗号分隔编号或 `all`/`none`
- [x] 4.3 实现终端可交互性检测（复用标准库 `sys.stdin.isatty()`），非交互且 `raw is None` 时直接返回空列表（等价 `none`），不调用交互式选择函数
- [x] 4.4 编写 `tests/test_tools_arg.py`，覆盖：`all`/`none`/子集解析正确、未知 id 报错信息包含合法 id 列表、非交互环境未传参数时返回空列表

## 5. 接入 loopspec init

- [x] 5.1 在 `cli.py` 的 `init` 命令新增 `--tools` 选项，串联 `resolve_tools_arg`/交互式选择/`scaffold_tools`
- [x] 5.2 `init` 的 JSON 响应新增字段：`toolsConfigured`（工具 id 列表）、`scaffoldedFiles`（按工具分组的文件路径）、`skippedCommandGeneration`（无适配器工具列表）
- [x] 5.3 确保不传 `--tools` 且非交互时，`init` 的行为与新增该参数之前完全一致（回归验证）
- [x] 5.4 编写/扩展 `tests/test_cli.py`，覆盖：`--tools all`、`--tools claude,codex` 子集、`--tools` 未知 id 报错、非交互未传 `--tools` 时不写入任何工具目录且与既有测试结果一致、重复运行覆盖已有脚手架文件

## 6. 收尾与文档

- [x] 6.1 更新 `README.md`：补充 `loopspec init --tools ...` 用法说明与支持的工具列表
- [x] 6.2 运行 `make lint` 与 `make test`，确保全部通过（含本变更新增测试与既有 132 个测试）

## 7. 修正：脚手架写入项目根目录（首次真实使用发现的 bug）

- [x] 7.1 修复 `cli.py` 的 `init`：脚手架目标由 workflow home 改为项目根目录（默认解析为 workflow home 的父目录），新增 `--project-root` 显式覆盖参数，响应新增 `projectRoot` 字段
- [x] 7.2 更新 `specs/tool-scaffolding/spec.md`：新增"脚手架写入项目根目录，而非 workflow home"需求，并把 skill 落盘规则中的"项目路径"明确为"项目根目录"
- [x] 7.3 更新 `specs/loopspec-cli/spec.md`：`init` 签名加入 `--project-root`，补充项目根写入语义与 `projectRoot` 响应字段、以及对应场景
- [x] 7.4 修正 `tests/test_cli.py` 的路径断言，并新增 `isolated_codex_home` fixture 隔离 `CODEX_HOME`，避免测试污染开发者真实的 `~/.codex/prompts/`
- [x] 7.5 更新 `README.md` 说明脚手架落在项目根而非 workflow home
- [x] 7.6 重新运行 `make lint` 与 `make test` 并实际验证 `init --tools` 的落盘路径
