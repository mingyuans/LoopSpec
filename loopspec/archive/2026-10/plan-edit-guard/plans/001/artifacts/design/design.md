## 背景与现状

- plan.yaml 位于 `<home>/<artifacts_dir>/<change>/plans/<NNN>/plan.yaml`（归档后在 `<home>/archive/<YYYY-MM>/<change>/...`），
  Change 根目录有 `.workflow.yaml`。`meta.status` 取值 `draft` / `approved` / `archived`。
- 引擎只通过 `workflow_state.write_plan` 写 plan.yaml；读取时 `read_plan` 校验 `spec_digest(spec) == meta.digest`，
  但 LLM 可同时改写 digest，或把 draft 直接改成 approved（spec 不变 digest 仍匹配）。
- `loopspec init --tools claude` 目前只写 `.claude/skills/*` 与 `.claude/commands/lpsx/*`，不写 settings。
- Claude Code PreToolUse hook：stdin 收到 `{"tool_name", "tool_input", "cwd", "hook_event_name", ...}`；
  stdout 输出 `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
  "permissionDecisionReason": "..."}}` 且退出码 0 即拒绝该调用，原因会回传给模型；此拒绝在任何权限模式下生效。
- Codex CLI 也有同构的 hook 机制（官方文档 learn.chatgpt.com/docs/hooks）：项目级 `<repo>/.codex/hooks.json`，
  结构与 Claude Code 相同（`hooks.PreToolUse[].matcher` + `hooks[].type/command`），默认启用（`[features] hooks`）；
  stdin 字段同样有 `tool_name`、`tool_input`、`cwd`；拒绝输出与 Claude Code 相同的 `hookSpecificOutput` deny JSON。
  差异：shell 命令 `tool_name` 为 `Bash`、`tool_input.command`；文件编辑统一为 `apply_patch`，
  补丁全文在 `tool_input.command`；项目级 hook 需用户在 Codex 中信任 `.codex/` 层并用 `/hooks` 审阅后才运行。

## 目标 / 非目标

**目标：**
- LLM 的编辑类工具与 Bash 不能直接改写已确认 Plan 的 plan.yaml，也不能把 plan.yaml 直接写成 approved。
- 同一条 `loopspec hook pre-tool-use` 同时服务 Claude Code 与 Codex。
- `loopspec init` 选中 `claude` / `codex` 时分别写入各自的项目级 hook 配置。

**非目标：**
- 不改变 CLI 写入（`plan approve`、`plan approve -f`、`plan archive`、rollback 等）。
- 不保护 plan.yaml 以外的文件；不支持 Claude Code、Codex 以外的 AI 工具；Bash 检测不是安全边界。
- 不替用户完成 Codex 的 hook 信任（`/hooks` 审阅）。

## 方案

### 1. 判定规则（新模块 `src/loopspec/plan_guard.py`，纯函数，便于单测）

**受保护形状**：真实路径 `p`（`os.path.realpath(join(cwd, path))`）满足
`p.name == "plan.yaml"`、`p.parent.name` 匹配 `PLAN_RE`、`p.parent.parent.name == "plans"`、
`p.parent.parent.parent / ".workflow.yaml"` 是普通文件。不依赖 workflow home 与 `artifacts_dir` 配置，归档 Change 同样识别。

**当前状态**：读取 `p`（上限 2 MiB，`parse_yaml`），取 `meta.status`。
- 文件不存在 → `None`；存在但无法读取 / 解析 / 缺字段 → 视为 `approved`（fail closed）。

**拒绝条件**（任一成立）：
1. 当前状态为 `approved`。
2. 写入后的状态为 `approved`（防止伪造确认）：
   - `Write`：解析 `tool_input.content`；
   - `Edit`：读取当前文本，按 `old_string` → `new_string`（`replace_all` 时全部替换，否则替换第一次出现）得到结果后解析；
   - `MultiEdit`：依次应用 `edits`；
   - 结果无法解析时不据此拒绝（引擎读取时会报 `plan_integrity`），只看条件 1。

