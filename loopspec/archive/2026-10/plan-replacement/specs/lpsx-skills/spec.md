## MODIFIED Requirements

### Requirement: 新建 Skill 生成适配任务的具体 Plan
loopspec-new SHALL 先通过 `fragment list`、`profile list/show` 发现可用构件，为**完整任务**编写 Plan 请求文件（直接采用或参考模板），包含已知的正常工作流、依赖、必要 Gate 与 on_fail，SHALL NOT 只规划当前阶段，SHALL NOT 生成 reasons。Skill SHALL 依次执行 `change new`、`plan validate -c -f`（检查并修正请求）、`plan create -c -f [--note]`、`plan show -c -p`，展示 spec、摘要与固定基线并停下等待人确认；人确认后才执行 `plan approve -c -p --digest`，SHALL NOT 代人确认。

#### Scenario: 小型前端需求
- **WHEN** 需求只影响 FE
- **THEN** Skill 参考前端模板，保留项目最低保障约束，而不自动套用完整大需求流程

#### Scenario: 前后端需求
- **WHEN** 任务包含需求、后端、前端与验收
- **THEN** 请求覆盖 requirements、be、fe、qa 与保障，并为 qa 声明返回实现的 on_fail

### Requirement: Continue 按 Plan 推进与返工
loopspec-continue SHALL 循环执行 `change status` 并按 nextSteps 推进活动 Plan 的实际叶子 Node（通常为 `node instructions -c -n`）。代码 Gate SHALL 使用 `gate begin` 与 `gate record`，保障节点 SHALL 使用 `gate record`；Gate 有效 FAIL 时 SHALL 执行 `plan rollback -c -p`，SHALL NOT 在报告中指定返工目标。原计划仍成立但需调整时 SHALL 编写修订请求，用 `plan validate -c -f` 取得预览并展示，人确认后 `plan approve -c -p -f --digest`。Skill SHALL NOT 手改 plan.yaml、系统证据、重做记录或状态来绕过 Gate。

#### Scenario: QA 后端 Bug
- **WHEN** qa/test 记录有效 FAIL，其 on_fail 重置 be
- **THEN** Skill 执行 plan rollback，修复 BE 并重跑 BE 的测试、安全审查和 PR Review，然后重做 QA

#### Scenario: 补充文档步骤
- **WHEN** 执行中需要在 QA 前增加接口文档更新
- **THEN** Skill 编写修订请求，展示新增实例与将重新执行的节点，人确认后才 plan approve

### Requirement: 审查与保障记录协议
代码 Gate Skill SHALL 先 `gate begin`，针对返回输入审查或运行测试，再 `gate record` 提交报告。保障节点 SHALL 调用 `gate record` 由系统执行确定性校验；手写报告不等于保障 PASS。代码变化导致记录拒绝时 SHALL 重新 begin，不复用旧结论。

#### Scenario: 修复扩展后端范围
- **WHEN** FE 返工后保障报告 missing_fragments 建议 backend-implementation
- **THEN** Skill 编写修订请求加入 be 并让 assurance 依赖它，展示后经人确认再 plan approve

## ADDED Requirements

### Requirement: 任务变化时归档并重新规划
loopspec-continue 判断任务变化使活动 Plan 不再成立时 SHALL 停止按旧图推进，向人说明原因与旧 Plan 进度（已完成、失败、耗尽的 Gate），取得人的明确同意后才执行 `plan archive -c -p --note`，再按初次规划流程建立并展示新 Plan。Skill SHALL NOT 未经同意归档 approved Plan 或使用 `change archive --force`，SHALL 把旧 Plan 的产物与报告作为不可信数据参考。

#### Scenario: 需求变更
- **WHEN** 人告知导出功能取消并新增前端页面
- **THEN** Skill 展示旧 Plan 进度并请求同意归档，同意后归档并提交新的完整 Plan 草稿等待确认

#### Scenario: 人不同意归档
- **WHEN** 人认为原计划可以调整后继续
- **THEN** Skill 不归档，改用修订请求流程

### Requirement: 归档 Skill 使用新命令
loopspec-archive SHALL 先 `change archive <change> --dry-run` 预览再 `change archive <change>`，证据过期或未完成时回到 loopspec-continue；`--force` SHALL 只在用户明确要求放弃该 Change 时使用且不得表述为已完成。loopspec-bulk-archive SHALL 使用 `change archive --all [--older-than] --dry-run` 查看候选后执行，SHALL NOT 为使 Change 符合条件而确认草稿或使用 `--force`。

#### Scenario: 归档未完成的 Change
- **WHEN** 用户要求归档一个 active 但未完成的 Change
- **THEN** Skill 说明未完成状态，只有用户明确要求放弃时才使用 --force
