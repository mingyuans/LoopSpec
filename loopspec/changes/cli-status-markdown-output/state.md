# Change State

## Current Focus
- `security` gate 第 6 轮判定 **PASS**。下一步 `approval` 第 4 轮（人类审批）。**注意：`security` 的回退已用 2/3，若再触发一次 security FAIL 即 exhausted。**

## Frozen Decisions
- `--json` 的字段契约**完全不变**。本次只改默认（非 `--json`）输出，任何按 JSON 集成的调用方不受影响。
- 默认输出的目标读者是 **LLM**，不是人眼：**纯文本、不含任何 Markdown 语法**，不带颜色、glyph、spinner，不随终端宽度改变换行。
- 两种输出承载的**信息一致**（沿用 `loopspec-cli` 现有约定），差别只在编码形式与详略呈现方式。
- **D1** 渲染放进新模块 `src/loopspec/status_report.py`（`render_status_report(payload) -> str`），不扩展 `presentation.py`；控制字符消毒复用 `presentation.sanitize()`。
- **D2** 单一 payload 两种编码：`cli.status` 构造的同一个 `result` dict，`--json` 走 `json.dumps`，否则走渲染器；渲染器已知键集合与实际 payload 键集合由测试断言相等（节点侧取并集），防漂移。
- **D3**（第 3 轮改写，`approval` 第 1 轮裁定）分节用独占一行的 `=== <全大写节名> ===`，节序固定：`OVERVIEW` / `NODES` / `GATE FAILURES`（条件）/ `PENDING ROLLBACK`（条件）/ `NEXT STEPS`；前二与末一恒在。
- **D4** `=== OVERVIEW ===` 给一次绝对 change root，节点行给相对路径；`existingOutputPaths` 压成文件计数；artifact root 与 change root 相同时省略该行。
- **D5**（第 3 轮改写）节点清单是纯文本行，列序固定为 ID / 状态 / 产物相对路径 / 备注；前三列空白对齐，备注包在圆括号内且**不参与对齐**；gate 产物用 `<dir>/{pass,fail}.<ext>` 紧凑显示形式（非字面路径，实际路径取自 `instructions`）。原「`|` 转义」要求随表格取消而整条移除。清单**不声称可机械解析**，需要精确字段者用 `--json`，且不得为它另加引号/转义协议。
- **D6** gate 失败详情独立成节，子块由 `--- <gate-id> ---` 引出，`blockingIssues` 逐条编号并缩进。
- **D7** `_fail()` 的非 JSON 分支渲染 `=== ERROR ===` + error/message/fix，此项**全命令生效**；三项内插值必须经与报告同一条消毒规则。
- **D10**（第 2 轮新增，回应 `security` 第 1 轮阻塞；第 3 轮改写措辞）消毒是**输出层的统一规则**：报告与错误输出共用同一个消毒实现，`summary`/`blockingIssues` 不得豁免。核心推理链——消毒消灭换行 ⇒ 内插值无法开启新行 ⇒ 无法伪造 `=== SECTION ===` 分隔行。取消表格后 `|` 转义规则已移除，消毒因此是**唯一**那道结构防线。可读性解法是给多行文本加固定缩进（缩进行不可能等于分隔行），不是放松消毒。不得依赖 `click.echo` 的 ANSI 剥离兜底（它不处理换行）。
- **D11**（第 2 轮新增）`loopspec new` 的 `schema_selection_required` 走 `_emit` 而非 `_fail`，改完后非 JSON 错误输出会有两种形态。如实记录为已知一致性缺口，本次**不修**（属 `new` 的输出形态，纳入即把范围扩成全命令重做）。
- **D12**（第 4 轮新增，`approval` 第 2 轮裁定）每节分隔行之后附一段**内置说明文字**，交代该节是什么、怎么读、读完做什么；说明与数据间空一行；**不用 `#` 等注释前缀**（会与"输出不出现 `#` 开头行"这条可测 scenario 冲突）。说明的字面文本定在 `design.md` 的 Rendered Examples 中，是设计产物而非实现细节，实现须逐字照搬。
- ~~**D13**（第 4 轮新增）`WorkflowConfig` 新增可选字段 `status_report_prompts: dict[str, str]`，按节名小写连字符索引（`overview`/`nodes`/`gate-failures`/`pending-rollback`/`next-steps`/`error`）。**只追加、不覆盖**——内置说明定义各节语义，允许覆盖等于允许每个项目重定义语义，而 LLM 正靠它跨项目稳定读懂报告。未知节名告警不中断（复用 `rules` 的告警通道）。字段可选且默认空，既有 `config.yaml` 无需改动，**无配置迁移**。~~
  ← **已被 `approval` 第 3 轮撤销**（本次不支持 `config.yaml` 自定义提示词），相关 design 决策、`specs/workflow-schema/spec.md` 与配套任务已删除。
