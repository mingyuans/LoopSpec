# Human Approval: APPROVED

## Summary Presented to the Human

第 5 轮呈现的摘要以"自第 4 轮审批以来发生了什么"为主线，因为计划的骨架人已经看过三轮：

**问题**（未变）：`loopspec status` 不带 `--json` 时走 `cli._emit()` 的 `key: value` 分支，`nodes` 被 `str()` 成一行 Python repr；真正的调用方是每轮循环执行它的 LLM，因此 `/lpsx:*` skills 只能一律加 `--json`，去解析一份塞满绝对路径的 JSON。

**自第 4 轮审批以来的三件事**：

1. **第 7 轮按第 4 轮裁定重做** `design`/`specs`/`tasks`：D4 改为 glob 列全、D5 补齐三处版式细节（续行列位、备注归属行、零匹配呈现）、新增 D16（续行不得顶格，安全约束）。重做时另修了两处历轮遗留的不一致：备注取值前几轮写作"互斥"而 `apply` 实际同时含 `taskProgress` 与 `missingDeps`（改为固定优先级）；gate 产物列前几轮一律写作紧凑 `{pass,fail}` 而历轮样例里已产出的 gate 用的是实际路径（把隐含规则写明）。
2. **`security` 第 7 轮 FAIL**，阻塞项是第 4 轮裁定直接引入的：`outputs.resolve_output_entries()` 对每个 glob 匹配返回 `path.resolve()`、**跟随符号链接**，因此 change 目录下一个指向外部的符号链接会作为合法匹配进入 `existingOutputPaths`（已实测复现，取值为 artifact 根目录之外的绝对路径）。压成计数时这些路径不进报告；列全后三条直觉实现路径分别导致 `loopspec status` 抛 traceback（一个符号链接即可让 agent 循环停摆）、把 change 目录外的路径喂进 LLM 上下文（推翻 `resolve_output_entries()` docstring 已确立的立场）、或违反 D4。
3. **第 8 轮新增 D17 解决它，`security` 第 8 轮 PASS**：相对化改为纯字符串运算；根目录之下的匹配给相对路径；逃逸的匹配给固定占位符常量 `<outside artifact root>`（不打印真实位置、不打印 `..` 形式），且仍各占一行使"有几条匹配"不丢；`status` 不得因此抛异常（须显式判断，禁止 `try/except ValueError` 兜底）；多行顺序沿用 `--json` 的 `existingOutputPaths` 数组。**未让步任何冻结决策**——第 7 轮 `fail.md` 自己建议的"让步 D2"在第 8 轮 design 中被显式讨论并拒绝，理由是 D2 禁的是第二条数据通路（重新访问文件系统或重算状态），而对 payload 里已有字符串做路径运算两者都不是。

**当前计划的规模**：决策 D1–D12 + D16 + D17 共 14 条（D13–D15 是第 3 轮撤销的，编号不复用）；`status-report` 12 条 requirement，`loopspec-cli` MODIFIED 3 条 + ADDED 1 条，`lpsx-skills` MODIFIED 1 条；任务 7 组 **57 条**，标注**安全**的 13 条，起点是 1.1 建 `src/loopspec/status_report.py`；`design.md` 末尾五份字面输出样例（正常态含多行 glob、`security` gate 失败态、glob 零匹配、含逃逸符号链接、错误输出），列对齐由脚本算出。

**安全结论**：第 8 轮 PASS，核验重点是第 7 轮阻塞项为真解决而非改写措辞，以及历轮防线（第 1 轮 `_fail` 消毒、第 3 轮行首深度防御、消毒覆盖 glob 路径、不内联产物正文）只增未减。接受的残余风险：文件名以自然语言形态进入 LLM 上下文（缓解从三层减为两层，人已在第 4 轮知情下裁定）；`--json` 的 `existingOutputPaths` 仍打印外部绝对路径（改动前的既有行为、契约冻结）；含空白路径的列边界含糊（报告不声称可机械解析）。默认输出格式变更为 BREAKING。

