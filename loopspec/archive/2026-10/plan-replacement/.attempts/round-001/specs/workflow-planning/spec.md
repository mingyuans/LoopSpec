## ADDED Requirements

### Requirement: 一个 Change 多份 Plan 且最多一个活动
一个 Change SHALL 以修订号标识并保存多份不可变 Plan 快照，历史快照 SHALL 完整保留且不被修改。同一时间 SHALL 最多一个活动 Plan，执行导航 SHALL 只以活动 Plan 为准。每份修订 SHALL 记录 mode（initial、revise、expand、replace），替换修订 SHALL 额外记录 replaces 处置与 history_boundary。plans history SHALL 按修订列出 mode、替换原因、历史边界与该修订期间的返工记录摘要。

#### Scenario: 查看替换历史
- **WHEN** Change 经历修订 1（initial）、2（revise）、3（replace）
- **THEN** plans history 按序返回三份修订的摘要与 mode，修订 3 包含替换原因与历史边界

### Requirement: 新快照版本兼容旧快照
新建 Plan SHALL 使用快照版本 3 记录 mode、history_boundary 与 replacement。版本 1/2 快照 SHALL 按原字段读取并按原方式计算摘要；版本 2 的 safety_expansion SHALL 映射为 expand 或 revise，history_boundary SHALL 视为 0。

#### Scenario: 读取开发期快照
- **WHEN** 已有版本 2 活动 Plan 的 Change 执行 status 与普通修订
- **THEN** 摘要校验通过，行为与本变更之前一致

### Requirement: 初始 Plan 覆盖完整任务
初始 Plan SHALL 覆盖当前已知的完整任务，包含正常工作流、依赖、必要 Gate、on_fail 与重试预算，SHALL NOT 默认只规划当前阶段。系统 SHALL 继续以项目最低约束与最终保障要求判断 Change 完成。

#### Scenario: 只规划需求阶段
- **WHEN** 项目要求最终保障，初始请求只包含 requirements
- **THEN** 草稿创建因缺少项目要求的最终 Assurance 被拒绝
