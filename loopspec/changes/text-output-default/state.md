# 需求记录

跨 Plan 的背景、边界、重要决策与待解决问题；引擎在末尾追加 Plan 记录。
优先用 `loopspec state add` 追加；`loopspec change status` 原样输出全文，引擎不解析内容。

## 背景

<!-- 问题来源、现状与触发原因。用 `loopspec state add --section background` 追加。 -->
- 2026-11-20 loopspec CLI 的调用方主要是 MODEL。目前只有 change status、graph（以及 init/update/version）默认输出文本，其余工作流命令（node instructions、plan show 等）只输出 JSON：大段 Markdown（instruction、template）被转义进一行字符串，模型阅读困难。

## 目标与边界

<!-- 预期结果、范围与明确不做的事。用 `loopspec state add --section goals` 追加。 -->
- 2026-11-20 所有 loopspec 命令默认输出文本模式（样式参考 change status：=== SECTION === 分节、说明段、key: value 字段、不可信文本缩进引用），并统一提供 --json 切回原 JSON（JSON 结构不变）。错误在文本模式下按 === ERROR === 输出。AGENTS.md 增加规范：loopspec 命令都提供文本与 JSON 两种格式，默认文本，新增命令须遵守。同步更新 skill、文档与测试。不做：hook pre-tool-use（Claude/Codex hook 协议要求 JSON，保持不变）；不改变 JSON 字段。

## 决策

<!-- 重要取舍与确认：`- YYYY-MM-DD [HUMAN: 用户] 内容` 或 `- YYYY-MM-DD [MODEL: BE] 内容`。主体是实际作出决策的人或 Agent 角色，不是代写者。用 `loopspec state add --section decision` 追加。 -->
- 2026-11-20 [HUMAN: 用户（Desk 卡片）] 确认执行 Plan 001（requirements→design→be→qa→assurance）。
- 2026-11-20 [HUMAN: 用户（Desk 卡片）] 文本实现方式：每个命令手写渲染器（不采用通用渲染器），可读性优先。

## 待解决问题

<!-- 跨 Plan 仍需追踪的问题；解决或移交时追加新条目并引用原问题。用 `loopspec state add --section open-question --scope change` 追加。 -->

## 参考

<!-- 相关 issue / PR / 讨论 / 产物入口及用途。用 `loopspec state add --section reference` 追加。 -->
- 2026-11-20 用户原话（2026-11-20）：新开 worktree 完成这个需求：loopspec 命令都默认输出文本模式，样式参考 status，另外提供 --json 来切回 JSON。同时 Agents.md 加这个说明，loopspec 命令都提供文本模式和 JSON 两种返回格式，默认文本。因为 loopspec cli 是 MODEL 在调用，需要按 MODEL 更容易理解的方式来。
- 2026-11-20 Memory：gate-workflow（先 commit 再 assurance；assurance 配 on_fail）、skill-files（改 skill 只改 builtin/skills 源文件，副本由 CLI 同步）均适用并已核对；agent-step-enforcement 与本需求无直接关系。现有实现参考 src/loopspec/status_report.py（文本契约：无 ANSI/Markdown、sanitize、单一数据源、key 集合测试）。

## Plan 记录

<!-- 引擎自动追加 Plan 沿革，请勿手工编辑，也勿在此段之后新增段落。 -->
