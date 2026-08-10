# Security Review: FAIL

## Blocking Issues

- **`status_report_prompts` 未知键的告警没有出口，三条可能的出口各自撞上一条已冻结的约束或一片未定义行为。** D13 与 `specs/workflow-schema/spec.md` 都要求"未知节名告警但不中断，复用 `rules` 引用未知节点 ID 的既有告警通道"，但那条通道在 `status` 上并不存在——核实代码：`rules` 的未知节点告警在 `instructions.py:33-35` 构造，只进入 `loopspec instructions` 响应的 `warnings` 数组；`cli.status` 构造的 payload（`cli.py:539-552`）没有 `warnings` 字段，`cli.py:723` 那个 `warnings` 属于 `artifacts` 命令。

  于是实现者只剩三条路，每一条都越过了本变更自己划的线：

  1. **在 `status` 的 payload 里新增 `warnings`** —— 直接违反本变更反复声明的冻结决策"`--json` 的字段契约一字不改"。
  2. **把告警印进报告 stdout** —— 告警文本要内插**用户在 `config.yaml` 里写的键名**，那是一个新的内插点，而 `specs/status-report/spec.md` 的消毒需求逐项列举了它覆盖的取值（change 名、schema 名、节点 ID、路径、判定摘要、阻塞问题、`nextSteps` 文本），不含配置键名；同时报告的节结构是被逐条规定死的，这条告警该落在哪一节、是否影响"三节恒在两节条件"的判定，规格里没有任何位置容纳它。
  3. **输出到 stderr** —— 规格通篇只约束 stdout（"报告的输出字节 SHALL 与终端宽度、是否为 TTY、`NO_COLOR` 无关"），stderr 的存在与否、是否消毒、是否影响"两次渲染逐字节相同"的断言，全部未定义。

  这不是实现细节：三条路里有两条会让本变更亲手加固的那条防线出现缺口（未消毒的用户可控文本进入 LLM 上下文），第三条会推翻一条冻结决策。规格必须在这三者之间做出选择并写明，而不是留给实现者在编码时即兴决定。

## Scope Reviewed

- `loopspec/changes/cli-status-markdown-output/design.md`（D1–D14、Risks、Migration Plan、Rendered Examples、内置说明一览表）
- `loopspec/changes/cli-status-markdown-output/tasks.md`（7 组 51 条）
- `loopspec/changes/cli-status-markdown-output/proposal.md`（第 4 轮就地补充的 Capabilities 与 Impact）
- `specs/status-report/spec.md`（14 条 ADDED requirement）、`specs/loopspec-cli/spec.md`、`specs/lpsx-skills/spec.md`、`specs/workflow-schema/spec.md`（本轮新增）
- `.attempts/round-001/security/fail.md`、`.attempts/round-003/`（`approval` 第 2 轮裁决与被归档的产物），用于核验既有约束在本轮扩充后没有被稀释
- 受影响的既有代码：`src/loopspec/instructions.py`（`rules` 告警的实际构造点）、`src/loopspec/cli.py`（`status`/`_fail`/`artifacts` 各自的 payload）、`src/loopspec/models.py`（`WorkflowConfig`、`NodeSpec.id` 的 `KEBAB_RE`）、`src/loopspec/presentation.py`

## Checks Performed

- **前三轮的既有防线在本轮扩充后完好**：D10 的统一消毒规则、`summary`/`blockingIssues` 不得豁免、`_fail` 三项经同一消毒入口、不内联产物正文、glob 压成计数、D2 的单一数据通路——逐条比对第 3 轮文本，均原样保留。第 1 轮阻塞项的四个落点仍在。
- **D14 的多行处理在正常路径上是正确的**：按 `\n` 拆行 → 逐行消毒 → 逐行固定缩进，换行由渲染器产生而非从内插值穿透。缩进使任何一行都不顶格，因而无法伪造分隔行。spec 明写"固定缩进 SHALL NOT 被省略"，把这一点钉成了需求而不是实现习惯。
- **内置说明不经消毒是正确的**，且 D12 与任务 1.6/1.7 把它与用户说明分成了两条路径，而不是"反正都过一遍"——后者会让实现看不出哪一条才是防线所在。
- **`config.yaml` 作为指令通道未构成扩权**：能改 `config.yaml` 的人也能改 schema 的 `instruction`（那已是直接指挥 LLM 的通道），因此本项没有给攻击者新的能力。见 Notes 第 1 条的补充建议。
- **新增配置字段的解析面**：`dict[str, str]`，类型不符（如写成列表）由 Pydantic 拒为 `config_invalid`；`WorkflowConfig` 的 `extra: "forbid"` 保证字段名拼错会被拒绝而非静默忽略。无反序列化风险。
- **注入（SQL / shell / LDAP / XPath / 模板）**：不适用，改动不构造查询、不启动子进程、不做模板求值。
- **认证 / 授权、密钥处理、路径遍历**：均不适用或未被触碰；`status` 与本次改动只读不写。
- **第三方依赖**：无新增。

## Recommended Fix Direction

在三条出口里选一条并写进规格，把选择的理由一并写下——这个选择同时决定了"用户可控文本会不会以未消毒形态进入 LLM 上下文"。

从与既有决策的相容性看，**stderr 是冲突最少的方向**：它不碰 `--json` 契约，不改报告的节结构，也不影响 stdout 的字节稳定性断言（那些断言只看 stdout）。若选它，规格需补齐三点：告警走 stderr 而非 stdout；告警文本中的配置键名同样经消毒（stderr 也会被 agent 捕获并进入上下文，"不是报告"不等于"不进 LLM"）；以及明确 stdout 的字节不因告警的有无而改变。

若选"印进报告"，则必须同时扩充 `specs/status-report/spec.md` 的消毒需求使其覆盖配置键名，并明确该告警在节结构中的确切位置及其对"三节恒在两节条件"判定的影响。

若选"静默忽略"（不告警），需要正面论证为何用户拼错键名得不到任何反馈是可接受的，并相应修改 `specs/workflow-schema/spec.md` 中那条"告警但不中断"的 scenario——不要让规格里留着一条实现不打算满足的需求。
