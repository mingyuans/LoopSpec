## ADDED Requirements

### Requirement: loopspec artifacts 查看一个 change 的全部产物路径

`loopspec artifacts <change-name> [--schemas <names>] [--home <dir>] [--json]` SHALL 输出该 change 在全部位置（活跃目录与全部归档月份）下、由全部被考察 schema 认领的产物路径，按 `artifact-discovery` 能力定义的发现规则执行。本命令 SHALL 为只读：不创建、不移动、不删除任何文件或目录。

`--schemas` SHALL 接受逗号分隔的 schema 名列表（如 `secure-spec-driven,docs-only`），围绕逗号的空白 SHALL 被忽略，重复名称 SHALL 去重并保持首次出现的顺序；空值或只含分隔符的取值 SHALL 以 `config_invalid` 拒绝，而不是被当作「未点名」静默放行；每个名称 SHALL 校验为 kebab-case，不合法以 `config_invalid` 拒绝。省略 `--schemas` 时 SHALL 报告全部已知 schema。

`--json` 响应 SHALL 至少包含以下字段：`changeName`、`artifactsDir`、`requestedSchemas`（未点名时为 `null`）、`schemasSeen`、`locations`、`files`、`warnings`、`nextSteps`。`locations[]` 的每一条 SHALL 包含 `kind`（`active` 或 `archived`）、`archiveMonth`（活跃位置为 `null`）、`changeRoot`、`declaredSchema`、`created`、`statePath`、`stateExists`、`schemas`、`attempts`、`unclassifiedFiles` 与该位置的 `files`。`locations[].schemas[]` 的每一条 SHALL 包含 `name`、`declared`、`schemaPath`、`artifactRoot`、`nodes` 与该 schema 的 `files`；`nodes[]` 的每一条 SHALL 包含 `id`、`isGate`、`outputPatterns` 与 `files`。`locations[].attempts[]` 的每一条 SHALL 包含 `round`、`gate`、`verdict`、`archiveDir` 与 `files`。

全部路径字段 SHALL 为绝对路径，且 SHALL 全部位于 workflow home 之内——按 `artifact-discovery` 的路径收口要求，解析后逃出 home 的路径不出现在响应的任何字段里，只在 `warnings` 中被指名。`files` 类字段 SHALL 去重并稳定排序，使同一磁盘状态下多次调用输出一致。

本命令的职责边界 SHALL 与既有命令区分开，三者的契约均不因本命令的加入而改变：

- `status` 回答「当前那一个 schema 走到哪了」——它按 `.workflow.yaml` 解析单一 schema，且在 change 目录不存在时以 `change_not_found` 失败，因此无法覆盖归档位置。
- `instructions` 的 `contextFiles` 回答「产出当前节点需要读什么」——同样限定在当前 schema。
- `history` 回答「当前位置内部回退过几轮」——覆盖 `.attempts/round-NNN/`，与 schema 接力和目录归档是两件不同的事。
- `artifacts` 回答「这个 change 名下一共存在哪些产物文件」——跨 schema、跨位置，不解释状态、不读文件内容。

#### Scenario: 列出活跃 change 的全部产物
- **WHEN** 对一个活跃且已产出若干产物的 change 执行 `loopspec artifacts <change> --json`
- **THEN** 命令成功，返回恰好一个活跃位置，其中每个已写产物都出现在对应 schema 的对应节点下，且路径为绝对路径

#### Scenario: 归档后仍可查询
- **WHEN** change 已被归档到 `<home>/archive/2026-07/<change>/`，执行 `loopspec artifacts <change> --json`
- **THEN** 命令成功，返回一个 `kind` 为 `archived`、`archiveMonth` 为 `2026-07` 的位置，产物路径指向归档目录下的真实文件

#### Scenario: --schemas 过滤
- **WHEN** 执行 `loopspec artifacts <change> --schemas docs-only --json`
- **THEN** `requestedSchemas` 为 `["docs-only"]`，只报告该 schema 认领的产物，其余产物出现在 `unclassifiedFiles` 中

#### Scenario: --schemas 接受多个名称
- **WHEN** 执行 `loopspec artifacts <change> --schemas "docs-only, secure-spec-driven" --json`
- **THEN** 两个 schema 都被考察，围绕逗号的空白不影响解析

#### Scenario: --schemas 点名不存在的 schema
- **WHEN** 执行 `loopspec artifacts <change> --schemas nope --json`
- **THEN** 以退出码 1 与 `schema_not_found` 失败

#### Scenario: --schemas 取值为空
- **WHEN** 执行 `loopspec artifacts <change> --schemas "" --json`
- **THEN** 以退出码 1 与 `config_invalid` 失败

#### Scenario: --schemas 点名的名称不是安全相对路径
- **WHEN** 执行 `loopspec artifacts <change> --schemas ../../etc --json`
- **THEN** 以退出码 1 与 `config_invalid` 失败，且不尝试从 workflow home 之外加载任何 schema

#### Scenario: change 不存在
- **WHEN** 对任何位置都不存在的 change 名执行本命令
- **THEN** 以退出码 1 与 `change_not_found` 失败

#### Scenario: change 名不安全
- **WHEN** 执行 `loopspec artifacts ../../etc --json`
- **THEN** 以退出码 1 与 `invalid_change_name` 失败，输出中不含 workflow home 之外的任何路径

#### Scenario: 命令为只读
- **WHEN** 在任意状态的 change 上执行本命令
- **THEN** workflow home 下的文件与目录集合在命令前后完全一致

#### Scenario: 人类可读模式给出摘要
- **WHEN** 不带 `--json` 执行本命令
- **THEN** 输出中不出现 JSON 载荷的原始字段名或语言层面的容器字面量，且被聚合掉的完整路径明细仍可通过 `--json` 取到
