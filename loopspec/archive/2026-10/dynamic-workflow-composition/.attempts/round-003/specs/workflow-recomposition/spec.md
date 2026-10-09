## ADDED Requirements

### Requirement: 基于修订版检查的重组
`loopspec recompose <change> --composition <relative-request>` SHALL 只为计划型活动变更接受完整替换组合。请求的 `base_revision` MUST 等于活动修订版。修订版不一致时，操作 SHALL 在落盘前被拒绝。

#### Scenario: 当前修订版
- **WHEN** 请求指定活动修订版并满足全部校验规则
- **THEN** 重组进入冻结节点比较

#### Scenario: 并发导致请求过期
- **WHEN** 另一次重组已经推进活动修订版
- **THEN** 过期请求以 `plan_revision_stale` 失败，较新的计划保持活动状态

### Requirement: 已执行工作和当前工作保持冻结
重组 SHALL 冻结每个已完成、失败或重试耗尽的节点，Attempts 历史中出现的每个节点，确定性当前游标之前的每个节点，以及第一个就绪节点本身。每个冻结节点 MUST 保留，且在新计划中的语义定义必须相同。

#### Scenario: 删除已完成节点
- **WHEN** 替换计划省略了其输出已使其完成的节点
- **THEN** 重组失败，并指出该冻结节点

#### Scenario: 修改当前游标
- **WHEN** 替换计划修改第一个就绪节点的输出、依赖、指令、模板、跟踪关系或门禁策略
- **THEN** 重组在写入修订版 N+1 前失败

#### Scenario: 修改未来待办工作
- **WHEN** 所选片段只添加、删除或修改严格位于游标之后的节点，且完整图仍有效
- **THEN** 替换计划具备激活资格

### Requirement: 历史尝试证据冻结归属
如果 Attempts 轮次在 `reset_closure` 中记录了某节点，或归档了某节点拥有的产物，该节点 SHALL 被冻结，即使其当前状态为就绪或阻塞。Attempts 元数据不可读时，重组 SHALL 失败，而不是猜测。

#### Scenario: 曾经失败的未来节点
- **WHEN** 回滚已归档某节点的输出，而该节点当前再次处于就绪状态
- **THEN** 重组不能删除或重新定义该节点

### Requirement: 重组创建不可变历史
接受的重组 SHALL 创建修订版 N+1，保留全部早期计划目录，在新 Manifest 中记录前序摘要和变更摘要，并原子更新元数据。系统 SHALL NOT 原地编辑任何现有计划目录。

#### Scenario: 重组成功
- **WHEN** 修订版 1 被安全重组
- **THEN** 修订版 1 保持可读，修订版 2 成为活动版本，且 `status` 使用修订版 2

#### Scenario: 修订版激活失败
- **WHEN** 修订版 2 的暂存或校验失败
- **THEN** 修订版 1 保持活动且不变

### Requirement: 受保护门禁策略适用于重组
重组 SHALL 对替换计划重新执行受保护片段策略。删除尚未执行的受保护片段 SHALL 要求省略理由以及绑定替换计划摘要的新审批，即使前一修订版已经获得其他审批。

#### Scenario: 删除待执行的安全审查
- **WHEN** 修订版 2 省略待执行的受保护安全审查片段
- **THEN** 在记录新的匹配审批之前不得激活修订版 2

### Requirement: 项目自定义片段使用相同校验
用户 SHALL 能在 `<home>/fragments/` 下添加片段。内置片段与项目自定义片段 SHALL 使用相同清单结构、来源解析、组合校验、路径限制、摘要规则和冲突处理。

#### Scenario: 有效自定义片段
- **WHEN** 项目片段引用有效自定义 Schema 节点
- **THEN** 该片段可以像内置片段一样被列出、选择、快照和重组

#### Scenario: 自定义片段冲突
- **WHEN** 自定义片段与内置片段发生节点或输出归属冲突
- **THEN** 组合拒绝该请求，不根据来源设置优先级

### Requirement: 可复用工作流 Profile
`loopspec profiles save <name> --change <change>` SHALL 把活动计划的片段选择、纳入理由、省略理由、说明和来源摘要保存到 `<home>/profiles/<name>.yaml`。命令 SHALL 拒绝不安全名称，并在没有显式覆盖选项时拒绝名称冲突。Profile SHALL NOT 保存审批原话，也 SHALL NOT 使旧审批可被复用。

#### Scenario: 保存可复用 Profile
- **WHEN** 有效组合变更保存为 `focused-change` Profile
- **THEN** 该 Profile 可以被检查并作为其他组合的基础

#### Scenario: 不复制审批
- **WHEN** 已保存计划在获得审批后省略了受保护门禁
- **THEN** Profile 包含省略理由但不包含审批，且新变更需要新的摘要绑定决定

### Requirement: 基于 Profile 创建
`loopspec new <change> --profile <name>` SHALL 解析已保存的选择与理由，并针对当前片段目录重新编译。如果 Profile 保留全部受保护片段，可以直接创建；如果省略任何受保护片段，创建 SHALL 要求工作流 Home 相对路径下的审批覆盖文件，其中包含与当前摘要匹配的审批。

#### Scenario: 安全 Profile 直接创建
- **WHEN** Profile 选择全部受保护片段
- **THEN** `new --profile` 无需组合审批即可创建新计划修订版

#### Scenario: Profile 来源已变化
- **WHEN** 保存 Profile 后片段或来源 Schema 发生变化
- **THEN** 当前校验生成当前摘要和图，而不静默复用 Profile 的来源摘要

### Requirement: 计划历史检查
`loopspec plans show <change>` 与 `loopspec plans history <change>` SHALL 在不读取任意路径的前提下报告活动计划和不可变修订版。JSON 输出 SHALL 包含修订版、摘要、前序摘要、所选片段、省略项、审批是否存在以及活动状态。

#### Scenario: 检查已重组变更
- **WHEN** 一个变更包含两个修订版
- **THEN** 历史按修订版升序报告两者，并且只把修订版 2 标记为活动
