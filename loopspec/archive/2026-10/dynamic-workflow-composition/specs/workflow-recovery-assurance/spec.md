> **已被 `plan-replacement` 部分取代（2.0.0）。** 下列内容以 `loopspec/changes/plan-replacement/design.md` 为准：
> - D1.2 由内向外的恢复处理链 → 编译时把 `on_fail` 下放到每个 Gate，每个 Gate 最多一条，重叠报 `on_fail_conflict`；次数按 Gate 统计（plan-replacement D4、D11 B4）。
> - D4 Profile `protected` 与请求 `deviations` → 删除；项目最低要求只由 `config.yaml` 的 `required_fragments` 与保障规则保证（D11 A1）。
> - D5 请求中的 `reasons` 与 `baseline` → 删除；基线在 Change 级 `.workflow.yaml` 固定（D3）。
> - D6 自包含快照、资源字节固化与原子激活 → 每份 Plan 一个 `plan.yaml`（`meta` + `spec`，摘要校验），指令、模板与保障规则执行时实时读取（D4）。
> - D10 每份 Plan 的基线 → Change 级基线；Diff 控制目录排除改为 Change 根下 `.workflow.yaml`、`state.md` 与 `plans/`（D3、D7）。
> - D11 修订快照、修订事务与安全扩张 → `plan validate -f` 预览、`plan approve -f --digest` 确认，冻结节点只能增加 `requires`；中断后重新执行同一命令收敛，删除 `recover`（D5、D8）。
> - V1/V2 能力版本（`min_engine_version`、`manual-v1`、`delivery-review`）、`assurance check` 命令与平铺/复数命令 → 删除；命令树改为 `loopspec <资源> <动作>`，保障节点用 `gate record` 执行（D11、D12）。

## ADDED Requirements

### Requirement: Flow 级失败返工
Profile 与 Plan 的 flow 条目 SHALL 可声明 on_fail，语法与 Fragment 内引用节点相同。reset SHALL 只列出同一 flow 中执行上位于该实例之前的实例；失败时 SHALL 重置列出的全部实例的成员、失败来源及传递下游，SHALL NOT 由失败报告选择或缩小目标。Profile 与 Plan 请求 SHALL NOT 包含 recovery 或 cases；失败报告 SHALL NOT 包含 route_case。Node 与引用节点 on_fail 的失败来源 SHALL 为系统从成员树追踪的有效内部 Gate FAIL。非法目标 SHALL 编译拒绝；恢复链全部耗尽 SHALL 停止自动推进。

#### Scenario: QA 失败重置前后端
- **WHEN** qa 的 flow 条目声明 on_fail.reset: [be, fe]，qa/test 记录有效 FAIL
- **THEN** 系统重置 be 与 fe 的全部实现、测试、Security Review、PR Review Node 以及 qa、assurance，全部重跑后再回到 QA

#### Scenario: 只含一侧的 bugfix
- **WHEN** bugfix Plan 只有 be，qa 的 on_fail.reset 为 [be]
- **THEN** QA 失败只重置 be、qa 与 assurance

#### Scenario: 非法目标或旧路由字段
- **WHEN** flow on_fail.reset 指向下游或不存在的实例，或 Profile 声明 recovery，或失败报告包含 route_case
- **THEN** 编译或报告解析以结构化错误拒绝，不修改执行产物

### Requirement: 返工重置闭包与历史
返工 SHALL 重置目标、失败 Gate、被选中引用边界全部成员和传递下游，包括 Gate 与 Assurance 证据。直接目标 SHALL 对应叶子 Node；引用目标和 flow 实例目标 SHALL 对应全部成员。无依赖的并行分支 SHALL 保留。归档 SHALL 不还原业务代码，SHALL 记录来源 Gate、失败轮次、处理者、传播层级与重置闭包，并将失败信息提供给下轮 instructions。

#### Scenario: BE 分支返工
- **WHEN** fe 和 be 为并行分支，qa 依赖二者，qa 的 on_fail.reset 只列出 be
- **THEN** be、qa 和 assurance 重置，独立 fe 产物保留

#### Scenario: 中断归档
- **WHEN** 返工归档中途失败
- **THEN** 可恢复事务记录保留，next 阻塞到恢复完成，不能把部分重置当作成功

### Requirement: 恢复边不破坏执行 DAG
on_fail SHALL 作为有次数限制的恢复规则存储，不作为反向依赖边加入 Node DAG。max_retries SHALL 绑定规范处理者/规则身份及对应 Gate 历史，引用节点共享预算 SHALL 覆盖其全部内部失败。内层计数 SHALL 不因父级重置、重组或删除当前 FAIL 文件清零。修订 SHALL 保留既有身份历史映射，或拒绝试图重命名已有处理者以清零预算的请求。

#### Scenario: 连续 QA 失败
- **WHEN** 同一 qa/test 经多轮返工达到上限
- **THEN** 系统停止并返回历史与人工处理指引

### Requirement: 嵌套失败按最近处理者唯一恢复
系统 SHALL 优先选择失败叶子的 on_fail，再沿引用归属从内向外选择尚有预算的引用节点 on_fail，最后考虑所属 flow 实例的 on_fail。没有规则或局部预算耗尽 SHALL 允许传播，不得直接绕过内部规则。损坏结果、非法路径及事务错误 SHALL 阻塞而非兜底传播。一次有效失败 SHALL 绑定唯一处理者和事务；恢复中 SHALL 不同时执行外层动作。多分支失败 SHALL 稳定排序、串行处理后重算。恢复 SHALL 不免除任何必要 Gate。

#### Scenario: 内部恢复优先
- **WHEN** security/check 和其外层 security 引用节点都有合法恢复规则，内层尚有预算
- **THEN** 仅执行 security/check 的规则，外层不得同时重置 implement

#### Scenario: 内部耗尽向外传播
- **WHEN** 内层规则耗尽但 security 引用节点还有恢复预算
- **THEN** 同一失败选择外层规则，重跑 implement 和引用成员，内层已消耗计数保持不变，最终仍需有效 Gate PASS

#### Scenario: 没有内部规则
- **WHEN** security-review 内部 Gate 没有 on_fail，而引用节点有 on_fail.reset: [implement]
- **THEN** 当前有效 FAIL 直接传播到引用节点并启动固定恢复，不要求来源 Fragment 额外提供成败接口

#### Scenario: 所有层级耗尽
- **WHEN** 有效 FAIL 的全部内部、引用及 flow 处理者都已无预算
- **THEN** 最终状态为 exhausted，不自动清零、跳过 Gate 或切换规则重试

#### Scenario: 重复执行与并行失败
- **WHEN** 同一 FAIL 被重复读取，或多个内部 Gate 同时失败
- **THEN** 事务幂等地处理选定失败且只消耗一次预算，其他有效失败在状态重算后按稳定顺序处理

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
- **WHEN** QA 的 on_fail 只重置 FE，但实际 Diff 包含后端改动
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
