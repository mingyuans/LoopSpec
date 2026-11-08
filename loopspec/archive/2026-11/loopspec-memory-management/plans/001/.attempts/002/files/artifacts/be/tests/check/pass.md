---
verdict: PASS
summary: "返工后在固定输入上重跑全量 pytest：1235 passed、1 skipped（既有 skip），make lint 与 mypy 通过，本轮没有失败用例。"
---

# 后端测试：通过

## 审查输入
- gate begin 轮次：`001.1:be/tests/check:4`，基线 `70a2d0b9b8d1a5e3c8e56ed3d6c39253683622cc`，固定范围摘要 `47d4285b784296e9f4251c985e428781cfe0609988e9a8ec9ba96b071850bc94`。
- 这是安全审查 FAIL 回退后的返工轮（rollback attempt 1）：与回退前相比，固定输入多了安全修复（`workflow_diff.py`、`workflow_memory.py`、`cli.py`）及其测试；begin 之后没有再改代码。
- `builtin/skills/*.md` 与 `docs/**` 按 `config.yaml` 的 `excluded_paths` 不在 Diff 内，但对应测试（`test_skill_templates.py`、`test_docs_consistency.py`）都在下面的运行中。

## 执行的测试
因单次命令时限，按文件分三批运行 `uv run pytest <文件列表> -q`，三批合起来覆盖 `tests/test_*.py` 全部 46 个文件，均在 begin 之后运行：

1. 第一批（前 16 个文件，含 `test_cli.py`、`test_docs_consistency.py`、`test_plan_guard.py`、`test_workflow_diff.py` 等）：`512 passed, 1 skipped in 142.20s`。
2. 第二批（第 17–32 个文件，含 `test_skill_templates.py`、`test_status_report.py` 等）：`483 passed in 317.85s`。
3. 第三批（第 33 个文件起，含 `test_workflow_memory.py`、`test_workflow_lifecycle.py`、`test_workflow_runtime.py` 等）：`240 passed in 169.06s`。
4. 合计 1235 passed、1 skipped（既有 skip），无失败；回退前的首轮是 1230 passed，增加的 5 项是返工新增的测试（Diff 只排除合法 topic 文件、条目总数上限、扫描竞态、`init` 的两项符号链接用例）。
5. `make lint`：`ruff check src tests hatch_version.py` 通过；`mypy src hatch_version.py`：`Success: no issues found in 36 source files`。
6. 本轮覆盖安全返工的直接证据：`tests/test_workflow_diff.py::test_only_valid_topic_files_in_memory_are_excluded_from_the_diff`（`memory/` 下的脚本、子目录、非法名文件仍进入 Diff）、`tests/test_workflow_memory.py` 的条目上限与竞态用例、`tests/test_cli.py` 的悬空符号链接与目录符号链接用例。

## 剩余风险
- 首轮全量运行中，对机器负载敏感的 `tests/test_plan_guard.py::test_long_command_is_decided_quickly`（2 秒墙钟断言）曾失败过一次，单独重跑和整批重跑均通过；本轮没有再出现，仍可能在高负载下偶发。
- 模型行为（是否漏读 topic、是否重复写入、`core` 被截断时是否补读）没有自动化测试，也没有人工执行验证；skill 提示词只做固定文本标记检查，不证明 LLM 的语义表现。
- 引擎没有写入口，因此没有针对 memory 写入冲突或敏感内容的引擎层测试；这是设计上有意接受的边界。
