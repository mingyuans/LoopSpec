# Human Approval: CHANGES REQUESTED

## Changes Requested

- 删除完整替换模式的复杂机制：`plans create --replace`、`replaces`（reuse/carry/retire）、`validate_replacement`、suspended 状态与 `plan_suspended`、`history_boundary`、确认事务中的 copies、RevisionContext.mode 与 Plan 快照版本 3。
- 改为“归档后重新规划”：任务变化时用 `plans archive` 归档当前活动 Plan，Change 回到无活动 Plan 的状态，再按与初次规划相同的草稿创建 → 展示 → 确认流程建立新 Plan。引擎只关心当前是否有活动 Plan；没有时，最新 Plan 处于草稿或其他状态。
- 状态分两层：Change 级状态（`.workflow.yaml` 记录固定基线、仓库身份、唯一活动 Plan 指针、下一个 Plan 编号）与每个 Plan 自己的状态（`plans/<NNN>/state.yaml` 记录 draft/active/archived/discarded、活动修订、确认记录、归档原因）；每个 Plan 的产物、Gate 证据与返工历史放在自己的目录内。
- 保留 Revision 层：任务层级为 Change → Plan → Revision；同一 Plan 内的普通修订与安全扩张沿用现有冻结与失效规则并共用该 Plan 的运行时数据；任务变化才新建 Plan。
- 在 design.md 中完整说明两套层级：任务层级 Change → Plan → Revision，工作流组织层级 Node → Fragment → Profile → Plan，以及 Plan 在两套层级中的位置；给出关键流程的顺序说明与 mermaid sequenceDiagram。

## Human's Words

> 需要这么复杂吗，不就是 新增订 Plan 的时候，归档已有 Plan, 重新规划，然后走 plan draft review 的过程？LoopSpec 引擎只管当前有没有 active plan, 如果没有，最新 paln 是 draft 还是什么状态，

> 你现在的设计里边， 有 change 级别的 state 吗

> 不够，如果是 一个 change 多个 plan, 那么 state也要分开；有 chagne 级别的 state, 每个 plan 也有自己的 state

> Revision 这层是什么

> 保留； 所以现在就任务而言有 change -plan - revision 三层； 工作流组织方面，有 node - fragments - profile - plan 四层？ 你把这些关键层级划分，整理成到 design 里边，完整说明，然后有顺序时序说明，mermaid sequense 表达。

## Summary Presented to the Human

第一轮方案：一个 Change 保存多份 Plan（以修订号标识），同一时间最多一个活动 Plan；新增 `plans create --replace` 完整替换模式，请求带 `replaces`（reuse 沿用产物、carry 承接失败、retire 放弃实例）；替换草稿使活动 Plan suspended；`plans discard` 撤销草稿；确认事务归档旧 Plan 全部节点并复制沿用产物；返工历史以 history_boundary 分区；RevisionContext.mode 与 Plan 快照版本 3。任务 7 组 25 项，安全审查 PASS。

## Suggested Direction

- Change 级与 Plan 级状态分离，Plan 目录自包含运行时数据，使“归档”只是状态变化、无需移动文件；运行时根目录指向 Plan 目录，Diff 控制目录排除与固定基线仍按 Change 计算。
- 新 Plan 强制沿用 Change 固定基线，最终保障覆盖从最初基线开始的全量 Diff，防止通过重新规划遗漏已有改动的审查。
- 默认决策（待在下一轮审批中确认）：每个 Plan 保留人可读的 `state.md`；`plans archive` 执行前必须取得人的明确同意。

## state.md Write-Back

- Decision Log: round 1 - changes requested
- Rejected Options: 完整替换模式（--replace、replaces、suspended、history_boundary、copies、mode/版本 3）
- Open Questions: Plan 级 state.md 是否需要；plans archive 前是否必须人工同意（暂定均为是）
- Current Focus: redo specs/design per round 1 feedback
- Artifact Notes: approval/changes-requested.md - changes requested
