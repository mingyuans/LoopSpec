# CLI 参考

> 覆盖范围：全部命令与参数、JSON 输出约定与全部错误码。
> 适用读者：查命令的人与 Agent。
> 语言：**中文** · [English](../en/cli-reference.md)

## 约定

- 命令统一为 `loopspec <资源> <动作>`，资源名为单数：`change`、`plan`、`node`、`gate`、`state`、`fragment`、`profile`。只有 `version`、`update` 与 `init` 单独使用；`hook` 组供 AI 工具的 hook 调用。
- `-c/--change` 指定 Change，`-p/--plan` 指定三位数字的 Plan 编号，`-n/--node` 指定叶子节点或 Gate 路径，`-f/--file` 指定相对工作区的请求文件，`--digest` 是人确认过的摘要，`--note` 是可选说明。`change` 组的命令以位置参数给出 Change 名。
- 除 `version`、`update`、`init` 与 `hook` 外，所有命令都接受 `--home`（默认 `./loopspec`），并输出 JSON；唯一例外是 `change status`，默认输出给 LLM 阅读的纯文本报告，带 `--json` 时才输出 JSON。失败时输出 `{"error": <错误码>, "message": <说明>, "fix": <下一步>}`，退出码为 1；用法错误退出码为 2。
- 执行类命令（`node`、`gate`、`plan rollback`）只作用于活动 Plan。没有活动 Plan 时返回 `plan_not_active`，`fix` 给出下一个规划步骤。每条命令只有一次生效写入，中断后 Change 要么是命令之前、要么是命令之后的状态；尚待归档的返工文件由下一条写入类命令先行搬运。

## loopspec version

打印已安装的版本号。`--json` 输出 `{"version": "..."}`。

## loopspec update

```bash
loopspec update [--version <X.Y.Z|X.Y.Z-beta>] [--beta] [--check] [--json]
```

升级 loopspec CLI 本身，做法与 `install.sh` 相同。目标 Release 取决于参数。默认只跟踪正式版：下载最新 Release 的 `checksums.txt`（`https://github.com/mingyuans/LoopSpec/releases/latest/download/checksums.txt`），从其中的 wheel 行读出版本。带 `--beta` 时也考虑 beta：从仓库的 `https://github.com/mingyuans/LoopSpec/releases.atom` 订阅源读取 tag，忽略不是 `vX.Y.Z` 或 `vX.Y.Z-beta` 的 tag，取其中最高的版本，无论是 beta 还是正式版；若该 tag 的 Release 返回 HTTP 404（尚未发布），按版本从高到低最多尝试 3 个 tag，其他任何失败都会直接中止；订阅源只列出最近的 Release，且从不调用 `api.github.com`。带 `--version` 时恰好以该版本为目标，接受 `X.Y.Z`、`X.Y.Z-beta` 或包版本形式 `X.Y.Zb0`，beta 映射为 `vX.Y.Z-beta` tag。`--beta` 与 `--version` 不能同时使用（`update_invalid_version`）。确定 tag 后，下载该 tag 的 `checksums.txt`，并要求其中的版本与 tag 一致。不带 `--version` 时按版本顺序比较，beta（`1.1.4b0`）排在对应正式版（`1.1.4`）之前，只有目标版本比已安装版本新时才安装，因此永不降级：已安装的 beta 比最新正式版新时保持不变，直到更新的正式版发布。`--version` 总是安装指定版本，即使与已安装版本相同，也可用于回退到旧版本。安装时从该 Release 的 tag（`v1.2.0`，包版本 `1.1.4b0` 则为 `v1.1.4-beta`）下载 wheel，要求 `checksums.txt` 中恰好一行精确命名该文件且 SHA256 一致，然后用 `uv tool install --force`（没有 uv 时用 `pipx install --force`）安装已校验的本地文件；没有跳过校验的选项。`--check` 只报告是否有新版本，不下载 wheel，可与 `--beta` 组合。版本号无论来自参数、订阅源还是 `checksums.txt`，都必须先通过版本校验才会被使用。下载只走 https（包括重定向），30 秒超时，`checksums.txt` 上限 64 KiB、订阅源上限 512 KiB、wheel 上限 50 MiB；安装器不经过 shell 执行。与 `install.sh` 一样，校验能防下载损坏或被替换，不能防 Release 本身被攻破。默认输出一行人类可读文本；带 `--json` 时输出 `{"status", "current", "latest", "installer"}`，`status` 为 `up_to_date`、`available`（`--check` 时）或 `updated`，`installer` 为 `uv`、`pipx`，未安装时为 `null`，此时安装器自身的输出写到 stderr。参数：`--version`、`--beta`、`--check`、`--json`。

## loopspec init

