## ADDED Requirements

### Requirement: status 默认输出为面向 LLM 的分段纯文本报告
`loopspec status <change-name>` 在**未传** `--json` 时 SHALL 输出一份版式固定的纯文本报告，而不是逐字段的 `key: value` 列表。该报告的目标读者是 LLM/Agent：它 SHALL 使调用方只读这一份文本就能判断当前进度并得知下一条该执行的命令，无需解析 JSON。

报告 SHALL NOT 使用 Markdown 语法——不使用 `#` 标题、不使用表格、不使用列表标记、不使用强调记号。分段靠专用的分隔行完成（见下一条需求）。

传入 `--json` 时 SHALL 输出既有的 JSON，字段契约不变。

#### Scenario: 默认输出是分段纯文本而非 key: value
- **WHEN** 对一个已创建的 change 执行 `loopspec status <change>`（不带 `--json`）
- **THEN** 输出以 `=== OVERVIEW ===` 开头，且不含形如 `nodes: [{'id': ...}]` 的 Python 字面量文本

#### Scenario: 输出不含 Markdown 语法
- **WHEN** 生成任意 change 的报告
- **THEN** 输出中不出现以 `#` 开头的标题行，也不出现 Markdown 表格的表头分隔行（形如 `|---|---|`）

#### Scenario: --json 输出不受影响
- **WHEN** 对同一个 change 执行 `loopspec status <change> --json`
- **THEN** 输出为合法 JSON，且其字段与本次变更前完全一致

### Requirement: 报告的分节形式、固定节序与恒在/条件节
报告 SHALL 由形如 `=== <全大写节名> ===` 的独占一行的分隔行分节，且各节 SHALL 严格按以下顺序出现：`=== OVERVIEW ===` → `=== NODES ===` → `=== GATE FAILURES ===` → `=== PENDING ROLLBACK ===` → `=== NEXT STEPS ===`。

`=== OVERVIEW ===`、`=== NODES ===`、`=== NEXT STEPS ===` 三节 SHALL 恒定出现（即便对应内容为空也 SHALL 输出该分隔行与一行占位说明），使调用方有稳定的定位锚点。`=== GATE FAILURES ===` SHALL 仅在存在 `failed` 或 `exhausted` 状态的 gate 时出现；`=== PENDING ROLLBACK ===` SHALL 仅在 `pendingRollback` 非 null 时出现——这两节的出现本身即是信号，因此 SHALL NOT 以空节形式输出。

`=== GATE FAILURES ===` 节内部的每个 gate 子块 SHALL 由形如 `--- <gate-id> ---` 的独占一行的分隔行引出，以三连横线与节级的三连等号区分层级。

每一节的结构 SHALL 为：分隔行 → 内置说明文字 → 一个空行 → 该节数据。

#### Scenario: 一切正常时只出现三个恒在节
- **WHEN** 某 change 无任何 `failed`/`exhausted` gate
- **THEN** 报告依次含 `=== OVERVIEW ===`、`=== NODES ===`、`=== NEXT STEPS ===` 三条分隔行，且不含 `=== GATE FAILURES ===` 与 `=== PENDING ROLLBACK ===`

#### Scenario: gate 失败时追加两个条件节
- **WHEN** 某 gate 状态为 `failed`
- **THEN** 报告在 `=== NODES ===` 之后、`=== NEXT STEPS ===` 之前依次含 `=== GATE FAILURES ===` 与 `=== PENDING ROLLBACK ===`

#### Scenario: nextSteps 为空时该节仍出现
- **WHEN** `nextSteps` 为空列表
- **THEN** 报告仍含 `=== NEXT STEPS ===` 分隔行及一行占位说明

### Requirement: 每节附带内置说明文字
每一个分节（`OVERVIEW`、`NODES`、`GATE FAILURES`、`PENDING ROLLBACK`、`NEXT STEPS`，以及非 JSON 失败输出的 `ERROR`）SHALL 在其分隔行之后、该节数据之前输出一段内置说明文字，向读到它的 LLM 交代：这一节是什么、其中的列或行怎么读、以及读到之后该做什么。报告 SHALL NOT 假定读者事先了解 loopspec 的节点、gate、rollback 等概念。

