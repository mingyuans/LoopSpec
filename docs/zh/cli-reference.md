# CLI 参考

> 覆盖范围：每一条 `loopspec` 命令——用途、语法、选项、`--json` 响应字段、真实示例——以及错误码总表。
> 适用读者：查参数的人类，以及需要精确响应结构的 LLM agent。
> 语言：[English](../en/cli-reference.md) · **中文**

每条命令都接受 `--json`。这是从 agent 驱动 LoopSpec 的主协议；不加它则得到面向人类的纯文本摘要。两种模式呈现同一组事实，但人类可读模式允许做聚合（用计数替代完整路径明细）。

有两个选项几乎出现在每条命令上：

| 选项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--home` | path | `./loopspec` | 要操作的 workflow home。见 [workflow home](overview.md#术语表)。 |
| `--json` | flag | 关闭 | 在 stdout 输出机器可解析的 JSON，替代人类摘要。 |

下文示例中的 JSON 路径一律以 `/path/to/project` 为根——真实输出里是你本机的绝对路径。

## 失败契约

任何失败的命令都以退出码 **1** 结束，并在 `--json` 模式下打印一个恰好含三个字段的对象：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `error` | string | 机器可读错误码，取自[错误码总表](#错误码)。 |
| `message` | string | 人类可读的失败原因。 |
| `fix` | string | 建议的下一步动作。没有具体建议时可能是空字符串。 |

```json
{
  "error": "change_not_found",
  "message": "Change not found: nope",
  "fix": ""
}
```

成功的命令以退出码 **0** 结束。

## loopspec version

打印已安装的 LoopSpec 版本。

```bash
loopspec version [--json]
```

| 选项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--json` | flag | 关闭 | 输出 `{"version": "..."}` 而非裸版本号。 |

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `version` | string | 已安装的包版本，由构建时所在的 git tag 写入。未安装过的源码树返回 `0.0.0.dev0`，因为此时没有可报告的发布版本。 |

```json
{"version": "0.1.0"}
```

## loopspec init

创建 workflow home、把内置 schema 复制进去，并可选地为 AI 编程工具生成 skill 与斜杠命令文件。

```bash
loopspec init [PATH] [--no-builtin] [--tools all|none|<ids>] [--project-root <dir>] [--json]
```

| 选项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `PATH` | path | `./loopspec` | 位置参数：在哪里创建 workflow home。 |
| `--no-builtin` | flag | 关闭 | 跳过复制随包分发的内置 schema。 |
| `--tools` | string | 见下文 | `all`、`none`，或逗号分隔的工具 id 列表（例如 `claude,codex`）。 |
| `--project-root` | path | `PATH` 的父目录 | 把 `.claude`、`.codex` 之类工具目录写到哪里。 |
| `--json` | flag | 关闭 | 输出机器可解析的 JSON，并抑制全部进度输出与装饰。 |

`init` 是幂等的：已存在的 `config.yaml` 不会被改动，已存在的 schema 目录不会被覆盖。重复执行是刷新工具脚手架，而不是重复写入。

### `--tools` 的解析规则

- 显式给值（`all`、`none` 或列表）总是被遵从。
- 省略、处于交互式终端、且未加 `--json`：先显示欢迎屏，再给出对全部 31 个已注册工具的可搜索多选列表。首次配置时，目录已存在的工具默认勾选；一旦配置过，后续运行改为预选*已配置*的工具。确认时什么都没勾等同于 `none`，Ctrl+C 被当作"本次不配置任何工具"而非报错。
- 省略、且处于非交互环境（管道、重定向、CI）或加了 `--json`：等同于 `none`。

对每个被选中的工具，skill 文件写入 `<project root>/<tool dir>/skills/loopspec-*/SKILL.md`。斜杠命令只为有命令适配器的工具生成；31 个已注册工具中有 28 个具备适配器，另外三个（`forgecode`、`kimi`、`vibe`）会在 `skippedCommandGeneration` 中被报告。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `workflowHome` | string | 现已存在的 workflow home 的绝对路径。 |
| `projectRoot` | string | 工具目录被写入的绝对路径。 |
| `createdFiles` | array of string | 本次运行创建的 workflow home 文件；若全部已存在则为空。 |
| `copiedSchemas` | array of string | 本次运行复制进来的内置 schema 名称。 |
| `toolsConfigured` | array of string | 本次运行选中的工具 id。 |
| `scaffoldedFiles` | object | 工具 id 到为它写入的文件列表。 |
| `skippedCommandGeneration` | array of string | 只拿到 skill、没拿到斜杠命令的工具 id，因为不存在对应的命令适配器。 |
| `createdTools` | array of string | 首次被配置的工具 id。 |
| `refreshedTools` | array of string | 原本已有 skill 文件、本次被重写的工具 id。 |
| `nextSteps` | array of string | 建议的后续命令。 |

```json
{
  "workflowHome": "/path/to/project/loopspec",
  "projectRoot": "/path/to/project",
  "createdFiles": [
    "config.yaml"
  ],
  "copiedSchemas": [
    "secure-spec-driven"
  ],
  "toolsConfigured": [],
  "scaffoldedFiles": {},
  "skippedCommandGeneration": [],
  "createdTools": [],
  "refreshedTools": [],
  "nextSteps": [
    "Run `loopspec schemas list --home /path/to/project/loopspec --json` to see available schemas."
  ]
}
```

不加 `--json` 时，`init` 打印一份分节摘要：`Created:` 或 `Refreshed:` 工具列表、聚合计数行、配置文件路径及其 schema、被跳过的命令生成、一条 `Getting started:` 命令，以及文档链接。当 stdout 不是终端或设置了 `NO_COLOR` 时，颜色与进度指示器自动消失；当输出编码无法表示 Unicode 字形时，它们降级为 ASCII （`ok`、`x`、`!`、`-`、`|`）。

## loopspec schemas list

列出 workflow home 中每一个可加载的 schema。

```bash
loopspec schemas list [--home <dir>] [--json]
```

