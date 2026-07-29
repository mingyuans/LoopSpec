# Agent 协议

> 覆盖范围：LLM agent 把一个 change 推进到完成所要运行的确切循环、每一步该读哪个响应字段，以及四种最容易搞错的行为。
> 适用读者：驱动 LoopSpec 的 LLM agent，以及编写驱动提示词的人类。
> 语言：[English](../en/agent-protocol.md) · **中文**

始终传 `--json`。始终读 `nextSteps`。永远不要从文件名或对前一轮的记忆去推断下一步——文件系统才是事实来源，而且它可能已经变了。

## 主循环

```text
loopspec status <change> --json
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
| 1 | `loopspec status <change> --json` | `nextSteps` | 指名恰好一条命令。执行它。不要自己挑节点。 |
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

重复到 `isComplete` 为 `true`，然后归档：

```bash
loopspec archive <change> --json
```

## 回退支线

当某个门禁的裁决是 FAIL 时，`status` 会把该节点报为 `failed` 并填上 `pendingRollback`。循环的形态随之改变：

| 步骤 | 命令 | 要读的字段 | 拿它做什么 |
| --- | --- | --- | --- |
| 1 | `loopspec status <change> --json` | `pendingRollback.command` | 确切的回退命令。原样执行。 |
| 2 | *（同一响应）* | `pendingRollback.closure` | 即将被重置的节点，让你知道接下来有多少工作量。 |
| 3 | `loopspec rollback <change> --json` | `archivedFiles`, `archiveDir` | 什么被移走了、在哪能找到。什么都没被删除。 |
| 4 | *（同一响应）* | `rollbacksUsed`, `maxRetries` | 在门禁变为 `exhausted` 之前还剩多少余量。 |
| 5 | `loopspec status <change> --json` | `nextSteps` | 回到主循环；被重置的节点重新变为 `ready`。 |
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

两条命令能让你在不改动任何东西的前提下建立认知：

```bash
loopspec status <change> --json
loopspec history <change> --json
```

`status` 给出当前形态：什么已完成、下一步是什么、是否有门禁失败。`history` 给出过去：每一轮尝试、哪个门禁失败、被归档的产物去了哪里。然后对那个 `ready` 节点执行 `loopspec instructions <node>`，它会交给你 `contextFiles`——已产出的一切的真实路径——外加 `state`，即这些产物背后的决策。

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
