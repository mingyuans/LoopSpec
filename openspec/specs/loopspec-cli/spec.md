# loopspec-cli Specification

## Purpose
TBD - created by archiving change gated-artifact-workflow. Update Purpose after archive.
## Requirements
### Requirement: 全命令支持结构化 JSON 输出
`loopspec` 的每个子命令 SHALL 支持 `--json` 标志，输出机器可解析的结构化结果；`--json` 是 LLM/Agent 消费的主协议，人类可读输出（无 `--json`）为次要形式，二者返回的信息内容 SHALL 保持一致。

#### Scenario: 任意命令附加 --json
- **WHEN** 对任意 `loopspec` 子命令附加 `--json`
- **THEN** 命令以合法 JSON 格式输出结果到 stdout

### Requirement: 统一错误输出格式
任何命令执行失败 SHALL 以退出码 `1` 结束，并在结构化模式下输出包含 `error`（机器可读错误码）、`message`（人类可读说明）、`fix`（可直接执行的修复建议）三个字段的 JSON。系统 SHALL 支持以下错误码：`schema_not_found`、`schema_selection_required`、`schema_invalid`、`config_invalid`、`template_not_found`、`instruction_not_found`、`change_not_found`、`change_exists`、`invalid_change_name`、`node_not_found`、`gate_output_conflict`、`no_failed_gate`、`retries_exhausted`、`archive_conflict`、`archive_unsafe`。

#### Scenario: 命令失败时的错误结构
- **WHEN** 任意命令因某种校验失败或前置条件不满足而无法完成
- **THEN** 命令以退出码 1 结束，且 stdout 输出的 JSON 含 `error`、`message`、`fix` 三个字段

### Requirement: loopspec version 查看版本
`loopspec version [--json]` SHALL 输出当前已安装 `loopspec` 包的版本号，且 SHALL 不依赖存在已初始化的 workflow home（即在任意目录、workflow home 不存在时也能正常执行，不报 `change_not_found` 等目录相关错误）。人类可读模式 SHALL 直接打印版本号字符串；`--json` 模式 SHALL 返回包含 `version` 字段的 JSON 对象。

#### Scenario: 查看版本号
- **WHEN** 在任意目录执行 `loopspec version`
- **THEN** 命令以退出码 0 结束，输出当前安装的版本号

#### Scenario: 查看版本号的 JSON 输出
- **WHEN** 执行 `loopspec version --json`
- **THEN** 输出 `{"version": "<当前版本号>"}`

#### Scenario: 未初始化 workflow home 时仍可查询版本
- **WHEN** 当前目录不存在 `config.yaml`/workflow home
- **THEN** `loopspec version` 仍正常返回版本号，不报任何 workflow home 相关错误

### Requirement: loopspec init 初始化 workflow home
`loopspec init [path] [--tools TOOLS] [--project-root DIR]` SHALL 在指定路径（缺省为 `./loopspec`）创建 workflow home，包含 `config.yaml`（含默认 `artifacts_dir: changes` 与默认 `schema`）、空的 `schemas/` 目录与空的 `changes/` 目录；默认 SHALL 同时把内置 schema 复制到 `schemas/` 下；传入 `--no-builtin` SHALL 跳过复制，只生成空骨架。

`--tools` 参数 SHALL 接受 `all`（选中全部已注册工具）、`none`（不做任何工具脚手架）或逗号分隔的工具 id 列表（如 `claude,codex`），大小写不敏感；传入未注册的工具 id SHALL 报错并在 `fix` 中列出全部合法 id。未传 `--tools` 时：若当前处于可交互终端，SHALL 打印已注册工具的编号列表，读取一行逗号分隔的编号或 `all`/`none` 作为选择；若处于非交互环境，SHALL 直接按 `none` 处理（不做任何工具脚手架、不报错、不阻塞），以保持与本参数引入前完全一致的默认行为。

对每个被选中的工具，`init` SHALL 按 `tool-scaffolding` 能力描述的规则写入其 skill 文件与（如有命令适配器）命令文件；这些文件 SHALL 写入项目根目录（默认为 workflow home 的父目录，可用 `--project-root` 覆盖），而非 workflow home 内部。未选择任何工具或全部工具都不支持时，`init` 的其余行为（`config.yaml`/`schemas/`/`changes/` 初始化）SHALL 不受影响。`init` 的响应 SHALL 包含 `projectRoot` 字段，说明脚手架实际写入的根目录。

#### Scenario: 默认初始化包含内置 schema
- **WHEN** 执行 `loopspec init ./loopspec`
- **THEN** 生成 `config.yaml`/`schemas/`/`changes/`，且 `schemas/` 下包含内置 schema 的完整拷贝

#### Scenario: --no-builtin 跳过内置 schema
- **WHEN** 执行 `loopspec init ./loopspec --no-builtin`
- **THEN** 生成空的 `schemas/` 目录，不包含任何内置 schema 文件

