# Security Review: PASS

## Scope Reviewed

- `loopspec/changes/cli-status-markdown-output/design.md`（D1–D11、Risks、Migration Plan）
- `loopspec/changes/cli-status-markdown-output/tasks.md`（7 组 33 条）
- `loopspec/changes/cli-status-markdown-output/specs/status-report/spec.md`、`specs/loopspec-cli/spec.md`、`specs/lpsx-skills/spec.md`
- 第 1 轮判定 `.attempts/round-001/security/fail.md` 与被归档的 `design.md`/`tasks.md`，用于逐条核验
- 受影响的既有代码：`src/loopspec/cli.py`（`_emit`/`_fail`/`status`/`new`）、`src/loopspec/presentation.py`（`sanitize`）、`src/loopspec/errors.py`、`src/loopspec/paths.py`

## 第 1 轮阻塞项的逐条核验

**「错误输出的 Markdown 化没有消毒要求，可被换行伪造节标题」— 已解决，且是实质修复而非改写措辞。**

修复落到了四个可检查的位置，而不只是在 design 里加一句提醒：

- `design.md` D10 把消毒从"`status-report` 一家的规则"提升为**输出层的统一规则**，并给出一次性定义、两处调用的具体形态（复用 `presentation.sanitize()`）。
- `design.md` D7 补上"`error`/`message`/`fix` 三项在渲染前 SHALL 经 `sanitize()`"。
- `specs/loopspec-cli/spec.md`「统一错误输出格式」新增规范条款（同一条规则、同一个实现、不得依赖框架的 ANSI 剥离兜底）与一条可测 scenario：含换行的 change 名不得在错误输出中产生新的行首 `#`。
- `specs/status-report/spec.md` 反向补上"消毒是核心结构防线、同一实现供错误输出复用、任何字段不得豁免"，并新增一条多行 gate 文本的 scenario。
- `tasks.md` 1.2（共用消毒入口）、3.3（`_fail` 三项经该入口）、5.11（针对性测试）落到实现与测试。

修复没有走"只在 `status` 的错误路径上消毒"这条最小路径——`design.md` 的 Rejected Options 明确记录了否决理由（`_fail()` 全命令共用，那样会让同一函数对不同命令有不同安全等级）。这是本轮最想看到的判断。

## Checks Performed

- **注入（Markdown 结构 / 终端）**：核心防线成立且现已被写成规范——`sanitize()` 消灭换行 ⇒ 内插值无法开启新行 ⇒ 无法伪造 `## Section`。表格场景由 `|` → `\|` 补齐。报告与错误输出共用同一实现，无第二套标准。
- **注入（SQL / shell / LDAP / XPath / 模板）**：不适用。改动不构造查询、不启动子进程、不做模板求值。
- **认证 / 授权**：不适用，本地 CLI，改动未新增此类面。
- **密钥处理**：无硬编码凭据，不读环境变量、不写日志。
- **路径遍历**：`status` 与本次改动只读不写，不新增由外部输入决定的写入路径；`paths.resolve_within` 的既有防护未被触碰。
- **反序列化 / 解析不可信输入**：不新增解析器；D2 明确禁止渲染器重新访问文件系统，报告只消费已构造的 dict。
- **第三方依赖**：无新增。D1 明确新模块不经 rich `Console`，既有依赖的使用面在收窄。
- **数据暴露 / prompt injection**：三层缓解（不内联产物正文、全值消毒、glob 压成计数）保留完好，5.7 有对应测试。
- **第 1 轮通过项未被本轮稀释**：`|` 转义（D5）、不内联产物正文、glob 计数、D2 的单一数据通路、无新增依赖——逐条比对第 2 轮文本，均原样保留或加强。
- **本轮新增内容是否引入新风险**：D10、D11 与新增任务逐条检查，未发现新增攻击面。两处需要注意的推论已写入下方 Notes。

## Notes

以下均为非阻塞的实现提醒，不构成对本设计的反对：

1. **代码块方案的安全性同样依赖消毒。** D10 说可读性成问题时可把多行的 `summary`/`blockingIssues` 包进 Markdown 代码块。该方案是安全的，但理由必须说清：正因为消毒已消灭换行，内容里的 ` ``` ` 无法自成一行，也就无法提前关闭代码块。实现者若选此路，不要以为代码块本身提供了隔离——隔离仍来自消毒。

2. **`nextSteps` 文本同样要过消毒。** `policy.build_next_steps` 生成的字符串里内插了 change 名（如 "Run \`loopspec status <change>\`"），因此它是携带外部输入的字段，而不是纯粹由 CLI 控制的常量。spec 的消毒条款以"等"字覆盖了它，实现时不要因为"这是我们自己生成的文案"而跳过。

3. **`schema_selection_required` 路径（D11）维持现状是可接受的。** 该路径走 `_emit` 而非 `_fail`，本次不改。核验其风险未被加剧：`loopspec new` 在 `_KEBAB.match()` 之后才可能走到这里，change 名不可能含换行；schema 名来自 `config.yaml`（可信输入）；且其输出不是 Markdown 报告形态，不会被 LLM 当作节标题读。后续 change 收口时一并处理即可。

4. **D2 的字段覆盖断言需按并集实现。** 节点字段是条件性的（`taskProgress`/`gate`/`missingDeps` 只在特定状态出现），断言"相等"时应取全部节点字段的并集，否则测试会在正常情况下误报。属实现细节，与安全无关，记在此处以免 5.6 落地时踩坑。
