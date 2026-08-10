# Security Review: FAIL

## Blocking Issues

- **`existingOutputPaths` 里可能出现 artifact 根目录之外的绝对路径，而 D4/D5 与 `specs/status-report/spec.md` 只要求"glob 节点列出全部匹配文件的**相对**路径"，未规定这种情形该如何取值与呈现。** `outputs.resolve_output_entries()` 对每个匹配都返回 `path.resolve()`，**跟随符号链接**；`_is_artifact_candidate()` 只用未解析的路径排除 `.attempts/` 与保留名，因此指向 change 目录之外的符号链接会被当作合法匹配。实测（`loopspec status probe --json`，在 `specs/cap/` 下放一个指向 change 外文件的 `link.md`）：

  ```
  existingOutputPaths: [
    ".../changes/probe/specs/cap/=== NEXT STEPS ===.md",
    ".../symlink-probe/outside-secret.md"        ← artifact root 之外
  ]
  ```

  上一轮把这些路径压成 `(3 files)`，它们根本不进报告；改为逐条列出后，实现必须把每条绝对路径转成相对形式，而三条路走向三种坏结果：① `Path.relative_to(artifact_root)` 对逃逸路径抛 `ValueError`，`loopspec status` 变成 traceback 而不是 `=== ERROR ===`——任何能在 change 目录下放一个外部符号链接的人都能让整个 agent 循环卡死（读不到状态就走不到下一步）；② `os.path.relpath()` 会输出 `../../../outside-secret.md`，把 artifact root 之外的路径写进 LLM 上下文，而 `resolve_output_entries()` 的 docstring 明写它保留 relative name 正是为了"报告一条被拒绝的路径时不必打印它实际指向哪里"——直接相对化等于推翻既有代码写下的立场；③ 原样打印绝对路径则违反 D4"节点行给相对路径"。

- **上一条无法留给实现自行决定，因为两条冻结决策把出路堵住了，必须由 design 裁定。** D2 冻结了"渲染器只读 `status` 已构造的 payload，SHALL NOT 另行访问文件系统"，而 payload 里只有 `resolve()` 后的绝对路径，没有 `resolve_output_entries()` 那份未跟随符号链接的 relative name；"`--json` 字段契约一字不改"又排除了往 payload 里加一个相对名字段。design SHALL 明确裁定这三者中放弃哪一条（或给出第四条路），并把结论写进 `specs/status-report/spec.md` 的「NODES 节」requirement 与配套 scenario，而不是只在 design 里提一句。

- **裁定后 SHALL 补一条针对逃逸路径的可测 scenario 与对应任务。** 至少覆盖：change 目录下存在一个指向外部的符号链接匹配时，`loopspec status`（不带 `--json`）SHALL 正常退出（不得 traceback），且报告 SHALL NOT 打印该链接解析后的真实位置。当前 `tasks.md` 的 5.5/5.6/5.7/5.13/5.14/5.15 六条 glob 相关测试没有一条覆盖符号链接。

## Scope Reviewed

- `loopspec/changes/cli-status-markdown-output/design.md`（第 7 轮：D1–D12 + 新增 D16、Risks、Migration Plan、四份 Rendered Examples）
- `loopspec/changes/cli-status-markdown-output/tasks.md`（第 7 轮：7 组 51 条，其中标注**安全**的 9 条）
- `loopspec/changes/cli-status-markdown-output/proposal.md`
- `specs/status-report/spec.md`（12 条 ADDED requirement）、`specs/loopspec-cli/spec.md`、`specs/lpsx-skills/spec.md`
- `.attempts/round-006/`（上一轮设计与规格，用于逐条比对本轮改动范围）与 `approval/changes-requested.md` 第 4 轮裁决（已归档至 round-006）
- 受影响的既有代码：`src/loopspec/outputs.py`（`resolve_output_entries`/`resolve_outputs`/`_is_artifact_candidate`）、`src/loopspec/cli.py`、`src/loopspec/presentation.py`、`src/loopspec/gate_outcome.py`
- 实测：在临时 workflow home 下构造 `specs/cap/link.md`（指向 change 外文件）与 `specs/cap/=== NEXT STEPS ===.md`，读取 `loopspec status --json` 的 `existingOutputPaths` 实际取值

## 本轮通过项（重做时 SHALL 原样保留）

以下均已逐条核验，**不在**本次阻塞范围内，下一轮不要连带改动：

