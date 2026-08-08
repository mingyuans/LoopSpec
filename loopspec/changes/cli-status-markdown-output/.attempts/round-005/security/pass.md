# Security Review: PASS

## Scope Reviewed

- `loopspec/changes/cli-status-markdown-output/design.md`（D1–D15、Risks、Migration Plan、Rendered Examples）
- `loopspec/changes/cli-status-markdown-output/tasks.md`（7 组 53 条）
- `specs/status-report/spec.md`（14 条 ADDED requirement）、`specs/loopspec-cli/spec.md`、`specs/lpsx-skills/spec.md`、`specs/workflow-schema/spec.md`
- `.attempts/round-004/security/fail.md`（第 4 轮阻塞项）与被归档的 `design.md`/`tasks.md`，用于逐条核验
- 受影响的既有代码：`src/loopspec/cli.py`（`status`/`_fail`/`new` 各自的 `_fail` 调用点）、`src/loopspec/instructions.py`（`rules` 告警的实际构造点）、`src/loopspec/config.py`、`src/loopspec/models.py`、`src/loopspec/presentation.py`

## 第 4 轮阻塞项的逐条核验

**「未知配置键的告警没有出口」— 已解决，且是做出选择而非绕开选择。**

第 4 轮指出三条出口各自撞线，要求规格在三者间明确选一条。本轮 D15 选了 **stderr**，并把它撞上的那片"未定义"逐项补齐：

- **选择的理由是与既有决策的相容性**，不是随手挑一个：payload 加 `warnings` 会推翻"`--json` 契约一字不改"这条冻结决策；印进 stdout 需要同时扩充消毒需求覆盖配置键名，并在被逐条规定死的节结构里为它找位置。design 的 Rejected Options 与 `state.md` 都记下了这两条为何被否。
- **三点补齐落到了可测的 scenario**，而不是停留在设计叙述：`specs/status-report/spec.md` 新增的「配置告警写 stderr，不污染报告」给出四条 scenario——告警出现在 stderr、配与不配未知键时 stdout **逐字节相同**、`--json` 字段与未配置时完全一致、键名含控制字符时以 `\xNN` 呈现。
- **拒绝了"走 stderr 所以不用消毒"这条捷径**，理由写在 D15 与 spec 正文里：agent 通常合并捕获两个流，防线关心的是有没有文本能造出独立的一行，与文件描述符无关。这正是第 4 轮担心的那个缺口，被正面堵上了。
- **"stdout 字节不变"被写成需求而非期望**。这条是本次修复里最容易被实现悄悄绕过的地方——"走 stderr"很自然会退化成"两边各印一份"，那样等于什么都没改。把它钉成断言是对的。

`instructions` 那边 `rules` 的既有告警未被改动（任务 3.10 显式要求确认），两条命令出口不同是因响应结构不同，design 对此有说明，不构成不一致。

## Checks Performed

- **注入（分节结构 / 终端）**：防线完好且未被本轮改动削弱。消毒消灭换行 ⇒ 内插值无法开启新行 ⇒ 无法伪造 `=== SECTION ===`。新增的 stderr 通道被纳入同一条消毒规则。
- **前四轮防线在本轮扩充后完好**：D10 统一消毒规则、`summary`/`blockingIssues` 不得豁免、`_fail` 三项经同一入口、不内联产物正文、glob 压成计数、D2 单一数据通路、D12 内置说明与用户说明分两条路径、D14 拆行→逐行消毒→逐行固定缩进——逐条比对 round-004 文本，均原样保留。
- **行首内插值的封堵仍然成立**（第 3 轮确立）：唯一处于行首的内插值是节点 ID，`NodeSpec.id` 由 Pydantic 以 `KEBAB_RE` 强制校验。用户自定义说明因逐行缩进而不顶格，同时也挡住了 `--- <gate-id> ---` 这一层子分隔行。
- **新增配置字段的解析面**：`dict[str, str]`，类型不符由 Pydantic 拒为 `config_invalid`；`extra: "forbid"` 保证字段名拼错被拒而非静默忽略。无反序列化风险。
- **`config.yaml` 作为指令通道未构成扩权**：能改它的人也能改 schema 的 `instruction`。任务 6.4 已补上"该字段内容会直接进入 LLM 上下文、应与代码同等审阅"的文档要求——这条便宜且有价值，因为 `config.yaml` 在 review 中常被当作"配置"而非"代码"。
- **注入（SQL / shell / LDAP / XPath / 模板）、认证 / 授权、密钥处理、路径遍历**：均不适用或未被触碰；`status` 与本次改动只读不写。
- **第三方依赖**：无新增。

## Notes

以下均为非阻塞，不构成对本设计的反对：

1. **`_fail()` 取用配置时必须容忍"没有配置"这一状态——这是实现健壮性问题，不是安全问题，但它落在错误处理路径上，值得在实现前想清楚。** 任务 3.8 要求把配置取值传给 `cli.status` 与 `cli._fail`，但 `_fail` 有一类调用点发生在 `load_config` 本身失败之后（`cli.py:397-399`：`except LoopspecError as exc: _fail(exc, as_json)`），此时并没有 config 对象可取。`status` 侧同理（`cli.py:503-506`，`_load_change_context` 内部会 `load_config`）。实现须让 `=== ERROR ===` 的自定义说明在无配置时安全退化为"只输出内置说明"，否则错误处理路径自身会抛异常，把原始错误掩盖成一个 traceback。建议在任务 3.8 上补一句，或加一条测试：`config.yaml` 损坏时 `loopspec status <change>` 仍输出干净的 `=== ERROR ===` 报告并以退出码 1 结束。

2. **stderr 上的告警仍会进入 LLM 上下文**，design 的 Risks 已如实承认而非回避。选择 stderr 换来的是"不污染 stdout 的字节稳定性与 `--json` 契约"，不是"这段文本不进模型"。这个区分被写清楚了，后续不会有人误以为 stderr 是个安全区。

3. **`security` gate 的回退已用 2/3。** 与安全无关，但下一轮若再 FAIL 即 `exhausted`，需人工介入。记在此处供后续节点知晓。
