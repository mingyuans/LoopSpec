---
verdict: PASS
summary: "第 4 次返工后本轮固定输入下 lint、类型检查、1670 个单元/BDD 测试与 3 个 timing 测试全部通过；LLM E2E 12 个场景在同一代码上通过"
---

# 后端测试：通过

## 审查输入

- 轮次 `001.1:be/tests/check:5`，基线 `04812daa63283f7991d1c4684958e3538b816928`，23 个固定路径。

## 执行的测试

- `uv run ruff check src tests hatch_version.py`：All checks passed!
- `uv run mypy src hatch_version.py`：Success: no issues found in 40 source files
- `uv run pytest -q -n 2 -m "not timing and not llm"`：1670 passed, 1 skipped（基线 1615 passed, 1 skipped）
- `uv run pytest -q -m "timing and not llm"`：3 passed
- 本轮新增覆盖：同 commit 改绑 tag 与首次打 tag 生成计划；无文件变化的来源切换输出 `sourceChanged`/`previousRegistry`；目标 lock 超限时不发布计划；超大 lock 为 `config_invalid`；非 registry 项目带旧字段或坏 YAML 的 config 仍可读定义；一次 `node instructions` 只解析一次 lock；改绑 tag 后离线可用；v1 lock 超过 2048 条目可读。
- LLM E2E（同一代码）：`make test-llm` 12 passed，15 次启动，$1.666，无重跑，`.llm-e2e-runs/20261119T054402Z/`。

## 剩余风险

- 本机内存不足以运行 `-n auto`/`-n 4`，以 `-n 2` 运行同一选择器。
- SHA-256 对象格式 registry 只有代码路径，未用真实 SHA-256 仓库测试。