`=== NODES ===` 的说明 SHALL 额外交代多行节点的读法：glob 节点把当前匹配的每个文件各占一行、续行缩进在首行之下；产物列中仍含 `*` 的路径表示该 glob 尚无匹配；备注描述节点因此固定留在首行。缺了这几句，读者会把缩进的续行误读成另一个节点，或把 `specs/**/*.md` 当成一个真实文件名。

说明文字 SHALL NOT 使用注释前缀（如 `#`）——那会与本能力"输出不出现以 `#` 开头的行"的约束冲突。说明与数据之间 SHALL 以一个空行分隔。

各节说明的**具体措辞**是设计产物而非实现细节：它决定 LLM 如何解读整份报告。实现 SHALL 逐字采用设计文档中给定的文本，SHALL NOT 在实现中自行改写。

内置说明是代码常量而非内插值，因此 SHALL NOT 经过消毒处理——消毒只适用于从数据中取出的内插值。

#### Scenario: 每一节都带说明
- **WHEN** 生成一份含 `failed` gate 的报告（五节俱全）
- **THEN** 五个分隔行之后各有一段说明文字，说明与该节数据之间有一个空行

#### Scenario: NODES 的说明交代多行节点的读法
- **WHEN** 检查 `=== NODES ===` 的说明文字
- **THEN** 其中说明了 glob 节点逐行列出匹配文件且续行缩进、含 `*` 的路径表示尚无匹配、备注位于节点首行

#### Scenario: 错误输出同样带说明
- **WHEN** 任意命令在不带 `--json` 的情况下失败
- **THEN** `=== ERROR ===` 分隔行之后有一段说明文字，交代命令已失败且未做改动

#### Scenario: 说明不使用注释前缀
- **WHEN** 检查任意一节的说明文字
- **THEN** 说明的每一行都不以 `#` 开头

### Requirement: OVERVIEW 节的内容
`=== OVERVIEW ===` 节 SHALL 给出 change 的整体定位信息：change 名、schema 名、change 根目录的**绝对**路径、`state.md` 是否存在、以及该 change 是否已全部完成（`isComplete`）。每项占一行，形式为标签加取值。

当 artifact 根目录与 change 根目录不同（schema 配置了二级 `path`）时，SHALL 额外给出 artifact 根目录；两者相同时 SHALL 省略该行，避免输出一条重复信息。

#### Scenario: OVERVIEW 给出绝对根路径与完成状态
- **WHEN** 对一个未完成的 change 生成报告
- **THEN** `=== OVERVIEW ===` 节含该 change 根目录的绝对路径、schema 名，并标明尚未完成

#### Scenario: 二级 schema path 时给出 artifact 根目录
- **WHEN** 选中的 schema 配置了 `path`，使 artifact 根目录为 `<changeRoot>/<path>`
- **THEN** `=== OVERVIEW ===` 节同时给出 change 根目录与 artifact 根目录

#### Scenario: 两个根目录相同时省略 artifact 根目录
- **WHEN** 选中的 schema 未配置 `path`，artifact 根目录与 change 根目录相同
- **THEN** `=== OVERVIEW ===` 节只给出 change 根目录一行

### Requirement: NODES 节为对齐的纯文本行清单，glob 节点占多行
`=== NODES ===` 节 SHALL 为每个节点输出**至少**一行，节点顺序与 `--json` 的 `nodes` 数组一致（即 schema 的拓扑构建序）。每个节点首行的列序 SHALL 固定为：节点 ID、状态、产物相对路径、备注。