- ~~**D15**（第 5 轮新增，回应 `security` 第 4 轮阻塞）未知配置键的告警走 **stderr**：不碰 `--json` 契约、不改报告节结构、不影响 stdout 字节稳定性断言。三点缺一不可——① 写 stderr 不写 stdout；② 键名**同样经消毒**（agent 合并捕获两个流，"不是报告"不等于"不进模型"）；③ **stdout 字节不因告警有无而改变**（写成可测 scenario，防止实现退化成两边各印一份）。`instructions` 那边 `rules` 的既有告警行为不变——两条命令出口不同是因响应结构不同。~~
  ← **已被 `approval` 第 3 轮撤销**（本次不支持 `config.yaml` 自定义提示词），相关 design 决策、`specs/workflow-schema/spec.md` 与配套任务已删除。
- ~~**D14**（第 4 轮新增）用户自定义说明的多行处理：**按 `\n` 拆行 → 逐行消毒 → 逐行加两格缩进**。换行由渲染器产生而非从内插值穿透，多行可读性与防线两全。`config.yaml` 可信**不等于**免消毒——防线是"分隔行必须独占一行且顶格才生效"，不区分文本来源。自定义说明是本报告中**唯一**被允许产生多行输出的内插来源。内置说明是常量，走另一条不经消毒的路径。~~
  ← **已被 `approval` 第 3 轮撤销**（本次不支持 `config.yaml` 自定义提示词），相关 design 决策、`specs/workflow-schema/spec.md` 与配套任务已删除。
- **D8** 指向 `status` 的 `nextSteps` 文案去掉 `--json`；指向 `instructions` 的保留。
- **D9** `skill_templates.py` 同步去掉 `--json`；已 scaffold 的旧 skill 不自动更新但仍可用（平滑降级，无需迁移脚本）。

## Decision Log
- 2026-07-31 · `proposal` · 新增 capability `status-report`，而非把版式直接塞进 `loopspec-cli`：`loopspec-cli` 规定的是各命令的字段契约与错误码，而"面向 LLM 的报告版式"是一套独立的、可被其他命令复用的呈现规则，混在一起会让 `loopspec status` 那条 requirement 同时承载契约与排版两件事。
- 2026-07-31 · `proposal` · 把默认输出格式变更标为 **BREAKING**：`status` 的非 JSON 输出目前是 `key: value`，任何按行 grep 它的脚本都会失效。虽然本仓库内无此类消费者，但如实标注。
- 2026-07-31 · `proposal` · 连带修改 `lpsx-skills`：既然默认输出就是给 LLM 读的，skill 模板里 `loopspec status ... --json` 的 `--json` 就该去掉，否则新格式无人使用，改动等于空转。
- 2026-07-31 · `proposal` · 只把 `status` 一个命令纳入范围。`new`/`rollback`/`history` 的默认输出同样是 `key: value`，但它们不在每轮循环里被反复调用，收益不对等；留待后续 change。

