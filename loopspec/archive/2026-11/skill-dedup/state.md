# 需求记录

跨 Plan 的背景、边界、重要决策与待解决问题；引擎在末尾追加 Plan 记录。
优先用 `loopspec state add` 追加；`loopspec change status` 原样输出全文，引擎不解析内容。

## 背景

<!-- 问题来源、现状与触发原因。用 `loopspec state add --section background` 追加。 -->
- 2026-11-20 所有命令改为默认文本输出后，每节都带说明段（引用块读法、fragmentDir、resolvedOutputPath、STATE PROTOCOL 的命令与规则、NEXT STEPS 用法、归档 memory 审阅指引等）。5 个 skill（new/continue/archive/bulk-archive/update-registry，共约 4567 词）仍逐条复述这些读法，与命令输出重复。

## 目标与边界

<!-- 预期结果、范围与明确不做的事。用 `loopspec state add --section goals` 追加。 -->
- 2026-11-20 审视全部 5 个 skill，删除命令输出已说明的内容（读法、字段位置、命令格式），保留安全红线与流程语义（人工确认、不代替人表态、HUMAN 决策适用范围、taskProgress 一次一项、并行 sub agent 规则、不手改 plan.yaml 等）。不改 CLI 行为与输出；必要时补强输出说明以承接被删内容。make test-llm 必须通过。

## 决策

<!-- 重要取舍与确认：`- YYYY-MM-DD [HUMAN: 用户] 内容` 或 `- YYYY-MM-DD [MODEL: BE] 内容`。主体是实际作出决策的人或 Agent 角色，不是代写者。用 `loopspec state add --section decision` 追加。 -->
- 2026-11-20 [HUMAN: 用户（Desk 卡片）] skill 去重范围：审视全部 5 个 skill，只删命令输出已说明的内容，保留红线与流程语义。
- 2026-11-20 [HUMAN: 用户（Desk 卡片）] 确认执行 Plan 001。

## 待解决问题

<!-- 跨 Plan 仍需追踪的问题；解决或移交时追加新条目并引用原问题。用 `loopspec state add --section open-question --scope change` 追加。 -->

## 参考

<!-- 相关 issue / PR / 讨论 / 产物入口及用途。用 `loopspec state add --section reference` 追加。 -->
- 2026-11-20 用户 2026-11-20：现在命令都是文本输出，skill 是不是不用写那么多？比如 continue 第 2 步会不会跟命令的文本输出重复？；卡片选择「审视全部 5 个 skill 去重」。

## Plan 记录

<!-- 引擎自动追加 Plan 沿革，请勿手工编辑，也勿在此段之后新增段落。 -->
- 2026-11-20T17:01:14+00:00 · Change skill-dedup 归档前 memory 审阅 · 结论：updated · 变化的 topic：skill-files · 备注：skill-files 增加 skill 与命令输出分工的约定（读法放输出说明段，skill 只写流程与红线；共享 memory 维护流程例外）。
