---
verdict: PASS
summary: "用本分支 CLI 在临时项目中端到端验证归档删除 .attempts：单个、dry-run、拒绝、--force、--all 全部符合验收条件"
---

# 验收测试：通过

## 验收条件核对

- [x] AC1 有返工记录的 complete Change 归档后：归档目录只有 `.workflow.yaml`、`state.md`、`plans/001/{plan.yaml,state.md,artifacts}`，`find -name .attempts` 为 0；原 Change 目录已移走。
- [x] AC2 结果 `droppedAttempts` 为 `['plans/001/.attempts']`；无返工时为空列表（单测 `test_archive_without_rework_drops_nothing`）。
- [x] AC3 `--dry-run` 返回 `['plans/001/.attempts']`，磁盘上 `.attempts/001` 仍在。
- [x] AC4 未完成 Change `--force` 归档：`forced: true`，`.attempts` 被删除。
- [x] AC5 `--all`：归档项 `droppedAttempts` 正确，`archive/` 下无 `.attempts`。
- [x] AC6 多个 Plan（含已 `plan archive` 的 Plan）全部删除：单测 `test_attempts_of_every_plan_are_dropped`。
- [x] AC7 符号链接 `.attempts`：按偏差记录，归档以 `unsafe_path` 拒绝、外部目录不受影响（单测）；`drop_attempts` 只删链接本身（单测）。
- [x] AC8 未完成 Change 默认归档被拒（`archive_unsafe`）时 `.attempts` 保持不变；`archive_conflict` 同样不删除（单测）。
- [x] AC9 lint、全量测试与 docs 一致性通过（见 be/tests/check）。

## 执行的测试

- `artifacts/qa/test/acceptance.sh <worktree>/.venv/bin/loopspec`：在 `/tmp/lpqa2/run.upab` 中 10 项 PASS、0 FAIL；人工检查归档目录内容确认无 `.attempts`。
- `uv run pytest -q tests/test_workflow_archive.py`：14 passed；全量 1691 passed, 1 skipped。

## 剩余风险

- `archive/` 中已有的历史 `.attempts/` 不清理（非目标）。
