# change-memory Specification

## Purpose
TBD - created by archiving change gated-artifact-workflow. Update Purpose after archive.
## Requirements
### Requirement: state.md 初始创建
`loopspec new` 在创建 change 时 SHALL 在 change 根目录创建初始 `state.md`，内容 SHALL 至少包含以下小节：`Current Focus`、`Frozen Decisions`、`Decision Log`、`Rejected Options`、`Open Questions`、`Artifact Notes`。

#### Scenario: 创建 change 时生成初始 state
- **WHEN** 执行 `loopspec new <change-name>` 创建成功
- **THEN** change 根目录下存在 `state.md`，且包含 Current Focus / Frozen Decisions / Decision Log / Rejected Options / Open Questions / Artifact Notes 六个小节

### Requirement: state.md 读取与降级处理
系统 SHALL 提供读取 `state.md` 正文的能力，用于 `loopspec instructions` 响应；文件缺失 SHALL 不阻塞流程——返回 `state: null` 并在 `warnings` 中包含 `state_missing`，节点指令仍照常返回。

#### Scenario: 读取存在的 state.md
- **WHEN** `state.md` 文件存在
- **THEN** 读取操作返回其正文内容，且不产生 warning

#### Scenario: state.md 缺失
- **WHEN** `state.md` 文件不存在（如被用户手动删除）
- **THEN** 读取操作返回 `None`，并附带 `state_missing` 的 warning；该 change 的节点指令生成不受影响

### Requirement: state.md 语义标签不参与状态判定
`state.md` 中允许出现 `draft`/`under-review`/`approved`/`superseded` 等人工/LLM 备注标签，用于说明某个 artifact 的语义阶段；系统 SHALL 将这些标签仅视为自由文本正文的一部分返回，不解析、不用其驱动任何节点状态枚举（`blocked`/`ready`/`done`/`failed`/`exhausted`）的判定。

#### Scenario: state.md 含语义标签
- **WHEN** `state.md` 正文中出现 `[approved]` 或 `[superseded]` 等标签
- **THEN** 读取操作原样返回包含这些标签的正文，不对其做任何结构化解析或状态映射

### Requirement: state.md 与产物矛盾时以产物为准
当 `state.md` 正文描述与实际产物文件存在性矛盾时（如标注某 artifact 为 approved 但对应文件不存在），系统在返回节点状态判定结果时 SHALL 以产物文件的存在性为唯一权威依据；该矛盾不阻塞 `loopspec status` 的输出。

#### Scenario: state.md 与实际产物矛盾
- **WHEN** `state.md` 标注某 artifact 已 approved，但对应产物文件已被删除
- **THEN** `loopspec status` 返回的节点状态仍以产物文件推导结果为准（如 `ready`），不采信 `state.md` 中的标注

### Requirement: instructions 注入 state 上下文
`loopspec instructions <node> --change <change>` SHALL 在响应中返回 `statePath` 与当前 `state.md` 正文（字段名 `state`），并在生成指令的措辞中要求调用方：（1）先阅读 `state`、`dependencies`、`priorAttempts`；（2）写完节点产物后更新 `state.md`，记录新的决策、冻结结论、被否决方案、开放问题与 artifact 备注状态；（3）不得用 `state.md` 覆盖 `status` 判断，若发现矛盾应以 `status` 结果为准并修正 `state.md` 描述。

#### Scenario: instructions 响应包含 state 字段
- **WHEN** 调用 `loopspec instructions <node> --change <change> --json`，且该 change 的 `state.md` 存在
- **THEN** 响应中包含 `statePath` 与该文件的当前正文

#### Scenario: instructions 文案要求更新 state.md
- **WHEN** 查看任意节点的 `instructions` 响应
- **THEN** 响应中的指令文案明确要求 LLM 在写完产物后更新 `state.md` 的决策日志与 artifact 备注

### Requirement: 回退不自动归档 state.md，需人工/LLM 追加记录
`state.md` 不属于任何节点的产物，回退操作 SHALL 不将其移动到 `.attempts/` 归档目录。系统在回退响应的 `nextSteps` 中 SHALL 提示调用方：应在 `state.md` 中追加记录本轮 gate 失败原因、已归档的 artifact 版本与下一轮重做应保留或避开的决策。

#### Scenario: 回退后 state.md 仍在原位
- **WHEN** 执行 `loopspec rollback` 且该 change 存在 `state.md`
- **THEN** 回退完成后 `state.md` 仍位于 change 根目录，未被移动到 `.attempts/`

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
