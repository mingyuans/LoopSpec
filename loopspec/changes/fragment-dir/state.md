# 需求记录

跨 Plan 的背景、边界、重要决策与待解决问题；引擎在末尾追加 Plan 记录。
优先用 `loopspec state add` 追加；`loopspec change status` 原样输出全文，引擎不解析内容。

## 背景

<!-- 问题来源、现状与触发原因。用 `loopspec state add --section background` 追加。 -->
- 2026-11-20 registry 模式下 fragment 定义存放在全局快照（~/.loopspec/registry/...），项目内没有 loopspec/fragments/。fragment 指令里引用的辅助文件（references/、scripts/，或只写文件名如 doc-writing-rules.md）无法定位：node instructions 只给出指令正文，fragment 字段是实例 id（如 qa），不给出 fragment 名与目录。实测 aftership-channels 快照 7b6cc1b：42 个文件 83 处引用。

## 目标与边界

<!-- 预期结果、范围与明确不做的事。用 `loopspec state add --section goals` 追加。 -->
- 2026-11-20 node instructions 输出 fragment 的绝对路径：新增 fragmentName、fragmentDir（registry 模式指向已校验的全局快照目录，本地模式指向 workflow home 下的 fragments/<name>），以及 instructionPath/templatePath 的绝对路径；文本报告说明指令中的相对引用按 fragmentDir 解析；skill 与文档同步。不做：改写指令中的路径前缀、映射表、修改上游 registry 内容。

## 决策

<!-- 重要取舍与确认：`- YYYY-MM-DD [HUMAN: 用户] 内容` 或 `- YYYY-MM-DD [MODEL: BE] 内容`。主体是实际作出决策的人或 Agent 角色，不是代写者。用 `loopspec state add --section decision` 追加。 -->
- 2026-11-20 [HUMAN: 用户（Desk 对话）] fragment 辅助文件路径问题的修复方案：在 node instructions 中带上 fragment 的绝对路径，不采用前缀改写/映射表或逐 fragment 链接。
- 2026-11-20 [HUMAN: 用户（Desk 卡片）] 确认执行 Plan 001（requirements→design→be→qa→assurance）。

## 待解决问题

<!-- 跨 Plan 仍需追踪的问题；解决或移交时追加新条目并引用原问题。用 `loopspec state add --section open-question --scope change` 追加。 -->

## 参考

<!-- 相关 issue / PR / 讨论 / 产物入口及用途。用 `loopspec state add --section reference` 追加。 -->
- 2026-11-20 用户原话（2026-11-20）：「fragment 辅助文件路径修复方案：就还是 node 命令里边，带上 framgent 的绝对路径」。此前用户提议：loopspec node 命令同时给出 node instruction 的绝对路径，方便 instruction 里有 references 时 MODEL 知道具体路径。
- 2026-11-20 Memory：dev-environment（仓库内用 uv run loopspec、只格式化改动文件、pytest -n 2）、gate-workflow（先 commit 再 assurance；PASS 后改代码需重跑 Gate；LLM E2E 期间不改代码）、skill-files 适用。本分支基于 feat/text-output（PR #19 未合并），PR 依赖 #19。

## Plan 记录

<!-- 引擎自动追加 Plan 沿革，请勿手工编辑，也勿在此段之后新增段落。 -->
