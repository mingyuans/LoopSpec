---
verdict: PASS
summary: "source-id 改为可读前缀加短 hash、tag 绑定记录带上来源后，本轮固定输入下 lint、类型检查、全量单元/BDD 与 timing 测试通过"
---

# 后端测试：通过

## 审查输入

- 轮次 `001.1:be/tests/check:7`，基线 `04812daa63283f7991d1c4684958e3538b816928`。

## 执行的测试

- `uv run ruff check src tests hatch_version.py`：All checks passed!
- `uv run mypy src hatch_version.py`：Success: no issues found in 40 source files
- `uv run pytest -q -n 2 -m "not timing and not llm"`：1676 passed, 1 skipped in 121.05s (0:02:01)
- `uv run pytest -q -m "timing and not llm"`：3 passed, 1689 deselected in 3.81s
- 本轮新增覆盖：`source_id` 格式与区分性；tag 绑定记录包含 url/path/tag/commit，来源不符的记录不被信任（离线时报 `registry_fetch_failed`）。
- LLM E2E：source-id 改动后运行 `make test-llm` 12 passed（$1.709，`.llm-e2e-runs/20261119T073440Z/`）；其后的 tag 绑定记录格式改动不影响 skill 可见的 CLI 输出，未重跑。

## 剩余风险

- 本机内存不足以运行 `-n auto`/`-n 4`，以 `-n 2` 运行同一选择器。
- SHA-256 对象格式 registry 只有代码路径，未用真实 SHA-256 仓库测试。
