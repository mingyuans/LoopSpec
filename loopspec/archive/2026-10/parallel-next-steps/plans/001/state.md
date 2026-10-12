# Plan 001

本计划执行中的决策与备注。人与 LLM 可直接编辑；`loopspec change status` 原样输出全文，引擎不解析。

## 人工决策

<!-- 节点要求询问人时：- YYYY-MM-DD [节点 id] 问：…；答：… -->

- 2026-10-11 [design/tasks] 问：是否确认测试计划（runtime 扇出/线性/rollback/exhausted、change next nodes、文本报告并行提示、skill 文案、全量 make test）？；答：approve

## 假设与偏离

<!-- 执行中的假设、与设计的偏差及原因：- YYYY-MM-DD [节点 id] … -->

- 2026-10-11 [be/code/implement] change next / status --json 用例放在 tests/test_workflow_runtime.py 而非 test_workflow_cli.py，复用扇出夹具。
- 2026-10-11 [be/code/implement] 额外同步 .claude/commands/lpsx/continue.md；docs 扇出示例使用占位 Fragment 名，不加 loopspec:example 标记。
- 2026-10-11 [be/code/implement] 全局指令要求的 jimmy-be-guideline skill 在本会话不可用，按仓库现有风格实现。
- 2026-10-12 [be/code/implement] 设计未涉及 node instructions 的加锁；QA 发现其阻碍并行后改为按需持锁（src/loopspec/workflow_cli.py），并新增 tests/test_workflow_recovery.py 两个用例。

## 返工记录

<!-- Gate FAIL 并 rollback 后：- YYYY-MM-DD [Gate id] attempt N：失败原因摘要；修复方向 -->

- 2026-10-12 [qa/test] attempt 1：三个 sub agent 并发执行 node instructions 时 2/3 返回 concurrent_write，因为该命令无条件持写锁；修复为仅在存在未完成返工归档时持锁，平时只读，写锁语义不变。

## 事件

<!-- 引擎在此之后追加生命周期事件，勿在此段之后新增段落。 -->
- 2026-10-11T11:07:06+00:00 · create · digest 321f50cd · note: List every ready leaf in nextSteps with a parallel marker and teach the continue skill to fan out sub agents
- 2026-10-11T11:07:47+00:00 · approve · revision 1 · digest 321f50cd
- 2026-10-12T02:41:53+00:00 · rollback · gate qa/test · attempt 1 · reset: assurance/check, be/code/implement, be/review/check, be/security/check, be/tests/check, qa/test
