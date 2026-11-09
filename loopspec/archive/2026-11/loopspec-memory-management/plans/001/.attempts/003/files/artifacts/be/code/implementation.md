## 完成的任务

tasks.md 的全部 17 项均已完成并保持勾选。本轮是第 2 次返工（审查门禁 FAIL），在前两轮（首轮实现、安全返工）之上处理独立代码审查提出的问题，全部先写失败测试再修复：

- 测试质量：`limit` 夹紧测试改为真的验证夹紧（把 `LIST_MAX_LIMIT` 调小）并补 `offset` 等于/超过总数的用例；“每个节点同摘要”测试改为对两个不同 Fragment 的节点比较；测试源码中 5 处字面量 U+2028 改成转义，并加了防回归检查；`summary()` 错误分支（`memory/` 是符号链接时 `change status` 仍可输出，文本与 JSON）、topic 上限的“恰好等于通过、多一个失败”边界、`ENTRY_SCAN_MAX` 提前终止补了测试；新增的几个测试一度“空转通过”，已加断言要求确实用到 `scandir`。
- `memory list --all`：`ignored` 只给按名称排序的前 `limit` 项并附 `ignoredTotal`，输出有界。
- `title` 与 `hint` 一样截断到 120 字符；topic 按 topic 名排序（`a` 在 `a-b` 之前）。
- 扫描改用 `os.scandir` 迭代并在超过 `ENTRY_SCAN_MAX` 时立即终止；非 UTF-8 文件名输出前转义（`printable_name`）。
- memory 路径错误给出贴切的 `fix`（符号链接 / 硬链接），不再是“检查配置并重新校验计划”。
- 保障 Diff 的 memory 排除只认工作区里的普通 topic 文件：名字像 topic 的符号链接照常计入 Diff（已删除的 topic 文件仍视为排除）。
- `continue.md` 与 `archive.md` 的 maintenance procedure 逐字一致，加测试防漂移。
- design.md、proposal.md、tasks.md 与中英文 docs 同步到上述行为。

此前轮次的内容保持不变：`workflow_memory.py`（topic 校验、分页索引、`read_topic`、`core_view` 条目边界内联、`summary`/`pointer`）、`memory list|show`、`change status` 的 `=== MEMORY ===` 段、`node instructions` 的 `memory` 字段、`init` 建目录（`lexists`）、条目总数上限、三份 skill 提示词与已安装副本、中英文 docs。

## 改动文件

- 引擎：`src/loopspec/workflow_memory.py`（新）、`workflow_cli.py`、`workflow_changes.py`、`workflow_runtime.py`、`status_report.py`、`workflow_diff.py`、`cli.py`。
- Skill：`builtin/skills/{new,continue,archive}.md` 与重新生成的 `.claude`、`.codex` 下对应副本（本轮未再改动）。
- 文档：`docs/{en,zh}/cli-reference.md`、`overview.md`、`agent-protocol.md`、`configuration.md`。
- 测试：`tests/test_workflow_memory.py`（新）、`test_workflow_cli.py`、`test_status_report.py`、`test_cli.py`、`test_workflow_diff.py`、`test_skill_templates.py`。
- 变更记录：`loopspec/changes/loopspec-memory-management/`（proposal、design、tasks、state.md）。

## 执行的检查

- 红：本轮新增或改写的测试中，排序、`ignored` 有界、title 上限、非 UTF-8 名字转义、memory 错误 `fix`、Diff 排除符号链接 6 项在实现前失败；`scandir` 提前终止与“条目消失”两项最初因实现仍用 `listdir` 而空转通过，补上“确实遍历了 phantom 条目 / 确实用到 scandir”的断言后转红。
- 绿：`uv run pytest tests/test_workflow_memory.py tests/test_workflow_diff.py tests/test_skill_templates.py -q`：`158 passed`；改成按异常来源判断 `fix` 之后又跑 `tests/test_docs_consistency.py tests/test_skill_templates.py`（全部通过）和 `tests/test_workflow_memory.py -k "path_errors or symlinked or hard or unsafe"`（`4 passed`）。
- `make lint`：`ruff check` 通过，`mypy src hatch_version.py` 通过（36 个源文件）。
- 过程中的一个失误：一次脚本替换位置错误，把 `tests/test_workflow_memory.py` 的中段复制了一份（文件膨胀到 1203 行，存在重复定义）；已按函数名去重并保留新版本（现 792 行，77 项被收集），随后 lint 与测试重新通过。
- 全量 `uv run pytest`（分批）尚未在本轮代码上运行，将由随后的 `be/tests/check` 门禁在固定输入后执行并记录，这里不引用其结果。
- 未运行：模型行为场景没有自动化，也没有人工执行，不宣称已验证。

## 与设计的偏差

1. `memory list` / `memory show` 默认输出 JSON，没有 `--json` 选项（与其他工作流命令一致）；设计原文写的是“均支持 `--json`”。
2. `=== MEMORY ===` 段与 skill 正文是英文（报告其他各段、`builtin/skills` 都是英文，且有测试要求 skill 正文为 ASCII）；设计里的中文提示对应为 `NOT fully read ... you must read the rest with loopspec memory show core`。
3. `summary()` 在 `memory/` 异常时不抛错，而是在 payload 的 `error` 中给出错误码，status 段显示 `unavailable`，避免坏掉的 memory 目录让 `change status` 整体失败。
4. 保障 Diff 的排除范围比设计初稿更窄：只排除工作区里的普通 topic 文件（安全审查与代码审查先后要求），设计与 docs 已同步。
5. `ignored` 只给前 `limit` 项并附 `ignoredTotal`，而不是随 `offset` 翻页；这是为了让输出有界的最小做法。
6. 既有测试 `test_status_report.py` 中固定的段落列表加入了 `MEMORY`（该段始终存在），`TOP_KEYS` 新增 `memory`。
7. 提示词以中文原文为语义基准，落地为对应的英文版并共用结构化标记。

## 后续事项

- 审查指出但有意不处理的三点：core 在报告里既内联又出现在索引中（设计与测试有意如此）；`core` 含非法 UTF-8 时 `bytes`（原始字节）与 `shown`（解码重编码后的长度）单位不完全一致（极少见，只影响提示文字）；`pointer()` 为了 `bytes` 字段会读一遍 core（最大 2 MiB，开销可忽略）。
- 首轮全量测试中 `tests/test_plan_guard.py::test_long_command_is_decided_quickly`（2 秒墙钟断言）曾在高负载下失败过一次，单独重跑通过，与本次改动无关。
- 模型行为的真实效果（是否漏读、是否重复写入）需要在实际使用中观察；是否需要 fragments 映射取决于是否反复漏读。
