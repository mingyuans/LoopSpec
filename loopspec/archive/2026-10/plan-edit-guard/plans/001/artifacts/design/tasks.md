# 实施任务

按 TDD 推进：每组先写失败的测试，再实现到全部通过。用例对应 `design.md` 的"验证方案"。

## 1. 判定逻辑 `plan_guard.py`

- [x] 1.1 新增 `tests/test_plan_guard.py`：编辑类工具（Edit/MultiEdit/Write/NotebookEdit）对 approved / draft / archived / request.yaml / state.md 的结果；相对路径 + `cwd`、`..`、符号链接；伪造确认（Write 新建 approved、Edit 把 draft 改成 approved）；fail closed（受保护形状但内容非法）。验证：新用例因功能缺失而失败。
- [x] 1.2 新增 `src/loopspec/plan_guard.py`：受保护形状判定、当前状态读取（2 MiB 上限、`parse_yaml`、fail closed）、Edit/MultiEdit 结果模拟、deny 原因文本。验证：1.1 用例通过。

## 2. Bash 启发式与 Codex `apply_patch`

- [x] 2.1 在 `tests/test_plan_guard.py` 写 Bash 用例（`sed -i`、`>`、`>>`、`tee`、`cp`、`mv`、`rm`、`python3 -c`、`cd ... && sed -i`、glob 写入、引号不配对 → deny；`cat`、`grep`、`cat p > /tmp/x`、`sed -n`、`git diff`、`loopspec plan show` → allow；数组 command）与 Codex `apply_patch` 用例（Add/Update/Delete/Move 指向 approved → deny；Add 新建 approved 内容 → deny；Update draft / 其他文件 → allow）。验证：新用例失败。
- [x] 2.2 实现 Bash 分词、简单命令切分、`cd` 跟踪、路径片段提取与 glob、重定向目标与只读白名单；实现 `apply_patch` 文件头解析。验证：2.1 用例通过。

## 3. hook 入口命令

- [x] 3.1 CLI 用例：`loopspec hook pre-tool-use` 命中时 stdout 为 deny JSON、退出码 0、原因含 `plan approve` 与 `plan archive`；stdin 非 JSON / 非对象 / 未知工具 → 退出码 0、无 stdout。验证：新用例失败。
- [x] 3.2 在 `cli.py` 注册 `hook` 命令组与 `pre-tool-use`（stdin 上限 1 MiB；意外异常放行并写 stderr）。验证：3.1 通过。

## 4. `loopspec init` 写入 hook 配置

- [x] 4.1 新增 `tests/test_hook_settings.py`：Claude（`.claude/settings.json`）与 Codex（`.codex/hooks.json`）各自 created / updated（保留其他键与其他 PreToolUse）/ unchanged / skipped（非法 JSON、符号链接，文件不变）；`init --tools claude,codex --json` 含 `hooks.claude`、`hooks.codex`；未选工具不写。验证：新用例失败。
- [x] 4.2 `scaffold.py` 新增 `install_hooks()`（原子写入）；`cli.py` 的 `init` 调用并输出结果、文本汇总一行与 Codex `/hooks` 信任提示。验证：4.1 通过；既有 init 测试通过。

## 5. 文档与 skill

- [x] 5.1 zh/en `docs/*/cli-reference.md`：`hook pre-tool-use` 小节、`init` 的 hook 配置行为（含 Codex 信任步骤）。
- [x] 5.2 zh/en `docs/*/agent-protocol.md`：已确认 Plan 受 hook 保护、被拒后的正确路径与局限。
- [x] 5.3 `builtin/skills/continue.md` 补充"hook 拒绝时按提示走 CLI，不得绕过"，同步 `.claude/skills/loopspec-continue/SKILL.md`。验证：`tests/test_skill_templates.py`、`tests/test_docs_consistency.py` 通过。

## 6. 回归

- [x] 6.1 `make test` 与 `make lint` 全部通过，记录真实结果。结果：1058 passed；ruff、mypy 通过。
