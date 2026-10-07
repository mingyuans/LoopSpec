## ADDED Requirements

### Requirement: 有限 Fragment 级失败路由
恢复规则 SHALL 绑定具体 Gate 实例、有限 route_case 与目标 Fragment 实例。报告 SHALL 只选择枚举值，SHALL NOT 自由指定目标。目标 SHALL 已在活动图内且位于失败 Gate 之前；未知分类、无目标和重试耗尽 SHALL 保持阻塞并明确报告。

#### Scenario: QA 后端失败
- **WHEN** qa/test 返回允许的 backend 分类
- **THEN** 系统选择 be 实例及其全部实现、测试、Security Review、PR Review Node 进行返工

#### Scenario: 非法分类
- **WHEN** 报告包含未声明分类或任意路径作为目标
- **THEN** 系统拒绝路由且不修改执行产物

### Requirement: 返工重置闭包与历史
Fragment 返工 SHALL 重置目标全部成员、失败 Gate 和传递下游，包括 Gate 与 Assurance 证据。无依赖的并行分支 SHALL 保留。归档 SHALL 不还原业务代码，SHALL 记录路由与重置闭包，并将失败信息提供给下轮 instructions。

#### Scenario: BE 分支返工
- **WHEN** fe 和 be 为并行分支，qa 依赖二者
- **THEN** be、qa 和 assurance 重置，独立 fe 产物保留

#### Scenario: 中断归档
- **WHEN** 返工归档中途失败
- **THEN** 可恢复事务记录保留，next 阻塞到恢复完成，不能把部分重置当作成功

### Requirement: 恢复边不破坏执行 DAG
失败路由 SHALL 作为有次数限制的恢复规则存储，不作为反向依赖边加入 Node DAG。max_retries SHALL 按 Gate 规范身份计数，不能因重组或删除当前 FAIL 文件自动清零。

#### Scenario: 连续 QA 失败
- **WHEN** 同一 qa/test 经多轮返工达到上限
- **THEN** 系统停止并返回历史与人工处理指引

### Requirement: 两步 Gate 证据记录
代码 Gate SHALL 先通过 gate begin 固定审查输入和轮次，再通过 gate record 提交报告。PASS SHALL 要求当前输入、规则、Plan、Gate 和轮次与 begin 匹配。证据字段 SHALL 由 LoopSpec 生成，报告不能自报摘要。测试覆盖 SHALL 需要测试 Gate，不以普通产物代替 PASS。
begin/record SHALL 检查 Gate 就绪状态，令牌 SHALL 单次有效。代码 Gate SHALL 仅在报告和系统证据同时有效时完成；失效时 SHALL 重新就绪并阻塞下游，而非因旧 PASS 文件存在而无法重审。

#### Scenario: 审查期间修改代码
- **WHEN** begin 后、record PASS 前审查范围变化
- **THEN** PASS 被拒绝，要求重新获取并审查输入

#### Scenario: 复用旧轮次令牌
- **WHEN** Gate 已被 rollback 而 Agent 提交前一轮令牌
- **THEN** 记录失败，旧令牌不得生成新 PASS

### Requirement: Diff 固定基线与完整清单
代码 Plan SHALL 记录固定 Git 基线。校验 SHALL 覆盖基线到当前工作树的跟踪/未跟踪、暂存/未暂存、新增/删除、重命名及文件类型/模式变化。Index 与工作树不同且交付 Index 时 SHALL 验证单独的 Index 摘要。并发扫描变化、超限、不可解码路径和不支持类型 SHALL 明确失败。

#### Scenario: 暂存与工作树不同
- **WHEN** 暂存内容为版本 A，而工作树已改为版本 B
- **THEN** 工作树 B 的证据不能批准提交 Index A

#### Scenario: 删除及重命名
- **WHEN** 后端文件被删除，或移动到新目录
- **THEN** 删除旧路径与新增路径都参与规则覆盖和证据摘要

