## ADDED Requirements

### Requirement: status 默认输出为面向 LLM 的 Markdown 报告
`loopspec status <change-name>` 在**未传** `--json` 时 SHALL 输出一份版式固定的 Markdown 报告，而不是逐字段的 `key: value` 列表。该报告的目标读者是 LLM/Agent：它 SHALL 使调用方只读这一份文本就能判断当前进度并得知下一条该执行的命令，无需解析 JSON。

传入 `--json` 时 SHALL 输出既有的 JSON，字段契约不变。

#### Scenario: 默认输出是 Markdown 而非 key: value
- **WHEN** 对一个已创建的 change 执行 `loopspec status <change>`（不带 `--json`）
- **THEN** 输出以 `# LoopSpec Status: <change-name>` 开头，且不含形如 `nodes: [{'id': ...}]` 的 Python 字面量文本

#### Scenario: --json 输出不受影响
- **WHEN** 对同一个 change 执行 `loopspec status <change> --json`
- **THEN** 输出为合法 JSON，且其字段与本次变更前完全一致

### Requirement: 报告的固定节序与恒在/条件节
报告 SHALL 由二级 Markdown 标题分节，且 SHALL 严格按以下顺序出现：`## Overview` → `## Nodes` → `## Gate Failures` → `## Pending Rollback` → `## Next Steps`。

`## Overview`、`## Nodes`、`## Next Steps` 三节 SHALL 恒定出现（即便对应内容为空也 SHALL 输出该节标题与一行占位说明），使调用方有稳定的定位锚点。`## Gate Failures` SHALL 仅在存在 `failed` 或 `exhausted` 状态的 gate 时出现；`## Pending Rollback` SHALL 仅在 `pendingRollback` 非 null 时出现——这两节的出现本身即是信号，因此 SHALL NOT 以空节形式输出。

#### Scenario: 一切正常时只出现三个恒在节
- **WHEN** 某 change 无任何 `failed`/`exhausted` gate
- **THEN** 报告依次含 `## Overview`、`## Nodes`、`## Next Steps`，且不含 `## Gate Failures` 与 `## Pending Rollback`

#### Scenario: gate 失败时追加两个条件节
- **WHEN** 某 gate 状态为 `failed`
- **THEN** 报告在 `## Nodes` 之后、`## Next Steps` 之前依次含 `## Gate Failures` 与 `## Pending Rollback`

#### Scenario: nextSteps 为空时该节仍出现
- **WHEN** `nextSteps` 为空列表
- **THEN** 报告仍含 `## Next Steps` 标题及一行占位说明

### Requirement: Overview 节的内容
`## Overview` 节 SHALL 给出 change 的整体定位信息：change 名、schema 名、change 根目录的**绝对**路径、`state.md` 是否存在、以及该 change 是否已全部完成（`isComplete`）。当 artifact 根目录与 change 根目录不同（schema 配置了二级 `path`）时，SHALL 额外给出 artifact 根目录。

#### Scenario: Overview 给出绝对根路径与完成状态
- **WHEN** 对一个未完成的 change 生成报告
- **THEN** `## Overview` 节含该 change 根目录的绝对路径、schema 名，并标明尚未完成

#### Scenario: 二级 schema path 时给出 artifact 根目录
- **WHEN** 选中的 schema 配置了 `path`，使 artifact 根目录为 `<changeRoot>/<path>`
- **THEN** `## Overview` 节同时给出 change 根目录与 artifact 根目录

### Requirement: Nodes 节为四列 Markdown 表格
`## Nodes` 节 SHALL 以 Markdown 表格逐行列出全部节点，行顺序与 `--json` 的 `nodes` 数组一致（即 schema 的拓扑构建序）。表头 SHALL 固定为 `Node`、`Status`、`Output`、`Notes` 四列。