| 选项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--home` | path | `./loopspec` | 要扫描的 workflow home。 |
| `--json` | flag | 关闭 | 输出机器可解析的 JSON。 |

`<home>/schemas/` 下没有 `schema.yaml` 的目录，或者有但加载失败的目录，会被静默跳过，而不会让整个列表失败。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `schemas` | array of object | 每个可加载的 schema 一条。 |
| `schemas[].name` | string | `schema.yaml` 内部声明的 schema 名称。 |
| `schemas[].version` | integer | schema 版本。 |
| `schemas[].source` | string | 本版本中恒为 `local`。 |
| `schemas[].path` | string | schema 目录的绝对路径。 |
| `schemas[].nodes` | array of string | 按拓扑序排列的节点 id。 |

```json
{
  "schemas": [
    {
      "name": "secure-spec-driven",
      "version": 1,
      "source": "local",
      "path": "/path/to/project/loopspec/schemas/secure-spec-driven",
      "nodes": [
        "proposal",
        "specs",
        "design",
        "tasks",
        "security",
        "approval",
        "apply"
      ]
    }
  ]
}
```

## loopspec schemas show

展示某一个 schema 的节点图。

```bash
loopspec schemas show <name> [--home <dir>] [--json]
```

| 选项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `NAME` | string | 必填 | 位置参数：`<home>/schemas/` 下的 schema 目录名。 |
| `--home` | path | `./loopspec` | 要读取的 workflow home。 |
| `--json` | flag | 关闭 | 输出机器可解析的 JSON。 |

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `name` | string | schema 名称。 |
| `version` | integer | schema 版本。 |
| `nodes` | array of object | 按构建（拓扑）序排列的节点。 |
| `nodes[].id` | string | 节点 id。 |
| `nodes[].requires` | array of string | 本节点依赖的节点 id。 |
| `nodes[].generates` | string or null | 产物路径或 glob；不产出文档的门禁为 `null`。 |
| `nodes[].isGate` | boolean | 该节点是否声明了 `gate` 块。 |

```json
{
  "name": "secure-spec-driven",
  "version": 1,
  "nodes": [
    {
      "id": "proposal",
      "requires": [],
      "generates": "proposal.md",
      "isGate": false
    },
    {
      "id": "security",
      "requires": [
        "tasks"
      ],
      "generates": null,
      "isGate": true
    }
  ]
}
```

该路径下没有 `schema.yaml` 时报 `schema_not_found`；文件存在但校验不通过时报 `schema_invalid`。

## loopspec schemas validate

加载一个 schema，并对它执行全部结构与语义校验。

```bash
loopspec schemas validate <name> [--home <dir>] [--json]
```

| 选项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `NAME` | string | 必填 | 位置参数：`<home>/schemas/` 下的 schema 目录名。 |
| `--home` | path | `./loopspec` | 要读取的 workflow home。 |
| `--json` | flag | 关闭 | 输出机器可解析的 JSON。 |

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `valid` | boolean | 恒为 `true`——不合法的 schema 会以退出码 1 与错误对象结束，不会走到这里。 |
| `name` | string | schema 名称。 |
| `buildOrder` | array of string | 按拓扑序排列的节点 id，同层按 id 排序，保证多次运行结果稳定。 |

```json
{
  "valid": true,
  "name": "secure-spec-driven",
  "buildOrder": [
    "proposal",
    "design",
    "specs",
    "tasks",
    "security",
    "approval",
    "apply"
  ]
}
```

编写 schema 时应当用这条命令。全部校验项及各自抛出的错误码见 [Schema 参考](schema-reference.md)。

```json
{
  "error": "schema_invalid",
  "message": "Cyclic dependency: alpha → beta → alpha",
  "fix": "Remove the circular `requires` reference between these nodes."
}
```

## loopspec new

创建或复用 canonical change 目录并记录所选 schema。未显式配置 `schemas[*].path` 时，多 schema 项目的每个 schema 独占 `<change>/<schema>/`，其中包含 metadata、`state.md`、rollback 历史与 artifacts。显式 `path` 保持原有的 artifact-only 语义，单 schema 项目继续使用平铺布局。

```bash
loopspec new <change-name> [--schema <name>] [--home <dir>] [--json]
```

| 选项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `CHANGE_NAME` | string | 必填 | 位置参数：kebab-case 的 change 名称（`^[a-z][a-z0-9]*(-[a-z0-9]+)*$`）。 |
| `--schema` | string | 取自配置 | 使用哪个 schema。当 `config.yaml` 列了多个候选时必填。 |
| `--home` | path | `./loopspec` | 在哪个 workflow home 中创建 change。 |
| `--json` | flag | 关闭 | 输出机器可解析的 JSON。 |

被选中的 schema 会写入该 change 的 `.workflow.yaml`，因此即使项目默认值后来改了，后续命令仍作用于同一个 schema。完整解析顺序见[配置](configuration.md)。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `changeName` | string | change 的名称。 |
| `requestedChangeName` | string | 调用方请求的名称，即 canonical 复用前的名称。 |
| `reusedChange` | boolean | 是否复用了已有 active change 目录。 |
| `schemaName` | string | 为该 change 解析出的 schema。 |
| `artifactsDir` | string | `config.yaml` 中 `artifacts_dir` 的取值。 |
| `schemaPath` | string or null | schema 的有效子目录：显式 `path`，或多 schema 自动布局中的 schema 名。 |
| `changeRoot` | string | change 目录的绝对路径。 |
| `artifactRoot` | string | 产物解析所基于的绝对路径。未设 `schemaPath` 时等于 `changeRoot`。 |
| `statePath` | string | 该 change 的 `state.md` 的绝对路径。 |
| `metadataPath` | string | 该 change 的 `.workflow.yaml` 的绝对路径。 |
| `activeMetadataPath` | string | 未传 `--schema` 的命令用于定位当前 schema 的根 metadata 指针绝对路径。 |
| `created` | string | 创建日期，`YYYY-MM-DD`。 |
| `createdFiles` | array of string | 本命令写出的文件。 |
| `nextSteps` | array of string | 建议的后续命令。 |

```json
{
  "changeName": "add-payment",
  "requestedChangeName": "add-payment",
  "reusedChange": false,
  "schemaName": "secure-spec-driven",
  "artifactsDir": "changes",
  "schemaPath": null,
  "changeRoot": "/path/to/project/loopspec/changes/add-payment",
  "artifactRoot": "/path/to/project/loopspec/changes/add-payment",
  "statePath": "/path/to/project/loopspec/changes/add-payment/state.md",
  "metadataPath": "/path/to/project/loopspec/changes/add-payment/.workflow.yaml",
  "activeMetadataPath": "/path/to/project/loopspec/changes/add-payment/.workflow.yaml",
  "created": "2026-07-29",
  "createdFiles": [
    ".workflow.yaml",
    "state.md"
  ],
  "nextSteps": [
    "Run `loopspec status add-payment --json` to see the first node."
  ]
}
```

当 `config.yaml` 列了多个候选 schema 而又没给 `--schema` 时，命令以退出码 1 与 `schema_selection_required` 结束；与其他错误不同，它还会带上候选列表，便于调用方把选择呈现给用户：

```json
{
  "error": "schema_selection_required",
  "message": "config.yaml defines multiple candidate schemas; one must be chosen before creating this change.",
  "fix": "Pick a schemas[*].name and re-run with --schema <name>.",
  "changeName": "some-change",
  "artifactsDir": "changes",
  "schemas": [
    {
      "name": "secure-spec-driven",
      "path": null,
      "description": "Full spec-driven flow with security, approval and implementation gates",
      "when": "Default choice for anything that touches production behaviour"
    },
    {
      "name": "docs-only",
      "path": null,
      "description": "Lightweight flow for documentation-only changes",
      "when": "Use when no runtime code changes"
    }
  ],
  "selectionInstruction": "Ask the human which flow fits before creating the change."
}
```

创建目录前，`new` 会扫描 active 与 archived change 名。请求名追加了所选 schema 后缀（例如 `be-driven` 对应的 `-be`），或与唯一已有 change 共享 `afd-13592` 这类工单前缀时，会复用已有 canonical 名；匹配有歧义时绝不自动合并。只有 canonical change 中已经存在同一 schema workspace 时才报 `change_exists`，另一 schema 可以复用同一 change。

其他失败：名称不是 kebab-case 时报 `invalid_change_name`。

## loopspec status

报告每个节点推导出的状态，并指名下一条该执行的命令。这是 agent 每一轮都要调用的命令。

```bash
loopspec status <change-name> [--home <dir>] [--json]
```

| 选项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `CHANGE_NAME` | string | 必填 | 位置参数：要查看哪个 change。 |
| `--home` | path | `./loopspec` | change 所在的 workflow home。 |
| `--json` | flag | 关闭 | 输出机器可解析的 JSON。 |

不带 `--json` 时，本命令输出一份版式固定的纯文本报告，而不再是逐字段的 `key: value` 列表。这份默认输出是为驱动循环的 LLM 写的，因此 skill 不必再为了知道下一步而附加 `--json` 去解析 JSON；`--json` 仍是需要精确字段的调用方的取值来源。**破坏性变更：** 原先按行 grep 非 JSON 输出的脚本现在必须改用 `--json`。

<!-- loopspec:example=status-report -->
```text
=== OVERVIEW ===
Where this change lives and whether it is finished. Paths here are absolute;
paths in every other section are relative to the artifact root.

