## MODIFIED Requirements

### Requirement: Profile 是可复用的 Fragment 工作流模板
Profile SHALL 以 `flow` 声明 Fragment 实例及实例级 requires，支持串行和并行分支；flow 条目 SHALL 可声明 on_fail；Profile SHALL 包含说明与可选 LLM 指引，SHALL NOT 包含 recovery、protected 或 min_engine_version。Profile SHALL NOT 维护执行状态。系统 SHALL 提供 Profile 的发现、校验、保存和复用；`profile save` SHALL 取自活动 Plan 的 spec.flow。

#### Scenario: 前后端并行模板
- **WHEN** fe、be 同时依赖 design，qa 依赖 fe 与 be
- **THEN** Plan 图允许前后端并行，并阻止 qa 在任一分支未完成时执行

#### Scenario: 保存已执行 Plan 为模板
- **WHEN** 用户执行 profile save new-template -c AFD1111
- **THEN** 系统保存 flow（含 flow 条目上的 on_fail）与说明，不保存 nodes、证据、执行状态或返工次数

#### Scenario: 旧字段
- **WHEN** Profile 声明 protected 或 min_engine_version
- **THEN** 校验以未知字段拒绝

### Requirement: LLM 可直接采用或参考 Profile 生成 Plan
Plan 请求文件 SHALL 指定最终 flow 与可选 based_on，修订请求 SHALL 另含 base_revision，SHALL NOT 包含 reasons、deviations 或 recovery；Plan 级说明 SHALL 通过 plan create 的 --note 写入 meta.note。系统 SHALL NOT 从请求 prose 推断隐式执行边。

#### Scenario: 前端小需求
- **WHEN** 请求参考 frontend-small-change 只选 FE、前端 QA 和最终保障
- **THEN** 编译生成轻量 Plan，不要求大型 PRD 或 BE 实现阶段

#### Scenario: 自行组合
- **WHEN** 请求没有 based_on，但定义了合法 Fragment 图
- **THEN** 系统在满足项目最低约束后允许编译

### Requirement: 项目最低保护不能通过换模板绕过
项目 config.yaml 的 required_fragments 与 assurance_rules SHALL 在 plan create 与 plan approve 时按当前配置检查：缺少必需 Fragment 或配置了保障规则却缺少保障节点 SHALL 拒绝。代码保障流程的未知路径失败、证据一致性检查及最终保障依赖交付分支 SHALL 不能关闭。执行期间 SHALL 读取最新的 config.yaml。config.yaml SHALL 只接受 artifacts_dir 与 workflow 字段。

#### Scenario: 更换轻量 Profile
- **WHEN** Agent 选择没有后端流程的 Profile，但项目要求最终保障
- **THEN** Plan 仍必须包含最终保障节点

#### Scenario: 旧配置字段
- **WHEN** config.yaml 含 schema、schemas、schema_selection、context、rules 或 default_profile
- **THEN** 加载以未知字段拒绝并提示删除

### Requirement: 自包含不可变计划
Plan SHALL 持久化为 `plans/<NNN>/plan.yaml`，spec SHALL 保存实例级 flow 与展开后的叶子 nodes（含实例路径、依赖、产物、Gate、Gate 内 on_fail 与资源路径）；引用成员树 SHALL 由 nodes 推导，SHALL NOT 另存。执行图结构 SHALL 以确认时的 spec 为准，Fragment 定义后续变化 SHALL NOT 改变已确认的图；指令、模板与保障规则等资源 SHALL 在执行时读取最新内容。引用节点 SHALL 不另行执行为黑盒任务。Plan SHALL 不存完成状态。

#### Scenario: Fragment 定义变化
- **WHEN** Plan 确认后 backend-implementation 的 fragment.yaml 增加了一个节点
- **THEN** 活动 Plan 的节点不变；修订或新 Plan 才会采用新定义

#### Scenario: 指令内容变化
- **WHEN** Plan 执行中 backend-code 的指令文件被修改
- **THEN** node instructions 返回修改后的内容

### Requirement: 原子激活与并发隔离
所有改变 Plan 状态的操作 SHALL 在逐 Change 写锁内校验并按固定顺序落盘；基础修订与摘要 SHALL 在写锁内复核。每条操作 SHALL 只有一次生效写入，中断 SHALL 不产生两个 approved Plan 或部分写入的 plan.yaml，中断后状态 SHALL 等于操作之前或之后。

#### Scenario: 两个并发修订
- **WHEN** 两个修订请求都基于 revision 1
- **THEN** 只有先确认者生效为 revision 2，另一请求返回 stale_revision 且不覆盖

### Requirement: 状态按产物与有效证据推导
系统 SHALL 保留 done/ready/blocked/failed/exhausted 五态，并以活动 Plan 的 Plan 目录为根推导。change next SHALL 使用与 change status 的 nextSteps 一致的确定性推进逻辑。过期证据 SHALL 使节点重新就绪并附 evidence_stale 原因，而不伪造 FAIL 或继续 done。Change 完成 SHALL 实时推导，SHALL NOT 落盘。

#### Scenario: 保障后修改代码
- **WHEN** 保障节点 PASS 后当前 Diff 摘要发生变化
- **THEN** 保障节点重新就绪，Change 状态回到 active

## REMOVED Requirements

### Requirement: 模板引擎能力版本可验证
**Reason**: 引擎只有一种能力，V1/V2 分级是早期分阶段交付的产物。
**Migration**: 删除 Fragment 与 Profile 中的 min_engine_version；删除 manual-v1 Profile 与 delivery-review Fragment，使用 bugfix 或自行组合的 Plan。

### Requirement: 旧格式兼容适配
**Reason**: 旧 Schema 流程整体删除，CLI 只保留一套工作流。
**Migration**: 升级前用 v1.x 完成并归档旧 Schema Change；未完成的需求在 2.0.0 中用 change new 重新建立。