- 前三列 SHALL 以空白填充对齐。产物列宽 SHALL 仅由各节点**首行**的产物取值决定，续行 SHALL NOT 参与列宽计算——否则一条深层嵌套的匹配路径会把整份报告的备注列右推，而续行之后本无其他列。
- 产物路径 SHALL 为相对 artifact 根目录的形式。该相对化 SHALL 由纯路径字符串运算得出，渲染实现 SHALL NOT 为此访问文件系统或重算节点状态。
- 某条匹配路径**不位于 artifact 根目录之下**时（`existingOutputPaths` 跟随符号链接，因此指向 change 目录之外的链接会成为合法匹配），该行的产物列 SHALL 输出一个固定占位符，且 SHALL NOT 输出该路径解析后的真实位置，也 SHALL NOT 输出需要 `..` 才能表达的相对路径。该占位符 SHALL 是代码常量，因此不携带任何外部内容、不需消毒。这类匹配 SHALL 仍各占一行，使"当前匹配了几个文件"这一信息不因此丢失；需要知道具体是哪些文件的调用方 SHALL 使用 `--json`。
- 渲染实现 SHALL NOT 因某条匹配路径位于 artifact 根目录之外而抛出异常；该情形 SHALL 由显式判断处理，而 SHALL NOT 依赖对相对化异常的捕获。
- 多行节点内各行的顺序 SHALL 与 `--json` 的 `existingOutputPaths` 数组逐项一致，渲染实现 SHALL NOT 自行排序——两种输出的顺序不一致会使"信息相同"这一约定打折。
- gate 节点的产物列有两种形态：尚无任何产物时 SHALL 以 `<dir>/{<pass-stem>,<fail-stem>}.<ext>` 的紧凑形式呈现；已存在恰好一个产物时 SHALL 给出该产物的实际相对路径。紧凑形式是**显示形式**，SHALL NOT 被当作可直接使用的字面路径——需要实际写入路径的调用方使用 `loopspec instructions` 返回的 `resolvedOutputPath.pass`/`.fail`。
- 产物为 glob 形式的节点 SHALL 列出其当前匹配的**全部**文件：第一个与该节点首行同行，其余各占一条续行。续行 SHALL 缩进至产物列的起始列位，且 SHALL 只含路径——不含状态，也不含备注。
- glob 节点当前零匹配时，产物列 SHALL 给出 schema 声明的 glob 模式本身（因此该取值含 `*`），使该节点仍占据一行，保住"每个节点至少一行"这个定位锚点。
- 备注 SHALL NOT 参与列对齐，SHALL 包在圆括号内紧跟产物列之后，并 SHALL 固定位于该节点的**首行**（备注描述节点，不描述某个文件）。备注 SHALL 按以下**固定优先级**取第一个命中项：① `blocked` 节点给出其缺失依赖；② 声明了 `tracks` 的节点给出任务进度（已完成/总数）；③ `failed` 或 `exhausted` 的 gate 给出指向 `GATE FAILURES` 节的提示；④ glob 节点当前零匹配时给出"尚无匹配"；⑤ 以上均不命中时整个括号 SHALL 省略，且行尾 SHALL NOT 留下尾随空白。
  这里 SHALL 是优先级判断而非互斥判断：一个节点可以同时处于 `blocked` 且声明了 `tracks`（其 payload 同时含 `missingDeps` 与 `taskProgress`），此时 SHALL 取 `blocked` 的缺失依赖。

本清单 SHALL NOT 被声明为可机械解析的格式：产物路径中若含空白，列边界即不再可靠。需要精确字段的调用方 SHALL 使用 `--json`。系统 SHALL NOT 为该清单引入引号或转义协议来假装它可解析——那既增加实现复杂度与阅读负担，又换不来真正的可解析性。该结论 SHALL NOT 因 glob 节点改为列出全部匹配文件而放宽：信息是否齐全与列边界是否可靠是两件独立的事。

#### Scenario: 每个节点至少一行且首行数等于节点数
- **WHEN** 对一个七节点的 change 生成报告
- **THEN** `=== NODES ===` 节中不缩进的数据行恰有七行，其首列取值与顺序同 `--json` 的 `nodes[*].id`

#### Scenario: 前三列对齐
- **WHEN** 某次渲染中各节点 ID 长度不一
- **THEN** 全部节点首行的状态列起始于同一列位置，产物列亦起始于同一列位置

#### Scenario: glob 节点逐条列出全部匹配文件
- **WHEN** 某 glob 节点当前匹配到三个文件
- **THEN** 该节点占三行：首行含节点 ID、状态与第一个匹配文件的相对路径，其余两个匹配文件各占一条缩进续行，缩进后的路径左端与产物列起始列位一致，且续行不含状态与备注

