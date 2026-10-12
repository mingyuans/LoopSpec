---
verdict: FAIL
summary: "并行扇出、汇总 Gate、rollback 后再次并行均符合预期，但三个 sub agent 并发执行 node instructions 时有两个返回 concurrent_write，不满足并行节点互不影响的验收条件"
---

# 验收测试：失败

## 失败的验收条件

- 验收条件“并行 sub agent 分别对 B、C、D 执行 `node instructions` 与写产物不互相影响”
  - 复现步骤：临时仓库中 `loopspec init`，按扇出请求（prd → be/fe/qa-review → review-gate）创建并确认 Plan，写入 `prd/proposal.md`，然后同时在后台运行三条 `loopspec node instructions -c demo2 -n {be,fe,qa}-review/proposal --home loopspec` 并 `wait`。
  - 预期：三条命令都返回各自节点的 instruction（status ready）。
  - 实际：只有 `qa-review/proposal` 成功，另外两条返回 `{"error": "concurrent_write"}`。并行执行时，每个 sub agent 的第一条命令就会大概率失败。

## 初步分析

- `workflow_cli.node_instructions` 无条件在 Change 写锁（`LOCK_NB`）内执行：先 `settled()` 补完待归档的返工记录，再计算 status 与 instruction（含 Git Diff），持锁时间较长。
- 对只读调用来说这把锁大多数时候并不需要：只有存在待补完的返工归档时才需要写入。

## 执行的测试

通过真实 CLI（`.venv/bin/loopspec`）在 scratchpad 临时 Git 仓库中运行两个脚本：

- 串行场景 `qa_fanout.sh`（全部符合预期）：
  - 起始只有 prd 时 `parallel=False`，nextSteps 为 `[prd/proposal]`。
  - prd 完成后，文本报告 NODES 显示三个评审为 ready、review-gate blocked，NEXT STEPS 给出并行提示与三条命令；JSON `parallel=True`；`change next` 的 `nodes` 含三项、`node` 为 be-review。
  - review-gate 在三份评审完成前 `node instructions` 返回 `node_not_ready`。
  - 完成两份评审后只剩一条、`parallel=False`；三份都完成后只剩 review-gate。
  - review-gate FAIL 后 nextSteps 只有 rollback，`parallel=False`；rollback 重置 prd、三份评审与 gate；prd 重做后三份评审再次以 `parallel=True` 列出。
  - review-gate PASS 后 status `complete`，`parallel=False`，nextSteps 为 `change archive`。
  - `loopspec init --tools claude` 生成的 continue skill 含 `parallel: true` 说明。
- 并发场景 `qa_concurrent.sh`：三条 `node instructions` 后台并发执行，2/3 返回 `concurrent_write`（见上）；三个产物并发写入后 status 正确为全部 done、review-gate ready。
- 后端测试 Gate 已记录 `make test` 1079 passed，`make lint` 通过。
