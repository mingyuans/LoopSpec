## ADDED Requirements

### Requirement: Change 级状态
Change SHALL 在 `.workflow.yaml` 中使用 format_version 4，只记录 change_name、created、baseline 与 repository，SHALL NOT 保存任何 Plan 指针。未结束 Plan 与活动 Plan SHALL 由各 plan.yaml 的 meta.status 推导；Change 状态 SHALL 推导为 unplanned（无 draft 或 approved Plan）、planning（有 draft Plan）、active（有 approved Plan 且未完成）或 complete（approved Plan 全部节点完成），SHALL NOT 另行持久化，SHALL NOT 存在表示命令执行一半的状态。format_version 3 或含 schema 字段的 Change SHALL 返回 unsupported_format 并提示重建或使用 v1.x 处理。

#### Scenario: 新建 Change
- **WHEN** 执行 loopspec change new AFD1111
- **THEN** .workflow.yaml 为 format_version 4，baseline 与 repository 为空且没有 Plan 指针，change status 返回 unplanned

#### Scenario: 旧格式 Change
- **WHEN** 读取 format_version 3 或旧 Schema 创建的 Change
- **THEN** 返回 unsupported_format 与处理指引，不尝试执行

### Requirement: 固定基线属于 Change
第一次 `plan create` 时系统 SHALL 把当前完整 Commit 哈希与仓库根目录身份写入 Change 级 baseline 与 repository，之后 SHALL NOT 改变。所有 Plan SHALL 使用 Change 级基线计算 Diff 与证据，`spec` SHALL NOT 记录或覆盖基线。执行时当前仓库与 repository 不一致 SHALL 拒绝。

#### Scenario: 重新规划不换基线
- **WHEN** Plan 001 归档后仓库 HEAD 已前进，再 plan create 建立 Plan 002
- **THEN** Plan 002 使用 Change 首次固定的基线，旧 Plan 期间的改动仍在 Diff 中

### Requirement: 一份 Plan 一个 plan.yaml
每份 Plan SHALL 是 `plans/<NNN>/plan.yaml`，编号 SHALL 为已有 plan.yaml 的最大编号加 1。文件 SHALL 只有 meta 与 spec 两段：meta 记录 plan、status（draft、approved、archived）、revision、digest、approved_at、note、created、archived_at、archive_note；spec 只含 based_on、flow 与 nodes，Gate 的 on_fail 位于 nodes 的 gate 内。status SHALL 只记录人的决定，完成状态 SHALL 由 change status 实时推导。每份 Plan 目录 SHALL 另有人可读的 state.md，引擎 SHALL NOT 读取它推导状态。

#### Scenario: 完成后代码又被修改
- **WHEN** approved Plan 的全部节点完成后代码又被修改
- **THEN** plan.yaml 不变，change status 推导为 active 并给出需要重新执行的节点

### Requirement: plan.yaml 完整性
系统 SHALL 在每次加载 plan.yaml 时重新计算 spec 的规范摘要，并 SHALL 要求其等于 meta.digest；不一致 SHALL 返回 plan_integrity 并拒绝执行与确认。对 plan.yaml 的所有修改 SHALL 是整文件原子替换。

#### Scenario: 手改执行图
- **WHEN** 有人直接修改 approved Plan 的 spec.nodes
- **THEN** change status、node instructions、gate 与 plan rollback 均返回 plan_integrity

### Requirement: 最多一个未结束 Plan
同一 Change SHALL 最多存在一个 draft 或 approved Plan，status 为 approved 的 Plan 即活动 Plan；发现多于一个 SHALL 返回 history_integrity。新建 Plan SHALL 只在没有 draft 或 approved Plan 时进行。

#### Scenario: 有活动 Plan 时新建
- **WHEN** Plan 001 为 approved 时执行 plan create -c AFD1111 -f other.yaml
- **THEN** 返回错误并提示修订使用 plan validate 与 plan approve -f、重新规划先 plan archive，不创建 Plan 002

