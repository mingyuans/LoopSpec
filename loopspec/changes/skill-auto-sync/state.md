# 需求记录

跨 Plan 的背景、边界、重要决策与待解决问题；引擎在末尾追加 Plan 记录。
优先用 `loopspec state add` 追加；`loopspec change status` 原样输出全文，引擎不解析内容。

## 背景

<!-- 问题来源、现状与触发原因。用 `loopspec state add --section background` 追加。 -->
- 2026-11-19 loopspec CLI 升级后内置 skill 文本会变（例如归档改为两段式），但项目中由 loopspec init 生成的 skill/command 文件只在重新 init 时更新，常常停留在旧版本，导致 agent 按旧流程调用新 CLI 而出错。skill 文件没有版本标记，scaffold 每次 init 全量覆盖。

## 目标与边界

<!-- 预期结果、范围与明确不做的事。用 `loopspec state add --section goals` 追加。 -->
- 2026-11-19 loopspec CLI 执行时检查项目中已有的 loopspec skill/command 文件是否与当前 CLI 内置版本一致，不一致时自动更新；项目有几个就更新几个。非目标：不为未配置的 AI 工具新建文件；不改 hook 配置。

## 决策

<!-- 重要取舍与确认：`- YYYY-MM-DD [HUMAN: 用户] 内容` 或 `- YYYY-MM-DD [MODEL: BE] 内容`。主体是实际作出决策的人或 Agent 角色，不是代写者。用 `loopspec state add --section decision` 追加。 -->
- 2026-11-19 [HUMAN: xq.yan] Plan 001 确认执行；对已配置的 AI 工具，缺失的 loopspec skill/command 也一并补上；loopspec 生成的 skill/command 文件由 CLI 固定排除出交付 Diff。
- 2026-11-19 [MODEL: ENG-claude-remote] Plan 001 design：同步只写项目根内文件（Codex 的全局 prompts 不同步）；通过 HOME 选项回调触发；提供 LOOPSPEC_SKILL_SYNC=0 供测试隔离与紧急关闭。
- 2026-11-19 [MODEL: ENG-claude-remote] Plan 001 design：Codex 审阅 6 条全部采纳（回调返回原值、项目根与 init 默认一致、init 保留全局 Codex prompts、fd 逐级 O_NOFOLLOW 写入、Diff 只排除内容与模板一致的普通文件、去掉关闭开关），替代此前「提供 LOOPSPEC_SKILL_SYNC」的决定。

## 待解决问题

<!-- 跨 Plan 仍需追踪的问题；解决或移交时追加新条目并引用原问题。用 `loopspec state add --section open-question --scope change` 追加。 -->

## 参考

<!-- 相关 issue / PR / 讨论 / 产物入口及用途。用 `loopspec state add --section reference` 追加。 -->
- 2026-11-19 用户原始需求（2026-11-19）：loopspec cli 版本更新之后有变更 skills，但项目已有的 skills 会存在没更新的情况，导致使用异常。增加机制，loopspec cli 执行的时候，检查项目 skill 与 cli 版本内置 skill 版本是否一致，如果不一致，自动更新。项目有几个 skill 就都更新几个。相关代码：src/loopspec/scaffold.py、skill_templates.py、tool_registry.py。
- 2026-11-19 No relevant memory（memory topics: agent-step-enforcement、archive-behavior、gate-workflow、safe-deletion 与本需求无关）

## Plan 记录

<!-- 引擎自动追加 Plan 沿革，请勿手工编辑，也勿在此段之后新增段落。 -->
