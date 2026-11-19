## 完成的任务

- 1.1 `scaffold.expected_files(project, tool)`：一个工具全部 loopspec skill/command 文件与应有内容（含 Codex 全局 prompts）；`scaffold_tools()` 改为复用它，`init` 行为不变。
- 1.2 新模块 `skill_sync.py`：`project_root(home) = home.resolve().parent`；`managed_files()` 只取已配置工具、项目根内的文件；逐个按字节比较，缺失或不同时用 `workflow_io.atomic_write`（逐级 O_NOFOLLOW、目录 fd 写入）写入；非普通文件或路径不安全记为 skipped。
- 1.3 `HOME` 选项增加 `callback=_sync_skills`（返回原值），默认值与显式 `--home` 都会触发；`sync_before_command` 吞掉全部异常，只在 stderr 报告更新与跳过；`hook`、`version`、`update`、`init` 不使用 `HOME`，不触发。
- 1.4 `workflow_diff._exclusions()` 固定排除 loopspec 管理的 skill/command 路径，仅当工作区是普通文件且内容与当前 CLI 内置内容逐字节相同。
- 2.1 中英文 cli-reference（约定中的同步说明）、configuration（Diff 固定排除项）、release-notes（并更正上一条中关于 `--update-resources` 的不准确说法）。
- 2.2 单测 `tests/test_skill_sync.py`（15）、BDD `tests/features/skill_sync.feature`（3 场景，注册 `skill_sync` 标记与 steps 模块）。

## 改动文件

- 代码：`src/loopspec/scaffold.py`、`src/loopspec/skill_sync.py`（新）、`src/loopspec/workflow_cli.py`、`src/loopspec/workflow_diff.py`
- 测试：`tests/test_skill_sync.py`（新）、`tests/features/skill_sync.feature`（新）、`tests/steps/skill_sync_steps.py`（新）、`tests/conftest.py`、`pyproject.toml`（pytest 标记）
- 文档：`docs/{zh,en}/{cli-reference,configuration,release-notes}.md`

## 执行的检查

- `uv run ruff check src tests`：All checks passed；`uv run mypy src hatch_version.py`：Success（41 files）
- `uv run pytest -q tests/test_skill_sync.py`：15 passed（含对照组：去掉排除后同步文件出现在 Diff）
- BDD skill_sync：3 passed
- `uv run pytest -q -n 2 -m "not timing and not llm"`：1732 passed, 1 skipped
- `make test-llm`：12 passed，无重跑，15 次启动，$1.686，`.llm-e2e-runs/20261119T165618Z/`

## 与设计的偏差

- 无（设计修订 1–6 均已实现）。

## 后续事项

- 用 `init --project-root` 指定其他项目根的项目不会被同步（根目录未持久化）。