- `Node` 列为节点 ID；`Status` 列为节点状态。
- `Output` 列为节点产物的**相对**路径（即 schema 声明的 `generates`）；gate 节点 SHALL 同时给出 pass 与 fail 两个相对路径。
- `Notes` 列 SHALL 按节点情况取**恰好一种**内容：`blocked` 节点给出其缺失依赖；声明了 `tracks` 的节点给出任务进度（已完成/总数）；`failed` 或 `exhausted` 的 gate 给出指向 `## Gate Failures` 节的提示；以上均不适用时为空。

对 glob 形式 `generates` 的节点，`Notes` 列 SHALL 以**已匹配文件数**呈现其现有产物，而 SHALL NOT 逐一列出文件路径；完整清单仍可通过 `--json` 或 `loopspec instructions` 取得。

#### Scenario: 表格逐行覆盖全部节点且顺序与 JSON 一致
- **WHEN** 对一个七节点的 change 生成报告
- **THEN** `## Nodes` 表格恰有七个数据行，其 `Node` 列取值与顺序同 `--json` 的 `nodes[*].id`

#### Scenario: blocked 节点给出缺失依赖
- **WHEN** 某节点状态为 `blocked` 且缺少两个依赖
- **THEN** 该行 `Notes` 列列出这两个依赖的节点 ID

#### Scenario: 声明 tracks 的节点给出进度
- **WHEN** 某节点声明了 `tracks`，被追踪文件含 12 条任务、已勾选 3 条
- **THEN** 该行 `Notes` 列呈现 3/12 的进度

#### Scenario: glob 节点以计数而非路径清单呈现
- **WHEN** 某 glob 节点已匹配到三个文件
- **THEN** 该行以文件数呈现，报告中不出现这三个文件的逐条路径

#### Scenario: gate 节点给出双路径
- **WHEN** 表格中出现一个 gate 节点
- **THEN** 该行 `Output` 列同时给出其 pass 与 fail 产物的相对路径

### Requirement: Gate Failures 节逐个展开失败 gate
`## Gate Failures` 节 SHALL 为每个 `failed` 或 `exhausted` 的 gate 输出一个三级标题子节（`### <gate-id>`），其中 SHALL 给出该 gate 的判定结果、判定摘要、逐条列出的阻塞问题、已用回退次数与上限、以及该 gate 的 reset closure（会被回退重置的节点列表）。

阻塞问题 SHALL 以无序列表逐条呈现，SHALL NOT 压缩进表格单元格——其条数与长度不可预测。

#### Scenario: 失败 gate 的细节完整呈现
- **WHEN** 某 gate 状态为 `failed`，判定含三条阻塞问题
- **THEN** `## Gate Failures` 下该 gate 的子节以无序列表逐条给出这三条阻塞问题，并给出判定摘要、已用回退次数与上限、reset closure

#### Scenario: 多个 gate 失败时逐个成节
- **WHEN** 有两个 gate 分别处于 `failed` 与 `exhausted`
- **THEN** `## Gate Failures` 下出现两个三级子节，各自对应一个 gate

### Requirement: Pending Rollback 与 Next Steps 节给出可直接执行的命令
`## Pending Rollback` 节 SHALL 给出待回退的 gate、其 reset closure、以及可原样执行的回退命令。`## Next Steps` 节 SHALL 把 `nextSteps` 的每一条作为有序列表的一项逐条输出，保持其原始顺序与文本内容。

#### Scenario: 回退命令原样可执行
- **WHEN** 存在 `failed` gate
- **THEN** `## Pending Rollback` 节中给出的回退命令与 `--json` 的 `pendingRollback.command` 文本一致

#### Scenario: nextSteps 逐条列出
- **WHEN** `nextSteps` 含一条指令
- **THEN** `## Next Steps` 节以有序列表输出该条指令，文本与 `--json` 的 `nextSteps[0]` 一致

### Requirement: 报告为纯文本，输出字节不受终端环境影响
报告 SHALL 是纯文本：SHALL NOT 包含 ANSI 转义序列、颜色、`presentation` 模块的语义 glyph、spinner 或任何仅对人眼有意义的终端装饰，且 SHALL NOT 依据终端宽度做软换行。对同一份状态，报告的输出字节 SHALL 与终端宽度、是否为 TTY、`NO_COLOR` 环境变量无关。