```bash
loopspec init [PATH] [--tools all|none|<ids>] [--project-root <dir>] [--update-resources] [--json]
```

在 `PATH`（默认 `./loopspec`）创建工作区：`config.yaml`（`artifacts_dir: changes` 与空的 `workflow`）、`changes/`，以及内置的 `fragments/` 与 `profiles/`，只复制缺失的文件。`fragments/` 或 `profiles/` 中已有内容时，未经同意不改动两者：交互式终端询问 `[y/N]`（只有 `y` 或 `yes` 才复制），`--json` 与非交互运行不询问直接跳过；`--update-resources` 不询问直接复制。Skill、命令与 hook 照常刷新。`--tools` 为指定工具生成 Agent Skill 与 `/lpsx:*` 命令；不带时，交互式终端显示选择器，其他情况不配置任何工具。`--project-root` 指定工具目录的位置（默认工作区的上级目录）。选中 `claude` 或 `codex` 时，还会把 `loopspec hook pre-tool-use` 作为 PreToolUse hook 合并进项目级配置：Claude Code 为 `.claude/settings.json`（matcher `Edit|MultiEdit|Write|NotebookEdit|Bash`），Codex 为 `.codex/hooks.json`（matcher `^apply_patch$|^Bash$`）。只合并、不覆盖：保留已有键与 hook，已有同一命令时不重复添加；文件不是普通文件、不是合法 JSON 或 `hooks` 结构不对时不写入。Codex 的项目级 hook 需要在 Codex 中用 `/hooks` 审阅并信任后才运行。默认输出人类可读摘要，带 `--json` 时输出 JSON，其中 `resourcesUpdate` 为 `installed` 或 `skipped`，`hooks` 按工具给出 `{path, status, reason?}`，`status` 为 `created`、`updated`、`unchanged` 或 `skipped`。 同时创建空的 `memory/` 目录，用于存放跨 Change 的 memory topic；不触碰已有 topic，也不会创建任何 topic。

## loopspec hook pre-tool-use

```bash
loopspec hook pre-tool-use < <hook 输入 JSON>
```

Claude Code 与 Codex 的 PreToolUse hook，由 `loopspec init` 配置，不需要手动执行。从 stdin 读取 hook 输入（`tool_name`、`tool_input`、`cwd`），拒绝 LLM 直接改写已确认 Plan 的 `plan.yaml`：

- 受保护文件：解析符号链接与 `..` 后形如 `<Change>/plans/<NNN>/plan.yaml`、Change 根目录有 `.workflow.yaml`，且当前 `meta.status` 为 `approved`。
- `Edit`、`MultiEdit`、`Write`、`NotebookEdit` 写受保护文件时拒绝；写入结果的 `meta.status` 为 `approved`（例如新建 approved 的 plan.yaml，或把草稿改成 approved）时也拒绝。
- Codex 的 `apply_patch`：补丁中 Add、Update、Delete、Move 涉及受保护文件时拒绝；新增行把 plan.yaml 写成 `status: approved` 时拒绝。
- `Bash`：受保护文件是重定向目标，或出现在只读命令（`cat`、`grep`、`head`、`git diff/log/show`、不带 `-i` 的 `yq`、`loopspec` 等；`sed` 不算只读，`git --output`、`rg --pre` 也不算）以外的命令中时拒绝；跟踪 `cd`，展开通配符（包括不含 `plan.yaml` 字样的 `pl?n.yaml`、`*`），引号不配对时按出现的路径处理。这是启发式护栏，不是安全边界；`plan.yaml` 的摘要校验仍是第二道防线。

拒绝时在 stdout 输出 `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": ...}}`，原因指向 `plan validate` + `plan approve -f` 修订，或经人同意后 `plan archive` 再重新规划。其他情况不输出、退出码 0；输入不是合法 JSON 或不是受保护的工具时放行。原则是能检测到就拒绝，检测不了就放行，不影响正常工具调用：输入超过 64 MiB、分析超过 10 秒、分析出错，或 plan.yaml 无法读取或解析时都放行；`bash -c` 嵌套超过 8 层的部分不再展开，其余部分照常检查。草稿与已归档 Plan、`request.yaml`、`state.md`、产物不受限制，CLI 自身写入 `plan.yaml` 不经过 hook。没有参数。

## loopspec change new

```bash
loopspec change new <change>
```

创建一个未规划的 Change：`.workflow.yaml`（format 4，没有 Plan，没有基线）、带分段模板的 `state.md`（背景、目标与边界、决策、待解决问题、参考，末尾是引擎追加的 Plan 记录）与 `plans/`。不编译也没有可执行节点。对已有 Change 重复执行时返回它，并带 `reusedChange: true`。参数：`--home`。

## loopspec change status

```bash
loopspec change status <change> [--json]
```

