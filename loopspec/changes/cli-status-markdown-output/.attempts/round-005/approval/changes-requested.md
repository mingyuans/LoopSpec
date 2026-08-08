# Human Approval: CHANGES REQUESTED

## Changes Requested

- **撤销 `config.yaml` 自定义分节说明这一整项功能，本次不做。** 具体删除：`design.md` 的 D13（`status_report_prompts` 配置项与"只追加不覆盖"语义）、D14（用户说明的逐行消毒与逐行缩进）、D15（未知配置键告警走 stderr）三条决策及其在 Risks、Migration Plan 中的对应条目。

- **删除 `specs/workflow-schema/spec.md` 这份 delta spec**（本次变更第 4 轮为该配置项新增），并从 `proposal.md` 的 Modified Capabilities 中移除 `workflow-schema`；`proposal.md` 的 What Changes 与 Impact 两节中关于 `config.yaml` 追加说明、`WorkflowConfig`、`src/loopspec/config.py` 的条目一并移除。`proposal.md` 不在 `approval` gate 的 reset closure（`design`/`specs`/`tasks`/`security`/`approval`/`apply`）内，需就地修改。

- **从 `specs/status-report/spec.md` 中删除三条 requirement**：「项目可在 config.yaml 中按节追加自定义说明」、「自定义说明的多行处理与逐行消毒」、「配置告警写 stderr，不污染报告」。同时修订「报告的分节形式、固定节序与恒在/条件节」中"每一节的结构 SHALL 为：分隔行 → 内置说明文字 → 项目自定义说明（仅当配置了该节时）→ 一个空行 → 该节数据"这一句，去掉项目自定义说明一环。

- **保留 D12（每节附带内置说明文字）不变。** 本轮撤销的只是项目级自定义那一层，内置说明本身是上一轮裁决的产物，继续保留，其字面文本仍定在 `design.md` 的 Rendered Examples 中。

- **同步删除 `tasks.md` 中为该功能新增的任务**：1.7（自定义说明的逐行消毒与缩进渲染）、3.6–3.11（`WorkflowConfig` 新增字段、未知键校验与 stderr 告警、config 取值入口、既有 config 兼容性确认、`instructions` 告警未改动的确认、`_fail` 在无 config 时的退化）、5.15、5.16、5.17、5.18，以及 6.4（`docs/*/configuration.md` 的字段文档）。2.8 中"其后接项目自定义说明（若有）"一句需相应修订。

- **相应回退消毒规格中因该功能而写下的表述。** `specs/status-report/spec.md` 的「内插值的控制字符消毒」与 `design.md` 的 D10 中，"自定义说明是本报告中唯一被允许产生多行输出的内插来源"这类论述随该功能一并移除；撤销后报告回到"全部内插值均为单行消毒"的状态。注意 D10 的核心防线本身（消毒消灭换行 ⇒ 内插值无法开启新行 ⇒ 无法伪造 `=== SECTION ===` 分隔行）**SHALL NOT** 被一并删除——它与本功能无关，是第 1 轮 `security` 阻塞项的修复成果。

## Human's Words

> 撤销，先不支持 config.yaml 增加自定义提示词

（针对 `design.md` 第 154 行 `### D13 · config.yaml 按节追加，不覆盖` 提出。）

## Summary Presented to the Human

呈现的内容为按 `approval` 第 2 轮裁决重做后的方案，涵盖：

- **加了分节说明后的正常态字面输出**：`=== OVERVIEW ===`、`=== NODES ===`、`=== NEXT STEPS ===` 三节各自的内置说明文字与数据，并说明 `=== GATE FAILURES ===`/`=== PENDING ROLLBACK ===`/`=== ERROR ===` 三节也各有说明，字面文本均在 `design.md` 的 Rendered Examples 中。
- **`config.yaml` 追加自定义说明的配置样例与渲染结果**：`status_report_prompts.nodes` 配置一段文字后，渲染为内置说明之后的 `Project notes:` 引导行加两格缩进的段落。
- **三个替人做的判断及理由**：只追加不覆盖（内置说明定义各节语义，允许覆盖则 LLM 无法跨项目稳定读懂报告）；说明不加 `#` 前缀（会废掉"输出不出现以 `#` 开头的行"这条可测断言）；说明的字面文本定在 design 而非实现（这些句子决定 LLM 如何解读整份报告）。
- **安全第 4 轮 FAIL 及其修复**：D13 原写"未知配置键告警走 `rules` 的既有通道"，但该通道在 `status` 上不存在（`rules` 的 warnings 只在 `loopspec instructions` 响应中）；三条可能出口各自撞线——加 `warnings` 字段推翻"`--json` 契约不变"、印进 stdout 需内插未被消毒规则覆盖的配置键名、走 stderr 则规格通篇只约束 stdout。回退后 D15 选定 stderr 并补齐键名消毒与 stdout 字节不变两点，第 5 轮 PASS。
- **`security` gate 回退已用 2/3** 的提示。
- **仍待裁定的 open question**：glob 节点压成 `(3 files)`，还是列出全部匹配文件。

人未对内置说明、安全修复或其他部分提出异议，而是要求撤销 `config.yaml` 自定义提示词这一整项功能；glob 节点那个 open question 仍未答复。

## Suggested Direction

这是一次范围收窄，不是方向修正——撤销后本变更回到"只改 `loopspec status` 的默认输出形态、外加每节内置说明"这一件事上，`config.yaml` 与 `WorkflowConfig` 完全不被触碰，`workflow-schema` 不再是 Modified Capability。

撤销时最需要盯住的是**别把不属于这项功能的东西一并删掉**。D10 那条防线（消毒消灭换行 ⇒ 无法伪造分隔行）是第 1 轮 `security` 阻塞项的修复成果，与 `config.yaml` 无关；`_fail` 三项内插值经同一消毒入口（D7）同理。撤销后这两条仍须原样存在，只是不再需要为"多行输入"开特例。

另可留意：`security` 第 5 轮曾以 Notes 形式指出 `_fail` 在 `load_config` 失败后的调用点没有 config 可取（任务 3.11、5.18）。该问题本就由 D13 引入，随本次撤销自然消失，无需保留补丁。

## state.md Write-Back

- Decision Log: round 3 - changes requested
- Rejected Options: `config.yaml` 按节追加自定义分节说明（`status_report_prompts`），本次不做
- Open Questions: glob 节点详略（第 1、2 轮遗留，本轮仍未答复）
- Current Focus: redo design/specs/tasks per round 3 approval feedback，撤销 D13/D14/D15 及配套 spec 与任务，并就地修改 proposal.md
- Artifact Notes: approval/changes-requested.md - changes requested