#### Scenario: 续行不参与列宽计算
- **WHEN** 某 glob 节点的某条续行路径长于全部节点首行产物取值
- **THEN** 其他节点行的备注起始列位与该续行不存在时完全相同

#### Scenario: 逃出 artifact 根目录的匹配以占位符呈现
- **WHEN** 某 glob 节点匹配到三个文件，其中一个是指向 change 目录之外的符号链接
- **THEN** 该节点占三行，逃逸那一行的产物列为固定占位符，报告中不出现该链接解析后的真实路径，也不出现以 `..` 开头的路径

#### Scenario: 逃逸的匹配不会使 status 失败
- **WHEN** change 目录下存在一个指向外部文件的符号链接匹配，且执行 `loopspec status <change>`（不带 `--json`）
- **THEN** 命令正常退出并输出完整报告，不抛出异常也不输出 traceback

#### Scenario: 多行节点内的顺序与 JSON 一致
- **WHEN** 某 glob 节点匹配到多个文件
- **THEN** 报告中这些行的顺序与 `--json` 的该节点 `existingOutputPaths` 数组逐项一致

#### Scenario: glob 节点零匹配时给出模式本身
- **WHEN** 某 glob 节点当前没有匹配到任何文件
- **THEN** 该节点仍占一行，产物列为 schema 声明的 glob 模式（含 `*`），备注表明尚无匹配

#### Scenario: blocked 节点给出缺失依赖
- **WHEN** 某节点状态为 `blocked` 且缺少两个依赖
- **THEN** 该行的圆括号备注中列出这两个依赖的节点 ID

#### Scenario: 声明 tracks 的节点给出进度
- **WHEN** 某节点声明了 `tracks`，被追踪文件含 12 条任务、已勾选 3 条，且该节点不处于 `blocked`
- **THEN** 该行的圆括号备注中呈现 3/12 的进度

#### Scenario: 同时 blocked 且声明 tracks 时取 blocked
- **WHEN** 某节点同时处于 `blocked` 且声明了 `tracks`，其 payload 同时含 `missingDeps` 与 `taskProgress`
- **THEN** 该行的备注给出缺失依赖，而不是任务进度

#### Scenario: 无备注的节点不输出空括号
- **WHEN** 某节点既非 `blocked`、未声明 `tracks`、非失败 gate、亦非零匹配的 glob 节点
- **THEN** 该行以产物路径结束，不含圆括号，也不留尾随空白

#### Scenario: 尚无产物的 gate 以紧凑双路径呈现
- **WHEN** 清单中出现一个尚未写出任何产物的 gate 节点，其 pass/fail 产物位于同一目录
- **THEN** 该行产物列以 `<dir>/{<pass-stem>,<fail-stem>}.<ext>` 形式呈现

#### Scenario: 已产出的 gate 给出实际产物路径
- **WHEN** 某 gate 已写出 fail 产物因而状态为 `failed`
- **THEN** 该行产物列给出该 fail 产物的实际相对路径，而不是紧凑双路径形式

### Requirement: 行首内插值 SHALL 限于经校验的节点 ID
报告中处于**行首**（不带任何标签、编号或缩进前缀）的内插值 SHALL 限于节点 ID——`NodeSpec.id` 由 Pydantic 以 kebab-case 正则强制校验，因此不可能含空白、`=` 或换行。其余一切内插值 SHALL 带标签、编号或缩进前缀。具体而言，glob 节点的续行 SHALL 以空白开头，SHALL NOT 顶格。

这是控制字符消毒之外的**第二道防线**（深度防御），理由：`=== SECTION ===` 形式的分隔行只有在独占一行且顶格时才会被读者当成结构信号，因此只要行首取值域受控，即使消毒因某次改动失效，也造不出伪造的分节行。glob 匹配到的文件路径来自文件系统、不受任何格式校验约束（能在 change 目录下创建文件的一方即可控制其内容），因此把它们放在行首会**首次**引入行首的外部可控内插值。