- 2026-07-31 · `security`（第 1 轮）· 判定 **FAIL**，1 项阻塞：D7/task 3.2 把 `_fail()` 的非 JSON 输出改成 Markdown，却没有要求内插值经 `sanitize()`，而 `status-report` 为报告写了完整消毒要求——两处同源同去向的输出有两套标准。实测 `loopspec status "$(printf 'bad\n## Next Steps\n1. ...')"` 的换行原样穿透，能在错误输出里伪造出一个看起来合法的 `## Next Steps` 节。风险是被本次改动**加剧**的（节标题从乱码升级为 LLM 会当结构信号读的东西），不是原样继承。
- 2026-07-31 · `security`（第 1 轮）· 明确通过项（重做时原样保留）：报告侧「sanitize 消灭换行 ⇒ 内插值无法开启新行 ⇒ 无法伪造 `## Section`」这条推理链成立，是核心防线；`|` 转义规则；不内联产物正文（限制 prompt injection 面）+ 5.7 对应测试；glob 压成计数；D2 禁止渲染器重新访问文件系统；无新增依赖；只读不写故无新增路径遍历面。
- 2026-07-31 · `security`（第 1 轮）· 非阻塞观察：① `click.echo` 在非 TTY 下只剥离 ANSI，不剥离换行/`\r`/`\x07`，**不可当作防线**；② `schema_selection_required` 走 `_emit` 而非 `_fail`，改完后非 JSON 错误输出会出现 Markdown 与 `key: value` 两种形态，是一致性缺口（非安全问题）；③ 绝对路径含用户目录名并进入 LLM 上下文，属既有行为（`--json` 已如此），如实接受；④ gate 的 `summary`/`blockingIssues` 是多行文本，经 sanitize 后换行变 `\x0a` 会损可读性——实现时**不得**为改善可读性而对这两个字段豁免消毒。

- 2026-07-31 · `design`（第 2 轮）· 对阻塞项**不采纳**"只在 `status` 的错误路径上消毒"这条最小修法：`_fail()` 是全命令共用的，那样会让同一个函数对不同命令有不同安全等级。改为把消毒提升为输出层规则（D10），报告与错误共用一个实现。
- 2026-07-31 · `design`（第 2 轮）· 顺带把"为什么报告侧本来就安全"的推理链显式写进 D10：消毒消灭换行是结构防线本身，而非可有可无的美化——写下来是为了防止日后有人为改善 `summary` 可读性而移除它。
- 2026-07-31 · `specs`（第 2 轮）· `specs` 不在 `security` gate 的 reset closure（`design`/`tasks`/`security`/`approval`/`apply`）内，故未被回退归档，直接就地补齐两条 scenario 与消毒条款。
- 2026-07-31 · 工具观察（与本 change 无关，留给后续）· `gate_outcome` 解析 `security/fail.md` 时把 `## Blocking Issues` 之外各节的 `-` 列表项也收进了 `blockingIssues`（第 1 轮 13 条中只有 1 条是真正的阻塞项）。属 loopspec 自身的解析缺陷，不在本次范围。

- 2026-07-31 · `security`（第 2 轮）· 判定 **PASS**。第 1 轮阻塞项已落到四个可检查位置（D10、D7 补句、`loopspec-cli` 规范条款+scenario、`status-report` 反向条款+scenario、tasks 1.2/3.3/5.11），非措辞改写。第 1 轮通过项逐条比对未被稀释。
- 2026-07-31 · `security`（第 2 轮）· 4 条非阻塞提醒：① 代码块方案的隔离性同样来自消毒（内容里的 ``` 因换行被消灭而无法自成一行提前闭合），不要误以为代码块自带隔离；② `nextSteps` 文本内插了 change 名，属携带外部输入的字段，实现时不得因"自己生成的文案"而跳过消毒；③ `schema_selection_required` 维持现状可接受——`new` 在 `_KEBAB.match()` 之后才可能到达该路径，change 名不可能含换行，且其输出非报告形态；④ D2 的字段覆盖断言需按**并集**实现，因节点字段是条件性的（`taskProgress`/`gate`/`missingDeps`），否则正常情况下会误报。

- 2026-07-31 · 流程事实修正 · `approval` gate 的 reset closure 是 `design`/**`specs`**/`tasks`/`security`/`approval`/`apply`，与 `security` gate 的 closure（不含 `specs`）不同。`approval/changes-requested.md` 里"`specs` 不在 reset closure 内、就地改写"的说法有误：三份 spec 已随 round-002 一并归档，必须重写。
- 2026-07-31 · `approval` 第 1 轮 · **要求修改**（裁决文件 `approval/changes-requested.md`，人的原话存于其中）。裁决要点：报告**整体不使用 Markdown**——分节标记从 `## Section` 改为 `=== SECTION ===` 形式的纯文本分隔行；`=== NODES ===` 节内的节点清单取消 Markdown 四列表格，改为以空白对齐的纯文本行，随之「单元格内 `|` 转义为 `\|`」的要求整条移除；`_fail()` 的非 JSON 输出同步改为 `=== ERROR ===`；`design.md` 必须内置正常态与 gate 失败态两份字面输出 example；消毒防线的论证文本需从"无法伪造 `## Section`"改写为"无法伪造 `=== SECTION ===` 分隔行"，防线实质不得削弱。裁决未提及 glob 节点压成计数（D4），视为未否决。

