## 背景

`collect_diff()`（`src/loopspec/workflow_diff.py`）为每个改动文件记录一个条目，包含 `base`（基线内容）、`index`（暂存区内容）和 `worktree`（工作区内容），以及 `path`、`kind` 和改名信息。`DiffSnapshot.diff_digest` 和 `scope_digest` 对整个条目求摘要，代码 Gate 与 assurance 的证据都绑定在这些摘要上。

`git add` 和 `git commit` 只改变暂存区，交付内容（工作区）不变，但条目里的 `index` 变了，于是摘要改变，所有证据被判 `evidence_stale`。在 assurance-unknown-paths-warn 中实际发生过：Gate 全部通过后提交代码，归档被拒绝，三个代码 Gate 都要重跑，最后只能撤销提交、先归档再提交。

暂存区已有单独的约束：它只能等于基线或等于工作区，否则报 `index_worktree_mismatch`。所以条目里的 `index` 只表示"有没有暂存"，不包含交付内容之外的信息。

## 用户场景

- 开发者在 Gate 全部通过后执行 `git add`、`git commit`，然后归档需求：证据仍然有效，可以直接归档，不需要重跑 Gate。
- 开发者在审查过程中暂存或提交部分文件：只要工作区内容没变，已经开始的审查轮次和证据都不受影响。
- 开发者提交后又改了代码：证据照常失效，需要重新审查。

## 范围

1. **摘要只按交付内容计算**：`diff_digest` 和 `scope_digest` 在计算时去掉条目里的 `index`，保留 `path`、`kind`、`base`、`worktree`、`renamed_from`、`renamed_to`。
2. **暂存区检查改为与 HEAD 比较**（实现中发现，人已知悉）：原规则要求暂存区等于基线或工作区。基线之后有过提交时，暂存区等于 HEAD，正常修改也会报 `index_worktree_mismatch`，所有计算 Diff 的命令都无法使用。改为暂存区既不等于 HEAD 中的版本、也不等于工作区时才报错，部分暂存仍会被拦下。条目是否存在只看交付内容（工作区）是否不同于基线。条目本身仍然保存 `index`，`gate begin` 的输出继续显示它。
3. **测试**：补充 diff 层和端到端（Gate → 提交 → 归档）的回归测试。
4. **文档**：中英文 release-notes 说明摘要的计算方式变了，升级前记录的代码 Gate 与 assurance 证据会失效，需要重跑；cli-reference 或 overview 中说明暂存和提交不影响证据。

## 非目标

- 不改变基线的固定方式，也不让证据跟随新的 HEAD 移动。
- 不放宽 `index_worktree_mismatch` 等暂存区一致性检查。
- 不做旧证据的迁移或兼容判定（旧摘要直接失效）。
- 不优化 `collect_diff()` 的扫描性能。

## 验收条件

- [ ] 对已修改、新增、删除、改名的文件，在 `git add` 前后、`git commit` 前后，`diff_digest` 和 `scope_digest` 都不变。
- [ ] `git commit` 之后再修改工作区内容，`diff_digest` 和 `scope_digest` 改变。
- [ ] 暂存区内容既不等于 HEAD 也不等于工作区时（提交前、提交后各一次），仍然报 `index_worktree_mismatch`。
- [ ] 基线之后提交过、再把文件改回基线内容时，该文件不是 Diff 条目。
- [ ] 端到端：代码 Gate 与 assurance 都 PASS 后，执行 `git add -A` 和 `git commit`，`change status` 仍为 `complete`，`change archive --dry-run` 成功。
- [ ] 端到端：Gate `begin` 之后、`record` 之前执行 `git add` 和 `git commit`，`record` 成功，不报 `review_input_changed`。
- [ ] 条目中仍然保留 `index`，`gate begin` 输出的 `paths[*].index` 不变。
- [ ] `make test` 全部通过，`make lint` 通过，`tests/test_docs_consistency.py` 通过。

## 风险

- **旧证据失效**：摘要的计算方式变了，升级前记录的证据全部失效。本仓库当前只有草稿需求 `state-md-writeback`，没有证据，不受影响。其他项目升级后需要对进行中的需求重跑 Gate。应对：写进 release notes。
- **安全边界**：去掉 `index` 后，证据不再区分"已暂存"和"未暂存"。交付内容始终是工作区版本，暂存区与工作区不一致时仍会被 `index_worktree_mismatch` 拦下，所以审查过的内容和交付的内容依然一致。
