## 完成的任务

- 1.1/1.2 新增 `plan_guard.py`：受保护形状判定（realpath、`plans/<NNN>/plan.yaml`、Change 根有 `.workflow.yaml`）、状态读取（2 MiB、`parse_yaml`、fail closed）、Edit/MultiEdit/Write 结果模拟防伪造确认、deny 原因文本。
- 2.1/2.2 Bash 启发式（shlex 分词、简单命令切分、`cd` 跟踪、路径片段提取与 glob、重定向目标、只读白名单、嵌套 `bash -c` 脚本、引号不配对退化）与 Codex `apply_patch` 文件头解析（Add/Update/Delete/Move，新增行 `status: approved`）。
- 3.1/3.2 `loopspec hook pre-tool-use`：stdin 上限 1 MiB，命中输出 deny JSON，其他情况静默放行；意外异常放行并写 stderr。
- 4.1/4.2 `scaffold.install_hooks()`：Claude `.claude/settings.json`、Codex `.codex/hooks.json` 合并写入（created/updated/unchanged/skipped，原子替换，不写符号链接/非法 JSON）；`init` JSON 新增 `hooks`，文本输出附 hook 状态与 Codex `/hooks` 信任提示。
- 5.1–5.3 zh/en `cli-reference.md`、`agent-protocol.md`；`builtin/skills/continue.md` 并同步 `.claude/skills`、`.claude/commands/lpsx`。
- 6.1 全量回归。

## 改动文件

- 新增：`src/loopspec/plan_guard.py`、`tests/test_plan_guard.py`、`tests/test_hook_settings.py`
- 修改：`src/loopspec/cli.py`、`src/loopspec/scaffold.py`、`tests/test_workflow_cli.py`（命令树加入 `hook`）
- 文档/skill：`docs/{zh,en}/cli-reference.md`、`docs/{zh,en}/agent-protocol.md`、`builtin/skills/continue.md`、`.claude/skills/loopspec-continue/SKILL.md`、`.claude/commands/lpsx/*.md`（与 builtin 重新同步，含此前未同步的 archive/new 文案）

## 执行的检查

- `uv run pytest tests/test_plan_guard.py tests/test_hook_settings.py`：72 passed（实现前因模块缺失收集失败）。
- `make test`：1058 passed in 670.90s。
- `make lint`：ruff All checks passed；mypy Success: no issues found in 34 source files。

## 与设计的偏差

- Bash 只读白名单额外包含 `echo`（重定向目标仍单独判定，`echo x > plan.yaml` 照样拒绝）。
- Bash 对含空格的参数（如 `bash -c "<script>"`）递归按 shell 解析，设计未写明，用于覆盖嵌套脚本。
- `init` 的 hook 状态行在原有汇总之后输出，而非并入 `render_init_summary`，避免改动展示模块。

## 后续事项

- 本仓库自身未启用 hook；需要时执行 `loopspec init --tools claude,codex`。
