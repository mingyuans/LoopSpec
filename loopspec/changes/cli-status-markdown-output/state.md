# Change State

## Current Focus
- ~~`security` gate 第 6 轮判定 **PASS**。下一步 `approval` 第 4 轮（人类审批）。~~
  ← 已由 `approval` 第 4 轮判定取代
- **当前**：`apply` **已完成**，`isComplete` 为 `true`（`apply/report.md`）。57 条任务全部勾选，`make lint` 干净、`make test` 756 passed、`design.md` 五份 Rendered Examples 逐字核对全部 IDENTICAL。**下一步：`loopspec archive cli-status-markdown-output`。**
- ~~`approval` 第 5 轮 **已批准**（`approval/approved.md`）。下一步 `apply`：按 `tasks.md` 从 1.1 开始实现。~~ ← 已完成
- ~~`security` gate 第 8 轮判定 **PASS**（`security/pass.md`，第 7 轮阻塞项已由 D17 解决）。下一步 `approval` 第 5 轮（人类审批）。~~ ← 已由 `approval` 第 5 轮批准取代
- ~~`security` gate 第 7 轮判定 **FAIL**（`security/fail.md`）：glob 列全后，`existingOutputPaths` 里可能出现 artifact root 之外的绝对路径（符号链接被 `resolve()` 跟随，实测已复现），而"节点行给相对路径"未规定该情形，且 D2 与"`--json` 一字不改"堵住了取安全 relative name 的出路。**下一步：`loopspec rollback`，然后重做 `design`/`tasks`**（`security` 的 reset closure **不含 `specs`**，故三份 spec 就地修改即可）。~~
  ← 已完成（第 8 轮 D17 已裁定该情形，`security` 第 8 轮 PASS）
- ~~`approval` 第 4 轮判定 **FAIL（要求修改）**：redo `design`/`specs`/`tasks` per round 4 approval feedback——`=== NODES ===` 中的 glob 节点改为逐条列出全部匹配文件（推翻原 D4 的计数压缩），续行缩进至产物列且**不得顶格**，改完后须重新过一次 `security`。~~
  ← 已完成（第 7 轮 `design`/`specs`/`tasks` 已按此重做），并已由上一条的 `security` 第 7 轮判定取代

## Frozen Decisions
- `--json` 的字段契约**完全不变**。本次只改默认（非 `--json`）输出，任何按 JSON 集成的调用方不受影响。
- 默认输出的目标读者是 **LLM**，不是人眼：**纯文本、不含任何 Markdown 语法**，不带颜色、glyph、spinner，不随终端宽度改变换行。
- ~~两种输出承载的**信息一致**（沿用 `loopspec-cli` 现有约定），差别只在编码形式与详略呈现方式。~~
  ← **第 7 轮收紧**：glob 计数被 `approval` 第 4 轮否决后，默认输出不再对任何字段做详略压缩，差别只剩**可还原的编码形式**（相对路径、gate 双产物的紧凑写法）。`loopspec-cli` 里"可对列表类字段做计数式压缩"那句已从 spec 中删除。
- **D1** 渲染放进新模块 `src/loopspec/status_report.py`（`render_status_report(payload) -> str`），不扩展 `presentation.py`；控制字符消毒复用 `presentation.sanitize()`。
- **D2** 单一 payload 两种编码：`cli.status` 构造的同一个 `result` dict，`--json` 走 `json.dumps`，否则走渲染器；渲染器已知键集合与实际 payload 键集合由测试断言相等（节点侧取并集），防漂移。
- **D3**（第 3 轮改写，`approval` 第 1 轮裁定）分节用独占一行的 `=== <全大写节名> ===`，节序固定：`OVERVIEW` / `NODES` / `GATE FAILURES`（条件）/ `PENDING ROLLBACK`（条件）/ `NEXT STEPS`；前二与末一恒在。
- ~~**D4** `=== OVERVIEW ===` 给一次绝对 change root，节点行给相对路径；`existingOutputPaths` 压成文件计数；artifact root 与 change root 相同时省略该行。~~
  ← **第 7 轮改写**（`approval` 第 4 轮裁定 glob 列全），见下条
