## MODIFIED Requirements

### Requirement: Flow 级失败返工
Profile 与 Plan 的 flow 条目 SHALL 可声明 on_fail，reset SHALL 只列出同一 flow 中执行上位于该实例之前的实例。编译时 flow 条目与引用节点上的 on_fail SHALL 下放到其范围内的每个 Gate，reset SHALL 展开为叶子节点；失败时 SHALL 重置 reset 中的全部节点、失败 Gate 及其全部下游，SHALL NOT 由失败报告选择目标。失败报告 SHALL NOT 包含 route_case。

#### Scenario: QA 失败重置前后端
- **WHEN** qa 的 flow 条目声明 on_fail.reset: [be, fe]，qa/test 记录有效 FAIL
- **THEN** qa/test 的 gate.on_fail.reset 包含 be 与 fe 的全部叶子，plan rollback 重置它们以及 qa、assurance

#### Scenario: 非法目标
- **WHEN** flow on_fail.reset 指向下游或不存在的实例
- **THEN** 编译以结构化错误拒绝

### Requirement: 返工重置闭包与历史
`plan rollback -c <change> -p <NNN>` SHALL 只作用于活动 Plan，只按失败 Gate 自身的 gate.on_fail 执行，重置其 reset 节点、该 Gate 与全部下游，把这些节点的产物、报告与 Gate 证据归档到 Plan 目录的 `.attempts/<序号>/`，record.yaml 记为 kind: rollback。无依赖的并行分支 SHALL 保留。归档 SHALL 不还原业务代码。修订确认时被重新执行节点的归档 SHALL 使用同一目录与编号，记为 kind: revision。两类记录 SHALL 作为重跑节点 node instructions 的 priorAttempts，并标注为不可信数据。

#### Scenario: 并行分支保留
- **WHEN** fe 和 be 为并行分支，qa 依赖二者，qa 的 on_fail.reset 只列出 be
- **THEN** be、qa 和 assurance 重置，fe 产物保留

#### Scenario: 指定的不是活动 Plan
- **WHEN** 对已归档的 Plan 001 执行 plan rollback -p 001
- **THEN** 返回 plan_not_active，不修改任何文件

### Requirement: 恢复边不破坏执行 DAG
on_fail SHALL 作为 Gate 上有次数限制的返工规则存储，不作为反向依赖边加入 Node DAG。每个 Gate SHALL 最多一条 on_fail。返工次数 SHALL 按 Plan 隔离，并按 Gate ID 统计 kind: rollback 的记录；达到 max_retries 时该 Gate 为 exhausted 并停止自动推进；Gate 没有 on_fail 时有效 FAIL 直接为 exhausted。修订 SHALL NOT 清零次数，有返工记录的 Gate SHALL NOT 在修订中改名或删除。

#### Scenario: 连续 QA 失败
- **WHEN** 同一 qa/test 经多轮返工达到上限
- **THEN** 系统停止并返回历史与人工处理指引

#### Scenario: 修订不清零
- **WHEN** be/tests/check 已返工 2 次后确认一次修订
- **THEN** 新修订中 be/tests/check 仍计为 2 次

### Requirement: 两步 Gate 证据记录
带 evidence 的代码 Gate SHALL 先通过 `gate begin -c <change> -n <gate>` 固定审查输入（范围内改动的摘要）与一次性轮次，再通过 `gate record -c <change> -n <gate> --round <roundId> --report <报告文件>` 提交报告。PASS SHALL 要求当前输入、Plan 摘要、Gate 与轮次与 begin 匹配。证据字段 SHALL 由系统生成，报告头部 SHALL 只接受 verdict 与 summary。begin/record SHALL 检查 Gate 就绪状态，轮次 SHALL 单次有效。代码 Gate SHALL 仅在报告和系统证据同时有效时完成；失效时 SHALL 重新就绪并阻塞下游。

#### Scenario: 审查期间修改代码
- **WHEN** begin 后、record PASS 前审查范围变化
- **THEN** PASS 被拒绝，要求重新 begin

#### Scenario: 复用旧轮次
- **WHEN** Gate 已开始新一轮而 Agent 提交前一轮的 roundId
- **THEN** 记录失败，旧轮次不得生成新 PASS

### Requirement: Diff 固定基线与完整清单
Change SHALL 记录固定 Git 基线与仓库身份，所有 Plan SHALL 使用它。校验 SHALL 覆盖基线到当前工作树的跟踪/未跟踪、暂存/未暂存、新增/删除、重命名及文件类型/模式变化。Index 与工作树不同且交付 Index 时 SHALL 验证单独的 Index 摘要。并发扫描变化、超限、不可解码路径和不支持类型 SHALL 明确失败。

#### Scenario: 暂存与工作树不同
- **WHEN** 暂存内容为版本 A，而工作树已改为版本 B
- **THEN** 工作树 B 的证据不能批准提交 Index A