**两条明确提请注意的事**：① `security` 的回退额度已用满 **3/3**——若本轮要求修改，`approval` FAIL 的 reset closure 含 `security`，该 gate 会被重新判定且无回退额度，任何 FAIL 都会直接 `exhausted`；② `design.md` 剩最后一条 open question 待裁定：glob 列全**不设数量上限**，代价是大 glob 会使报告膨胀（与本变更"降低每轮 token 开销"的动机相抵），且 `security` 提醒能批量建文件的一方可用大量匹配把 `=== NEXT STEPS ===` 挤出 LLM 有效上下文。为避免第 4 轮那种答复冲突，本轮把该问题与审批判定合并为一个三选一。

## Human's Words

> approval 第 5 轮：这份计划（D1–D12 + D16 + D17、57 条任务）可以开始实现吗？三个选项已把 glob 上限那条 open question 合并进来，选一个就不会冲突。
> **批准：glob 不设上限**

该选项的完整文本为：「写 approval/approved.md，apply 解锁，按 tasks.md 从 1.1 开始实现。同时把"glob 列全不设上限"记为冻结决策，报告膨胀的代价如实接受」。

被否的两项是「要求修改：给 glob 列全设上限」与「要求修改：其他」，两者的说明中都写明了 `security` 会被重判且已无回退额度、若重判 FAIL 即 `exhausted`。

## Non-Blocking Suggestions

人未提出附加意见。以下是 `security` 与 `design` 留下的非阻塞事项，实现期与后续 change 应知晓，但不影响本次开工：

- **指向 artifact 根目录内部的符号链接**会显示其目标的相对路径而非链接自身的名字（`resolve()` 结果仍在根目录之下，走正常分支）。两者都在 change 目录内、不构成泄露，且写文件的入口是 `loopspec instructions`。要修需让 payload 携带 relative name，会动 `--json` 契约，属后续 change。
- **上下文稀释**：能在 change 目录批量建文件的一方可用大量匹配把 `=== NEXT STEPS ===` 挤出 LLM 有效上下文。判为非阻塞（能批量写 change 目录者也能改 `tasks.md` 正文，而 agent 会读那些文件），但这是"不设上限"这一裁定的已知代价。
- **`_is_artifact_candidate()` 只按未解析路径排除 `.attempts/`**，因此指向 `.attempts/` 内部的符号链接能绕过该过滤、把归档产物列回当前节点。属既有行为（压成计数时同样成立），留给后续 change。
- **D11 的已知一致性缺口**：`loopspec new` 的 `schema_selection_required` 走 `_emit` 而非 `_fail`，因此改完后非 JSON 错误输出会有 `=== ERROR ===` 与 `key: value` 两种形态。本次不修，留待后续 change。
- **loopspec 自身的解析缺陷**：`gate_outcome` 把裁决文件中 `## Blocking Issues` 之外各节的 `-` 列表项也收进 `blockingIssues`（因此 `priorAttempts` 里混着摘要条目）。与本 change 无关，留给后续。

## state.md Write-Back

- Decision Log: round 5 - approved
- Frozen Decisions: 新增两条签核点——**glob 列全不设数量上限**（报告膨胀与上下文稀释的代价如实接受，`approval` 第 5 轮裁定）；**D17 的四条取值规则**（纯字符串相对化、逃逸给固定占位符且不打印真实位置或 `..`、逃逸匹配仍各占一行、`status` 不得因此抛异常且须显式判断）。既有的 D1–D12、D16 与三份 spec 的其余条款一并签核，`apply` 阶段不得静默改动——改动它们需要再走一轮 approval。
- Open Questions: 「glob 列全是否需要数量上限」已裁定为不设，`design.md` 的 Open Questions 一节自此为空。
- Artifact Notes: approval/approved.md - approved
