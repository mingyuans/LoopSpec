# Schema 参考

> 覆盖范围：`schema.yaml` 的每一个字段、schema 需要的目录布局、全部加载期校验及各自抛出的错误码，以及一份可直接复制的最小 schema。
> 适用读者：编写工作流的人类，以及被要求撰写或修复 `schema.yaml` 的 LLM agent。
> 语言：[English](../en/schema-reference.md) · **中文**

一个 schema 描述一条工作流：一次变更必须产出哪些文档、按什么顺序、哪些步骤是能把工作打回去的 [门禁](overview.md#术语表)。schema 位于 `<home>/schemas/<name>/`，由 `config.yaml` 引用。

## 目录布局

```text
<home>/schemas/<name>/
  schema.yaml        # the node graph -- required
  templates/         # starting skeletons, one per node output
  instructions/      # instruction text, when a node uses `instruction: {file: ...}`
```

`schema.yaml` 是唯一必需的文件。只要存在任何普通节点，`templates/` 就成为必需，因为每个普通节点都必须指定一份模板。`instructions/` 只在节点引用指令文件（而非内联文本）时才需要。

这两个目录都是沙箱：解析后落在目录之外的 `template` 或 `instruction.file` 取值会被拒绝，因此 `../../etc/passwd` 不是一个可用的模板名。

## 顶层字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | string | 是 | 无 | schema 名称，kebab-case。习惯上与目录名一致；`loopspec schemas show` 报告的是这个值，而不是目录名。 |
| `version` | integer | 是 | 无 | schema 版本，必须大于 0。仅作信息用途——LoopSpec 不在版本之间做迁移。 |
| `description` | string | 否 | 无 | 该工作流的人类可读简介。 |
| `nodes` | array of object | 是 | 无 | 该工作流的节点。至少要有一条。 |

## `nodes[]` 字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | 无 | 节点 id，kebab-case，在 schema 内唯一。被 `requires`、`on_fail.reset` 以及每条指名节点的 CLI 命令使用。 |
| `description` | string | 是 | 无 | 节点的一行描述，由 `loopspec instructions` 返回，也作为上游依赖的描述展示。 |
| `generates` | string or null | 普通节点必填 | 无 | 相对 artifact root 的产物路径，且不得越出其外：非绝对路径，不含 `..`。可以是 glob，例如 `specs/**/*.md`。门禁必须为 `null` 或省略。 |
| `template` | string or null | 普通节点必填 | 无 | `templates/` 下的模板文件名。其内容作为 `loopspec instructions` 的 `template` 字段返回。门禁必须为 `null` 或省略。 |
| `requires` | array of string | 否 | 空 | 本节点变为 `ready` 之前必须 `done` 的节点 id。每个 id 都必须存在，且构成的图必须无环。 |
| `instruction` | string or object | 否 | 无 | 指令文本。要么是内联字符串，要么是 `{file: <name>}` 指向 `instructions/` 下的一个文件。没有 `instruction` 的节点返回空字符串。 |
| `gate` | object | 否 | 无 | 把该节点变成门禁。见 [`gate`](#gate)。 |
| `tracks` | string | 否 | 无 | 一个带 checkbox 的产物路径，其完成度决定本节点是否完成。见 [`tracks`](#tracks)。 |

### `instruction`

两种等价写法。内联适合一句话：

```yaml
- id: changelog
  generates: CHANGELOG-entry.md
  description: One-line changelog entry
  template: changelog.md
  instruction: Write exactly one line, in the past tense, naming the user-visible effect.
```

文件引用适合更长的内容，并且能让 `schema.yaml` 保持可读：

```yaml
- id: proposal
  generates: proposal.md
  description: Initial proposal document outlining the change
  template: proposal.md
  instruction:
    file: proposal.md
```

`file` 的取值在 `instructions/` 下解析并在加载期读取，因此文件缺失会立刻以 `instruction_not_found` 失败，而不是等到某个 agent 真的来取这个节点时才暴露。

### `generates` 与 glob

普通节点在 `generates` 匹配到东西之后即为 `done`。具体路径必须作为文件存在。glob（取值中含 `*`、`?` 或 `[` 的任何值）用 `Path.glob` 在 artifact root 下匹配；一个或多个匹配即算完成，`loopspec status` 会报告全部匹配并排序。

glob 匹配刻意排除两类东西：`.attempts/` 下的任何内容，使被归档的上一次尝试永不会让一个被重置的节点看起来已完成；以及保留的 change 级文件 `state.md` 与 `.workflow.yaml`，即使像 `**/*.md` 这样宽泛的 glob 本会匹配到它们。

### `tracks`

声明了 `tracks` 的节点，只有在被追踪文件存在**并且**其中每个 checkbox 都被勾选时才 `done`。正是这一点让实现类节点等待真正的工作，而不是等一份报告被写出来。

```yaml
- id: apply
  description: Implementation of the approved plan
  requires: [approval]
  tracks: tasks.md
  instruction:
    file: apply.md
  gate:
    outputs:
      pass: apply/report.md
      fail: apply/blocked.md
    templates:
      pass: apply-report.md
      fail: apply-blocked.md
    on_fail:
      reset: [design]
      max_retries: 2
```

checkbox 解析识别 `- [ ]`、`- [x]`、`- [X]` 以及以 `*` 开头的等价写法，任意缩进都可以。零个 checkbox 的文件算作*未*完成，因此空任务列表无法让一个 tracked 节点通过。解析永不抛异常：缺失或不可读的被追踪文件读作零个任务，并在 `loopspec instructions` 中体现为一条 `tracked file not found: <path>` 警告。

以下约束全部在加载期校验：

- `tracks` 必须是安全相对路径——非绝对、不含 `..`。
- `tracks` 必须是具体路径而非 glob。进度必须来自一个确定的文件。
- 必须有某个节点在其 `generates` 中声明了完全相同的路径。
- 至少要有一个这样的产出节点是本节点的祖先，从而保证本节点运行时该文件已经存在。

### `gate`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `outputs` | object | 是 | 无 | 两条裁决路径。见 [`gate.outputs`](#gateoutputs)。 |
| `templates` | object | 是 | 无 | 两份裁决模板。见 [`gate.templates`](#gatetemplates)。 |
| `on_fail` | object | 是 | 无 | 裁决为 FAIL 时重做什么。见 [`gate.on_fail`](#gateon_fail)。 |

写出 PASS 文件意味着门禁通过；写出 FAIL 文件意味着未通过。两个都写是 `gate_output_conflict`，因为裁决会变成歧义——删掉不反映事实的那一个。

### `gate.outputs`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `pass` | string | 是 | 无 | 门禁通过时写出的产物路径。必须是具体路径（非 glob）且与 `fail` 不同。 |
| `fail` | string | 是 | 无 | 门禁未通过时写出的产物路径。必须是具体路径（非 glob）且与 `pass` 不同。 |

### `gate.templates`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `pass` | string | 是 | 无 | `templates/` 下对应 PASS 裁决的模板文件名。 |
| `fail` | string | 是 | 无 | `templates/` 下对应 FAIL 裁决的模板文件名。 |

两者都由 `loopspec instructions` 作为 `templates.pass` 与 `templates.fail` 返回，因此 agent 在决定裁决之前就能看到两种形态。

### `gate.on_fail`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `reset` | array of string | 是 | 无 | FAIL 时重做哪些节点。至少要有一个 id，且每个 id 都必须是本门禁的祖先。 |
| `max_retries` | integer | 否 | `3` | 该门禁可消耗多少次回退。必须大于或等于 0。用尽后门禁变为 `exhausted` 而不再是 `failed`。 |
| `on_exhausted` | string | 否 | `escalate` | 用尽意味着什么：`escalate`（交给人类）或 `stop`。 |

`reset` 指的是*起点*。实际被重置的集合是闭包：这些节点、门禁自身，以及全部传递后继。在 `tasks` 依赖 `design`、`security` 依赖 `tasks` 的图中声明 `reset: [design]`，会重置 `design`、`tasks` 与 `security` ——下游节点不需要你自己列出来。

选择 `reset` 是设计一个门禁时的主要决策。重置那个拥有此门禁所检测的*错误类别*的节点：安全评审发现的是 "怎么做"的问题，所以它重置 `design`；人类审批往往否决的是"做什么"，所以它还要重置 `specs`。

## 保留路径

`state.md` 与 `.workflow.yaml` 属于 change 而不属于任何节点。把它们中任何一个声明为 `generates`、 `gate.outputs.pass` 或 `gate.outputs.fail` 都会以 `schema_invalid` 失败。它们同样被排除在 glob 匹配之外，而且回退永不归档它们——正是这一点让 `state.md` 成为唯一能跨轮次留存的记忆。

## 加载期校验

加载分两个阶段：先用 Pydantic 做结构校验（未知字段是错误，不是警告），再做语义校验。第一个失败即抛出；不会有半加载状态。

| 校验项 | 错误码 |
| --- | --- |
| YAML 可解析，每个字段符合其声明类型，且不含未知字段。 | `schema_invalid` |
| `name` 是 kebab-case，`version` 大于 0，`nodes` 非空。 | `schema_invalid` |
| 节点 id 唯一。 | `schema_invalid` |
| 每个 `requires` 条目都指向存在的节点。 | `schema_invalid` |
| `requires` 构成的图无环。消息会给出完整环路，例如 `alpha → beta → alpha`。 | `schema_invalid` |
| 普通节点有非空的 `generates` 与非空的 `template`。 | `schema_invalid` |
| 门禁的 `generates` 与 `template` 为 `null` 或字符串，不可为其他类型。 | `schema_invalid` |
| 门禁的 `pass` 与 `fail` 产物是具体路径（非 glob）且互不相同。 | `schema_invalid` |
| 每个 `template` 路径都留在 `templates/` 内且是安全相对路径。 | `schema_invalid` |
| 每个被引用的模板文件都存在。 | `template_not_found` |
| 每个产物路径 —— `generates` 与门禁的两个裁决路径 —— 都是安全相对路径：非绝对路径，不含 `..`。产物必须留在自己的 change 目录内，因为 `rollback` 会**移动**它解析出的产物。 | `schema_invalid` |
| 没有任何产物路径使用保留名（`state.md`、`.workflow.yaml`）。 | `schema_invalid` |
| 每个 `on_fail.reset` 条目都指向存在的节点。 | `schema_invalid` |
| 每个 `on_fail.reset` 条目都是其门禁的祖先。消息会列出合法选项。 | `schema_invalid` |
| `tracks` 是安全相对路径。 | `schema_invalid` |
| `tracks` 不是 glob。 | `schema_invalid` |
| `tracks` 指向某个节点在 `generates` 中声明过的路径。 | `schema_invalid` |
| 至少有一个产出被追踪路径的节点是追踪节点的祖先。 | `schema_invalid` |
| 每个 `instruction.file` 路径都留在 `instructions/` 内且是安全相对路径。 | `schema_invalid` |
| 每个被引用的指令文件都存在。 | `instruction_not_found` |

执行 `loopspec schemas validate <name> --json` 可以跑完全部校验。成功时它返回拓扑构建序，那也是 `loopspec status` 报告节点的顺序。

## 一份完整的最小 schema

两个节点：先一份文档，再一个评审它的门禁。足以真正可用，又小到能一眼读完。

<!-- loopspec:example=schema-dir -->
```yaml
name: draft-and-review
version: 1
description: Write a short draft, then review it

nodes:
  - id: draft
    generates: draft.md
    description: The draft document under review
    template: draft.md
    requires: []
    instruction:
      file: draft.md

  - id: review
    generates: null
    description: Review gate over the draft
    template: null
    requires: [draft]
    instruction:
      file: review.md
    gate:
      outputs:
        pass: review/approved.md
        fail: review/rejected.md
      templates:
        pass: review-approved.md
        fail: review-rejected.md
      on_fail:
        reset: [draft]
        max_retries: 2
        on_exhausted: escalate
```

它期望磁盘上有这些文件：

```text
loopspec/schemas/draft-and-review/
  schema.yaml
  templates/
    draft.md
    review-approved.md
    review-rejected.md
  instructions/
    draft.md
    review.md
```

接上并检查：

```bash
loopspec schemas validate draft-and-review --json
loopspec new my-first-change --schema draft-and-review --json
loopspec status my-first-change --json
```

由此得到的流程：`draft` 起初是 `ready`；`draft.md` 存在后它变为 `done`，`review` 变为 `ready`；写出 `review/approved.md` 即完成该 change，而写出 `review/rejected.md` 会让 `review` 变为 `failed`， `loopspec rollback` 随后把 `draft.md` 与那份拒绝意见移动进 `.attempts/round-001/`，使草稿可以带着拒绝意见中的阻塞项重写。两次被拒之后门禁变为 `exhausted` 并要求人类介入。

## 下一步

- [配置](configuration.md)——schema 如何被 `config.yaml` 引用。
- [secure-spec-driven](workflows/secure-spec-driven.md)——一份含三个门禁的七节点实例 schema。
- [Agent 协议](agent-protocol.md)——agent 如何消费 schema 所声明的内容。
