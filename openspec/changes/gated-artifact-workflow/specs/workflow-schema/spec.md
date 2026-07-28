## ADDED Requirements

### Requirement: Schema 结构定义与加载
系统 SHALL 提供一套 YAML schema 格式，描述工作流的节点列表（`nodes`）、每个节点的产物路径（`generates`）、模板（`template`）、依赖（`requires`）、生成指导（`instruction`）以及可选的门禁配置（`gate`）。加载 SHALL 分两步执行：先用 Pydantic 模型做结构校验（`extra: "forbid"`，未知字段必须报错），再执行语义校验；任一语义校验失败 SHALL 立即抛出携带具体错误信息的异常，不继续加载。

#### Scenario: 合法 schema 加载成功
- **WHEN** 一个 schema.yaml 通过全部 14 条语义校验
- **THEN** 系统返回可用的 `WorkflowSchema` 对象，其 `build_order()` 可被后续调用

#### Scenario: 未知字段导致加载失败
- **WHEN** schema.yaml 中出现未在模型中定义的字段（如 `require` 少写一个 `s`）
- **THEN** 系统 SHALL 报错而不是静默忽略该字段

### Requirement: 节点 ID 与依赖合法性校验
系统 SHALL 校验：节点 ID 在 schema 内唯一；`requires` 引用的每个 ID 都必须是 schema 中存在的节点；`requires` 关系构成的图必须无环。

#### Scenario: 重复节点 ID
- **WHEN** 两个节点使用相同的 `id`
- **THEN** 系统报错，错误信息包含重复的 ID

#### Scenario: requires 引用不存在的节点
- **WHEN** 某节点的 `requires` 列表包含一个未定义的节点 ID
- **THEN** 系统报错，错误信息包含该未知 ID

#### Scenario: requires 成环
- **WHEN** 若干节点的 `requires` 关系构成一个环（如三节点环）
- **THEN** 系统报错，错误信息包含完整的环路径，路径顺序正确

### Requirement: 普通节点的产物与模板校验
非 gate 节点 SHALL 必须声明字符串类型的 `generates`（产物路径）和存在于 schema `templates/` 目录下的 `template` 文件；缺失或文件不存在 SHALL 报错。

#### Scenario: 非 gate 节点缺少 generates
- **WHEN** 一个没有 `gate` 配置的节点未声明 `generates`
- **THEN** 系统报错

#### Scenario: 模板文件缺失
- **WHEN** 节点声明的 `template` 文件名在 schema 的 `templates/` 目录下不存在
- **THEN** 系统抛出模板加载错误，指明缺失的文件路径

### Requirement: Gate 节点配置校验
gate 节点（声明了 `gate` 字段的节点）SHALL 必须同时声明 `gate.outputs.pass`/`gate.outputs.fail`（两个具体、不同的非 glob 路径）与 `gate.templates.pass`/`gate.templates.fail`（且模板文件必须存在）；`generates`/`template` 若存在也必须是字符串或 `null`。

#### Scenario: gate 使用 generates: null 且声明 gate.outputs
- **WHEN** 一个 gate 节点的 `generates` 为 `null`，但完整声明了 `gate.outputs.pass` 与 `gate.outputs.fail`
- **THEN** 加载通过

#### Scenario: gate 缺少 outputs
- **WHEN** 一个声明了 `gate` 字段的节点未提供 `gate.outputs.pass` 或 `gate.outputs.fail`
- **THEN** 系统报错

#### Scenario: gate 缺少 templates
- **WHEN** 一个 gate 节点未提供 `gate.templates.pass` 或 `gate.templates.fail`
- **THEN** 系统报错

#### Scenario: gate 的 pass/fail 输出是 glob 或相同
- **WHEN** `gate.outputs.pass` 与 `gate.outputs.fail` 相同，或任一路径包含 glob 字符（`*`、`?`、`[`）
- **THEN** 系统报错，提示两个输出路径必须是具体且互不相同的路径

#### Scenario: gate 模板文件缺失
- **WHEN** `gate.templates.pass` 或 `gate.templates.fail` 指向的文件在 `templates/` 目录下不存在
- **THEN** 系统抛出模板加载错误

### Requirement: on_fail.reset 必须指向 gate 的祖先节点
gate 的 `on_fail.reset` 列表中每个节点 ID SHALL 必须存在于 schema 中，且必须是该 gate 节点在依赖图中的祖先（通过 `requires` 的传递闭包判定）；引用不存在或非祖先节点 SHALL 报错。

#### Scenario: reset 指向不存在的节点
- **WHEN** `on_fail.reset` 包含一个 schema 中不存在的节点 ID
- **THEN** 系统报错，错误信息包含该未知 ID