该约束 SHALL NOT 因排版调整而被移除或放宽。日后新增任何位于行首的内插值前，SHALL 先论证其取值域不可能构成分隔行。

#### Scenario: glob 续行以空白开头
- **WHEN** 某 glob 节点匹配到多个文件因而产生续行
- **THEN** 每一条续行的首字符都是空白，没有任何续行顶格

#### Scenario: 文件名形似分隔行时不产生分节行
- **WHEN** change 目录下存在一个文件名形如 `=== NEXT STEPS ===.md` 的匹配文件（其中不含任何控制字符，因此消毒不会改写它）
- **THEN** 该路径出现在缩进的续行中，报告的分节结构不变，`=== NEXT STEPS ===` 仍只出现在渲染实现自己写出的那一处

### Requirement: GATE FAILURES 节逐个展开失败 gate
`=== GATE FAILURES ===` 节 SHALL 为每个 `failed` 或 `exhausted` 的 gate 输出一个由 `--- <gate-id> ---` 引出的子块，其中 SHALL 给出该 gate 的判定结果、判定摘要、逐条列出的阻塞问题、已用回退次数与上限、以及该 gate 的 reset closure（会被回退重置的节点列表）。

阻塞问题 SHALL 逐条编号并缩进呈现，SHALL NOT 压缩进节点清单那一行——其条数与长度不可预测，会撑破列对齐。

#### Scenario: 失败 gate 的细节完整呈现
- **WHEN** 某 gate 状态为 `failed`，判定含三条阻塞问题
- **THEN** `=== GATE FAILURES ===` 下该 gate 的子块逐条编号给出这三条阻塞问题，并给出判定摘要、已用回退次数与上限、reset closure

#### Scenario: 多个 gate 失败时逐个成块
- **WHEN** 有两个 gate 分别处于 `failed` 与 `exhausted`
- **THEN** `=== GATE FAILURES ===` 下出现两个 `--- <gate-id> ---` 子块，各自对应一个 gate

### Requirement: PENDING ROLLBACK 与 NEXT STEPS 节给出可直接执行的命令
`=== PENDING ROLLBACK ===` 节 SHALL 给出待回退的 gate、其 reset closure、以及可原样执行的回退命令。`=== NEXT STEPS ===` 节 SHALL 把 `nextSteps` 的每一条逐条编号输出，保持其原始顺序与文本内容。

#### Scenario: 回退命令原样可执行
- **WHEN** 存在 `failed` gate
- **THEN** `=== PENDING ROLLBACK ===` 节中给出的回退命令与 `--json` 的 `pendingRollback.command` 文本一致

#### Scenario: nextSteps 逐条列出
- **WHEN** `nextSteps` 含一条指令
- **THEN** `=== NEXT STEPS ===` 节以编号形式输出该条指令，文本与 `--json` 的 `nextSteps[0]` 一致

### Requirement: 报告为纯文本，输出字节不受终端环境影响
报告 SHALL 是纯文本：SHALL NOT 包含 ANSI 转义序列、颜色、`presentation` 模块的语义 glyph、spinner 或任何仅对人眼有意义的终端装饰，且 SHALL NOT 依据终端宽度做软换行。对同一份状态，报告的输出字节 SHALL 与终端宽度、是否为 TTY、`NO_COLOR` 环境变量无关。

#### Scenario: 输出不含 ANSI 转义
- **WHEN** 在 TTY 环境下生成报告
- **THEN** 输出中不含任何 ANSI 转义序列

#### Scenario: 终端宽度不改变输出
- **WHEN** 在两种不同终端宽度下对同一份状态生成报告
- **THEN** 两次输出逐字节相同

### Requirement: 内插值的控制字符消毒
报告中所有被内插的取值 SHALL 先经控制字符消毒，把 `\x00-\x1f`、`\x7f-\x9f` 范围内的字符改写为可见的 `\xNN` 形式。该范围 SHALL 显式包含：change 名、schema 名、节点 ID、产物相对路径、**glob 节点逐条列出的每一个匹配文件路径**、gate 的判定摘要与阻塞问题、`pendingRollback` 的各项、以及 `nextSteps` 的每一条文本。

