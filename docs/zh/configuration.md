# 配置

> 覆盖范围：`config.yaml` 的每一个字段、各自的校验规则、LoopSpec 如何决定一个 change 使用哪个 schema，以及四个递进示例。
> 适用读者：搭建项目的人类，以及需要读写合法 `config.yaml` 的 LLM agent。
> 语言：[English](../en/configuration.md) · **中文**

`config.yaml` 位于 [workflow home](overview.md#术语表) 的根目录，配置整个项目。`loopspec init` 会写出一份两行的起步版本：

<!-- loopspec:example=config -->
```yaml
artifacts_dir: changes
schema: secure-spec-driven
```

其余全部可选。未知字段会被拒绝而不是被忽略，因此像 `schemata:` 这样的笔误会以 `config_invalid` 失败，而不是被静默丢弃。

## 顶层字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `artifacts_dir` | string | 否 | `changes` | workflow home 下存放 change 目录的目录名。必须是安全相对路径：非绝对、不含 `..`。 |
| `schema` | string | 否 | 无 | 新建 change 的默认 schema，也是没有 `.workflow.yaml` 的既有 change 的兜底值。必须是 kebab-case。当同时设置了 `schemas` 时，该值必须出现在 `schemas[*].name` 中。 |
| `schemas` | array of object | 否 | 空 | 创建 change 时可选用的候选 schema。见 [`schemas[]` 条目](#schemas-条目)。名称必须唯一。 |
| `schema_selection` | object | 否 | 无 | 指导 agent 如何在多个候选之间选择。见 [`schema_selection`](#schema_selection)。 |
| `context` | string | 否 | 无 | 项目级上下文，原样作为每次 `loopspec instructions` 响应的 `context` 字段返回。 |
| `rules` | object | 否 | 空 | 按节点附加的额外规则：节点 id 到字符串列表，作为该节点 `loopspec instructions` 响应的 `rules` 字段返回。 |

`schema` 与 `schemas` 至少要出现一个。两者都没有的配置会以 `config_invalid` 失败，消息为 `config.yaml must define schema or schemas`。

### `schemas[]` 条目

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | string | 是 | 无 | `<home>/schemas/` 下的 schema 目录名，kebab-case。该目录必须含一份可加载的 `schema.yaml`，在配置加载时校验。 |
| `path` | string | 否 | 无 | 把该 schema 的产物收进 change 目录下的哪个子目录。必须是安全相对路径。未设置时产物直接放在 change 目录下。 |
| `description` | string | 否 | 无 | 人类可读的简介，会回显在 `schema_selection_required` 的错误载荷中。 |
| `when` | string | 否 | 无 | 什么情况下该选这个 schema，会回显在 `schema_selection_required` 的错误载荷中。 |

### `schema_selection`

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `instruction` | string | 是 | 无 | 需要选择 schema 时交给 agent 的指令。作为 `schema_selection_required` 错误载荷中的 `selectionInstruction` 返回。不得为空。 |

## 校验规则

任何命令加载配置时都会执行；每一条失败都以退出码 1 与 `config_invalid` 结束。

| 规则 | 你会看到的消息 |
| --- | --- |
| 文件必须存在。 | `config.yaml not found in <home>` |
| 顶层与嵌套层都不允许未知字段。 | Pydantic 校验错误，会指出多余的字段。 |
| `schema` 或 `schemas` 至少出现一个。 | `config.yaml must define schema or schemas` |
| `schemas[*].name` 必须唯一。 | `schemas[*].name must be unique` |
| `schema` 与 `schemas` 同时出现时，前者必须是候选之一。 | `schema must be included in schemas[*].name when both are configured` |
| `schema` 与 `schemas[*].name` 必须是 kebab-case。 | Pydantic 正则错误。 |
| `artifacts_dir` 必须是安全相对路径。 | `artifacts_dir must be a safe relative path: <value>` |
| `schemas[*].path` 必须是安全相对路径。 | `schemas[*].path must be a safe relative path: <value>` |
| 每个候选 schema 都必须可加载。 | `Candidate schema '<name>' cannot be loaded: <dir> not found` |

`rules` 中的键指向 schema 未定义的节点**不是**错误。它会作为 `loopspec instructions` 响应中的一条 `warnings`（`rules reference unknown node '<key>'`）出现，因此重命名节点不会让工作流直接崩掉。

## schema 是如何解析出来的

存在两条不同的解析路径，把它们搞混是最常见的配置错误。区别在于：change 在创建时就把自己的 schema 记进了 `.workflow.yaml`，因此创建之后项目默认值不再决定任何事。

| 场景 | 优先级顺序 |
| --- | --- |
| 创建 change（`loopspec new`） | 1. `--schema`——但若配置了 `schemas`，该值必须是候选之一，否则报 `config_invalid`。2. 若 `schemas` 有多于一条：以 `schema_selection_required` 失败。3. 若 `schemas` 恰好一条：用它。4. `schema`。5. 以 `config_invalid` 失败。 |
| 操作既有 change（`status`、`instructions`、`rollback`、`history`、`archive`、`bulk-archive`） | 1. 该 change 自己的 `.workflow.yaml`。2. `schema`。3. 以 `config_invalid` 失败。 |

由此带来几个值得知道的后果：

- 改动 `config.yaml` 中的 `schema` 不会迁移既有 change。它们仍沿用自己 `.workflow.yaml` 中记录的 schema。
- 列出多个候选会让 `--schema` 成为 `loopspec new` 的必填项。这是刻意的：强制显式选择，而不是静默取第一条。
- `.workflow.yaml` 有两个字段，都由 `loopspec new` 写入：`schema`（解析出的 schema 名称）与 `created` （`YYYY-MM-DD` 日期）。它不是为手改设计的，但改 `schema` 是把一个进行中的 change 迁到另一条工作流的受支持做法。

## 示例

### 最小配置

一个 schema，默认布局。这就是 `loopspec init` 产出的内容。

<!-- loopspec:example=config -->
```yaml
artifacts_dir: changes
schema: secure-spec-driven
```

### 多个候选 schema

两条工作流可选，外加 agent 选择时应遵循的指令。注意这里没有 `schema`：有多个候选又没有默认值时， `loopspec new` 总是要求 `--schema`。

<!-- loopspec:example=config -->
```yaml
artifacts_dir: changes
schemas:
  - name: secure-spec-driven
    description: Full spec-driven flow with security, approval and implementation gates
    when: Default choice for anything that touches production behaviour
  - name: docs-only
    description: Lightweight flow for documentation-only changes
    when: Use when no runtime code changes are involved
schema_selection:
  instruction: Ask the human which flow fits before creating the change.
```

此时创建 change 是这样：

```bash
loopspec new update-readme --schema docs-only --json
```

### 项目上下文与按节点的规则

`context` 会附加到每个节点的指令载荷；`rules` 为特定节点补充约束。两者都是原样透传，因此它们正是在不改 schema 的前提下编码团队规范的地方。

<!-- loopspec:example=config -->
```yaml
artifacts_dir: changes
schema: secure-spec-driven
context: |
  This is a Python 3.11 project managed with uv. Tests run via `make test`,
  linting via `make lint`. Public APIs live in src/acme/api/.
rules:
  proposal:
    - Reference the tracking issue id in the first paragraph.
  design:
    - Call out every new third-party dependency explicitly.
    - Note any change to the public API surface.
  tasks:
    - Every task must be completable in one sitting.
```

### 自定义布局

`artifacts_dir` 改名存放 change 的目录；`schemas[*].path` 把每个 change 的产物收进一个子目录，从而让 `state.md` 与 `.workflow.yaml` 在视觉上与文档本身分开。

<!-- loopspec:example=config -->
```yaml
artifacts_dir: work-items
schema: secure-spec-driven
schemas:
  - name: secure-spec-driven
    path: artifacts
```

在这份配置下，名为 `add-payment` 的 change 布局如下：

```text
loopspec/
  work-items/
    add-payment/
      .workflow.yaml
      state.md
      artifacts/
        proposal.md
        design.md
        specs/<capability>/spec.md
        tasks.md
        security/pass.md
```

## 下一步

- [Schema 参考](schema-reference.md)——`schema` 与 `schemas[*].name` 所指向的那些 `schema.yaml` 文件的格式。
- [CLI 参考](cli-reference.md)——读取本文件的那些命令。