#### Scenario: reset 指向非祖先节点
- **WHEN** `on_fail.reset` 包含一个与该 gate 无依赖关系的节点 ID
- **THEN** 系统报错，提示该节点不是该 gate 的祖先

#### Scenario: reset 指向直接或传递祖先
- **WHEN** `on_fail.reset` 包含该 gate 的直接祖先节点，或隔一层的传递祖先节点
- **THEN** 加载通过

### Requirement: instruction 内联字符串与文件引用
节点的 `instruction` 字段 SHALL 支持内联字符串或 `{file: <name>}` 引用形式；引用形式 SHALL 从 schema 的 `instructions/` 目录加载文件内容并展开为字符串；`file` 字段 SHALL 必须是安全相对路径（禁止绝对路径、`..`、空路径段），否则报 `schema_invalid`；文件缺失 SHALL 抛出指令加载错误。

#### Scenario: instruction 为内联字符串
- **WHEN** 节点的 `instruction` 直接写成一段字符串
- **THEN** 加载通过，且该字符串原样用于展开

#### Scenario: instruction.file 指向存在的文件
- **WHEN** 节点的 `instruction` 为 `{file: security.md}`，且该文件存在于 `instructions/` 目录
- **THEN** 加载成功，加载结果为该文件的展开字符串内容

#### Scenario: instruction.file 文件缺失
- **WHEN** `instruction.file` 指向的文件不存在
- **THEN** 系统抛出指令加载错误

#### Scenario: instruction.file 路径不安全
- **WHEN** `instruction.file` 是绝对路径或包含 `..`
- **THEN** 系统报 `schema_invalid`

### Requirement: 保留路径不得被节点产物声明
系统 SHALL 拒绝任何节点将 `generates`、`gate.outputs.pass` 或 `gate.outputs.fail` 声明为保留路径（`state.md`、`.workflow.yaml`），因为这些是 change 级系统文件，不是节点产物。

#### Scenario: generates 指向保留文件名
- **WHEN** 某节点的 `generates` 为 `state.md` 或 `.workflow.yaml`
- **THEN** 系统报 `schema_invalid`

#### Scenario: gate 输出指向保留文件名
- **WHEN** 某 gate 的 `gate.outputs.pass` 或 `gate.outputs.fail` 为 `state.md` 或 `.workflow.yaml`
- **THEN** 系统报 `schema_invalid`

### Requirement: 项目级 config.yaml 与多 schema 候选
项目级 `config.yaml` SHALL 支持单一默认 `schema` 或多个候选 `schemas`（至少配置其中之一），每个候选项含 `name`/`path`/`description`/`when`；当配置多个候选且未提供 `--schema` 参数时，创建 change SHALL 返回 `schema_selection_required` 结构化响应（包含全部候选、`selectionInstruction`、修复建议），不创建 change 目录。

#### Scenario: 仅配置默认 schema
- **WHEN** `config.yaml` 只配置了 `schema` 字段
- **THEN** 加载成功，作为唯一默认 schema

#### Scenario: 配置多个候选 schema
- **WHEN** `config.yaml` 配置了 `schemas` 列表（多项）
- **THEN** 加载成功，保留每项的 `description`/`when`/`path` 与 `schema_selection.instruction`

#### Scenario: schema 与 schemas 同时配置但默认值不在候选中
- **WHEN** `config.yaml` 同时配置 `schema: X` 与 `schemas`，且 `X` 不在 `schemas[*].name` 中
- **THEN** 系统报 `config_invalid`

#### Scenario: 候选 schema 名称重复
- **WHEN** `schemas[*].name` 出现重复值
- **THEN** 系统报 `config_invalid`

#### Scenario: 既无 schema 也无 schemas
- **WHEN** `config.yaml` 既未配置 `schema` 也未配置 `schemas`
- **THEN** 系统报 `config_invalid`

#### Scenario: 多候选且未指定 --schema 时创建 change
- **WHEN** 调用 `loopspec new <name> --json` 且 `config.yaml` 配置了多个候选 schema，命令未传 `--schema`
- **THEN** 系统返回 `schema_selection_required` 及全部候选与选择说明，且不在磁盘上创建该 change 的任何文件

### Requirement: 路径安全校验
`artifacts_dir`、`schemas[*].path`、节点 `generates`、`gate.outputs.pass/fail`、模板与指令的相对路径 SHALL 在 normalize 后校验仍位于允许的根目录内；禁止绝对路径、`..` 与空路径段，违反 SHALL 报错（`schema_invalid` 或 `config_invalid`）。

#### Scenario: artifacts_dir 包含路径穿越
- **WHEN** `config.yaml` 的 `artifacts_dir` 或某个 `schemas[*].path` 是绝对路径或包含 `..`
- **THEN** 系统报 `config_invalid`
