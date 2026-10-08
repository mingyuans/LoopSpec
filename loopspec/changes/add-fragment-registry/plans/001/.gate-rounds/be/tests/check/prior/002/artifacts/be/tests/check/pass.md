---
verdict: PASS
summary: "本轮固定的 16 个文件上 make test 886 passed / 1 skipped（与本次无关的 dist 依赖用例），registry 专项 89 passed，ruff 与 mypy 通过"
---

# 后端测试：通过

## 审查输入
- 轮次：`001.1:be/tests/check:2`；基线 `9b90c66c11bab432176d640cfc6caad760706fcc`；Plan digest `321f50cd…2552`。
- 固定路径（16 个）：`builtin/skills/update-registry.md`、`src/loopspec/{models,registry_git,registry_sync,workflow_cli,workflow_planning}.py`、`tests/registry_helpers.py`、`tests/test_registry_{config,git,sync}.py`、`tests/test_{builtin_resources,cli,docs_consistency,scaffold,skill_templates,workflow_cli}.py`。

## 执行的测试
- `make test`：886 passed, 1 skipped in 438.06s。被跳过的是 `tests/test_release_workflow.py` 中要求先 `make build` 生成 `dist/` 的用例（`dist/` 已按用户决定删除，以免阻塞 Gate），与本次改动无关。
- `uv run pytest -q tests/test_registry_config.py tests/test_registry_git.py tests/test_registry_sync.py`：89 passed in 67.84s。覆盖范围：
  - URL / version / path 白名单，且错误消息不回显 URL
  - ls-remote 解析与 latest 选择
  - git 缺失返回 `registry_unavailable`；拉取失败返回 `registry_fetch_failed`，消息经过脱敏和截断
  - 环境变量 `GIT_DIR` / `GIT_CONFIG_PARAMETERS` 不能重定向仓库
  - 读树时拒绝符号链接、子模块和非法名称，并检查超限与 path 不存在
  - 七类分类；update 不写本地文件；commit 不变时只调用 ls-remote；固定 tag 时零 git 调用；`--full`
  - apply 的计划过期、冲突未解决、resolve / skip 非法、本地漂移、staging 被篡改、校验失败零写入、skip 保留基线和版本、删除并清理空目录、并发写锁
  - 相对路径的 home
- 本轮执行前，实现阶段的同一代码已跑过一次 `make test`（887 passed，当时 `dist/` 还在）。
- `make lint`：ruff 显示 All checks passed；mypy 显示 Success: no issues found in 31 source files。
- 手工冒烟（实现阶段）：在 `file://` 本地 registry 上跑完 update、apply、upToDate、冲突、skip 与版本展示的完整流程。

## 剩余风险
- 测试只使用 `file://` 本地仓库，没有真正访问 GitHub 的 https / ssh。协议白名单和凭据继承由代码审查保证，没有真实网络测试；建议发布前对一个私有 GitHub registry 手工验证一次。
- 被跳过的 release 用例需要在有 `dist/` 的环境（例如 CI）中运行。
