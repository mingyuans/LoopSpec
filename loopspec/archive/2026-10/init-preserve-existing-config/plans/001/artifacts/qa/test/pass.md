---
verdict: PASS
summary: "以本地构建的 loopspec 在临时目录及真实 pty 中逐条验证 AC1–AC10，全部符合预期"
---

# 验收测试：通过

## 验收条件核对
- [x] AC1 首次 init `--json`：`resourcesUpdate=installed`，复制了 fragments/profiles。
- [x] AC2 删除 `profiles/bugfix.yaml` 后 `--json` 重跑：`skipped`，`copiedWorkflowResources=[]`，文件未恢复。
- [x] AC3 `--update-resources --json`：`installed`，`copiedWorkflowResources=['profiles/bugfix.yaml']`，仅补回缺失文件（自动化用例同时验证定制文件不被改写）。
- [x] AC4 非 TTY 人类输出（stdin 为 /dev/null）：无提示，输出 “Kept existing fragments/profiles; rerun with --update-resources ...”，文件未恢复。
- [x] AC5 真实 pty 输入 `n` / 直接回车：出现 `[y/N]` 提示与跳过提示，文件未恢复。
- [x] AC6 真实 pty 输入 `y`：出现提示，`bugfix.yaml` 被补回。
- [x] AC7 真实 pty + `--update-resources`：无提示，`bugfix.yaml` 被补回。
- [x] AC8 已存在时 `--tools claude --json`：`skipped`、`toolsConfigured=['claude']`，`.claude/skills/loopspec-*` 已生成，profiles 未补齐。
- [x] AC9 仅 `fragments/custom` 存在：`skipped`，未创建 `profiles/`，未写入内置 fragment。
- [x] AC10 `make test` 1154 passed；`make lint`（ruff + mypy）通过；`docs-check` 包含在全量测试中通过。`init --help` 显示 `--update-resources` 说明。

## 执行的测试
- 临时目录（scratchpad/qa）中运行 `.venv/bin/loopspec init ...` 覆盖 AC1–AC4、AC8、AC9，结果见上。
- `scratchpad/pty_run.py`：用 Python `pty.fork()` 启动 `loopspec init <home> --tools none`，看到 `[y/N]` 后发送答案，分别验证 `y`、`n`、空回车及 `--update-resources`（AC5–AC7）。
- 说明：先尝试 `printf | script -q /dev/null ...`，因 macOS `script` 在管道下提前发送 EOF，`y` 未送达而被视为拒绝（符合 EOF→拒绝设计）；改用 pty 驱动后结果正确。

## 剩余风险
- 未覆盖 Windows 终端下的提示交互。
