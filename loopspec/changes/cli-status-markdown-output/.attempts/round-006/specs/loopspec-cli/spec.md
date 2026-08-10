## MODIFIED Requirements

### Requirement: 全命令支持结构化 JSON 输出
`loopspec` 的每个子命令 SHALL 支持 `--json` 标志，输出机器可解析的结构化结果；`--json` 是需要精确字段的程序化调用方的主协议。

不带 `--json` 时的默认输出，其目标读者 SHALL 按命令区分：`loopspec status` 的默认输出以 **LLM/Agent 消费**为目标，输出面向 LLM 的分段纯文本报告（见 `status-report` 能力）；其余命令的默认输出为人类可读形式。无论何种形式，同一命令的默认输出与 `--json` 输出所承载的信息 SHALL 保持一致，差别仅在编码形式与详略呈现（默认输出可对列表类字段做计数式压缩，但 SHALL NOT 遗漏任何一类信息）。

#### Scenario: 任意命令附加 --json
- **WHEN** 对任意 `loopspec` 子命令附加 `--json`
- **THEN** 命令以合法 JSON 格式输出结果到 stdout

#### Scenario: status 的默认输出面向 LLM
- **WHEN** 执行 `loopspec status <change>` 而不带 `--json`
- **THEN** 输出为面向 LLM 的分段纯文本报告，而非逐字段的 `key: value` 列表

### Requirement: 统一错误输出格式
任何命令执行失败 SHALL 以退出码 `1` 结束，并在结构化模式下输出包含 `error`（机器可读错误码）、`message`（人类可读说明）、`fix`（可直接执行的修复建议）三个字段的 JSON。不带 `--json` 时，失败输出 SHALL 以 `=== ERROR ===` 分隔行开头，其后 SHALL 跟一段内置说明文字（交代命令已失败且未做任何改动、`error` 是稳定的机器可读码、`fix` 是建议的下一条命令），再逐项给出错误码、说明与修复建议三项内容——分隔行与说明文字的形式均与 `status` 报告的分节一致（见 `status-report` 能力），使两类输出在版式上同构。此约定对**全部**子命令生效，而不仅是 `status`。

该失败输出中被内插的三项取值 SHALL 与 `status` 的纯文本报告适用**同一条**控制字符消毒规则（见 `status-report` 能力），并 SHALL 复用同一个消毒实现。两类输出的输入同源（同一批用户提供的 change 名与路径）、去向同一（同一个 LLM 的上下文），因此 SHALL NOT 存在两套标准。

该约束不是理论洁癖：`message` 中内插的 change 名未经格式校验（读取类命令只判断 change 目录是否存在，不校验 kebab-case），因此含换行的 change 名会使失败输出多出攻击者控制的行；由于 `=== SECTION ===` 形式的分隔行已被确立为 LLM 定位结构的信号，这样一行可以冒充成一个合法的指令节。系统 SHALL NOT 依赖 CLI 框架在非 TTY 下的 ANSI 剥离行为作为防线——该行为不处理换行、`\r` 等控制字符。

系统 SHALL 支持以下错误码：`schema_not_found`、`schema_selection_required`、`schema_invalid`、`config_invalid`、`template_not_found`、`instruction_not_found`、`change_not_found`、`change_exists`、`invalid_change_name`、`node_not_found`、`gate_output_conflict`、`no_failed_gate`、`retries_exhausted`、`archive_conflict`、`archive_unsafe`。

#### Scenario: 命令失败时的错误结构
- **WHEN** 任意命令因某种校验失败或前置条件不满足而无法完成
- **THEN** 命令以退出码 1 结束，且 stdout 输出的 JSON 含 `error`、`message`、`fix` 三个字段

#### Scenario: 非 JSON 模式下的错误呈现
- **WHEN** 任意命令在不带 `--json` 的情况下失败
- **THEN** 命令以退出码 1 结束，stdout 输出以 `=== ERROR ===` 分隔行开头，其后含一段内置说明文字，并含 `error`、`message`、`fix` 三项内容

#### Scenario: 含换行的 change 名无法在错误输出中伪造分节行
- **WHEN** 以一个含换行、且换行后紧跟 `=== NEXT STEPS ===` 的 change 名执行 `loopspec status`（不带 `--json`）
- **THEN** 失败输出中除渲染实现自身写出的 `=== ERROR ===` 之外不出现任何其他分隔行，被内插的换行以可见的 `\xNN` 形式呈现

