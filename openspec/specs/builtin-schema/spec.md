# builtin-schema Specification

## Purpose
内置 `secure-spec-driven` schema 的阶段图与各阶段语义契约：节点/依赖/产物路径约定、人类审批门禁与实现门禁的行为要求及回退策略。

## Requirements
### Requirement: 内置 secure-spec-driven schema 的阶段图
内置 schema `secure-spec-driven` SHALL 定义 7 个节点，构成从"写计划"到"落地实现"的完整链路：

| 节点 | 类型 | requires | 产物 |
| --- | --- | --- | --- |
| `proposal` | 普通 | — | `proposal.md` |
| `specs` | 普通 | `proposal` | `specs/**/*.md` |
| `design` | 普通 | `proposal` | `design.md` |
| `tasks` | 普通 | `specs`, `design` | `tasks.md` |
| `security` | gate | `tasks` | `security/pass.md` / `security/fail.md` |
| `approval` | gate | `security` | `approval/approved.md` / `approval/changes-requested.md` |
| `apply` | gate | `approval` | `apply/report.md` / `apply/blocked.md` |

`apply` 节点 SHALL 声明 `tracks: tasks.md`，即其完成度由 `tasks.md` 中的 checkbox 追踪。每个节点 SHALL 通过 `instruction: {file: <node>.md}` 从 schema 的 `instructions/` 目录加载指令，每个 gate SHALL 在 `templates/` 目录下提供 pass 与 fail 两份模板。原有的 `proposal → {specs, design} → tasks → security` 部分（含 `security` 的 `on_fail.reset: [design]`、`max_retries: 3`、`on_exhausted: escalate`）SHALL 保持不变。

#### Scenario: 内置 schema 校验通过且拓扑序含新阶段
- **WHEN** 执行 `loopspec schemas validate secure-spec-driven --json`
- **THEN** 返回 `valid: true`，`buildOrder` 包含全部 7 个节点，且 `approval` 排在 `security` 之后、`apply` 排在 `approval` 之后

#### Scenario: 新建 change 的首个待办仍是 proposal
- **WHEN** 用 `secure-spec-driven` 创建一个新 change 并执行 `loopspec status`
- **THEN** `nextSteps` 指向 `proposal` 节点，`approval` 与 `apply` 均为 `blocked`

#### Scenario: security PASS 后解锁 approval 而非 apply
- **WHEN** `security/pass.md` 已写出，`approval` 的产物尚未写出
- **THEN** `approval` 状态为 `ready`，`apply` 状态为 `blocked` 且 `missingDeps` 含 `approval`

#### Scenario: 全链路完成才算 change 完成
- **WHEN** `security` 与 `approval` 均 PASS、`apply/report.md` 已写出且 `tasks.md` 的 checkbox 全部勾选
- **THEN** `isComplete` 为 `true`，该 change 可被 `loopspec archive` 归档

### Requirement: approval 人类审批门禁
`approval` 门禁 SHALL 要求 LLM 在写出任何判定产物之前，先把该 change 到目前为止的全部产物（`proposal.md`、`specs/**/*.md`、`design.md`、`tasks.md`、`security/pass.md`）汇总成一份面向人类的摘要——至少覆盖：本次改动要解决什么、将新增/修改哪些能力、关键技术决策与取舍、任务清单的规模与顺序、安全评审的结论与遗留风险——并通过宿主工具的交互式提问能力（Claude Code 的 `AskUserQuestion` 工具，或其他工具的等价机制）请人类明确回答"按此计划执行"还是"需要调整"。

该门禁 SHALL 二选一写入：人类明确认可 → 写 `approval/approved.md`（PASS）；人类要求调整 → 写 `approval/changes-requested.md`（FAIL），并把人类提出的每项调整要求写成"阻断问题"列表中一条自包含、可执行的条目。

`approval` SHALL 配置 `on_fail.reset: [specs, design]`、`max_retries: 5`、`on_exhausted: escalate`：人类的意见往往同时触及"做什么"（specs）与"怎么做"（design），因此回退闭环覆盖 `specs`/`design`/`tasks`/`security`/`approval`/`apply`，而 `proposal`（为什么做）保留不动。

指令 SHALL 明确规定一条红线：**在无法取得真人回答的环境下（无交互提问能力、非交互式运行、人类未回答），Agent 一律不得自行写出 PASS 产物**，而应停在该节点等待人类，因为该门禁的唯一判定依据是真人的回答。

#### Scenario: 人类认可后写 PASS
- **WHEN** LLM 汇总全部产物、向人类提问，人类回答"按此计划执行"
- **THEN** 仅写出 `approval/approved.md`，`approval` 状态变为 `done`，`apply` 变为 `ready`

#### Scenario: 人类要求调整后写 FAIL
- **WHEN** 人类回答"需要调整"并给出具体意见
- **THEN** 仅写出 `approval/changes-requested.md`，其中每项调整意见是一条独立的阻断问题条目；`approval` 状态变为 `failed`，`pendingRollback` 指向 `approval`

