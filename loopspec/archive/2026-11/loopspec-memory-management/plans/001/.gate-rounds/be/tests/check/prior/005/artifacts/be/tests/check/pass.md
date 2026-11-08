---
verdict: PASS
summary: "第 2 次返工后在固定输入上重跑全量 pytest：1250 passed、1 skipped（既有 skip），make lint 与 mypy 通过，无失败用例。"
---

# 后端测试：通过

## 审查输入
- gate begin 轮次：`001.1:be/tests/check:5`，基线 `70a2d0b9b8d1a5e3c8e56ed3d6c39253683622cc`，固定范围摘要 `94aa3a0d2bd58c0a07fbb309e1f847b70314895644ac6b9bae73178ec646fa9d`。
- 这是代码审查 FAIL 回退后的返工轮（rollback attempt 2）：固定输入包含 `workflow_memory.py`（`scandir` 提前终止、按 topic 名排序、`title` 上限、`ignored` 有界、名字转义、`fix` 文案）、`workflow_diff.py`（排除只认普通 topic 文件）及相应测试。begin 之后没有再改代码。
- `builtin/skills/*.md` 与 `docs/**` 按 `config.yaml` 的 `excluded_paths` 不在 Diff 内，但对应测试（`test_skill_templates.py`、`test_docs_consistency.py`）都在下面的运行中。

## 执行的测试
因单次命令时限（其中一批在本机负载下曾超过 10 分钟），按文件分批运行 `uv run pytest <文件列表> -q`，合起来覆盖 `tests/test_*.py` 全部 46 个文件，均在 begin 之后运行：

1. 第一批（前 16 个文件，含 `test_cli.py`、`test_docs_consistency.py`、`test_plan_guard.py`）：`512 passed, 1 skipped in 285.93s`。
2. 第二批前半（`test_skill_templates.py`、`test_status_report.py`、`test_tool_picker.py`、`test_tool_registry.py`、`test_tools_arg.py`、`test_workflow_assurance.py`、`test_workflow_builtin.py`、`test_workflow_catalog.py`）：`353 passed in 287.92s`。第二批最初作为一整批运行时被 10 分钟时限中止（`Exit code 143`，没有得到测试结果），随后拆成前后两半重新运行。
3. 第二批后半（`test_workflow_cli.py`、`test_workflow_compiler.py`、`test_workflow_diff.py`、`test_workflow_e2e.py`、`test_workflow_errors.py`、`test_workflow_evidence.py`、`test_workflow_git.py`、`test_workflow_io.py`）：`132 passed in 435.83s`。
4. 第三批（第 33 个文件起，含 `test_workflow_memory.py`、`test_workflow_lifecycle.py`、`test_workflow_runtime.py` 等）：`253 passed in 297.83s`。
5. 合计 1250 passed、1 skipped（既有 skip），无失败。与回退前相比多出的用例是两轮返工新增的：条目上限、竞态、`init` 符号链接、Diff 排除符号链接与合法 topic 文件、`limit` 夹紧、`offset` 越界、同摘要、`ignored` 有界、title 上限、排序、名字转义、`fix` 文案、`memory/` 为符号链接时 `change status`、topic 上限边界、skill 维护提示词一致性、测试源码无不可见分隔符等。
6. `make lint`：`ruff check src tests hatch_version.py` 通过；`mypy src hatch_version.py`：`Success: no issues found in 36 source files`。
7. 针对两轮返工的直接证据：`tests/test_workflow_diff.py` 中 memory 相关三项（只排除合法 topic 文件、符号链接不被排除、其他目录的 `memory/` 是普通代码）；`tests/test_workflow_memory.py` 中扫描上限与提前终止（要求确实用到 `scandir`）、条目消失被跳过、上限边界、`ignored` 有界、title 上限、排序、名字转义、错误 `fix`；`tests/test_cli.py` 的 `init` 符号链接用例。

## 剩余风险
- 首轮全量运行中，对机器负载敏感的 `tests/test_plan_guard.py::test_long_command_is_decided_quickly`（2 秒墙钟断言）曾失败过一次，单独重跑和整批重跑均通过；本轮没有再出现，仍可能在高负载下偶发。
- 模型行为（是否漏读 topic、是否重复写入、`core` 被截断时是否补读）没有自动化测试，也没有人工执行验证；skill 提示词只做固定文本标记检查，不证明 LLM 的语义表现。
- 引擎没有写入口，因此没有针对 memory 写入冲突或敏感内容的引擎层测试；这是设计上有意接受的边界。
