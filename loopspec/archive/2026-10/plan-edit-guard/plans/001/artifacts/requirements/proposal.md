## 背景

Plan 经人确认（`plan approve`）后，执行阶段的 LLM 仍可以用编辑类工具直接改写
`changes/<change>/plans/<NNN>/plan.yaml`，从而改变节点图、Gate、on_fail，绕过人对 digest 的确认。

现状（2026-10-11 核查）：

- `workflow_state.read_plan` 在读取时校验 `spec_digest(spec) == meta.digest`，但 digest 是 spec 的 SHA-256，
  LLM 可以连同 `meta.digest` 一起改写，校验即可通过；也可以把 `meta.status` 改回 `draft` 再自行 approve。
- `continue` skill 只有一句"Never hand-edit `plan.yaml`"，属于软约束。
- 合法的变更通道已存在且保留：经人确认的修订 `plan approve -f <revision> --digest`，或经人同意后
  `plan archive` 再重新 `plan create`。CLI 写入 plan.yaml 不受影响。

## 用户场景

1. 执行中的 LLM 想直接 `Edit` 已确认 Plan 的 plan.yaml（例如删掉一个 Gate）：工具调用被拒绝，
   LLM 收到原因与正确做法（CLI 修订需人确认，或归档后重新起 Plan）。
2. LLM 用 Bash（`sed -i`、重定向、`tee`、`mv`/`cp` 覆盖等）改写该文件：同样被拒绝。
3. LLM 读取 plan.yaml（`Read`、`cat`）或运行 `loopspec plan ...` 命令：不受影响。
4. 草稿 Plan、已归档 Plan 的 plan.yaml、request.yaml、state.md、artifacts：不受影响。
5. 用户执行 `loopspec init --tools claude`：hook 配置被合并进项目 `.claude/settings.json`，
   已有设置保留，重复执行不产生重复条目。

## 范围

**A. `loopspec hook pre-tool-use` 子命令**

- 从 stdin 读取 Claude Code PreToolUse hook 的 JSON（`tool_name`、`tool_input`、`cwd`）。
- 判定"受保护文件"：路径形如 `<change-root>/plans/<NNN>/plan.yaml`，`<change-root>/.workflow.yaml` 存在，
  且该 plan.yaml 当前 `meta.status == approved`。
- 覆盖工具：`Edit`、`MultiEdit`、`Write`（`file_path`）、`NotebookEdit`（`notebook_path`）；
  `Bash`（`command` 中出现指向受保护文件的路径，且含写入特征）。
- 命中时输出 PreToolUse 的 deny 决定，原因说明：已确认的 Plan 不能直接编辑；需要调整时走经人确认的
  `plan validate` + `plan approve -f` 修订，流程不再适用时经人同意 `plan archive` 后重新 `plan create`。
- 未命中、输入不是合法 hook JSON、或与 LoopSpec 无关的调用：静默放行（退出码 0，无输出）。

**B. `loopspec init` 写入 Claude Code hook 配置**

- 选中 `claude` 工具时，把 PreToolUse hook 合并进 `<project-root>/.claude/settings.json`；
  不存在则创建；已存在同一命令的条目则不重复添加；文件不是合法 JSON 对象时不覆盖，给出提示。

**B2. Codex 支持**

- 同一个 `loopspec hook pre-tool-use` 处理 Codex 的 `apply_patch`（补丁头中的文件路径）与 `Bash`。
- `loopspec init` 选中 `codex` 时把同结构的 hook 合并进 `<project-root>/.codex/hooks.json`，并提示用户在 Codex 中用 `/hooks` 信任。

**C. 文档与 skill**

- zh/en `cli-reference.md` 增加 `hook pre-tool-use` 说明；`agent-protocol.md` / `overview.md` 说明保护机制。
- `continue` skill 的现有禁止手改说明补充：被 hook 拒绝时按提示走 CLI，不得绕过。

## 非目标

- 不限制 CLI 写入 plan.yaml；不移除修订通道。
- 不保护 request.yaml、`.workflow.yaml`、`.gates/`、`.gate-rounds/`、`.attempts/`、state.md、artifacts/。
- 不为 Claude Code、Codex 以外的 AI 工具提供 hook。
- Bash 检测是启发式的护栏，不承诺拦截所有间接写法（如脚本内拼接路径）；不是安全边界。

## 验收条件

- [ ] Edit/MultiEdit/Write 指向 approved Plan 的 plan.yaml（绝对路径或相对 `cwd`）时，hook 输出
      `permissionDecision: deny`，原因含 `plan validate`/`plan approve -f` 与 `plan archive` 指引。
- [ ] 同样的调用指向 draft 或 archived Plan 的 plan.yaml、request.yaml、state.md 时放行。
- [ ] NotebookEdit 的 `notebook_path` 指向受保护文件时拒绝。
- [ ] Bash 命令 `sed -i ... plan.yaml`、`echo x > plan.yaml`、`tee`、`mv`/`cp` 覆盖受保护文件时拒绝；
      `cat`/`grep` 读取、`loopspec plan ...` 命令放行。
- [ ] 通过符号链接或 `..` 指向受保护文件的路径按解析后的真实路径判定。
- [ ] Write 新建 plan.yaml 且内容的 `meta.status` 为 approved 时拒绝（防止伪造已确认 Plan）。
- [ ] plan.yaml 存在但无法解析时按受保护处理（fail closed）；stdin 不是合法 JSON 时放行且退出码 0。
- [ ] `loopspec init --tools claude` 创建或合并 `.claude/settings.json`，保留已有键与已有 hooks；
      重复执行不产生重复条目；非法 JSON 不被覆盖并在结果中报告。
- [ ] Codex `apply_patch` 的 Add/Update/Delete/Move 指向 approved plan.yaml 时拒绝；Add 新建 approved 内容时拒绝。
- [ ] `loopspec init --tools codex` 创建或合并 `.codex/hooks.json`，规则同 Claude Code。
- [ ] 通过 CLI 的 `plan approve -f` 修订与 `plan archive` 行为不变，既有测试全部通过。
- [ ] `make test` 与 `make lint` 通过。

## 风险

- **误拦**：Bash 启发式可能拒绝只读但含 `>` 的命令（例如 `cat plan.yaml > /tmp/x`）。应对：只检查写入目标位置
  （重定向目标、`-i` 编辑、`tee`/`mv`/`cp`/`rm` 的参数），读取方向不拦；误拦时提示走 CLI，代价可接受。
- **漏拦**：间接写法（脚本、变量拼接）无法识别；由 `read_plan` 的 digest 校验作为第二道防线，文档写明局限。
- **hook 不可用**：`loopspec` 不在 PATH 时 hook 报非阻塞错误，相当于未启用；文档说明。
- **覆盖用户配置**：settings.json 只做合并，非法 JSON 不覆盖；写入使用原子替换。
- **性能**：hook 对每次匹配工具调用启动一次 Python 进程；只在路径含 `plan.yaml` 时才读文件。