#### Scenario: 回退闭环覆盖 specs 与 design
- **WHEN** `approval` FAIL 后执行 `loopspec rollback`
- **THEN** 归档的 reset 闭环为 `specs`/`design`/`tasks`/`security`/`approval`/`apply` 中已存在的产物，`proposal.md` 不被归档

#### Scenario: 重做节点能看到人类的调整意见
- **WHEN** `approval` FAIL 回退后，对 `specs` 或 `design` 调用 `loopspec instructions`
- **THEN** 响应的 `priorAttempts` 含该轮 `approval` 的 `verdict`/`summary`/`blockingIssues`，即人类提出的调整意见

#### Scenario: 无法取得真人回答时不得自行签核
- **WHEN** 运行环境没有向人类提问的能力，或人类尚未回答
- **THEN** 既不写 `approval/approved.md` 也不写 `approval/changes-requested.md`，`approval` 保持 `ready` 等待人类介入

#### Scenario: 人类连续 5 轮要求调整
- **WHEN** `approval` 已发生 5 次回退且再次 FAIL
- **THEN** `approval` 状态为 `exhausted`，`nextSteps` 提示已达重试上限、需人工介入并建议查看 `loopspec history`

### Requirement: approval 的人类判定必须回写 state.md
`approval` 门禁的指令 SHALL 要求 LLM 在写出判定产物之后，把人类的判定回写到该 change 的 `state.md`，具体规则如下：

- **原话与提炼信息分工**：人类的**原话摘录**只写进 `approval` 的 pass/fail 产物（`approval/approved.md` 或 `approval/changes-requested.md`）；`state.md` SHALL 只记录提炼后的信息，不搬运原话。
- `Decision Log` SHALL 追加一条带轮次的判定记录，含判定结果（认可 / 要求调整）、提炼后的判定要点与该判定对应的产物路径（原话可在该产物中查阅）；轮次 N SHALL 由 `instructions` 响应中 `priorAttempts` 里属于本 gate 的条目数 + 1 推导。
- 人类认可时，`Frozen Decisions` SHALL 追加人类已签核的计划要点，并注明后续节点不得擅自变更这些要点（确需变更应重新走一轮 `approval`）。
- 人类要求调整时：`Rejected Options` SHALL 追加人类明确否决的做法；`Open Questions` SHALL 追加人类提出但尚无定论的问题；`Current Focus` SHALL 被改写为"按人类第 N 轮意见重做 `specs`/`design`"。
- `Artifact Notes` SHALL 追加本次 `approval` 产物的路径与结论。
- **每条记录 SHALL 自包含、去指代**：人类原话中的指代词（"这个"、"那个"、"它"、"上面说的"、"刚才那条"、"这里"）SHALL 在回写时全部替换为具体所指——具体能力名、文件路径、任务编号、需求名或决策编号。例如人类说"这个先不做，那个要补测试"，`state.md` SHALL 写成"暂不实现 `<具体能力名>`（原任务 3.2）；为 `<具体模块路径>` 补测试"。任何一条记录脱离当时的对话上下文单独阅读时仍应可解析，因为 `state.md` 会被后续多个节点在没有该对话上下文的情况下反复读取。
- 回写 SHALL 一律**追加**，不得删除或改写历史条目：`state.md` 不属于任何节点的产物、回退时不会被归档，因此它是跨多轮审批唯一连续可读的决策记忆。
- 若 `state.md` 缺失（`instructions` 响应的 `warnings` 含 `state_missing`），SHALL 先按标准小节结构重建该文件再追加本轮记录。
- 该回写 SHALL 仅作为记录存在，不改变任何状态判定：`approval` 的判定依据永远只是 pass/fail 产物文件本身。

两份 `approval` 模板 SHALL 各含一个「state.md 回写记录」小节，列出本次追加到了哪些小节，使"是否回写"可从产物本身审计。

#### Scenario: 人类认可后的回写
- **WHEN** 人类回答"按此计划执行"，LLM 写出 `approval/approved.md`
- **THEN** `state.md` 的 `Decision Log` 新增一条含轮次、判定结果、提炼后判定要点与产物路径的记录，`Frozen Decisions` 新增人类已签核的计划要点，`Artifact Notes` 新增该产物路径与结论

#### Scenario: 人类要求调整后的回写
- **WHEN** 人类回答"需要调整"并给出意见，LLM 写出 `approval/changes-requested.md`
- **THEN** `state.md` 的 `Decision Log` 新增该轮判定记录（提炼要点 + 产物路径），`Rejected Options` 新增被否决的做法，`Open Questions` 新增尚无定论的问题，`Current Focus` 被改写为按该轮人类意见重做 `specs`/`design`

#### Scenario: 原话留在产物、state.md 只记提炼信息
- **WHEN** 人类给出一段口语化的审批意见，LLM 完成判定与回写
- **THEN** 人类的原话摘录出现在 `approval/approved.md` 或 `approval/changes-requested.md` 中，而 `state.md` 中只有提炼后的要点与指向该产物的路径，不重复搬运原话

