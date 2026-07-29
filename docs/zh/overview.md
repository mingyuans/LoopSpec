# 总览

> 覆盖范围：LoopSpec 是什么、解决什么问题、核心模型，以及其余各篇都依赖的术语表。
> 适用读者：人类与 LLM agent，建议第一篇读这里。
> 语言：[English](../en/overview.md) · **中文**

## LoopSpec 是什么

LoopSpec 是一个运行**门禁式产物工作流**的命令行工具：你用 YAML 声明一张图，描述一次变更必须产出哪些文档（提案、规格、设计、任务……）以及它们之间的依赖。LLM 逐个生成这些文档。图中某些节点是**门禁** （gate）：它们不产出文档，而是给出 PASS 或 FAIL 裁决；FAIL 会把变更回退到声明好的上游节点，让这部分工作在完全知道上一次为什么被拒的前提下重做。

LoopSpec 自己不生成任何内容。它只反复回答一个问题：*就当前磁盘上的状态而言，下一步该产出什么，以及产出它的指令是什么？* 生成是 agent 的活；排序、门禁与回退的记账是 LoopSpec 的活。

## 它解决什么问题

用 LLM 做规范驱动开发，通常在三个地方失败：

- **agent 跳步。** 需求还没定下来就先写实现计划，因为没有任何东西强制这个顺序。
- **评审结论蒸发。** 安全评审或人类评审说了"不行，因为 X"；两轮之后同一个 X 又回来了，因为那条反对意见从未成为持久状态。
- **进度与现实脱节。** 一个独立的进度数据库说某步已完成，而对应文件其实从未被写出，或者写了又被删掉。

LoopSpec 从结构上而非靠更用力地提示来解决每一条：

- 顺序就是声明式的依赖图，一个节点在其输入存在之前始终是 `blocked`。
- 门禁失败会把失败的那次尝试**移动**进 `.attempts/round-NNN/`，并把上一次裁决的阻塞项交给下一次尝试，于是反对意见能活到重试。
- 没有进度数据库。所有状态、裁决与重试次数都在每次调用时从文件系统推导。

## 核心模型

### 一切都从文件系统推导

