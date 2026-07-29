## ADDED Requirements

### Requirement: 人类判定必须在 state.md 留痕
对任何以人类回答为判定依据的节点（人类审批类 gate），系统 SHALL 在其指令文案中要求 LLM 于写出判定产物后把人类的判定追加到 `state.md`：`Decision Log` 记录一条含轮次、判定结果、**提炼后的判定要点**与该判定产物路径的条目；判定为通过时把人类已签核的要点追加到 `Frozen Decisions`；判定为要求调整时把人类否决的做法追加到 `Rejected Options`、尚无定论的问题追加到 `Open Questions`、并把 `Current Focus` 改写为按该轮人类意见重做的下一步；`Artifact Notes` 记录该判定产物的路径与结论。

**原话与提炼信息的分工** SHALL 明确：人类的原话摘录只写进该 gate 的 pass/fail 产物（需要保真、随回退归档留档、可通过 `priorAttempts.archivedPath` 回溯）；`state.md` 只写提炼后的信息，不搬运原话。

`state.md` 中的每一条记录 SHALL 自包含、去指代：人类原话中的指代词（"这个"、"那个"、"它"、"上面说的"、"刚才那条"、"这里"）SHALL 被替换为具体所指（能力名、文件路径、任务编号、需求名或决策编号），使该条目脱离当时的对话上下文单独阅读时仍可解析——`state.md` 会被后续多个节点在没有该对话上下文的情况下反复读取。

该留痕 SHALL 一律**追加**，不得删改历史条目——`state.md` 不属于任何节点产物、回退时不被归档，是跨多轮判定唯一连续可读的决策记忆。留痕 SHALL 不改变任何状态判定：判定依据永远只是 gate 的 pass/fail 产物文件本身（与"state.md 语义标签不参与状态判定"一致）。若 `state.md` 缺失（`warnings` 含 `state_missing`），SHALL 先按标准小节结构重建再追加。

#### Scenario: 人类判定被追加到 state.md
- **WHEN** 某人类审批类 gate 依人类回答写出判定产物
- **THEN** `state.md` 的 `Decision Log` 新增一条含轮次、判定结果、提炼后要点与产物路径的记录，并按判定结果同步更新 `Frozen Decisions` 或 `Rejected Options`/`Open Questions`/`Current Focus`

#### Scenario: 原话不进 state.md
- **WHEN** 人类给出一段口语化的判定意见
- **THEN** 原话摘录出现在该 gate 的 pass/fail 产物中，`state.md` 中只有提炼后的要点与指向该产物的路径

#### Scenario: state.md 条目不含未解析的指代词
- **WHEN** 人类原话中使用"这个"/"那个"等指代词指向某个能力、任务或文件
- **THEN** 写入 `state.md` 的对应条目已把指代词替换为具体所指，单独阅读该条目即可确定其指向

#### Scenario: 多轮判定的记录不被覆盖
- **WHEN** 同一 change 的同一人类审批 gate 发生第二轮判定
- **THEN** 第一轮的记录仍完整保留，第二轮以新轮次追加在其后

#### Scenario: state.md 中的人类结论不驱动状态
- **WHEN** `state.md` 已记录人类认可，但对应 gate 的 pass 产物不存在
- **THEN** 该 gate 状态仍按产物文件推导（`ready`），不因 `state.md` 的记录而判定为 `done`
