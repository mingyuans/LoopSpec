---
verdict: PASS
summary: "本轮固定输入下 lint、类型检查、1637 个单元/BDD 测试与 3 个 timing 测试全部通过；LLM E2E 12 个场景已在同一代码上通过"
---

# 后端测试：通过

## 审查输入

- 轮次 `001.1:be/tests/check:1`，基线 `04812daa63283f7991d1c4684958e3538b816928`。
- 固定路径：`src/loopspec/{cli,registry_git,registry_store,registry_sync,workflow_assurance,workflow_catalog,workflow_cli,workflow_runtime}.py` 与 `tests/` 下 15 个改动文件（含新增 `tests/test_registry_store.py`）。

## 执行的测试

- `uv run ruff check src tests hatch_version.py`：All checks passed!
- `uv run mypy src hatch_version.py`：Success: no issues found in 40 source files
- `uv run pytest -q -n 4 -m "not timing and not llm"`：1637 passed, 1 skipped（基线 1615 passed, 1 skipped）
- `uv run pytest -q -m "timing and not llm"`：3 passed
- 覆盖要点：
  - `tests/test_registry_store.py`（24）：新 clone 自动拉取、同 commit 第二个 checkout 离线可用、lock 缺失/来源不一致/hash 不符（不留快照）、快照文件或 manifest 被篡改、读取时篡改、registry 不可达且存储为空、符号链接与组可写存储根、新目录 0700、中断残留临时目录、4 进程并发首次发布、本地与 registry 定义混用、三类本地同名冲突与删除后恢复、v1 lock 兼容与 `held`、非 registry 项目不变、assurance 同时读取 registry 规则与 config 规则。
  - `tests/test_registry_sync.py`（27）：首次 update 不改项目（`git status` 干净）、首次 apply 只写 lock、latest 与固定 tag 的快速路径（git 调用计数）、`--full`、added/modified/deleted 与 base/upstream 内容、apply 立即影响运行中 Plan、旧 commit 被改写历史后 `baseAvailable: false`、四类 stale、并发 apply、本地冲突、registry 新增与本地同名、删除被 profile 使用的 fragment、已失效本地定义不阻塞、破坏运行中 Plan、required_fragments、v1 迁移、来源切换、`registry.path`、非法 lock、相对 home。
  - `tests/test_registry_git.py`：`fetch_commit` 按 tag/按 commit 成功与严格失败。
  - CLI：`test_workflow_cli.py`（`--skip` 已移除、list 的 `source`、`profile save` 同名、`graph --profile`）、`test_cli.py`（registry 模式 init 两种参数）。
  - BDD `registry.feature` 7 个场景通过。
- LLM E2E（同一代码，gate begin 前执行）：`make test-llm` 12 passed，15 次启动，$1.641，无重跑，`.llm-e2e-runs/20261119T042134Z/`。

## 剩余风险

- 本机 `-n auto` 会被内存限制终止，测试以 `-n 4` 运行，选择器与 `make test` 相同。
- SHA-256 对象格式的 registry 仅有代码路径与参数，未用真实 SHA-256 仓库测试。
