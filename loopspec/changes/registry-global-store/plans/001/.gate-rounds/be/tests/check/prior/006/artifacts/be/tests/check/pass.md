---
verdict: PASS
summary: "source-id 改为可读前缀加短 hash 后，本轮固定输入下 lint、类型检查、全量单元/BDD 与 timing 测试通过；LLM E2E 12 个场景在同一代码上通过"
---

# 后端测试：通过

## 审查输入

- 轮次 `001.1:be/tests/check:6`，基线 `04812daa63283f7991d1c4684958e3538b816928`。

## 执行的测试

- `uv run ruff check src tests hatch_version.py`：All checks passed!
- `uv run mypy src hatch_version.py`：Success: no issues found in 40 source files
- `uv run pytest -q -n 2 -m "not timing and not llm"`：1675 passed, 1 skipped in 113.40s (0:01:53)
- `uv run pytest -q -m "timing and not llm"`：3 passed, 1688 deselected in 5.63s
- 本轮新增覆盖：`source_id` 为 `<仓库名>[-<path>]-<hash8>`、只含 `[a-z0-9-]`；SSH/HTTPS 写法与不同 path 区分；超长仓库名截断。
- LLM E2E（同一代码）：`make test-llm` 12 passed，15 次启动，$1.709，无重跑，`.llm-e2e-runs/20261119T073440Z/`。

## 剩余风险

- 本机内存不足以运行 `-n auto`/`-n 4`，以 `-n 2` 运行同一选择器。
- SHA-256 对象格式 registry 只有代码路径，未用真实 SHA-256 仓库测试。
