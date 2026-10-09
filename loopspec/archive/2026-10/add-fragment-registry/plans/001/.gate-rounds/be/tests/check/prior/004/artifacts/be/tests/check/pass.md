---
verdict: PASS
summary: "代码审查返工后本轮固定的 16 个文件上 make test 905 passed / 1 skipped（与本次无关的 dist 依赖用例），registry 专项 108 passed，ruff 与 mypy 通过"
---

# 后端测试：通过

## 审查输入
- 轮次：`001.1:be/tests/check:4`；基线 `9b90c66c11bab432176d640cfc6caad760706fcc`；Plan digest `321f50cd…2552`。
- 固定路径 16 个（与此前各轮相同）。本轮包含安全 Gate 返工（priorAttempts seq 1）与代码审查 Gate 返工（seq 2）。

## 执行的测试
- `make test`：905 passed, 1 skipped in 319.49s。跳过的是 `tests/test_release_workflow.py` 中需要 `dist/` 的用例（`dist/` 已按用户决定删除），与本次改动无关。
- `uv run pytest -q tests/test_registry_config.py tests/test_registry_git.py tests/test_registry_sync.py`：108 passed in 106.97s。在上一轮的基础上，本轮新增：
  - 被 skip 的新增定义在 latest 和固定 tag 下都不会被遗忘，`held` 会被写入并在之后清空
  - 本地 Profile 引用了上游删除的 Fragment 时，apply 在写入前失败
  - 本地原本就坏的定义不阻塞同步
  - 来源变化后不会规划任何删除，且 `baseAvailable: false`
  - 固定 tag 与 latest 之间互相切换
  - 冲突选择 local 后定义版本照常推进
- `make lint`：ruff 显示 All checks passed；mypy 显示 Success: no issues found in 31 source files。

## 剩余风险
- 只使用 `file://` 本地仓库测试，没有真实访问 GitHub 的 https / ssh；建议发布前对私有 GitHub registry 手工验证一次。
- 被跳过的 release 用例需要在有 `dist/` 的环境（例如 CI）中运行。