- **D4**（第 7 轮改写）`=== OVERVIEW ===` 给一次绝对 change root，节点行给相对路径；artifact root 与 change root 相同时省略该行；**glob 节点列出 `existingOutputPaths` 的全部匹配文件**（每文件一行，首个与节点同行、其余缩进续行）。压缩取消后报告不再有信息丢失式压缩，与 `--json` 的差异只剩可还原的编码形式（相对路径、gate 紧凑写法），因此原"不与 `--json` 逐字段等价"的论断收窄为"信息相同、编码不同"。但 D5 的「不声称可机械解析」**不因此放宽**——其理由是空白分隔遇含空白路径，与详略压缩无关。代价（大 glob 使报告膨胀）如实记入 Risks 并作为 Open Question 交回 `approval` 第 5 轮。
- **D5**（第 3 轮改写，第 7 轮再改写）节点清单是纯文本行，列序固定为 ID / 状态 / 产物相对路径 / 备注；前三列空白对齐，备注包在圆括号内且**不参与对齐**。原「`|` 转义」要求随表格取消而整条移除。清单**不声称可机械解析**，需要精确字段者用 `--json`，且不得为它另加引号/转义协议。第 7 轮新增的四条裁定：① 一个节点可占多行，**列宽只由各节点首行的产物取值决定，续行不参与**（否则一条深层 glob 路径会把整份报告的备注列推远，而续行后面本无列）；续行缩进 = ID 列宽 + 2 + 状态列宽 + 2；② 续行只含路径，**备注固定留在首行**（备注描述节点，不描述某个文件）；③ 备注是**固定优先级取第一命中**而非"互斥取值"——`blocked` > `tracks` 进度 > gate 失败 > glob 零匹配 > 省略；前几轮"多种情况互斥"的表述实测有误：`apply` 同时声明 `tracks` 且处于 `blocked`，payload 里 `taskProgress` 与 `missingDeps` 同时存在；④ glob **零匹配**时产物列给 schema 声明的 glob 模式本身（含 `*`）配 `(no matches yet)`，这是 change 刚创建或刚回退后的默认状态而非边角；⑤ gate 产物列有两种形态——尚无产物时用 `<dir>/{pass,fail}.<ext>` 紧凑显示形式（非字面路径，实际路径取自 `instructions`），已有产物时给**实际那一条**（`failed` 状态本身即由 `fail.md` 存在派生，故必然有产物；两者都存在时 `read_gate_outcome` 抛 `gate_output_conflict`，走不到渲染）。前六轮只写了紧凑形式，实际样例用的是实际路径，本轮把隐含规则写明。
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
- **D16**（第 7 轮新增，由 `approval` 第 4 轮裁定引出）**glob 续行 SHALL NOT 顶格**，必须缩进至产物列起始列位，且这条要写进 `specs/status-report/spec.md` 并配可测 scenario，而不是只当排版说明。理由是它守着 `security` 第 3 轮确认的那道免费深度防御：分隔行只有独占一行且顶格才生效，而报告里唯一处于行首的内插值是节点 ID（`NodeSpec.id` 由 `KEBAB_RE` 钉住）。glob 匹配路径来自文件系统、不受任何格式校验，续行一旦顶格，报告里就**第一次**出现行首的外部可控内插值。该条同时把这道防御明文化：行首内插值 SHALL 限于经 `KEBAB_RE` 校验的节点 ID，新增行首内插值须先论证其取值域不可能构成分隔行。**编号从 D16 起而不复用 D13–D15**，以免与本文件中对已撤销的 D13/D14/D15 的引用混淆。
- **D17**（第 8 轮新增，回应 `security` 第 7 轮阻塞）glob 匹配路径的相对化与逃逸规则：相对化是**纯字符串运算**（不访问文件系统、不重算状态，故不触碰 D2）；artifact 根目录之下的匹配给相对路径；**逃出根目录的匹配给固定占位符常量 `<outside artifact root>`**，不打印解析后的真实位置也不打印 `..` 形式；逃逸匹配仍各占一行；`status` **不得**因此抛异常（须显式判断，禁止 `try/except ValueError` 兜底）；多行顺序沿用 payload 的 `existingOutputPaths` 数组，渲染器不自行排序。背景事实：`resolve_output_entries()` 对每个匹配返回 `path.resolve()`、**跟随符号链接**，而 `_is_artifact_candidate()` 只按未解析路径过滤，故外部路径会成为合法匹配（已实测复现）。`--json` 仍打印这些外部绝对路径，属改动前的既有行为、契约冻结，本次不改。
- **glob 列全不设数量上限**（`approval` 第 5 轮签核）：报告膨胀（大 glob 使每轮 token 开销上升，与 `proposal.md` 的动机相抵）与上下文稀释（批量建文件可把 `=== NEXT STEPS ===` 挤出 LLM 有效上下文）两项代价如实接受。不得在实现期擅自加截断或"前 N 条 + 省略"。
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

