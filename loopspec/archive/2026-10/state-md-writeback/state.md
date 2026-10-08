# 需求记录

需求背景、跨 Plan 的决策与更替原因（人读，引擎不读取）。

## 背景

`change new` 与 `plan create` 会生成 Change 级和 Plan 级的 `state.md`，但只写入模板头。
现状核查（2026-10-08）：

- `loopspec/archive/2026-10/` 下所有带 `state.md` 的 Change（add-fragment-registry、
  assurance-unknown-paths-warn、block-unreviewed-commits、diff-scan-performance、
  evidence-survives-commit、fix-ignored-input-exclusions）两级 `state.md` 都只有 3 行模板。
- `builtin/skills/*.md` 没有任何一处要求写 `state.md`；决策原因只零散地落在
  `plan.yaml` 的 `meta.note` / `meta.archive_note`（`--note` 可选，经常为空）。
- 结果：归档后无法回答"为什么做这个需求、为什么换 Plan、Gate 为什么失败过、谁确认了什么"。

## 目标

让两级 `state.md` 在 Change 生命周期内持续有内容，且不破坏"引擎不读取 state.md"的约定，
不影响 Diff / 证据（`state.md` 已在 Diff 排除列表中）。

## 应写入的内容（评估）

### Change 级 `state.md`（跨 Plan，语义内容为主）

| 段落 | 内容 | 写入方 |
| --- | --- | --- |
| 背景 | 用户原始诉求、问题现状、触发原因 | skill（new 步骤） |
| 目标 / 非目标 | 范围边界，明确不做的事 | skill（new 步骤） |
| 关键决策 | 方案取舍、理由、由谁在何时确认 | skill（人确认后） |
| Plan 更替 | Plan id、创建/批准/归档时间、更替原因（= `archive_note`） | 引擎追加事实 + skill 补充原因 |
| 参考 | 相关 issue / PR / 归档 Change | skill |

### Plan 级 `state.md`（本 Plan 执行流水，事实性事件为主）

| 事件 | 记录内容 | 写入方 |
| --- | --- | --- |
| create / 重建草稿 | 时间、digest、`--note` | 引擎 |
| approve | 时间、digest、revision | 引擎 |
| revision | base_revision → 新 revision、addedInstances、rerunNodes、原因 | 引擎 + skill 补原因 |
| Gate FAIL / rollback | 节点、轮次 / max_retries、reset 目标、失败摘要 | 引擎 + skill 补摘要 |
| 人工决策 | instruction 要求询问人时的问题与答复 | skill |
| 偏离与假设 | 执行中的假设、与设计的偏差 | skill |
| archive | 时间、`archive_note` | 引擎 |

## 方案方向（Plan 001 草稿：A + B）

- **A. skill 约定**：在 `new.md` / `continue.md` / `archive.md` 中规定何时、写哪一级、写什么
  （背景、决策原因、人工答复、失败摘要）。
- **B. 引擎自动追加**：create / approve / revise / rollback / archive 成功后向对应
  `state.md` 追加一行带时间戳的事实记录，不依赖 agent 记忆。

## 关键决策

- 2026-10-08（用户确认）：暂时允许 LLM 直接编辑 `state.md`，本需求不新增
  `loopspec change note` 之类的写入命令，也不做禁止编辑或防篡改校验；引擎继续不读取 `state.md`。
  备选方案（CLI 只追加、skill 禁止直接编辑、可选 hook 拦截）留待后续需求再评估。
- 2026-10-08（用户确认）：引擎追加顺序为先写 `plan.yaml`（命令提交点），成功后再追加 `state.md`；
  不允许反过来，避免 `state.md` 记录未生效的事件。
- 2026-10-08（用户确认）：两次写入之间崩溃导致 `state.md` 少一行时允许缺失，不补写、不去重；
  因此追加格式为纯 Markdown 列表行，不加机器可识别前缀，引擎始终不读取 `state.md`。
- 2026-10-08（用户确认）：已归档 Change 的空 `state.md` 不回填，新规则只对之后的 Change 生效。
- 2026-10-08（用户确认）：`loopspec change status` 输出 Change 级与 Plan 级 `state.md` 的全文，
  让 LLM 接手时完整感知本次 Change 的过程信息。"引擎不读取 `state.md`"调整为
  "引擎只原样读出用于展示，不解析、不据此做任何状态判断、去重或校验"。
- 2026-10-08（用户确认）：`change status` 默认输出 Markdown 报告（直接作为给 LLM 的 prompt），
  加 `--json` 才输出 JSON；参考 1.x `status_report.py` 的实现原则。其他 workflow 命令仍只输出 JSON。
- 2026-10-08（用户确认）：取代上一条的 Markdown 版式，恢复 1.x 评审裁定的 `=== SECTION ===` 纯文本报告
  （不用 Markdown 语法）；默认输出纯文本、`--json` 输出 JSON 不变。
- 2026-10-08（用户确认）：`change status` 同时列出各 Plan（含已归档）现有的 artifacts 文件及简单说明
  （所属节点与角色，由 Plan 定义推出，不读文件内容）。
- 2026-10-08（用户确认）：产物清单只列活动 Plan 的 artifacts，已归档 Plan 不列（取代上一条的"含已归档"）。
- 2026-10-08（用户确认）：撤销单独的产物清单（取代上两条）：`=== NODES ===` 已列出各节点产物，不再新增 `=== ARTIFACTS ===` 节与 `artifacts` 字段。
- 2026-10-08（用户确认）：纯文本报告不输出 `=== INSTANCES ===`（`NODES` 已齐全），`instances` 只保留在 `--json` 中。
- 2026-10-08（用户确认）：status 只输出 Change 级与当前 Plan（活动 Plan，planning 时为草稿）的 `state.md`，已归档 Plan 不输出。
- 2026-10-08（用户确认）：`=== PLANS ===` 保留全部 Plan（含已归档）的摘要行：Plan 更替是关键事件，需要 LLM 感知。

## 待定问题

1. ~~追加顺序与缺失处理~~ 已决，见"关键决策"。
2. ~~追加格式~~ 已决，见"关键决策"。
3. ~~是否需要 `loopspec change note` 之类的命令供 skill 写入？~~ 已决，见"关键决策"。
4. ~~已归档 Change 的空 `state.md` 是否回填~~ 已决，见"关键决策"。
