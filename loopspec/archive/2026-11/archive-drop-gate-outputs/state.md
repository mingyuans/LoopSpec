# 需求记录

跨 Plan 的背景、边界、重要决策与待解决问题；引擎在末尾追加 Plan 记录。
优先用 `loopspec state add` 追加；`loopspec change status` 原样输出全文，引擎不解析内容。

## 背景

<!-- 问题来源、现状与触发原因。用 `loopspec state add --section background` 追加。 -->
- 2026-11-19 change archive 已在归档时删除各 Plan 的 .attempts。归档目录中仍保留 Gate 相关文件：.gates/（begin/evidence/assurance 证据）、.gate-rounds/（每轮记录与 prior 报告副本）以及 artifacts 下各 Gate 的 pass/fail 报告；以 archive-drop-attempts 为例 .gates 80K、.gate-rounds 224K，均只在执行中的 Plan 用于证据绑定。

## 目标与边界

<!-- 预期结果、范围与明确不做的事。用 `loopspec state add --section goals` 追加。 -->
- 2026-11-19 change archive 归档时一并删除 Gate 类型的产物，删除范围待人确认；沿用 .attempts 的删除方式（移动成功后经已移动目录 fd、O_NOFOLLOW、失败只报告）。非目标：plan archive、返工流程、已有历史归档的清理（另行决定）。

## 决策

<!-- 重要取舍与确认：`- YYYY-MM-DD [HUMAN: 用户] 内容` 或 `- YYYY-MM-DD [MODEL: BE] 内容`。主体是实际作出决策的人或 Agent 角色，不是代写者。用 `loopspec state add --section decision` 追加。 -->
- 2026-11-19 [HUMAN: xq.yan] 删除范围：三类全删（.gates/、.gate-rounds/、artifacts 下各 Gate 的 pass/fail 报告），保留需求、设计、实现等非 Gate 产物；Plan 001 草稿确认执行；同一 PR 内按新规则清理 loopspec/archive/ 下已有的 Gate 产物。

## 待解决问题

<!-- 跨 Plan 仍需追踪的问题；解决或移交时追加新条目并引用原问题。用 `loopspec state add --section open-question --scope change` 追加。 -->

## 参考

<!-- 相关 issue / PR / 讨论 / 产物入口及用途。用 `loopspec state add --section reference` 追加。 -->
- 2026-11-19 用户原始需求（2026-11-19）：开 worktree 创建需求：archive 的时候，一起把 gate 类型的产物也一并删除。前序：PR #14（archive-drop-attempts）已合并，代码在 src/loopspec/workflow_archive.py。
- 2026-11-19 No relevant memory（loopspec memory list 为空）

## Plan 记录

<!-- 引擎自动追加 Plan 沿革，请勿手工编辑，也勿在此段之后新增段落。 -->
