# 人工审批：要求修改

## 修改要求

- 将新架构的对外领域模型收敛为 `Node`、`Fragment`、`Profile`、`Plan` 四个概念；`Schema` 仅作为旧格式兼容实现，不再参与新工作流的用户心智模型。
- 将 `Node` 定义为最小执行单位且不提供独立配置文件；将 `Fragment` 定义为最小文件配置单位，允许直接定义一个或多个 Node，并允许声明式引用其他 Fragment。
- 将 `Profile` 定义为供 LLM 直接使用或参考的工作流模板，承载 Fragment 级正常流程和有限枚举的失败路由，但不增加 Fragment `interface` 或 Node 级通用 `links`。
- 将 `Plan` 定义为单个需求最终确定、完全展开、自包含且不可变修订的执行图；`status`、`next`、`rollback` 等运行时行为只读取活动 Plan。
- 增加 Fragment 级返工语义：例如 `qa-testing` 失败报告按受 Profile 限制的分类路由到 `fe-implementation` 或 `be-implementation`，并重跑目标 Fragment 内包含的 `pr-review`、`security-review` 等必要 Gate。
- 增加提交前 `change-assurance` Fragment：基于固定 Diff 基线检查全部变更是否具有当前内容摘要绑定的 Gate PASS 证据；未知文件、缺失证据或过期证据必须默认失败，并路由到相应 Fragment 补齐后再次校验。
- 重新划分第一版本与第二版本：第一版本解决按场景组合轻量或完整工作流并生成 Plan；第二版本实现 QA 返工闭环、Fragment 级跳转、Gate 证据覆盖与计划修订。

## 用户原话

> 你按照上面讨论，整理方案，重新设计

## 已向用户展示的讨论结论

现有固定模板无法同时适配大型需求、仅前端的小需求和 Bugfix。Fragment/Profile/Plan 能解决流程轻重选择，但仅靠 QA 失败跳转无法保证修复期间或审查之后发生的所有代码变更都经过必要 Gate。讨论形成的方案是：Profile 负责 Fragment 级模板与失败路由，Implementation Fragment 内包含必要审查 Gate，最终由 `change-assurance` Fragment 对本次全部 Diff 和 Gate PASS 证据进行封闭式校验。

## 建议调整方向

用 Fragment 作为配置、复用和返工边界；用 Profile 表达模板级流程与有限路由；用 Plan 固化展开后的 Node Graph。避免引入 Fragment `interface`、Profile Node-level `links` 和分散的通用 `when.changed_any` 作为主机制。通过 Diff 基线、Gate 覆盖规则、内容摘要和最终保障门禁实现安全闭环。

## state.md 回写

- 决策日志：人工审批第 2 轮要求修改。
- 否决选项：新架构继续以 Schema 为核心、Fragment 黑盒接口、Profile Node-level 通用 Links、仅靠 QA 分类保证审查覆盖。
- 当前关注：按第 2 轮反馈重新设计规格与方案。
- 材料备注：`approval/changes-requested.md`——要求修改。
