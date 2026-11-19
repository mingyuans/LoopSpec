## 完成的任务

- `change archive` 在目录移动成功后，删除归档目录中每个 Plan（含已 `plan archive` 的 Plan）的 `plans/<NNN>/.attempts/`；`--force` 与 `--all` 同样处理。
- 结果新增 `droppedAttempts`（已删除，或 `--dry-run` 时将删除的路径，相对 Change 目录）与删除失败时的 `attemptsNotDropped`；删除失败不回滚归档。
- 删除基于目录 fd、不跟随符号链接：目录用 `shutil.rmtree(dir_fd=...)`，符号链接或文件只删除条目本身。
- 中英文 `cli-reference` 与 `plan-reference` 说明归档会删除 `.attempts`；BDD 与单元测试补齐。

## 改动文件

- 代码：`src/loopspec/workflow_archive.py`
- 测试：`tests/test_workflow_archive.py`（新增）、`tests/features/change.feature`、`tests/steps/change_steps.py`
- 文档：`docs/zh/cli-reference.md`、`docs/en/cli-reference.md`、`docs/zh/plan-reference.md`、`docs/en/plan-reference.md`

## 执行的检查

- `uv run ruff check src tests`：All checks passed
- `uv run mypy src hatch_version.py`：Success: no issues found in 40 source files
- `uv run pytest -q tests/test_workflow_archive.py`：11 passed
- `uv run pytest -q -n 2 -m "not timing and not llm"`：1688 passed, 1 skipped
- `make test-llm`：12 passed，15 次启动，$1.623，无重跑，`.llm-e2e-runs/20261119T143305Z/`（archive skill 依赖的 CLI 输出新增字段）

## 与设计的偏差

- 需求验收条件「`.attempts` 是指向外部的符号链接时归档成功」未按原样实现：归档前重新推导状态（settle / 返工记录读取）已有的保护会以 `unsafe_path` 拒绝整个归档，`--force` 也一样，不会移动或删除任何内容。这比「归档成功并删除链接」更保守，因此保留原有保护；`drop_attempts` 对符号链接只删除链接本身的行为由单元测试直接覆盖。

## 后续事项

- `archive/` 中已有的历史 `.attempts/` 未清理（非目标）。
