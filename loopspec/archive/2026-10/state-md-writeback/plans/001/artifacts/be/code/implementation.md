## 完成的任务

- 1.1 新增 `tests/test_workflow_journal.py` 的 T1–T11，先运行确认因 `loopspec.workflow_journal` 不存在而失败。
- 1.2 `workflow_io.append_text()`：目录描述符 + `O_RDWR|O_APPEND|O_CREAT|O_NOFOLLOW`，非普通文件拒绝，末尾无换行时先补 `\n`，`fsync`；`tests/test_workflow_io.py` 新增追加与拒绝符号链接 / 目录用例。
- 1.3 新增 `workflow_journal.py`：两级模板常量、`one_line()`（空白折叠、去控制字符）、`event_line()`、`record()`（吞掉 `WorkflowError` / `OSError`）、`with_warnings()`。
- 1.4 `change new` / `plan create` 改用新模板；`plan create`（create / replace-draft）、`plan approve`（approve / revise）、`plan rollback`、`plan archive`（Plan 级 + Change 级）在提交点之后追加事件，失败时结果加 `warnings: ["state_append_failed: <path>"]`。T1–T11 通过。
- 2.1 新增 T12–T16（四种状态的 `state` / `planState` / `untrustedData`，已归档 Plan 不输出，缺失 / 非 UTF-8 / 符号链接 / 超 64 KiB 截断，其他命令不输出全文，digest 不变），先确认失败。
- 2.2 `workflow_io.read_capped()`（首尾各 32 KiB）、`workflow_journal.state_view()`；`workflow_changes.status()` 四个分支都带 `state`、`planState`、`untrustedData`。T12–T16 通过。
- 3.1 新增 `tests/test_status_report.py`（T17–T23 及缺失 / 不可读 state 的标题写法），先确认因模块不存在而失败。
- 3.2 新增 `status_report.py`：`render_status_report()` / `render_error_report()`，`=== SECTION ===` 纯文本，节序 OVERVIEW / STATE RECORDS / PLANS / NODES / GATE FAILURES / PENDING ROLLBACK / NEXT STEPS；插值经 `presentation.sanitize()`，`state.md` 原文逐行缩进 4 空格；`TOP_KEYS` 等键集合供字段覆盖测试使用。
- 3.3 `change status` 新增 `--json`，默认输出纯文本、失败输出 `=== ERROR ===`，退出码不变；`run()` 增加可选文本渲染器；其他 workflow 命令仍拒绝 `--json`。
- 4.1–4.3 更新 `builtin/skills/new.md`、`continue.md`、`archive.md` 的 `state.md` 写入约定与读取纯文本报告的说明。
- 4.4 `.claude/skills/loopspec-{new,continue,archive}/SKILL.md` 与 `builtin/skills` 同步（改动前两者逐字相同，直接复制）。
- 5.1 `docs/zh|en/overview.md` 新增"state.md 记录"一节，目录树注释更新。
- 5.2 `docs/zh|en/cli-reference.md` 更新约定、`change new`、`change status`（纯文本报告、`--json`、新字段）、`plan create/approve/archive/rollback` 的事件追加与 `warnings`。
- 6.1–6.3 lint、全量测试、手工核对均完成，见下文。
- 返工 attempt 1（`be/security/check` FAIL：未拒绝硬链接）：`append_text()` 与 `read_capped()` 打开文件后检查 `st_nlink == 1`，否则抛 `unsafe_path`；上层沿用既有处理（追加失败返回 `warnings`，读取返回 `error: "unreadable"`）。先补测试并确认失败：`tests/test_workflow_io.py::test_append_and_capped_read_refuse_hard_links`、`tests/test_workflow_journal.py::test_hard_linked_state_is_neither_written_nor_shown`，修复后通过。
- 返工 attempt 2（`be/review/check` FAIL：`continue.md` 仍引用 `loopspec-new` 的 steps 3-8）：两处改为 steps 3-9 并同步 `.claude/skills/loopspec-continue/SKILL.md`；新增 `tests/test_skill_templates.py::test_continue_points_at_every_planning_step_of_new`（先确认失败，修复后通过），以及审查建议的 `tests/test_status_report.py::test_glob_outputs_list_their_matches_indented`（构造 glob 产物 payload，校验续行缩进且文件名无法伪造分隔行）。

## 改动文件

新增：

- `src/loopspec/workflow_journal.py`
- `src/loopspec/status_report.py`
- `tests/test_workflow_journal.py`
- `tests/test_status_report.py`

修改（引擎）：

- `src/loopspec/workflow_io.py`：`read_capped()`、`append_text()`（返工：两者拒绝硬链接）
- `src/loopspec/workflow_plans.py`：模板与五处事件追加
- `src/loopspec/workflow_changes.py`：模板、status 的 state 字段
- `src/loopspec/workflow_cli.py`：`run()` 文本渲染、`change status --json`

修改（测试）：

