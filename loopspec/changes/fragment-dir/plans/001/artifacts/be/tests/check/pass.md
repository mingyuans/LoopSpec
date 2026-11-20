---
verdict: PASS
summary: "ruff/mypy 通过；pytest（非 LLM）1765 passed, 1 skipped；make test-llm 13 passed（16 次启动，$1.876，无重跑），新场景按 fragmentDir 读到快照中的辅助文件"
---

# 后端测试：通过

## 审查输入

- 轮次 `001.1:be/tests/check:1`，基线 `c926291972c6d73097a38a8ddb2208d5b87d4b70`（feat/text-output），审查 gate begin 固定的工作区改动。

## 执行的测试

- `uv run ruff check src tests hatch_version.py`：All checks passed!
- `uv run mypy src hatch_version.py`：Success: no issues found in 51 source files
- `uv run pytest -q -n 2 -m "not timing and not llm"`：1765 passed, 1 skipped（含 `tests/test_fragment_paths.py` 5 项、node_gate 新场景）。以上在 gate begin 前对同一代码运行，之后未改代码。
- `make test-llm`：13 passed in 138.29s，16 次模型启动，合计 $1.876，无重跑，记录 `.llm-e2e-runs/20261120T160002Z/`。新场景「指令引用的辅助文件按 fragmentDir 在注册表快照中找到」通过：转录中模型读取了 NODE 的 fragmentDir 并打开 `references/rules.md`，产物写入口令。

## 剩余风险

- 无阻塞项。
