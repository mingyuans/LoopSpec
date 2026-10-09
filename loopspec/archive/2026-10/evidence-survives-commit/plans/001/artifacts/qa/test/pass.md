---
verdict: PASS
summary: "源码版 CLI 端到端验证通过：审查中途提交、Gate 通过后提交都不影响证据，提交后改代码证据失效，改回后可正常归档"
---

# 验收测试：通过

## 验收条件核对
- [x] 修改、新增、删除、改名在 `git add` 和 `git commit` 前后摘要不变：单元测试 `test_staging_and_committing_keep_digests` 通过；端到端中修改的 `backend/app.py` 和新增的 `backend/new.py` 提交后，证据仍然有效。
- [x] 提交后修改工作区，摘要改变：端到端提交后把 `backend/app.py` 改为 `print(3)`，status 变为 active，`be/tests/check`、`be/security/check`、`be/review/check`、`assurance/check` 均为 `evidence_stale`。
- [x] 部分暂存仍然报 `index_worktree_mismatch`（提交前、提交后）：单元测试 `test_staged_worktree_divergence_rejected`、`test_after_commit_partial_staging_is_still_rejected` 通过。
- [x] 提交后改回基线内容不算改动：单元测试 `test_committed_then_reverted_file_is_not_a_change` 通过。
- [x] Gate 与 assurance 通过后执行 `git add -A` 和 `git commit`，仍为 complete，可以归档：端到端提交后 status 为 `complete`、`isComplete=True`；把工作区恢复为审查过的内容后，`change archive` 成功（exit 0，`complete=True`，`moved=True`）。
- [x] 审查轮次中途提交，`record` 成功：端到端在 `be/review/check` 的 begin 和 record 之间提交了 `backend/app.py`，record 返回 PASS。
- [x] `gate begin` 输出仍包含 `paths[*].index`：单元测试 `test_committing_during_review_round_still_records` 断言通过。
- [x] `make test` 938 passed，`make lint` 通过，文档一致性测试通过（在 be/tests 第 2 轮执行）。

## 执行的测试
- 在 scratchpad 中执行 `python3 -I qa/e2e_commit.py <LoopSpec> qa/commit`，CLI 用 `uv run --project <LoopSpec> loopspec` 直接运行当前源码。步骤：
  1. `git init` → `loopspec init --tools none`
  2. `change new` → `plan create/approve`（backend-implementation + change-assurance）
  3. 修改 `backend/app.py`，新增 `backend/new.py`
  4. 三个代码 Gate begin/record（review 轮次中途提交）
  5. assurance record → `git add -A` 加 `git commit` → status
  6. 改代码 → status
  7. 恢复内容 → `change archive`
- 输出：三个 Gate PASS、assurance PASS、提交后 complete、改代码后 4 个节点 stale、恢复后归档成功。

## 剩余风险
- 本需求自己的 Gate 证据是用全局安装的旧版 CLI 记录的（旧摘要格式）。安装新版后，未归档需求的证据会失效，这正是 release notes 里写明的升级影响。因此本需求应当先归档、提交，再安装新版。
- 没有覆盖 rebase 等改写历史的情况。
