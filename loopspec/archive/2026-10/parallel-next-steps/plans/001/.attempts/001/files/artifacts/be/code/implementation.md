## 完成的任务

- 1.1 / 1.2 / 1.3：先写测试并确认失败（runtime 5 个用例因 `KeyError: 'parallel'` 等失败，status_report 2 个用例失败）。
- 2.1：`workflow_runtime.status` 列出全部 ready 叶子的 `node instructions` 命令，新增 `parallel`（无 rollback 且 ≥2 条命令时为 true）。
- 2.2：`workflow_changes.status` 在 unplanned / planning / complete 分支输出 `parallel: false`；`next_step` 保持 `node` 原语义，新增 `nodes`（rollback Gate → exhausted Gate → 全部 ready 叶子）与 `parallel`。
- 3.1：`status_report` 的 `TOP_KEYS` 加入 `parallel`；新增 `PROMPT_NEXT_STEPS_PARALLEL`（独立、可并行、每步一个 sub agent、`concurrent_write` 重试、完成后重读 status）；NODES 提示改为 “act only on the nodes named in NEXT STEPS”。
- 4.1 / 4.2：`builtin/skills/continue.md` 第 2 步新增并行派发子条目；同步 `.claude/skills/loopspec-continue/SKILL.md`、`.codex/skills/loopspec-continue/SKILL.md`、`.claude/commands/lpsx/continue.md`（各 +1 行）。
- 5.1 / 5.2：更新 en/zh 的 agent-protocol、cli-reference、workflow-composition（新增“并行分支”示例）与 release-notes。
- 6.1：lint、mypy 与全量测试通过。

## 改动文件

- 引擎：`src/loopspec/workflow_runtime.py`、`src/loopspec/workflow_changes.py`、`src/loopspec/status_report.py`
- Skill：`builtin/skills/continue.md`、`.claude/skills/loopspec-continue/SKILL.md`、`.codex/skills/loopspec-continue/SKILL.md`、`.claude/commands/lpsx/continue.md`
- 测试：`tests/test_workflow_runtime.py`、`tests/test_status_report.py`、`tests/test_skill_templates.py`
- 文档：`docs/{en,zh}/agent-protocol.md`、`docs/{en,zh}/cli-reference.md`、`docs/{en,zh}/workflow-composition.md`、`docs/{en,zh}/release-notes.md`

## 执行的检查

- `make test`：1079 passed in 451.06s。
- `make lint`：ruff `All checks passed!`；mypy `Success: no issues found in 34 source files`（修正一处行长与两处类型注解后）。
- 修正后复跑 `pytest tests/test_workflow_runtime.py tests/test_status_report.py tests/test_workflow_journal.py`：45 passed。

## 与设计的偏差

- 设计计划把 `change status --json` / `change next` 的用例放在 `tests/test_workflow_cli.py`，实际与扇出 Plan 夹具一起放在 `tests/test_workflow_runtime.py`（同样经 CLI 调用），避免重复夹具。
- 同时 ready 的叶子按编译器的依赖顺序输出，独立节点之间按 id 排序（be-review、fe-review、qa-review），测试按此断言。
- 额外同步了 `.claude/commands/lpsx/continue.md`（设计只列出两份 skill 副本）。
- docs 中的扇出示例未加 `loopspec:example=plan` 标记，因为评审 Fragment 为占位名，不在内置目录中。

## 后续事项

- PRD 三方评审的 Fragment / Profile 需在 registry 仓库另开需求。
