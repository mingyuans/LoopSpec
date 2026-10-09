## ADDED Requirements

### Requirement: loopspec schemas list 报告每个 schema 的来源

`loopspec schemas list [--home <dir>] [--json]` SHALL 列出所有源（`local` 与 `schema_sources` 中声明的每个源）中可加载的 schema。每个条目 SHALL 包含既有字段 `name`、`version`、`path`、`nodes`，其中 `source` SHALL 为提供该 schema 的源名称（`local` 或 `schema_sources[*].name`），`path` SHALL 为该 schema 目录的规范化绝对路径；每个条目 SHALL 新增布尔字段 `shadowed`，当同名 schema 已由优先级更高的源提供时为 `true`。条目 SHALL 先按源优先级、再按名称排序。无法加载的 schema 目录 SHALL 继续被跳过而不导致命令失败。

#### Scenario: 同时列出本地与外部 schema
- **WHEN** `local` 提供 `secure-spec-driven`，源 `team-shared` 提供 `team-flow`，执行 `loopspec schemas list --json`
- **THEN** 响应包含 `{name: secure-spec-driven, source: local, shadowed: false}` 与 `{name: team-flow, source: team-shared, shadowed: false}`，且前者排在前面

#### Scenario: 标出被遮蔽的条目
- **WHEN** `local` 与 `team-shared` 都提供 `team-flow`
- **THEN** 响应中 `source: local` 的 `team-flow` 为 `shadowed: false`，`source: team-shared` 的 `team-flow` 为 `shadowed: true`

#### Scenario: 未配置外部源时向后兼容
- **WHEN** `config.yaml` 不含 `schema_sources`
- **THEN** 响应条目与既有输出相同，仅每个条目多出 `shadowed: false`

### Requirement: 命令响应报告所用 schema 的来源

`loopspec schemas show <name>` 与 `loopspec schemas validate <name>` SHALL 经 schema 源解析 `<name>`，其 JSON 响应 SHALL 新增 `source` 字段，值为提供该 schema 的源名称。`loopspec new` 与 `loopspec status` 的 JSON 响应 SHALL 新增 `schemaSource` 字段，值为当前解析出的源名称。既有字段 SHALL 保持不变。

#### Scenario: show 外部 schema
- **WHEN** `team-flow` 仅由源 `team-shared` 提供，执行 `loopspec schemas show team-flow --json`
- **THEN** 命令成功，响应包含 `source: team-shared` 与该 schema 的节点列表

#### Scenario: validate 不存在的 schema
- **WHEN** 执行 `loopspec schemas validate nope --json`，且任何源都不提供 `nope`
- **THEN** 以退出码 1 与 `schema_not_found` 失败

#### Scenario: status 报告来源
- **WHEN** 对一个使用本地 schema 的 change 执行 `loopspec status <change> --json`
- **THEN** 响应包含 `schemaSource: local`
