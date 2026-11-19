---
verdict: PASS
summary: "返工后本轮固定输入下 lint、类型检查、1649 个单元/BDD 测试与 3 个 timing 测试全部通过；LLM E2E 12 个场景在同一代码上通过"
---

# 后端测试：通过

## 审查输入

- 轮次 `001.1:be/tests/check:2`，基线 `04812daa63283f7991d1c4684958e3538b816928`，23 个固定路径（src/loopspec 下 8 个、tests 下 15 个）。

## 执行的测试

- `uv run ruff check src tests hatch_version.py`：All checks passed!
- `uv run mypy src hatch_version.py`：Success: no issues found in 40 source files
- `uv run pytest -q -n 2 -m "not timing and not llm"`：1649 passed, 1 skipped（基线 1615 passed, 1 skipped）
- `uv run pytest -q -m "timing and not llm"`：3 passed
- 返工新增覆盖：存储路径中间符号链接被拒；伪造 lock 以已发布 tag 指向未发布 commit 时报 `registry_lock_mismatch`；超深嵌套与重复键 lock 报 `config_invalid`；超深嵌套计划报 `registry_plan_stale`；`fetch_commit` 严格失败；LLM 守卫只允许 fixture registry 且存储在项目内。
- 其余覆盖同上一轮：全局存储（物化、离线复用、篡改、权限、并发首次发布、本地冲突、v1 兼容）、update/apply 全部分支、CLI list/save/graph/init、BDD registry 7 个场景。
- LLM E2E（同一代码）：`make test-llm` 12 passed，15 次启动，$1.628，无重跑，`.llm-e2e-runs/20261119T043103Z/`。

## 剩余风险

- 本机内存不足以运行 `-n auto`/`-n 4`（进程被以 137 终止），测试以 `-n 2` 运行，选择器与 `make test` 相同。
- SHA-256 对象格式 registry 只有代码路径，未用真实 SHA-256 仓库测试。