#### Scenario: 输出不含 ANSI 转义
- **WHEN** 在 TTY 环境下生成报告
- **THEN** 输出中不含任何 ANSI 转义序列

#### Scenario: 终端宽度不改变输出
- **WHEN** 在两种不同终端宽度下对同一份状态生成报告
- **THEN** 两次输出逐字节相同

### Requirement: 内插值的消毒与表格分隔符转义
报告中所有被内插的取值（change 名、schema 名、节点 ID、路径、判定摘要、阻塞问题等）SHALL 先经控制字符消毒，把 `\x00-\x1f`、`\x7f-\x9f` 范围内的字符改写为可见的 `\xNN` 形式，使其无法改写终端状态或伪造报告的行结构。

内插进 Markdown 表格单元格的取值 SHALL 额外把 `|` 转义为 `\|`，使含该字符的路径不会撕裂表格结构。

消毒是本能力的**核心结构防线**而非美化：正因为消毒消灭了换行，任何内插值都无法开启新的一行，也就无法伪造 `## Section` 形式的节标题去冒充报告结构。该规则 SHALL NOT 对任何字段豁免——包括 gate 的 `summary` 与 `blockingIssues` 这类天然多行、消毒后可读性下降的字段。若可读性成为问题，SHALL 通过把整段包进 Markdown 代码块解决，而 SHALL NOT 通过放松消毒解决。

同一个消毒实现 SHALL 同时供 `loopspec` 的非 JSON 失败输出复用（见 `loopspec-cli` 的「统一错误输出格式」），两者 SHALL NOT 各自实现一套。

#### Scenario: 控制字符被改写为可见形式
- **WHEN** 某产物路径中含换行或其他控制字符
- **THEN** 报告中该字符以 `\xNN` 形式出现，报告的行结构未被破坏

#### Scenario: 含竖线的路径不撕裂表格
- **WHEN** 某节点的产物路径中含 `|`
- **THEN** 该字符在表格单元格中以 `\|` 形式出现，表格仍为四列

#### Scenario: 多行的 gate 判定文本无法伪造节标题
- **WHEN** 某 gate 的判定摘要或某条阻塞问题中含换行，且换行后紧跟 `## Next Steps`
- **THEN** 报告中该处换行以 `\xNN` 形式呈现，不产生新的行首 `#`，报告的节结构未被改变

### Requirement: 报告只呈现路径与状态，不内联产物正文
报告 SHALL NOT 内联任何产物文件、模板文件或 `state.md` 的正文内容。它承载的文件相关信息 SHALL 限于路径、存在与否、以及计数——这与 `loopspec status` 既有的"不返回节点模板正文"约束一致。

该约束的目的是限制 prompt injection 面：报告会整体进入 LLM 的上下文，而 change 目录下的文件内容不受本工具控制。

#### Scenario: 产物正文不进入报告
- **WHEN** 某节点的产物文件中写有一段自然语言指令文本
- **THEN** 报告中不出现该文件的任何正文内容，只出现其路径或计数

### Requirement: 报告与 JSON 的字段覆盖一致性由测试锁定
Markdown 报告与 `--json` SHALL 渲染自同一份内部结果数据，报告 SHALL NOT 另行访问文件系统或重算节点状态。

渲染实现 SHALL 显式声明它已处理的顶层字段与节点字段集合，并 SHALL 有测试断言该集合与 `status` 实际产出的字段集合相等；新增字段而未决定其在报告中的呈现方式（呈现，或列入有意省略名单）时，该测试 SHALL 失败。

#### Scenario: 新增字段未被处理时测试失败
- **WHEN** 给 `status` 的结果数据新增一个顶层字段，而未在报告渲染实现中处理
- **THEN** 字段覆盖一致性测试失败

#### Scenario: 报告不重新访问文件系统
- **WHEN** 生成 Markdown 报告
- **THEN** 报告内容完全取自 `status` 已构造的结果数据
