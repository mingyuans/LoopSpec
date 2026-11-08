---
verdict: PASS
summary: "全量 pytest 1230 passed、1 skipped（既有 skip），make lint 与 mypy 通过；其间一个与本次改动无关的计时用例在高负载下失败过一次，单独重跑 3 次及整批重跑均通过。"
---

# 后端测试：通过

## 审查输入
- gate begin 轮次：`001.1:be/tests/check:3`（测试在第 1 轮输入上运行；之后只修改了本报告的表述，因此重新 begin 了第 2、3 轮；三轮的固定范围摘要相同，均为 `cdc986f44f5ae7dfb0291f44a21ff0c3a6c52e90b814bf3a8f6288191e635c14`，被测代码未变，下面的测试运行结果适用于本轮输入），基线 `70a2d0b9b8d1a5e3c8e56ed3d6c39253683622cc`，固定范围共 13 个路径（`src/loopspec/` 下 7 个，`tests/` 下 6 个，其中 `workflow_memory.py` 与 `test_workflow_memory.py` 为新增）。
- 固定输入之后没有再改代码；`builtin/skills/*.md` 与 `docs/**` 被 `config.yaml` 的 `excluded_paths`（`*.md`、`docs/**`）排除在 Diff 之外，但它们对应的测试（`test_skill_templates.py`、`test_docs_consistency.py`）已包含在下面的运行里。

## 执行的测试
命令与输出摘要（因单次命令时限，按文件分三批运行 `uv run pytest <文件列表> -q`，三批合起来覆盖 `tests/test_*.py` 全部 46 个文件）：

1. 第一批（`tests/test_*.py` 前 16 个文件）：首次运行 `1 failed, 509 passed, 1 skipped`，失败的是 `tests/test_plan_guard.py::test_long_command_is_decided_quickly`。该用例断言一条超长命令在 2 秒内被判定，是对机器负载敏感的墙钟断言，与本次改动无关（`plan_guard.py` 未改动）。随后单独运行该用例 3 次，均为 `1 passed`；整批重跑结果 `510 passed, 1 skipped in 155.68s`。
2. 第二批（第 17–32 个文件，含 `test_skill_templates.py`、`test_status_report.py`）：`482 passed in 447.61s`。`test_docs_consistency.py` 在第一批内。
3. 第三批（第 33 个文件起，含 `test_workflow_memory.py`、`test_workflow_lifecycle.py`、`test_workflow_runtime.py` 等）：`238 passed in 211.74s`。
4. 合计 1230 passed、1 skipped（既有 skip）。本次新增与改动的用例包括：`tests/test_workflow_memory.py` 62 项（topic 名、索引与分页、符号链接/硬链接/超限、`core_view` 的条目边界与多字节、status/instructions 注入、CLI、端到端）、`tests/test_skill_templates.py` 新增 11 项、`tests/test_cli.py` 的 init 两项、`tests/test_workflow_diff.py` 的 memory 排除两项，以及既有 `test_status_report.py` 中因新增 `MEMORY` 段而更新的段落顺序断言。
5. `make lint`：`ruff check src tests hatch_version.py` 通过；`mypy src hatch_version.py`：`Success: no issues found in 36 source files`。

## 剩余风险
- `test_long_command_is_decided_quickly` 在本机高负载时可能偶发失败（本轮出现 1 次，重跑通过），属既有的时间敏感用例，不阻塞本次交付。
- 模型行为（是否漏读 topic、是否重复写入、`core` 被截断时是否补读）没有自动化测试，也没有人工执行验证；提示词只做了固定文本标记检查，不证明 LLM 的语义表现。
- 引擎没有写入口，因此没有针对 memory 写入冲突或敏感内容的引擎层测试；这是设计上有意接受的边界。
