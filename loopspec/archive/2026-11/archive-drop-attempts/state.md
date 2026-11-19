# 需求记录

跨 Plan 的背景、边界、重要决策与待解决问题；引擎在末尾追加 Plan 记录。
优先用 `loopspec state add` 追加；`loopspec change status` 原样输出全文，引擎不解析内容。

## 背景

<!-- 问题来源、现状与触发原因。用 `loopspec state add --section background` 追加。 -->
- 2026-11-19 loopspec change archive 目前把整个 Change 目录（含每个 Plan 下的 .attempts/ 返工归档文件）移到 archive/<YYYY-MM>/。.attempts 只在活动 Plan 的返工流程（rollback 计数、priorAttempts）中有用，归档后体积大、文件多（例如 registry-global-store 有 4 轮返工、几十个文件），提交进仓库没有价值。

## 目标与边界

<!-- 预期结果、范围与明确不做的事。用 `loopspec state add --section goals` 追加。 -->
- 2026-11-19 change archive 实际归档时自动删除各 Plan 的 .attempts/，不放入 archive；--dry-run 报告将删除的内容但不删除。非目标：不改 plan archive（Plan 级归档）、不清理已在 archive/ 中的历史 .attempts、不改返工流程本身。

## 决策

<!-- 重要取舍与确认：`- YYYY-MM-DD [HUMAN: 用户] 内容` 或 `- YYYY-MM-DD [MODEL: BE] 内容`。主体是实际作出决策的人或 Agent 角色，不是代写者。用 `loopspec state add --section decision` 追加。 -->
- 2026-11-19 [HUMAN: xq.yan] 需求：change archive 归档时自动删除 .attempts，不放入 archive。
- 2026-11-19 [HUMAN: xq.yan] Plan 001：确认 requirements→be→qa→assurance 草稿（无 design 节点）；--force 归档未完成 Change 时也删除 .attempts，所有归档一律不保留。

## 待解决问题

<!-- 跨 Plan 仍需追踪的问题；解决或移交时追加新条目并引用原问题。用 `loopspec state add --section open-question --scope change` 追加。 -->

## 参考

<!-- 相关 issue / PR / 讨论 / 产物入口及用途。用 `loopspec state add --section reference` 追加。 -->
- 2026-11-19 用户原始需求（2026-11-19）：开 worktree 完成需求：需求归档的时候，自动删除 .attempts 不放到 archive。相关代码：src/loopspec/workflow_archive.py archive()/move()。
- 2026-11-19 No relevant memory（loopspec memory list 为空）

## Plan 记录

<!-- 引擎自动追加 Plan 沿革，请勿手工编辑，也勿在此段之后新增段落。 -->
