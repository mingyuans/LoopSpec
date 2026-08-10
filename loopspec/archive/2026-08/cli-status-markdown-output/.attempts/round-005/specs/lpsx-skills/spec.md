## MODIFIED Requirements

### Requirement: 四个内置 skill/命令模板
系统 SHALL 内置 4 个 skill/命令模板，分别对应 loopspec 主循环中的一个动作，每个模板 SHALL 提供 `name`（如 `loopspec-new`）、`description`、`verb`（用于命令文件命名，如 `new`）与正文指令：
- `loopspec-new`：对应 `loopspec new <change-name>`，创建成功后建议接着执行 `loopspec status` 获取第一个 `nextSteps`。
- `loopspec-continue`：对应读取 `loopspec status` 的 `nextSteps`，再执行其中指定的 `loopspec` 命令（可能是 `instructions`、`rollback`，或提示已完成/需人工介入）。
- `loopspec-archive`：对应 `loopspec archive <change-name>`。
- `loopspec-bulk-archive`：对应 `loopspec bulk-archive`。

模板正文中调用 `loopspec status` 的步骤 SHALL NOT 附加 `--json`：该命令的默认输出已是为 LLM 准备的分段纯文本报告，让 skill 继续要求 `--json` 会使 Agent 绕开该报告去解析 JSON。正文中调用其他子命令（如 `loopspec instructions`）的步骤 SHALL 继续附加 `--json`。

#### Scenario: 四个模板均可被取出
- **WHEN** 请求全部内置 skill/命令模板
- **THEN** 返回恰好 4 个模板，`verb` 分别为 `new`/`continue`/`archive`/`bulk-archive`

#### Scenario: 模板正文引用对应的 loopspec 命令
- **WHEN** 查看 `loopspec-new` 模板正文
- **THEN** 正文中包含对 `loopspec new` 命令的引用与后续建议动作

#### Scenario: 模板正文中的 status 调用不带 --json
- **WHEN** 检查全部内置模板的正文
- **THEN** 其中每一处 `loopspec status` 调用均不含 `--json`

#### Scenario: 模板正文中的 instructions 调用仍带 --json
- **WHEN** 查看 `loopspec-continue` 模板正文中执行节点指令的步骤
- **THEN** 其 `loopspec instructions` 调用仍含 `--json`