- 2026-08-08 · `approval` 第 4 轮 · **要求修改**（裁决文件 `approval/changes-requested.md`，人的原话存于其中）。裁决要点：**`=== NODES ===` 中的 glob 节点改为逐条列出全部匹配文件**（取值仍来自 `existingOutputPaths`），第一行与其他节点行同构、其余匹配文件各占一行并缩进对齐到产物列——这推翻了原 D4 的计数压缩，是前三轮一直悬着的 open question 的最终裁定。连带要改：`specs/status-report/spec.md` 删除「glob 节点 SHALL NOT 逐一列出匹配文件」整句与备注取值中的 glob→计数一项并补多行 scenario；D4 重写"唯一压缩点/不与 `--json` 等价"的论断（但 D5 的「不声称可机械解析」不得放宽，其理由是空白分隔本身而非详略压缩）；D5 裁定续行列位、多行节点与 `blocked`/`tracks`/gate 备注共存时备注的位置、glob 零匹配的呈现；Risks 中 prompt injection 的第三层缓解（glob 压成计数）失效须如实重写；tasks 1.5/2.2/2.3/2.9/5.4/7.2 同步改写。
- 2026-08-08 · `approval` 第 4 轮 · **新增一条安全约束**（本轮由裁定的副作用引出，须写进 `specs/status-report/spec.md` 并配可测 scenario）：glob 多行呈现的**续行 SHALL NOT 顶格，必须以空白开头**。理由是 `security` 第 3 轮确立的深度防御——分隔行只有独占一行且顶格才生效，而唯一处于行首的内插值是节点 ID（`NodeSpec.id` 由 `KEBAB_RE` 钉住）；glob 匹配到的路径来自文件系统、不受 `KEBAB_RE` 约束，续行一旦顶格，行首就第一次出现攻击者可影响的内插值。
- 2026-08-08 · `approval` 第 4 轮 · 处理了一次**答复内部冲突**：人先同时选了"批准，开始实现"与"glob 列出全部匹配文件"，而后者与 `specs/status-report/spec.md`、D4/D5、Rendered Examples 及任务 2.3/5.4/2.9 直接矛盾，且这三份产物都在 `approval` 的 reset closure 内、无法在批准后就地修改。向人说明冲突与连带代价（D4 等价性论断需重写、`security` 第三层缓解失效、`security` 回退已用 2/3）后二次提问，人选定"回退重做，纳入 glob 列全"。**未替人裁定**，两次答复原文均存于裁决文件。

- 2026-08-08 · `design`（第 7 轮）· 执行 `approval` 第 4 轮裁定：D4 改为 glob 列全并重写"信息压缩/等价性"论断；D5 补齐三处版式细节（续行列位、备注归属行、零匹配呈现）并修正"备注互斥"为"固定优先级"；新增 D16（续行不得顶格，安全约束）；D10 的消毒覆盖范围显式扩到 glob 匹配路径——此前它们被压成计数、根本不进报告，列全后成为报告中数量最多的一类内插值；Risks 中 prompt injection 由三层缓解改为两层并如实记录残余风险扩大；Rendered Examples 重写为四份样例（正常态含多行 glob、gate 失败态、glob 零匹配、错误输出），列对齐由脚本算出（ID 8 / 状态 7 / 产物 40 / 续行缩进 19）。
- 2026-08-08 · `design`（第 7 轮）· 两处**顺带发现并修正的既有不一致**（非本轮裁定内容，但不修就会带进实现）：① 前几轮称备注取值"互斥"，而 `apply` 节点实际同时有 `taskProgress` 与 `missingDeps`（本 change 当前状态即是），故规则必须是优先级而非互斥；② 前几轮把 gate 产物列一律写成紧凑 `{pass,fail}` 形式，但历轮样例里已产出的 gate 用的是实际路径（如 `security/pass.md`），且 `failed` 状态本身就由 `fail.md` 存在派生，隐含规则本轮写明。
- 2026-08-08 · `design`（第 7 轮）· **不擅自给 glob 列全加数量上限**：那等于部分恢复被第 4 轮否决的压缩，且"前 N 条 + 省略提示"会让 LLM 无法判断所见是否完整。改为把代价（大 glob 使报告膨胀，与 proposal 里"降低每轮 token 开销"的动机相抵）写进 Risks，并作为唯一一条 Open Question 交回 `approval` 第 5 轮裁定。

