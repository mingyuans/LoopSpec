# Human Approval: CHANGES REQUESTED

## Changes Requested

- **每个分节需附带一段内置说明文字（section prompt），告诉 LLM 该节是什么、怎么用。** 当前 `design.md` 的 Rendered Examples 里 `=== OVERVIEW ===` 等分隔行之后直接是数据，LLM 需要自行推断各节语义与各列含义。影响 `specs/status-report/spec.md` 的分节需求与各节内容需求，以及 `design.md` D3 与 Rendered Examples——五个节（OVERVIEW / NODES / GATE FAILURES / PENDING ROLLBACK / NEXT STEPS）与 `=== ERROR ===` 各需一段内置说明，`design.md` 须给出这些说明的**字面文本**，而不只是描述"应当有说明"。

- **说明文字须支持在 `config.yaml` 中按节追加项目自定义内容。** 需要在 `WorkflowConfig`（`src/loopspec/models.py`，当前为 `extra: "forbid"`，新增字段必须显式声明）中新增一个按报告节名索引的配置项，与既有的 `context`（全局）、`rules`（按节点 ID）并列为第三个扩展维度。该配置项属 `workflow-schema` 能力的「项目级 config.yaml 与多 schema 候选」需求范围，需要为该能力补一份 delta spec——本次变更的 `proposal.md` 的 Capabilities 一节须相应补上 `workflow-schema` 作为 Modified Capability。

- **明确"追加"与"覆盖"的语义并给出理由。** 需在 design 中裁定用户配置是追加在内置说明之后、还是替换内置说明，并说明为什么——这个选择决定了不同项目的报告语义能否被 LLM 依赖。

- **用户自定义说明的多行与消毒处理须有明确规格。** 用户在 `config.yaml` 里写的说明天然是多行段落，但 `status-report` 的消毒规则会把换行改写为 `\xNN`，两者直接冲突。需要一个既保住多行可读性、又不让用户文本能够伪造 `=== SECTION ===` 分隔行的方案，并写进 spec 而非留给实现自由发挥。注意 `config.yaml` 虽是可信输入，但"可信"不等于"免消毒"——`security` 第 3 轮确认的防线是"分隔行必须独占一行才生效"，任何能产生独立行的文本来源都要受同一约束。

- **未知节名的处理须与既有约定一致。** `config.yaml` 中若为一个不存在的报告节名配置了说明，应当告警而不中断——与 `loopspec-cli` 现有「`rules` 引用不存在的节点 ID 时输出告警但不中断」的处理保持一致。

## Human's Words

> 每个章节是不是要加点 prompt? 不然 LLM 无法准确理解每个是什么意思？
> 这个 prompt, 即要有 built-in, 也需要支持在 config.yaml 追加 ueser 自己的 prompt?

（针对 `design.md` 第 197 行 Rendered Examples 中的 `=== OVERVIEW ===` 提出。）

## Summary Presented to the Human

呈现的内容为按 `approval` 第 1 轮裁决重做后的方案，涵盖：

- **三份字面输出样例**：正常态、`security` gate 失败态、`_fail()` 的错误输出，列对齐由脚本算出。
- **四个替人做的判断及理由**：备注用圆括号且不参与列对齐（多数行末会拖空白）；gate 产物用 `<dir>/{pass,fail}.<ext>` 紧凑形式（写全会把该列撑到 51 字符，代价是它非字面路径，但写文件入口本就是 `loopspec instructions`）；`artifact root` 仅在与 `change root` 不同时出现；不声称节点清单可机械解析（路径含空格时列边界不可靠，需要精确字段用 `--json`）。
- **取消表格的连带后果**：`|` 转义规则整条移除，控制字符消毒从"两道防线之一"变成唯一那道，该结论已写进 D10 与任务 1.2。
- **安全第 3 轮 PASS**：重点核验整份重写未丢失第 1 轮阻塞项的四个落点；新确认分隔行只有独占一行才生效，而唯一处于行首的内插值是节点 ID，`NodeSpec.id` 由 Pydantic 以 `KEBAB_RE` 钉住。
- **仍待裁定的 open question**：glob 节点压成 `(3 files)`，还是列出全部匹配文件。

人未对上述任何一项提出异议，也未回答 glob 节点那个 open question，而是提出了新的一项要求：各节需附说明文字，且支持项目级追加。

## Suggested Direction

内置说明放在分隔行之后、该节数据之前，与数据之间留一个空行。**倾向不引入 `#` 之类的注释前缀**：那会与 `specs/status-report/spec.md` 中"输出不出现以 `#` 开头的行"这条可测 scenario 直接冲突，而该 scenario 正是"整份报告不用 Markdown"这条裁决的检验手段。无前缀的说明段落 + 空行分隔已足以让 LLM 区分说明与数据。

多行与消毒的冲突有一个与既有决策一致的解法：**把用户文本按行拆开、逐行消毒、逐行加固定缩进后输出**。换行因此是被解析的而非被内插的（多行可读性保住），而缩进保证任何一行都不可能等于 `=== ... ===`（防线保住）。这与 D10 已写下的"可读性解法是加固定缩进，而不是放松消毒"是同一条思路，不是新发明。

配置项的形状建议按报告节名（小写、连字符，如 `next-steps`）索引，与 `rules` 按节点 ID 索引的形状对齐，便于复用既有的未知键告警逻辑。

范围提醒：本项新增了 `workflow-schema` 这个 Modified Capability，`proposal.md` 需要同步——而 `proposal` 不在 `approval` gate 的 reset closure（`design`/`specs`/`tasks`/`security`/`approval`/`apply`）内，需就地补充。

## state.md Write-Back

- Decision Log: round 2 - changes requested
- Rejected Options: 无（本轮未否决既有方案，是追加新要求）
- Open Questions: 用户自定义说明是追加还是覆盖内置说明；glob 节点详略（第 1 轮遗留，本轮仍未答复）
- Current Focus: redo design/specs/tasks per round 2 approval feedback，并就地补充 proposal.md 的 Capabilities
- Artifact Notes: approval/changes-requested.md - changes requested
