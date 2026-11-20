---
verdict: PASS
summary: "ruff/mypy 通过；pytest（非 LLM）1762 passed, 1 skipped；make test-llm 12 passed（15 次启动，$1.831，无重跑）"
---

# 后端测试：通过

## 审查输入

- 轮次 `001.1:be/tests/check:1`，基线 `c926291972c6d73097a38a8ddb2208d5b87d4b70`。

## 执行的测试

- `uv run ruff check src tests hatch_version.py`：All checks passed!；`uv run mypy src hatch_version.py`：Success（51 source files）。
- `uv run pytest -q -n 2 -m "not timing and not llm"`：1762 passed, 1 skipped（gate begin 之后运行，期间未改代码）。含新增 `test_every_quoted_block_is_bounded_and_counted`、`test_quoted_text_cannot_end_its_block_early`、`test_state_and_core_blocks_are_bounded_and_counted`。
- `make test-llm`：12 passed in 129.43s，15 次启动，$1.831，无重跑，`.llm-e2e-runs/20261120T163058Z/`。

## 剩余风险

- 无。
