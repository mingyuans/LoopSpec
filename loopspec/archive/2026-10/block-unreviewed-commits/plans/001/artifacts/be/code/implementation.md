## 完成的任务

本 Plan 没有 design/tasks 节点，按 proposal 的范围 1–5 实现：

1. **识别偏离提交**：
   - `collect_diff()` 的候选路径加入 HEAD 树中的路径；快速跳过条件增加"HEAD 对象等于基线对象"。
   - 只有 HEAD 对象与基线不同时才读取 HEAD 内容；内容既不等于基线也不等于工作区时，记入 `DiffSnapshot.diverged`（按路径排序），不参与任何摘要。
   - 被排除的路径在循环开头就跳过，不做检查。
2. **assurance 判定**：诊断新增 `diverged_commits`，计入失败条件。`diverged_text()` 在系统报告的 `summary` 中列出路径（最多 20 条、4000 字符）并给出处理方法。
3. **证据复核**：`valid_evidence()` 对 assurance 节点，只要当前快照存在偏离提交就返回 `evidence_stale`，所以 status 不是 complete，archive 被拒。
4. **文档**：中英文 workflow-composition（诊断类别与处理方法）、overview（交付前 HEAD 的要求）、release-notes。
5. **测试**：新增 8 个用例。
   - diff 层 4 个：绕过场景、中间提交到最终提交、提交后改回基线、被排除路径。
   - assurance 4 个：PASS 后绕过被拦、绕过发生在 assurance 前、中间提交时代码 Gate 仍可用直到最终提交、FAIL 摘要的长度上限。

## 改动文件

- 引擎：`src/loopspec/workflow_diff.py`、`src/loopspec/workflow_assurance.py`、`src/loopspec/workflow_evidence.py`
- 测试：`tests/test_workflow_diff.py`、`tests/test_workflow_assurance.py`
- 文档：`docs/{zh,en}/workflow-composition.md`、`docs/{zh,en}/overview.md`、`docs/{zh,en}/release-notes.md`

## 执行的检查

- 新测试先红（6 failed），实现后通过；补充 2 个用例后也通过
- `uv run pytest tests/test_workflow_diff.py tests/test_workflow_assurance.py tests/test_workflow_evidence.py -q`：60 passed
- `make test`：946 passed（6 分 36 秒）
- `make lint`：ruff 与 mypy 通过

## 与设计的偏差

- 存在偏离提交时，assurance 的 FAIL 证据同样视为过期，节点回到 ready 而不是 failed。修复手段是 git 操作（提交最终内容或撤销中间提交），不是代码返工；这样既不消耗 `on_fail` 次数，也不会因为 assurance 没有 `on_fail` 而进入 exhausted。修正后重新执行 assurance 即可。

## 后续事项

- 无
