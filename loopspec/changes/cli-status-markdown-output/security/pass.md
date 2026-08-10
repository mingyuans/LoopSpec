# Security Review: PASS

## Scope Reviewed

- `loopspec/changes/cli-status-markdown-output/design.md`（第 8 轮：Context 的 `existingOutputPaths` 性质说明与实测、D1–D12 + D16 + **新增 D17**、Risks、Migration Plan、五份 Rendered Examples）
- `loopspec/changes/cli-status-markdown-output/tasks.md`（第 8 轮：7 组 57 条，其中标注**安全**的 13 条）
- `specs/status-report/spec.md`（12 条 requirement，本轮就地补入 D17 的四条规范 bullet 与三条 scenario——`security` gate 的 reset closure 不含 `specs`，故它未被回退归档）、`specs/loopspec-cli/spec.md`、`specs/lpsx-skills/spec.md`、`proposal.md`
- `.attempts/round-007/`（上一轮的 design、tasks 与本 gate 自己的 `fail.md`），用于逐条核对阻塞项是否真的被解决而非改写措辞
- 受影响的既有代码：`src/loopspec/outputs.py`（`resolve_output_entries`/`resolve_outputs`/`_is_artifact_candidate`/`resolved_output_path`）、`src/loopspec/cli.py`、`src/loopspec/presentation.py`、`src/loopspec/gate_outcome.py`

## 第 7 轮阻塞项的核验（本轮唯一必须回答的问题）

上一轮 FAIL 的阻塞项是：`existingOutputPaths` 跟随符号链接、可能给出 artifact 根目录之外的绝对路径，而"glob 节点列出相对路径"对这种匹配没有定义，实现三条直觉路径分别导致 traceback、外部路径泄露、或违反 D4。逐条核验本轮是否真的解决：

- **取值规则已明文裁定，不再留给实现。** D17 给出四条：相对化是纯字符串运算；根目录之下的匹配给相对路径；不在其下的匹配给固定占位符常量 `<outside artifact root>`，且 SHALL NOT 打印解析后的真实位置或 `..` 形式；逃逸的匹配仍各占一行。`specs/status-report/spec.md` 的「NODES 节」requirement 已就地补入对应的四条规范 bullet，并新增三条 scenario（占位符呈现、`status` 不因此失败、多行顺序与 `--json` 一致）。这不是措辞改写：上一轮 spec 里完全没有"artifact 根目录之外"这个概念。
- **崩溃这条底线被写成了实现约束而非期望。** tasks 2.5 明确要求用**显式判断**处理，并禁止用 `try/except ValueError` 兜底 `Path.relative_to`；spec 亦有对应条款与 scenario（5.15 断言退出码为 0、无 traceback）。禁止兜底捕获是对的：那会把"外部路径"与其他 `ValueError` 混为一谈，日后新增的真实错误会被同一个 `except` 静默吞掉。
- **泄露这条与既有代码立场对齐。** D17 引用了 `resolve_output_entries()` docstring 里"报告一条被拒绝的路径时不必打印它实际指向哪里"这一既有立场，并据此选择占位符。占位符是**代码常量**，因此不携带外部内容、不需消毒——这个判断与 D12 内置说明的处理方式一致，不是为它开的特例。
- **本轮没有为了修这个问题而让步任何冻结决策**，这一点比上一轮 `fail.md` 里我自己给的方向（"最该让步的是 D2"）更好，且理由站得住：D2 禁的是渲染器自行访问文件系统或重算状态（第二条数据通路），而对 payload 里已有的字符串做路径运算既不访问磁盘也不重算状态。`--json` 契约同样未被触碰。上一轮的建议在 design 中被显式讨论并拒绝，而不是被忽略。
- **顺序被钉住。** 第 7 轮 Notes ② 建议把顺序写死为"与 `--json` 的 `existingOutputPaths` 一致"，本轮 D17 与 spec 均已如此规定（tasks 2.3 与 5.6 对应）。这条虽非安全问题，但两种输出顺序不一致会侵蚀"信息相同"这一约定，顺手解决是对的。

## Checks Performed

