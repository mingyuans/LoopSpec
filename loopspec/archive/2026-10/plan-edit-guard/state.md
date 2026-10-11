# 需求记录

需求背景、跨 Plan 的决策与更替原因。
人与 LLM 可直接编辑；`loopspec change status` 原样输出全文，引擎不解析。

## 背景

Plan 确认（approve）后，LLM 仍可以用编辑类工具直接改写 `plans/<NNN>/plan.yaml`，从而绕过人对 digest 的确认、影响整个流程。现有 `read_plan` 的 spec 摘要校验只能在读取时发现篡改，而 LLM 可以同时重算 digest，或改 meta.status。

期望：流程有变更时走 CLI（经人确认的修订 `plan approve -f`，或归档后重新 plan create），而不是直接编辑文件。

## 目标 / 非目标

目标：
- 新增 `loopspec hook pre-tool-use`，读取 Claude Code PreToolUse hook 的 JSON 输入；目标是已确认 Plan 的 `plan.yaml` 时阻止，并提示 LLM 通过 CLI 修订，或归档后重新起 Plan。
- 覆盖 Edit / Write / MultiEdit / NotebookEdit，以及 Bash 中对该路径的写操作（启发式）。
- `loopspec init` 为 Claude Code 写入 `.claude/settings.json` 的 PreToolUse 配置（合并，不覆盖用户已有配置）。

非目标：
- 不限制 CLI 对 plan.yaml 的写入（`plan approve -f` 修订、`plan archive` 等保持不变）。
- 不保护 request.yaml、.gates/、.gate-rounds/、.workflow.yaml、state.md、artifacts/。
- 不为 Claude Code、Codex 以外的 AI 工具提供 hook。

## 关键决策

<!-- 每条一行：- YYYY-MM-DD（确认人）：决策内容；理由。
只追加；推翻旧决策时新增一条并注明取代哪条。 -->

- 2026-10-11（用户）：保留经人确认的 CLI 修订通道，只拦 LLM 直接编辑；理由：MODEL 通过 CLI 修改 plan.yaml 是可以的。
- 2026-10-11（用户）：保护范围只限已确认 Plan 的 plan.yaml。
- 2026-10-11（用户）：交付形态为 CLI 子命令 + init 写 Claude Code hook 配置，Bash 做启发式拦截。
- 2026-10-11（用户）：同时支持 Codex 的 hook（`.codex/hooks.json`，`apply_patch` + `Bash`）；理由：Codex 有同构的 PreToolUse 机制。
- 2026-10-11（用户）：Bash 检测保持现有实现（分词、cd 跟踪、通配符、只读白名单），不改为“出现 plan.yaml 字样即拒绝”的简化方案。
- 2026-10-11（用户）：hook 输入超过 64 MiB（无法解析）时放行而非拒绝；理由：不影响正常 tool 调用。
- 2026-10-11（用户）：原则改为“能检测到就禁，检测不了就放行”：超长、超时、分析异常、plan.yaml 无法读取/解析时一律放行；取代 security 返工中的 fail closed 做法；理由：不影响正常 tool 调用，digest 校验兜底。

## 参考

<!-- 相关 issue / PR / 已归档 Change。 -->

## Plan 记录

<!-- 引擎在此之后追加 Plan 归档事件；LLM 可在事件行下补充更替原因。 -->
