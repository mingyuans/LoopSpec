## 1. 测试先行

- [x] 1.1 `tests/test_workflow_runtime.py`：扇出 Plan（A → B、C、D → Gate E）的 `nextSteps` / `parallel` 随进度变化；线性 Plan 行为不变；分支 Gate FAIL（有/无重试）时 rollback / 空列表且 `parallel` False。验证：新增用例在实现前失败。
- [x] 1.2 `tests/test_workflow_cli.py`：`change status --json` 各状态的 `parallel`；`change next` 的 `nodes` 与 `node`。验证：新增用例在实现前失败。
- [x] 1.3 `tests/test_status_report.py`：并行提示、单步提示不变、NODES 新文案、`parallel` 在 `TOP_KEYS`。验证：新增用例在实现前失败。

## 2. 引擎

- [x] 2.1 `workflow_runtime.status`：列出全部 ready 叶子并输出 `parallel`。验证：1.1 通过。
- [x] 2.2 `workflow_changes.status` / `next_step`：各分支补 `parallel`，`next_step` 增加 `nodes`。验证：1.2 通过。

## 3. 文本报告

- [x] 3.1 `status_report`：`TOP_KEYS` 加 `parallel`，新增并行提示，改 NODES 提示。验证：1.3 通过。

## 4. Skill

- [x] 4.1 `builtin/skills/continue.md` 补充并行派发与 `concurrent_write` 重试说明。验证：skill 模板测试通过。
- [x] 4.2 同步 `.claude/skills/loopspec-continue/SKILL.md`、`.codex/skills/loopspec-continue/SKILL.md`。验证：`diff` 与源文件一致。

## 5. 文档

- [x] 5.1 `docs/{en,zh}/agent-protocol.md`、`cli-reference.md` 更新 `nextSteps` / `parallel` / `change next` 描述。
- [x] 5.2 `docs/{en,zh}/workflow-composition.md` 新增扇出 / 扇入评审示例；`release-notes.md` 追加条目。

## 6. 验证

- [x] 6.1 `make test` 全量通过，lint 通过，记录真实输出。
