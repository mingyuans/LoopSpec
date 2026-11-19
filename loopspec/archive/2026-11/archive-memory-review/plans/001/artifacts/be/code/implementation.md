## 完成的任务

- 1.1 `content_digest()`（Change 目录全部条目摘要，不跟随符号链接，跳过写锁）、`memory_snapshot()`（只计有效 topic，复用 `workflow_memory` 的扫描与安全读取）、凭据读写（`<home>/.cache/archive/<archiveId>.json`，自带 `.gitignore`；`archiveId` 为凭据主体摘要，读取时校验字段与摘要）。
- 1.2 `prepare()`：单个 / `--all`（含 `--older-than`）；锁内 settle 收尾与状态复核；返回 `archiveId`、`changes`（含 `dropped` 与 `inputs`）、`skipped`、`memoryReview`（指引 + 从 archive skill 截取的维护流程原文、`memoryIndex`）、`nextSteps`；无可归档 Change 时不发凭据。
- 1.3 `confirm()`：`--note` 按 state 文本规则校验；凭据不存在/损坏；按名排序持有全部 Change 写锁；复核状态、内容摘要、归档目标；锁内取 memory 快照核对 `updated`/`none`；逐项严格追加审阅事件 → 移动并删除运行期文件 → 进度写回凭据；全部成功后删除凭据；中途失败可用同一凭据续跑。
- 1.4 CLI：去掉 `--dry-run`；新增 `--confirm/--memory/--note` 及互斥校验；新错误码 `archive_ticket_not_found/invalid/stale`、`memory_review_required/missing/mismatch`。
- 2.1 archive / bulk-archive skill 改为两段式，同步本仓库 `.claude`、`.codex` 副本；更新 skill 测试与 init BDD 步骤。
- 2.2 中英文 `cli-reference`、`agent-protocol`（含 memory 第 4 条）、`release-notes`、README 示例。
- 3.1 改写依赖单命令归档与 `--dry-run` 的测试（archive、cli、e2e、assurance、change/init BDD）；新增两段式用例。
- 3.2 LLM E2E 两个归档场景新增断言：先第一段、再以正确的 `--memory` 确认，且归档后的 `state.md` 有审阅事件。
- 4.1 补做 memory：`loopspec/memory/archive-behavior.md`、`safe-deletion.md`、`gate-workflow.md`，来源为 archive-drop-attempts、archive-drop-gate-outputs、registry-global-store 的 state 记录与测试。

## 改动文件

- 代码：`src/loopspec/workflow_archive.py`、`src/loopspec/workflow_cli.py`、`src/loopspec/workflow_journal.py`
- skill：`builtin/skills/archive.md`、`builtin/skills/bulk-archive.md` 及 `.claude/skills`、`.claude/commands/lpsx`、`.codex/skills` 副本
- 文档：`docs/{zh,en}/{cli-reference,agent-protocol,release-notes}.md`、`README.md`
- 测试：`tests/test_workflow_archive.py`、`tests/test_workflow_cli.py`、`tests/test_workflow_e2e.py`、`tests/test_workflow_assurance.py`、`tests/test_skill_templates.py`、`tests/workflow_helpers.py`、`tests/features/{change,init,llm_skills}.feature`、`tests/steps/{change,init,llm}_steps.py`
- memory：`loopspec/memory/*.md`

## 执行的检查

- `uv run ruff check src tests`：All checks passed；`uv run mypy src hatch_version.py`：Success
- `uv run pytest -q tests/test_workflow_archive.py`：32 passed（含两段式新增 16 个）
- `uv run pytest -q -n 2 -m "not timing and not llm"`：1714 passed, 1 skipped
- `tests/test_docs_consistency.py`：43 passed
- `make test-llm`：12 passed，无重跑，15 次启动，$1.656，`.llm-e2e-runs/20261119T154013Z/`；两个归档场景中模型均先执行第一段、维护或核对 memory，再以 `--memory updated`（写入 `loopspec/memory/calc-conventions.md`）/ `--memory none`（附理由）确认。

## 与设计的偏差

- 无。

## 后续事项

- 本次 change 自身归档将首次使用两段式流程。
