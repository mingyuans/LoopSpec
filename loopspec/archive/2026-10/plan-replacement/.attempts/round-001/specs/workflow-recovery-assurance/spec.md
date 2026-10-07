## MODIFIED Requirements

### Requirement: 恢复边不破坏执行 DAG
on_fail SHALL 作为有次数限制的恢复规则存储，不作为反向依赖边加入 Node DAG。max_retries SHALL 绑定规范处理者/规则身份及对应 Gate 历史，引用节点共享预算 SHALL 覆盖其全部内部失败。内层计数 SHALL 不因父级重置、普通重组、安全扩张或删除当前 FAIL 文件清零。修订 SHALL 保留既有身份历史映射，或拒绝试图重命名已有处理者以清零预算的请求。经人工确认的完整替换 SHALL 以 history_boundary 开始新的计数区间，边界之前的记录 SHALL 原地保留且可查询；exhausted 的 Gate SHALL NOT 通过替换承接后重新获得预算。

#### Scenario: 连续 QA 失败
- **WHEN** 同一 qa/test 经多轮返工达到上限
- **THEN** 系统停止并返回历史与人工处理指引

#### Scenario: 普通重组不清零
- **WHEN** qa 的 on_fail 已消耗 2 次后进行普通重组
- **THEN** 新修订继续统计这 2 次

#### Scenario: 替换开始新区间
- **WHEN** 人确认完整替换后新 Plan 的 qa 首次失败
- **THEN** 计数从边界之后开始，边界之前的记录仍在 plans history 中可见

### Requirement: 修订与安全扩张
普通重组 SHALL 冻结当前及具有执行/Attempts 证据的 Node。安全扩张 SHALL 只添加系统诊断要求的 Fragment，保留旧节点定义和基线，并显式使新增依赖影响的 QA/Assurance 失效。完整替换 SHALL 不受上述冻结规则约束，但 SHALL 保持固定基线与项目约束、显式处置旧成果与未解决问题，并通过覆盖检查。激活与失效归档 SHALL 在受锁保护的可恢复事务中完成；新 Plan 摘要 SHALL 使旧代码 Gate 证据不可直接继承。

#### Scenario: 扩张到 BE
- **WHEN** FE Plan 的 Assurance 要求新增 BE 流程
- **THEN** 新 Plan 增加 BE，在重新 QA 和 Assurance 前完成必要 Gate，并保存旧修订版

#### Scenario: 扩张事务失败
- **WHEN** 已写新计划但失效归档失败
- **THEN** 系统保持旧绑定或阻塞待恢复，不能暴露新图和旧完成证据的混合状态

#### Scenario: 普通重组试图改写已完成节点
- **WHEN** 任务变化后用普通重组改写已完成的 be/code
- **THEN** 系统以 node_frozen 拒绝并提示使用 --replace
