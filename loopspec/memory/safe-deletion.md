# 安全删除工作区内的目录与文件

适用时机：在 LoopSpec 代码中删除或移动 workflow home 内的目录与文件时（例如归档后的清理）。

- 先完成移动，再删除；删除通过移动时一直持有的目录 fd 进行，rename 之后先核对目标位置的 inode 与该 fd 一致才删除；每一级都以 `O_DIRECTORY|O_NOFOLLOW` 相对 fd 打开，符号链接只删除条目本身；`OSError` 与 `RecursionError` 只报告、不回滚已完成的移动。原因：按路径重新打开会删到被并发替换的目录，rename 前被替换则会删到未归档的原目录。来源：archive-drop-attempts 安全审查第 1 轮 FAIL 与返工（2026-11-19），回归用例见 `tests/test_workflow_archive.py`（`test_drop_follows_the_moved_directory_not_the_path`、`test_nothing_is_dropped_when_another_directory_was_moved`），已通过。
- 删除范围来自 `plan.yaml` 等可能被篡改的文件时，先经 `relative_path` 校验并限制在预期子目录（如只删 `artifacts/` 下的 Gate 报告），删空目录的清理不越过该子目录。来源：archive-drop-gate-outputs 安全审查（2026-11-19，人工审查结论）。
