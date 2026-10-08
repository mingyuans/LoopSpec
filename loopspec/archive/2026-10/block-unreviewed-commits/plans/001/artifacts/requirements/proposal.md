## 背景

`aea1744`（evidence-survives-commit）让证据摘要只绑定基线与工作区内容，并把暂存区检查从"与基线比较"改为"与 HEAD 比较"。后台安全审查指出，这带来一个门禁绕过：

1. 把未审查的内容 C 提交进 HEAD；
2. 把工作区改回审查过的内容 W，不提交；
3. Diff 与证据只看"基线 → 工作区"，看到的是 W，Gate 和 assurance 都有效，可以归档；
4. 真正在 git 历史里、会被 push 出去的是 C。

修改之前，第 2 步会触发 `index_worktree_mismatch`，这种状态根本无法继续。人已选择方案 A：开发过程中保持可用，交付判定时拦截。

## 用户场景

- 正常交付：Gate 通过后提交全部改动，或者完全不提交，assurance 通过，可以归档。
- 开发中途提交过一个中间版本，然后继续修改：`status` 和代码 Gate 照常可用；assurance 提示有偏离提交，要求把最终内容提交后再判定。
- 有人提交了未审查的内容，同时把工作区恢复成审查过的版本：assurance 判 FAIL；如果 assurance 之前已经 PASS，需求退回未完成，归档被拒。

## 范围

1. **识别偏离提交**：`collect_diff()` 对每个未排除的路径（包括只存在于 HEAD 中的路径），如果 HEAD 中的内容既不等于基线内容、也不等于工作区内容，就把它记入 `DiffSnapshot.diverged`，按路径排序。只有 HEAD 对象与基线对象不同时才读取 HEAD 内容。`diverged` 不参与 `diff_digest` 和 `scope_digest`。
2. **assurance 判定**：`diagnose()` 新增 `diverged_commits` 类别，列出偏离路径，非空即判 FAIL；系统 FAIL 报告的 `summary` 说明原因和处理方法（提交最终内容，或撤销中间提交）。
3. **证据复核**：assurance 节点的证据在当前快照存在偏离提交时视为过期（`evidence_stale`），所以 `change status` 不是 complete，`change archive` 被拒。
4. **文档**：中英文 overview 与 cli-reference（assurance 诊断类别）说明偏离提交及处理方法；release-notes 补充一条。
5. **测试**：见验收条件。

## 非目标

- 不改变代码 Gate 的证据规则：代码 Gate 审查的仍然是工作区内容，偏离提交只由 assurance 和归档把关。
- 不检查 push 到远端的状态，也不检查基线之前的提交历史。
- 不恢复"提交后再修改就报 `index_worktree_mismatch`"的严格规则。

## 验收条件

- [ ] 绕过回归：Gate 与 assurance 都 PASS 后，提交未审查的内容，再把工作区改回审查过的内容，`change status` 不是 complete，assurance 节点的 reason 为 `evidence_stale`，`change archive --dry-run` 被拒；重新执行 assurance 判 FAIL，`diverged_commits` 包含该路径。
- [ ] 先提交未审查内容、工作区保留审查版本，再执行 assurance：判 FAIL，`diverged_commits` 包含该路径。
- [ ] 正常流程：Gate 与 assurance 通过后执行 `git add -A` 和 `git commit`，仍为 complete，可以归档（原有用例继续通过）。
- [ ] 提交中间版本后继续修改：`collect_diff()` 不报错，`diverged` 包含该路径，代码 Gate 的 begin/record 可用；把最终内容提交后 `diverged` 为空。
- [ ] 提交后又把文件改回基线内容（HEAD 是中间版本）：该路径出现在 `diverged` 中。
- [ ] 被排除的路径（如 `excluded_paths`、当前 Change 的控制文件）即使有偏离提交，也不出现在 `diverged` 中。
- [ ] `diverged` 不影响 `diff_digest` 和 `scope_digest`。
- [ ] `make test` 全部通过，`make lint` 通过，`tests/test_docs_consistency.py` 通过。

## 风险

- **交付流程更严格**：只提交一部分、又在工作区继续修改的中间状态，assurance 无法通过，必须在交付前把最终内容提交，或者撤销中间提交。报告与文档会说明处理方法。
- **性能**：每次扫描多读取 HEAD 中与基线不同的文件内容，仍受单文件与累计大小限制约束。
- **历史改写**：rebase 等操作之后，HEAD 中的内容仍按"等于基线或等于工作区"判定，不会放宽。