### Requirement: 初次规划与草稿 Plan
`plan validate -c <change> -f <请求文件>` SHALL 只读编译请求并返回编译结果与约束检查，SHALL NOT 写任何文件。`plan create -c <change> -f <请求文件> [--note]` SHALL 编译请求并按当前 config.yaml 检查项目最低约束：无未结束 Plan 时 SHALL 创建 status 为 draft 的新 Plan 并写入 meta.note；已有 draft Plan 时 SHALL 覆盖其 spec；已有 approved Plan 时 SHALL 拒绝。`plan show -c <change> [-p <NNN>]` SHALL 展示 meta、spec、digest 与固定基线。`plan approve -c <change> -p <NNN> --digest <摘要>` SHALL 在摘要一致时以一次写入把 draft Plan 置为 approved（revision 1、approved_at），使其成为活动 Plan；摘要不一致 SHALL 返回 plan_changed。

#### Scenario: 调整后确认
- **WHEN** 人看过草稿要求调整，LLM 再次 plan create，人确认新的摘要
- **THEN** approve 使用新摘要成功，旧摘要的 approve 返回 plan_changed

### Requirement: 归档 Plan 与重新规划
`plan archive -c <change> -p <NNN> [--note]` SHALL 适用于 draft 或 approved Plan，SHALL 以一次写入把 status 置为 archived 并记录 archived_at 与 archive_note。归档 SHALL NOT 移动、删除或修改该 Plan 目录内的产物、证据与重做记录，SHALL NOT 触及业务代码。之后 SHALL 可按初次规划流程建立新 Plan；新 Plan SHALL 从空的 Plan 目录开始推导状态，SHALL NOT 继承旧 Plan 的产物、Gate 结论或返工次数。

#### Scenario: 任务变化后重新规划
- **WHEN** Plan 001 已完成 be/code/implement，人同意归档后建立并确认 Plan 002，其中也有 be/code/implement
- **THEN** Plan 002 的 be/code/implement 为 ready，Plan 001 目录原样保留，业务代码不变

#### Scenario: 放弃草稿
- **WHEN** 人决定不采用 draft Plan 002，执行 plan archive -p 002
- **THEN** Plan 002 为 archived，Change 回到 unplanned，下一次 plan create 建立 Plan 003

### Requirement: 单一生效写入，中断后状态只有之前或之后
每条命令 SHALL 只有一次决定状态的原子写入（生效点）：plan create 为写入 plan.yaml（首次时之前先固定基线）；plan approve 与 plan archive 为改写 plan.yaml；plan rollback 为写入 `.attempts/<序号>/record.yaml`（含重置节点、文件清单与摘要），之后再归档文件且失败报告最后；修订确认先写 revision 记录，再整文件替换 plan.yaml 作为生效点，之后再归档文件。生效点之前的写入 SHALL NOT 影响状态推导，重新执行时 SHALL 被覆盖或复用；revision 记录在 plan.yaml 达到其目标修订号之前 SHALL 视为不存在。已生效记录中尚未搬走的源文件在推导状态时 SHALL 视为不存在；node instructions、gate、plan rollback、plan approve、plan archive 与 change archive SHALL 在写锁内先按记录摘要补完这些文件，SHALL NOT 新建重复记录或重复计次。系统 SHALL NOT 提供中断状态、事务文件或 recover 命令。所有写入 SHALL 在逐 Change 写锁内进行。

#### Scenario: 创建草稿中断
- **WHEN** plan create 在写入 plan.yaml 之前中断
- **THEN** change status 仍为 unplanned 并给出 plan create；重新执行后得到与一次完成相同的 Plan 001

#### Scenario: 返工中断
- **WHEN** plan rollback 已写 record.yaml 并归档部分文件后中断
- **THEN** change status 显示重置节点为待执行、失败 Gate 不再为 failed；下一条 node instructions 先按记录补完归档，记录只有一条，该 Gate 的返工次数只增加一次

#### Scenario: 修订中断
- **WHEN** plan approve -f 已写 revision 记录但尚未替换 plan.yaml 时中断
- **THEN** 旧 spec 照常执行，该记录不出现在历史中；以同一请求与摘要重新确认时复用记录并完成修订

#### Scenario: 归档文件不符
- **WHEN** 补完归档时发现待归档文件或已归档文件的内容与记录摘要不符
- **THEN** 返回 history_integrity，不覆盖、不移动
