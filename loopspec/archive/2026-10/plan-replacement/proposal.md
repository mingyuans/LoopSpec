## Why

LLM 接到任务后通过 Fragment 组合完整 Plan，确认后由 CLI 按图导航。执行中任务可能发生变化，使原 Plan 不再适用；现有实现既不能重新组织已执行的部分，也没有“放弃旧计划、重新规划”的入口。现有 Change 只有一份状态，产物、Gate 证据和返工历史都放在 Change 根目录下，多份 Plan 会共用这些文件：新 Plan 的同名节点会因旧文件存在而被视为完成，返工次数也会混在一起；固定基线只存在于 Plan 快照中，重新规划可能换成新的 HEAD。

同时，尚未发布的新工作流积累了较多兼容代码与重复机制（快照/草稿/确认记录目录、受保护步骤、V1/V2 能力版本、安全扩张专用模式、三套事务与 recover、由内向外的 `on_fail` 处理链等），而 CLI 里还并存着已发布的旧 Schema 流程，两套工作流共用平铺命令。在加入多 Plan 之前先做减法、只保留一套工作流，可以让实现、命令与概念保持一致。

## What Changes

- **两套层级**：任务层级 **Change → Plan → Revision**；工作流组织层级 **Node → Fragment → Profile → Plan**。一份 Plan 的 `plan.yaml` 中的 `spec` 就是当前修订的执行图。
- **两级状态**：
  - Change 级 `.workflow.yaml`（format_version 4）：固定基线、仓库身份、不保存 Plan 指针；活动 Plan 与未结束 Plan 由各 plan.yaml 的 status 推导，Change 状态（unplanned/planning/active/complete）同样推导。
  - Plan 级：一份 Plan 就是一个 `plans/<NNN>/plan.yaml`，`meta` 记录 `status`（draft/approved/archived，只记录人的决定）、当前修订号、`spec` 摘要、确认时间与说明；`spec` 只含 `based_on`、`flow`、`nodes`。另有人可读的 `plans/<NNN>/state.md`。完成状态不落盘，实时推导。
- **Plan 目录自包含**：产物、Gate 证据、审查轮次与重做记录都在 `plans/<NNN>/` 内；运行时以 Plan 目录为根；Git Diff 与固定基线按 Change 计算；指令、模板等资源与 `config.yaml` 执行时读取最新内容；加载时校验 `spec` 摘要。
- **归档后重新规划**：`plan archive` 归档 draft 或 approved Plan（归档 approved Plan 前必须取得人的同意），之后按与初次规划相同的流程建立新 Plan；新 Plan 从空状态开始，旧 Plan 原样保留。
- **同一 Plan 内修订不保存草稿**：`plan validate -f` 只读编译并返回修订预览，`plan approve -f --digest` 确认后替换 `spec`；`plan create` 只负责 draft Plan。冻结节点的 `requires` 允许增加，增加依赖的节点及下游重新执行，取代安全扩张模式；有效 FAIL 必须落在重新执行范围内。
- **`on_fail` 回到原 Schema 语义**：编译后放在 Gate 内，每个 Gate 最多一条，重叠报错；返工次数按 Gate 统计。
- **单一生效写入**：每条命令只有一次决定状态的写入，中断后状态只有“之前”或“之后”，Agent 照常按 change status 推进；生效后的归档搬运由后续命令按记录补完；不设中断状态、事务文件与 recover 命令。
- **命令树**：统一为 `loopspec <资源> <动作>`（`change`、`plan`、`node`、`gate`、`fragment`、`profile`），用 `-c`、`-p`、`-n`、`-f` 显式指定 Change、Plan、节点与请求文件；保障节点通过 `gate record` 执行；工作流命令统一输出 JSON。
- **BREAKING：删除旧 Schema 流程**（已在 v1.0.x 发布）：`schemas` 命令、按 Schema 执行的 Change、`builtin/schemas/`、纯文本状态报告、跨 Schema 产物发现及相关模块、文档与测试；发布为 2.0.0，旧 Change 不自动迁移。
- **BREAKING（均未发布）删除**：快照/草稿/确认记录目录与相关模型；`spec` 中的冗余字段与逐实例 `reasons`；确认说明与修订历史；受保护步骤与偏离审批；Plan 版本 1/2 与直接激活入口；`plans recompose`、`plans discard`、`--safety-expansion`、`--message`、`assurance check`、`recover`；V1/V2 能力版本、`manual-v1` Profile 与 `delivery-review` Fragment；`config.yaml` 的 `default_profile`；`.workflow/revisions/`；平铺命令与复数分组命令。
- **保留**：`change-assurance` 保障节点、Gate 两步证据、固定基线 Diff、保障规则与 `provides`、Fragment 节点的 `tracks`、写锁与安全路径、返工不碰业务代码、`init` 的工具脚手架。