- **D10 的核心防线完好**，且消毒覆盖范围已按本轮新增的攻击面**正确扩写**：`specs/status-report/spec.md` 的「内插值的控制字符消毒」显式列举了"glob 节点逐条列出的每一个匹配文件路径"，并写明理由（此前压成计数、根本不进报告）。tasks 1.2 同步点明。这正是本轮应该做的事。
- **D16（行首内插值限于经校验的节点 ID）是对的，而且必要。** 实测确认 `=== NEXT STEPS ===.md` 这类文件名**能**进入 `existingOutputPaths`，且其中无任何控制字符——消毒对它完全无效。唯一拦住它的就是"续行必须缩进"。这条被写成 spec requirement + 两条 scenario + tasks 2.4/5.15，层次正确；它被明确定性为深度防御而非消毒的替代，表述也准确。
- **D7 的共用消毒入口与「含换行的 change 名无法在错误输出中伪造分节行」scenario 完好**（`specs/loopspec-cli/spec.md`、tasks 3.3/5.18），仍是第 1 轮阻塞项的修复成果。
- **「不内联产物正文」这条边界被加强而非放宽**：spec 补了"文件名变多故这条边界比以往更重要，SHALL NOT 以任何理由放宽"，tasks 5.16 保留。
- **Risks 如实记录了缓解层数从三层减为两层**，没有用"路径本来就会出现"含混带过，并指明人已在知情下裁定。这是本轮 Risks 写得最好的一处。
- **`loopspec-cli` 里那句"默认输出可对列表类字段做计数式压缩"被删除**是正确的连带修改——留着它就等于规格自己给被否决的 glob 计数留了后门。
- 无新增第三方依赖；不触及认证/授权/密钥；`config.yaml` 与 `WorkflowConfig` 未被触碰；`status` 与本次改动只读不写，无新增写入路径。
- SQL / shell / LDAP / XPath / 模板注入、反序列化：均不适用。

## Recommended Fix Direction

- 三条冻结决策里最该让步的是 **D2 的"渲染器只读 payload"**，而不是 `--json` 契约或"节点行给相对路径"：D2 的立法目的是防止**第二条数据通路**造成两种输出漂移（渲染器自行重算节点状态），而"把已经在 payload 里的绝对路径转成相对形式"是纯字符串计算，不重算任何状态、不引入第二份真相。可行的裁定是明确"渲染器可以做纯路径字符串运算，但仍 SHALL NOT 访问文件系统或重算状态"，并规定相对化失败（结果需要 `..` 才能表达）时的呈现方式。
- 逃逸路径的呈现建议与既有的 `archive_unsafe` 立场对齐：**只给它在 artifact root 下的那个名字（即 glob 匹配到的链接自身的相对路径），不打印解析后的目标**。既有代码保留 relative name 就是为此。若渲染器只能拿到解析后的绝对路径，那这条就构成"payload 缺少必要信息"的论据，可据此重新审视是否真要死守 `--json` 一字不改——但那是 design 的裁定权，本 gate 不代劳。
- 无论怎么裁定，**`loopspec status` 都 SHALL NOT 因为 change 目录里的一个符号链接而抛 traceback**。这条是底线：`status` 是 agent 循环的唯一状态入口，它崩掉等于整条流程停摆，而触发条件只是"在 change 目录下建一个符号链接"。

## Notes（非阻塞，供下一轮与 `approval` 参考）

1. **glob 列全带来一个新的上下文层面风险**，与上限那个 open question 相关：攻击者若能在 change 目录批量创建文件，节点清单会膨胀到把 `=== NEXT STEPS ===` 挤出 LLM 的有效上下文窗口——报告的结构信号还在，但读者可能读不到它。这不是注入而是稀释，后果是流程混乱而非直接受控；且能批量写 change 目录的人也能改 `tasks.md` 正文（agent 会去读那些文件）。因此判为非阻塞，但请 `approval` 在裁定"是否设上限"时把这一点算进去。
2. `resolve_outputs()` 的排序键是**解析后的绝对路径**（`sorted(..., key=entry[1])`），因此一个指向外部的符号链接会按其目标路径排序，节点行的顺序未必与文件名字典序一致。输出仍是确定的（不影响"两次渲染逐字节相同"），只是顺序对读者略反直觉。建议下一轮在 spec 里把顺序写死为"与 `--json` 的 `existingOutputPaths` 数组一致"，避免实现自行排序造成两种输出不一致。
3. `_is_artifact_candidate()` 只按未解析路径排除 `.attempts/`，因此**指向 `.attempts/` 内部的符号链接**能绕过该过滤、把归档产物重新列进当前节点。属既有行为（与本次改动无关，压成计数时同样成立），不在本次范围，留给后续 change。
4. 第 4 轮那条阻塞项（配置告警出口）随 `approval` 第 3 轮撤销整项功能而消失，本轮复查未发现任何残留的无主补丁。
5. **本 gate 的回退在本次 FAIL 后将用满 3/3**：下一轮 `security` 若再 FAIL 即 `exhausted`，届时无法再回退。下一轮 design 请把上述裁定一次做到位，并把符号链接场景的 scenario 与任务一并补齐。