#### Scenario: 忽略文件
- **WHEN** 存在没有被固化生成目录分类覆盖的忽略文件
- **THEN** 系统报告未覆盖并阻塞，不因 .gitignore 自动忽略风险

### Requirement: Git 输入安全
Git SHALL 使用无 Shell 的参数调用且禁止外部 Diff 驱动、textconv 和工作区代码执行。输出 SHALL 使用 NUL 安全处理。读取 SHALL 不跟随仓库外符号链接，证据清单 SHALL 不输出源代码或 Secret 值。

#### Scenario: 恶意路径和配置
- **WHEN** 文件名包含换行/命令字符或 Git 配置声明外部驱动
- **THEN** 路径只作为数据处理，驱动不执行，越界目标不读取

### Requirement: 全量 Diff 的审查能力覆盖
Assurance SHALL 按每个实际路径合并所有命中规则的能力要求，并验证具体 Gate 实例对该范围具有当前 PASS。证据 SHALL 绑定 Plan、基线、规则、匹配路径集合、状态与内容摘要。未知路径、缺失 Gate、过期证据和读取错误 SHALL 默认失败。

#### Scenario: FE 修复触及 BE
- **WHEN** QA 路由选择 FE，但实际 Diff 包含后端改动
- **THEN** Assurance 要求 BE 的测试、安全审查和 PR Review，FE 的 PASS 不能代替

#### Scenario: 轻量 Plan 没有 BE
- **WHEN** 未绑定的 BE 审查能力在实际 Diff 中被命中
- **THEN** 系统输出 missing_fragments，要求安全扩张而不是静默放行

#### Scenario: 安全审查后修改代码
- **WHEN** PR Review 修复改变后端代码而旧安全 PASS 未重录
- **THEN** Assurance 输出 stale_evidence 并要求重审

### Requirement: 保障结果由确定性校验产生
Assurance SHALL 使用系统验证命令生成结论，不能用手写 pass.md 代替。最终保障 SHALL 依赖所有交付分支；next、完成判断和归档 SHALL 复核当前全量摘要。LoopSpec SHALL 明确本地证据检查的边界，不宣称阻止所有外部提交。

#### Scenario: 伪造保障文件
- **WHEN** Agent 只写入 assurance/pass.md 但没有有效系统校验记录
- **THEN** 保障 Node 仍未完成

### Requirement: 管理产物避免自引用且不能掩盖源代码
Plan SHALL 固化精确控制目录并验证完整性，以便报告和证据写入不改变自身业务 Diff。控制目录 SHALL 不接受任意 exclude Glob 或包含业务源代码。Profile、Fragment、规则源和可执行配置的变更 SHALL 仍按项目规则审查。

#### Scenario: 写入 PASS 证据
- **WHEN** LoopSpec 在已声明证据目录写入保障结果
- **THEN** 业务 Diff 摘要保持相同，结果不会立即自失效

#### Scenario: 隐藏代码目录
- **WHEN** 请求把 backend 或整个工作流 Home 配置为无需审查的控制目录
- **THEN** 系统拒绝不安全排除

### Requirement: 修订与安全扩张
普通重组 SHALL 冻结当前及具有执行/Attempts 证据的 Node。安全扩张 SHALL 只添加系统诊断要求的 Fragment，保留旧节点定义和基线，并显式使新增依赖影响的 QA/Assurance 失效。激活与失效归档 SHALL 在受锁保护的可恢复事务中完成；新 Plan 摘要 SHALL 使旧代码 Gate 证据不可直接继承。

#### Scenario: 扩张到 BE
- **WHEN** FE Plan 的 Assurance 要求新增 BE 流程
- **THEN** 新 Plan 增加 BE，在重新 QA 和 Assurance 前完成必要 Gate，并保存旧修订版

#### Scenario: 扩张事务失败
- **WHEN** 已写新计划但失效归档失败
- **THEN** 系统保持旧绑定或阻塞待恢复，不能暴露新图和旧完成证据的混合状态