- 2026-07-31 · `design`（第 3 轮）· 取消 Markdown 表格是**净简化**：初版设计里唯一需要转义的语法就是表格的 `|`，纯文本形态需要防的只剩控制字符，而那本来就必须防。但连带后果必须写明——消毒从"两道防线之一"变成"唯一那道"。
- 2026-07-31 · `design`（第 3 轮）· 备注**不参与列对齐**、改用圆括号紧跟产物列：七个节点里通常只有两三个有备注，为它对齐会在多数行末留下大片空白；括号让归属一目了然，不必靠列位置推断。
- 2026-07-31 · `design`（第 3 轮）· gate 产物列用 `<dir>/{pass,fail}.<ext>` 紧凑形式：写全两条路径会把该列撑到 51 字符、把备注推出去一大截。代价是它不是可直接使用的字面路径——但写文件的入口本来就是 `loopspec instructions`（返回 `resolvedOutputPath.pass`/`.fail`），与 D4 的分工一致。
- 2026-07-31 · `design`（第 3 轮）· 对"含空格的路径使列边界含糊"这一问题，选择**承认而非掩盖**：明确写入 spec"本清单不声称可机械解析"，而不是加引号/转义协议去假装它可解析——后者既增复杂度又换不来真正的保证（报告本就做了详略压缩，与 `--json` 不等价）。
- 2026-07-31 · `design`（第 3 轮）· `design.md` 末尾新增 **Rendered Examples** 一节，含三份字面输出样例（正常态、gate 失败态、错误输出），并加了任务 2.8 与 7.2 要求实现逐字对照。样例中的列对齐是脚本算出来的，不是手写估的。

- 2026-07-31 · `security`（第 3 轮）· 判定 **PASS**。重点核验"整份重写是否丢了安全约束"：第 1 轮阻塞项的四个落点（D7、D10、`loopspec-cli` 消毒条款+scenario、tasks 1.2/3.3/5.13）逐条比对完好；`|` 转义要求的移除正当（随表格取消而失去对象，新 spec 全文中 `|` 不承担任何结构作用）；消毒地位反而上升为"唯一防线"并被 D10 与 tasks 1.2 显式钉住。
- 2026-07-31 · `security`（第 3 轮）· 新增核验并确认：**分隔行必须独占一行才能生效，而唯一处于行首的内插值是节点 ID**，`NodeSpec.id` 由 Pydantic 以 `KEBAB_RE` 强制校验（不可能含空格/`=`/换行）。其余内插值都有标签、编号或缩进前缀。即使消毒失效，行首也造不出 `=== SECTION ===`。这是一道免费的深度防御，但当前无任何东西阻止后续改动把字段挪到行首——已建议以注释+测试固化（非阻塞）。
- 2026-07-31 · `security`（第 3 轮）· 4 条非阻塞观察：① gate 紧凑路径 `{pass,fail}` 被 LLM 误当字面路径的后果是 **fail-safe**——`gate_outcome` 按具体文件名判定，误写只会让流程卡住，不会让 gate 误判通过（若失败方向相反则此项应为阻塞）；② "不声称可机械解析"在安全上更稳，加解析契约等于新增歧义面；③ `schema_selection_required`（D11）维持现状的理由已从含混带过升级为写入 design 的显式论证；④ 第 2 轮以 Notes 提出的"字段覆盖断言取并集"已固化为规范文本（`status-report` 末条 requirement + tasks 5.7）。

