# Security Review: PASS

## Scope Reviewed

- `loopspec/changes/cli-status-markdown-output/design.md`（D1–D11、Risks、Migration Plan、Rendered Examples）
- `loopspec/changes/cli-status-markdown-output/tasks.md`（7 组 39 条）
- `loopspec/changes/cli-status-markdown-output/specs/status-report/spec.md`（第 3 轮整份重写，11 条 ADDED requirement）、`specs/loopspec-cli/spec.md`、`specs/lpsx-skills/spec.md`
- `.attempts/round-001/security/fail.md`（第 1 轮阻塞项）与 `.attempts/round-002/`（`approval` 第 1 轮裁决及被归档的三份 spec），用于核验重写过程中没有丢东西
- 受影响的既有代码：`src/loopspec/cli.py`（`_emit`/`_fail`/`status`/`new`）、`src/loopspec/presentation.py`（`sanitize`）、`src/loopspec/models.py`（`NodeSpec.id` 的校验）、`src/loopspec/errors.py`、`src/loopspec/paths.py`

## 本轮的核心问题：整份重写后防线是否还在

`approval` 第 1 轮把报告从 Markdown 改成 `=== SECTION ===` 纯文本，三份 spec 被整份重写。重写是丢失安全约束最常见的场合，因此本轮把重点放在逐条比对而非重新论证。

**第 1 轮阻塞项（错误输出缺消毒要求）在重写后完好。** 四个落点逐一核对：`design.md` D7 保留"三项内插值 SHALL 经 `sanitize()`"、D10 保留并强化；`specs/loopspec-cli/spec.md`「统一错误输出格式」的消毒条款与「含换行的 change 名无法在错误输出中伪造分节行」scenario 都在，只是把目标从 `## Next Steps` 改写为 `=== NEXT STEPS ===`；`specs/status-report/spec.md`「内插值的控制字符消毒」保留"同一实现供错误输出复用"；`tasks.md` 1.2/3.3/5.13 保留。

**`|` 转义要求的移除是正当的，不是稀释。** 它随 Markdown 表格取消而失去对象：新形态下 `|` 不再承担任何结构作用——节点清单用空白分隔，gate 产物用 `{pass,fail}` 紧凑形式而非 `a | b`。核对新 spec 全文，`|` 只出现在"Markdown 表格分隔行不应出现"这条否定式 scenario 里。移除后无遗留攻击面。

**消毒的地位反而上升了，且 design 如实写明。** D10 明确指出：取消表格后消毒从"两道防线之一"变成"唯一那道"，`tasks.md` 1.2 要求把这句话写进模块文档，防止日后被当作美化而移除。这正是重写中最该保住的东西，它被保住了。

## Checks Performed

- **注入（分节结构 / 终端）**：防线成立。消毒消灭换行 ⇒ 内插值无法开启新行 ⇒ 无法伪造 `=== SECTION ===` 分隔行。
- **新形态下"行首内插值"这一唯一暴露点已被封堵**（本轮新增核验）：分隔行必须独占一行才能生效，因此只有出现在行首的内插值才有伪造可能。逐节点核对——`=== OVERVIEW ===`、`=== PENDING ROLLBACK ===`、`=== ERROR ===` 各行都有标签前缀；`=== NEXT STEPS ===` 各条有编号前缀；`blocking issues` 有编号加两格缩进；`=== NODES ===` 的产物与备注列前面都有内容。唯一真正处于行首的内插值是**节点 ID**（节点行首列，以及 `--- <gate-id> ---`），而 `NodeSpec.id` 由 Pydantic 以 `KEBAB_RE`（`^[a-z][a-z0-9]*(-[a-z0-9]+)*$`）强制校验，不可能含空格、`=` 或换行。即使消毒失效，行首也造不出分隔行。
- **注入（SQL / shell / LDAP / XPath / 模板）**：不适用。改动不构造查询、不启动子进程、不做模板求值。
- **认证 / 授权**：不适用，本地 CLI，改动未新增此类面。
- **密钥处理**：无硬编码凭据，不读环境变量、不写日志。
- **路径遍历**：`status` 与本次改动只读不写，不新增由外部输入决定的写入路径；`paths.resolve_within` 的既有防护未被触碰。
- **反序列化 / 解析不可信输入**：不新增解析器；D2 明确禁止渲染器重新访问文件系统。
- **第三方依赖**：无新增。D1 明确新模块不经 rich `Console`。
- **数据暴露 / prompt injection**：三层缓解（不内联产物正文、全值消毒、glob 压成计数）在重写后完好，`tasks.md` 5.9 有对应测试。
- **本轮新决策是否引入新风险**：D5 的 gate 紧凑路径形式与"不声称可机械解析"的立场逐条检查，结论见 Notes 第 1、2 条。

## Notes

以下均为非阻塞，不构成对本设计的反对：

1. **gate 紧凑路径 `<dir>/{pass,fail}.<ext>` 的误用后果是 fail-safe 的——这是它可以通过的理由，值得记下来。** LLM 有可能把 `approval/{approved,changes-requested}.md` 当字面路径去写文件。核验后果：`gate_outcome` 按具体文件名判定 pass/fail，因此写到花括号字面名只会让流程**卡住**（gate 保持 `ready`），不会让 gate 被误判为通过；`paths` 层的逃逸防护也保证该名字出不了 change 目录。若这个失败方向反过来（误写能让 gate 通过），这一条就该是阻塞项。spec 已写明它是显示形式、实际路径取自 `instructions`，可以接受。

2. **"不声称可机械解析"是安全上更稳的立场，不只是设计口味。** 若反过来给纯文本加一层引号/转义协议，就等于新增一个解析契约，而任何解析契约都会带来歧义与解析歧义类漏洞。D5 选择承认列边界不可靠、把精确解析推给 `--json`，减少了攻击面而非增加。

3. **建议把"内插值不出现在行首"固化为实现约束与测试**（对应上面的核验）。它当前是天然成立的，但没有任何东西阻止后续改动把某个字段挪到行首。一条注释加一条测试即可把这道免费的深度防御钉住。属实现建议，不影响本轮判定。

4. **`schema_selection_required`（D11）维持现状仍然可接受。** 复核理由：`loopspec new` 在 `_KEBAB.match()` 之后才可能到达该路径，change 名不含换行；`schemas`/`selectionInstruction` 来自 `config.yaml`（可信）；输出非报告形态，不会被当作分节信号。design 已把这段理由显式写入，不再是含混带过。

5. **D2 的字段覆盖断言按并集实现这一点已落到 spec**（`status-report` 最后一条 requirement 与 `tasks.md` 5.7）。第 2 轮以 Notes 形式提出的实现坑，本轮已被固化为规范文本。