- `tests/workflow_helpers.py`：`invoke()` 调用 `change status` 时自动加 `--json`
- `tests/test_workflow_cli.py`：原"所有命令总是 JSON"用例改为 status 例外；`status_report` 移出"已删除模块"列表
- `tests/test_workflow_io.py`：追加与截断读取用例
- `tests/test_skill_templates.py`：continue 引用 new 规划步骤区间的一致性用例（返工 2）
- `tests/test_workflow_lifecycle.py`：归档用例改为排除 `state.md` 比较，并断言只多一行 archive 事件
- `tests/test_workflow_recovery.py`：`normalized()` 屏蔽 `state.md` 事件行时间戳

修改（skill 与文档）：

- `builtin/skills/new.md`、`continue.md`、`archive.md`
- `.claude/skills/loopspec-new|continue|archive/SKILL.md`
- `docs/zh|en/overview.md`、`docs/zh|en/cli-reference.md`、`docs/zh|en/agent-protocol.md`

## 执行的检查

- `uv run pytest tests/test_workflow_journal.py`（实现前）：收集失败，`ModuleNotFoundError: loopspec.workflow_journal`。
- `uv run pytest tests/test_status_report.py`（实现前）：收集失败，`status_report` 模块不存在。
- `uv run pytest tests/test_workflow_journal.py tests/test_workflow_io.py`：25 passed（第 1 组完成时）；`tests/test_workflow_journal.py`：16 passed（第 2 组完成时）。
- `uv run pytest tests/test_status_report.py`：10 passed。
- `uv run pytest tests/test_docs_consistency.py`：43 passed；`make docs-check`：43 passed。
- `uv run pytest tests/test_skill_templates.py tests/test_builtin_resources.py`：42 passed。
- `make lint`：ruff `All checks passed!`；mypy `Success: no issues found in 33 source files`。
- `make test`：974 passed in 581.42s（首轮实现）。
- 返工 attempt 2：修复前 `uv run pytest tests/test_skill_templates.py::test_continue_points_at_every_planning_step_of_new tests/test_status_report.py::test_glob_outputs_list_their_matches_indented`：1 failed（区间用例）、1 passed；修复后 `uv run pytest tests/test_skill_templates.py tests/test_status_report.py`：49 passed；`make lint`：通过。全量测试在 `be/tests/check` 第 3 轮 gate begin 之后执行。
- 返工 attempt 1：修复前 `uv run pytest tests/test_workflow_io.py tests/test_workflow_journal.py -k hard`：2 failed；修复后 `uv run pytest tests/test_workflow_io.py tests/test_workflow_journal.py tests/test_status_report.py`：42 passed；`make lint`：ruff 通过、mypy `Success: no issues found in 33 source files`；`make test`：976 passed。
- 手工：`uv run loopspec change status state-md-writeback` 输出 OVERVIEW / STATE RECORDS（change + plan 001 两个子块）/ PLANS / NODES / NEXT STEPS；`--json` 含 `state`、`planState`（plan 001）、`untrustedData`；`uv run loopspec change status nope` 输出 `=== ERROR ===`，退出码 1。

## 与设计的偏差

- **skill 不提 `--json`**：现有测试 `test_no_template_passes_json_flags` 禁止 skill 正文出现 `--json`，因此 `continue.md` 未写"需要结构化字段时加 `--json`"。
- **skill 用英文描述段落**：现有测试要求 skill 正文为 ASCII，skill 以含义指代模板段落（background、key-decisions section 等），不写中文标题。
- **planning 状态的 OVERVIEW 不带 digest**：planning 分支的 payload 本身不含 digest，渲染器不得另取数据，只输出 `draft plan: 001`。
- **截断标记沿用 JSON 内容**：纯文本报告引用 `state_view` 产生的中文省略标记行（`…（已省略 N 字节，完整内容见 <path>）…`），不另写设计 5.2 中的英文标记，保持单一数据源；子块标题仍带 `(truncated: first and last 32 KiB shown)`。
- **OVERVIEW 渲染 `warnings`**：status 的 `warnings` 实际为 `{ignoredPaths, ignoredTotal}`，渲染为 `warnings: N ignored paths not excluded: …`。
- **额外更新 `docs/zh|en/agent-protocol.md`**：其中"所有工作流命令都输出 JSON"已不准确，补充 `change status` 例外。
- **模板文本换行**：为满足行宽 100 的 lint，Change 级模板的说明与关键决策注释各拆为两行，内容不变。
- **已有测试的调整**：除设计列出的 CLI 用例与辅助函数外，还调整了归档用例（`state.md` 现在会追加事件）与恢复用例的时间戳归一化，二者都是预期行为变化。

## 后续事项

- `docs/zh|en/release-notes.md` 仍描述 2.0.0 的"只输出 JSON"，属历史版本说明，未改；发布新版本时需在新版本条目中说明 `change status` 默认改为纯文本报告。
- 全局安装的 `loopspec`（`~/.local/bin/loopspec`，0.0.0.dev0）不是本工作树代码，需重新安装后 skill 才会读到纯文本报告。
