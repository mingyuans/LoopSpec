---
verdict: PASS
summary: "第 3 次返工后在固定输入上重跑全量 pytest：1253 passed、1 skipped（既有 skip），make lint 与 mypy 通过，无失败用例。"
---

# 后端测试：通过

## 审查输入
- gate begin 轮次：`001.1:be/tests/check:6`，基线 `70a2d0b9b8d1a5e3c8e56ed3d6c39253683622cc`，固定范围摘要 `40cbcf352a454939ed1558d2467b3b793ecfc1dff1008919a96d166b80d7f524`。
- 这是代码审查第二次 FAIL 回退后的返工轮（rollback attempt 3）：固定输入相对上一轮的变化是 `workflow_diff.py`（排除判断捕获 `OSError`）、`workflow_memory.py`（`_reraise`、`_refix` 只处理 `ELOOP`/`ENOTDIR`）及测试（删除两个旧测试、新增缺口测试）。begin 之后没有再改代码。
- `builtin/skills/*.md` 与 `docs/**` 按 `config.yaml` 的 `excluded_paths` 不在 Diff 内，但对应测试（`test_skill_templates.py`、`test_docs_consistency.py`）都在下面的运行中。

## 执行的测试
因单次命令时限，按文件分批运行 `uv run pytest <文件列表> -q`，合起来覆盖 `tests/test_*.py` 全部 46 个文件，均在 begin 之后运行：

1. 第一批（前 16 个文件，含 `test_cli.py`、`test_docs_consistency.py`、`test_plan_guard.py`）：`512 passed, 1 skipped in 282.73s`。
2. 第二批前半（`test_skill_templates.py`、`test_status_report.py`、`test_tool_picker.py`、`test_tool_registry.py`、`test_tools_arg.py`、`test_workflow_assurance.py`、`test_workflow_builtin.py`、`test_workflow_catalog.py`）：`353 passed in 191.98s`。
3. 第二批后半（`test_workflow_cli.py`、`test_workflow_compiler.py`、`test_workflow_diff.py`、`test_workflow_e2e.py`、`test_workflow_errors.py`、`test_workflow_evidence.py`、`test_workflow_git.py`、`test_workflow_io.py`）：`133 passed in 352.32s`。
4. 第三批（第 33 个文件起，含 `test_workflow_memory.py`、`test_workflow_lifecycle.py`、`test_workflow_runtime.py` 等）：`255 passed in 355.83s`。
5. 合计 1253 passed、1 skipped（既有 skip），无失败。
6. `make lint`：`ruff check src tests hatch_version.py` 通过；`mypy src hatch_version.py`：`Success: no issues found in 36 source files`。
7. 针对本轮返工的直接证据：`tests/test_workflow_memory.py` 中“无自引用 cause”“权限问题不提示符号链接”（root 下会跳过，本机非 root 已执行）“`pointer` 报告损坏的 core”“topic 超限时 status 仍可输出”；`tests/test_workflow_diff.py` 中“`memory/` 被换成文件时是结构化错误而不是崩溃”；`tests/test_skill_templates.py` 中完整比较 maintenance procedure 的一致性测试。

## 剩余风险
- 首轮全量运行中，对机器负载敏感的 `tests/test_plan_guard.py::test_long_command_is_decided_quickly`（2 秒墙钟断言）曾失败过一次，单独重跑和整批重跑均通过；此后各轮没有再出现，仍可能在高负载下偶发。
- 模型行为（是否漏读 topic、是否重复写入、`core` 被截断时是否补读）没有自动化测试，也没有人工执行验证；skill 提示词只做固定文本标记检查，不证明 LLM 的语义表现。
- 引擎没有写入口，因此没有针对 memory 写入冲突或敏感内容的引擎层测试；这是设计上有意接受的边界。