默认输出纯文本报告，供 LLM 直接阅读：以顶格的 `=== SECTION ===` 行分节，不使用 Markdown，不含颜色，字节不随终端变化。节序固定为 `OVERVIEW`、`STATE RECORDS`、`MEMORY`、`PLANS`、`NODES`（有活动 Plan 时）、`GATE FAILURES`（有失败 Gate 时）、`PENDING ROLLBACK`（有待返工时）、`NEXT STEPS`，每节先有一段说明。`STATE RECORDS` 原样引用 Change 级与当前 Plan（活动 Plan，规划中为草稿）的 `state.md`，每行缩进四个空格，标明为不可信数据；已归档 Plan 的 `state.md` 不输出，但 `PLANS` 仍列出全部 Plan。失败时输出 `=== ERROR ===` 报告，退出码为 1。 `MEMORY` 引用 `memory/core.md` 并列出其他 topic 的索引，标明为不可信参考数据：core 按完整的 `## ` 条目引用，最多 8 KiB（放不下的条目整条略去，不会截成半条），core 被截断时明确提示用 `loopspec memory show core` 读完其余部分；最多列出 20 个 topic（路径、适用说明、大小），更多时给出 `loopspec memory list --offset` 的入口；没有任何 memory 时输出 `(no memory)`。`--json` 在 `memory` 下给出同样的数据。

带 `--json` 时返回 `status`（`unplanned`、`planning`、`active`、`complete`）、`baseline`、`repository`、`activePlan`、`openPlan`、全部 Plan 摘要，列出全部可执行下一条命令的 `nextSteps`，以及 `parallel`：`nextSteps` 含两条及以上可并行的独立 `node instructions` 命令时为 `true`，否则为 `false`。有活动 Plan 时还返回 `plan`、`revision`、`digest`、`nodes`（每个节点的 `status`、输出路径、证据过期时的 `reason`、失败时的 `gate` 详情、跟踪节点的 `taskProgress`）、`instances`（引用汇总）与 `pendingRollback`；为复核已有证据计算了 Diff 且存在被忽略、未排除的路径时，还返回 `warnings`。四种状态都返回 `state`（Change 级 `state.md`）、`planState`（当前 Plan 的 `state.md` 及其 `plan` 编号，未规划时为 `null`）与 `untrustedData`（不可信声明）。`state` 与 `planState` 形如 `{path, content, truncated}`：文件不存在时 `content` 为 `null`；无法读取（符号链接、非普通文件）时另带 `error: "unreadable"`；超过 64 KiB 时保留首尾各 32 KiB 并置 `truncated: true`。参数：`--json`、`--home`。

## loopspec change next

```bash
loopspec change next <change>
```

与 `change status` 使用同一逻辑，只返回 `status`、`isComplete`、`node`（第一个要处理的节点）、`nodes`（`nextSteps` 对应的全部节点：rollback 的 Gate、exhausted 的 Gate，或全部就绪叶子）、`parallel` 与 `nextSteps`。参数：`--home`。

## loopspec change history

```bash
loopspec change history <change> [-p <NNN>]
```

列出活动 Plan（或未结束 Plan、最新 Plan，或 `--plan` 指定的 Plan）在 `.attempts/` 中的重做记录：`seq`、`kind`、`gate`、`reset`、归档的 `files`，修订记录还包括目标摘要与修订号。参数：`--plan`、`--home`。

## loopspec change artifacts

```bash
loopspec change artifacts <change>
```

按位置（当前 Change 与已归档副本）和 Plan（含已归档 Plan）列出 Change 拥有的全部产物。只读。参数：`--home`。

## loopspec change archive

```bash
loopspec change archive <change> [--force] [--dry-run]
loopspec change archive --all [--older-than <days>] [--dry-run]
```

把 Change 目录移到 `archive/<YYYY-MM>/<change>`。移动前重新推导状态，包括代码证据与保障；只归档 `complete` 的 Change。`--force` 用于人明确放弃时归档未完成的 Change，结果中 `forced: true` 并说明是未完成归档。`--dry-run` 只报告不移动。`--all` 归档全部 complete 的 Change，其余的附原因跳过；`--older-than` 只处理创建至少指定天数的 Change。`--all` 不能与 `--force` 或需求名同时使用。参数：`--all`、`--older-than`、`--force`、`--dry-run`、`--home`。

## loopspec plan validate

```bash
loopspec plan validate -c <change> -f <request>
```

只读。没有已确认 Plan 时编译请求并检查项目约束，返回 `spec` 与 `digest`。有已确认 Plan 时按修订处理：检查 `base_revision` 与冻结规则，返回新的 `digest`、`addedInstances` 与 `rerunNodes` 供展示给人。参数：`--change`、`--file`、`--home`。

