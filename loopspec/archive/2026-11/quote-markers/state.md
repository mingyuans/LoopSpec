# 需求记录

跨 Plan 的背景、边界、重要决策与待解决问题；引擎在末尾追加 Plan 记录。
优先用 `loopspec state add` 追加；`loopspec change status` 原样输出全文，引擎不解析内容。

## 背景

<!-- 问题来源、现状与触发原因。用 `loopspec state add --section background` 追加。 -->
- 2026-11-20 文本报告中的多行引用块（instruction、template、memory、state、Gate 模板、归档指引等）只靠 4 空格缩进与说明段区分，没有显式结束标记；正文中的空行与原有缩进让边界不清，模型写产物时还需自行去缩进。

## 目标与边界

<!-- 预期结果、范围与明确不做的事。用 `loopspec state add --section goals` 追加。 -->
- 2026-11-20 所有多行引用块加显式边界：--- begin <名称> (N lines) --- 与 --- end <名称> ---，块内仍每行缩进 4 空格；覆盖 text_reports 各命令与 change status 的 state/memory core 引用；说明段、文档、skill 与测试同步。不改 JSON。

## 决策

<!-- 重要取舍与确认：`- YYYY-MM-DD [HUMAN: 用户] 内容` 或 `- YYYY-MM-DD [MODEL: BE] 内容`。主体是实际作出决策的人或 Agent 角色，不是代写者。用 `loopspec state add --section decision` 追加。 -->
- 2026-11-20 [HUMAN: 用户（Desk 卡片）] 引用块边界：加 begin/end 标记与行数，保留 4 空格缩进；在 PR #19 分支上追加。
- 2026-11-20 [HUMAN: 用户（Desk 卡片）] 确认执行 Plan 001。

## 待解决问题

<!-- 跨 Plan 仍需追踪的问题；解决或移交时追加新条目并引用原问题。用 `loopspec state add --section open-question --scope change` 追加。 -->

## 参考

<!-- 相关 issue / PR / 讨论 / 产物入口及用途。用 `loopspec state add --section reference` 追加。 -->
- 2026-11-20 用户 2026-11-20 看了 memory show / node instructions 的文本样例后，在卡片中选择「加 begin/end 标记 + 行数，保留缩进」。基于 feat/text-output（PR #19）追加。

## Plan 记录

<!-- 引擎自动追加 Plan 沿革，请勿手工编辑，也勿在此段之后新增段落。 -->
- 2026-11-20T16:34:06+00:00 · Change quote-markers 归档前 memory 审阅 · 结论：none · 变化的 topic：无 · 备注：引用块格式规范已写入 AGENTS.md 与 text_format 文档并由 quoted_blocks 测试固定；流程上沿用已有 gate-workflow/dev-environment 经验，本次无新的可复用结论。
