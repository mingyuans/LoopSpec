# CLI 参考

> 覆盖范围：全部命令与参数、JSON 输出约定与全部错误码。
> 适用读者：查命令的人与 Agent。
> 语言：**中文** · [English](../en/cli-reference.md)

## 约定

- 命令统一为 `loopspec <资源> <动作>`，资源名为单数：`change`、`plan`、`node`、`gate`、`fragment`、`profile`。只有 `version` 与 `init` 单独使用。
- `-c/--change` 指定 Change，`-p/--plan` 指定三位数字的 Plan 编号，`-n/--node` 指定叶子节点或 Gate 路径，`-f/--file` 指定相对工作区的请求文件，`--digest` 是人确认过的摘要，`--note` 是可选说明。`change` 组的命令以位置参数给出 Change 名。
- 除 `version` 与 `init` 外，所有命令都接受 `--home`（默认 `./loopspec`），并总是输出 JSON。失败时输出 `{"error": <错误码>, "message": <说明>, "fix": <下一步>}`，退出码为 1；用法错误退出码为 2。
- 执行类命令（`node`、`gate`、`plan rollback`）只作用于活动 Plan。没有活动 Plan 时返回 `plan_not_active`，`fix` 给出下一个规划步骤。每条命令只有一次生效写入，中断后 Change 要么是命令之前、要么是命令之后的状态；尚待归档的返工文件由下一条写入类命令先行搬运。

## loopspec version

打印已安装的版本号。`--json` 输出 `{"version": "..."}`。

## loopspec init

```bash
loopspec init [PATH] [--tools all|none|<ids>] [--project-root <dir>] [--json]
```

在 `PATH`（默认 `./loopspec`）创建工作区：`config.yaml`（`artifacts_dir: changes` 与空的 `workflow`）、`changes/`，以及内置的 `fragments/` 与 `profiles/`，只复制缺失的文件。`--tools` 为指定工具生成 Agent Skill 与 `/lpsx:*` 命令；不带时，交互式终端显示选择器，其他情况不配置任何工具。`--project-root` 指定工具目录的位置（默认工作区的上级目录）。默认输出人类可读摘要，带 `--json` 时输出 JSON。

## loopspec change new

```bash
loopspec change new <change>
```

创建一个未规划的 Change：`.workflow.yaml`（format 4，没有 Plan，没有基线）、`state.md` 与 `plans/`。不编译也没有可执行节点。对已有 Change 重复执行时返回它，并带 `reusedChange: true`。参数：`--home`。

## loopspec change status

```bash
loopspec change status <change>
```

返回 `status`（`unplanned`、`planning`、`active`、`complete`）、`baseline`、`repository`、`activePlan`、`openPlan`、全部 Plan 摘要，以及给出唯一下一条命令的 `nextSteps`。有活动 Plan 时还返回 `plan`、`revision`、`digest`、`nodes`（每个节点的 `status`、输出路径、证据过期时的 `reason`、失败时的 `gate` 详情、跟踪节点的 `taskProgress`）、`instances`（引用汇总）与 `pendingRollback`；为复核已有证据计算了 Diff 且存在被忽略、未排除的路径时，还返回 `warnings`。参数：`--home`。

## loopspec change next

```bash
loopspec change next <change>
```

与 `change status` 使用同一逻辑，只返回 `status`、`isComplete`、当前要处理的节点与 `nextSteps`。参数：`--home`。

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

按当前 Fragment 与 `config.yaml` 编译请求。没有未结束 Plan 时新建下一个编号的草稿 Plan，首次时固定 Change 基线与仓库；已有草稿时覆盖其 `spec`（给出 `--note` 时同时更新说明）；已有已确认 Plan 时返回 `plan_active`。参数：`--change`、`--file`、`--note`、`--home`。

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

只在人明确确认展示内容后执行。不带 `--file` 时确认草稿：重新编译草稿的 flow，要求存储摘要与重新编译摘要都等于 `--digest`，核对仓库，置 `revision: 1` 并设为活动 Plan。带 `--file` 时确认活动 Plan 的修订：重新编译请求，要求其摘要等于 `--digest`，检查 `base_revision` 与冻结规则，归档将重新执行节点的文件并替换 `spec`。重复提交已生效的确认返回 `alreadyApproved: true`。参数：`--change`、`--plan`、`--digest`、`--file`、`--home`。

## loopspec plan archive

```bash
loopspec plan archive -c <change> -p <NNN> [--note <text>]
```

把未结束的草稿或已确认 Plan 标记为 `archived` 并清空 Change 的指针，Change 回到 `unplanned`。Plan 目录与业务代码保持原样。归档已确认 Plan 前必须先取得人的明确同意。参数：`--change`、`--plan`、`--note`、`--home`。

## loopspec plan rollback

```bash
loopspec plan rollback -c <change> -p <NNN>
```

活动 Plan 中有有效 FAIL 时，按该 Gate 自身的 `on_fail` 返工：把其 `reset` 节点、该 Gate 与全部下游的产物、报告与证据归档到 `.attempts/<NNN>/`（`kind: rollback`）。业务代码不回退。Gate 没有 `on_fail` 或次数用完时返回 `retries_exhausted`，没有失败时返回 `no_failed_gate`。参数：`--change`、`--plan`、`--home`。

## loopspec node instructions

```bash
loopspec node instructions -c <change> -n <node>
```

返回执行活动 Plan 中一个就绪（或已完成）叶子节点所需的一切：实时读取的 `instruction`、`template` 或 Gate `templates`，`outputPath` 与 `resolvedOutputPath`，`dependencies`，以及 `priorAttempts`（以前的重做记录与 FAIL 报告，标注为不可信）。代码 Gate 额外返回含 `gate begin` 与 `gate record` 命令的 `gateProtocol`；保障节点返回它的 `gate record` 命令。它持有 Change 写锁，先补完已生效重做记录中待归档的文件，保证新产物不会覆盖尚未归档的文件。参数：`--change`、`--node`、`--home`。

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
| `profile_exists` | `profile save` 会覆盖已有 Profile。 |
| `archive_unsafe` | Change 未完成；完成它，或在明确要求时使用 `--force`。 |
| `archive_conflict` | 归档目标已存在。 |
| `baseline_required` | 代码 Gate 或保障需要 Git 仓库与固定基线。 |
| `invalid_baseline` | 基线不是完整 Commit 哈希。 |
| `repository_changed` | Git 仓库不是 Change 固定的仓库。 |
| `git_input_error` | Git 输出无法安全解析。 |
| `unsupported_input` | Diff 中有不支持的路径、模式、子模块或冲突。 |
| `index_worktree_mismatch` | 暂存区与工作树内容不一致；先决定交付哪个版本。 |
| `concurrent_input_change` | 读取代码期间代码发生变化。 |
| `concurrent_source_change` | 读取期间文件发生变化。 |
| `concurrent_path_change` | 操作期间目录被替换。 |
| `concurrent_write` | 另一条命令持有该 Change 的写锁。 |
| `registry_not_configured` | `config.yaml` 没有配置 `registry`。 |
| `registry_unavailable` | 未安装 `git` 或它不在 `PATH` 中。 |
| `registry_fetch_failed` | `ls-remote` 或拉取失败、超时、tag 不存在，或 registry 在预检与拉取之间发生变化。 |
| `registry_invalid` | registry 树无法读取、`path` 不存在，或超过大小与数量限额。 |
| `registry_plan_stale` | 没有当前计划、计划 ID 不一致，或 `registry update` 之后暂存文件或本地文件被修改。 |
| `registry_conflict_unresolved` | 有冲突没有 `--resolve`。 |
