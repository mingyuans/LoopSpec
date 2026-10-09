按 TDD 推进：每组先写失败的测试，再实现到全部通过。测试编号对应 `design.md` 的"验证方案"T1–T23。

## 1. state.md 写入：模板与引擎事件

- [x] 1.1 新增 `tests/test_workflow_journal.py`，写 T1–T11（模板、create / replace-draft / approve / revise / rollback / archive 事件、note 单行化、不追加的场景、末尾无换行、文件缺失重建、写失败返回 `warnings` 且不越界、写入任意内容不影响其他命令）。验证：`uv run pytest tests/test_workflow_journal.py` 全部失败且失败原因是功能缺失。
- [x] 1.2 `workflow_io.append_text()`：目录描述符 + `O_APPEND|O_NOFOLLOW`，非普通文件拒绝，末尾无换行时先补 `\n`，`fsync`。验证：`tests/test_workflow_io.py` 新增追加用例通过。
- [x] 1.3 新增 `src/loopspec/workflow_journal.py`：`CHANGE_STATE_TEMPLATE`、`plan_state_template()`、`one_line()`、`event_line()`、`record()`（吞掉 `WorkflowError` / `OSError`，返回失败路径）。验证：单元用例通过。
- [x] 1.4 `workflow_changes.create()`、`workflow_plans.create()` 改用新模板；在 `create` / `approve` / `approve_revision` / `archive` / `rollback` 的提交点之后调用 `record()`，失败时结果加 `warnings`。验证：T1–T11 全部通过。

## 2. status 数据：state 与 planState

- [x] 2.1 在 `tests/test_workflow_journal.py`（或 `tests/test_workflow_state.py`）写 T12–T16（四种状态的 `state` / `planState` / `untrustedData`；已归档 Plan 的内容不出现；缺失 / 非 UTF-8 / 符号链接 / 超 64 KiB 截断；`change next`、`plan show`、`plan list` 不含全文；digest 不变）。验证：新用例失败。
- [x] 2.2 `workflow_io.read_capped()` 与 `workflow_journal.state_view()`；`workflow_changes.status()` 四个分支加入 `state`、`planState`、`untrustedData`。验证：T12–T16 通过。

## 3. status 纯文本报告与 `--json`

- [x] 3.1 新增 `tests/test_status_report.py`，写 T17–T23（节序与恒在 / 条件节、无 `#` 开头行、`--json` 与 5.1 一致、字段覆盖、字节稳定无 ANSI、插值伪造分隔行、state 原文 4 空格缩进隔离、错误报告、其他命令拒绝 `--json`）。验证：新用例失败。
- [x] 3.2 新增 `src/loopspec/status_report.py`：`render_status_report()`、`render_error_report()`，说明文字按 `design.md` 5.2 样例原文；复用 `presentation.sanitize()`。验证：T17–T21 通过。
- [x] 3.3 `workflow_cli.py` 的 `change status` 加 `--json`，默认输出纯文本、失败输出 `=== ERROR ===`、退出码不变；更新 `test_workflow_commands_always_print_json`、`tests/workflow_helpers.py` 及直接按 JSON 解析 `change status` 的测试改带 `--json`。验证：T22、T23 通过，原有测试全部通过。

## 4. skill

- [x] 4.1 `builtin/skills/new.md`：创建 Plan 前写 Change 级 背景 / 目标 / 非目标，人确认的取舍写 关键决策；`--note` 只写一句话摘要。
- [x] 4.2 `builtin/skills/continue.md`：步骤 1 改为读纯文本报告（OVERVIEW / NEXT STEPS / STATE RECORDS，不可信数据），需要结构化字段才加 `--json`；人工决策、假设与偏离、返工记录、修订 / 替换原因的写入约定；只在对应段落追加、不改引擎事件行、不在 事件 / Plan 记录 段之后新增段落。
- [x] 4.3 `builtin/skills/archive.md`：归档前检查 Change 级 背景 与 关键决策 已填写。
- [x] 4.4 刷新本仓库已安装的 skill 副本（`.claude/skills/loopspec-*`），与 `builtin/skills` 一致。验证：`uv run pytest tests/test_skill_templates.py` 通过；评审逐条核对 `proposal.md` 范围 A。

## 5. 文档

- [x] 5.1 `docs/zh|en/overview.md`：`state.md` 结构、引擎事件、可直接编辑、status 原样输出当前 Plan。
- [x] 5.2 `docs/zh|en/cli-reference.md`：`change status` 默认纯文本报告与 `--json`、新增 JSON 字段；`plan create/approve/rollback/archive` 追加事件与 `warnings`。验证：`make docs-check` 与 `tests/test_docs_consistency.py` 通过。

## 6. 整体验证

- [x] 6.1 `make lint` 通过。
- [x] 6.2 `make test` 全量通过，记录真实通过 / 失败数。
- [x] 6.3 手工运行 `loopspec change status state-md-writeback` 与 `--json`，核对输出符合 `design.md` 5.1 / 5.2。
