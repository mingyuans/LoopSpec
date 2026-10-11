## 完成的任务

- 1.1/1.2 新增 `plan_guard.py`：受保护形状判定（realpath、`plans/<NNN>/plan.yaml`、Change 根有 `.workflow.yaml`）、状态读取（非阻塞打开、要求普通文件、2 MiB、`parse_yaml`；读不了按未确认处理）、Edit/MultiEdit/Write 结果模拟防伪造确认、deny 原因文本。
- 2.1/2.2 Bash 启发式（shlex 分词、简单命令切分、`cd` 跟踪、线性路径片段提取、通配符展开（含不带 `plan.yaml` 字样的 token）、重定向目标、只读白名单、嵌套 `bash -c` 递归且限深 8 层、引号不配对退化）与 Codex `apply_patch` 文件头解析。
- 3.1/3.2 `loopspec hook pre-tool-use`：命中输出 deny JSON；其他一律静默放行，包括超大输入、分析超 10 秒（SIGALRM）与任何分析异常（能检测到就禁，检测不了就放行）。
- 4.1/4.2 `scaffold.install_hooks()`：Claude `.claude/settings.json`、Codex `.codex/hooks.json` 合并写入（created/updated/unchanged/skipped，原子替换，不写符号链接/非法 JSON）；`init` JSON 新增 `hooks`，文本输出附 hook 状态与 Codex `/hooks` 信任提示。
- 5.1–5.3 zh/en `cli-reference.md`（含 fail closed 说明）、`agent-protocol.md`；`builtin/skills/continue.md` 并同步 `.claude/skills`、`.claude/commands/lpsx`。
- 6.1 全量回归。

### 返工（attempt 1，be/security/check FAIL）

- 路径提取由正则 `[^…]*plan\.yaml`（O(n²)，10 万字符命令 20 秒未完成）改为 `str.find` + 向左有界扩展的线性扫描；30 万字符命令 0.75 秒内判定。
- 曾改为对超时、嵌套超限、分析异常一律拒绝（fail closed）；之后按用户决定改回放行，保留线性扫描与 10 秒时间预算，使 hook 在宿主超时前就给出结果。嵌套超过 8 层的脚本不再展开，命令其余部分照常检查。
- plan.yaml 读取改为 `O_NONBLOCK` + `fstat` 普通文件检查，FIFO 不再阻塞。
- 新增回归用例：长命令限时、超大输入放行、异常放行、时间预算放行、深度嵌套有界、FIFO 不阻塞、`pl?n.yaml`/`rm *` 通配符、`p'l'an.yaml` 引号拼接。

## 改动文件

- 新增：`src/loopspec/plan_guard.py`、`tests/test_plan_guard.py`、`tests/test_hook_settings.py`
- 修改：`src/loopspec/cli.py`、`src/loopspec/scaffold.py`、`tests/test_workflow_cli.py`（命令树加入 `hook`）
- 文档/skill：`docs/{zh,en}/cli-reference.md`、`docs/{zh,en}/agent-protocol.md`、`builtin/skills/continue.md`、`.claude/skills/loopspec-continue/SKILL.md`、`.claude/commands/lpsx/*.md`（与 builtin 重新同步）

## 执行的检查

- `uv run pytest tests/test_plan_guard.py`：71 passed（含白名单收紧后的新增写入用例）。
- `make test`：1072 passed in 466.03s（改为“能检测到就禁，检测不了就放行”之后）。
- `make lint`：ruff All checks passed；mypy Success: no issues found in 34 source files。

## 与设计的偏差

- 设计中"无法读取或解析的 plan.yaml 视为受保护（fail closed）"按用户决定改为放行；异常、超时、超限均放行（与设计"意外异常放行"一致）。
- stdin 上限由 1 MiB 改为 64 MiB；超出时无法解析，按用户决定放行，不影响正常工具调用。
- Bash 只读白名单额外包含 `echo`（重定向目标仍单独判定）；`sed` 移出白名单（其 `w` 命令可写文件），`less`/`more` 移除（`-o` 写日志文件），`yq -i`/`--inplace`、`git --output`、`rg --pre` 视为写入；粘连在其他字符后的 `plan.yaml`（如 `sed 1wplan.yaml`）也按同目录的 plan.yaml 判定。
- Bash 对含空格的参数（如 `bash -c "<script>"`）递归按 shell 解析，限深 8 层。
- 不含 `plan.yaml` 字样但含通配符的 token 也展开检查。
- `init` 的 hook 状态行在原有汇总之后输出，而非并入 `render_init_summary`。

## 后续事项

- 本仓库自身未启用 hook；需要时执行 `loopspec init --tools claude,codex`。
- 时间预算依赖 SIGALRM，Windows 上无此保护（Codex hook 官方说明 Windows 支持有限）。
