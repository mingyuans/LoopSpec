## 1. 核心协议

- [x] 1.1 `workflow_archive`：`memory_snapshot()`（只计有效 topic）、`content_digest()`、凭据读写（`.cache/archive/`，自带 `.gitignore`）。验证：单测。
- [x] 1.2 `prepare()`：单个 / `--all`，返回 `archiveId`、`changes`、`skipped`、`memoryReview`（instructions 取自 archive skill 维护流程段落、inputs、memoryIndex）、`nextSteps`；不归档不删除。验证：单测、BDD。
- [x] 1.3 `confirm()`：参数校验、凭据校验、锁内复核与内容摘要、memory 核对（updated/none）、严格写入审阅事件、移动与删除、进度写回与重试、成功删除凭据。验证：单测、BDD。
- [x] 1.4 CLI：去掉 `--dry-run`；`--confirm/--memory/--note` 与互斥规则；新错误码。验证：`test_workflow_cli.py`。

## 2. skill 与文档

- [x] 2.1 `builtin/skills/archive.md`、`bulk-archive.md` 改为两段式；同步本仓库 `.claude`、`.codex` 生成副本；更新 skill 相关测试。验证：`test_skill_templates.py`、`test_scaffold.py`。
- [x] 2.2 中英文 `cli-reference`、`agent-protocol` 与相关文档。验证：`test_docs_consistency.py`。

## 3. 测试

- [x] 3.1 改写依赖 `--dry-run` 的既有测试（archive、cli、e2e、assurance、change BDD、init steps）。验证：`make test` 等价命令。
- [x] 3.2 LLM E2E：归档场景适配两段式并断言第二段前执行过第一段。验证：`make test-llm`。

## 4. 补做 memory

- [x] 4.1 按维护流程为 archive-drop-attempts、archive-drop-gate-outputs（及 registry-global-store 已记录教训）写入 `loopspec/memory/`，注明来源。验证：`loopspec memory list` 可见、来源齐全。

## 5. 全量验证

- [x] 5.1 lint、类型检查、全量测试、LLM E2E 全部通过并如实记录。
