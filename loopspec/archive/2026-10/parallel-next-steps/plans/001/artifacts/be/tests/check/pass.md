---
verdict: PASS
summary: "返工后固定输入下 make lint 通过，全部 40 个测试文件分两批运行共 1081 passed（含 node instructions 按需加锁的 2 个新用例）"
---

# 后端测试：通过

## 审查输入

- 轮次：`001.1:be/tests/check:2`，基线 `1c5ce6ad00450d3639c64501523fd377492fbfc9`，scopeDigest `dcd579f0…`，warnings 为空。
- 固定路径：`src/loopspec/{status_report,workflow_changes,workflow_cli,workflow_runtime}.py`、`tests/{test_skill_templates,test_status_report,test_workflow_recovery,test_workflow_runtime}.py`。

## 执行的测试

- `make lint`：ruff `All checks passed!`；mypy `Success: no issues found in 34 source files`。
- 全量 pytest：因单次命令时限，按文件名顺序分两批运行全部 40 个 `tests/test_*.py`：
  - 第 1–20 个文件：`733 passed in 189.07s`。
  - 第 21–40 个文件：`348 passed in 347.39s`。
  - 合计 1081 passed（上一轮 1079 + 本轮新增 2）。
- 返工新增用例：
  - `test_instructions_read_without_the_lock_when_nothing_is_pending`：其他命令持写锁时，`node instructions` 仍返回 ready 节点（修复前失败）。
  - `test_instructions_still_lock_to_finish_pending_archiving`：存在未完成返工归档时仍需写锁（持锁时报 `concurrent_write`），释放后补完归档并返回。
- 已有的 `history_integrity` 恢复用例（篡改归档目标、越界 record）仍通过，说明待归档时仍走加锁 + settle 路径。

## 剩余风险

- 全量测试分两批而非单次 `make test` 运行（上一次后台 `make test` 因系统内存不足被停止）；覆盖的测试文件相同。