#### Scenario: 删除及重命名
- **WHEN** 后端文件被删除，或移动到新目录
- **THEN** 删除旧路径与新增路径都参与规则覆盖和证据摘要

#### Scenario: 忽略文件
- **WHEN** 存在没有被工具生成目录分类覆盖的忽略文件
- **THEN** 系统报告未覆盖并阻塞，不因 .gitignore 自动忽略风险

### Requirement: 全量 Diff 的审查能力覆盖
保障节点 SHALL 按每个实际路径合并所有命中规则的能力要求，并验证活动 Plan 中具体 Gate 实例对该范围具有当前 PASS。证据 SHALL 绑定 Plan 摘要、Change 基线、规则、匹配路径集合、状态与内容摘要。旧 Plan 的证据 SHALL NOT 被接受。未知路径、缺失 Gate、过期证据和读取错误 SHALL 默认失败，并给出建议 Fragment。

#### Scenario: FE 修复触及 BE
- **WHEN** QA 的 on_fail 只重置 FE，但实际 Diff 包含后端改动
- **THEN** 保障要求 BE 的测试、安全审查和 PR Review，FE 的 PASS 不能代替

#### Scenario: 轻量 Plan 没有 BE
- **WHEN** 未在活动 Plan 中提供的 BE 审查能力被实际 Diff 命中
- **THEN** 保障输出 missing_fragments，提示通过修订加入 backend-implementation

#### Scenario: 重新规划后的旧证据
- **WHEN** Plan 001 中 be 的审查已 PASS，Plan 001 归档后 Plan 002 尚未审查同一后端改动
- **THEN** Plan 002 的保障要求重新取得后端证据

### Requirement: 保障结果由确定性校验产生
保障节点 SHALL 通过 `gate record -c <change> -n <保障节点>` 执行，不需要 gate begin 与报告文件；系统 SHALL 执行确定性检查并写出系统 PASS 或 FAIL，手写 pass.md SHALL 不构成通过。change status、完成判断与 change archive SHALL 复核当前全量摘要。LoopSpec SHALL 明确本地证据检查的边界，不宣称阻止所有外部提交。

#### Scenario: 伪造保障文件
- **WHEN** Agent 只写入 assurance/check 的 pass.md 但没有系统检查记录
- **THEN** 保障节点仍未完成

### Requirement: 管理产物避免自引用且不能掩盖源代码
系统 SHALL 把 Change 根下的 `.workflow.yaml`、`state.md` 与整个 `plans/` 视为控制目录并从业务 Diff 中排除，另加 config.yaml 声明的工具生成目录；SHALL NOT 接受任意 exclude Glob 或排除业务源代码。Profile、Fragment、规则源和可执行配置的变更 SHALL 仍按项目规则审查。

#### Scenario: 写入证据与状态
- **WHEN** LoopSpec 写入 plan.yaml、Gate 证据或重做记录
- **THEN** 业务 Diff 摘要保持相同，结果不会立即自失效

#### Scenario: 隐藏代码目录
- **WHEN** config.yaml 把 backend 声明为工具生成目录
- **THEN** 系统拒绝不安全排除

### Requirement: 修订与安全扩张
同一 Plan 内的修订 SHALL 冻结已完成、当前就绪、失败过或有重做记录的节点：冻结节点 SHALL NOT 删除、改名或改变执行定义，其 requires SHALL 只能增加；requires 增加的冻结节点及其全部下游 SHALL 在确认时归档并重新执行。存在有效 FAIL 的 Gate 时，修订 SHALL 使这些 Gate 落在重新执行范围内，否则拒绝。修订 SHALL 保持 Change 基线与项目最低约束；修订确认后旧代码 Gate 证据 SHALL 因摘要变化不可继承。

#### Scenario: 保障要求补后端
- **WHEN** FE Plan 的保障报告缺少后端能力，修订加入 be 并让 assurance 依赖它
- **THEN** 确认后 be 新增执行，assurance 重新执行，已完成的 FE 节点保留

#### Scenario: 用修订绕过失败
- **WHEN** qa/test 有效 FAIL，修订没有让 qa/test 重新执行
- **THEN** 确认被拒绝，提示先返工或让失败 Gate 进入重新执行范围

#### Scenario: 改写已完成节点
- **WHEN** 修订改变已完成 be/code/implement 的指令路径
- **THEN** 返回 node_frozen，并提示任务变化时归档后重新规划

## REMOVED Requirements

### Requirement: 嵌套失败按最近处理者唯一恢复
**Reason**: on_fail 回到原 Schema 语义，每个 Gate 最多一条，不再有叶子、引用节点、flow 由内向外逐层接手的处理链与引用节点共享次数。
**Migration**: 在 Fragment 或 flow 中保留一处 on_fail 声明；编译时若同一 Gate 收到多条将报 on_fail_conflict，需由作者删除重叠声明。