- 2026-08-08 · `specs`（第 7 轮）· 三份 delta spec 随 round-006 回退一并归档，全部重写（`approval` gate 的 reset closure 含 `specs`，与 `security` gate 的 closure 不同）。`status-report` 从 11 条增至 **12 条** requirement：「NODES 节」整条改写为「NODES 节为对齐的纯文本行清单，glob 节点占多行」（列宽只由首行决定、续行缩进只含路径、备注固定优先级、零匹配给模式本身、gate 产物两形态），删除「glob 节点 SHALL NOT 逐一列出匹配文件」整句；**新增第 12 条「行首内插值 SHALL 限于经校验的节点 ID」**（D16，配两条 scenario）；「内插值的控制字符消毒」显式列举 glob 匹配路径为受管取值；「每节附带内置说明文字」补一段要求 NODES 说明交代多行读法 + 一条 scenario；「不内联产物正文」补一句"文件名变多故这条边界比以往更重要"。
- 2026-08-08 · `specs`（第 7 轮）· 顺带修掉 `loopspec-cli` 里一句会与本轮裁定冲突的措辞：「全命令支持结构化 JSON 输出」原文允许"默认输出可对列表类字段做**计数式压缩**"，那正是被否决的 glob 计数。改为"差别仅在编码形式（相对路径、gate 紧凑写法）且不遗漏任何一类信息"，并新增 scenario「默认输出不遗漏 JSON 中的信息」断言 glob 每个匹配文件都在。`lpsx-skills` 与本轮裁定无关，原样重写。
- 2026-08-08 · `tasks`（第 7 轮）· 7 组 **51 条**（上一轮 42 条）。新增/改写的是：1.5（列宽只由首行决定 + 续行缩进算法）、1.6（NODES 说明须含多行 glob 三句）、2.2（gate 产物两形态）、2.3（glob 多行渲染）、**2.4（安全：续行不得顶格，附注释说明理由）**、2.5（备注固定优先级 + 零匹配给模式本身）、5.5（断言从"以计数呈现"**反转**为列全）、5.6（续行不参与列宽）、5.7（零匹配）、5.8（备注优先级）、5.9（gate 两形态）、**5.14（安全：glob 文件名含换行的消毒）**、**5.15（安全：文件名形如 `=== NEXT STEPS ===.md` 时靠缩进拦住，消毒对它无效）**。标注**安全**的任务从 6 条增至 **9 条**：1.2、2.4、2.6、3.3、5.13、5.14、5.15、5.16、5.18。
- 2026-08-08 · `tasks`（第 7 轮）· 7.2 特意点明：本 change 自己的 `specs` 节点就是一个匹配三个文件的 glob 节点，因此人工执行 `loopspec status cli-status-markdown-output` 能直接验证多行版式与续行缩进，不需要另造夹具。

- 2026-08-08 · `security`（第 7 轮）· 判定 **FAIL**，1 项阻塞（拆成 3 条 bullet：问题、为何不能留给实现、需补的 scenario/任务）。核心：`outputs.resolve_output_entries()` 对每个 glob 匹配返回 `path.resolve()`、**跟随符号链接**，而 `_is_artifact_candidate()` 只按未解析路径排除 `.attempts/` 与保留名，因此**指向 change 目录之外的符号链接会作为合法匹配进入 `existingOutputPaths`**。实测已复现（临时 home 下 `specs/cap/link.md` → `existingOutputPaths` 里出现 artifact root 之外的绝对路径）。上一轮压成计数时这些路径根本不进报告，改为列全后实现必须相对化它们，三条路都坏：`relative_to()` 抛 `ValueError` 使 `status` 变 traceback（**任何能在 change 目录放一个外部符号链接的人都能让 agent 循环停摆**）、`relpath()` 打印 `../../..` 泄露 artifact root 之外的位置（推翻 `resolve_output_entries` docstring 明写的立场）、原样打印绝对路径违反 D4。
- 2026-08-08 · `security`（第 7 轮）· 为什么判阻塞而不是"实现细节"：D2（渲染器只读 payload、不访问文件系统）与"`--json` 一字不改"两条冻结决策，把"取到那份未跟随符号链接的 relative name"这条出路堵死了，实现无从自行选择。建议的让步方向是 D2——其立法目的是防第二条数据通路造成漂移，而纯路径字符串运算不重算状态——但裁定权在 `design`，本 gate 不代劳。
- 2026-08-08 · `security`（第 7 轮）· 本轮通过项（重做时原样保留）：消毒覆盖范围按新攻击面正确扩写并显式列举 glob 匹配路径（spec + tasks 1.2）；**D16 经实测确认必要**——`=== NEXT STEPS ===.md` 这类文件名确实能进 `existingOutputPaths` 且不含控制字符，消毒对它完全无效，唯一拦住它的就是续行缩进；D7 共用消毒入口与含换行 change 名的 scenario 完好；「不内联产物正文」被加强；Risks 如实记录缓解从三层减为两层；删掉 `loopspec-cli` 那句"可做计数式压缩"是正确的连带修改；无新增依赖、不触认证/授权/密钥、只读不写。
- 2026-08-08 · `security`（第 7 轮）· 3 条非阻塞观察：① glob 列全使攻击者可用批量文件把 `=== NEXT STEPS ===` 挤出 LLM 有效上下文（稀释而非注入，且能批量写 change 目录者也能改 `tasks.md` 正文），请 `approval` 裁定上限时纳入考虑；② `resolve_outputs()` 按**解析后的绝对路径**排序，符号链接会按目标排序，建议 spec 把顺序写死为"与 `--json` 的 `existingOutputPaths` 一致"；③ 指向 `.attempts/` 内部的符号链接能绕过 `.attempts` 过滤把归档产物列回当前节点——属既有行为，与本次改动无关，留给后续 change。

