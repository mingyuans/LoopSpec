# 需求记录

需求背景、跨 Plan 的决策与更替原因。
人与 LLM 可直接编辑；`loopspec change status` 原样输出全文，引擎不解析。

## 背景

用户希望评估：为 LoopSpec 内置「memory 管理」能力——在 loopspec 工作目录下设置明确的 `memory/` 目录，跨 Change 沉淀常用规则（团队约定、踩坑、命令、评审偏好等），让后续 Change 的流程越跑越顺。

现状：LoopSpec 的知识只存在于单个 Change（state.md、各节点产物）与 archive 中，跨 Change 没有一等公民的沉淀位置；规则只能散落在 Fragment instruction、config 或 agent 自身记忆里，新 Change 无法自动继承前序经验。

## 目标 / 非目标

目标：
- 在 workflow home 下提供 `memory/{topic}.md`：普通 Markdown，按 topic 组织，跨 Change 沉淀可复用经验。
- 引擎只负责 topic 发现、合法 topic/路径、安全 IO、索引与有界输出；LLM 经内置 skill 负责筛选证据、命名 topic、创建/合并/更新/整理。
- 读侧：core 存在时默认内联（8 KiB 展示上限），其他 topic 给索引、按需读全文；写侧：new/continue/archive 三个时机的维护流程。
- 输出 proposal、design、tasks，随后按 design 做后端（CLI）实现、测试、安全与代码审查。

非目标：
- 不处理 agent 个人长期记忆（如 Claude/Desk memory）的同步。
- 引擎不调用模型、不做语义分类、不维护条目数据库；无 fragments 映射、无单条 frontmatter/确认人/状态/归档模型。

## 关键决策

<!-- 每条一行：- YYYY-MM-DD（确认人）：决策内容；理由。
只追加；推翻旧决策时新增一条并注明取代哪条。 -->
- 2026-11-08（用户）：Plan 在 design 之后包含 be implement（backend-implementation）；理由：用户明确要求评估后继续实现，取代此前「只评估」的草案。
- 2026-11-08（用户，经 General-Codex 转达）：memory 按 topic 存为 `loopspec/memory/{topic}.md`，由 LLM 自主判断 topic 并创建/更新，框架只支持该目录结构；常规有证据的写入由 LLM 直接完成并报告 diff，不再逐条人确认；取代 proposal/design 初稿中的「一条一个文件、`memory add/archive`、`confirmed_by`、人确认后写入」设计（初稿尚未实现，无代码回退）。
- 2026-11-08（用户）：采用“memory 记录知识与原因，rules 规定必须怎样做”的边界定义，按内容含义分流；用户明确要求的“以后必须怎样做”单独记入 `memory/rule.md`（保留名，仅在用户明确表态时写入，不得推断；效力低于用户当前指令、安全规则与门禁），经验中发现的规则候选只提案、不改 Fragment/skill/config；topic 条目字段由“做法”改为“结论/建议”。
- 2026-11-08（用户）：方案中不单独处理 rules，删除所有 rules 相关说明（含 `memory/rule.md`、memory 与 rules 的边界定义、规则候选与晋升、一次性例外/长期修改的区分）；用户直接给出的约定按普通 memory 条目记入 topic，标注“用户确认”；取代此前同日采用“知识与约束边界、`rule.md`”的决策（相关设计只存在于未实现的文档，无代码回退）。

## 参考

<!-- 相关 issue / PR / 已归档 Change。 -->

## Plan 记录

<!-- 引擎在此之后追加 Plan 归档事件；LLM 可在事件行下补充更替原因。 -->
