## MODIFIED Requirements

### Requirement: loopspec status 查看状态
`loopspec status <change-name> --json` SHALL 扫描该 change 的 artifact 根目录与 `.attempts/`，返回每个节点的当前状态、`isComplete`、`statePath`/`stateExists`、`pendingRollback`（存在 `failed` gate 时非 null，含 `gate`/`closure`/`command`；否则为 `null`）以及 `nextSteps`。`nextSteps` SHALL 按拓扑序找到第一个 `exhausted` 或 `failed` 的 gate 优先返回对应的人工介入或回退指令；若无失败/耗尽 gate，则返回第一个 `ready` 节点对应的 `loopspec instructions` 命令；若全部完成则返回完成提示。本命令 SHALL 不返回节点的模板正文。

对声明了 `tracks` 的节点，其节点条目 SHALL 额外包含 `taskProgress` 摘要：`path`（被追踪文件的相对路径）、`resolvedPath`（绝对路径）、`total`、`complete`、`remaining`；该摘要 SHALL 不包含逐条任务列表（逐条任务只在 `loopspec instructions` 中返回），以便调用方只调用一次 `status` 就能报告实现进度。未声明 `tracks` 的节点条目 SHALL 不包含 `taskProgress` 字段。

#### Scenario: 首次 status 返回首节点指令
- **WHEN** 对新创建、尚无任何产物的 change 执行 `status`
- **THEN** `nextSteps` 指向拓扑序第一个节点的 `loopspec instructions` 命令

#### Scenario: gate 失败时返回 pendingRollback
- **WHEN** 某 gate 状态为 `failed`
- **THEN** `pendingRollback` 非 null，包含该 gate ID、reset closure 与 `loopspec rollback` 命令

#### Scenario: gate 耗尽时不返回 rollback
- **WHEN** 某 gate 状态为 `exhausted`
- **THEN** `pendingRollback` 为 `null`，`nextSteps` 提示已达重试上限并建议查看 `loopspec history`

#### Scenario: 全部完成
- **WHEN** schema 内全部节点状态均为 `done`
- **THEN** `isComplete` 为 `true`

#### Scenario: 声明 tracks 的节点返回进度摘要
- **WHEN** 某节点声明了 `tracks`，且被追踪文件含已勾选与未勾选的任务
- **THEN** 该节点条目含 `taskProgress`，其 `total`/`complete`/`remaining` 与被追踪文件内容一致，且不含逐条任务列表

#### Scenario: 未声明 tracks 的节点无进度字段
- **WHEN** 某节点未声明 `tracks`
- **THEN** 该节点条目不含 `taskProgress` 字段

### Requirement: loopspec instructions 生成节点指令
`loopspec instructions <node> --change <change> --json` SHALL 返回该节点的生成指令上下文：普通节点返回单一 `template` 与单一 `resolvedOutputPath`；gate 节点返回 `templates.pass/fail` 与 `resolvedOutputPath.pass/fail`，并在指令文案中要求 LLM 只能二选一写入。响应 SHALL 同时包含 `description`、展开后的 `instruction` 字符串（不暴露原始 `instruction.file` 路径）、`context`、按节点 ID 匹配的 `rules`、`dependencies`（含各依赖的完成状态与路径）、`unlocks`（直接后继节点列表）、`statePath`/`state`/`warnings`、`priorAttempts`。

响应 SHALL 额外包含 `contextFiles`：一个"节点 ID → 该节点当前实际存在的产物绝对路径列表"的映射，覆盖 schema 中**全部**节点（而非仅当前节点的直接依赖），并 SHALL 省略当前没有任何产物存在的节点。glob 形式 `generates` 的节点 SHALL 列出全部匹配文件；gate 节点 SHALL 列出其当前存在的 pass 或 fail 产物。该字段的用途是让需要读齐全部上游产物的节点（如人类审批、实现类节点）不必猜测文件名。

当节点声明了 `tracks` 时，响应 SHALL 额外包含 `taskProgress`：`path`、`resolvedPath`、`total`、`complete`、`remaining` 以及逐条任务数组 `tasks`（每项含 `id`/`description`/`done`）。被追踪文件不存在时 SHALL 返回空 `tasks` 与全 0 进度，并在 `warnings` 中追加一条说明，而不是报错中断指令生成。未声明 `tracks` 的节点 SHALL 不包含 `taskProgress` 字段。

#### Scenario: 普通节点的指令结构
- **WHEN** 对一个非 gate 的 `ready` 节点调用 `instructions`
- **THEN** 响应含单一 `template` 字段与单一 `resolvedOutputPath` 字段

#### Scenario: gate 节点的指令结构
- **WHEN** 对一个 `ready` 的 gate 节点调用 `instructions`
- **THEN** 响应含 `templates.pass`/`templates.fail` 与 `resolvedOutputPath.pass`/`resolvedOutputPath.fail`，且指令文案要求二选一

#### Scenario: config.yaml 的 context 与 rules 注入
- **WHEN** `config.yaml` 配置了 `context` 与按节点 ID 匹配的 `rules`
- **THEN** 响应的 `context` 字段包含该内容，`rules` 字段只包含当前节点匹配到的规则条目

#### Scenario: rules 引用不存在的节点 ID
- **WHEN** `config.yaml` 的 `rules` 中出现一个不在当前 schema 中的节点 ID
- **THEN** 系统输出告警但不中断指令生成

#### Scenario: instruction.file 不直接暴露给调用方
- **WHEN** 节点的 `instruction` 配置为 `{file: ...}`
- **THEN** 响应 JSON 中只包含展开后的 `instruction` 字符串字段，不包含原始文件名或路径

#### Scenario: dependencies 与 unlocks 正确性
- **WHEN** 查询任意节点的 `instructions`
- **THEN** `dependencies` 数组正确反映各依赖节点的完成状态与产物路径，`unlocks` 数组正确列出该节点的直接后继

#### Scenario: contextFiles 覆盖全部已有产物
- **WHEN** 对某节点调用 `instructions`，而该 change 已产出上游若干节点的产物（含 glob 节点的多个文件与某个 gate 的 pass 产物）
- **THEN** `contextFiles` 以节点 ID 为键列出这些产物的绝对路径（glob 节点列出全部匹配文件），且不包含当前节点及其他尚无产物的节点

#### Scenario: 声明 tracks 的节点返回逐条任务
- **WHEN** 对声明了 `tracks` 的节点调用 `instructions`，被追踪文件含若干已勾选与未勾选任务
- **THEN** 响应含 `taskProgress`，其 `tasks` 数组按出现顺序给出每条任务的 `id`/`description`/`done`，且 `total`/`complete`/`remaining` 与之一致

#### Scenario: 被追踪文件缺失时降级为告警
- **WHEN** 节点声明了 `tracks`，但被追踪文件当前不存在（例如已被回退归档）
- **THEN** `taskProgress` 的 `tasks` 为空、进度全为 0，`warnings` 含一条说明该文件缺失的告警，命令仍以退出码 0 正常返回