### Requirement: loopspec status 查看状态
`loopspec status <change-name> --json` SHALL 扫描该 change 的 artifact 根目录与 `.attempts/`，返回每个节点的当前状态、`isComplete`、`statePath`/`stateExists`、`pendingRollback`（存在 `failed` gate 时非 null，含 `gate`/`closure`/`command`；否则为 `null`）以及 `nextSteps`。`nextSteps` SHALL 按拓扑序找到第一个 `exhausted` 或 `failed` 的 gate 优先返回对应的人工介入或回退指令；若无失败/耗尽 gate，则返回第一个 `ready` 节点对应的 `loopspec instructions` 命令；若全部完成则返回完成提示。本命令 SHALL 不返回节点的模板正文。

对声明了 `tracks` 的节点，其节点条目 SHALL 额外包含 `taskProgress` 摘要：`path`（被追踪文件的相对路径）、`resolvedPath`（绝对路径）、`total`、`complete`、`remaining`；该摘要 SHALL 不包含逐条任务列表（逐条任务只在 `loopspec instructions` 中返回），以便调用方只调用一次 `status` 就能报告实现进度。未声明 `tracks` 的节点条目 SHALL 不包含 `taskProgress` 字段。

不带 `--json` 时，本命令 SHALL 输出面向 LLM 的分段纯文本报告，其版式、分节与消毒规则由 `status-report` 能力规定。该报告 SHALL 渲染自与 `--json` 完全相同的一份内部结果数据，SHALL NOT 另行访问文件系统或重算节点状态。

#### Scenario: 首次 status 返回首节点指令
- **WHEN** 对新创建、尚无任何产物的 change 执行 `status`
- **THEN** `nextSteps` 指向拓扑序第一个节点的 `loopspec instructions` 命令

#### Scenario: gate 失败时返回 pendingRollback
- **WHEN** 某 gate 状态为 `failed`
- **THEN** `pendingRollback` 非 null，包含该 gate ID、reset closure 与 `loopspec rollback` 命令

#### Scenario: gate 耗尽时不返回 rollback
- **WHEN** 某 gate 状态为 `exhausted`
- **THEN** `pendingRollback` 为 `null`，`nextSteps` 提示已达重试上限并建议查看 `loopspec history`

#### Scenario: 全部完成
- **WHEN** schema 内全部节点状态均为 `done`
- **THEN** `isComplete` 为 `true`

#### Scenario: 声明 tracks 的节点返回进度摘要
- **WHEN** 某节点声明了 `tracks`，且被追踪文件含已勾选与未勾选的任务
- **THEN** 该节点条目含 `taskProgress`，其 `total`/`complete`/`remaining` 与被追踪文件内容一致，且不含逐条任务列表

#### Scenario: 未声明 tracks 的节点无进度字段
- **WHEN** 某节点未声明 `tracks`
- **THEN** 该节点条目不含 `taskProgress` 字段

#### Scenario: 默认输出为分段纯文本报告
- **WHEN** 执行 `loopspec status <change>` 而不带 `--json`
- **THEN** 输出为符合 `status-report` 能力所定版式的分段纯文本报告，且其内容与同一时刻 `--json` 的结果一致

## ADDED Requirements

### Requirement: nextSteps 中指向 status 的命令不带 --json
任何命令返回的 `nextSteps` 文案中，若引用 `loopspec status <change-name>`，SHALL NOT 附加 `--json`——`status` 的默认输出已是为 LLM 准备的形式，附加 `--json` 会把调用方引回需要自行解析 JSON 的路径。

引用其他子命令（如 `loopspec instructions`）的 `nextSteps` 文案 SHALL 继续附加 `--json`，因为这些命令的默认输出不在本约束范围内。

#### Scenario: new 的 nextSteps 指向不带 --json 的 status
- **WHEN** `loopspec new <change>` 创建成功
- **THEN** 其 `nextSteps` 中的 `loopspec status` 命令不含 `--json`

#### Scenario: rollback 的 nextSteps 指向不带 --json 的 status
- **WHEN** `loopspec rollback <change>` 执行成功
- **THEN** 其 `nextSteps` 中的 `loopspec status` 命令不含 `--json`

#### Scenario: 指向 instructions 的 nextSteps 仍带 --json
- **WHEN** `loopspec status` 返回指向某个 `ready` 节点的 `nextSteps`
- **THEN** 该 `loopspec instructions` 命令仍附加 `--json`