草稿、已归档 Plan 的普通编辑放行（与现状一致）。

**工具覆盖**：

| tool_name | 路径来源 | 判定 |
| --- | --- | --- |
| `Edit` / `MultiEdit` / `Write` | `tool_input.file_path` | 条件 1、2 |
| `NotebookEdit` | `tool_input.notebook_path` | 条件 1 |
| `apply_patch`（Codex） | `tool_input.command` 补丁头 | 条件 1；新增内容含 approved 时条件 2 |
| `Bash` | `tool_input.command` 启发式 | 条件 1 |
| 其他 | — | 放行 |

### 1b. Codex `apply_patch` 解析

补丁格式为 `*** Begin Patch` … `*** End Patch`，文件头为 `*** Add File: <path>`、`*** Update File: <path>`、
`*** Delete File: <path>`，Update 下可有 `*** Move to: <path>`。逐行扫描文件头取路径（相对 `cwd`），对每个路径：
- 指向当前 approved 的受保护文件（含 Delete、Move 的源与目标）→ 拒绝（条件 1）；
- 指向受保护形状且该文件段内 `+` 开头的新增行按 YAML 片段匹配到 `status: approved`（正则 `^\+\s*status:\s*['"]?approved['"]?\s*$`）→ 拒绝（条件 2，近似判定）。
`tool_input.command` 不是字符串时放行该段判定。

### 2. Bash 启发式

1. 用 `shlex.shlex(command, posix=True, punctuation_chars=True)` 分词；分词失败（引号不配对）时退化为：
   命令原文中任一含 `plan.yaml` 的路径片段指向受保护文件即拒绝。
2. 按 `;`、`&&`、`||`、`|`、`&`、换行切成简单命令；顺序跟踪 `cd <dir>` 更新有效 cwd（`cd` 参数含变量 / 无法解析时停止跟踪，后续按原 cwd）。
3. 对每个简单命令，从每个 token 中用正则 `[^\s'"=]*plan\.yaml` 提取路径片段（覆盖 `of=plan.yaml`、
   `python -c "open('x/plan.yaml','w')"` 中的嵌入路径）；含 `*?[` 时在有效 cwd 下 `glob`（最多 256 个结果）。
4. 若某片段指向当前 approved 的受保护文件：
   - 该片段是重定向目标（前一 token 为 `>`、`>>`、`>|`、`&>`、`&>>`、`<>`）→ 拒绝；
   - 否则命令名（`argv[0]` 的 basename）在只读白名单内且无写入标志 → 放行；
     白名单：`cat less more head tail grep egrep fgrep rg wc diff cmp ls stat file sha256sum shasum md5 md5sum yq jq bat`、
     `sed`（无 `-i` / `--in-place`）、`git`（子命令 `diff log show status blame`）、`loopspec`；
   - 其他命令名（`tee`、`mv`、`cp`、`rm`、`sed -i`、`perl`、`python`、`dd`、`truncate`、`ln`、`install` 等）→ 拒绝。
5. 前导的 `env`、`sudo`、`command`、`nohup`、`time` 与 `VAR=value` 赋值跳过后再取命令名。

### 3. hook 入口（`loopspec hook pre-tool-use`）

- 新增 `hook` 命令组（`src/loopspec/cli.py` 注册，逻辑在 `plan_guard.py`）。
- 读取 stdin（上限 1 MiB），`json.loads`；不是对象 / 缺 `tool_name` → 退出码 0、无输出（放行）。
- Claude Code 与 Codex 共用：按 `tool_name` 分派，不区分来源；Codex 的 `Bash` 若 `tool_input.command` 为数组，用 `shlex.join` 还原后按字符串处理。
- `cwd` 缺失时用进程 cwd。
- 判定出错（意外异常）→ 放行并在 stderr 写一行 `loopspec hook: <错误类型>`；受保护文件的读取失败已在判定内 fail closed。
- 命中时 stdout 输出 deny JSON，退出码 0。原因文本（英文，供模型阅读）：