## loopspec plan create

```bash
loopspec plan create -c <change> -f <request> [--note <text>]
```

按当前 Fragment 与 `config.yaml` 编译请求。没有未结束 Plan 时新建下一个编号的草稿 Plan，首次时固定 Change 基线与仓库；已有草稿时覆盖其 `spec`（给出 `--note` 时同时更新说明）；已有已确认 Plan 时返回 `plan_active`。新建草稿时写入带分段模板的 Plan 级 `state.md`；新建与覆盖草稿提交后向 Plan 级 `state.md` 末尾追加一行事件（见[概览](overview.md)）；追加失败不影响结果，只在输出中加 `warnings: ["state_append_failed: <路径>"]`。参数：`--change`、`--file`、`--note`、`--home`。

## loopspec plan show

```bash
loopspec plan show -c <change> [-p <NNN>]
```

返回未结束 Plan（或 `--plan` 指定的 Plan）的 `meta`、`spec`、`baseline` 与 `repository`，这是人在确认前评审的内容。参数：`--change`、`--plan`、`--home`。

## loopspec plan list

```bash
loopspec plan list -c <change>
```

列出全部 Plan 的编号、状态、修订号、说明与时间。参数：`--change`、`--home`。

## loopspec plan approve

```bash
loopspec plan approve -c <change> -p <NNN> --digest <digest>
loopspec plan approve -c <change> -p <NNN> -f <revision-request> --digest <digest>
```

只在人明确确认展示内容后执行。不带 `--file` 时确认草稿：重新编译草稿的 flow，要求存储摘要与重新编译摘要都等于 `--digest`，核对仓库，置 `revision: 1` 并设为活动 Plan。带 `--file` 时确认活动 Plan 的修订：重新编译请求，要求其摘要等于 `--digest`，检查 `base_revision` 与冻结规则，归档将重新执行节点的文件并替换 `spec`。重复提交已生效的确认返回 `alreadyApproved: true`，不追加事件。确认或修订生效后向 Plan 级 `state.md` 末尾追加一行事件（见[概览](overview.md)）；追加失败不影响结果，只在输出中加 `warnings: ["state_append_failed: <路径>"]`。参数：`--change`、`--plan`、`--digest`、`--file`、`--home`。

## loopspec plan archive

```bash
loopspec plan archive -c <change> -p <NNN> [--note <text>]
```

把未结束的草稿或已确认 Plan 标记为 `archived` 并清空 Change 的指针，Change 回到 `unplanned`。Plan 目录与业务代码保持原样。归档已确认 Plan 前必须先取得人的明确同意。提交后向 Plan 级与 Change 级 `state.md` 末尾各追加一行事件（见[概览](overview.md)）；追加失败不影响结果，只在输出中加 `warnings: ["state_append_failed: <路径>"]`。参数：`--change`、`--plan`、`--note`、`--home`。

## loopspec plan rollback

```bash
loopspec plan rollback -c <change> -p <NNN>
```

活动 Plan 中有有效 FAIL 时，按该 Gate 自身的 `on_fail` 返工：把其 `reset` 节点、该 Gate 与全部下游的产物、报告与证据归档到 `.attempts/<NNN>/`（`kind: rollback`）。业务代码不回退。Gate 没有 `on_fail` 或次数用完时返回 `retries_exhausted`，没有失败时返回 `no_failed_gate`。提交后向 Plan 级 `state.md` 末尾追加一行事件（见[概览](overview.md)）；追加失败不影响结果，只在输出中加 `warnings: ["state_append_failed: <路径>"]`。参数：`--change`、`--plan`、`--home`。

## loopspec node instructions

```bash
loopspec node instructions -c <change> -n <node>
```

返回执行活动 Plan 中一个就绪（或已完成）叶子节点所需的一切：实时读取的 `instruction`、`template` 或 Gate `templates`，`outputPath` 与 `resolvedOutputPath`，`dependencies`，以及 `priorAttempts`（以前的重做记录与 FAIL 报告，标注为不可信）。代码 Gate 额外返回含 `gate begin` 与 `gate record` 命令的 `gateProtocol`；保障节点返回它的 `gate record` 命令。每个叶子还会得到 `stateProtocol`：适合该节点的 `state add` 命令，与模板同源于同一张段落注册表，每项含 `when`、`contentBoundary`、`format`、`required`、`optional` 与 `command`。Change 级命令只带 Change；Plan 级命令固定实际的 Change、Plan 与节点；Gate 节点还会多出 `rework`。已生效重做记录中还有待归档的文件时，它先在 Change 写锁内补完搬运，保证新产物不会覆盖尚未归档的文件；否则只读，因此并行的 Agent 可以同时获取各自的节点。参数：`--change`、`--node`、`--home`。 另含 `memory`：与 `change status` 相同的有界 topic 摘要（`topics`、`total`、`omitted`、`listCommand`），其中 `core` 只有 `present`、`bytes` 与 `showCommand`，不含正文。

