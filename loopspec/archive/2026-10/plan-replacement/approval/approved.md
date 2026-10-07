# Human Approval: APPROVED

## Summary Presented to the Human

- **问题**：任务变化时无法放弃旧计划重新规划；多份 Plan 会共用产物、证据与返工次数；重新规划可能更换固定基线。同时新工作流积累了兼容代码与重复机制，CLI 中还并存已发布的旧 Schema 流程。
- **能力**：新增 `change-plan-lifecycle`（8 条需求）；修改 `workflow-plan-approval`、`workflow-planning`、`workflow-recovery-assurance`、`workflow-fragments`、`loopspec-cli`、`lpsx-skills`；整体删除 `status-report`（12 条）、`artifact-discovery`（10 条）与 `usage-docs` 中 2 条需求。
- **关键决策与取舍**：
  - 两套层级：任务层级 Change → Plan → Revision，工作流组织层级 Node → Fragment → Profile → Plan；执行图即 `plan.yaml` 的 `spec`。
  - Change 级 `.workflow.yaml`（基线、仓库、活动与未结束 Plan 指针、下一个编号）与一份 Plan 一个 `plans/<NNN>/plan.yaml`（`meta`：draft/approved/archived 等；`spec`：based_on、flow、nodes，`on_fail` 在 Gate 内）；每份 Plan 自带 `state.md` 与运行时目录。
  - 小调整在同一 Plan 内修订（`plan validate -f` 预览、`plan approve -f --digest` 确认；冻结节点只能增加依赖，取代安全扩张）；任务变化经人同意 `plan archive` 后重新规划，新 Plan 从空状态开始并沿用 Change 基线。
  - 中断后重新执行同一命令即可收敛，不设事务文件与 recover。
  - 命令树 `loopspec <资源> <动作>`（change、plan、node、gate、fragment、profile），`-c/-p/-n/-f` 显式指定；保障节点通过 `gate record` 执行；工作流命令统一输出 JSON；恢复 `plan validate` 作为只读检查与修订预览。
  - 删除旧 Schema 流程并发布不兼容的 2.0.0；删除未发布新工作流中的快照/草稿/确认记录、受保护步骤、能力版本、由内向外 on_fail 处理链、pending、reasons 等（design D11）。
  - 取舍：重新规划需重做旧进度；资源与配置实时生效；同一 Plan 只保留当前修订；旧 Schema Change 不自动迁移。
- **任务**：8 组 44 项；1.1 先确认测试计划；依次为模型、编译与 on_fail、命令树与 Plan 生命周期、中断收敛、运行时与修订、删除旧 Schema 流程、内置资源/Skill/文档、验证。
- **安全审查**：PASS；残余风险 5 条（实时资源与配置、本地完整性边界、人工同意由 Skill 约束、最低保障依赖 required_fragments、不兼容发布的迁移提示）。
- **待定事项**：tasks 6.6 中 `add-schema-sources` 与 `artifacts-command` 的处理方式。

## Human's Words

> 进入实施； add-schema-sources 先不管。

## Non-Blocking Suggestions

- tasks 6.6：`add-schema-sources` 本变更不处理（保持现状）；`artifacts-command` 的处理方式未表态，执行到 6.6 时再向用户确认。

## state.md Write-Back

- Decision Log: round 2 - approved
- Frozen Decisions: 见 state.md 中 round 2 冻结的方案要点（层级与两级状态、plan.yaml 结构、修订与重新规划、中断收敛、命令树与 plan validate、旧 Schema 删除与 2.0.0、D11 删除清单）
- Artifact Notes: approval/approved.md - approved