- 2026-08-08 · `design`（第 8 轮）· 新增 **D17**（回应 `security` 第 7 轮阻塞）：glob 匹配路径的相对化规则与逃逸情形。四条裁定——① 相对化是**纯字符串运算**，不访问文件系统、不重算状态，因此**不触碰 D2**；② 位于 artifact 根目录之下的匹配给相对路径；③ 不在其下的匹配（符号链接逃逸）给固定占位符常量 `<outside artifact root>`，**不打印**解析后的真实位置，也不打印 `..` 形式（与 `resolve_output_entries()` docstring 已确立的立场一致）；④ 逃逸的匹配仍各占一行，故"有几条匹配"不丢，具体文件的出口是 `--json`。另加两条：`status` 不得因此抛异常（须**显式判断**，禁止 `try/except ValueError` 兜底），多行顺序沿用 payload 数组、渲染器不自行排序。Context 开头补入 `existingOutputPaths` 跟随符号链接这一性质与实测输出；Rendered Examples 增至五份（新增逃逸样例）。
- 2026-08-08 · `design`（第 8 轮）· **拒绝了 `security` 第 7 轮自己给的修复方向**（"最该让步的是 D2"）：不必让步任何冻结决策就能安全解决——D2 禁的是第二条数据通路（渲染器自行访问文件系统或重算状态），而对 payload 里已有字符串做路径运算两者都不是。让步反而会削弱一条仍然有效的防漂移约束。三条被否的备选：给逃逸路径打印 `../` 形式（读者是 LLM，泄露无收益）、把逃逸匹配整条剔除（"行数=匹配数"不再成立，且被静默隐藏的匹配比标注在外的更危险——节点已因它被算作 `done`）、把逃逸升级为错误让 `status` 失败（越界，`status` 是只读观察入口，一个符号链接就能让整个 change 无法被观察）。
- 2026-08-08 · `specs`（第 8 轮，就地修改）· `security` gate 的 reset closure **不含 `specs`**，故三份 spec 未被回退归档，直接就地补入 D17：「NODES 节」requirement 增四条规范 bullet（纯字符串相对化、逃逸给占位符且不打印真实位置/`..`、不得因此抛异常、顺序与 `existingOutputPaths` 逐项一致），新增三条 scenario（占位符呈现、`status` 不失败、顺序一致）。
- 2026-08-08 · `tasks`（第 8 轮）· 7 组 **57 条**（第 7 轮 51 条）。新增 1.7（占位符常量）、2.4（**安全**：D17 相对化与占位符）、2.5（**安全**：显式判断、禁止兜底捕获、不得 traceback）、5.6（多行顺序与 `--json` 一致）、5.14（**安全**：逃逸匹配的占位符与不泄露）、5.15（**安全**：逃逸场景 `status` 退出码 0 且 `--json` 行为不变）；第 2 组重新编号使编号连续。标注**安全**的任务从 9 条增至 **13 条**：1.2、2.4、2.5、2.6、2.8、3.3、5.14–5.19、5.21。
- 2026-08-08 · `security`（第 8 轮）· 判定 **PASS**。第 7 轮阻塞项逐条核验为真解决而非改写措辞：取值规则已明文裁定并落到 spec 的四条 bullet + 三条 scenario（上一轮 spec 里完全没有"artifact 根目录之外"这个概念）；崩溃底线写成实现约束并禁止 `try/except` 兜底；泄露处理与既有代码立场对齐；顺序按第 7 轮 Notes ② 钉住；且**未让步任何冻结决策**。历轮阻塞项（第 1 轮 `_fail` 消毒、第 3 轮行首防御、消毒覆盖 glob 路径、不内联正文）逐条比对只增未减。
- 2026-08-08 · `security`（第 8 轮）· 5 条非阻塞观察：① 指向 artifact 根目录**内部**的符号链接会显示其目标的相对路径而非链接自身的名字（两者都在 change 目录内、不构成泄露；要修需让 payload 携带 relative name，会动 `--json` 契约，属后续 change）；② 上下文稀释风险请 `approval` 在裁定 glob 上限时一并考虑；③ 指向 `.attempts/` 内部的符号链接能绕过 `.attempts` 过滤（既有行为，后续 change）；④ 逃逸匹配按目标路径排序、可能出现在中间行（顺序仍确定）；⑤ **本 gate 回退已用满 3/3——此后 `approval` 若再要求修改，`security` 会被重新判定但已无回退额度，任何 FAIL 都直接 `exhausted`。**

