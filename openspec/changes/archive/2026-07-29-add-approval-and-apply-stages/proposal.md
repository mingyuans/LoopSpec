## Why

内置 schema `secure-spec-driven` 目前止步于 `security` 门禁：`proposal → {specs, design} → tasks → security`。这意味着 loopspec 只覆盖"把计划写清楚"，**计划做完就结束了**——真正的实现（改代码、勾任务）完全在 loopspec 之外发生，于是：

1. **没有人类签核点。** 从提案到任务清单全部由 LLM 生成、由 LLM 自己做安全评审，人类唯一的介入方式是中途打断。计划一旦成型就直接落到"人类照着做/让 Agent 照着做"，缺一个"把结果摊开给人看、人明确点头"的关卡。
2. **实现阶段脱离循环。** OpenSpec 用 `apply:` 块 + `openspec instructions apply` 把实现阶段纳入工作流（读全部产物 → 逐条做任务 → 勾选 checkbox → 汇报进度），loopspec 没有对应环节，`tasks.md` 里的 checkbox 写完就没人再看，`isComplete`/`archive` 也只看"文件在不在"，一个任务都没勾的 change 照样能被判定完成并归档。
3. **实现中发现计划有问题时无路可走。** 这恰恰是 loopspec 相对 OpenSpec 的核心差异（gate + 回退 + `priorAttempts`）最该发挥作用的地方，却因为实现阶段不在图里而完全用不上。

本变更把实现阶段纳入内置 schema，并在它之前插入一个人类审批门禁，让 loopspec 的循环从"写计划"延伸到"落地实现"。

## What Changes

- **内置 schema 新增 `approval` 人类审批门禁**（`requires: [security]`）：LLM 必须先把该 change 到目前为止的全部产物（proposal / specs / design / tasks / security 结论）汇总成一份给人看的摘要，然后**通过宿主工具的交互式提问能力**（Claude Code 的 `AskUserQuestion`、其他工具的等价机制）请人类明确回答"按此计划执行"还是"需要调整"。人类点头 → 写 `approval/approved.md`（PASS）；人类要求调整 → 写 `approval/changes-requested.md`（FAIL），把调整要求逐条列成阻断项。FAIL 时 `on_fail.reset: [specs, design]`，回退闭环覆盖 `specs → design → tasks → security → approval → apply`，人类的意见会以 `priorAttempts` 的形式喂给重做的节点。**在拿不到真人回答的环境里（非交互、无提问能力），Agent 一律不得自行写 PASS**，宁可停在这里等人。
- **`approval` 的人类判定必须回写 `state.md`，且分工明确**：人类的**原话摘录**只写进 `approval` 的 pass/fail 产物（那里需要保真、且会随回退被归档留档）；`state.md` 只写**提炼后的信息**——`Decision Log` 记一条带轮次的判定要点，认可时把已签核的计划要点写进 `Frozen Decisions`，要求调整时把被否决的做法写进 `Rejected Options`、未定论的问题写进 `Open Questions`、并把 `Current Focus` 改写为"按人类第 N 轮意见重做"，`Artifact Notes` 记产物路径与结论。一律**追加不覆盖**：`state.md` 是唯一不随回退被归档的文件，是跨轮次连续可读的决策记忆。
- **`state.md` 里的每一条记录必须是自包含的、去指代的**：人类原话里的"这个/那个/它/上面说的/刚才那条"等指代词，回写 `state.md` 时 SHALL 全部替换成具体所指（具体能力名、文件路径、任务编号、需求名）。因为 `state.md` 会被后续多个节点在脱离当时对话上下文的情况下反复读取，保留指代词等于把记录写成不可解析的死文本。两份 `approval` 模板各含一个「state.md 回写记录」小节，让回写与否在产物里可审计。
- **内置 schema 新增 `apply` 实现门禁**（`requires: [approval]`）：参照 `.claude/skills/openspec-apply-change` 的实现，指令要求 LLM 读齐全部上游产物 → 逐条实现 `tasks.md` 中未勾选的任务 → 每完成一条立刻把 `- [ ]` 改成 `- [x]` → 跑测试 → 写实现报告 `apply/report.md`（PASS）。若实现过程中发现计划本身走不通（设计有硬伤、任务前提不成立），写 `apply/blocked.md`（FAIL）而不是硬凑，`on_fail.reset: [design]` 回退重做设计与任务；`max_retries: 2`（实现级返工代价高，早escalate 给人类）。
- **schema 节点新增可选 `tracks` 字段**：值为某个节点 `generates` 声明的具体产物路径（如 `tasks.md`），表示"本节点的进度由该文件里的 checkbox 追踪"。内置 schema 的 `apply` 节点声明 `tracks: tasks.md`。
- **`tracks` 带来一条完成性硬约束**：声明了 `tracks` 的节点，即使自身产物（或 gate 的 PASS 产物）已写出，只要被追踪文件不存在、其中没有任何 checkbox、或还有未勾选的 checkbox，该节点一律**不判定为 `done`**。这堵住了"写完一份实现报告就宣称实现完成"的漏洞，也让 `isComplete` / `archive` 对未完成的实现不再放行。
- **`loopspec instructions` 响应新增两个字段**：`contextFiles`（节点 ID → 该节点当前实际存在的产物绝对路径列表，覆盖图中全部节点而非仅直接依赖，对应 OpenSpec apply 指令的 `contextFiles`，让 `approval`/`apply` 这种"要读齐全部产物"的节点不必靠猜文件名）与 `taskProgress`（仅当节点声明了 `tracks` 时出现：被追踪文件路径、`total`/`complete`/`remaining` 与逐条任务的 `id`/`description`/`done`）。
- **`loopspec status` 的节点条目**：对声明了 `tracks` 的节点附带 `taskProgress` 摘要（`total`/`complete`/`remaining`，不含逐条任务列表），让驱动循环的 Agent 只调一次 `status` 就能报出"3/12 tasks complete"。
- **`loopspec-continue` skill/命令正文补充说明**：`instructions` 返回的指令不一定是"写一份产物文件"，也可能要求向人类提问确认（审批类节点）或直接改动代码库（实现类节点），Agent 应按指令正文行事，而不是一律只写文件。正文保持 schema 无关，不硬编码 `approval`/`apply` 这两个节点名。