#### Scenario: 指代词被替换为具体所指
- **WHEN** 人类原话为"这个先不做，那个要补测试"
- **THEN** 写入 `state.md` 的条目把"这个"/"那个"替换为具体的能力名、任务编号或文件路径，脱离对话上下文单独阅读时仍可解析

#### Scenario: 多轮审批的记录累积
- **WHEN** 同一 change 的 `approval` 经历第二轮判定
- **THEN** `state.md` 中第一轮的记录仍完整保留，第二轮记录以轮次 2 追加在其后，历史条目未被删改

#### Scenario: 回写记录在产物中可审计
- **WHEN** 查看写出的 `approval/approved.md` 或 `approval/changes-requested.md`
- **THEN** 其中的「state.md 回写记录」小节列出了本次追加到 `state.md` 的小节

#### Scenario: state.md 缺失时先重建
- **WHEN** `approval` 节点的 `instructions` 响应 `warnings` 含 `state_missing`
- **THEN** LLM 先按标准小节结构重建 `state.md`，再追加本轮判定记录，判定产物照常写出

#### Scenario: 回写不影响状态判定
- **WHEN** `state.md` 中已记录"人类已认可"，但 `approval/approved.md` 尚未写出（或已被回退归档）
- **THEN** `approval` 状态仍按产物文件推导为 `ready`，不因 `state.md` 的记录而变为 `done`

### Requirement: apply 实现门禁
`apply` 门禁 SHALL 要求 LLM 按以下循环把 `tasks.md` 落地为真实代码改动：

1. 读齐 `instructions` 响应 `contextFiles` 中列出的全部上游产物文件（proposal / specs / design / tasks / security / approval），不靠猜测文件名。
2. 依据 `taskProgress` 找出 `tasks.md` 中尚未勾选的任务，按声明顺序逐条实现；每条任务只做该任务要求的最小改动。
3. 每完成一条任务，立刻把 `tasks.md` 中对应的 `- [ ]` 改成 `- [x]`，不攒到最后一次性勾选。
4. 按项目约定运行测试/校验（本仓库为 `make test`、`make lint`），并把真实结果（含失败）写进报告。
5. 全部任务勾选完成后，写实现报告 `apply/report.md`（PASS），内容 SHALL 包含：实现了哪些任务、改动了哪些文件、测试/校验的实际执行结果、与原设计的偏离及原因（如有）。

若实现过程中发现计划本身走不通（设计存在硬伤、任务前提不成立、需求存在矛盾），LLM SHALL 写 `apply/blocked.md`（FAIL）而不是强行凑出一个实现；FAIL 产物 SHALL 逐条列出阻断问题，并**记录此前已经落到代码库里的改动**（因为 loopspec 的回退只归档 change 目录内的产物，不会撤销任何代码改动），供重做设计与任务时参考。

`apply` SHALL 配置 `on_fail.reset: [design]`、`max_retries: 2`、`on_exhausted: escalate`：实现级返工代价高，重做两轮仍无法落地时应尽早升级给人类，而不是继续自动循环。

#### Scenario: 逐条实现并即时勾选
- **WHEN** `apply` 为 `ready`，`tasks.md` 中有未勾选任务
- **THEN** LLM 逐条实现任务并在每条完成后立即把该行改为 `- [x]`，`loopspec status` 中 `apply` 的 `taskProgress.complete` 随之递增

#### Scenario: 全部任务完成后写报告
- **WHEN** `tasks.md` 全部 checkbox 已勾选且测试已实际执行
- **THEN** 写出 `apply/report.md`，其中含改动文件清单与测试的真实执行结果，`apply` 状态变为 `done`

#### Scenario: 报告已写但仍有未勾选任务
- **WHEN** `apply/report.md` 已存在，但 `tasks.md` 中仍有 `- [ ]` 未勾选
- **THEN** `apply` 状态不为 `done`（为 `ready`），`isComplete` 为 `false`，`archive` 拒绝归档

#### Scenario: 实现发现计划走不通
- **WHEN** LLM 在实现中发现设计有硬伤，无法按计划完成任务
- **THEN** 写出 `apply/blocked.md`（不写 `apply/report.md`），其中逐条列出阻断问题并记录已经落地的代码改动；`apply` 状态为 `failed`

#### Scenario: apply FAIL 回退重做设计
- **WHEN** `apply` FAIL 后执行 `loopspec rollback`
- **THEN** reset 闭环为 `design`/`tasks`/`security`/`approval`/`apply`，重做 `design` 时 `priorAttempts` 含 `apply` 记录的阻断问题

#### Scenario: 实现两轮仍失败则升级
- **WHEN** `apply` 已发生 2 次回退且再次 FAIL
- **THEN** `apply` 状态为 `exhausted`，`nextSteps` 提示需人工介入