- 2026-08-08 · `approval` 第 5 轮 · **批准**（裁决文件 `approval/approved.md`，人的原话存于其中）。裁定要点：按第 8 轮的 `design.md`（D1–D12 + D16 + D17）、三份 spec 与 57 条任务开始实现；**glob 列全不设数量上限**，报告膨胀与上下文稀释的代价如实接受。人未提附加意见。被否的两项是"给 glob 列全设上限"与"其他修改"，两者的说明中都写明了 `security` 会被重判且已无回退额度、重判 FAIL 即 `exhausted`——本轮把 open question 与审批判定合并为一个三选一，正是为避免第 4 轮那种答复相互冲突。
- 2026-08-08 · `approval` 第 5 轮 · 实现期须知的五条非阻塞事项已记入裁决文件：指向 artifact 根目录内部的符号链接会显示目标路径而非链接名（要修需动 `--json` 契约，属后续 change）；上下文稀释是"不设上限"的已知代价；`.attempts/` 符号链接可绕过过滤（既有行为）；D11 的两种错误输出形态；`gate_outcome` 把裁决文件其他节的 `-` 列表项也收进 `blockingIssues`。

- 2026-08-08 · `apply` · **完成**（`apply/report.md`）。新增 `src/loopspec/status_report.py` 与 `tests/test_status_report.py`（43 个测试）；改 `cli.py`（`status` 与 `_fail` 的非 JSON 分支、三处 `nextSteps` 文案）、`skill_templates.py`、`tests/test_skill_templates.py`、以及 11 份双语文档。`presentation.py`、`config.py`、`models.py`、`outputs.py` 均未触碰。
- 2026-08-08 · `apply` · 三处 design 未规定、由实现裁定的细节（已记入报告）：① gate 双产物不同目录/后缀时退化为 `pass | fail`（内置 schema 走不到）；② `nextSteps` 为空时的占位文本定为 `(nothing queued)`；③ `fix` 为空时因逐行 `rstrip` 输出裸标签 `fix:`。
- 2026-08-08 · `apply` · **实现期发现（非偏差，但推翻了任务 5.18 的一个假设）**：`resolve_outputs()` 按解析后的绝对路径排序，因此以 `=` 开头的文件名（安全测试用的 `=== NEXT STEPS ===.md`）排在最前，落在节点**首行**的产物列而非缩进续行。防线仍成立——首行以节点 ID 开头，产物列永不在第 0 列——测试断言已改为"含该文件名的任何行都不顶格"，比原描述更准确。
- 2026-08-08 · `apply` · 测试环境事实（供后续参考）：本仓库测试对终端彩色环境敏感且方向相反——强制彩色时 `test_cli.py::test_artifacts_human_output_renders_markup_like_paths_verbatim` 失败，强制 `NO_COLOR` 时 `test_presentation.py` 两条颜色断言失败。`FORCE_COLOR= CLICOLOR_FORCE= make test` 为 756 全绿。与本次改动无关（该测试属 `artifacts` 命令，且改动前即失败），已列入报告的 Follow-Ups。

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
- **「glob 节点的 `existingOutputPaths` 在 `=== NODES ===` 中压成文件计数 `(3 files)`」（原 D4）——`approval` 第 4 轮否决**，改为逐条列出全部匹配文件、续行缩进至产物列。
- 「批准现状（glob 保持计数）、把 glob 列全记入 `state.md` 留给后续 change」——`approval` 第 4 轮否决：人选择在本次变更内一并解决，宁可回退重做 `design`/`specs`/`tasks` 并再过一次 `security`。

