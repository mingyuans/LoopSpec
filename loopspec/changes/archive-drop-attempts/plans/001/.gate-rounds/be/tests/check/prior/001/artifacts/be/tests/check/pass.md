---
verdict: PASS
summary: "本轮固定输入下 lint、类型检查、全量单元/BDD 与 timing 测试全部通过，新增 11 个归档单测与 1 个 BDD 场景；LLM E2E 12 个场景在同一代码上通过"
---

# 后端测试：通过

## 审查输入

- 轮次 `001.1:be/tests/check:1`，基线 `fa0dbbe9d2bfb49293908ec1e89156c77a7d24ac`。

## 执行的测试

- `uv run ruff check src tests hatch_version.py`：All checks passed!
- `uv run mypy src hatch_version.py`：Success: no issues found in 40 source files
- `uv run pytest -q -n 2 -m "not timing and not llm"`：1688 passed, 1 skipped in 115.48s (0:01:55)
- `uv run pytest -q -m "timing and not llm"`：3 passed, 1701 deselected in 5.72s
- `tests/test_workflow_archive.py`（11）：有返工记录时删除并保留其余文件；无返工时为空列表；dry-run 只报告不删除；--force 删除；拒绝归档与归档冲突时不删除；多个 Plan（含已归档 Plan）全部删除；--all 删除；符号链接 `.attempts` 在状态推导时被拒且外部目录不受影响；`drop_attempts` 只删链接本身；删除失败只报告不回滚。
- BDD `change.feature`「归档有返工记录的 Change 时删除 .attempts」：预览不删除、归档后删除。
- LLM E2E（同一代码）：`make test-llm` 12 passed，$1.623，`.llm-e2e-runs/20261119T143305Z/`。

## 剩余风险

- 本机内存原因以 `-n 2` 运行同一选择器。
