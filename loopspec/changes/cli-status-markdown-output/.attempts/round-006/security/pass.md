# Security Review: PASS

## Scope Reviewed

- `loopspec/changes/cli-status-markdown-output/design.md`（D1–D12、Risks、Migration Plan、Rendered Examples）
- `loopspec/changes/cli-status-markdown-output/tasks.md`（7 组 42 条）
- `loopspec/changes/cli-status-markdown-output/proposal.md`（第 6 轮就地修改的 Capabilities 与 Impact）
- `specs/status-report/spec.md`（11 条 ADDED requirement）、`specs/loopspec-cli/spec.md`、`specs/lpsx-skills/spec.md`
- `.attempts/round-005/`（被撤销功能的完整设计、规格与第 5 轮 PASS 判定）与 `.attempts/round-004/security/fail.md`，用于逐条比对撤销范围
- 受影响的既有代码：`src/loopspec/cli.py`、`src/loopspec/presentation.py`、`src/loopspec/models.py`

## 本轮的核心问题：撤销有没有误删安全约束

`approval` 第 3 轮撤销了 `config.yaml` 自定义分节说明整项功能。范围收窄本身不产生新的攻击面，因此本轮唯一值得花力气的问题是：**删的时候有没有把不属于这项功能的东西一并带走。** 裁决文件本身点名了两处必须保住的（D10 的核心防线、D7 的共用消毒入口），逐条核验：

- **D10 完好。** `design.md` 的 D10 原文仍在，包含实测复现、"不能指望 `click.echo` 兜底"、以及"消毒是唯一那道结构防线"的结论。`state.md` 的 Frozen Decisions 中 D10 未被划除。
- **D7 完好。** `_fail()` 三项内插值经同一消毒入口的要求仍在 design 与 `specs/loopspec-cli/spec.md` 第 19 行，「含换行的 change 名无法在错误输出中伪造分节行」这条 scenario 也仍在（第 33 行）。
- **`specs/status-report/spec.md` 的「内插值的控制字符消毒」只改了一句措辞**——内置说明为常量故不消毒的理由，从"与自定义说明是两条独立路径"改为"消毒只适用于从数据中取出的内插值"。requirement 的规范内容、"唯一结构防线"的定性、"任何字段不得豁免"、以及两条 scenario 全部原样。这是本次撤销里唯一触碰消毒规格的地方，改动是必要且最小的。
- **安全任务全部保留**：1.2（共用消毒入口 + 唯一防线的说明）、2.4（`summary`/`blockingIssues` 不得豁免）、3.3（`_fail` 经同一入口 + 不依赖 `click.echo`）、5.8（控制字符消毒）、5.9（不内联产物正文）、5.13（换行伪造分隔行）。被删的 13 条任务全部只服务于被撤销的功能。
- **无悬空引用**：`specs/workflow-schema/spec.md` 已删除，且 `specs/` 与 `design.md` 中不存在指向它的引用；`status-report` 与 `loopspec-cli` 之间的互引仍指向实际存在的 requirement。

## Checks Performed

- **注入（分节结构 / 终端）**：防线未被削弱。消毒消灭换行 ⇒ 内插值无法开启新行 ⇒ 无法伪造 `=== SECTION ===` 分隔行。撤销后报告回到"全部内插值均为单行消毒"，比上一轮更简单——不再存在被允许产生多行输出的内插来源。
- **行首内插值的封堵仍然成立**（第 3 轮确立）：唯一处于行首的内插值是节点 ID，`NodeSpec.id` 由 Pydantic 以 `KEBAB_RE` 强制校验。内置说明是代码常量，不携带外部输入，因此它出现在行首不构成暴露。
- **攻击面净减少**：`config.yaml` 与 `WorkflowConfig` 不再被触碰，随之消失的有——用户可控文本进入报告的新通道、stderr 这条新输出路径、以及 `_fail` 对配置对象的新依赖（后者曾是第 5 轮 Notes 里那个"错误处理路径自身可能抛异常"的隐患，现已随功能一并消失，未留下无主补丁）。
- **注入（SQL / shell / LDAP / XPath / 模板）、认证 / 授权、密钥处理、路径遍历**：均不适用或未被触碰；`status` 与本次改动只读不写。
- **第三方依赖**：无新增。
- **内置说明（D12，保留项）的安全性**：说明文本是代码常量，不经消毒是正确的；它不携带任何外部输入，因此既不构成注入面，也不需要走消毒路径。spec 对此的表述在本轮修订后仍然准确。

## Notes

1. **本轮是三轮里唯一一次攻击面**减少**的改动。** 前几轮每次扩充功能都要新增防线，这次撤销把"唯一允许多行输出的内插来源"和"新增的 stderr 输出路径"一并移除，规格因此回到一个更容易论证的状态：报告的每一个内插值都是单行、都经同一条消毒规则、都不在行首。

2. **被撤销的设计完整保存在 `.attempts/round-005/`**，包括 `specs/workflow-schema/spec.md` 与第 5 轮的 PASS 判定。若日后重启该功能，D15 关于"三条告警出口各自撞线"的分析与"走 stderr 不等于不进模型"的结论可直接复用，不必重新踩一遍。

3. **`security` gate 的回退已用 2/3**，与安全无关，记在此处供后续节点知晓。
