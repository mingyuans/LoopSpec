---
verdict: FAIL
summary: "移动后按路径重新打开归档目录删除 .attempts，未绑定刚移动的目录身份；Python 3.11 上深层 .attempts 的 rmtree RecursionError 未被捕获"
---

# 后端安全审查：失败

## 阻塞问题

- `src/loopspec/workflow_archive.py` `drop_attempts()`：在 `move()` 完成后按 `destination` 路径重新打开目录删除，期间若归档目标被另一棵目录树替换，会删除替代目录中的 `.attempts`；外层写锁的目录身份复核发生在删除之后。
- `src/loopspec/workflow_archive.py` `drop_attempts()`：只捕获 `OSError`/`WorkflowError`；Python 3.11 的 `shutil.rmtree` 对足够深的目录可抛 `RecursionError`，Change 已移动却异常退出，`--all` 中断后续归档。

## 审查输入

- 轮次 `001.1:be/security/check:1`，基线 `fa0dbbe9d2bfb49293908ec1e89156c77a7d24ac`。方法：人工审查 + Codex 只读审查（3 条；dry-run 获取写锁会创建 `plans/.write.lock` 为既有行为，记为剩余风险）。

## 建议修复方向

- 在 `move()` 持有的、随 rename 移动的 Change 目录 fd 上逐级（O_NOFOLLOW）打开 `plans/<NNN>` 后删除 `.attempts`，不再按路径重新解析。
- 捕获 `RecursionError` 并记入 `attemptsNotDropped`。