## loopspec gate begin

```bash
loopspec gate begin -c <change> -n <gate>
```

只用于就绪的代码 Gate。以基线为准固定其 `evidence.paths` 范围内的内容，返回一次性的 `roundId` 与范围内的文件（路径、类型与摘要，不含内容）。存在被 Git 忽略、但不在 `workflow.excluded_paths` 中的路径时，返回 `warnings`（`ignoredPaths` 最多 20 条与 `ignoredTotal`）；审查者应把这些告警写进报告摘要。参数：`--change`、`--node`、`--home`。

## loopspec gate record

```bash
loopspec gate record -c <change> -n <gate> --round <roundId> --report <artifacts/...>
loopspec gate record -c <change> -n <assurance-node>
```

代码 Gate 必须带 `--round` 与 `--report`。报告位于 Plan 的 `artifacts/` 下，头部只含 `verdict` 与 `summary`。轮次未被使用且固定的代码未变化时，写出 PASS 或 FAIL 报告与绑定 Plan 摘要的证据，并返回同样的 `warnings`。保障节点拒绝这两个参数：CLI 按保障规则检查完整 Diff，写出带诊断的系统 PASS 或 FAIL；告警不影响结论，会写进系统报告的 `summary` 与诊断的 `warnings`；保障规则的 `unknown_paths` 为 `warn` 时，不匹配任何规则的路径也作为告警写入。被忽略的文件从不计入 Diff 与证据摘要。参数：`--change`、`--node`、`--round`、`--report`、`--home`。

## loopspec state add

```bash
loopspec state add -c <change> --section <key> --text <content> [--scope change|plan] [-p <plan>] [-n <node>] [--actor HUMAN|MODEL --by <who>]
```

在 Change 写锁内，把一行单行记录追加到 Change 级或 Plan 级 `state.md` 的对应段落。这是唯一的 state 写操作：解决问题、替代决策、验证假设或更正记录，都通过追加一条引用旧记录的新记录来表达，不分配条目 ID。输出 `changeName`、`scope`、`plan`（Change 级为 `null`）、`section`、`path` 与追加的 `line`。参数：`--change`、`--section`、`--text`、`--scope`、`--plan`、`--node`、`--actor`、`--by`、`--home`。

| 段落 | 层级 | 必填 | 条目 |
| --- | --- | --- | --- |
| `background`、`goals`、`reference` | change | `--text` | `- YYYY-MM-DD 内容` |
| `decision` | change | `--text`、`--actor`、`--by` | `- YYYY-MM-DD [HUMAN: 谁] 内容` 或 `- YYYY-MM-DD [MODEL: Agent 角色] 内容` |
| `open-question` | change 或 plan | `--scope`、`--text` | `- YYYY-MM-DD 内容`；Plan 级带 `--node` 时为 `- YYYY-MM-DD [节点] 内容` |
| `assumption`、`deviation` | plan | `--text`、`--node` | `- YYYY-MM-DD [节点] 内容` |
| `rework` | plan | `--text`、`--node`（Gate） | `- YYYY-MM-DD [Gate] attempt N（rollback #S）：内容` |

- **层级与 Plan。**只存在于一层的段落不需要 `--scope`，显式给出时必须一致；`open-question` 两层都有，必须显式 `--scope`。Change 级记录拒绝 `-p` 与 `-n`。Plan 级记录使用 `-p`，省略时取当前 open Plan（draft 或 approved）；写记录不会批准或推进 Plan。已归档的 Plan 返回 `plan_archived`，不存在的返回 `plan_not_found`。
- **谁作出决策。**`--actor` 为 `HUMAN` 或 `MODEL`，`--by` 写实际作出决策的用户或 Agent 角色，而不是代写者。`decision` 两者都必填，其他段落传入则拒绝。该标签只是来源声明，不是经过校验的身份，也不是正式批准；不要猜测身份。
- **文本。**`--text` 与 `--by` 先折叠为单行（换行与控制字符被规范化），规范化后必须非空；`--text` 最多 1000 个字符，`--by` 最多 64 个。任何位置出现 `<!--` 或 `-->` 都会被拒绝。每条记录都写成 `- ` 开头的 bullet，因此标题之类的内容不会变成标题。非法输入返回 `workflow_invalid`，且不写任何内容。
- **节点。**`--node` 必须是所选 Plan 的叶子节点；`rework` 还要求它是 Gate。它只是数据，不会进入任何文件路径。
- **返工轮次。**`N` 是该 Gate 已提交的 rollback 次数，`S` 是它最新一次 rollback 的全局序号（即 `.attempts/` 目录号，也就是 `plan rollback` 返回的 `attempt`）。两者一般不相等，调用方不能传入任何一个；没有已提交 rollback 的 Gate 返回 `state_rework_no_rollback`。
- **安全追加。**命令完整读取文件（链接、特殊文件与超过 2 MiB 读取限额的文件会被拒绝），找到完整的 `## <标题>` 行，在该段最后一个非空行之后拼接原始字节插入，再原子回写。其余字节，包括 CRLF 换行、缺失的末尾换行与引擎写入的尾段，保持不变。文件或标题缺失返回 `state_section_missing`，标题重复返回 `state_section_ambiguous`；不会创建或猜测任何内容。
- **锁。**它与生命周期命令使用同一把写锁。锁被占用时返回 `concurrent_write` 且不写入，请原样重试同一条命令；CLI 自己不会重试，手工编辑也不受该锁保护。

