# 在 LoopSpec 仓库里开发时的本地环境

适用时机：在 LoopSpec 仓库（或其 worktree）里运行 loopspec 命令、跑格式化或测试时。

- 在仓库里推进 loopspec 工作流要用 `uv run loopspec`，不要用全局安装的 `loopspec`。全局 CLI 执行任何带 `--home` 的命令时都会把仓库里的 skill/command 副本同步回它自己（旧版本）的内置内容，覆盖正在开发的 skill 改动（见 [[skill-files]]）。来源：text-output-default（2026-11-20，实际发生：一次 `loopspec change status` 把 9 个 skill 副本改回 1.2.3 内容，随后用 `uv run loopspec` 重新同步）。
- 不要对整个 `src`/`tests` 运行 `ruff format`：基线中有 7 个文件本来就没按 ruff format 排版（如 `registry_sync.py`、`workflow_archive.py`、`workflow_journal.py`），整目录格式化会把这些无关改动带进交付 Diff。只格式化本次新增或改动的文件；Makefile 的 lint 只跑 `ruff check`。来源：同上（实际发生两次，提交前用 `git checkout` 撤销）。
- 本机跑全量测试用 `pytest -n 2`；`-n auto`/`-n 4` 会因内存不足被以 137 终止。来源：registry-global-store（2026-11-19）、text-output-default（`-n 2` 下 1759 passed）。
- 测试不要在 `--help` 等 rich 渲染的文本里查找选项名：CI 上帮助文本带 ANSI 颜色码，会把 `--json` 拆开导致断言失败；要检查选项就读 click/typer 命令对象的参数。本地可用 `FORCE_COLOR=1` 复现 CI 的彩色输出。来源：json-help-test（2026-11-20，main 的 Release 工作流在 #19、#21 后失败，修复前后在 FORCE_COLOR=1 下验证）。