change:        add-payment
schema:        secure-spec-driven
change root:   /Users/<you>/proj/loopspec/changes/add-payment
state.md:      present
complete:      no

=== NODES ===
Every node of the workflow, in dependency order. Columns: node id, status,
output path, then notes in parentheses. Statuses: done (output exists),
ready (dependencies met, output not written yet), blocked (waiting on the
nodes named in its notes), failed / exhausted (a gate rejected the work).
Do not pick a node yourself -- act on the one named in NEXT STEPS. A path
like dir/{a,b}.md means the node is a gate that writes exactly one of the
two; get the real paths from `loopspec instructions`. A node whose output
is a glob lists every file it currently matches, one per line, indented
under its first line; a path still containing * means that glob has no
matches yet. Notes describe the node, so they stay on its first line.

proposal  done     proposal.md
design    done     design.md
specs     done     specs/loopspec-cli/spec.md
                   specs/lpsx-skills/spec.md
                   specs/status-report/spec.md
tasks     done     tasks.md
security  done     security/pass.md
approval  ready    approval/{approved,changes-requested}.md
apply     blocked  apply/{report,blocked}.md                 (needs: approval)

=== NEXT STEPS ===
What to do next. Run these in order; the first one is enough to make
progress. Run them as written rather than composing your own.

