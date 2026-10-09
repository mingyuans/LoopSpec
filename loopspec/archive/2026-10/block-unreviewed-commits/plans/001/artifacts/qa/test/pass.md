---
verdict: PASS
summary: "源码版 CLI 端到端验证通过：提交未审查内容后需求退回未完成、归档被拒、assurance 判 FAIL，提交审查过的内容后恢复 PASS 并能归档"
---

# 验收测试：通过

## 验收条件核对
- [x] 绕过回归（assurance 之后）：PASS 后提交 `print('UNREVIEWED')`，工作区恢复为审查过的 `print('reviewed')`；status 为 `active`，assurance 的 reason 为 `evidence_stale`；`archive --dry-run` 返回 1 / `archive_unsafe`；重新执行 assurance 判 FAIL，`diverged=['backend/app.py']`，`fail.md` 写明了路径与处理方法。
- [x] 绕过发生在 assurance 之前：单元测试 `test_unreviewed_commit_before_assurance_fails` 通过。
- [x] 正常流程：把审查过的内容提交后，assurance 判 PASS，`diverged=[]`，`change archive` 成功（exit 0，`complete=True`，`moved=True`）；原有提交后归档的用例也通过。
- [x] 中间提交后继续修改：单元测试（diff 层和 assurance 层）通过，代码 Gate 可用，最终提交后 PASS。
- [x] 提交后改回基线算偏离、被排除路径不检查、`diverged` 不影响摘要：对应单元测试通过。
- [x] `make test` 946 passed，`make lint` 通过，文档一致性测试通过（在 be/tests 轮次执行）。

## 执行的测试
- 在 scratchpad 中执行 `python3 -I qa/e2e_diverged.py <LoopSpec> qa/diverged`，CLI 用 `uv run --project <LoopSpec> loopspec` 运行当前源码。步骤：
  1. `init` → `change new` → `plan create/approve`（backend-implementation + change-assurance）
  2. 修改 `backend/app.py`，三个代码 Gate 通过，assurance PASS
  3. 提交未审查内容，工作区恢复审查版本 → status → `archive --dry-run` → assurance
  4. 提交审查过的内容 → assurance → `archive`
- 输出与上方各条一致。

## 剩余风险
- 修复路径（第 5 步）提交审查过的内容之后，那次未审查的中间提交仍然留在 git 历史里，只是最终 HEAD 的内容是审查过的。如果需要历史中每个提交都经过审查，要依靠 squash 合并或远端 PR review，这超出本需求的范围。
- 只检查本地 HEAD，不检查远端。