#### Scenario: 非交互且未传 --tools 时行为不变
- **WHEN** 在非交互环境下执行 `loopspec init ./loopspec`（不传 `--tools`）
- **THEN** 只初始化 `config.yaml`/`schemas/`/`changes/`，不写入任何 `.claude/`/`.codex/` 等工具目录，行为与引入 `--tools` 之前完全一致

#### Scenario: --tools all 选中全部注册工具
- **WHEN** 执行 `loopspec init ./loopspec --tools all`
- **THEN** 为全部已注册工具（`claude`/`codex`/`opencode`/`cursor`/`windsurf`）在项目根目录写入其 skill 文件（及有适配器时的命令文件）

#### Scenario: 脚手架写入项目根而非 workflow home
- **WHEN** 在项目 `myproject/` 下执行 `loopspec init ./loopspec --tools claude`
- **THEN** 文件写入 `myproject/.claude/`，`myproject/loopspec/.claude` 不存在，且响应的 `projectRoot` 为 `myproject` 的绝对路径

#### Scenario: --tools 指定子集
- **WHEN** 执行 `loopspec init ./loopspec --tools claude,codex`
- **THEN** 只为 `claude` 与 `codex` 写入脚手架文件，其余已注册工具不受影响

#### Scenario: --tools 传入未注册的工具 id
- **WHEN** 执行 `loopspec init ./loopspec --tools not-a-real-tool`
- **THEN** 命令报错，`fix` 中列出全部合法工具 id，且不产生任何文件系统变更

#### Scenario: 交互式环境下未传 --tools 时提示选择
- **WHEN** 在可交互终端执行 `loopspec init ./loopspec`（不传 `--tools`）
- **THEN** 打印已注册工具的编号列表，等待用户输入逗号分隔的编号或 `all`/`none`，再按用户选择写入对应脚手架文件

### Requirement: loopspec schemas list/show/validate
`loopspec schemas list` SHALL 列出当前 workflow home 下可用的 schema（名称、版本、来源、路径、节点列表）。`loopspec schemas show <name>` SHALL 显示该 schema 的详细信息，包括每个节点的 `id`/`requires`/`generates`/是否为 gate，以结构化文本或 JSON 列表形式呈现节点间的依赖关系；v1 SHALL 不要求提供图形化（ASCII）依赖图渲染。`loopspec schemas validate <name>` SHALL 执行完整加载与校验，成功时返回 `valid: true` 及拓扑排序后的 `buildOrder`；失败时按统一错误格式返回具体的校验错误与修复建议。

#### Scenario: 列出可用 schema
- **WHEN** 执行 `loopspec schemas list`
- **THEN** 返回当前 workflow home 下全部可加载 schema 的名称、版本、来源与节点列表

#### Scenario: 校验通过的 schema
- **WHEN** 执行 `loopspec schemas validate <valid-schema>`
- **THEN** 返回 `{"valid": true, "name": <name>, "buildOrder": [...]}`

#### Scenario: 校验失败的 schema
- **WHEN** 执行 `loopspec schemas validate <invalid-schema>`
- **THEN** 返回统一错误格式，`message` 描述具体校验失败原因，`fix` 给出可执行的修复建议

### Requirement: loopspec new 创建 change
`loopspec new <change-name> [--schema S] [--json]` SHALL 校验 change 名符合 kebab-case（否则报 `invalid_change_name`）、change 不存在（否则报 `change_exists`）；创建成功 SHALL 在 change 目录写入 `.workflow.yaml`（记录选中的 `schema` 与 `created` 日期）与初始 `state.md`，并返回 `changeName`/`schemaName`/`artifactsDir`/`schemaPath`/`changeRoot`/`artifactRoot`/`statePath`/`metadataPath`/`created`/`createdFiles`/`nextSteps`。

当 `config.yaml` 配置了多个候选 schema 且命令未显式传 `--schema` 时，SHALL 返回 `schema_selection_required`（含 `schemas` 候选列表与 `selectionInstruction`），且不创建任何 change 目录或文件；调用方选定后需重新执行并显式传入 `--schema <selected>`。当 `--schema` 指定的名称不在 `config.yaml` 候选列表中时 SHALL 报 `config_invalid`。

#### Scenario: 创建成功输出契约
- **WHEN** `loopspec new add-payment --json` 执行成功
- **THEN** 输出符合上述字段契约，且 `.workflow.yaml` 与 `state.md` 已实际写入 change 目录

#### Scenario: 使用 schema 二级 path
- **WHEN** 选中的 schema 在 `config.yaml` 中配置了 `path: bugfix`
- **THEN** 输出的 `schemaPath` 为 `"bugfix"`，`artifactRoot` 为 `<changeRoot>/bugfix`

#### Scenario: 多候选未指定 schema
- **WHEN** `config.yaml` 配置了多个候选 schema，且 `loopspec new add-payment --json` 未传 `--schema`
- **THEN** 返回 `schema_selection_required`，包含全部候选与 `selectionInstruction`，且不创建 change 目录

