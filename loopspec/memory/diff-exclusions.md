# 交付 Diff 的固定排除

适用时机：在 `workflow_diff` 中新增或修改「固定不计入交付 Diff」的路径时（如 `.cache`、memory topic、loopspec 管理的 skill 文件）。

- 排除条件不能只看工作区：`collect_diff` 对被排除的路径直接跳过，连同暂存区与工作区一致性检查、HEAD 中未审查提交（diverged）检查一起跳过。必须同时核对暂存区与 HEAD 中与基线不同的版本（按 Git blob id 比较），否则可以先提交任意内容、再把工作区恢复成「可排除」的样子来绕过审查。原因与来源：skill-auto-sync 安全审查第 1 轮 FAIL 与返工（2026-11-19），回归用例 `tests/test_skill_sync.py` 的 `test_committed_unreviewed_content_is_not_hidden`、`test_staged_content_different_from_the_template_is_not_hidden` 已通过。
- 只排除精确路径上的普通文件，并核对内容（如与模板逐字节相同、topic 名合法）；符号链接、删除、同目录的其他文件照常计入。来源：同上，以及 memory topic 排除的既有实现。
