## 背景与动机

LoopSpec 当前以固定 Schema 表示完整工作流。预置流程适合包含需求、设计、前后端实现、安全审查、PR Review 和 QA 的大型需求，但对于仅涉及前端的小需求、局部 Bugfix 或纯文档变更过重；继续增加更多固定模板又会造成模板数量膨胀，并且仍然无法覆盖真实项目中的组合变化。

另一个核心问题是返工闭环。QA 环境发现问题后，Agent 不仅要回到正确的前端或后端实现阶段，还必须重新经过该实现阶段要求的关键 Gate。例如后端修复必须重新经过 `security-review` 和 `pr-review`。如果修复范围扩大，或 Gate 通过后代码再次变化，流程还需要在正式提交前发现缺失或过期的审查证据，不能仅依赖 Agent 对问题范围的文字判断。

本变更用 `Node`、`Fragment`、`Profile`、`Plan` 四个对外概念解决上述问题：LLM 参考 Profile 为单个需求生成适配场景的 Plan；LoopSpec 负责确定性展开、校验、快照和执行。第二版本进一步提供 Fragment 级返工路由和基于全部 Diff 的 Gate 证据保障。

## 变更内容

- 将 `Node` 定义为统一编排单位。Fragment 的 `nodes` 中可以直接定义执行 Node，也可以用 `use` 引用其他 Fragment 作为节点；引用在 Plan 编译时展开为内部 Node，运行时执行活动快照中的叶子，最终叶子 Node 是最小实际执行单位。Node 不拥有独立配置文件。
- 将 `Fragment` 定义为最小文件配置单位。`fragments/<name>.yaml` 只有统一的 `nodes` 编排列表，不另设 `includes`；直接定义节点与引用节点共用 `id/requires`，可任意混合。Fragment 同时是复用边界和返工重跑边界。
- 将 `Profile` 定义为工作流模板。Profile 选择 Fragment 实例并声明它们的依赖，提供适用场景与 LLM 指引，并可在 flow 条目上声明 on_fail 返回上游 Fragment 实例；可表达串行和并行流程。
- 将 `Plan` 定义为单个需求最终确定的执行图。Plan 记录 Profile 基线、LLM 的选择理由和偏离，完全展开 Fragment 与 Node，并把全部指令、模板、恢复规则、保障规则和资源固化为不可变修订版。
- 第一版本实现自适应计划生成：为大型需求、前端小需求、Bugfix 等提供内置 Fragment 与 Profile；LLM 可直接采用或参考 Profile，也可在项目最低约束下自行组合；LoopSpec 校验后创建变更并按活动 Plan 执行。
- 第二版本实现返工闭环：Profile/Plan 的 flow 条目可声明 `on_fail`，例如 `qa` 失败时重置其列出的 `fe`、`be` 实例及下游，从而重新执行实现 Fragment 内的必要 Gate；失败报告不选择返工目标。
- 引用节点可在本次引用中声明 `on_fail.reset`，返回同一 Fragment 的上游直接定义节点或引用节点。其成功由全部内部节点完成且必要证据有效推导，失败由未处理的有效 Gate FAIL 推导；未执行不是失败，系统错误阻塞。内部恢复先执行，没有规则或预算耗尽时再向外传播，同一失败只处理一次。
- 第二版本增加 `change-assurance` Fragment。其保障 Node 基于 Plan 创建时固定的 Git 基线检查当前全部 Diff，根据项目路径规则验证每项改动都有当前内容摘要绑定的 Gate PASS；未知文件、缺失证据和过期证据默认失败。Gate 先记录审查输入，审查结束再确认输入一致并记录 PASS，防止把旧审查绑定到新代码。
- 同一 Fragment 的多次引用生成独立实例和证据，例如 FE 与 BE 的 PR Review 不互相覆盖。项目最低保障约束独立于 Profile 选择，不能通过换用更轻的模板自动绕过。
- 保留运行中的计划修订。未来工作可安全重组；保障检查发现当前 Plan 无法覆盖的新改动范围时，必须先生成新 Plan 修订版补充所需 Fragment，不能绕过 Gate。
- 旧 Schema 与旧 Change 通过内部兼容适配器继续工作，但新 CLI、文档和用户心智模型不再把 Schema 作为新架构概念。
- 需求、方案与报告继续使用中文叙述；命令、字段、错误码、路径和规范关键字保留原始技术标识。按用户后续澄清，内置 Skill 源 builtin/skills 使用英文，不修改 .codex/skills 等本地安装投影。

## 能力范围

### 新增能力

- `workflow-fragments`：Node 定义、Fragment 文件、Fragment 递归组合、资源解析、确定性展开和冲突校验。
- `workflow-planning`：Profile 模板、LLM Plan 提议、Profile 偏离审批、自包含不可变 Plan 及旧 Schema 兼容适配。
- `workflow-recovery-assurance`：flow 级失败返工、QA 返工循环、Gate 证据绑定、全量 Diff 覆盖校验和安全计划修订。

### 修改能力

- `loopspec-cli`：新增 Fragment、Profile、Plan、Gate 证据和重组命令；新建流程优先使用 Plan，同时保持旧 Change 的状态、指令、回滚和归档行为。
- `lpsx-skills`：使 `loopspec-new` 根据任务选择或调整 Profile 并生成 Plan，使 `loopspec-continue` 按 Plan 推进、按 on_fail 处理返工、保障失败与计划修订。

## 影响范围

- 核心领域模型、图编译与状态计算、Gate 判定与回滚、Git Diff 采集、证据摘要、变更元数据、CLI 和错误契约。
- 新增 `fragments/`、`profiles/` 与逐变更 Plan 修订目录；旧 `schemas/` 仅保留兼容用途。
- 内置资源需覆盖大型需求、前端小需求和 Bugfix，并包含实现、审查、QA 与最终保障 Fragment。
- 需要扩展安全路径、原子写入、内容摘要、Git 路径处理、on_fail 返工和旧流程回归测试；不新增第三方运行时依赖或外部服务。
