# 需求记录

跨 Plan 的背景、边界、重要决策与待解决问题；引擎在末尾追加 Plan 记录。
优先用 `loopspec state add` 追加；`loopspec change status` 原样输出全文，引擎不解析内容。

## 背景

<!-- 问题来源、现状与触发原因。用 `loopspec state add --section background` 追加。 -->
- 2026-11-19 loopspec change archive 一条命令即可完成归档；memory 审阅只写在 loopspec-archive skill 里，模型可直接调用 CLI 跳过（archive-drop-attempts、archive-drop-gate-outputs 两次归档均被跳过，memory 为空）。归档还会删除 Gate 报告与 .attempts，跳过后这些素材在工作区中不可再得。

## 目标与边界

<!-- 预期结果、范围与明确不做的事。用 `loopspec state add --section goals` 追加。 -->
- 2026-11-19 把 change archive 改为两段式，使 memory 审阅成为 CLI 协议的一部分：第一段返回审阅提示与 archiveId 且不移动；第二段凭 archiveId 与审阅结论完成归档；跳过必须显式、可核查并留下记录。补做上述两次被跳过的 memory 审阅。

## 决策

<!-- 重要取舍与确认：`- YYYY-MM-DD [HUMAN: 用户] 内容` 或 `- YYYY-MM-DD [MODEL: BE] 内容`。主体是实际作出决策的人或 Agent 角色，不是代写者。用 `loopspec state add --section decision` 追加。 -->
- 2026-11-19 [HUMAN: xq.yan] change archive 改为两段式：第一段返回审阅提示、素材清单与 archiveId（不移动）；第二段 --confirm <archiveId> --memory updated|none --note 必填；updated 时 CLI 核对 memory/ 确有变化；审阅结论写入 change state.md；去掉 --dry-run（第一段即预览）。Plan 001 确认执行。
- 2026-11-19 [MODEL: ENG-claude-remote] Plan 001 design：Codex 审阅后采纳 6 条修订（memory 快照只计有效 topic、提交时持有全部锁并复核 memory、预检与进度写回可重试、settle 视为收尾而非归档、素材清单含将删除路径、严格事件写入）；不采纳为凭据做签名（与模型同权限环境下不构成安全边界）。

## 待解决问题

<!-- 跨 Plan 仍需追踪的问题；解决或移交时追加新条目并引用原问题。用 `loopspec state add --section open-question --scope change` 追加。 -->

## 参考

<!-- 相关 issue / PR / 讨论 / 产物入口及用途。用 `loopspec state add --section reference` 追加。 -->
- 2026-11-19 用户原始需求（2026-11-19）：loopspec change archive 改成两段式，先返回 prompt 要求 MODEL 提取记忆并返回 archive id；MODEL 确认后 loopspec change archive --confirm <archive id> 真正完成归档；或给出更好的方案，目的是防止 model 通过命令直接跳过 memory 过程。
- 2026-11-19 No relevant memory（loopspec memory list 为空）；基于 PR #15 分支 feat/archive-drop-gate-outputs（未合并）。

## Plan 记录

<!-- 引擎自动追加 Plan 沿革，请勿手工编辑，也勿在此段之后新增段落。 -->
