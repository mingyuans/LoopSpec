# 需求记录

需求背景、跨 Plan 的决策与更替原因。
人与 LLM 可直接编辑；`loopspec change status` 原样输出全文，引擎不解析。

## 背景

<!-- 用户原始诉求、要解决的问题、现状与触发原因。由 new skill 在创建 Plan 前填写。 -->

`loopspec change status` 的 NEXT STEPS 目前只给出一个步骤，但有些流程期望多步骤并行。例如 PRD 生成后，fe / be / qa 三个 sub agent 同时按流程评审 PRD 并各自生成评审意见，最后由一个 Gate 综合三份评审报告给出 PASS 或 FAIL，FAIL 时 rollback。

现状：Plan 本身是 DAG，`flow` 已能表达扇出 / 扇入（如 `large-feature` 中 fe、be 都只依赖 design），`status()` 也会把所有依赖满足的叶子标为 ready；但 `workflow_runtime.py` 只取第一个 ready 叶子写入 `nextSteps`，文本报告也提示“只执行 NEXT STEPS 中的那一个”，因此调用方只会串行推进。

## 目标 / 非目标

目标：
- `nextSteps` 列出所有 ready 叶子的 `loopspec node instructions` 命令（仍为字符串列表，保持现有契约），并在 JSON 中增加并行标记，表明这些步骤彼此独立、可并行执行。
- `change status` 文本报告在存在多个 ready 步骤时说明可并行（如每个步骤派一个 sub agent），并调整 NODES / NEXT STEPS 中“只执行一个”的提示语。
- `loopspec-continue` skill（含 `skill_templates` 生成的各工具版本）说明如何并行派发：每个 sub agent 只负责一个叶子，汇合后再读 status。
- 文档给出“PRD → fe/be/qa 并行评审 → 综合 Gate（on_fail 回退）”的 request 示例。

非目标：
- 不改变 `nextSteps` 为结构化对象。
- 不改写锁语义：并发写仍快速失败（`concurrent_write`），只在 skill 中说明稍后重试。
- 不新增 PRD 评审相关 Fragment / Profile（属于 registry 仓库，另开需求）。
- 不改变 rollback 优先级：存在待执行 rollback 时 nextSteps 仍只给 rollback 命令。

## 关键决策

<!-- 每条一行：- YYYY-MM-DD（确认人）：决策内容；理由。
只追加；推翻旧决策时新增一条并注明取代哪条。 -->

- 2026-10-11（用户）：nextSteps 保持字符串列表，列出全部 ready 叶子并增加并行标记；理由：向后兼容现有 skill 与调用方。
- 2026-10-11（用户）：写锁保持 LOCK_NB 快速失败，由 skill 指引重试；理由：不改引擎锁语义。
- 2026-10-11（用户）：本次只做引擎与 skill，不新增 PRD 评审 Fragment / Profile；理由：评审 Fragment 属于 registry 仓库。

## 参考

<!-- 相关 issue / PR / 已归档 Change。 -->

## Plan 记录

<!-- 引擎在此之后追加 Plan 归档事件；LLM 可在事件行下补充更替原因。 -->