## Open Questions
- ~~**节标题记法**（D3）~~：已由 `approval` 第 1 轮裁定为 `=== SECTION ===` 纯文本分隔行，并连带取消整份报告的 Markdown 语法。
- ~~**glob 节点详略**（D4）：`existingOutputPaths` 压成计数是否可接受，还是应完整列出匹配文件。~~：已由 `approval` 第 4 轮裁定为**逐条列出全部匹配文件**（第 1、2、3 轮均未答复，第 4 轮答复）。
- ~~**glob 多行呈现的续行缩进列位如何计算**（第 4 轮新增）~~：已由 `design`（第 7 轮）D5 裁定——续行缩进 = ID 列宽 + 2 + 状态列宽 + 2，且**列宽只由首行产物取值决定、续行不参与**。
- ~~**多行节点与备注共存时备注放在哪一行**（第 4 轮新增）~~：已由 `design`（第 7 轮）D5 裁定——备注固定留在首行，且规则由"互斥"改为固定优先级 `blocked` > `tracks` > gate 失败 > glob 零匹配 > 省略。
- ~~**glob 匹配 0 个文件时该节点行如何呈现**（第 4 轮新增）~~：已由 `design`（第 7 轮）D5 裁定——产物列给 glob 模式本身（含 `*`），备注 `(no matches yet)`。
- ~~**glob 列全是否需要数量上限**（第 7 轮新增，D4 与 Risks）~~：已由 `approval` 第 5 轮裁定为**不设上限**，代价（报告膨胀、上下文稀释）如实接受并记入 Frozen Decisions。`design.md` 的 Open Questions 一节自此为空。
- ~~**用户自定义节说明是追加还是覆盖内置说明**~~：该问题随 `approval` 第 3 轮撤销整项功能而消失。
- ~~**含空格的产物路径在 `=== NODES ===` 纯文本列中如何呈现**~~：已由 `design`（第 3 轮）D5 裁定——明确写入 spec"本清单不声称可机械解析、需要精确字段者用 `--json`"，不加引号/转义协议。

