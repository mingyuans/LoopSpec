# lpsx-skills Specification

## Purpose
TBD - created by archiving change ai-tool-scaffolding. Update Purpose after archive.
## Requirements
### Requirement: 四个内置 skill/命令模板
系统 SHALL 内置 4 个 skill/命令模板，分别对应 loopspec 主循环中的一个动作，每个模板 SHALL 提供 `name`（如 `loopspec-new`）、`description`、`verb`（用于命令文件命名，如 `new`）与正文指令：
- `loopspec-new`：对应 `loopspec new <change-name>`，创建成功后建议接着执行 `loopspec status` 获取第一个 `nextSteps`。
- `loopspec-continue`：对应读取 `loopspec status` 的 `nextSteps`，再执行其中指定的 `loopspec` 命令（可能是 `instructions`、`rollback`，或提示已完成/需人工介入）。
- `loopspec-archive`：对应 `loopspec archive <change-name>`。
- `loopspec-bulk-archive`：对应 `loopspec bulk-archive`。

#### Scenario: 四个模板均可被取出
- **WHEN** 请求全部内置 skill/命令模板
- **THEN** 返回恰好 4 个模板，`verb` 分别为 `new`/`continue`/`archive`/`bulk-archive`

#### Scenario: 模板正文引用对应的 loopspec 命令
- **WHEN** 查看 `loopspec-new` 模板正文
- **THEN** 正文中包含对 `loopspec new` 命令的引用与后续建议动作

### Requirement: 同一正文跨工具复用
系统 SHALL 保证每个模板只维护一份正文内容，写入不同工具的 skill 文件与命令文件时复用同一份正文（经过命名转换后），不为每个工具单独维护一份重复的正文文本。

#### Scenario: 同一模板生成的 Claude 与 OpenCode 文件正文一致
- **WHEN** 用 `loopspec-continue` 模板分别生成 Claude Code 的 skill 文件与 OpenCode 的命令文件
- **THEN** 两者的核心指令正文内容相同，仅命令引用的命名风格不同（见"命令引用命名转换"需求）

### Requirement: 命令引用命名转换
模板正文中如果引用了其他 loopspec 命令（形如 `/lpsx:<verb>`），系统 SHALL 在为使用连字符命名（如 OpenCode、Cursor、Windsurf、Codex）的工具生成文件时，把正文中的 `/lpsx:<verb>` 引用统一转换为 `/lpsx-<verb>`；为 Claude Code 生成文件时 SHALL 保留原始的 `/lpsx:<verb>` 形式，不做转换。

#### Scenario: 连字符命名工具的引用被转换
- **WHEN** 某模板正文包含"回退后重新执行 `/lpsx:continue`"，并为 OpenCode 生成文件
- **THEN** 生成文件中的对应引用变为 `/lpsx-continue`

#### Scenario: Claude Code 保留冒号命名引用
- **WHEN** 同一模板正文为 Claude Code 生成文件
- **THEN** 生成文件中的引用保持原始的 `/lpsx:continue` 形式，未被转换

#### Scenario: 转换只影响命令引用，不影响其他文本
- **WHEN** 模板正文中出现形似但并非命令引用的文本
- **THEN** 命名转换规则 SHALL 只匹配 `/lpsx:<verb>` 模式，不误改其他文本内容

