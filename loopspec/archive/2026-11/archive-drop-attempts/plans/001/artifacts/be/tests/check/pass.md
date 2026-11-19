---
verdict: PASS
summary: "返工后本轮固定输入下 lint、类型检查、全量单元/BDD 与 timing 测试全部通过，归档单测 14 个"
---

# 后端测试：通过

## 审查输入

- 轮次 `001.1:be/tests/check:2`，基线 `fa0dbbe9d2bfb49293908ec1e89156c77a7d24ac`。

## 执行的测试

- `uv run ruff check src tests hatch_version.py`：All checks passed!；`uv run mypy src hatch_version.py`：Success
- `uv run pytest -q -n 2 -m "not timing and not llm"`：1691 passed, 1 skipped in 113.62s (0:01:53)
- `uv run pytest -q -m "timing and not llm"`：3 passed, 1704 deselected in 3.64s
- 返工新增：归档路径在移动后被替换时只删已移动目录；`RecursionError` 只报告；源目录在 rename 前被替换时不删除任何 `.attempts` 并报错。
- LLM E2E：返工前 `make test-llm` 12 passed（$1.623，`.llm-e2e-runs/20261119T143305Z/`）；返工未改变 CLI 输出，未重跑。

## 剩余风险

- 本机内存原因以 `-n 2` 运行。