- 2026-07-31 · `approval` 第 2 轮 · **要求修改**（裁决文件 `approval/changes-requested.md`，人的原话存于其中）。裁决要点：五个报告分节与 `=== ERROR ===` 各需一段**内置说明文字**，让 LLM 不必自行推断各节语义与各列含义，`design.md` 须给出这些说明的字面文本；说明须支持在 `config.yaml` 中**按报告节名追加**项目自定义内容，这在 `WorkflowConfig`（`extra: "forbid"`）中是继 `context`（全局）、`rules`（按节点 ID）之后的第三个扩展维度，属 `workflow-schema` 能力范围，需补 delta spec 并在 `proposal.md` 补 `workflow-schema` 为 Modified Capability；须裁定"追加 vs 覆盖"语义并说明理由；用户自定义说明的多行与消毒冲突须有明确规格（`config.yaml` 可信不等于免消毒——防线是"分隔行必须独占一行才生效"，任何能产生独立行的来源都受同一约束）；未知节名须告警而不中断，与 `rules` 引用未知节点 ID 的既有约定一致。人未对第 1 轮重做后的方案提出异议，也仍未答复 glob 节点详略那个 open question。

- 2026-07-31 · `design`（第 4 轮）· 内置说明**不用 `#` 前缀**：`specs/status-report/spec.md` 有一条可测 scenario 断言"输出不出现以 `#` 开头的行"，那正是"整份报告不用 Markdown"这条裁决的检验手段；为说明引入 `#` 会把它废掉。无前缀段落加空行分隔已足够——报告的读者是能读自然语言的模型，不是正则。
- 2026-07-31 · `design`（第 4 轮）· 说明文字的**字面文本定在 design 而非实现**：这些句子决定 LLM 如何解读整份报告，改动它们等同于改动报告语义。spec 只要求"存在且覆盖全部节"，字面文本归 design，任务 1.6/2.9/5.14 要求逐字对照。
- 2026-07-31 · `design`（第 4 轮）· 配置放 `config.yaml` 而非 schema：说明讲的是"本项目的约定"，与选用哪个 schema 无关；同一 schema 在不同项目应能配不同补充。这是 `context`/`rules` 已确立的分工。
- 2026-07-31 · `design`（第 4 轮）· 内置说明与用户说明走**两条不同路径**（前者常量不消毒、后者逐行消毒），而不是"反正都过一遍"：混为一谈会让实现看不出哪一条才是防线所在。
- 2026-07-31 · 范围事实 · 本轮新增 `workflow-schema` 为 Modified Capability（`config.yaml` 新字段）。`proposal` 不在 `approval` gate 的 reset closure 内，故就地补充其 Capabilities 与 Impact 两节。

- 2026-07-31 · `security`（第 4 轮）· 判定 **FAIL**，1 项阻塞：D13 与 `specs/workflow-schema/spec.md` 要求"未知节名告警但不中断，复用 `rules` 的既有告警通道"，但**那条通道在 `status` 上不存在**——核实代码：`rules` 的告警在 `instructions.py:33-35` 构造，只进 `loopspec instructions` 响应的 `warnings` 数组；`cli.status` 的 payload 没有 `warnings` 字段（`cli.py:723` 那个属 `artifacts` 命令）。三条可能出口各自撞线：① payload 加 `warnings` 违反"`--json` 契约一字不改"这条冻结决策；② 印进报告 stdout 会内插用户提供的配置键名，而 `status-report` 的消毒需求逐项列举的取值里**不含配置键名**，且报告节结构无处容纳该行；③ 走 stderr 则规格通篇只约束 stdout，stderr 是否消毒、是否影响"两次渲染逐字节相同"全未定义。
- 2026-07-31 · `security`（第 4 轮）· 明确通过项（重做时原样保留）：前三轮防线在本轮扩充后完好（D10 统一消毒、`summary`/`blockingIssues` 不豁免、`_fail` 经同一入口、不内联产物正文、glob 计数、D2 单一数据通路）；D14 的"拆行→逐行消毒→逐行固定缩进"在正常路径上正确，且"固定缩进 SHALL NOT 被省略"已钉成需求；内置说明不消毒且与用户说明分两条路径是对的；`config.yaml` 作为指令通道未构成扩权（能改它的人也能改 schema 的 `instruction`）；新增字段无反序列化风险（`extra: "forbid"` + `dict[str, str]`）。

