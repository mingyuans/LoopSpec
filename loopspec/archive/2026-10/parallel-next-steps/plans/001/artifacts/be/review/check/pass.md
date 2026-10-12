---
verdict: PASS
summary: "并行 nextSteps 与 node instructions 按需加锁的实现正确、改动最小，回退与耗尽优先级不变，测试覆盖新路径与原有恢复路径；审查中发现的 cli-reference 过时描述已同步修正"
---

# 后端代码审查：通过

## 审查输入

- 轮次：`001.1:be/review/check:2`，基线 `1c5ce6ad00450d3639c64501523fd377492fbfc9`，scopeDigest `dcd579f0…`，warnings 为空。
- 路径：`src/loopspec/{status_report,workflow_changes,workflow_cli,workflow_runtime}.py`、`tests/{test_skill_templates,test_status_report,test_workflow_recovery,test_workflow_runtime}.py`。

## 审查要点

- **正确性（上一轮已审部分）**：`nextSteps` 列出全部 ready 叶子且按依赖顺序；`parallel = rollback is None and len(next_steps) > 1`；`change status` 各分支与 `change next` 的 `nodes` 均与 `nextSteps` 对应；文本报告的并行提示与 NODES 文案符合设计。
- **正确性（返工，`workflow_cli.node_instructions`）**：先 `active_plan(ctx)` 再判断 `pending_sources`，与旧实现中 `settled()` 内部调用顺序一致；无 active Plan 时仍抛相同错误。待归档时的分支保持原代码（重新 `open_change` + `settled`），行为与原来逐字一致。
- **边界**：存在被篡改或越界的归档 record 时，`pending_sources` 非空，进入加锁 + settle 路径并报 `history_integrity`（已有用例通过）。
- **错误处理**：无吞异常；`concurrent_write` 只会在确实需要写入时出现。
- **测试覆盖**：新增两个用例分别覆盖“持锁时只读仍可用”和“待归档时仍需锁并完成归档”，前者在修复前失败；全量 1081 passed，lint / mypy 通过。
- **文档一致性**：`docs/{en,zh}/cli-reference.md` 中 `node instructions` 原写“总是持写锁”，审查中已改为“仅在有待归档文件时持锁，否则只读”；`plan-reference.md` 中“先在写锁内补完这些搬运”的表述仍然准确；docs 一致性测试 43 passed。

## 剩余风险

- `change next` 在 exhausted Gate 前仍有 ready 叶子时，`node` 与 `nodes[0]` 可能不同（为保持 `node` 旧语义的取舍，不阻塞）。
