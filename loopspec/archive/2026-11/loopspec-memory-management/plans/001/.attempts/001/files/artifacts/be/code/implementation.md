## 完成的任务

tasks.md 中全部 17 项已完成并勾选：

- 1.1–1.4：新增 `src/loopspec/workflow_memory.py`，含 topic 名校验、`list_topics`（分页、`total/nextOffset`、5000 上限）、`read_topic`、`core_view`（按 `## ` 条目边界内联，上限 8 KiB）、`summary`/`pointer`。
- 2.1：`loopspec memory list [--offset] [--limit] [--all]` 与 `loopspec memory show <topic>`（只读）。
- 3.1–3.3：`change status` payload 与 `=== MEMORY ===` 段；`node instructions` 的 `memory` 字段（摘要与 core 入口，不含 core 全文）。
- 4.1–4.3：`init` 创建空 `memory/`；保障 Diff 永远排除 `<home>/memory/`；缺目录按空处理。
- 5.1–5.3：`builtin/skills/{new,continue,archive}.md` 的读侧与维护侧提示词；中英文 docs；本仓库 `.claude`、`.codex` 的已安装副本经 `scaffold_tools` 重新生成。
- 6.1–6.3：端到端用例、全量 `make test` 与 `make lint`、模型行为场景的预期写入 `docs/*/agent-protocol.md` 第 9 节并注明未自动化。

## 改动文件

- 引擎：`src/loopspec/workflow_memory.py`（新）、`workflow_cli.py`、`workflow_changes.py`、`workflow_runtime.py`、`status_report.py`、`workflow_diff.py`、`cli.py`。
- Skill：`builtin/skills/new.md`、`continue.md`、`archive.md`；重新生成 `.claude/skills/loopspec-{new,continue,archive}/SKILL.md`、`.claude/commands/lpsx/{new,continue,archive}.md`、`.codex/skills/loopspec-{new,continue,archive}/SKILL.md`。
- 文档：`docs/{en,zh}/cli-reference.md`、`overview.md`、`agent-protocol.md`、`configuration.md`。
- 测试：`tests/test_workflow_memory.py`（新，62 项）、`test_workflow_cli.py`、`test_status_report.py`、`test_cli.py`、`test_workflow_diff.py`、`test_skill_templates.py`。
- 变更记录：`loopspec/changes/loopspec-memory-management/`（proposal、design、tasks、state.md）。

## 执行的检查

先写失败的测试再实现，每一批都先看到红再转绿（引擎层：`ImportError`；CLI/status/init/diff：`JSONDecodeError`；skill：9 项失败；docs：6 项失败）。

- `uv run pytest`（因单次命令时限，按文件分三批运行）：第一批 `510 passed, 1 skipped`；第二批 `482 passed`；第三批 `238 passed`，合计 1230 passed、1 skipped（skip 为既有用例）。
- 之后又改了一处（core 被截断时追加“Consider tidying core.md”提示），重跑 `tests/test_workflow_memory.py` 与 `tests/test_status_report.py`：`77 passed`。该改动只影响这两个文件覆盖的输出。
- `make lint`：`ruff check` 通过，`mypy src hatch_version.py` 通过（36 个源文件）。
- `tests/test_docs_consistency.py`（含在上面的批次内，改文档后单独跑过）：`43 passed`。
- 未运行：模型行为场景（已有 topic 同义不重复、新主题创建、新证据修订/冲突不覆盖、core 被截断时补读）没有自动化，也没有人工执行，不宣称已验证。

## 与设计的偏差

1. `memory list` / `memory show` 默认输出 JSON，没有 `--json` 选项：与其他工作流命令一致（只有 `change status` 有 `--json`），设计里写的“均支持 `--json`”按现有约定调整。
2. `=== MEMORY ===` 段与 skill 的文字是英文（报告其他各段、`builtin/skills` 都是英文，且有测试要求 skill 正文为 ASCII）；设计里的中文提示（如“未读全，必须补读”）对应为 `NOT fully read ... you must read the rest with loopspec memory show core`。
3. `summary()` 在 `memory/` 异常（如是符号链接、topic 超过 5000 个）时不抛错，而是在 payload 里给出 `error`，由 status 段显示 `unavailable: <code>`，避免一个坏掉的 memory 目录让 `change status` 整体失败。设计未写，属于实现细节补充。
4. 既有测试 `test_status_report.py` 中固定的段落列表需要加入 `MEMORY`（该段始终存在），属于有意的预期变更，不是回归；另外 `TOP_KEYS` 新增 `memory`。
5. 设计中的提示词原文以中文为基准，落地为语义对应的英文版，共用结构化标记，测试断言这些标记。
6. 没有增加 `memory check` 之类的写入侧或敏感内容检查命令（设计已明确不做）。

## 后续事项

- topic 数量很大或需要“按相关性自动选择”时，可再评估 fragments 映射（当前方案有意不做）。
- 模型行为的真实效果（是否漏读、是否重复写入）需要在实际使用中观察。
