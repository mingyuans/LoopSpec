---
verdict: FAIL
summary: "Diff 排除只核对工作区内容，被排除的 skill 路径同时跳过了暂存区一致性与 HEAD 中未审查提交的检查，可借此提交未经审查的 skill 指令"
---

# 后端安全审查：失败

## 阻塞问题

- `src/loopspec/workflow_diff.py` `_exclusions().managed_skill()`：只要工作区是与模板相同的普通文件就排除该路径；而 `collect_diff` 对被排除路径直接 `continue`，不再做 index 与 worktree 一致性检查，也不进入 diverged commits 判定。先在 managed skill 路径提交任意内容、再把工作区恢复为模板内容，这段未经审查的 skill 指令就能通过 assurance。

## 审查输入

- 轮次 `001.1:be/security/check:1`，基线 `23738851a934917e94014f0213dbd51d8dde03e1`。方法：人工审查（Codex 只读审查超时）。其余方面（只写项目根内固定路径、逐级 O_NOFOLLOW 写入与读取、异常不影响命令、未配置工具不创建）未发现问题。

## 建议修复方向

- 只有当该路径在暂存区与 HEAD 中的版本（若与基线不同）也等于模板内容（按 Git blob id 比较）时才排除；否则照常计入 Diff 与各项一致性检查。