## Artifact Notes
- `proposal.md`（第 6 轮就地修改）：Why / What Changes / Capabilities / Impact 四节齐备；新增 `status-report`，修改 `loopspec-cli`、`lpsx-skills`。第 4 轮曾加入的 `workflow-schema` 已随 `approval` 第 3 轮撤销而移除。
- 实现期必踩的坑：`test_docs_consistency.py` 对 `docs/en` 与 `docs/zh` 做双向集合相等与示例块**逐字节**比对，任一 `status` 示例改动必须双语同步。
- ~~`design.md`（第 6 轮）：D1–D12 十二条决策（原 D13–D15 已删除）……~~ ← 已由第 7 轮取代（第 6 轮版本存于 `.attempts/round-006/design.md`）
- `design.md`（第 8 轮）：D1–D12 + **D16 + D17** 十四条决策（原 D13–D15 已撤销，编号不复用）。Context 开头新增 `existingOutputPaths` 跟随符号链接这一性质的说明与实测输出；末尾 **Rendered Examples** 五份字面样例（正常态含多行 glob / `security` gate 失败态 / glob 零匹配 / 含逃逸符号链接的匹配 / 错误输出）、版式要点汇总、内置说明一览表。Risks 新增「符号链接使匹配路径逃出 artifact 根目录」一条。第 7 轮版本存于 `.attempts/round-007/design.md`。
- ~~`design.md`（第 7 轮）：D1–D12 + **D16** 十三条决策（原 D13–D15 已撤销，编号不复用），末尾 **Rendered Examples** 四份字面样例（正常态含多行 glob 节点 / `security` gate 失败态 / glob 零匹配 / 错误输出）、一节版式要点汇总、一张内置说明文字一览表。安全面在 Risks 中显式展开：**glob 列全使 prompt injection 缓解从三层减为两层**（如实接受，人已在知情下裁定）、大 glob 使报告膨胀、含空白路径的列边界含糊、未消毒内插值可伪造 `=== SECTION ===` 分隔行（消毒是唯一结构防线，覆盖范围显式含 glob 匹配路径）、内置说明文字随实现漂移。`=== NODES ===` 的内置说明文字已扩写三句以交代多行 glob 与零匹配的读法。
- `specs/status-report/spec.md`（第 7 轮重写 + **第 8 轮就地补 D17**，共 **12 条** ADDED requirement）：「NODES 节」整条改写为多行 glob 版本，并于第 8 轮补入四条 D17 规范 bullet（纯字符串相对化、逃逸给占位符且不打印真实位置/`..`、不得因此抛异常、顺序与 `existingOutputPaths` 逐项一致）与三条 scenario；新增「行首内插值 SHALL 限于经校验的节点 ID」（D16）；消毒条款显式列举 glob 匹配路径；内置说明条款要求 NODES 说明交代多行读法。**该文件在 `security` 的两次回退中都未被归档**（`security` 的 reset closure 不含 `specs`），因此第 8 轮是就地修改。第 4、5 轮那三条配置相关 requirement 已随第 3 轮撤销删除，第 6 轮版本存于 `.attempts/round-006/`。
- `specs/loopspec-cli/spec.md`（delta）：MODIFIED 三条（JSON 主协议定位、统一错误输出格式改 `=== ERROR ===` 且带内置说明、共用消毒实现、`loopspec status`），ADDED 一条（`nextSteps` 中指向 `status` 的命令不带 `--json`）。
- `specs/lpsx-skills/spec.md`（delta）：MODIFIED「四个内置 skill/命令模板」，补充"模板正文中 `status` 调用不带 `--json`、`instructions` 调用仍带"。
- ~~`specs/workflow-schema/spec.md`~~：第 4 轮新增，已随 `approval` 第 3 轮撤销而删除；内容存于 `.attempts/round-005/specs/workflow-schema/spec.md`。
- `apply/report.md`：实现报告——7 组 57 条逐组说明、变更文件清单（新增 2 个、改动 3 个代码文件与 11 份文档）、真实的 lint/test 输出（含对彩色环境敏感那条既有失败的如实记录与三点证据）、五份样例逐字核对结果、三处 design 未规定的实现裁定、一处实现期发现、六条 Follow-Ups。
- `approval/approved.md`（第 5 轮判定，**当前文件**）：呈现给人的摘要以"自第 4 轮以来的三件事"为主线（第 7 轮重做、`security` 第 7 轮 FAIL 及其实测复现、第 8 轮 D17 与 `security` PASS）、人的原话、五条非阻塞事项、以及 state.md 写回清单。
- `approval/changes-requested.md`：第 1 轮（round-002 归档，5 条）、第 2 轮（round-003 归档，5 条）、第 3 轮（round-005 归档，撤销配置提示词）、第 4 轮（round-006 归档，glob 节点改为列出全部匹配文件，8 条）。人的原话与呈现给人的摘要均存于各自文件中；第 4 轮还记录了人的两次答复相互冲突、以及向人说明冲突后由人二次选定的经过。
- `security/fail.md`（第 7 轮判定，已随 round-007 回退归档至 `.attempts/round-007/security/fail.md`）：1 项阻塞拆成 3 条 bullet（符号链接使 artifact root 之外的绝对路径进入 glob 列全的取值；为何 D2 与 `--json` 冻结使其无法留给实现；需补的逃逸路径 scenario 与任务），另有「本轮通过项」7 条（**重做时不得连带改动**）与 4 条非阻塞观察。含实测复现步骤。
- `security/pass.md`（**当前文件为第 8 轮判定**）：第 7 轮阻塞项的逐条核验（取值规则已明文裁定、崩溃底线写成实现约束并禁止兜底捕获、泄露处理与既有立场对齐、顺序钉住、未让步任何冻结决策）、Checks Performed、5 条非阻塞观察（含"本 gate 回退已用满 3/3"的提醒）。第 3、5 轮判定存于对应 `.attempts/` 目录，第 6 轮存于 `.attempts/round-006/`。
- `tasks.md`（**第 8 轮**）：7 组 **57 条**，标注**安全**的 **13 条**为 1.2（共用消毒入口，含 glob 路径）、2.4（D17 相对化与逃逸占位符）、2.5（显式判断、禁止兜底捕获、不得 traceback）、2.6（续行不得顶格，D16）、2.8（`summary`/`blockingIssues` 不得豁免消毒）、3.3（`_fail` 经同一入口、不依赖 `click.echo`）、5.14（逃逸占位符与不泄露）、5.15（逃逸场景不崩且 `--json` 不变）、5.16（控制字符消毒）、5.17（glob 文件名含换行）、5.18（文件名形似分隔行时靠缩进拦住）、5.19（不内联产物正文）、5.21（换行 change 名伪造分隔行）。第 7 轮版本（51 条）存于 `.attempts/round-007/tasks.md`。
- ~~`tasks.md`（第 7 轮）：7 组 **51 条**，标注**安全**的 9 条为 1.2（共用消毒入口，含 glob 路径）、2.4（续行不得顶格，D16）、2.6（`summary`/`blockingIssues` 不得豁免消毒）、3.3（`_fail` 经同一入口、不依赖 `click.echo`）、5.13（控制字符消毒）、5.14（glob 文件名含换行）、5.15（文件名形似分隔行时靠缩进拦住）、5.16（不内联产物正文）、5.18（换行 change 名伪造分隔行）。本次不引入任何新依赖、不触及认证/授权/密钥、**不触碰 `config.yaml` 与 `WorkflowConfig`**。第 6 轮版本（42 条）存于 `.attempts/round-006/tasks.md`。
- ~~`tasks.md`（第 6 轮）：7 组 42 条。~~安全相关任务已显式标注供 `security` gate 定位——1.2（共用消毒入口，并注明消毒已是唯一防线）、2.4（`summary`/`blockingIssues` 不得豁免消毒）、3.2/3.3（错误输出改 `=== ERROR ===` 并经同一消毒入口，波及全命令）、3.5（确认未触碰 `schema_selection_required`）、5.8（控制字符消毒）、5.9（不内联产物正文）、5.13（换行伪造分隔行）。本次不引入任何新依赖、不触及认证/授权/密钥、**不触碰 `config.yaml` 与 `WorkflowConfig`**。