1. Run `loopspec instructions approval --change add-payment --json`, then write the artifact per the returned template(s) and update state.md.
```

报告的分节固定为以下顺序：

| 分节 | 是否恒在 | 渲染的内容 |
| --- | --- | --- |
| `=== OVERVIEW ===` | 是 | `changeName`、`schemaName`、`changeRoot`、`artifactRoot`（仅当它与 `changeRoot` 不同时）、`stateExists`、`isComplete` |
| `=== NODES ===` | 是 | 每个 `nodes[]` 条目一条首行，glob 的其余匹配各占一条续行 |
| `=== GATE FAILURES ===` | 仅当某个 gate 为 `failed` 或 `exhausted` | `nodes[].gate` |
| `=== PENDING ROLLBACK ===` | 仅当 `pendingRollback` 非 null | `pendingRollback` |
| `=== NEXT STEPS ===` | 是 | `nextSteps`，逐条编号；为空时输出一行占位 |

每一节的分隔行之后都有一段内置说明，交代该节是什么、怎么读，因此报告不假定读者事先了解 loopspec 的节点、gate、回退等概念。

读节点清单时注意：

- 路径相对 artifact 根目录，其绝对形式由 `=== OVERVIEW ===` 给出一次。
- glob 节点列出它当前匹配到的**全部**文件：第一个与节点同行，其余各占一条缩进的续行。产物列中仍含 `*` 的路径表示该 glob 尚无匹配。
- gate 在写出判定之前显示 `dir/{pass,fail}.ext`，写出之后显示实际那一个文件的路径。花括号形式是显示形式，不是可直接写入的路径——真实路径由 `loopspec instructions` 返回。
- 圆括号里的备注属于节点而非某个文件，且恰好取以下之一：缺失依赖、任务进度、指向 `=== GATE FAILURES ===` 的提示、或"尚无匹配"。
- 解析后位于 artifact 根目录之外的匹配（指向 change 目录之外的符号链接）显示 `<outside artifact root>`，而不是它实际指向哪里。需要解析后的路径请用 `--json`。
- 这份清单**不是**可解析的格式：产物路径可能含空格，列边界因此不可靠。需要精确字段时请用 `--json`。
- 任何内插值中的控制字符都会被改写为 `\xNN`，因此路径、判定摘要或 change 名都无法开启新行、伪造出 `=== SECTION ===` 分隔行。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `changeName` | string | change 的名称。 |
| `schemaName` | string | 该 change 当前生效的 schema。 |
| `artifactsDir` | string | `config.yaml` 中 `artifacts_dir` 的取值。 |
| `schemaPath` | string or null | schema 的有效子目录：显式 `path`，或自动生成的 schema 同名 workspace。 |
| `changeRoot` | string | change 目录的绝对路径。 |
| `artifactRoot` | string | 产物解析所基于的绝对路径。 |
| `statePath` | string | `state.md` 的绝对路径。 |
| `stateExists` | boolean | `state.md` 是否存在。 |
| `isComplete` | boolean | 只有全部节点都 `done` 时才为真。 |
| `nodes` | array of object | 每个节点一条，按构建序排列。 |
| `nodes[].id` | string | 节点 id。 |
| `nodes[].status` | string | `blocked`、`ready`、`done`、`failed` 或 `exhausted`。 |
| `nodes[].outputPath` | string or object | 声明的产物。普通节点为字符串；门禁为 `{pass, fail}`。 |
| `nodes[].resolvedOutputPath` | string, array, object or null | 绝对路径，且绝不是模式串：具体的 `generates` 解析为它的路径，无论文件是否已存在；glob 解析为它当前匹配到的文件数组，无匹配时为 `null`。门禁为 `{pass, fail}`。 |
| `nodes[].existingOutputPaths` | array of string | 上述产物中当前实际存在于磁盘的那些，绝对路径并已排序。glob 会展开为它匹配到的文件。 |
| `nodes[].missingDeps` | array of string | 仅在 `blocked` 时出现：尚未 `done` 的依赖节点。 |
| `nodes[].taskProgress` | object | 仅对声明了 `tracks` 的节点出现。只给计数；逐条任务列表在 `instructions` 中。 |
| `nodes[].taskProgress.path` | string | 被追踪文件相对 artifact root 的路径。 |
| `nodes[].taskProgress.resolvedPath` | string | 被追踪文件的绝对路径。 |
| `nodes[].taskProgress.total` | integer | 找到的 checkbox 总数。 |
| `nodes[].taskProgress.complete` | integer | 已勾选数量。 |
| `nodes[].taskProgress.remaining` | integer | 仍未勾选数量。 |
| `nodes[].gate` | object | 仅在节点为 `failed` 或 `exhausted` 时出现。 |
| `nodes[].gate.verdict` | string | `FAIL`。 |
| `nodes[].gate.summary` | string or null | FAIL 文件的首个标题，用作一行摘要。 |
| `nodes[].gate.blockingIssues` | array of string | 从 FAIL 文件中提取的列表项。 |
| `nodes[].gate.rollbacksUsed` | integer | 该门禁已消耗的回退次数。 |
| `nodes[].gate.maxRetries` | integer | 该门禁的 `on_fail.max_retries`。 |
| `nodes[].gate.resetDeclared` | array of string | 该门禁声明的 `on_fail.reset` 列表。 |
| `nodes[].gate.resetClosure` | array of string | 一次回退实际会重置的完整节点集合。 |
| `pendingRollback` | object or null | 有门禁处于 `failed` 时出现：接下来应执行的回退。 |
| `pendingRollback.gate` | string | 失败门禁的节点 id。 |
| `pendingRollback.closure` | array of string | 回退将重置的节点。 |
| `pendingRollback.command` | string | 要执行的确切命令。 |
| `nextSteps` | array of string | 唯一的下一步动作，以可直接执行的命令形式给出。 |

一个刚创建的 change：

```json
{
  "changeName": "add-payment",
  "schemaName": "secure-spec-driven",
  "artifactsDir": "changes",
  "schemaPath": null,
  "changeRoot": "/path/to/project/loopspec/changes/add-payment",
  "artifactRoot": "/path/to/project/loopspec/changes/add-payment",
  "statePath": "/path/to/project/loopspec/changes/add-payment/state.md",
  "stateExists": true,
  "isComplete": false,
  "nodes": [
    {
      "id": "proposal",
      "status": "ready",
      "outputPath": "proposal.md",
      "resolvedOutputPath": "/path/to/project/loopspec/changes/add-payment/proposal.md",
      "existingOutputPaths": []
    },
    {
      "id": "specs",
      "status": "blocked",
      "outputPath": "specs/**/*.md",
      "resolvedOutputPath": null,
      "existingOutputPaths": [],
      "missingDeps": [
        "proposal"
      ]
    },
    {
      "id": "design",
      "status": "blocked",
      "outputPath": "design.md",
      "resolvedOutputPath": "/path/to/project/loopspec/changes/add-payment/design.md",
      "existingOutputPaths": [],
      "missingDeps": [
        "proposal"
      ]
    }
  ],
  "pendingRollback": null,
  "nextSteps": [
    "Run `loopspec instructions proposal --change add-payment --json`, then write the artifact per the returned template(s) and update state.md."
  ]
}
```

一个安全门禁已失败的 change：

```json
{
  "nodes": [
    {
      "id": "security",
      "status": "failed",
      "outputPath": {
        "pass": "security/pass.md",
        "fail": "security/fail.md"
      },
      "resolvedOutputPath": {
        "pass": "/path/to/project/loopspec/changes/add-payment/security/pass.md",
        "fail": "/path/to/project/loopspec/changes/add-payment/security/fail.md"
      },
      "existingOutputPaths": [
        "/path/to/project/loopspec/changes/add-payment/security/fail.md"
      ],
      "gate": {
        "verdict": "FAIL",
        "summary": "Security Review: FAIL",
        "blockingIssues": [
          "Card numbers are logged in plaintext by the checkout handler.",
          "The refund endpoint has no authorization check."
        ],
        "rollbacksUsed": 0,
        "maxRetries": 3,
        "resetDeclared": [
          "design"
        ],
        "resetClosure": [
          "design",
          "tasks",
          "security",
          "approval",
          "apply"
        ]
      }
    }
  ],
  "pendingRollback": {
    "gate": "security",
    "closure": [
      "design",
      "tasks",
      "security",
      "approval",
      "apply"
    ],
    "command": "loopspec rollback add-payment --json"
  },
  "nextSteps": [
    "Gate \"security\" verdict is FAIL: Security Review: FAIL",
    "Run `loopspec rollback add-payment --json` to roll back, then regenerate the reset nodes."
  ]
}
```

## loopspec instructions

返回产出某一个节点所需的一切：指令文本、模板、写到哪里、哪些依赖已存在、以及历史尝试失败在什么地方。

```bash
loopspec instructions <node-id> --change <change-name> [--home <dir>] [--json]
```

| 选项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `NODE_ID` | string | 必填 | 位置参数：要取哪个节点的指令。 |
| `--change` | string | 必填 | 该节点属于哪个 change。 |
| `--home` | path | `./loopspec` | change 所在的 workflow home。 |
| `--json` | flag | 关闭 | 输出机器可解析的 JSON。 |

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `changeName` | string | change 的名称。 |
| `schemaName` | string | 当前生效的 schema。 |
| `changeDir` | string | change 目录的绝对路径。 |
| `artifactRoot` | string | 产物解析所基于的绝对路径。 |
| `nodeId` | string | 节点 id。 |
| `description` | string | schema 中该节点的一行描述。 |
| `instruction` | string | 完整指令文本：schema 中的内联字符串，或所引用指令文件的内容。 |
| `context` | string or null | 来自 `config.yaml` 的项目级上下文。 |
| `rules` | array of string | `config.yaml` 中为该节点配置的额外规则。 |
| `dependencies` | array of object | `requires` 中每个节点一条。 |
| `dependencies[].id` | string | 依赖节点 id。 |
| `dependencies[].done` | boolean | 该依赖是否已完成。 |
| `dependencies[].path` | string or null | 它的产物路径——门禁取 PASS 路径。 |
| `dependencies[].resolvedPath` | string, array or null | 绝对路径，且绝不是模式串：具体的 `generates` 解析为它的路径，无论文件是否已存在；glob 解析为它当前匹配到的文件数组，无匹配时为 `null`。 |
| `dependencies[].description` | string | 该依赖的描述。 |
| `contextFiles` | object | 节点 id 到该节点当前已存在的产物文件列表，使一个节点无需猜文件名即可读到整个 change。磁盘上什么都没有的节点会被省略。 |
| `unlocks` | array of string | 本节点完成后会解除阻塞的节点 id。 |
| `statePath` | string | `state.md` 的绝对路径。 |
| `state` | string or null | `state.md` 的当前内容；文件缺失时为 `null`。 |
| `warnings` | array of string | 非致命问题，例如 `state_missing`、`rules` 键指向未知节点、被追踪文件缺失。 |
| `priorAttempts` | array of object | 曾经重置过该节点的历史回退，最早的在前。首次尝试时为空。 |
| `priorAttempts[].round` | integer | 该次失败属于第几轮。 |
| `priorAttempts[].gate` | string | 失败的门禁。 |
| `priorAttempts[].verdict` | string | `FAIL`。 |
| `priorAttempts[].summary` | string or null | 该次失败的一行摘要。 |
| `priorAttempts[].blockingIssues` | array of string | 下一次尝试必须解决的问题。 |
| `priorAttempts[].archivedPath` | string | 该节点上一次的产物被移动到了哪里。 |
| `outputPath` | string or object | 写到哪里。普通节点为字符串；门禁为 `{pass, fail}`。 |
| `resolvedOutputPath` | string, array, object or null | 绝对路径，且绝不是模式串：具体的 `generates` 解析为它的路径，无论文件是否已存在；glob 解析为它当前匹配到的文件数组，无匹配时为 `null`。门禁为 `{pass, fail}`。 |
| `template` | string | 普通节点专有：模板文件的内容。 |
| `templates` | object | 门禁专有：`{pass, fail}` 两份模板的内容。 |
| `taskProgress` | object | 声明了 `tracks` 的节点专有：`status` 中的计数，外加一个 `{id, description, done}` 的 `tasks` 数组。 |

```json
{
  "priorAttempts": [
    {
      "round": 1,
      "gate": "security",
      "verdict": "FAIL",
      "summary": "Security Review: FAIL",
      "blockingIssues": [
        "Card numbers are logged in plaintext by the checkout handler.",
        "The refund endpoint has no authorization check."
      ],
      "archivedPath": "/path/to/project/loopspec/changes/add-payment/.attempts/round-001/design.md"
    }
  ],
  "dependencies": [
    {
      "id": "proposal",
      "done": true,
      "path": "proposal.md",
      "resolvedPath": "/path/to/project/loopspec/changes/add-payment/proposal.md",
      "description": "Initial proposal document outlining the change"
    }
  ],
  "warnings": [],
  "unlocks": [
    "tasks"
  ]
}
```

节点 id 不存在时报 `node_not_found`，change 不存在时报 `change_not_found`。

## loopspec rollback

回退该 change 当前处于失败状态的门禁：把回退闭包内的每个产物移动进一个新的 `.attempts/round-NNN/` 目录，并附一份记录触发裁决的 `_meta.yaml`。

```bash
loopspec rollback <change-name> [--home <dir>] [--json]
```

| 选项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `CHANGE_NAME` | string | 必填 | 位置参数：要回退哪个 change。 |
| `--home` | path | `./loopspec` | change 所在的 workflow home。 |
| `--json` | flag | 关闭 | 输出机器可解析的 JSON。 |

文件是**被移动，绝不被删除**。`state.md` 与 `.workflow.yaml` 永不被归档，因此该 change 的记忆能存活过每一轮。回退不回滚源码——只处理 change 目录内的产物。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `changeName` | string | change 的名称。 |
| `gate` | string | 被回退的门禁。 |
| `round` | integer | 本次回退创建的轮次号。 |
| `closure` | array of string | 被重置的节点，按拓扑序排列。 |
| `archivedFiles` | array of string | 被移动的产物路径，相对 artifact root。 |
| `archiveDir` | string | `.attempts/round-NNN/` 目录的绝对路径。 |
| `rollbacksUsed` | integer | 该门禁至此已消耗的回退次数。 |
| `maxRetries` | integer | 该门禁的 `on_fail.max_retries`。 |
| `nextSteps` | array of string | 建议的后续命令。 |

```json
{
  "changeName": "add-payment",
  "gate": "security",
  "round": 1,
  "closure": [
    "design",
    "tasks",
    "security",
    "approval",
    "apply"
  ],
  "archivedFiles": [
    "design.md",
    "tasks.md",
    "security/fail.md"
  ],
  "archiveDir": "/path/to/project/loopspec/changes/add-payment/.attempts/round-001",
  "rollbacksUsed": 1,
  "maxRetries": 3,
  "nextSteps": [
    "Run `loopspec status add-payment --json` to see the next node."
  ]
}
```

没有任何东西处于失败状态时报 `no_failed_gate`；唯一可处理的门禁已用尽 `max_retries` 时报 `retries_exhausted`：

```json
{
  "error": "no_failed_gate",
  "message": "No gate is currently in a failed state; there is nothing to roll back.",
  "fix": "Run `loopspec status` to see the current state."
}
```

## loopspec history

列出某个 change 记录下的每一轮尝试。

```bash
loopspec history <change-name> [--home <dir>] [--json]
```

| 选项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `CHANGE_NAME` | string | 必填 | 位置参数：读取哪个 change 的历史。 |
| `--home` | path | `./loopspec` | change 所在的 workflow home。 |
| `--json` | flag | 关闭 | 输出机器可解析的 JSON。 |

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `changeName` | string | change 的名称。 |
| `rounds` | array of object | 每个 `.attempts/round-NNN/` 目录一条，最早的在前。 |
| `rounds[].round` | integer | 轮次号。 |
| `rounds[].gate` | string | 失败的门禁。 |
| `rounds[].verdict` | string | `FAIL`。 |
| `rounds[].summary` | string or null | 该次失败的一行摘要。 |
| `rounds[].resetClosure` | array of string | 被重置的节点。 |
| `rounds[].archivedFiles` | array of string | 被移动的产物路径。 |
| `rounds[].archiveDir` | string | 该轮目录的绝对路径。 |
| `rounds[].archivedAt` | string | 回退时刻的 ISO-8601 时间戳。 |

```json
{
  "changeName": "add-payment",
  "rounds": [
    {
      "round": 1,
      "gate": "security",
      "verdict": "FAIL",
      "summary": "Security Review: FAIL",
      "resetClosure": [
        "design",
        "tasks",
        "security",
        "approval",
        "apply"
      ],
      "archivedFiles": [
        "design.md",
        "tasks.md",
        "security/fail.md"
      ],
      "archiveDir": "/path/to/project/loopspec/changes/add-payment/.attempts/round-001",
      "archivedAt": "2026-07-29T17:00:11.952957+08:00"
    }
  ]
}
```

## loopspec artifacts

列出一个 canonical change 名下的全部产物路径——跨越所有工作过它的 schema，以及它存在的所有位置，归档目录也包含在内。无歧义的工单/schema 后缀别名会按与 `new` 相同的规则解析。

```bash
loopspec artifacts <change-name> [--schemas <names>] [--home <dir>] [--json]
```

| 选项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `CHANGE_NAME` | string | 必填 | 位置参数：列出哪个 change 的产物。 |
| `--schemas` | string | 全部已知 schema | 逗号分隔的 schema 名列表，只报告这些 schema 的产物（例如 `secure-spec-driven,docs-only`）。 |
| `--home` | path | `./loopspec` | 要搜索的 workflow home。 |
| `--json` | flag | 关闭 | 输出机器可解析的 JSON。 |

这条命令回答的问题是其他命令答不了的。`status` 与 `instructions` 都只解析**一个** schema——`.workflow.yaml` 里记的那个——且要求 change 目录仍然存在。这在两种情况下不成立：

- **schema 接力**。多个 schema 依次工作同一个 change。`.workflow.yaml` 只有一个 `schema` 字段，把 change 迁到另一条工作流时前一个 schema 名被覆盖；而每个 schema 的产物可能落在不同的 `schemas[*].path` 根下，当前 schema 的节点模式根本匹配不到。
- **归档**。`loopspec archive` 把整个目录**移动**到 `<home>/archive/YYYY-MM/<change>/`。一段工作被归档后，`status` 会以 `change_not_found` 失败，那一段的产物再也无法通过它触达——而「做完、归档、以同名继续下一段」恰恰是接力最常见的形态。

因此 `artifacts` 同时跨越三个维度：

| 维度 | 覆盖范围 |
| --- | --- |
| 位置 | 活跃目录，外加**全部**归档月份。`ArchiveConflictError` 只阻止同月重名，因此同一个名字可以在多个月份各有一份；每个命中都作为一条独立的 location 返回。 |
| schema | 范围内的每个 schema 都被**探测**：显式 `schemas[*].path` 给出 artifact root；未配置时，多 schema change 使用 schema 同名 workspace。各节点的产物模式匹配磁盘上真实存在的文件，旧版平铺 change 仍原地兼容探测。 |
| 轮次 | 每个位置下的每个 `.attempts/round-NNN/` 目录，与当前产物分开报告。 |

三点值得知道的后果：

- **归属是「对 schema 当前定义的一次投影」，不是历史记录**。改动某个 schema 的 `generates` 会改变一个老 change 的文件分组方式。文件绝不会因此丢失——它们会转入 `unclassifiedFiles`。
- **`unclassifiedFiles` 是完整性的兜底**。任何真实存在、却匹配不上任何被探测模式的文件都会出现在那里：被删掉的 schema 留下的残留、改名后的产物、有人手工放进来的附件。隐藏文件也不被过滤，因此 `.DS_Store` 会出现——可见的噪音优于一份静默漏项的清单。
- **解析后逃出 workflow home 的路径会被跳过**。路径解析会跟随符号链接，因此 change 目录里指向文件系统别处的链接会被从所有清单中剔除，并在 `warnings` 中只以相对名指名。该位置的其余部分照常报告。

`state.md` 与 `.workflow.yaml` 不算产物（与 CLI 其余部分同一条规则），但每个位置无论如何都会给出 `statePath` 与 `stateExists`：接力工作流对前一段的决策记录和对它的文件同样需要。

本命令为只读。它不创建、不移动、不删除任何东西，归档目录内也一样。

位置按「从早到晚」返回——归档月份升序在前，然后是活跃目录。这个顺序是契约的一部分：接力阅读的顺序是先读较早的几段再读当前那段，因此这个列表可以直接顺序遍历。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `changeName` | string | change 的名称。 |
| `artifactsDir` | string | `config.yaml` 中 `artifacts_dir` 的取值。 |
| `requestedSchemas` | array of string or null | 传给 `--schemas` 的名称；省略该选项时为 `null`，这与空列表不是一回事。 |
| `schemasSeen` | array of string | 实际被探测的 schema，已排序。 |
| `locations` | array of object | 该 change 产物所在的每个位置一条，最早的在前。 |
| `locations[].kind` | string | `active` 或 `archived`。 |
| `locations[].archiveMonth` | string or null | 归档月份目录名；活跃位置为 `null`。 |
| `locations[].changeRoot` | string | 该位置 change 目录的绝对路径。 |
| `locations[].declaredSchema` | string or null | 该位置 `.workflow.yaml` 记录的 schema；该文件缺失或不可读时为 `null`。 |
| `locations[].created` | string or null | 同一文件中的 `created` 日期。 |
| `locations[].statePath` | string | 该位置 `state.md` 的绝对路径。 |
| `locations[].stateExists` | boolean | 该文件是否存在。 |
| `locations[].schemas` | array of object | 每个被探测的 schema 一条，按名称排序。 |
| `locations[].schemas[].name` | string | schema 名称。 |
| `locations[].schemas[].declared` | boolean | 该位置的 `.workflow.yaml` 是否记的就是这个 schema。为假是正常的——接力就是这个样子。 |
| `locations[].schemas[].schemaPath` | string or null | schema 的有效子目录：显式 `path`，或多 schema 自动布局中的 schema 名。 |
| `locations[].schemas[].artifactRoot` | string | 探测所基于的绝对路径。 |
| `locations[].schemas[].nodes` | array of object | 至少有一个现存产物的节点，按构建序排列。磁盘上什么都没有的节点被省略。 |
| `locations[].schemas[].nodes[].id` | string | 节点 id。 |
| `locations[].schemas[].nodes[].isGate` | boolean | 该节点是否声明了 `gate` 块。 |
| `locations[].schemas[].nodes[].outputPatterns` | array of string | 探测该节点所用的声明模式——门禁则为它的 PASS 与 FAIL 产物。 |
| `locations[].schemas[].nodes[].files` | array of string | 为该节点匹配到的现存文件。 |
| `locations[].schemas[].files` | array of string | 该 schema 在该位置认领的全部文件，已去重。 |
| `locations[].attempts` | array of object | 每个回退轮次目录一条。 |
| `locations[].attempts[].round` | integer or null | 从目录名得出的轮次号；目录名不是 `round-<digits>` 时为 `null`。这样的目录仍会被报告，因此其中的文件不会丢失。 |
| `locations[].attempts[].gate` | string or null | 该轮 `_meta.yaml` 中记录的门禁；缺失或不可读时为 `null`。 |
| `locations[].attempts[].verdict` | string or null | 同一文件中的裁决。 |
| `locations[].attempts[].archiveDir` | string | 该轮次目录的绝对路径。 |
| `locations[].attempts[].files` | array of string | 该轮归档的文件，不含它的 `_meta.yaml`。 |
| `locations[].unclassifiedFiles` | array of string | 该位置中没有被任何被探测 schema 认领的文件。 |
| `locations[].files` | array of string | 该位置的全部产物路径，已去重并排序。 |
| `files` | array of string | 全部位置的全部产物路径，已去重并排序。 |
| `warnings` | array of string | 非致命问题：元数据不可读、某个 schema 加载失败、某文件被多个 schema 认领、某路径解析后逃出 workflow home。 |
| `nextSteps` | array of string | 建议的后续命令。 |

一个曾被归档、又以同名重新开始的 change：

```json
{
  "changeName": "add-payment",
  "artifactsDir": "changes",
  "requestedSchemas": null,
  "schemasSeen": [
    "docs-only",
    "secure-spec-driven"
  ],
  "locations": [
    {
      "kind": "archived",
      "archiveMonth": "2026-06",
      "changeRoot": "/path/to/project/loopspec/archive/2026-06/add-payment",
      "declaredSchema": "secure-spec-driven",
      "created": "2026-06-11",
      "statePath": "/path/to/project/loopspec/archive/2026-06/add-payment/state.md",
      "stateExists": true,
      "schemas": [
        {
          "name": "secure-spec-driven",
          "declared": true,
          "schemaPath": null,
          "artifactRoot": "/path/to/project/loopspec/archive/2026-06/add-payment",
          "nodes": [
            {
              "id": "proposal",
              "isGate": false,
              "outputPatterns": [
                "proposal.md"
              ],
              "files": [
                "/path/to/project/loopspec/archive/2026-06/add-payment/proposal.md"
              ]
            }
          ],
          "files": [
            "/path/to/project/loopspec/archive/2026-06/add-payment/proposal.md"
          ]
        }
      ],
      "attempts": [
        {
          "round": 1,
          "gate": "security",
          "verdict": "FAIL",
          "archiveDir": "/path/to/project/loopspec/archive/2026-06/add-payment/.attempts/round-001",
          "files": [
            "/path/to/project/loopspec/archive/2026-06/add-payment/.attempts/round-001/design.md"
          ]
        }
      ],
      "unclassifiedFiles": [],
      "files": [
        "/path/to/project/loopspec/archive/2026-06/add-payment/.attempts/round-001/design.md",
        "/path/to/project/loopspec/archive/2026-06/add-payment/proposal.md"
      ]
    }
  ],
  "files": [
    "/path/to/project/loopspec/archive/2026-06/add-payment/.attempts/round-001/design.md",
    "/path/to/project/loopspec/archive/2026-06/add-payment/proposal.md"
  ],
  "warnings": [],
  "nextSteps": [
    "Every copy of this change is archived; read the listed paths directly, or run `loopspec new add-payment --schema <name>` to start a new stretch of work under this name."
  ]
}
```

不加 `--json` 时，命令按位置分节打印计数而不是路径——schema 名称与各自认领的文件数、未认领数、回退轮次、`state.md` 是否存在——最后给出总计。完整的路径明细仍可通过 `--json` 取得。

失败情形：任何位置都匹配不上的 change 名报 `change_not_found`；不是安全相对路径的名字报 `invalid_change_name`；`--schemas` 的取值 strip 后一段不剩、或含有非 kebab-case 的名称，报 `config_invalid`。点名一个加载不出来的 schema 报 `schema_not_found` 或 `schema_invalid`，而不是返回空结果——否则「这个 schema 什么都没产出」与「你把名字拼错了」将无法区分。仅仅是被**推断**出来的 schema（来自 `config.yaml` 候选或某位置自己的 `.workflow.yaml`）则降级为一条 warning，因此从配置里删掉一条候选永远不会让老产物凭空消失。

## loopspec archive

把一个已完成的 change 移动进 `<home>/archive/YYYY-MM/`，其中 `YYYY-MM` 取执行时刻的 UTC 年月。

```bash
loopspec archive <change-name> [--dry-run] [--exhausted] [--include-pending-failures] [--home <dir>] [--json]
```

| 选项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `CHANGE_NAME` | string | 必填 | 位置参数：要归档哪个 change。 |
| `--dry-run` | flag | 关闭 | 只报告会移动什么，不改动磁盘。 |
| `--exhausted` | flag | 关闭 | 允许归档卡在 `exhausted` 门禁上的 change，前提是没有任何门禁仅处于 `failed`。 |
| `--include-pending-failures` | flag | 关闭 | 允许归档仍有 `failed` 门禁、本可继续回退的 change。 |
| `--home` | path | `./loopspec` | change 所在的 workflow home。 |
| `--json` | flag | 关闭 | 输出机器可解析的 JSON。 |

归档是**移动**目录，什么都不会被删除。它默认立即执行——没有确认参数——但会拒绝任何不合格的 change：

- 已完成的 change 总是合格。
- `exhausted` 的 change 只在加了 `--exhausted` 且没有任何东西处于 `failed` 时合格。
- `failed` 的 change 只在加了 `--include-pending-failures` 时合格。
- 其余情况以退出码 1 与 `archive_unsafe` 结束。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `dryRun` | boolean | 本次是否为预览。 |
| `changeName` | string | change 的名称。 |
| `schemaName` | string | 该 change 使用的 schema。 |
| `reason` | string | 合格原因：`complete`、`exhausted` 或 `pending-failure`。 |
| `source` | string | change 移出的绝对路径。 |
| `destination` | string | change 移入的绝对路径。 |
| `moved` | boolean | 仅在真实执行时出现：恒为 `true`。 |
| `nextSteps` | array of string | 建议的后续动作。 |

```json
{
  "dryRun": false,
  "changeName": "add-payment",
  "schemaName": "secure-spec-driven",
  "reason": "complete",
  "source": "/path/to/project/loopspec/changes/add-payment",
  "destination": "/path/to/project/loopspec/archive/2026-07/add-payment",
  "moved": true,
  "nextSteps": [
    "Archiving complete."
  ]
}
```

未完成的 change 会被拒绝：

```json
{
  "error": "archive_unsafe",
  "message": "This change is not complete and does not qualify for archiving under the current flags.",
  "fix": "Finish the change, or pass --exhausted / --include-pending-failures if that applies."
}
```

目标路径已存在时改报 `archive_conflict`，因此同名的旧归档永不会被覆盖。

## loopspec bulk-archive

一次性归档全部合格的 change。

```bash
loopspec bulk-archive [--complete] [--exhausted] [--older-than <days>] [--dry-run] [--home <dir>] [--json]
```

| 选项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `--complete` | flag | 开启 | 为与 `--exhausted` 对称而接受。已完成的 change 本来就总是候选，因此传它不改变任何行为。 |
| `--exhausted` | flag | 关闭 | 同时归档卡在 `exhausted` 门禁上的 change。 |
| `--older-than` | integer | 未设置 | 只考虑目录最后修改时间距今至少这么多天的 change。 |
| `--dry-run` | flag | 关闭 | 只报告候选列表，不改动磁盘。 |
| `--home` | path | `./loopspec` | 要扫描的 workflow home。 |
| `--json` | flag | 关闭 | 输出机器可解析的 JSON。 |

不合格的 change 会被静默跳过，而不会让整次运行失败。与单个 `archive` 不同，批量归档从不接受待处理的失败——只要有门禁处于 `failed`，该 change 就不合格。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `dryRun` | boolean | 本次是否为预览。 |
| `archiveRoot` | string | 本月的目标目录。 |
| `candidates` | array of object | 合格的 change，每条形如一次 `archive --dry-run` 的结果。 |
| `moved` | array of object | 仅在真实执行时出现：实际被移动的 change。 |
| `nextSteps` | array of string | 建议的后续动作。 |

```json
{
  "dryRun": true,
  "archiveRoot": "/path/to/project/loopspec/archive/2026-07",
  "candidates": [
    {
      "dryRun": true,
      "changeName": "add-payment",
      "schemaName": "secure-spec-driven",
      "reason": "complete",
      "source": "/path/to/project/loopspec/changes/add-payment",
      "destination": "/path/to/project/loopspec/archive/2026-07/add-payment",
      "nextSteps": [
        "Re-run without --dry-run to move this change into the archive."
      ]
    }
  ],
  "nextSteps": [
    "Re-run without --dry-run to move these changes into the archive."
  ]
}
```

## 错误码

任何失败都以退出码 1 结束，并在 `error` 字段中报告以下之一。

| 错误码 | 触发条件 | 修复方向 |
| --- | --- | --- |
| `schema_not_found` | 解析出的 schema 目录下不存在 `schema.yaml`。 | 创建该文件，或指向正确的 schema 名称。 |
| `schema_selection_required` | `config.yaml` 列了多个候选 schema，而 `loopspec new` 没收到 `--schema`。 | 从 `schemas[*].name` 中选一个并传 `--schema`。错误载荷里带着候选列表。 |
| `schema_invalid` | schema 结构校验失败（未知字段、类型错误），或任一语义校验失败（id 重复、`requires` 指向未知节点、成环、门禁产物有问题、`on_fail.reset` 非法、`tracks` 非法、使用了保留产物路径）。 | 修正报告中指出的节点或字段；见 [Schema 参考](schema-reference.md)。 |
| `config_invalid` | `config.yaml` 缺失、校验失败，或含不安全的相对路径。 | 修正 `config.yaml` 中被指出的字段。 |
| `template_not_found` | 某节点的 `template`，或某门禁的 pass/fail 模板，在 schema 的 `templates/` 下不存在。 | 补上模板文件，或修正 `schema.yaml` 中的名称。 |
| `instruction_not_found` | 某节点的 `instruction.file` 在 schema 的 `instructions/` 下不存在。 | 补上指令文件，或修正 `schema.yaml` 中的名称。 |
| `change_not_found` | 该 workflow home 中不存在指定名称的 change 目录。 | 检查名称，或检查 `--home`。 |
| `change_exists` | canonical change 中已存在所选 schema workspace，或该路径无法安全复用。 | 继续该 schema，或选择另一 schema/change。 |
| `invalid_change_name` | change 名称不是 kebab-case。 | 改成符合 `^[a-z][a-z0-9]*(-[a-z0-9]+)*$` 的名称。 |
| `node_not_found` | `loopspec instructions` 收到的节点 id 未在 schema 中定义。 | 用 `loopspec schemas show` 列出真实的节点 id。 |
| `gate_output_conflict` | 同一门禁的 PASS 与 FAIL 文件同时存在，裁决因此歧义。 | 删掉不反映真实裁决的那一个文件。 |
| `no_failed_gate` | 执行 `loopspec rollback` 时没有任何门禁处于 `failed`。 | 用 `loopspec status` 看清该 change 真正需要什么。 |
| `retries_exhausted` | 执行 `loopspec rollback` 时唯一可处理的门禁已是 `exhausted`。 | 查阅 `loopspec history` 并升级给人类。 |
| `archive_conflict` | 归档目标路径已存在。 | 先重命名或移除已归档的同名副本。 |
| `archive_unsafe` | 在所给参数下该 change 不合格归档。 | 先完成该 change，或在适用时传 `--exhausted` / `--include-pending-failures`。 |