#### Scenario: 选定后重新创建成功
- **WHEN** 在收到 `schema_selection_required` 后执行 `loopspec new add-payment --schema secure-spec-driven --json`
- **THEN** 创建成功，`.workflow.yaml` 中记录的 `schema` 为 `secure-spec-driven`

#### Scenario: --schema 不在候选列表中
- **WHEN** 传入的 `--schema` 名称不在 `config.yaml` 的 `schemas[*].name` 列表中
- **THEN** 报 `config_invalid`

#### Scenario: 同名重复创建
- **WHEN** 对已存在的 change 名再次执行 `loopspec new`
- **THEN** 报 `change_exists`

#### Scenario: 非法 change 名
- **WHEN** change 名不符合 `^[a-z][a-z0-9]*(-[a-z0-9]+)*$` 规则（如包含大写字母、下划线或 `/`）
- **THEN** 报 `invalid_change_name`

### Requirement: loopspec status 查看状态
`loopspec status <change-name> --json` SHALL 扫描该 change 的 artifact 根目录与 `.attempts/`，返回每个节点的当前状态、`isComplete`、`statePath`/`stateExists`、`pendingRollback`（存在 `failed` gate 时非 null，含 `gate`/`closure`/`command`；否则为 `null`）以及 `nextSteps`。`nextSteps` SHALL 按拓扑序找到第一个 `exhausted` 或 `failed` 的 gate 优先返回对应的人工介入或回退指令；若无失败/耗尽 gate，则返回第一个 `ready` 节点对应的 `loopspec instructions` 命令；若全部完成则返回完成提示。本命令 SHALL 不返回节点的模板正文。

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

### Requirement: loopspec instructions 生成节点指令
`loopspec instructions <node> --change <change> --json` SHALL 返回该节点的生成指令上下文：普通节点返回单一 `template` 与单一 `resolvedOutputPath`；gate 节点返回 `templates.pass/fail` 与 `resolvedOutputPath.pass/fail`，并在指令文案中要求 LLM 只能二选一写入。响应 SHALL 同时包含 `description`、展开后的 `instruction` 字符串（不暴露原始 `instruction.file` 路径）、`context`、按节点 ID 匹配的 `rules`、`dependencies`（含各依赖的完成状态与路径）、`unlocks`（直接后继节点列表）、`statePath`/`state`/`warnings`、`priorAttempts`。

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

### Requirement: loopspec rollback 执行回退
`loopspec rollback <change-name> --json` SHALL 依据 `gate-rollback` 能力执行归档，成功时返回 `changeName`/`gate`/`round`/`closure`/`archivedFiles`/`archiveDir`/`rollbacksUsed`/`maxRetries`/`nextSteps`（指向后续 `loopspec status`）。前置条件不满足时按统一错误格式返回 `no_failed_gate` 或 `retries_exhausted`。

#### Scenario: 回退成功输出契约
- **WHEN** 存在 `failed` 状态的 gate 并执行 `loopspec rollback <change> --json`
- **THEN** 输出符合上述字段契约，且 `rollbacksUsed` 已增加

### Requirement: loopspec history 查看回退历史
`loopspec history <change-name> --json` SHALL 扫描该 change 的 `.attempts/round-*/_meta.yaml`，按 round 升序返回 `rounds` 数组，每项含 `round`/`gate`/`verdict`/`summary`/`resetClosure`/`archivedFiles`/`archiveDir`/`archivedAt`。

#### Scenario: 查看历史回退记录
- **WHEN** 该 change 已发生过至少一次回退
- **THEN** `loopspec history <change> --json` 返回包含对应轮次完整信息的 `rounds` 数组

### Requirement: nextSteps 生成策略的优先级顺序
系统在生成 `nextSteps` 时 SHALL 严格按以下优先级遍历拓扑序节点并在命中第一项后立即返回：`exhausted` 状态的 gate（提示人工介入并建议查看 `loopspec history`）> `failed` 状态的 gate（提示执行 `loopspec rollback`）> 第一个 `ready` 节点（提示执行 `loopspec instructions`）> 全部完成提示。`exhausted`/`failed` 分支 SHALL 优先于 `ready` 分支，防止上游节点因产物被回退清空而被误判为可直接覆写。

#### Scenario: failed 优先于 ready
- **WHEN** 某 gate 处于 `failed` 状态，同时其上游节点因回退而处于物理上"依赖齐备、产物待生成"的 `ready` 状态
- **THEN** `nextSteps` 返回该 gate 的回退指令，而不是上游节点的生成指令

#### Scenario: 多个 gate 同时失败时只返回拓扑序最早的一个
- **WHEN** schema 中有多个 gate 同时处于 `failed` 或 `exhausted` 状态
- **THEN** `nextSteps` 只返回拓扑序中最早出现的那个 gate 对应的指令，避免一次触发多个无关闭包的回退

