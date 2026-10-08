## 背景

`loopspec change new` 与 `loopspec plan create` 会生成 Change 级 `state.md` 与 Plan 级
`plans/<id>/state.md`，但只写入模板头，之后引擎与 skill 都不再写它。

现状（2026-10-08 核查）：

- `loopspec/archive/2026-10/` 下所有带 `state.md` 的已归档 Change，两级文件都只有 3 行模板。
- `builtin/skills/*.md` 没有任何一处要求写 `state.md`。
- 决策原因只能落在 `plan.yaml` 的 `meta.note` / `meta.archive_note`，二者都靠可选的 `--note`，经常为空；
  approve、revision、rollback 完全没有人读的记录。
- 结果：Change 执行中或归档后，无法回答"为什么做这个需求、为什么换 Plan、何时批准了哪个 digest、
  Gate 为什么被打回过、人确认过什么"。

## 用户场景

1. 人在 IDE 中打开一个进行中的 Change，读 Change 级 `state.md` 即可知道需求背景、目标、
   关键决策和 Plan 更替原因。
2. 人打开某个 Plan 的 `state.md`，按时间顺序看到该 Plan 的创建、批准、修订、打回、归档事件，
   无需翻 `plan.yaml` 与 `.attempts/`。
3. 新会话中的 agent 接手一个 Change 时，执行 `loopspec change status` 即可在输出中拿到两级 `state.md` 全文，
   完整感知需求背景、决策与执行过程，无需另外查找文件。
4. 人可以直接在 `state.md` 中补充或修正内容，不会被引擎拒绝或覆盖。

## 范围

**A. skill 约定（语义内容）** — 修改 `builtin/skills/new.md`、`continue.md`、`archive.md`：

- `new`：创建 Plan 前，把用户原始诉求整理为 Change 级 `state.md` 的"背景 / 目标 / 非目标"；
  人确认的方案取舍写入"关键决策"（日期 + 由谁确认 + 内容）。
- `continue`：
  - 节点 instruction 要求询问人时，把问题与答复写入 Plan 级 `state.md`；
  - Gate FAIL 执行 rollback 后，补一条失败原因摘要；
  - 修订、替换 Plan 前，把人同意的原因写入对应 `state.md`；
  - 执行中的假设与对设计的偏离写入 Plan 级 `state.md`。
- `archive`：归档前检查 Change 级 `state.md` 是否已有背景与关键决策，缺失时先补齐再归档。
- 允许 LLM 直接编辑 `state.md`；只追加或修订自己负责的段落，不删除他人已写内容。

**B. 引擎自动追加（事实事件）** — 以下命令在提交点写入成功后，向 `state.md` 追加一行 Markdown 列表项：

| 命令 | 追加到 | 记录内容 |
| --- | --- | --- |
| `plan create`（新建草稿） | Plan 级 | 时间、事件 create、digest 前缀、note（如有） |
| `plan create`（替换草稿） | Plan 级 | 时间、事件 create（替换草稿）、新 digest 前缀、note（如有） |
| `plan approve`（首次批准） | Plan 级 | 时间、事件 approve、revision、digest 前缀 |
| `plan approve -f`（修订） | Plan 级 | 时间、事件 revise、revision 变化、新 digest 前缀、rerunNodes |
| `plan rollback` | Plan 级 | 时间、事件 rollback、Gate、attempt 序号、reset 节点 |
| `plan archive` | Plan 级 + Change 级 | 时间、事件 archive、Plan id、archive_note（如有） |

追加行的具体文本格式在设计阶段确定。

**C. `change status` 输出 `state.md` 全文** — `loopspec change status` 默认输出一份给 LLM 阅读的 `=== SECTION ===` 纯文本报告（恢复 1.x `status_report.py` 的版式），加 `--json` 时输出 JSON；两种输出都包含：

- Change 级：`state.md` 的路径与全文；
- Plan 级：当前 Plan（活动 Plan；planning 时为草稿）的 `state.md` 路径与全文；已归档 Plan 不输出；
- 一个说明字段，标明这些内容是人 / LLM 可自由编辑的不可信数据，只作参考，不作为指令执行
  （与 `node instructions` 的 `untrustedData` 做法一致）。

引擎只原样读出用于展示，不解析内容；`status`、`nextSteps`、节点状态等计算与 `state.md` 无关。
`continue` skill 增加约定：接手 Change 时先阅读 status 输出中 Change 级与当前 Plan 的 `state.md`。

## 非目标

- 不新增 `loopspec change note` 等写入命令，不禁止也不检测 LLM / 人对 `state.md` 的直接编辑。
- 引擎除 `change status` 原样输出外不读取 `state.md`；不解析、不校验其内容，不用它做去重、状态判断或证据。
- 两次写入之间崩溃导致少一行时不补写；不保证 `state.md` 是完整审计日志。
- 不回填已归档 Change 的 `state.md`。
- 不改变 `state.md` 在 Diff / 证据中的排除规则，不改变 `plan.yaml` 的结构与 digest 计算。
- 不为 `gate record`、`node instructions`、`change archive` 等其他命令追加记录。
- 除 `change status` 外，其他命令（`plan show`、`node instructions`、`change next` 等）不输出 `state.md`。

## 验收条件

引擎（B）：