- 2026-07-31 · `design`（第 5 轮）· 三条告警出口中选 **stderr**：`status` payload 加 `warnings` 会推翻"`--json` 契约一字不改"这条冻结决策；印进报告 stdout 需要同时扩充消毒需求覆盖配置键名、并在被逐条规定死的节结构里为它找位置。stderr 是唯一不推翻既有决策的一条，代价只是要把 stderr 的消毒与 stdout 的字节不变性补写成需求。
- 2026-07-31 · `design`（第 5 轮）· 拒绝把"走 stderr"当成免于消毒的理由：agent 通常合并捕获两个流，防线关心的是有没有文本能造出独立的一行，与文件描述符无关。
- 2026-07-31 · `design`（第 5 轮）· `docs/*/configuration.md` 须明确提示 `status_report_prompts` 的内容会直接进入 LLM 上下文、应与代码同等审阅（任务 6.4）：`config.yaml` 在 review 中常被当作"配置"而非"代码"，而此字段实为一条指令通道。

- 2026-07-31 · `security`（第 5 轮）· 判定 **PASS**。第 4 轮阻塞项已解决：D15 明确选定 stderr 并把三点补齐成可测 scenario（告警只在 stderr、stdout 逐字节不变、`--json` 字段不变、键名消毒），选择理由与两条被否出口都记录在案；拒绝了"走 stderr 所以不用消毒"这条捷径。前四轮防线逐条比对未被稀释。
- 2026-07-31 · `security`（第 5 轮）· 非阻塞观察（已落为任务 3.11 与 5.18）：`_fail` 有一类调用点发生在 `load_config` **失败之后**（`cli.py:397-399`；`status` 侧同理，`_load_change_context` 内部会 `load_config`），此时没有 config 可取。`=== ERROR ===` 的自定义说明必须在无配置时安全退化为"只输出内置说明"，否则错误处理路径自身抛异常会把原始错误掩盖成 traceback。属健壮性而非安全问题。

- 2026-07-31 · `approval` 第 3 轮 · **要求修改**（裁决文件 `approval/changes-requested.md`，人的原话存于其中）。裁决要点：**撤销 `config.yaml` 自定义分节说明这一整项功能**——删除 D13（`status_report_prompts` 与"只追加不覆盖"）、D14（逐行消毒与缩进）、D15（告警走 stderr）三条决策及其在 Risks/Migration Plan 中的条目；删除 `specs/workflow-schema/spec.md` 并从 `proposal.md` 移除 `workflow-schema` 为 Modified Capability；从 `specs/status-report/spec.md` 删除三条对应 requirement 并修订分节结构那一句；删除 `tasks.md` 中 1.7、3.6–3.11、5.15–5.18、6.4 及 2.8 的相应措辞。**保留 D12 内置说明不变**。撤销时 D10 的核心防线（消毒消灭换行 ⇒ 无法伪造分隔行）与 D7（`_fail` 三项经同一消毒入口）**不得**被一并删除——它们是第 1 轮 `security` 阻塞项的修复成果，与本功能无关。glob 节点详略仍未答复。

- 2026-07-31 · `design`（第 6 轮）· 执行 `approval` 第 3 轮的撤销：删除 D13/D14/D15 及 Risks 中的两条对应风险、Migration Plan 中的配置步骤、Rendered Examples 中的 `config.yaml` 样例与 `Project notes:` 段落、内置说明一览表里的"`config.yaml` 键"一列；删除 `specs/workflow-schema/spec.md`；从 `specs/status-report/spec.md` 删除三条 requirement 并把分节结构改回"分隔行 → 内置说明 → 空行 → 数据"；`tasks.md` 删 13 条（1.7、3.6–3.11、5.15–5.18、6.4、7.3），第 3 组标题改回「CLI 接线」。
- 2026-07-31 · `design`（第 6 轮）· 撤销时刻意保住的两处：D10 的核心防线（消毒消灭换行 ⇒ 无法伪造 `=== SECTION ===` 分隔行）与 D7（`_fail` 三项经同一消毒入口）——它们是第 1 轮 `security` 阻塞项的修复成果，与被撤销的功能无关。「内插值的控制字符消毒」这条 requirement 只改了一句措辞（内置说明为常量不消毒的理由，不再提"与自定义说明是两条路径"），其余原样。
- 2026-07-31 · `design`（第 6 轮）· `security` 第 5 轮以 Notes 提出的 `_fail` 在 `load_config` 失败后无 config 可取的问题（原任务 3.11、5.18），随本次撤销自然消失——`_fail` 不再需要读配置，故一并删除，不留无主补丁。

