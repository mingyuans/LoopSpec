## 完成的任务

- 1.1 `scaffold.expected_files(project, tool)`：一个工具全部 loopspec skill/command 文件与应有内容（含 Codex 全局 prompts）；`scaffold_tools()` 改为复用它，`init` 行为不变。
- 1.2 新模块 `skill_sync.py`：`project_root(home) = home.resolve().parent`；`managed_files()` 只取已配置工具、项目根内的文件；逐个按字节比较，缺失或不同时用 `workflow_io.atomic_write`（逐级 O_NOFOLLOW、目录 fd 写入）写入；非普通文件或路径不安全记为 skipped。
- 1.3 `HOME` 选项增加 `callback=_sync_skills`（返回原值），默认值与显式 `--home` 都会触发；`sync_before_command` 吞掉全部异常，只在 stderr 报告更新与跳过；`hook`、`version`、`update`、`init` 不使用 `HOME`，不触发。
- 1.4 `workflow_diff._exclusions()` 固定排除 loopspec 管理的 skill/command 路径，仅当工作区是普通文件且内容与当前 CLI 内置内容逐字节相同。
- 返工（安全审查 FAIL 后，rollback 001）：managed skill 的 Diff 排除改在 `collect_diff` 主循环中判定，除工作区为模板内容的普通文件外，暂存区与 HEAD 中与基线不同的版本也必须是同一 blob（按仓库对象格式计算 sha1/sha256 blob id、mode 100644），否则照常走 Diff 与 index/提交一致性检查；配置文档同步说明。
- 2.1 中英文 cli-reference（约定中的同步说明）、configuration（Diff 固定排除项）、release-notes（并更正上一条中关于 `--update-resources` 的不准确说法）。
- 2.2 单测 `tests/test_skill_sync.py`（15）、BDD `tests/features/skill_sync.feature`（3 场景，注册 `skill_sync` 标记与 steps 模块）。

## 改动文件

- 代码：`src/loopspec/scaffold.py`、`src/loopspec/skill_sync.py`（新）、`src/loopspec/workflow_cli.py`、`src/loopspec/workflow_diff.py`
- 测试：`tests/test_skill_sync.py`（新）、`tests/features/skill_sync.feature`（新）、`tests/steps/skill_sync_steps.py`（新）、`tests/conftest.py`、`pyproject.toml`（pytest 标记）
- 文档：`docs/{zh,en}/{cli-reference,configuration,release-notes}.md`

## 执行的检查

- `uv run ruff check src tests`：All checks passed；`uv run mypy src hatch_version.py`：Success（41 files）
- `uv run pytest -q tests/test_skill_sync.py`：18 passed（含对照组；返工新增：提交未审查内容后恢复工作区仍被审查、暂存内容与工作区不一致报 index_worktree_mismatch、同步后提交仍被排除）
- BDD skill_sync：3 passed
- `uv run pytest -q -n 2 -m "not timing and not llm"`：1735 passed, 1 skipped（返工后）
- `make test-llm`（返工前；返工只影响 managed skill 路径的 Diff 判定，LLM 场景不涉及）：12 passed，无重跑，15 次启动，$1.686，`.llm-e2e-runs/20261119T165618Z/`

## 与设计的偏差

- 无（设计修订 1–6 均已实现）。

## 后续事项

- 用 `init --project-root` 指定其他项目根的项目不会被同步（根目录未持久化）。