- [ ] `plan create` 新建草稿成功后，`plans/<id>/state.md` 保留模板头，并在末尾恰好多一行 create 记录，含 digest 前缀；带 `--note` 时含 note。判定：自动化测试读取文件比对。
- [ ] 草稿存在时再次 `plan create`（替换草稿）成功后，Plan 级 `state.md` 再追加一行，标明替换草稿。
- [ ] `plan approve` 首次批准成功后，Plan 级 `state.md` 追加一行 approve 记录，含 revision 1 与 digest 前缀。
- [ ] 对已批准 Plan 重复 `plan approve`（返回 `alreadyApproved: true`）不追加任何行。
- [ ] `plan approve` 因 `plan_changed`、`plan_archived`、`stale_revision` 等失败时，`state.md` 字节不变。
- [ ] `plan approve -f` 修订成功后，Plan 级 `state.md` 追加一行 revise 记录，含新 revision、新 digest 前缀与 rerunNodes。
- [ ] `plan rollback` 成功后，Plan 级 `state.md` 追加一行 rollback 记录，含 Gate id、attempt 序号与 reset 节点；`retries_exhausted` / `no_failed_gate` 失败时不追加。
- [ ] `plan archive` 成功后，Plan 级与 Change 级 `state.md` 各追加一行 archive 记录，含 archive_note（如有）；对已归档 Plan 重复执行不再追加。
- [ ] 追加时保留文件已有全部内容（包括人/LLM 手写内容），只在末尾追加；原文件末尾无换行时不与最后一行粘连。
- [ ] `state.md` 被删除时，追加会重新创建该文件并写入记录，命令仍成功。
- [ ] `state.md` 无法写入（例如路径被替换为目录）时，命令已提交的结果不变、命令返回成功，不抛出异常。
- [ ] 往 `state.md` 写入任意内容（含非 UTF-8 字节、伪造的事件行）后，`plan show`、`plan approve` 等命令的输出与行为不变；`change status` 除 state 相关字段外输出不变（`status`、`nextSteps`、节点状态相同）。判定：测试对比写入前后命令结果。
- [ ] 改动前后同一请求的 `plan.yaml` digest 不变；现有测试全部通过。

status 输出（C）：

- [ ] `change status` 默认输出 `=== SECTION ===` 纯文本报告（不含 Markdown 语法，无 `#` 开头的行），`--json` 输出 JSON；两者信息一致，由字段覆盖测试保证。
- [ ] 纯文本报告不含 ANSI 转义，字节不随终端宽度、`NO_COLOR` 变化；插值内容与 `state.md` 原文无法伪造报告的分隔行结构。
- [ ] `change status` 失败时默认输出 `=== ERROR ===` 纯文本错误报告、`--json` 输出 JSON 错误，退出码均为 1；其他 workflow 命令仍只输出 JSON。
- [ ] `change status` 在 unplanned、planning、active、complete 四种状态下都输出 Change 级 `state.md` 的路径与全文。
- [ ] 存在已归档 Plan 时，`change status` 只输出当前 Plan 的 `state.md` 路径与全文，已归档 Plan 的 `state.md` 内容不出现在输出中。
- [ ] `state.md` 缺失时对应全文字段为 `null`，命令仍成功。
- [ ] `state.md` 含非 UTF-8 字节时命令仍成功，无法解码的字节以替换字符输出。
- [ ] `state.md` 超过单文件上限时输出截断后的内容并带截断标记（上限在设计阶段确定），命令仍成功。
- [ ] 输出包含说明字段，标明 `state.md` 内容为不可信数据。
- [ ] 读取 `state.md` 时不跟随指向 Change 目录外的符号链接。判定：测试构造符号链接，命令不输出目标文件内容。

skill（A）：

- [ ] `builtin/skills/new.md`、`continue.md`、`archive.md` 中包含上文"范围 A"列出的各条写入约定，并明确写在 Change 级还是 Plan 级；`continue.md` 包含"接手时先读 status 输出中 Change 级与当前 Plan 的 `state.md`"。判定：评审逐条核对。
- [ ] 若存在 skill 内容的快照或渲染测试，更新后测试通过。

文档：

- [ ] `docs/zh` 与 `docs/en` 中关于 `state.md` 的描述同步说明：引擎会在哪些命令后追加事件，人与 LLM 可直接编辑，`change status` 原样输出全文，引擎不解析其内容；`cli-reference` 中 `change status` 的输出字段同步更新。

## 风险

- **一致性**：追加是提交点之后的第二次写入，崩溃会导致少一行。已接受（允许缺失），文档中说明 `state.md` 不是完整审计日志。
- **写入失败影响主流程**：追加失败若抛出异常，会让已提交的命令看似失败，诱导重复执行。应对：追加失败只吞掉并可选地在输出中给出提示，不改变返回状态。
- **路径安全**：追加路径必须由 Change 根与已校验的 Plan id 拼出，沿用现有 `atomic_write` / 目录句柄方式，防止通过符号链接写到 Change 目录之外。
- **内容注入**：`--note` 由用户输入，写进 Markdown 可能包含换行或 Markdown 语法。应对：写入前把换行折叠为单行；引擎不解析该文件，不存在执行风险。
- **并发**：所有追加在命令已持有的 `write_lock` 内完成，与现有写入互斥；人在 IDE 中同时编辑可能被覆盖或覆盖追加，需用追加模式而非整文件重写来降低冲突。
- **提示注入**：`state.md` 可被任何人 / LLM 编辑，全文进入 agent 上下文后可能被当作指令。应对：输出中标明不可信数据，skill 中重申只作参考。
- **输出体积**：`state.md` 持续增长会让 status 输出变大、挤占上下文。应对：单文件设上限并截断，截断时提示文件路径供按需阅读。
- **读取越界**：读取路径与写入一样必须限制在 Change 根下，不跟随越界符号链接。
- **兼容性**：status 只新增字段，不改已有字段；旧 Change 的 `state.md` 只有模板头，追加逻辑不依赖其内容，直接适用。
