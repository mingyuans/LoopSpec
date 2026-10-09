---
verdict: PASS
summary: "安全返工后本轮固定的 16 个文件上 make test 898 passed / 1 skipped（与本次无关的 dist 依赖用例），registry 专项 101 passed（含 12 项安全回归），ruff 与 mypy 通过"
---

# 后端测试：通过

## 审查输入
- 轮次：`001.1:be/tests/check:3`；基线 `9b90c66c11bab432176d640cfc6caad760706fcc`；Plan digest `321f50cd…2552`。
- 固定路径（16 个）：`builtin/skills/update-registry.md`、`src/loopspec/{models,registry_git,registry_sync,workflow_cli,workflow_planning}.py`、`tests/registry_helpers.py`、`tests/test_registry_{config,git,sync}.py`、`tests/test_{builtin_resources,cli,docs_consistency,scaffold,skill_templates,workflow_cli}.py`。
- 本轮包含安全 Gate 第 1 轮 FAIL 后的返工（priorAttempts seq 1）。

## 执行的测试
- `make test`：898 passed, 1 skipped in 399.54s。跳过的是 `tests/test_release_workflow.py` 中需要 `dist/` 的用例（`dist/` 已按用户决定删除），与本次改动无关。
- `uv run pytest -q tests/test_registry_config.py tests/test_registry_git.py tests/test_registry_sync.py`：101 passed in 95.84s。其中包括安全回归：
  - 缓存中预置的 `repo.git`，其 config 里的 `url.insteadOf` 不生效
  - `repo.git` 为符号链接时返回 `unsafe_path`，链接目标保持不变
  - 远端文件名带 `$( )`、反引号、`;`、U+202E、空格或引号时被丢弃，且 warning 不回显原名
  - ssh 用户名不能以 `-` 开头
  - 本地名称不合法的文件被忽略
  - 锁文件中出现不合法的文件名时返回 `config_invalid`
  - 伪造的 plan.json 不能写到定义目录之外
  - 1900 个 blob 的批量读取不会死锁
- `make lint`：ruff 显示 All checks passed；mypy 显示 Success: no issues found in 31 source files。

## 剩余风险
- 测试只使用 `file://` 本地仓库，没有真实访问 GitHub 的 https / ssh；建议发布前对一个私有 GitHub registry 手工验证一次。
- `cat-file` 死锁的回归测试在 macOS 上修复前也能通过（macOS 的 pipe 行为下没有复现），因此它只是防回归保护，不能证明修复有效；修复的正确性由代码结构保证（后台线程写 stdin，超时覆盖整个过程）。
- 被跳过的 release 用例需要在有 `dist/` 的环境（例如 CI）中运行。