```
LoopSpec: <path> belongs to approved Plan <NNN> of change <change>; do not edit plan.yaml directly.
To adjust the Plan, write a revision request, run `loopspec plan validate -c <change> -f <request>`,
show the human the digest, and after they confirm run `loopspec plan approve -c <change> -p <NNN> -f <request> --digest <digest>`.
If the flow no longer fits, get the human's consent, run `loopspec plan archive -c <change> -p <NNN> --note <reason>`,
then plan again with `loopspec plan create`.
```

  伪造确认（条件 2）时第一句改为 `writing an approved plan.yaml by hand is not allowed; only loopspec plan approve can approve a Plan.`

### 4. `loopspec init` 写入 hook 配置（新函数 `install_hooks(project_root, tool_ids)`，放在 `scaffold.py`）

- `claude` 在所选工具中 → `<project-root>/.claude/settings.json`，matcher `Edit|MultiEdit|Write|NotebookEdit|Bash`；
- `codex` 在所选工具中 → `<project-root>/.codex/hooks.json`，matcher `^apply_patch$|^Bash$`；
- 两个文件的合并规则相同（下同），JSON 结构相同（仅 matcher 不同）。
- 要合并的条目：

```json
{"hooks": {"PreToolUse": [{"matcher": "Edit|MultiEdit|Write|NotebookEdit|Bash",
  "hooks": [{"type": "command", "command": "loopspec hook pre-tool-use"}]}]}}
```

- 文件不存在 → 创建（含上述内容）→ `created`。
- 存在且是 JSON 对象：任一 `hooks.PreToolUse[*].hooks[*].command == "loopspec hook pre-tool-use"` → `unchanged`；
  否则追加一个 matcher 条目，保留其他键 → `updated`。
- 文件是符号链接 / 非普通文件 / 非法 JSON / `hooks` 或 `PreToolUse` 类型不对 → 不写入 → `skipped` 并带原因。
- 写入：同目录临时文件 + `os.replace`，`indent=2`，`ensure_ascii=False`，末尾换行。
- `init` JSON 结果新增 `hooks: {"claude": {"path", "status", "reason"?}, "codex": {...}}`（只含所选工具）；
  文本输出在汇总后加一行说明；选中 codex 时提示用户在 Codex 中用 `/hooks` 审阅并信任该 hook。

### 5. 文档与 skill

- zh/en `cli-reference.md`：新增 `loopspec hook pre-tool-use` 小节与 `init` 的 hook 配置行为（Claude Code、Codex；Codex 的信任步骤）。
- zh/en `agent-protocol.md`：说明已确认 Plan 受 hook 保护、被拒绝后的正确路径。
- `builtin/skills/continue.md`（同步 `.claude/skills`）：在"Never hand-edit plan.yaml"后补
  "If a hook denies an edit, follow its instructions; never work around it."

## 归属与路径

全部为 BE（Python CLI）：

- 新增 `src/loopspec/plan_guard.py`
- 修改 `src/loopspec/cli.py`（`hook` 命令组、init 调用与结果）、`src/loopspec/scaffold.py`（`install_claude_hook`）、
  `src/loopspec/presentation.py`（init 汇总一行，若需要）
- 测试：新增 `tests/test_plan_guard.py`、`tests/test_hook_settings.py`；必要时更新 `tests/test_cli*.py` 中 init 断言
- 文档：`docs/{zh,en}/cli-reference.md`、`docs/{zh,en}/agent-protocol.md`、`builtin/skills/continue.md` 与 `.claude/skills/loopspec-continue/SKILL.md`

`docs/**`、`*.md`、`.claude/**` 在 Diff 排除列表中；代码改动落在 `src/**` 与 `tests/**`，由 be 的 Gate 覆盖。

## 安全边界

- hook 输入来自 Claude Code，但 `tool_input` 内容由模型生成，视为不可信：只做路径解析、文件读取与 YAML 解析，
  不执行命令、不把内容拼进 shell 或正则；`glob` 只在有效 cwd 下展开且限数量。
