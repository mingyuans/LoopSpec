---
verdict: PASS
summary: "返工后用真实 CLI 复验全部验收条件：扇出并行、递减、汇总 Gate 阻塞、FAIL 回退后再次并行、完成状态均符合预期，三个 node instructions 并发执行连续 3 次全部成功"
---

# 验收测试：通过

## 验收条件核对

- [x] 扇出 Plan 在 A 完成后 `nextSteps` 恰为 B、C、D 三条命令（依赖顺序）且 `parallel` true：prd 完成后 JSON 为 `parallel=True`，nextSteps 为 be/fe/qa-review 三条。
- [x] 线性 / 单个 ready 时只有一条命令、`parallel` false：起始只有 prd 时 `parallel=False`、单条命令；单测 `test_linear_plan_keeps_a_single_step` 通过。
- [x] 并行分支部分完成后递减：完成两份评审后只剩 qa-review、`parallel=False`；单测覆盖剩两条时为 true。
- [x] 存在 `pendingRollback` 时只有 rollback 命令、`parallel` false：review-gate FAIL 后 nextSteps 仅 `loopspec plan rollback ...`。
- [x] exhausted 时 nextSteps 为空、`parallel` false：单测 `test_rollback_and_exhaustion_override_parallel_steps` 通过。
- [x] 文本报告：并行时 NEXT STEPS 出现“independent … run them in parallel, for example one sub agent per step … concurrent_write …”并列出三条命令；单步时提示语不变；NODES 提示改为 “act only on the nodes named in NEXT STEPS”。
- [x] `change next` 含 `nodes`：并行时 `nodes` 为三项、`node` 为 be-review、`parallel` true；rollback 时为该 Gate。
- [x] 并行 sub agent 分别执行 `node instructions` 与写产物互不影响：三条 `node instructions` 后台并发执行连续 3 次全部返回 ready（上一轮 2/3 返回 `concurrent_write`）；三份产物并发写入后 status 正确为全部 done、review-gate ready；三份评审完成前 review-gate 的 `node instructions` 返回 `node_not_ready`。
- [x] continue skill 源文件与生成副本含并行派发与 `concurrent_write` 重试说明：`loopspec init --tools claude` 生成的 SKILL.md 含 `parallel: true` 段落；skill 模板测试通过。
- [x] 全量测试通过：后端测试 Gate 第 2 轮 1081 passed，lint / mypy 通过。

另外：review-gate FAIL 后 rollback 重置 prd、三份评审与 gate；prd 重做后三份评审再次以 `parallel=True` 列出；review-gate PASS 后 status 为 `complete`，`parallel=False`，nextSteps 为 `change archive`。

## 执行的测试

- scratchpad 临时 Git 仓库，使用 `/Users/xq.yan/pythonprojects/LoopSpec/.venv/bin/loopspec`：
  - `qa_fanout.sh`：init → 扇出请求 create / approve → 逐步写产物 → FAIL → rollback → 重做 → PASS，检查每一步的 JSON、文本报告与 `change next`。
  - `qa_concurrent.sh`（连续 3 次）：新 Change 中 prd 完成后，后台并发执行三条 `node instructions` 并 `wait`，再并发写三份产物后读 status。
- 引用后端测试 Gate 第 2 轮结果：`make lint` 通过；全量 pytest 733 + 348 = 1081 passed。

## 剩余风险

- 并发的写命令（如多个代码 Gate 同时 `gate begin/record`）仍可能返回 `concurrent_write`，按设计由 skill 指引原样重试；本轮未做真实多 Agent 端到端演练。
