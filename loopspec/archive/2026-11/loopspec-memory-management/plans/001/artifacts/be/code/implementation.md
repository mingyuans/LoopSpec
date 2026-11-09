## 完成的任务

tasks.md 的全部 17 项均已完成并保持勾选。本轮是第 3 次返工（审查门禁第二次 FAIL），处理同一个独立审查者复审时指出、我核实属实的问题，全部先写失败测试再修复：

- 删除上一轮重构留下的两个旧测试（`test_every_node_gets_the_same_memory_summary` 对 `design/design` 在未就绪时直接 `continue`，最后是自己和自己比，属于空转测试；`test_the_memory_summary_does_not_depend_on_the_node_fragment` 与新测试重复），只保留对两个不同 Fragment 的节点比较摘要的那个。
- `workflow_diff` 的 topic 排除判断：`os.lstat` 除 `FileNotFoundError`（已删除，视为排除）之外也捕获 `OSError`（例如 `memory/` 被换成文件），此时不排除，交给 Diff 自身报告；排除判断不再抛裸 `NotADirectoryError`。
- 异常处理：新增 `_reraise`，不需要改写时原样 `raise`，只有替换 `fix` 时才 `raise new from exc`，不再出现 `raise exc from exc` 的自引用 cause。
- `_refix` 只对 `ELOOP`、`ENOTDIR`（符号链接、非目录）使用“不能是符号链接”的提示，权限错误（`EACCES`）保留通用提示。
- 补测试缺口：`pointer()` 在 core 出错时的 `error` 字段；topic 数超过上限时 `change status`（文本与 JSON）仍可输出并显示 `unavailable`；skill 维护提示词的一致性测试改为比较从 “Memory maintenance procedure.” 到固定结束句的完整文本（并要求长度合理）。

此前轮次的内容保持不变：`workflow_memory.py`（topic 校验、分页索引、`scandir` 提前终止、按 topic 名排序、title/hint 上限、`ignored` 有界并附 `ignoredTotal`、`read_topic`、`core_view` 条目边界内联、`summary`/`pointer`）、`memory list|show`、`change status` 的 `=== MEMORY ===` 段、`node instructions` 的 `memory` 字段、`init` 建目录（`lexists`）、保障 Diff 只排除工作区里的普通 topic 文件、三份 skill 提示词与已安装副本、中英文 docs。

## 改动文件

- 引擎：`src/loopspec/workflow_memory.py`（新）、`workflow_cli.py`、`workflow_changes.py`、`workflow_runtime.py`、`status_report.py`、`workflow_diff.py`、`cli.py`。
- Skill：`builtin/skills/{new,continue,archive}.md` 与已安装副本（本轮未再改动）。
- 文档：`docs/{en,zh}/cli-reference.md`、`overview.md`、`agent-protocol.md`、`configuration.md`（本轮未再改动）。
- 测试：`tests/test_workflow_memory.py`（新）、`test_workflow_cli.py`、`test_status_report.py`、`test_cli.py`、`test_workflow_diff.py`、`test_skill_templates.py`。
- 变更记录：`loopspec/changes/loopspec-memory-management/`（proposal、design、tasks、state.md）。

## 执行的检查

- 红：新增的“无自引用 cause”“权限问题不提示符号链接”“`memory/` 被换成文件时 Diff 不抛裸异常”3 项在修复前失败（其中后一项修复前抛的是裸 `NotADirectoryError`）；另外 `pointer` 出错、status 在 topic 超限时的行为、skill 一致性这 3 个补缺口的测试在修复前就已通过（它们验证的是既有行为，之前只是没有测试保护）。
- 绿：`uv run pytest tests/test_workflow_memory.py tests/test_workflow_diff.py tests/test_skill_templates.py -q` 修复后 `160 passed, 1 failed`，失败的是我对“目录被换成文件”的预期写错了——修复后它不再抛裸异常，而是走到 Diff 既有的结构化 `unsafe_path` 错误；把测试预期改为“结构化 `WorkflowError`（`unsafe_path`）而不是崩溃”后，`tests/test_workflow_diff.py`：`31 passed`。
- `make lint`：`ruff check` 通过，`mypy src hatch_version.py` 通过（36 个源文件）。
- 全量 `uv run pytest`（分批）尚未在本轮代码上运行，将由随后的 `be/tests/check` 门禁在固定输入后执行并记录，这里不引用其结果。
- 未运行：模型行为场景没有自动化，也没有人工执行，不宣称已验证。

## 与设计的偏差

1. `memory list` / `memory show` 默认输出 JSON，没有 `--json` 选项（与其他工作流命令一致）；设计原文写的是“均支持 `--json`”。
2. `=== MEMORY ===` 段与 skill 正文是英文（报告其他各段、`builtin/skills` 都是英文，且有测试要求 skill 正文为 ASCII）。
3. `summary()` 在 `memory/` 异常时不抛错，而是在 payload 的 `error` 中给出错误码，status 段显示 `unavailable`，避免坏掉的 memory 目录让 `change status` 整体失败。
4. 保障 Diff 的排除范围比设计初稿更窄：只排除工作区里的普通 topic 文件（安全审查与代码审查先后要求），设计与 docs 已同步。
5. `ignored` 只给前 `limit` 项并附 `ignoredTotal`，不随 `offset` 翻页；这是有意的“诊断用、有界输出”取舍，文档已写明。
6. 既有测试 `test_status_report.py` 中固定的段落列表加入了 `MEMORY`，`TOP_KEYS` 新增 `memory`。
7. 提示词以中文原文为语义基准，落地为对应的英文版并共用结构化标记。

## 后续事项

- 审查指出但有意不处理的点：core 在报告里既内联又出现在索引中（设计与测试有意如此）；`core` 含非法 UTF-8 时 `bytes` 与 `shown` 单位不完全一致（极少见）；`pointer()` 为了 `bytes` 字段读一遍 core（最大 2 MiB，开销可忽略）；`printable_name` 不转义字面反斜杠；`lstat` 会跟随中间路径的符号链接（符号链接本身会作为改动出现在 Diff 中）。
- 首轮全量测试中 `tests/test_plan_guard.py::test_long_command_is_decided_quickly`（2 秒墙钟断言）曾在高负载下失败过一次，单独重跑通过，与本次改动无关。
- 一个流程教训：整理测试文件时不要用“按函数名去重”的脚本，那会留下被改名的旧测试；本轮已直接删除。