## Capabilities

### New Capabilities
- `change-plan-lifecycle`: Change → Plan → Revision 层级、Change 级与 Plan 级状态、`plan.yaml` 结构与完整性、Plan 目录布局、归档后重新规划、修订确认、单一生效写入与收尾补完、固定基线跨 Plan 沿用。

### Modified Capabilities
- `workflow-plan-approval`: 草稿即 draft Plan；修订不保存草稿；确认绑定 `meta.digest`；删除快照、草稿目录、确认记录目录与受保护偏离审批。
- `workflow-planning`: Plan 持久化改为 `plan.yaml`；资源与项目约束实时读取；请求不再包含 `reasons`；删除能力版本与旧激活入口。
- `workflow-recovery-assurance`: 返工按 Gate 自身 `on_fail`，删除由内向外处理链；重做记录统一在 `.attempts/`；修订允许冻结节点增加依赖并取代安全扩张；固定基线归 Change；控制目录排除 `plans/`；保障节点通过 `gate record` 执行。
- `workflow-fragments`: 每个 Gate 最多一条 `on_fail`，引用节点与 flow 条目的 `on_fail` 编译下放，重叠报错；删除 `min_engine_version`。
- `loopspec-cli`: `loopspec <资源> <动作>` 命令树与参数约定；`init` 不再处理 Schema；删除旧流程命令与输出规则。
- `lpsx-skills`: 初始 Plan 覆盖完整任务；修订先预览再确认；任务变化时先取得人同意再归档并重新规划；使用新命令树。
- `status-report`: 整体删除（旧 Schema 的纯文本状态报告）。
- `artifact-discovery`: 整体删除（跨 Schema 产物发现），由 `change artifacts` 按 Plan 列出产物取代。
- `usage-docs`: 删除 schema.yaml 字段参考与内置工作流文档的要求。

## Impact

- 代码：重写 `cli.py` 为新命令树；修改 `workflow_models.py`、`workflow_lifecycle.py`、`workflow_confirmation.py`、`workflow_revision.py`、`workflow_recovery.py`、`workflow_runtime.py`、`workflow_compiler.py`、`workflow_planning.py`、`workflow_diff.py`、`workflow_evidence.py`、`workflow_assurance.py`、`workflow_changes.py`、`workflow_cli.py`、`models.py`、`errors.py`；删除 `workflow_drafts.py`、`workflow_approval.py`、`workflow_snapshot.py` 中的快照实现，以及旧 Schema 流程的全部模块（见 design D11）。
- 内置资源：删除 `builtin/schemas/`、`manual-v1` Profile 与 `delivery-review` Fragment；Fragment/Profile 去掉 `min_engine_version`。
- Skill 与文档：`builtin/skills` 的 new/continue/archive/bulk-archive；`docs/{zh,en}` 的概览、工作流组合、Agent 协议、配置与 CLI 参考，删除 schema 参考与 secure-spec-driven 工作流文档；README。
- 发布：不兼容的大版本 2.0.0，release notes 说明迁移方式。
- 关联变更：同步修订尚未归档的 `dynamic-workflow-composition` 与 `plan-draft-approval`；处理失去意义的 `add-schema-sources` 与 `artifacts-command`。
- 依赖：不新增第三方依赖、网络访问或 Shell 调用。
