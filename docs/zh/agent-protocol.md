# Agent 协议

> 覆盖范围：LLM agent 把一个 change 推进到完成所要运行的确切循环、每一步该读哪个响应字段，以及四种最容易搞错的行为。
> 适用读者：驱动 LoopSpec 的 LLM agent，以及编写驱动提示词的人类。
> 语言：[English](../en/agent-protocol.md) · **中文**

始终传 `--json`——只有一个例外：`loopspec status`，它的默认输出已经是给 agent 读的报告（只有需要精确字段取值时才加 `--json`）。始终读 `nextSteps`。永远不要从文件名或对前一轮的记忆去推断下一步——文件系统才是事实来源，而且它可能已经变了。

## 主循环

```text
loopspec status <change>
        |
        v
read nextSteps  ---> names exactly one command to run
        |
        v
loopspec instructions <node> --change <change> --json
        |
        v
do what `instruction` says, write to `resolvedOutputPath`, update state.md
        |
        +--------> back to status
```

| 步骤 | 命令 | 要读的字段 | 拿它做什么 |
| --- | --- | --- | --- |
| 1 | `loopspec status <change>` | `nextSteps` | 指名恰好一条命令。执行它。不要自己挑节点。 |
| 2 | *（同一响应）* | `isComplete` | 为 `true` 表示全部节点已完成；停止循环并归档。 |
| 3 | *（同一响应）* | `pendingRollback` | 非 null 表示有门禁失败。改走[回退支线](#回退支线)，不要继续。 |
| 4 | `loopspec instructions <node> --change <change> --json` | `instruction` | 任务本身。它并不总是"写一个文件"——见[不是文档的节点](#不是文档的节点)。 |
| 5 | *（同一响应）* | `template` or `templates` | 要遵循的骨架。门禁会同时拿到 `templates.pass` 与 `templates.fail`。 |
| 6 | *（同一响应）* | `resolvedOutputPath` | 要写入的绝对路径。门禁这里是一个对象：只写 `.pass` 或 `.fail` 中的一个。 |
| 7 | *（同一响应）* | `contextFiles` | 每个已存在产物的真实路径，按节点 id 组织。读这些，而不是去猜文件名。 |
| 8 | *（同一响应）* | `dependencies` | 上游节点，各自带 `resolvedPath` 与是否已 `done`。 |
| 9 | *（同一响应）* | `priorAttempts` | 非空表示该节点曾被失败的门禁重置。读 `blockingIssues` 并逐条解决。 |
| 10 | *（同一响应）* | `context` and `rules` | 来自 `config.yaml` 的项目级上下文与节点级规则。两者都要遵守。 |
| 11 | *（同一响应）* | `warnings` | 值得处理的非致命问题，例如 `state_missing`。 |
| 12 | *（同一响应）* | `state` and `statePath` | 该 change 的记忆。先读再写，然后追加你的决策。 |
| 13 | — | — | 回到步骤 1。 |

### 不带 `--json` 读 `status`

默认输出是一份纯文本报告，其各节承载的信息与 JSON 相同：

| 分节 | 对应的 JSON |
| --- | --- |
| `=== OVERVIEW ===` | `changeName`、`schemaName`、`changeRoot`、`artifactRoot`、`stateExists`、`isComplete` |
| `=== NODES ===` | `nodes[]`——每个节点一条首行，glob 的其余匹配各占一条缩进续行 |
| `=== GATE FAILURES ===` | `nodes[].gate`，仅当某 gate 为 `failed` 或 `exhausted` 时出现 |
| `=== PENDING ROLLBACK ===` | `pendingRollback`，仅当它非 null 时出现 |
| `=== NEXT STEPS ===` | `nextSteps` |

每一节开头都有一段说明交代该节怎么读，因此报告是自描述的。有两件事它不提供：单个产物的绝对路径（它给的是相对 artifact 根目录的形式，绝对形式在 `=== OVERVIEW ===` 里），以及可解析的节点清单（产物路径可能含空格）。需要其中任何一项时请传 `--json`。完整版式与示例见 [CLI 参考](cli-reference.md#loopspec-status)。

重复到 `isComplete` 为 `true`，然后归档：

```bash
loopspec archive <change> --json
```

## 回退支线

当某个门禁的裁决是 FAIL 时，`status` 会把该节点报为 `failed` 并填上 `pendingRollback`。循环的形态随之改变：

| 步骤 | 命令 | 要读的字段 | 拿它做什么 |
| --- | --- | --- | --- |
| 1 | `loopspec status <change>` | `pendingRollback.command` | 确切的回退命令。原样执行。 |
| 2 | *（同一响应）* | `pendingRollback.closure` | 即将被重置的节点，让你知道接下来有多少工作量。 |
| 3 | `loopspec rollback <change> --json` | `archivedFiles`, `archiveDir` | 什么被移走了、在哪能找到。什么都没被删除。 |
| 4 | *（同一响应）* | `rollbacksUsed`, `maxRetries` | 在门禁变为 `exhausted` 之前还剩多少余量。 |
| 5 | `loopspec status <change>` | `nextSteps` | 回到主循环；被重置的节点重新变为 `ready`。 |
| 6 | `loopspec instructions <node> ...` | `priorAttempts[].blockingIssues` | 上一次尝试被拒的原因。逐条具体地解决——换个说法但问题依旧，会再次被门禁拒掉。 |

被报为 `exhausted` 的门禁无法再回退；`loopspec rollback` 会以 `retries_exhausted` 拒绝。读 `loopspec history <change> --json` 拿到历轮的完整记录，然后升级给人类。

## 不是文档的节点

有三种行为会让"每个节点都意味着写一个 markdown 文件"的 agent 意外。

### 门禁写两个文件中的一个

门禁节点的 `resolvedOutputPath` 是对象而非字符串。写 `.pass` 或 `.fail`——绝不能两个都写。两者同时存在会让下一条命令报 `gate_output_conflict`，且在删掉一个之前该 change 无法继续。

### tracked 节点在报告写完时并未完成

声明了 `tracks` 的节点，即使 PASS 产物已存在，只要被追踪文件里还有未勾选的 checkbox，它就停在 `ready`。这是刻意的：它让实现类节点等待真正的工作。

实际后果：

- 在任务尚未勾完时写出 `apply/report.md`，会让 `apply` 停在 `ready` 而不是 `done`。
- `isComplete` 保持 `false`。
- `loopspec archive` 以 `archive_unsafe` 拒绝。

所以，做完一项就在被追踪文件里勾掉那一项——把 `- [ ]` 改成 `- [x]`——而不是最后再批量改。checkbox 状态是进度能在会话被打断后存活下来的方式。`status` 为每个 tracked 节点报告 `taskProgress` 计数，`instructions` 额外给出逐条任务列表。

### 人类审批门禁的裁决不属于你

如果某个 schema 的某个节点的指令要求人类做决定，那么裁决属于人类。总结计划、用宿主工具的交互提问能力去询问，并如实记录人类的回答。

如果你没有任何办法联系到人类，或者人类尚未回答，那就**两个**产物文件都不要写，就此停下并报告该 change 正在等待审批。节点保持 `ready`，这正是"正在等一个人"的正确状态。伪造一个 PASS 会让整个门禁失去意义。

## 使用 state.md

`state.md` 是该 change 的工作记忆。它位于 change 目录，作为每次 `loopspec instructions` 响应的 `state` 字段被完整返回，并且是唯一一个回退永不触碰的文件。当 `warnings` 含 `state_missing` 时，用以下六个标准小节重建它：

```markdown
# Change State

## Current Focus
## Frozen Decisions
## Decision Log
## Rejected Options
## Open Questions
## Artifact Notes
```

让它真正有用而不只是装饰的几条规则：

- **追加，不要重写。** 已有条目是历轮的记录。由于 `state.md` 没有 `.attempts/` 历史，覆盖是不可恢复的。
- **每条记录必须能独立成立。** 把每个代词与指示语——"这个"、"那个"、"它"、"上面那条"——替换成它真正指代的东西：一个能力名、一个文件路径、一个任务编号、一个节点 id。后续节点读 `state.md` 时完全没有当前对话的上下文，因此含"那个"的条目看起来像信息，实则无法解析。
- **保留限定条件。** "可以，但 X 必须先落地"不得被蒸馏成"可以"。
- **人类的逐字原话放在裁决文件里**，而不是 `state.md`。`state.md` 只放蒸馏后的要点加上裁决文件的路径，这样需要确切措辞的人知道去哪里查。

## 读一个不是你创建的 change

三条命令能让你在不改动任何东西的前提下建立认知：

```bash
loopspec artifacts <change> --json
loopspec status <change>
loopspec history <change> --json
```

**从 `artifacts` 开始**。它是唯一能回答「这个名字下到底存在些什么」的命令，因为它是唯一不被限定在「单一 schema、单一目录」里的：它报告全部位置（活跃目录**以及**每个归档月份）、留下过文件的每个 schema、以及每一轮回退。按顺序读它的 `locations`——最早的在前——你读到的就是这个 change 的时间线。

接着 `status` 给出当前形态：什么已完成、下一步是什么、是否有门禁失败。`history` 给出**当前位置内部**的过去：每一轮尝试、哪个门禁失败、被归档的产物去了哪里。然后对那个 `ready` 节点执行 `loopspec instructions <node>`，它会交给你 `contextFiles`——当前 schema 已产出的一切的真实路径——外加 `state`，即这些产物背后的决策。

这个分工在「一个 change 被多个 schema 依次工作过」时才见真章，而这有两种发生方式：`.workflow.yaml` 被迁移到了另一个 schema，或者较早的一段已归档、新的一段以同名重新开始。两种情况下较早的产物对 `status` 与 `contextFiles` 都是不可见的——前者因为前一个 schema 的模式已不再适用，后者因为目录一旦移走 `status` 就以 `change_not_found` 失败。所以当你要接着别人（或另一个 schema）开的头继续做时：

| 步骤 | 命令 | 该读什么 | 为什么 |
| --- | --- | --- | --- |
| 1 | `loopspec artifacts <change> --json` | `locations[].files` | 这个名字下存在的每一个文件，无论它在哪。 |
| 2 | `loopspec artifacts <change> --json` | `locations[].statePath` | 每个位置各自的 `state.md`。较早那一段的决策在那里，不在当前这一段里。 |
| 3 | `loopspec artifacts <change> --json` | `warnings` | 不可读的元数据、被两个 schema 同时认领的文件、因解析后逃出 workflow home 而被跳过的路径。 |
| 4 | `loopspec status <change>` | `nextSteps` | 回到当前这一段的主循环。 |

这份响应里有两点不要读错。`locations[].schemas[]` 下的归属反映的是 schema **当前**的定义——它是一次投影，不是「历史上哪个 schema 写了什么」的记录。还有 `locations[].unclassifiedFiles` 不是一个可以无视的残留箱：任何没有被探测 schema 认领的文件都会落到那里，其中包括某个此后已被删除的 schema 的产物。那些路径也要读。

## 检查清单

- 每条命令都传 `--json`。
- 执行 `nextSteps` 指名的那一条命令；不要自己挑节点。
- 读 `contextFiles`，不要猜文件名。
- 重写被重置的节点之前，逐条解决 `priorAttempts[].blockingIssues`。
- 门禁的两个产物路径只写其中一个。
- 边做边勾被追踪的 checkbox，不要留到最后。
- 永不代替人类批准。
- 向 `state.md` 追加；永不覆盖它。

## 下一步

- [CLI 参考](cli-reference.md)——每个响应的每个字段。
- [secure-spec-driven](workflows/secure-spec-driven.md)——内置工作流逐节点的产出要求。
