---
verdict: PASS
summary: "第 3 次返工后本轮固定输入下 lint、类型检查、1660 个单元/BDD 测试与 3 个 timing 测试全部通过；LLM E2E 12 个场景在同一代码上通过"
---

# 后端测试：通过

## 审查输入

- 轮次 `001.1:be/tests/check:4`，基线 `04812daa63283f7991d1c4684958e3538b816928`，23 个固定路径。

## 执行的测试

- `uv run ruff check src tests hatch_version.py`：All checks passed!
- `uv run mypy src hatch_version.py`：Success: no issues found in 40 source files
- `uv run pytest -q -n 2 -m "not timing and not llm"`：1660 passed, 1 skipped（基线 1615 passed, 1 skipped）
- `uv run pytest -q -m "timing and not llm"`：3 passed
- 本轮新增覆盖：固定 tag 项目的 lock 省略或改写 tag 报 `registry_lock_mismatch`；守卫在 `--note --home=…` 诱饵下仍检查默认 home 并拒绝。
- LLM E2E（同一代码）：`make test-llm` 12 passed，15 次启动，$1.673，无重跑，`.llm-e2e-runs/20261119T051151Z/`。

## 剩余风险

- 本机内存不足以运行 `-n auto`/`-n 4`，以 `-n 2` 运行同一选择器。
- SHA-256 对象格式 registry 只有代码路径，未用真实 SHA-256 仓库测试。
