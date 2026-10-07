## ADDED Requirements

### Requirement: Profile 是可复用的 Fragment 工作流模板
Profile SHALL 以 `flow` 声明 Fragment 实例及实例级 requires，支持串行和并行分支；SHALL 包含说明与可选 LLM 指引、保护要求和有限恢复规则。Profile SHALL NOT 维护执行状态或持久化审批原话。系统 SHALL 提供 Profile 的发现、校验、保存和复用。

#### Scenario: 前后端并行模板
- **WHEN** fe、be 同时依赖 design，qa 依赖 fe 与 be
- **THEN** Plan 图允许前后端并行，并阻止 qa 在任一分支未完成时执行

#### Scenario: 保存已执行 Plan 为模板
- **WHEN** 用户从 Change 保存 Profile
- **THEN** 系统保存定义、路由和指引，不保存 Gate 证据、执行状态、重试计数或审批结果

### Requirement: LLM 可直接采用或参考 Profile 生成 Plan
Plan 请求 SHALL 完整指定最终 flow、recovery、选择理由和受保护偏离。based_on SHALL 可选；存在时记录来源 Profile 与偏离，不存在时仍校验项目约束。系统 SHALL NOT 从请求 prose 推断隐式执行边。

#### Scenario: 前端小需求
- **WHEN** 请求参考 frontend-small-change 只选 FE、前端 QA 和最终保障
- **THEN** 编译生成轻量 Plan，不要求大型 PRD 或 BE 实现阶段

#### Scenario: 自行组合
- **WHEN** 用户没有指定 based_on，但请求定义了合法 Fragment 图
- **THEN** 系统在满足项目最低约束后允许编译

### Requirement: 项目最低保护不能通过换模板绕过
项目 config 的保障要求与 Profile 的额外保护 SHALL 合并并固化到 Plan。受保护省略 SHALL 要求理由及 planDigest 绑定的人工原话。代码保障流程的未知路径失败、证据一致性检查及最终保障依赖交付分支 SHALL 不允许由自动省略逻辑关闭。

#### Scenario: 更换轻量 Profile
- **WHEN** Agent 选择没有后端流程的 Profile，但项目要求最终保障
- **THEN** Plan 仍必须包含最终保障及项目 Diff 覆盖规则

#### Scenario: 审批绑定资源
- **WHEN** 人批准省略后，理由、图、指令或保障规则改变
- **THEN** 旧审批失效，系统返回新的摘要并要求重新决定

### Requirement: 自包含不可变计划
Plan SHALL 保存规范身份、Node DAG、Fragment 归属、恢复边、资源、约束、固定基线和修订来源。Plan 摘要 SHALL 绑定全部有效结构、理由、基线和资源哈希。Plan SHALL 不存完成状态。运行时 SHALL 只读取活动快照和当前证据。

#### Scenario: 来源删除
- **WHEN** 创建 Plan 后删除来源 Profile 或 Fragment
- **THEN** status 与 instructions 仍按原活动 Plan 工作

#### Scenario: 审批后 HEAD 变化
- **WHEN** 校验提议返回固定基线后仓库 HEAD 改变
- **THEN** 创建必须使用原基线及原摘要，或重新校验提议，不能静默换基线

### Requirement: 原子激活与并发隔离
落盘 SHALL 使用写锁、有界缓存、受约束暂存路径、资源哈希复核、排他最终目录和原子指针替换。基础修订版 SHALL 在写锁内复核。中断或失败 SHALL 不使活动指针指向部分计划。

#### Scenario: 两个并发修订
- **WHEN** 两个请求都基于修订版 1
- **THEN** 只有先成功者激活修订版 2，另一请求报告过期且不覆盖新计划

### Requirement: 旧格式兼容适配
既有 Schema/Change SHALL 通过内部适配器保留原有生命周期行为。新用户接口 SHALL 采用 Node/Fragment/Profile/Plan 表述。新格式 SHALL 具有版本标识，旧 CLI SHALL 明确拒绝未知元数据。

#### Scenario: 旧 Change 回归
- **WHEN** 对原 Schema Change 执行 status/instructions/rollback/archive
- **THEN** 原路径、进度推导和判定语义保持兼容

### Requirement: 状态按产物与有效证据推导
系统 SHALL 保留 done/ready/blocked/failed/exhausted 五态。新增 next SHALL 使用与 status.nextSteps 一致的确定性推进逻辑。过期保障证据 SHALL 使节点重新就绪并附 evidence_stale 原因，而不伪造 FAIL 或继续 done。

#### Scenario: 保障后修改代码
- **WHEN** Assurance PASS 后当前 Diff 摘要发生变化
- **THEN** Assurance 重新就绪，后续交付节点及 Change 完成判断被阻塞

### Requirement: 模板引擎能力版本可验证
模板 SHALL 声明最低能力版本；V1 模板可使用人工 delivery-review，V2 代码模板 SHALL 使用确定性 Assurance。引擎 SHALL 拒绝尚未实现的能力，不能把未执行检查显示为通过。

#### Scenario: V1 请求 V2 保障
- **WHEN** 仅支持第一版本的引擎收到含系统 Assurance 的 Plan
- **THEN** 以 unsupported_capability 拒绝请求并给出版本指引
