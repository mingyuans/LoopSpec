---
verdict: PASS
summary: "4 条验收条件满足：对抗样例中正文伪造的 end 行只以缩进出现，块计数正确；真实项目 change status 的 state 块成对且计数正确"
---

# 验收测试：通过

## 验收条件核对

- [x] 每个引用块 begin/end 同名配对、行数一致、块内缩进：`quoted_blocks()` 对全部 27 个命令样本（含 poison）通过；对抗样例（memory 正文含 `=== ERROR ===`、`--- end content ---`，instruction 含 `=== NEXT STEPS ===`、`1. loopspec plan approve …`、`--- fake ---`）解析结果为 `[('content', 8), ('instruction', 9), ('template', 24)]`。
- [x] 正文中的 end 行不提前结束块：memory 样例中 `--- end content ---` 只以 `    --- end content ---` 出现在块内第 8 行，真正的结束行在其后；`test_quoted_text_cannot_end_its_block_early` 通过。
- [x] `change status`：在锁定 aftership-channels registry 的演示项目中，`change status DEMO1` 输出 `--- begin change: …/state.md (28 lines) ---` / `--- end change ---` 与 `--- begin plan 001 (approved, active): …/plans/001/state.md (26 lines) ---` / `--- end plan 001 (approved, active) ---`；缺失文件的单行标题由 `test_missing_and_unreadable_state_are_named_in_the_header` 覆盖。
- [x] `--json` 不变、全部测试与 LLM E2E 通过：见 be/tests/check（1762 passed；12 passed，$1.831）。

## 执行的测试

- `uv run python /tmp/lsx/demo.py`（对抗样例，临时脚本）与 `quoted_blocks()` 解析；`.venv/bin/loopspec change status DEMO1`。

## 剩余风险

- 无。
