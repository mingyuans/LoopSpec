---
verdict: PASS
summary: "本轮固定输入下 make test 946 passed（含 8 个偏离提交用例），ruff 与 mypy 通过"
---

# 后端测试：通过

## 审查输入
- 轮次 `001.1:be/tests/check:1`，基线 `aea1744`，scopeDigest `8c4fe02f9ac9…`
- 5 个文件：`src/loopspec/workflow_{assurance,diff,evidence}.py`、`tests/test_workflow_{assurance,diff}.py`
- 本轮 `warnings` 为空

## 执行的测试
- `make test`：946 passed（8 分 3 秒）
- `make lint`：ruff All checks passed；mypy Success
- 覆盖的验收条件：
  - 绕过回归：PASS 后提交未审查内容、工作区恢复审查版本，status 不是 complete（assurance 为 `evidence_stale`），`archive --dry-run` 返回 `archive_unsafe`；重新判定 FAIL，`diverged_commits=["frontend/code.py"]`，`f.md` 中列出该路径
  - 绕过发生在 assurance 之前：FAIL，且只有 `diverged_commits` 一类问题
  - 正常提交流程：原有 `test_committing_after_gates_keeps_change_complete_and_archivable` 通过
  - 中间提交：diff 层 `diverged` 包含该路径，最终提交后为空；assurance 层代码 Gate 仍可 begin/record，最终提交后 PASS 且 complete
  - 提交后改回基线：`entries` 为空，`diverged` 包含该路径
  - 被排除路径不检查
  - `diverged` 不影响两个摘要
  - FAIL 摘要在 30 个长路径加两类告警时仍通过 `FailureReport` 校验

## 剩余风险
- 只存在于 HEAD、工作区和基线都没有的路径（例如 `git rm --cached` 后删除），按逻辑会记为偏离，没有单独写测试。