## loopspec fragment list

列出工作区中的 Fragment。每个条目带 `registry` 字段：在 `registry.lock.yaml` 中有记录的定义为 `{syncedTag, syncedCommit}`，否则为 `null`（锁缺失或不合法时也为 `null`）。参数：`--home`。

## loopspec fragment show

`loopspec fragment show <name>` 返回一个 Fragment 定义。参数：`--home`。

## loopspec fragment validate

`loopspec fragment validate <name>` 展开 Fragment 并检查依赖、资源、输出与 `on_fail`（含 `on_fail_conflict`）。参数：`--home`。

## loopspec profile list

列出工作区中的 Profile。每个条目带 `registry` 字段：在 `registry.lock.yaml` 中有记录的定义为 `{syncedTag, syncedCommit}`，否则为 `null`（锁缺失或不合法时也为 `null`）。参数：`--home`。

## loopspec profile show

`loopspec profile show <name>` 返回一个 Profile。参数：`--home`。

## loopspec profile validate

`loopspec profile validate <name>` 编译其 flow，返回构建顺序、实例与每个 Gate 最终的 `on_fail`。参数：`--home`。

## loopspec profile save

```bash
loopspec profile save <name> -c <change>
```

把活动 Plan 的 `spec.flow`（含 `on_fail`）保存为 `profiles/<name>.yaml`。不保存执行状态，从不覆盖已有 Profile。参数：`--change`、`--home`。

## loopspec registry update

```bash
loopspec registry update [--full]
```

按 `config.yaml` 的 `registry` 规划 `fragments/` 与 `profiles/` 的同步，只写 `<home>/.cache/registry/`。先用 `git ls-remote` 解析目标（`latest` 或固定 tag）：该 commit 与锁一致且没有落后的定义时，直接返回 `upToDate: true` 而不拉取；固定 tag 且已同步时完全不执行 git。否则把该 commit 拉取到私有裸仓库（从不 checkout），以锁为基线比对 registry 中的全部定义与本地副本，并暂存上游与基线内容供审阅。每个文件得到一个 `status`：`upstream-added`、`upstream-modified`、`upstream-deleted`（待确认）、`conflict`（必须解决）、`local-modified`、`local-deleted`、`local-only`（保持原样）。符号链接与子模块列入 `unsupported`，永不写入。返回 `registry`、`upToDate`、`baseCommit`、`baseTag`、`upstreamCommit`、`upstreamTag`、`baseAvailable`、`planId`、`definitions`（每项含 `kind`、`name`、`deletedUpstream`、`baseTag`、`baseCommit`、`upstreamTag`、`upstreamCommit`）、`files`（每项含 `path`、`status`、`localPath`、`upstreamPath`、`basePath`）、`unsupported`、`warnings` 与 `nextSteps`。`--full` 跳过版本预检，总是比对。需要 `PATH` 中有 `git`。参数：`--full`、`--home`。

## loopspec registry apply

```bash
loopspec registry apply --plan <planId> [--resolve <path>=local|upstream]... [--skip <path>]...
```

在人确认后写入最近一次 `registry update` 的计划。每个 `conflict` 必须恰好有一个 `--resolve`：`local` 保留当前本地文件（包括确认后写入的合并结果），`upstream` 采用 registry 版本。`--skip` 跳过一项待确认变更，其基线与所属定义的版本保持不变，下次仍会出现。计划不是最新、暂存内容被改动或计划生成后本地文件被修改时，返回 `registry_plan_stale`。结果先在预览目录中构建并加载，任何 Fragment 或 Profile 校验失败都会在写入前终止命令。随后原子写入文件，删除只删除计划列出的文件，并更新 `registry.lock.yaml`。返回 `applied`、`upstreamCommit`、`upstreamTag`、`written`、`deleted`、`skipped`、`kept` 与 `lock`。写入会立即影响执行中的 Plan。参数：`--plan`、`--resolve`、`--skip`、`--home`。