- 2026-07-31 · `security`（第 6 轮）· 判定 **PASS**。范围收窄本身不产生新攻击面，故本轮只查"撤销有没有误删"：D10 核心防线完好、D7 共用消毒入口与「含换行的 change 名无法伪造分节行」scenario 完好、`status-report` 的消毒 requirement 只改了一句必要措辞（内置说明为常量故不消毒的理由）、六条安全任务全部保留、`specs/workflow-schema/spec.md` 删除后无悬空引用。被删的 13 条任务全部只服务于被撤销的功能。
- 2026-07-31 · `security`（第 6 轮）· 本轮是唯一一次攻击面**减少**的改动：随功能一并消失的有"唯一允许多行输出的内插来源"、新增的 stderr 输出路径、以及 `_fail` 对配置对象的新依赖（第 5 轮 Notes 里那个"错误处理路径自身可能抛异常"的隐患，未留下无主补丁）。规格回到更易论证的状态——每个内插值都是单行、经同一条消毒规则、且不在行首。

## Rejected Options
- 「加一个 `--format md` 开关、保留 `key: value` 为默认」：多一个 LLM 必须记住并显式传的开关，与"默认就该好用"相悖，且 `key: value` 对嵌套结构本就是坏输出，没有保留价值。
- 「在 `presentation.py` 里加 `plain=True` 分支」（D1）：等于给该模块"一切返回带样式 `Text`"的安全不变量开后门，且 rich `Console` 的 markup 解析与 soft-wrap 仍在。
- 「渲染器直接接收领域对象（`states`、`loaded.graph`）自行组织」（D2）：第二条数据通路正是两种输出漂移的来源。
- 「节点改用每节点一个 `--- <node-id> ---` 子块 + 逐字段行」（D5，第 3 轮）：七到十个节点会膨胀成三十行以上，而提出者最初的抱怨正是逐字段输出。
- 「给纯文本节点清单加引号或转义协议，使其可机械解析」（D5，第 3 轮）：增复杂度与阅读负担，却换不来真正的可解析性——报告本就对部分字段做了详略压缩。需要精确字段用 `--json`。
- 「依赖 `click.echo` 在非 TTY 下剥离 ANSI 来兜底」（D10）：它不剥离换行、`\r`、`\x07`，而换行才是能伪造分节行的那个字符。
- 「只在 `status` 的错误路径上消毒」（D10）：`_fail()` 全命令共用，会造成同一函数对不同命令有不同安全等级。
- 「用 Markdown 二级标题 `## Section` 作为分节标记」：`approval` 第 1 轮否决，改用 `=== SECTION ===` 纯文本分隔行。
- 「用 Markdown 四列表格 `| Node | Status | Output | Notes |` 作为节点清单」：`approval` 第 1 轮否决（整份报告不用 Markdown），改用以空白对齐的纯文本行。
- 「用户配置可覆盖内置说明」（D13，第 4 轮）：内置说明定义各节语义，允许覆盖即允许每个项目重定义语义，LLM 就无法跨项目稳定读懂报告。项目该补充的是"本项目还要注意什么"。若真觉得内置说明有误，出口是改 loopspec 本身，不是在自己 config 里悄悄改写。
- 「把节说明放进 `--json`」（D12，第 4 轮）：`--json` 的消费者是程序，不需要散文；且会改动已冻结的字段契约。
- 「用户说明整体当作单个内插值消毒」（D14，第 4 轮）：会把多行段落压成一行含 `\x0a` 的乱码，等于让该功能不可用。正解是换行由渲染器解析产生、逐行消毒并缩进。
- 「在 `status` payload 里新增 `warnings` 字段承载配置告警」（D15，第 5 轮）：推翻"`--json` 字段契约一字不改"这条冻结决策。
- 「把配置告警印进报告 stdout」（D15，第 5 轮）：需内插用户写的配置键名（消毒需求未覆盖该取值），且被逐条规定死的节结构中无处容纳该行。
- 「未知配置键静默忽略、不告警」（D15，第 5 轮）：用户拼错键名将得不到任何反馈，且要删掉 `workflow-schema` 里那条已写好的"告警但不中断"需求。
- **「`config.yaml` 按节追加自定义分节说明（`status_report_prompts`）」——`approval` 第 3 轮裁定本次不做。** 整项功能连同 D13/D14/D15、`specs/workflow-schema/spec.md` 与 13 条任务一并撤销。内置说明（D12）保留。若日后重启，`.attempts/round-005/` 里有完整的设计与规格可取。

