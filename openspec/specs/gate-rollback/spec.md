# gate-rollback Specification

## Purpose
TBD - created by archiving change gated-artifact-workflow. Update Purpose after archive.
## Requirements
### Requirement: 回退闭包计算
系统 SHALL 在触发回退时计算 reset closure：种子集合为 `on_fail.reset` 声明的起点节点 ID 集合 ∪ 该 gate 自身；闭包为该种子集合的全部传递后继（含种子本身），按拓扑序返回，保证归档执行顺序稳定。gate 自身 SHALL 必须在闭包内。

#### Scenario: 闭包包含 gate 自身
- **WHEN** 计算某 gate 的回退闭包
- **THEN** 闭包集合中包含该 gate 节点自身的 ID

#### Scenario: reset 起点的下游节点被自动纳入闭包
- **WHEN** `on_fail.reset: [design]`，且 `tasks` 依赖 `design`，`security`（gate）依赖 `tasks`
- **THEN** 闭包为 `[design, tasks, security]`，即使用户只声明了 `design`

#### Scenario: 闭包按拓扑序返回
- **WHEN** 闭包包含多个节点
- **THEN** 返回列表的顺序与整体 schema 的拓扑排序顺序一致

### Requirement: 回退执行——归档而非删除
系统 SHALL 在执行回退时，把 reset closure 内每个节点当前存在的产物文件**移动**（而非删除）到 `<change_dir>/.attempts/round-NNN/`，保留其相对 change 目录的路径结构；round 编号 SHALL 从 1 开始递增，不复用已存在的编号（`mkdir(exist_ok=False)` 防止并发/重复覆盖）。归档完成后 SHALL 清理因文件移出而产生的空目录（`.attempts/` 目录自身除外）。`state.md` 与 `.workflow.yaml` SHALL 不被回退归档，始终保留在 change 根目录。

#### Scenario: 执行回退后原路径文件消失
- **WHEN** 对一个 `failed` 状态的 gate 执行回退
- **THEN** reset closure 内每个节点的原产物路径不再存在文件

#### Scenario: 执行回退后文件出现在归档目录
- **WHEN** 回退执行完成
- **THEN** 被归档的文件出现在 `.attempts/round-NNN/` 下，且保留原有的相对路径结构（如 `security/fail.md` → `round-001/security/fail.md`）

#### Scenario: 连续两次回退生成递增的 round 目录
- **WHEN** 对同一 change 连续执行两次回退
- **THEN** 依次生成 `round-001/`、`round-002/` 目录，编号不重复

#### Scenario: 回退清理空目录
- **WHEN** 某节点的产物位于一个专属子目录（如 `security/fail.md`），归档后该子目录内已无文件
- **THEN** 该空子目录被清理，但 `.attempts/` 目录本身保留

#### Scenario: 回退不归档 state.md
- **WHEN** 执行回退
- **THEN** `state.md` 保留在 change 根目录，不出现在归档目录中

### Requirement: 回退后的元数据记录
每次回退 SHALL 在对应 round 目录下写入 `_meta.yaml`，内容 SHALL 包含 `round`、`gate`、`verdict`、`summary`、`blocking_issues`、`reset_declared`（用户在 schema 中声明的起点）、`reset_closure`（实际计算出的闭包）、`archived_files`（相对路径列表）与 `archived_at`（ISO 8601 时间戳）。`_meta.yaml` SHALL 作为归档操作的最后一步写入，确保中途失败的 round 因缺少该文件而不计入回退次数统计。

#### Scenario: _meta.yaml 内容完整
- **WHEN** 一次回退执行成功
- **THEN** 对应 round 目录下的 `_meta.yaml` 包含 gate、verdict、reset_closure、archived_files 等全部必填字段

### Requirement: 回退后状态自动翻转
系统 SHALL 不为回退后的状态翻转编写任何专门逻辑：回退归档完成后再次调用状态推导算法（同 `artifact-state` 能力），原本"产物存在性 + requires 判定"的通用算法 SHALL 自动把闭包内节点重新判定为 `ready`/`blocked`。

#### Scenario: 回退后重新推导状态
- **WHEN** 对一个 `failed` 的 gate 执行回退，闭包为 `[design, tasks, security]`
- **THEN** 再次查询状态时，`design` 变为 `ready`（其依赖仍完整），`tasks` 与 `security` 变为 `blocked`

### Requirement: 回退前置条件校验
系统 SHALL 在执行回退前校验：当前必须存在处于 `failed` 状态的 gate，否则报 `no_failed_gate` 且不产生任何文件变更；若目标 gate 的回退次数已达 `max_retries`（状态为 `exhausted`），SHALL 拒绝执行并报 `retries_exhausted`。

#### Scenario: 无失败 gate 时执行回退
- **WHEN** 当前 change 中没有任何 `failed` 状态的 gate
- **THEN** 系统报 `no_failed_gate`，不产生任何文件系统变更

#### Scenario: 重试耗尽时执行回退
- **WHEN** 目标 gate 已处于 `exhausted` 状态
- **THEN** 系统拒绝执行回退，报 `retries_exhausted`

### Requirement: 多 gate 场景下的独立回退
当 schema 含多个 gate 时，系统 SHALL 保证回退某一个 `failed` gate 只归档该 gate 自身的 reset closure，不影响其他与之无依赖关系的 gate 及其上下游节点。

#### Scenario: 回退一个 gate 不影响无关 gate
- **WHEN** schema 中存在两个互不依赖的 gate，其中一个处于 `failed` 状态
- **THEN** 对该 gate 执行回退后，另一个 gate 及其相关节点的产物与状态不受影响

### Requirement: priorAttempts 构造
系统 SHALL 为每个节点构造 `priorAttempts` 数组：扫描 `.attempts/round-*/_meta.yaml`，筛选出 `archived_files` 中包含该节点当前产物路径的轮次，按 `round` 升序排列；每项 SHALL 包含 `round`、`gate`、`verdict`、`summary`、`blockingIssues`、`archivedPath`（归档后文件的绝对路径，指向实际可读的文件）。

#### Scenario: 首次生成节点没有历史
- **WHEN** 一个节点从未被回退过
- **THEN** 其 `priorAttempts` 为空数组

#### Scenario: 回退后重新生成节点带有历史
- **WHEN** 某节点在 round 1 被回退归档过
- **THEN** 其 `priorAttempts` 包含一条记录，含 round 1 的 verdict、summary、blockingIssues 与可读的 archivedPath

#### Scenario: 两次回退后历史按顺序排列
- **WHEN** 某节点先后在 round 1 和 round 2 被回退归档
- **THEN** 其 `priorAttempts` 包含两条记录，按 round 升序排列（round 1 在前，round 2 在后）