## Capabilities

### New Capabilities
- `builtin-schema`: 内置 `secure-spec-driven` schema 的阶段图与各阶段语义契约——`proposal → {specs, design} → tasks → security → approval → apply` 的节点/依赖/产物路径约定、`approval` 人类审批门禁的交互要求、"禁止自行签核"红线与人类判定回写 `state.md` 的规则、`apply` 实现门禁的实现循环与 `tracks: tasks.md` 约定、两个新门禁的 `on_fail.reset`/`max_retries` 回退策略。

### Modified Capabilities
- `workflow-schema`: 新增节点可选字段 `tracks` 及其校验规则（安全相对路径、非 glob、必须等于某个节点声明的 `generates` 且该节点必须是本节点的祖先）。
- `artifact-state`: 新增"声明 `tracks` 的节点必须被追踪文件的 checkbox 全部勾选才判 `done`"的完成性推导规则，以及 checkbox 解析规则。
- `loopspec-cli`: `loopspec instructions` 的响应契约新增 `contextFiles` 与 `taskProgress` 字段；`loopspec status` 的节点条目对声明 `tracks` 的节点新增 `taskProgress` 摘要。
- `change-memory`: 新增"以人类回答为判定依据的节点必须把人类结论追加到 `state.md`"的留痕规则（写入哪些小节、轮次编号来源、原话归产物而 `state.md` 只记提炼信息、条目必须去指代且自包含、追加不覆盖、留痕不参与状态判定）。
- `lpsx-skills`: `loopspec-continue` 模板正文需说明节点指令可能要求人类交互确认或代码实现，不止于写产物文件。

## Impact

- `schemas/secure-spec-driven/`：`schema.yaml` 新增 `approval`/`apply` 两个 gate 节点；新增 `instructions/approval.md`、`instructions/apply.md`；新增 `templates/approval-approved.md`、`templates/approval-changes-requested.md`、`templates/apply-report.md`、`templates/apply-blocked.md`。该目录通过 `[tool.hatch.build.targets.wheel.force-include]` 打进 wheel，源码检出下 `_builtin_schemas_source()` 直接回落到仓库根 `schemas/`，改完即生效，无需重装。
- `state.md` 回写完全落在指令与模板层（`instructions/approval.md` + 两份 approval 模板），不新增引擎代码：引擎按既有设计不解析 `state.md`、不用它驱动状态判定。
- `src/loopspec/models.py`：`NodeSpec` 新增 `tracks` 字段。
- `src/loopspec/schema_loader.py`：新增 `tracks` 的语义校验。
- `src/loopspec/`：新增 checkbox 解析模块（如 `task_tracking.py`）。
- `src/loopspec/state.py`：`compute_states` 的完成性判定接入 `tracks` 约束。
- `src/loopspec/instructions.py`：响应新增 `contextFiles`/`taskProgress`。
- `src/loopspec/cli.py`：`status` 的节点条目新增 `taskProgress` 摘要。
- `src/loopspec/skill_templates.py`：`_CONTINUE_BODY` 文案调整。
- `README.md`：内置 schema 节点图描述从 `proposal → {specs, design} → tasks → security` 更新为含 `approval`/`apply` 的完整链路。
- **对既有 change 的影响（破坏性）**：内置 schema 多了两个节点，用旧 schema 拷贝创建但尚未完成的 change（例如本仓库 `loopspec/changes/improve-init-display`）在刷新 `loopspec/schemas/` 拷贝后会多出两个待完成节点，`isComplete` 由 `true` 变 `false`。每个 change 的 schema 由 `.workflow.yaml` 记录、从 workflow home 的 `schemas/` 目录加载，因此**不刷新本地拷贝就不受影响**；是否刷新由使用者自行决定。
- 不影响 `gate-rollback`、`change-memory`、`change-archiving`、`tool-scaffolding` 的既有需求；`tracks` 是可选字段，未声明 `tracks` 的 schema 与节点行为完全不变。