- 读取 plan.yaml 走 `parse_yaml`（禁止别名、重复键、深度/条目上限）并限制 2 MiB。
- 路径按 `realpath` 判定，符号链接与 `..` 不能绕过；无法判定时对受保护形状 fail closed，对无关路径放行，避免 hook 故障阻塞所有编辑。
- settings 写入只合并、不覆盖用户配置，拒绝写符号链接目标；不读取任何环境变量或密钥文件。
- 不引入新依赖。

## 验证方案

单元测试（pytest，`tmp_path` 构造 Change 与 Plan，直接调用判定函数并通过 CliRunner 调用 `hook pre-tool-use`）：

- 工具判定：Edit/MultiEdit/Write/NotebookEdit 对 approved → deny；draft/archived/request.yaml/state.md → allow；
  相对路径 + `cwd`、`..`、符号链接指向受保护文件 → deny。
- 伪造确认：Write 新建 approved 内容 → deny；Edit 把 draft 的 `status: draft` 改成 `status: approved` → deny；
  对 draft 的普通 Edit → allow。
- fail closed：受保护形状但内容非法 → deny；stdin 非 JSON / 非对象 / 未知工具 → allow 且退出码 0、无 stdout。
- Bash：`sed -i`、`echo x > p`、`echo x >> p`、`tee p`、`cp a p`、`mv a p`、`rm p`、
  `python3 -c "open('p','w')"`、`cd plans/001 && sed -i ... plan.yaml`、glob `plans/*/plan.yaml` 写入 → deny；
  `cat p`、`grep x p`、`cat p > /tmp/x`、`sed -n 1p p`、`git diff p`、`loopspec plan show ...` → allow；引号不配对的写入命令 → deny。
- Codex：`apply_patch` 的 Update/Add/Delete/Move 指向 approved plan.yaml → deny；Add 新建内容含 `status: approved` → deny；
  Update draft plan.yaml 普通改动 → allow；Update 其他文件 → allow；`Bash` 的数组形式 command → 按字符串判定。
- deny 输出结构与原因文本包含 `plan approve` 与 `plan archive`。
- hook 配置（Claude Code 与 Codex 各一组）：不存在 → created；已有其他键与其他 PreToolUse → updated 且保留；重复执行 → unchanged；
  非法 JSON / 符号链接 → skipped 且文件不变；`init --tools claude,codex --json` 结果含 `hooks.claude` 与 `hooks.codex`；未选的工具不写。
- 回归：`make test`、`make lint` 全绿。
- 端到端（QA）：用真实 CLI 在临时项目中 `init --tools claude`，构造 approved Plan，管道输入模拟 hook JSON 验证 deny/allow。

## 风险与取舍

- **白名单误拦**：不在白名单的只读命令（如 `awk`）会被拒绝；取舍为 fail closed，原因文本引导走 CLI 或用 `Read`。
- **漏拦**：变量拼接路径、脚本文件内写入无法识别；由 digest 校验兜底，文档写明。
- **备选方案**：
  - 文件权限设只读（chmod 444）：LLM 可 chmod 回来，且影响 CLI 原子替换，放弃。
  - 在 plan.yaml 中加入 HMAC 签名：密钥需存放在 LLM 不可读处，本地 CLI 场景无法保证，放弃。
- **Codex 信任**：项目级 hook 需用户在 Codex 中 `/hooks` 审阅信任，未信任时不运行；init 输出与文档提示该步骤。
- **Codex `apply_patch` 的条件 2 为近似判定**：只看新增行文本，不模拟补丁应用；digest 校验兜底。
- **hook 依赖 PATH 中的 `loopspec`**：未安装时 Claude Code 报非阻塞错误，保护失效；文档说明。
- **本仓库自身**：本次不自动修改仓库的 `.claude/settings.json` 与 `.codex/hooks.json`；实现后可由用户执行 `loopspec init --tools claude,codex` 启用。
