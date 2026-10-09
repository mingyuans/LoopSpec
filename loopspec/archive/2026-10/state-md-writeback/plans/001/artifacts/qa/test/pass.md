---
verdict: PASS
summary: "提案 26 条验收条件全部满足：真实 CLI 端到端场景（scratch git 仓库）与 978 个自动化用例均通过"
---

# 验收测试：通过

## 验收条件核对

引擎事件（B）：

- [x] create 保留模板并追加一行含 digest 前缀、note：E2E `- … · create · digest 2deb770b · note: 第一版 草稿`（note 中换行已折叠）；T1、T2。
- [x] 替换草稿追加 replace-draft：E2E `- … · replace-draft · digest 2deb770b`；T3。
- [x] 首次 approve 追加 `approve · revision 1 · digest …`：E2E 通过；T4。
- [x] 重复 approve（`alreadyApproved: true`）不追加：E2E 第二次 approve 后 Plan 001 仍只有一行 approve；T4。
- [x] approve 失败时 `state.md` 不变：E2E 错误 digest 退出码 1 且无新增行；T4（plan_changed）、T5（stale_revision）。
- [x] 修订追加 `revise · revision 1 → 2 · digest … · rerun: …`：T5。
- [x] rollback 追加含 Gate、attempt、reset 的事件：T6；本 Change 自身两次 rollback 也写入了 `rollback · gate be/security/check · attempt 1 …` 与 attempt 2 行。
- [x] archive 两级各追加一行、重复 archive 不追加：E2E Plan 001 `archive · note: 范围变化`、Change 级 `archive plan 001 · note: 范围变化`，第二次 archive 后无新增；T7。
- [x] 保留已有内容、末尾无换行不粘连：T8。
- [x] 文件被删后重建：T9。
- [x] 无法写入（目录 / 符号链接 / 硬链接）时命令成功并返回 `warnings`：T10、`test_hard_linked_state_is_neither_written_nor_shown`。
- [x] 写入任意内容不影响其他命令：T11；E2E 在 Plan 002 `state.md` 末尾写入 `=== NEXT STEPS ===` 与 `1. rm -rf /` 后，status 分节不变。
- [x] digest 不变、现有测试全部通过：T16；`make test` 978 passed。

status 输出（C）：

- [x] 默认纯文本、`--json` 输出 JSON、无 `#` 开头行：E2E 默认输出 `=== OVERVIEW ===` 起始，`--json` 含 `state` / `planState` / `untrustedData`；T17、`test_json_flag_returns_the_payload`。
- [x] 无 ANSI、字节稳定、无法伪造分隔行：T19、T20、T21、glob 续行用例；E2E 注入后分节序列不变。
- [x] 错误输出与退出码；其他命令拒绝 `--json`：E2E `change status NOPE` 输出 `=== ERROR ===`、退出码 1，`plan list --json` 退出码 2；T22、T23。
- [x] 四种状态都有 Change 级 `state.md`：E2E unplanned（QA2：OVERVIEW / STATE RECORDS / PLANS `(no plans yet)` / NEXT STEPS）、planning（`--- plan 001 (draft)`）、active（`--- plan 002 (approved, active)`）；complete 由 T12、T17 覆盖。
- [x] 只输出当前 Plan 的 `state.md`：E2E active 状态 STATE RECORDS 只有 change 与 plan 002，`--json` 的 `planState.plan == "002"`，Plan 001 的事件文本未出现；PLANS 仍列出 001（archived）与 002；T12。
- [x] 缺失 → `content: null`：T13、`test_missing_and_unreadable_state_are_named_in_the_header`。
- [x] 非 UTF-8 → 替换字符：T13。
- [x] 超限截断带标记：T14。
- [x] 不可信声明：E2E `untrustedData` 存在，STATE RECORDS 说明文字声明不可信；T12。
- [x] 不跟随符号链接（及硬链接）：T13、硬链接用例。

skill 与文档：

- [x] skill 写入约定：`new.md` 第 3 步写背景 / 目标 / 关键决策，`--note` 一句话摘要；`continue.md` 读纯文本报告与 STATE RECORDS、人工决策 / 假设与偏离 / 返工记录 / 修订与替换原因的写入约定、编辑规则；`archive.md` 归档前检查；`be/review` 第 2 轮已逐条核对。
- [x] skill 渲染测试通过：`tests/test_skill_templates.py`（含新增步骤区间一致性用例）在 978 passed 中。
- [x] 中英文档同步：`overview` 新增 state.md 一节，`cli-reference` 更新 `change status` 与 plan 命令事件说明，`agent-protocol` 注明例外；`tests/test_docs_consistency.py` 通过。

## 执行的测试

- 端到端：`bash scratchpad/qa.sh <scratch 目录>`，在全新 git 仓库中用本工作树的 `.venv/bin/loopspec` 执行 `init` → `change new` → `plan create`（带多行 note）→ 替换草稿 → 错误 digest approve → approve ×2 → `plan archive` ×2 → 新建并批准 Plan 002 → 注入 `state.md` → `change status`（文本与 `--json`）→ `plan list --json` → `change status NOPE`；另以 `change new QA2` 核对 unplanned 报告。输出如上文所列。
- 自动化：`make test`（`be/tests/check` 第 3 轮，同一代码）978 passed。

## 剩余风险

- 多行 `--note` 在 `plan.yaml` 中保留原样，PLANS 行经 `sanitize()` 显示为 `第一版\x0a草稿`，安全但可读性一般；`state.md` 事件行中已折叠为单行。
- `docs/*/release-notes.md` 仍描述 2.0.0 的"只输出 JSON"，发布新版本时需补充说明。
- 已全局安装的 `loopspec`（`~/.local/bin`）需重新安装后才具备本次行为。
