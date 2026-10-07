## ADDED Requirements

### Requirement: 替换草稿暂停活动 Plan
存在 mode: replace 的待确认草稿时，Change SHALL 处于 suspended：status SHALL 返回 suspended 与 pendingReplacement，nextSteps SHALL 只指向 plans show；instructions、next、gate begin、gate record、rollback 与 assurance check SHALL 返回 plan_suspended。普通修订与安全扩张草稿 SHALL NOT 暂停活动 Plan。

#### Scenario: 替换等待确认
- **WHEN** 活动修订 2 存在替换草稿，Agent 调用 instructions be/code
- **THEN** 返回 plan_suspended，不推进旧图

#### Scenario: 普通修订草稿
- **WHEN** 活动修订存在普通修订草稿
- **THEN** 旧图照常执行，status 展示 pendingDraft

### Requirement: 撤销待确认草稿
系统 SHALL 提供 `plans discard <change> [--expected-digest]`，在写锁内且无未完成事务时清除草稿绑定，写入 `.workflow/discards/<draft-id>.yaml`（草稿 ID、摘要、时间、可选说明），草稿快照 SHALL 原地保留。摘要不匹配 SHALL 返回 plan_changed；没有草稿 SHALL 返回 draft_missing。撤销替换草稿后 SHALL 恢复执行当前活动 Plan。

#### Scenario: 放弃替换
- **WHEN** 人决定不替换，执行 plans discard 并给出展示过的摘要
- **THEN** 草稿绑定清除、记录写入 discards，status 不再 suspended，旧图恢复导航

### Requirement: 替换确认原子切换
替换草稿的 approve SHALL 复核替换校验且结果与草稿一致，并在同一可恢复确认事务中完成：归档旧 Plan 全部节点文件、按 copies 复制沿用产物并校验摘要、写审计记录、切换活动指针、写确认记录、清除草稿绑定。事务检查 SHALL 拒绝不属于旧节点输出或新沿用目标的路径。任何中断后 SHALL 只存在一个活动指针；recover --inspect SHALL 只读校验，recover --resume SHALL 续做同一切换且重复执行结果一致。

#### Scenario: 归档中途中断
- **WHEN** 确认事务已写入、部分旧文件已归档时进程中断
- **THEN** status 返回 transaction_pending，活动指针仍为旧修订；recover --resume 完成归档、复制与切换

#### Scenario: 指针已切换后中断
- **WHEN** .workflow.yaml 已指向新修订但事务文件尚未删除
- **THEN** recover --resume 只删除事务文件，不重复复制或产生新修订

#### Scenario: 复制目标被篡改
- **WHEN** 中断后沿用目标文件已存在但摘要与记录不同
- **THEN** recover 以 transaction_integrity 拒绝，不覆盖该文件