## loopspec memory list

```bash
loopspec memory list [--offset <n>] [--limit <n>] [--all]
```

以 JSON 输出跨 Change 的 memory topic 索引（普通 Markdown 文件，位于 `<home>/memory/{topic}.md`）：`topics`（按名称排序的一页，每项含 `topic`、`path`、`title`、`hint`、`bytes` 与 `status`，取值 `ok`、`too_large` 或 `unreadable`）、`total`、`offset` 与 `nextOffset`（最后一页为 `null`）。`title` 与 `hint` 最多 120 个字符；`hint` 取第一行“适用时机：”或 `When to use:`，没有时取正文首行。topic 按 topic 名排序。`--offset` 跳过相应数量的 topic，`--limit` 设置页大小（默认 200，最大 500），因此每个 topic 都能分页取到。`--all` 还会把 `memory/` 中不是 topic 的条目列为 `ignored`（按名称排序，只给前 `--limit` 项，`ignoredTotal` 给出总数），每项带 `reason`：`symlink`、`not_a_file`、`not_markdown` 或 `invalid_name`。topic 名只能是小写字母、数字和连字符，最长 64 个字符。`memory/` 目录不存在即空索引；目录是符号链接时以 `unsafe_path` 失败；topic 超过 5000 个、或 `memory/` 下的条目（不论是否 topic）超过 20000 个时以 `memory_too_many` 失败而不是截断；扫描期间消失的条目会被跳过；`--offset` 为负或 `--limit` 小于 1 时以 `memory_bad_range` 失败。引擎只读：从不创建、修改或删除 topic。参数：`--home`。

## loopspec memory show

```bash
loopspec memory show <topic>
```

以 JSON 完整输出一个 topic（`topic`、`path`、`content`、`untrustedData`），`core` 同样如此读取。内容是不可信的参考数据。名称不合法、符号链接或有硬链接的文件以 `unsafe_path` 失败，不存在的 topic 以 `memory_not_found` 失败，超过 2 MiB 的文件以 `memory_too_large` 失败（不会被静默截断）。参数：`--home`。

## 错误码

