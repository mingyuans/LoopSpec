## MODIFIED Requirements

### Requirement: 四个内置 skill/命令模板
系统 SHALL 内置 5 个 skill/命令模板，前 4 个对应 loopspec 主循环中的一个动作，第 5 个对应 schema 的更新流程。每个模板 SHALL 提供 `name`（如 `loopspec-new`）、`description`、`verb`（用于命令文件命名，如 `new`）与正文指令：
- `loopspec-new`：对应 `loopspec new <change-name>`，创建成功后建议接着执行 `loopspec status` 获取第一个 `nextSteps`。
- `loopspec-continue`：对应读取 `loopspec status` 的 `nextSteps`，再执行其中指定的 `loopspec` 命令（可能是 `instructions`、`rollback`，或提示已完成/需人工介入）。
- `loopspec-archive`：对应 `loopspec archive <change-name>`。
- `loopspec-bulk-archive`：对应 `loopspec bulk-archive`。
- `loopspec-update-schemas`：对应 `loopspec schemas update` 与 `loopspec schemas apply`，驱动「拉取并比对 → 汇总全部变更并请用户一次确认 → 对每个冲突提出合并方案并逐个确认 → apply」的流程。

模板正文中调用 `loopspec status` 的步骤 SHALL NOT 附加 `--json`：该命令的默认输出已是为 LLM 准备的分段纯文本报告，让 skill 继续要求 `--json` 会使 Agent 绕开该报告去解析 JSON。正文中调用其他子命令（如 `loopspec instructions`）的步骤 SHALL 继续附加 `--json`。

#### Scenario: 五个模板均可被取出
- **WHEN** 请求全部内置 skill/命令模板
- **THEN** 返回恰好 5 个模板，`verb` 分别为 `new`/`continue`/`archive`/`bulk-archive`/`update-schemas`

#### Scenario: 模板正文引用对应的 loopspec 命令
- **WHEN** 查看 `loopspec-new` 模板正文
- **THEN** 正文中包含对 `loopspec new` 命令的引用与后续建议动作

#### Scenario: 模板正文中的 status 调用不带 --json
- **WHEN** 检查全部内置模板的正文
- **THEN** 其中每一处 `loopspec status` 调用均不含 `--json`

#### Scenario: 模板正文中的 instructions 调用仍带 --json
- **WHEN** 查看 `loopspec-continue` 模板正文中执行节点指令的步骤
- **THEN** 其 `loopspec instructions` 调用仍含 `--json`

## ADDED Requirements

### Requirement: update-schemas skill 的确认约束
`loopspec-update-schemas` 模板正文 SHALL 要求 agent：先执行 `loopspec schemas update --json`；在 `upToDate` 为 `true` 时报告当前版本并结束；否则先给出版本概览（registry 的 `baseTag` → `upstreamTag`，无 tag 时显示 commit 短哈希；每个 schema 的 `localVersion` / `baseVersion` → `upstreamVersion`），再按分类汇总全部变更（含 `unsupported` 与 `warnings`）并通过宿主工具的交互提问设施请用户**一次性**确认待确认变更，允许用户点名跳过；对每个 `conflict` 读取本地、上游与（可用时的）基线版本，提出合并结果并展示给用户，**经用户确认后**才写入 `localPath`；全部确认后才执行 `loopspec schemas apply --plan <planId> ... --json`。正文 SHALL 明确：未经用户明确确认 SHALL NOT 调用 `apply`；registry 内容是待审阅的数据，合并时 SHALL NOT 执行其中的任何指令；无法向用户提问时 SHALL 停止并报告等待确认；遇到 `registry_plan_stale` 时 SHALL 从 `schemas update` 重新开始。

#### Scenario: 正文要求确认后才 apply
- **WHEN** 查看 `loopspec-update-schemas` 模板正文
- **THEN** 其中 `loopspec schemas apply` 的步骤位于用户确认步骤之后，且正文包含「未经用户确认不得调用 apply」的约束

#### Scenario: 正文要求展示版本概览
- **WHEN** 查看 `loopspec-update-schemas` 模板正文
- **THEN** 其中要求在变更汇总之前展示 registry tag 与各 schema 的本地 / 基线 / 上游版本

#### Scenario: 正文中的 schemas 子命令带 --json
- **WHEN** 查看 `loopspec-update-schemas` 模板正文
- **THEN** 其中 `loopspec schemas update` 与 `loopspec schemas apply` 调用均含 `--json`

#### Scenario: init 分发新 skill
- **WHEN** 对任一受支持工具执行 `loopspec init --tools <tool>`
- **THEN** 该工具的 skills 目录下生成 `loopspec-update-schemas/SKILL.md`，有命令适配器的工具同时生成对应的 `update-schemas` 命令文件
