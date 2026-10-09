## ADDED Requirements

### Requirement: 组合命令组
CLI SHALL 提供组合能力中定义的 `fragments`、`compose`、`recompose`、`plans` 和 `profiles` 命令面。每个命令 SHALL 支持 `--json`，使用统一的 `{error,message,fix}` 失败信封，并避免把请求说明或审批文本嵌入生成的 Shell 命令。

#### Scenario: JSON 校验响应
- **WHEN** `loopspec compose validate <request> --json` 成功
- **THEN** 标准输出是一个 JSON 文档，包含 `valid`、`planDigest`、`requiresApproval`、`readyToApply`、所选片段、省略项、节点和构建顺序

#### Scenario: 组合失败
- **WHEN** 任一组合命令拒绝不可信输入
- **THEN** 命令以退出码 1 结束，并返回统一结构化错误契约且不显示 Traceback

### Requirement: 现有命令响应标识活动计划
对于计划型变更，`new` 和 `status` JSON SHALL 增加 `planRevision`、`planDigest` 和 `selectedFragments`；对于旧式变更，这些字段 SHALL 分别为 null 或空列表，且不改变现有字段。`instructions` 与 `rollback` SHALL 继续使用共享变更上下文解析器所选的同一个活动 `LoadedSchema`。

#### Scenario: 查看组合变更状态
- **WHEN** 对组合变更执行 `status`
- **THEN** 响应在保留全部现有节点和状态字段的同时标识活动修订版及其摘要

#### Scenario: 查看旧式变更状态
- **WHEN** 对旧式 Schema 变更执行 `status`
- **THEN** 现有字段和后续步骤语义保持不变

### Requirement: 新增组合错误码
CLI SHALL 记录并发出不同错误码，分别表示片段缺失或无效、组合请求无效、需要受保护门禁审批、计划落盘失败、计划修订版过期、重组不安全、Profile 缺失和 Profile 冲突。

#### Scenario: Agent 获得可执行的纠正指引
- **WHEN** 组合请求被拒绝
- **THEN** 错误码能够区分被违反的不变量，且 `fix` 指出准确的下一步纠正动作

### Requirement: 初始化包含组合目录
`loopspec init` SHALL 创建 `fragments/` 和 `profiles/`，并在未设置 `--no-builtin` 时复制内置片段。现有 `schemas/`、`changes/`、配置和工具脚手架行为 SHALL 保持兼容。

#### Scenario: 不复制内置资源的初始化
- **WHEN** 执行 `init --no-builtin`
- **THEN** 空的 fragments 和 profiles 目录存在，且没有复制内置片段

### Requirement: 文档与 JSON 契约一致
中英文 CLI、配置、Schema、概览、Agent 协议和工作流文档 SHALL 一致描述组合与重组。文档测试 SHALL 覆盖命令名、字段、错误码、内置片段和双语一致性。

#### Scenario: 文档漂移
- **WHEN** 组合命令、字段、错误码或内置片段发生变化但对应文档未更新
- **THEN** 文档一致性测试失败