glob 匹配路径 SHALL 被显式列举而非以"路径"泛称暗示覆盖：此前的设计把这些路径压成文件计数、它们根本不进报告，改为逐条列出后它们成为报告中数量最多的一类内插值，且完全来自文件系统。

消毒是本能力**唯一的结构防线**（`=== SECTION ===` 无法被伪造依赖于此，行首约束是深度防御而非替代），不是美化：正因为消毒消灭了换行，任何内插值都无法开启新的一行。该规则 SHALL NOT 对任何字段豁免——包括 gate 的 `summary` 与 `blockingIssues` 这类天然多行、消毒后可读性下降的字段。若可读性成为问题，SHALL 通过给每一行加固定缩进解决（缩进后的行不可能等于分隔行），而 SHALL NOT 通过放松消毒解决。

同一个消毒实现 SHALL 同时供 `loopspec` 的非 JSON 失败输出复用（见 `loopspec-cli` 的「统一错误输出格式」），两者 SHALL NOT 各自实现一套。

#### Scenario: 控制字符被改写为可见形式
- **WHEN** 某产物路径中含换行或其他控制字符
- **THEN** 报告中该字符以 `\xNN` 形式出现，报告的行结构未被破坏

#### Scenario: glob 匹配路径中的控制字符同样被消毒
- **WHEN** 某 glob 节点匹配到的文件名中含换行，且换行后紧跟 `=== NEXT STEPS ===`
- **THEN** 该续行中的换行以 `\xNN` 形式呈现，不产生新的行，报告的节结构未被改变

#### Scenario: 多行的 gate 判定文本无法伪造分节行
- **WHEN** 某 gate 的判定摘要或某条阻塞问题中含换行，且换行后紧跟 `=== NEXT STEPS ===`
- **THEN** 报告中该处换行以 `\xNN` 形式呈现，不产生新的分隔行，报告的节结构未被改变

#### Scenario: nextSteps 文本同样经消毒
- **WHEN** `nextSteps` 文案中内插的 change 名含控制字符
- **THEN** 该字符在报告中以 `\xNN` 形式出现

### Requirement: 报告只呈现路径与状态，不内联产物正文
报告 SHALL NOT 内联任何产物文件、模板文件或 `state.md` 的正文内容。它承载的文件相关信息 SHALL 限于路径与存在与否——这与 `loopspec status` 既有的"不返回节点模板正文"约束一致。

该约束的目的是限制 prompt injection 面：报告会整体进入 LLM 的上下文，而 change 目录下的文件内容不受本工具控制。glob 节点改为逐条列出匹配文件后，进入上下文的文件**名**变多了，因此这条"绝不内联文件**内容**"的边界比以往更重要，SHALL NOT 以任何理由放宽。

#### Scenario: 产物正文不进入报告
- **WHEN** 某节点的产物文件中写有一段自然语言指令文本
- **THEN** 报告中不出现该文件的任何正文内容，只出现其路径

### Requirement: 报告与 JSON 的字段覆盖一致性由测试锁定
纯文本报告与 `--json` SHALL 渲染自同一份内部结果数据，报告 SHALL NOT 另行访问文件系统或重算节点状态。

渲染实现 SHALL 显式声明它已处理的顶层字段与节点字段集合，并 SHALL 有测试断言该集合与 `status` 实际产出的字段集合相等；新增字段而未决定其在报告中的呈现方式（呈现，或列入有意省略名单）时，该测试 SHALL 失败。节点字段是条件性出现的（`taskProgress`/`gate`/`missingDeps` 只在特定状态存在），因此该断言 SHALL 以全部节点字段的**并集**为比较对象。

#### Scenario: 新增字段未被处理时测试失败
- **WHEN** 给 `status` 的结果数据新增一个顶层字段，而未在报告渲染实现中处理
- **THEN** 字段覆盖一致性测试失败

#### Scenario: 报告不重新访问文件系统
- **WHEN** 生成纯文本报告
- **THEN** 报告内容完全取自 `status` 已构造的结果数据
