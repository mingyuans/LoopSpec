## 完成的任务

- `change archive` 的删除范围从 `.attempts/` 扩展为：各 Plan（含已归档 Plan）的 `.attempts/`、`.gates/`、`.gate-rounds/`，以及 `plan.yaml` 中所有 Gate 节点声明的 `outputs.pass`/`outputs.fail` 报告（仅限 `artifacts/` 下）。同目录的非 Gate 文件保留，删空的 Gate 输出目录逐级移除（不超过 `artifacts/`）。
- `plan.yaml` 无法读取时跳过该 Plan 的报告，仍删除控制目录，归档不受影响。
- 删除方式沿用上一需求：移动成功后，经移动时持有的目录 fd、逐级 O_NOFOLLOW，先核对 inode；失败只报告。通用化为 `archive_drops()` 与 `drop_paths()`。
- 结果字段统一为 `dropped` / `notDropped`，取代未发版的 `droppedAttempts` / `attemptsNotDropped`。
- archive skill：更正「归档保留全部产物与返工记录」的说法，提醒在归档前完成 memory 审阅并读取所需内容；同步本仓库 `.claude`、`.codex` 的生成副本。
- 中英文 `cli-reference`、`plan-reference` 同步。
- 历史清理：按同一规则处理 `loopspec/archive/` 下 15 个新格式归档，共删除 97 项；10 个旧格式（1.x schema）归档保持不变。

## 改动文件

- 代码：`src/loopspec/workflow_archive.py`
- skill：`builtin/skills/archive.md`、`.claude/skills/loopspec-archive/SKILL.md`、`.codex/skills/loopspec-archive/SKILL.md`、`.claude/commands/lpsx/archive.md`
- 测试：`tests/test_workflow_archive.py`、`tests/features/change.feature`、`tests/steps/change_steps.py`
- 文档：`docs/{zh,en}/cli-reference.md`、`docs/{zh,en}/plan-reference.md`
- 历史归档：`loopspec/archive/**`（删除）

## 执行的检查

- `uv run ruff check src tests`：All checks passed；`uv run mypy src`：Success
- `uv run pytest -q tests/test_workflow_archive.py`：16 passed
- `uv run pytest -q -n 2 -m "not timing and not llm"`：1693 passed, 1 skipped
- `tests/test_skill_templates.py tests/test_scaffold.py tests/test_docs_consistency.py`：108 passed
- `make test-llm`：12 passed、1 次重跑，16 次启动，$1.647，`.llm-e2e-runs/20261119T145836Z/`。首次失败的场景「归档时把可复用的人工决策沉淀到记忆并注明来源」中，模型把 memory 写到项目根 `memory/` 而非 `loopspec/memory/`，归档流程本身正确，与本次改动无关；重跑通过。

## 与设计的偏差

- 无（旧格式归档不清理已作为假设记录）。

## 后续事项

- 旧格式归档中的 `security/`、`approval/`、`apply/` 等文件未处理。
