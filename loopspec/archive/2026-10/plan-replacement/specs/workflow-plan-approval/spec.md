## MODIFIED Requirements

### Requirement: Change 先于 Plan 创建
`change new` SHALL 创建 format_version 4 的 Change 与空 plans 目录，SHALL NOT 选模板、编译或激活 Plan。没有未结束 Plan 时 change status SHALL 返回 unplanned、isComplete 为 false 与规划指引。

#### Scenario: 新需求尚未规划
- **WHEN** 用户执行 loopspec change new AFD1111
- **THEN** Change 存在但没有 Plan，change status 返回 unplanned、isComplete 为 false 和规划指引

#### Scenario: 新建元数据写入失败
- **WHEN** change new 写入元数据失败
- **THEN** 不产生可被解释为可执行的部分 Change

### Requirement: 所有新计划明确确认
初次规划与重新规划产生的 draft Plan、以及同一 Plan 内的修订，SHALL 都在人明确确认后才生效。plan approve SHALL 要求 --digest 与当前编译结果摘要一致，确认 SHALL 只写入 meta.digest 与 meta.approved_at，SHALL NOT 接受审批 YAML 文件或确认说明；本地记录 SHALL NOT 声称认证了人的身份。

#### Scenario: 完整模板仍需确认
- **WHEN** plan create 直接采用完整 Profile
- **THEN** Plan 为 draft，只有 plan approve 后才允许执行

#### Scenario: 确认期间草稿被替换
- **WHEN** plan approve 提交先前展示的摘要，但 draft Plan 的 spec 已被再次 plan create 覆盖
- **THEN** 返回 plan_changed，Plan 保持 draft

#### Scenario: 同一确认重复提交
- **WHEN** 已 approved 的 Plan 再次以相同摘要执行不带 -f 的 plan approve
- **THEN** 返回已确认结果，不改变 revision、产物或返工次数

### Requirement: 未批准草稿不能成为执行输入
draft Plan SHALL NOT 被执行：node instructions、gate 与 plan rollback SHALL 返回 plan_not_active，并在 nextSteps 中给出 plan show 与确认指引。存在 approved Plan 时，执行 SHALL 只按其当前 spec；修订请求在确认前 SHALL NOT 影响执行。

#### Scenario: 草稿有手写 PASS
- **WHEN** draft Plan 的 artifacts 中已有产物或 PASS
- **THEN** 执行类命令返回 plan_not_active，change status 不显示完成

#### Scenario: 修订请求待确认
- **WHEN** approved Plan 的修订请求已由 plan validate -f 预览
- **THEN** 执行仍按原 spec，change status 不显示修订

### Requirement: 确认复核固定约束
确认 SHALL 持逐 Change 写锁，重新编译请求并检查摘要、项目最低约束（按当前 config.yaml）、Change 级基线与仓库身份；修订确认还 SHALL 检查 base_revision 与冻结规则。约束不满足 SHALL 拒绝且不改变任何状态。

#### Scenario: 项目最低约束变化
- **WHEN** 草稿展示后 config.yaml 新增了 Plan 缺少的 required_fragments
- **THEN** plan approve 返回 project_constraint，Plan 保持原状态

#### Scenario: 修订基准过期
- **WHEN** 修订请求的 base_revision 为 1，但 Plan 已确认到 revision 2
- **THEN** plan approve 返回 stale_revision

## REMOVED Requirements

### Requirement: 草稿为独立不可变快照
**Reason**: 草稿不再保存为独立快照目录。初次规划与重新规划的草稿就是 draft 状态的 plan.yaml；同一 Plan 内的修订不保存草稿，以请求文件加摘要确认。
**Migration**: 使用 `plan create -c -f` 建立或覆盖 draft Plan；修订时 `plan validate -c -f` 取得预览，`plan approve -c -p -f --digest` 确认。

### Requirement: 安全扩张批准前无返工副作用
**Reason**: 安全扩张模式并入普通修订（冻结节点允许增加 requires），修订在确认前不写任何文件，自然没有副作用。
**Migration**: 保障诊断提示缺少的 Fragment 后，编写修订请求加入对应实例并让受影响节点依赖它，按修订流程预览与确认。
