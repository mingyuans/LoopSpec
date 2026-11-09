## 完成的任务

tasks.md 的全部 17 项均已完成并保持勾选；本轮（返工第 1 次）在此基础上修复了安全审查提出的 4 个问题，并同步设计与文档：

- 保障 Diff 的 memory 排除从“整个 `<home>/memory/` 目录”收紧为“合法 topic 文件 `<home>/memory/<topic>.md`”（任务 4.2）；`memory/` 下的脚本、子目录、非法名文件现在照常计入 Diff。
- `memory/` 下条目总数（含非 topic）设上限 `ENTRY_SCAN_MAX = 20000`，超过返回 `memory_too_many`（任务 1.2）。
- 扫描时条目在 `listdir` 与 `stat` 之间消失则跳过，不再把索引误判为空（任务 1.2）。
- `init` 创建 `memory/` 改用 `lexists` 判断，遇到同名符号链接（含悬空）不崩溃、不覆盖（任务 4.1）。
- design.md、proposal.md、tasks.md 与中英文 docs（overview、configuration、cli-reference）中“排除整个 memory/”的表述同步改为“只排除合法 topic 文件”，并写入新的条目上限与竞态处理。

首轮完成的内容（保持不变）：`src/loopspec/workflow_memory.py`（topic 校验、分页索引、`read_topic`、`core_view` 条目边界内联、`summary`/`pointer`）、`memory list|show` 子命令、`change status` 的 `=== MEMORY ===` 段与 payload、`node instructions` 的 `memory` 字段、`init` 建目录、`builtin/skills/{new,continue,archive}.md` 的提示词及本仓库 `.claude`/`.codex` 的已安装副本、中英文 docs。

## 改动文件

- 引擎：`src/loopspec/workflow_memory.py`（新）、`workflow_cli.py`、`workflow_changes.py`、`workflow_runtime.py`、`status_report.py`、`workflow_diff.py`、`cli.py`。
- Skill：`builtin/skills/{new,continue,archive}.md`，以及重新生成的 `.claude/skills`、`.claude/commands/lpsx`、`.codex/skills` 中对应文件。
- 文档：`docs/{en,zh}/cli-reference.md`、`overview.md`、`agent-protocol.md`、`configuration.md`。
- 测试：`tests/test_workflow_memory.py`（新）、`test_workflow_cli.py`、`test_status_report.py`、`test_cli.py`、`test_workflow_diff.py`、`test_skill_templates.py`。
- 变更记录：`loopspec/changes/loopspec-memory-management/`（proposal、design、tasks、state.md）。

## 执行的检查

本轮返工按 TDD 进行：先加 4 个失败测试并确认为红，再实现，再转绿。

- 红：`test_workflow_diff.py::test_only_valid_topic_files_in_memory_are_excluded_from_the_diff`、`test_workflow_memory.py` 的条目上限与竞态两项、`test_cli.py::test_init_does_not_crash_on_a_dangling_memory_symlink`（`FileExistsError`）均失败。
- 绿：`uv run pytest tests/test_workflow_memory.py tests/test_workflow_diff.py -q`：`93 passed`；`uv run pytest tests/test_cli.py -k init -q`：`24 passed`；`uv run pytest tests/test_docs_consistency.py -q`：`43 passed`。
- `make lint`：`ruff check` 通过，`mypy src hatch_version.py` 通过（36 个源文件）。
- 首轮（回退前）的全量运行为 1230 passed、1 skipped，那是在这次修复之前的代码上；回退后尚未重跑全量，全量 `uv run pytest`（分批）将由随后的 `be/tests/check` 门禁在固定输入后执行并记录，这里不引用它的结果。
- 未运行：模型行为场景没有自动化，也没有人工执行，不宣称已验证。

## 与设计的偏差

1. `memory list` / `memory show` 默认输出 JSON，没有 `--json` 选项（与其他工作流命令一致）；设计原文写的是“均支持 `--json`”。
2. `=== MEMORY ===` 段与 skill 正文是英文（报告其他各段、`builtin/skills` 都是英文，且有测试要求 skill 正文为 ASCII）；设计里的中文提示对应为 `NOT fully read ... you must read the rest with loopspec memory show core`。
3. `summary()` 在 `memory/` 异常（符号链接、条目过多）时不抛错，而是在 payload 的 `error` 中给出错误码，status 段显示 `unavailable`，避免坏掉的 memory 目录让 `change status` 整体失败。
4. 保障 Diff 的排除范围比设计初稿更窄（见上，由安全审查要求），设计与 docs 已同步。
5. 既有测试 `test_status_report.py` 中固定的段落列表加入了 `MEMORY`（该段始终存在），`TOP_KEYS` 新增 `memory`。
6. 提示词以中文原文为语义基准，落地为对应的英文版并共用结构化标记。

## 后续事项

- 首轮全量测试中 `tests/test_plan_guard.py::test_long_command_is_decided_quickly`（2 秒墙钟断言）曾在高负载下失败过一次，单独重跑通过，与本次改动无关；若再出现，可考虑放宽该用例的时间阈值（不在本次范围）。
- 是否需要按相关性自动选择 topic（fragments 映射）取决于实际使用中是否反复漏读。