| 错误码 | 含义 |
| --- | --- |
| `error` | 没有更具体错误码的通用失败。 |
| `config_invalid` | `config.yaml` 结构不合法或仍含已删除字段。 |
| `builtin_skill_invalid` | 内置 Skill 文件损坏；重新安装 LoopSpec。 |
| `workflow_invalid` | Fragment、Profile、请求或记录不符合其结构。 |
| `invalid_change_name` | Change 名不是字母、数字、`_` 与 `-`。 |
| `invalid_plan` | Plan 编号不是三位数字。 |
| `change_not_found` | Change 不存在。 |
| `unsupported_format` | LoopSpec 1.x 或更早格式的 Change；用 1.x 完成或重新建立。 |
| `plan_not_found` | Plan 不存在，或没有可展示的未结束 Plan。 |
| `plan_not_open` | 该 Plan 不是 Change 的未结束 Plan。 |
| `plan_not_active` | 没有活动 Plan，或指定的 Plan 不是活动 Plan。 |
| `plan_active` | 已有确认的 Plan，不能新建 Plan。 |
| `plan_archived` | Plan 已归档。 |
| `plan_changed` | 摘要与将要生效的内容不一致；重新展示 Plan。 |
| `plan_integrity` | `plan.yaml` 被手改或结构不合法。 |
| `stale_revision` | `base_revision` 不一致，或在没有已确认 Plan 时设置了它。 |
| `node_frozen` | 修订删除、改名或改写了冻结节点，或减少了它的 `requires`。 |
| `failure_pending` | 修订使有效 FAIL 落在重新执行范围之外。 |
| `project_constraint` | Plan 缺少必需的 Fragment 或必需的保障节点。 |
| `history_integrity` | 重做记录或归档文件不一致；需要人检查 `.attempts/`。 |
| `no_failed_gate` | 没有需要返工的失败。 |
| `retries_exhausted` | 失败的 Gate 没有 `on_fail` 或次数已用完。 |
| `node_not_found` | 该节点不是活动 Plan 的叶子。 |
| `node_not_ready` | 节点未就绪；按 `nextSteps` 推进。 |
| `reference_not_executable` | 指定的是引用节点；请执行其叶子。 |
| `not_code_gate` | 对不带 `evidence` 的节点执行 `gate begin` 或 `gate record`。 |
| `option_required` | 记录代码 Gate 时缺少 `--round` 与 `--report`。 |
| `option_conflict` | 参数不能同时使用。 |
| `round_stale` | 审查轮次已使用、不存在或属于其他输入。 |
| `review_input_changed` | 审查期间固定的代码发生变化；重新 begin。 |
| `invalid_verdict` | 报告头部不是恰好 `verdict` 与 `summary`，或为空。 |
| `verdict_conflict` | 同一 Gate 同时有 PASS 与 FAIL 报告。 |
| `unsafe_report` | 报告不在活动 Plan 的 `artifacts/` 内。 |
| `assurance_missing` | 保障节点没有配置保障规则。 |
| `invalid_assurance` | 保障节点缺失、重复，或没有位于所有分支与代码审查之后。 |
| `rule_conflict` | 两条保障规则同名但内容不同。 |
| `on_fail_conflict` | 同一 Gate 将收到两条 `on_fail` 策略。 |
| `invalid_reset` | `on_fail` 目标不是其覆盖 Gate 的上游。 |
| `invalid_tracks` | `tracks` 指向的不是同一实例的上游产物。 |
| `missing_dependency` | `requires` 指向不存在的节点或实例。 |
| `dependency_cycle` | 依赖图存在环。 |
| `fragment_cycle` | Fragment 之间循环引用。 |
| `duplicate_instance` | 两个实例 id 相同。 |
| `output_conflict` | 两个输出路径重叠。 |
| `unsafe_output` | 输出指向控制路径。 |
| `unsafe_path` | 路径为绝对路径、越出根目录，或是链接或特殊文件。 |
| `resource_limit` | 超过大小、深度或数量限制。 |
| `memory_not_found` | 没有该名称的 memory topic。 |
| `memory_too_large` | memory topic 超过读取上限（2 MiB）。 |
| `memory_too_many` | `memory/` 下的 topic 超过 5000 个或条目超过 20000 个；请整理并合并。 |
| `memory_bad_range` | `--offset` 为负或 `--limit` 小于 1。 |
| `profile_exists` | `profile save` 会覆盖已有 Profile。 |
| `archive_unsafe` | Change 未完成；完成它，或在明确要求时使用 `--force`。 |
| `archive_conflict` | 归档目标已存在。 |
| `baseline_required` | 代码 Gate 或保障需要 Git 仓库与固定基线。 |
| `invalid_baseline` | 基线不是完整 Commit 哈希。 |
| `repository_changed` | Git 仓库不是 Change 固定的仓库。 |
| `git_input_error` | Git 输出无法安全解析。 |
| `unsupported_input` | Diff 中有不支持的路径、模式、子模块或冲突。 |
| `index_worktree_mismatch` | 暂存区内容既不是 HEAD 中的版本也不是工作树内容（部分暂存）；先决定交付哪个版本。 |
| `concurrent_input_change` | 读取代码期间代码发生变化。 |
| `concurrent_source_change` | 读取期间文件发生变化。 |
| `concurrent_path_change` | 操作期间目录被替换。 |
| `concurrent_write` | 另一条命令持有该 Change 的写锁；没有写入任何内容，原样重试即可。 |
| `state_section_missing` | `state add` 找不到 `state.md` 或对应标题；没有写入也没有猜测。 |
| `state_section_ambiguous` | 该标题在 `state.md` 中出现了多次；需要人工合并段落。 |
| `state_rework_no_rollback` | 对没有已提交 rollback 的 Gate 执行 `state add --section rework`。 |
| `registry_not_configured` | `config.yaml` 没有配置 `registry`。 |
| `registry_unavailable` | 未安装 `git` 或它不在 `PATH` 中。 |
| `registry_fetch_failed` | `ls-remote` 或拉取失败、超时、tag 不存在，或 registry 在预检与拉取之间发生变化。 |
| `registry_invalid` | registry 树无法读取、`path` 不存在，或超过大小与数量限额。 |
| `registry_plan_stale` | 没有当前计划、计划 ID 不一致，或 `registry update` 之后暂存文件或本地文件被修改。 |
| `registry_conflict_unresolved` | 有冲突没有 `--resolve`。 |
| `update_invalid_version` | `update` 收到或读到的版本号不是合法的 Release 版本，或 `--beta` 与 `--version` 同时使用。 |
| `update_fetch_failed` | `update` 无法下载 Release 文件：网络错误、超时、超过大小上限、非 https 地址，`checksums.txt` 中没有 wheel，或（带 `--beta` 时）`releases.atom` 订阅源中没有合法的 Release tag。 |
| `update_verify_failed` | wheel 在 `checksums.txt` 中不是恰好一行，SHA256 不一致，或某个 tag 的 `checksums.txt` 中的版本与 tag 不符；未安装任何内容。 |
| `update_installer_missing` | `PATH` 中既没有 `uv` 也没有 `pipx`。 |
| `update_install_failed` | 安装器以非零状态退出。 |