## Open Questions
- ~~**节标题记法**（D3）~~：已由 `approval` 第 1 轮裁定为 `=== SECTION ===` 纯文本分隔行，并连带取消整份报告的 Markdown 语法。
- **glob 节点详略**（D4）：`existingOutputPaths` 压成计数是否可接受，还是应完整列出匹配文件。`approval` 第 1、2 轮均未答复，留待第 3 轮确认。
- ~~**用户自定义节说明是追加还是覆盖内置说明**~~：该问题随 `approval` 第 3 轮撤销整项功能而消失。
- ~~**含空格的产物路径在 `=== NODES ===` 纯文本列中如何呈现**~~：已由 `design`（第 3 轮）D5 裁定——明确写入 spec"本清单不声称可机械解析、需要精确字段者用 `--json`"，不加引号/转义协议。

## Artifact Notes
- `proposal.md`（第 6 轮就地修改）：Why / What Changes / Capabilities / Impact 四节齐备；新增 `status-report`，修改 `loopspec-cli`、`lpsx-skills`。第 4 轮曾加入的 `workflow-schema` 已随 `approval` 第 3 轮撤销而移除。
- 实现期必踩的坑：`test_docs_consistency.py` 对 `docs/en` 与 `docs/zh` 做双向集合相等与示例块**逐字节**比对，任一 `status` 示例改动必须双语同步。
- `design.md`（第 6 轮）：D1–D12 十二条决策（原 D13–D15 已删除），末尾 **Rendered Examples**（正常态 / gate 失败态 / 错误输出三份字面样例，加一张内置说明文字一览表）。安全面在 Risks 中显式展开：prompt injection 三层缓解、含空格路径的列边界含糊、未消毒内插值可伪造 `=== SECTION ===` 分隔行（且消毒是唯一防线）、内置说明文字随实现漂移。
- `specs/status-report/spec.md`（第 6 轮，共 11 条 ADDED requirement）：第 4 轮新增的「每节附带内置说明文字」保留；第 4、5 轮新增的另三条（项目可按节追加自定义说明、自定义说明的多行处理与逐行消毒、配置告警写 stderr）已随撤销删除。
- `specs/loopspec-cli/spec.md`（delta）：MODIFIED 三条（JSON 主协议定位、统一错误输出格式改 `=== ERROR ===` 且带内置说明、共用消毒实现、`loopspec status`），ADDED 一条（`nextSteps` 中指向 `status` 的命令不带 `--json`）。
- `specs/lpsx-skills/spec.md`（delta）：MODIFIED「四个内置 skill/命令模板」，补充"模板正文中 `status` 调用不带 `--json`、`instructions` 调用仍带"。
- ~~`specs/workflow-schema/spec.md`~~：第 4 轮新增，已随 `approval` 第 3 轮撤销而删除；内容存于 `.attempts/round-005/specs/workflow-schema/spec.md`。
- `approval/changes-requested.md`：第 1 轮（round-002 归档，5 条）、第 2 轮（round-003 归档，5 条）、第 3 轮（round-005 归档，撤销配置提示词）。人的原话与呈现给人的摘要均存于各自文件中。
- `security/pass.md`：第 3、5 轮判定存于对应 `.attempts/` 目录；当前文件为第 6 轮判定——撤销未误删安全约束的逐条核验，并记录本轮是唯一一次攻击面减少的改动。
- `tasks.md`（第 6 轮）：7 组 42 条。安全相关任务已显式标注供 `security` gate 定位——1.2（共用消毒入口，并注明消毒已是唯一防线）、2.4（`summary`/`blockingIssues` 不得豁免消毒）、3.2/3.3（错误输出改 `=== ERROR ===` 并经同一消毒入口，波及全命令）、3.5（确认未触碰 `schema_selection_required`）、5.8（控制字符消毒）、5.9（不内联产物正文）、5.13（换行伪造分隔行）。本次不引入任何新依赖、不触及认证/授权/密钥、**不触碰 `config.yaml` 与 `WorkflowConfig`**。