- **注入（报告结构 / 终端）**：三道防线齐备且分层清楚。① 消毒（D10）是唯一的结构防线，覆盖范围显式含 glob 匹配路径（spec 的消毒 requirement 逐项列举，tasks 1.2/5.16/5.17）；② 行首约束（D16）是深度防御，实测证明必要——`=== NEXT STEPS ===.md` 这类文件名能进入 `existingOutputPaths` 且不含控制字符，消毒对它完全无效，唯一拦住它的就是续行缩进（tasks 2.6/5.18）；③ D17 使外部路径根本不进报告，进一步缩小可控文本。三者互不替代，design 与 spec 都如实这么表述。
- **数据暴露 / 路径泄露**：默认输出这条新增暴露面已被 D17 收紧到"只出现 artifact 根目录之下的相对路径与常量占位符"。`--json` 的 `existingOutputPaths` 仍打印外部绝对路径，design 如实记录为**改动前的既有行为 + 契约冻结**，没有借本次改动含混掩盖，也没有虚称 loopspec 从此不泄露外部路径。这个诚实的边界划法是可接受的：`--json` 的消费者是程序，且本次未扩大该行为。
- **可用性（拒绝服务）**：`status` 是 agent 循环唯一的状态入口，本轮把"不得因一个符号链接而抛 traceback"写成了底线要求并配可测 scenario。这是本轮最实质的收益——上一轮的规格照直觉实现就会踩。
- **prompt injection 面**：`glob` 列全使进入上下文的文件**名**变多，缓解从三层减为两层（不内联正文 + 全值消毒），design 的 Risks 如实记录并说明人已在知情下裁定；「不内联产物正文」这条边界被加强而非放宽（spec 明写 SHALL NOT 以任何理由放宽，tasks 5.19）。
- **路径遍历**：`status` 与本次改动只读不写，不新增任何写入路径；D17 处理的正是"读到的路径逃出预期目录"这一情形。
- **认证 / 授权 / 密钥处理 / 反序列化 / SQL / shell / LDAP / XPath / 模板注入**：均不适用或未被触碰。`config.yaml` 与 `WorkflowConfig` 完全未被触碰（`approval` 第 3 轮撤销的结果，本轮复查无残留）。
- **第三方依赖**：无新增。
- **历轮阻塞项未被重写弄丢**：第 1 轮（`_fail` 三项经共用消毒入口 + 含换行 change 名的 scenario）见 D7/D10、`specs/loopspec-cli/spec.md`、tasks 3.3/5.21；第 3 轮确立的行首深度防御见 D16；第 4 轮那条随功能撤销而消失，无无主补丁。逐条比对 `.attempts/round-007/` 与当前版本，安全相关条款只增未减。

## Notes（非阻塞，供 `approval` 与后续 change 参考）

1. **指向 artifact 根目录内部的符号链接会显示其目标的相对路径，而不是链接自身的名字**（`resolve()` 的结果仍在根目录之下，因此走正常分支）。后果是报告里的路径与 glob 匹配到的文件名可能不一致。判为非阻塞：两者都在 change 目录内、都不构成泄露，且写文件的入口是 `loopspec instructions`（它给绝对路径），LLM 照报告去猜路径本就不是设计中的用法。若日后要修，出口是让 payload 同时携带 relative name——那会动 `--json` 契约，属另一个 change。
2. **上下文稀释**（第 7 轮 Notes ① 的延续）：能在 change 目录批量建文件的一方可以用大量匹配把 `=== NEXT STEPS ===` 挤出 LLM 的有效上下文窗口。仍判非阻塞（能批量写 change 目录者也能改 `tasks.md` 正文，而 agent 会读那些文件），但请 `approval` 在裁定"glob 列全是否要设上限"这个 open question 时把它算进去。
3. **`_is_artifact_candidate()` 只按未解析路径排除 `.attempts/`**，因此指向 `.attempts/` 内部的符号链接能绕过该过滤，把归档产物列回当前节点。属既有行为（压成计数时同样成立），与本次改动无关，留给后续 change。
4. `resolve_outputs()` 的排序键是解析后的绝对路径，因此一条逃逸的匹配会按其目标路径排序、可能出现在中间行。顺序仍是确定的（不影响"两次渲染逐字节相同"），且本轮已要求报告与 `--json` 顺序一致，无需额外处理。
5. **本 gate 的回退已用满 3/3。** 本轮 PASS 使流程进入 `approval` 第 5 轮；此后若 `approval` 再要求修改，其 reset closure 含 `security`，`security` 将被重新判定但**已无回退额度**——届时任何 `security` FAIL 都会直接使该 gate `exhausted`。请 `approval` 在裁定时把这一点考虑进去：需要改的内容越是触及消毒、行首、路径取值这三处，越应该在这一轮一次说清。
