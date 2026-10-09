## ADDED Requirements

### Requirement: 初始计划覆盖完整任务
loopspec-new SHALL 指导 LLM 一开始就为完整任务组合 Plan，包含已知的正常工作流、依赖、必要 Gate、on_fail 与重试预算，SHALL NOT 只规划当前阶段。

#### Scenario: 前后端需求
- **WHEN** 任务包含需求、后端、前端与验收
- **THEN** Skill 生成覆盖 requirements、be、fe、qa 与最终保障的完整请求，并展示等待确认

### Requirement: 任务变化时构建替换计划
loopspec-continue SHALL 在判断任务变化使活动 Plan 不再适用时停止按旧图推进，编写带 base_revision 与完整 replaces 的替换请求，执行 plans create --replace，展示草稿并等待人工确认。Skill SHALL 只对确实仍然正确的产物声明 reuse，SHALL 为每个有效 FAIL 给出 carry 或 retire，SHALL NOT 自行 approve 或 discard，SHALL NOT 通过手改产物、证据或返工记录绕过替换流程。

#### Scenario: 执行中需求变更
- **WHEN** 人告知导出功能取消并新增前端页面
- **THEN** Skill 停止推进，提交替换草稿（retire 导出实例、新增 fe、沿用仍有效的需求文档），展示后等待确认

#### Scenario: 人放弃替换
- **WHEN** 人在查看替换草稿后决定维持原计划
- **THEN** Skill 请人确认后执行 plans discard，并按恢复的旧图继续
