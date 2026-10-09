## 完成的任务

本 Plan 没有 design/tasks 节点，按 proposal 的范围实现：

1. **摘要只按交付内容计算**：新增 `_delivered()`，`diff_digest` 和 `scope_digest` 计算前去掉条目中的 `index`。
2. **暂存区检查改为与 HEAD 比较**：每次扫描读取 `git ls-tree -rz --full-tree HEAD`；只有暂存内容既不等于 HEAD 中的版本、也不等于工作区时，才报 `index_worktree_mismatch`。条目是否存在改为只看交付内容是否不同于基线（`original != current`）。
3. **测试**：新增 5 个用例。
   - diff 层 3 个：修改、新增、删除、改名在 `git add` 和 `git commit` 前后摘要不变，提交后再改则摘要改变；提交后部分暂存仍然报错；提交后改回基线内容，不再是条目。
   - 端到端 2 个：Gate 与 assurance 通过后提交，需求仍为 complete 且可以归档；审查轮次中途提交，`record` 仍然成功。
4. **文档**：
   - 中英文 overview 说明暂存和提交不影响证据；
   - cli-reference 更新 `index_worktree_mismatch` 的含义；
   - release-notes 说明旧证据会失效。

## 改动文件

- 引擎：`src/loopspec/workflow_diff.py`
- 测试：`tests/test_workflow_diff.py`、`tests/test_workflow_assurance.py`
- 文档：`docs/{zh,en}/overview.md`、`docs/{zh,en}/cli-reference.md`、`docs/{zh,en}/release-notes.md`

## 执行的检查

- 新测试先红：diff 和端到端共 3 个失败；实现后通过
- `uv run pytest tests/test_workflow_diff.py tests/test_workflow_assurance.py tests/test_workflow_evidence.py -q`：52 passed，补充 2 个用例后 diff 文件 22 passed
- `make test`：938 passed（8 分 56 秒）
- `make lint`：ruff 与 mypy 通过

## 与设计的偏差

- **范围扩大**：proposal 原本只去掉摘要中的 `index`，保留暂存区检查不变。实现时发现，"提交后再修改"会因为暂存区等于新 HEAD（既不等于基线也不等于工作区）而报 `index_worktree_mismatch`，验收条件"提交后改代码使证据失效"根本无法成立。于是把这条检查的比较对象从基线改成 HEAD，并同步更新了 proposal 的范围和验收条件。部分暂存的拦截没有放宽。
- 每次扫描多一次 `git ls-tree HEAD`；HEAD 中文件的内容只在暂存区和工作区不一致时才读取。

## 后续事项

- 无