除了你能看见的文件，LoopSpec 不保存任何自己的状态。每条命令都会遍历 [workflow home](#术语表)、读取哪些产物存在、读取门禁裁决文件、清点 `.attempts/round-NNN/` 目录，然后据此推导出全部结论。没有东西会失去同步，修复一个状态混乱的工作流靠移动或删除文件，而不是改数据库。

每个节点最终恰好处于以下五种状态之一：

| 状态 | 含义 |
| --- | --- |
| `blocked` | 至少还有一个依赖节点未 `done`。 |
| `ready` | 依赖已满足且产物尚不存在——这就是当前该做的事。 |
| `done` | 产物已存在（门禁还要求裁决为 PASS；若节点声明了 `tracks`，还要求被追踪文件的 checkbox 全部勾选）。 |
| `failed` | 门禁的 FAIL 产物已存在，且仍有重试余量。执行回退即可继续。 |
| `exhausted` | 门禁已失败且用尽 `max_retries`，无法再回退。 |

### 节点、产物与门禁

普通节点声明 `generates`（它负责产出的产物路径）与 `template`。该路径存在，节点即 `done`。 `generates` 可以是 glob，例如 `specs/**/*.md`，此时任一匹配即算存在。

[门禁](#术语表)节点改为声明两个产物路径——一个对应 PASS，一个对应 FAIL——以及一份 `on_fail` 策略。写出 PASS 文件意味着通过，写出 FAIL 文件意味着未通过。两个都写是错误（`gate_output_conflict`），因为那样裁决就是歧义的。

### 回退只移动，从不删除

门禁失败时，`loopspec rollback` 计算**回退闭包**：`on_fail.reset` 声明的节点、门禁自身，以及这些节点的全部传递后继。然后它把这些节点的产物*移动*进 `.attempts/round-NNN/`，每一轮递增 `NNN`。什么都不会被删除，因此下一次尝试可以被准确告知上一次产出了什么、以及为什么被拒——这就是 `loopspec instructions` 的 `priorAttempts` 字段所承载的内容。

### 驱动循环

几乎全部工作由两条命令完成。`loopspec status` 报告每个节点的状态，以及一份 `nextSteps` 列表，指名下一条该执行的命令；`loopspec instructions <node>` 返回某一个节点的提示词、模板、依赖路径与历史失败。 agent 在两者之间交替，直到变更完成。逐字段的契约见 [Agent 协议](agent-protocol.md)，全部命令见 [CLI 参考](cli-reference.md)。

## 磁盘上的布局

```text
<project root>/
  loopspec/                       # the workflow home (default ./loopspec)
    config.yaml                   # which schema to use, and project-wide extras
    schemas/
      secure-spec-driven/         # a schema: node graph + templates + instructions
        schema.yaml
        templates/
        instructions/
    changes/
      add-payment/                # one change
        .workflow.yaml            # which schema this change was created with
        state.md                  # the change's working memory
        proposal.md               # artifacts, as declared by the schema
        design.md
        specs/<capability>/spec.md
        tasks.md
        security/pass.md
        .attempts/round-001/      # artifacts moved here by a rollback
    archive/
      2026-07/add-payment/        # completed changes, moved here by `archive`
  .claude/                        # optional agent skills/commands, written by `init`
```

`state.md` 与 `.workflow.yaml` 是保留文件：schema 不得把它们中的任何一个声明为节点产物。`state.md` 是唯一一个回退永不触碰的文件，这也使它成为意图能跨轮次留存的唯一位置。

## LoopSpec 不做什么

- 它不调用 LLM。它只给出指令，生成由别的东西完成。
- 它不跑你的测试、不改你的代码，也不代替人类批准任何事。
- 它不回滚代码。回退归档的是变更目录内的产物文件；实现节点已经写下的源码仍然留在那里。

## 术语表

手册其余各篇使用的术语。

| 术语 | 含义 |
| --- | --- |
| **workflow home** | 存放 `config.yaml`、`schemas/`、`changes/` 与 `archive/` 的目录。默认 `./loopspec`；每条命令都可用 `--home` 指向别处。 |
| **project root** | workflow home 的父目录——agent 工具目录（`.claude`、`.codex`……）写在这里，因为那些工具只在项目根查找它们。 |
| **schema** | 一份 YAML，描述一条工作流：节点、依赖、产物路径、模板与门禁策略。位于 `<home>/schemas/<name>/schema.yaml`。 |
| **change** | 一个走完某条工作流的工作单元。位于 `<home>/changes/<name>/`，名称为 kebab-case。 |
| **node** | schema 中的一步。要么是普通节点（产出产物），要么是门禁（产出裁决）。 |
| **artifact** | 某节点负责产出的文件，由 `generates` 相对 artifact root 命名。 |
| **artifact root** | 一个 change 的产物所在位置。默认就是 change 目录本身，除非 `config.yaml` 中该 schema 引用带了 `path`，那样产物会被收进一个子目录。 |
| **gate** | 产出 PASS/FAIL 裁决而非文档的节点，同时带一份"FAIL 时重做什么"的策略。 |
| **verdict** | 门禁的 PASS 或 FAIL 结果，由它两个产物文件中哪一个存在来记录。 |
| **reset closure** | 一次回退会重置的节点集合：`on_fail.reset`、失败的门禁自身，以及全部传递后继，按拓扑序返回。 |
| **attempts round** | 一个 `.attempts/round-NNN/` 目录，存放某一次回退移走的产物，外加一份记录触发裁决的 `_meta.yaml`。 |
| **tracked node** | 声明了 `tracks: <file>` 的节点，只有该文件中每个 checkbox 都被勾选时才算 `done`。 |

## 下一步

- [CLI 参考](cli-reference.md)——每条命令、每个选项、每个 JSON 字段。
- [配置](configuration.md)——`config.yaml` 逐字段说明。
- [Schema 参考](schema-reference.md)——如何编写自己的工作流。
- [Agent 协议](agent-protocol.md)——LLM agent 应当运行的循环。
- [secure-spec-driven](workflows/secure-spec-driven.md)——内置工作流。
