---
verdict: PASS
summary: "删除只作用于刚移动且身份已核对的 Change 目录，逐级 O_NOFOLLOW、不跟随符号链接，异常只报告；上轮两个阻塞问题与复核发现的 rename 竞态均已修复"
---

# 后端安全审查：通过

## 审查输入

- 轮次 `001.1:be/security/check:2`，基线 `fa0dbbe9d2bfb49293908ec1e89156c77a7d24ac`。方法：人工审查 + Codex 只读复核（确认上轮 2 条已修复，并指出 rename 前替换的竞态，已修复并有用例）。

## 审查结论

- 删除目标：只经 `move()` 持有的 Change 目录 fd 逐级以 O_NOFOLLOW 打开 `plans/<NNN>`；rename 后核对归档位置 inode 与该 fd 一致才删除，否则不删并由身份复核报错。
- 路径：被删条目名固定为 `.attempts`，Plan 编号来自 `plan_ids()`（三位数字且有 `plan.yaml`），不回显或拼接外部输入。
- 符号链接：`.attempts` 为链接时归档前的状态推导已拒绝；`drop_attempts` 对链接只删链接本身（`rmtree` 的 dir_fd 版本本身不跟随符号链接）。
- 失败处理：`OSError`/`RecursionError` 记入 `attemptsNotDropped`，不回滚已完成的归档；拒绝归档或移动失败时不删除。

## 剩余风险

- `--dry-run` 会获取写锁、可能创建 `plans/.write.lock`（既有行为）。
- 删除不可恢复；可先用 `--dry-run` 预览。
