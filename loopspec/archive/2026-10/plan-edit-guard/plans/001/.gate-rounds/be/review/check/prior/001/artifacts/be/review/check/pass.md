---
verdict: PASS
summary: "实现与设计及返工记录一致，验收条件逐条有用例覆盖；错误处理按 fail closed 收敛，文档与 skill 同步；仅有非阻塞的改进建议"
---

# 后端代码审查：通过

## 审查输入

- 轮次：`001.1:be/review/check:1`；基线 `ec77d652…`；scopeDigest `9b4e50f4…`。
- 路径：`src/loopspec/cli.py`、`src/loopspec/plan_guard.py`、`src/loopspec/scaffold.py`、`tests/test_hook_settings.py`、`tests/test_plan_guard.py`、`tests/test_workflow_cli.py`；另核对了 `docs/{zh,en}/cli-reference.md`、`agent-protocol.md` 与 `builtin/skills/continue.md`（这些路径在 Diff 排除列表中，人工核对）。

## 结论

**正确性**：对照 proposal 的验收条件逐条核对。

| 验收条件 | 覆盖用例 |
| --- | --- |
| 编辑工具拒绝或放行 | `test_edit_tools_on_approved_plan_are_denied`、`test_draft_and_archived_plans_may_be_edited`、`test_other_change_files_are_not_guarded` |
| NotebookEdit | `test_notebook_edit_on_approved_plan_is_denied` |
| Bash 写入与读取 | `test_bash_writes_are_denied`（19 条）、`test_bash_reads_are_allowed`（8 条） |
| 符号链接与 `..` | `test_symlink_to_approved_plan_is_denied`、`test_relative_and_dotdot_paths_resolve_against_cwd` |
| 伪造确认 | `test_writing_a_new_approved_plan_is_denied`、`test_editing_a_draft_into_approved_is_denied` |
| fail closed 与非 JSON 放行 | `test_unreadable_plan_fails_closed`、`test_hook_allows_silently_on_irrelevant_input` |
| Codex apply_patch | 4 组用例 |
| init 的 Claude/Codex 配置 | `tests/test_hook_settings.py` |
| CLI 修订与归档不受影响 | 既有 `test_workflow_revision.py` 等全部通过 |

**边界条件**：
- `_plan_shape` 要求路径形如 `plans/<NNN>` 且 Change 根下有 `.workflow.yaml`，不在 Change 里的 `plan.yaml` 不受影响（`test_plan_yaml_outside_a_change_is_ignored`）。
- Edit 的结果模拟在 `old_string` 不存在时返回 None，不误判。
- `apply_patch` 的 Move 用目标文件判定伪造。

**错误处理**：
- 分析异常、超时、超限、嵌套超限时，对受保护工具一律拒绝；非 JSON 输入或非受保护工具放行。这与修订后的文档描述一致。
- `install_hooks` 遇到非法配置返回 `skipped` 而不抛错，写入是原子的。

**可维护性**：
- 判定逻辑都是纯函数，集中在 `plan_guard.py`。CLI 只负责读 stdin 和输出，配置合并逻辑放在 `scaffold.py`，与现有的工具脚手架放在一起。
- 每个常量都有说明注释，与仓库风格一致。

**文档一致性**：
- zh/en 的 `cli-reference.md` 都有 `hook pre-tool-use` 小节；`init` 小节描述了 hook 配置与 Codex 信任步骤；fail closed、只读白名单的描述与代码一致。
- `test_docs_consistency.py` 与 `test_skill_templates.py` 通过。
- `continue.md` 引用的 step 6/7 与 skill 正文一致。

**测试**：`make test` 1072 passed，`make lint` 通过（见 tests Gate 第 3 轮）。

## 非阻塞建议

- `init` 写 hook 配置时，如果遇到 `OSError`（例如 `.claude/` 不可写）会直接抛出。不过前一步写 skill 文件时已经会因同样的原因失败，所以不单独处理。
- 已归档 Change 中状态仍为 approved 的 Plan 同样受保护。这符合"只走 CLI"的原则，文档没有专门说明。
- 新建的 settings 文件权限为 0600（来自 `mkstemp`），不影响功能。
