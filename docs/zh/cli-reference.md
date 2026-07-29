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

创建一个 change 目录，记录它使用的 schema，并写出初始 `state.md`。

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
| `schemaName` | string | 为该 change 解析出的 schema。 |
| `artifactsDir` | string | `config.yaml` 中 `artifacts_dir` 的取值。 |
| `schemaPath` | string or null | schema 引用中的 `path`，即产物被收进子目录时的那个子目录。 |
| `changeRoot` | string | change 目录的绝对路径。 |
| `artifactRoot` | string | 产物解析所基于的绝对路径。未设 `schemaPath` 时等于 `changeRoot`。 |
| `statePath` | string | 该 change 的 `state.md` 的绝对路径。 |
| `metadataPath` | string | 该 change 的 `.workflow.yaml` 的绝对路径。 |
| `created` | string | 创建日期，`YYYY-MM-DD`。 |
| `createdFiles` | array of string | 本命令写出的文件。 |
| `nextSteps` | array of string | 建议的后续命令。 |

```json
{
  "changeName": "add-payment",
  "schemaName": "secure-spec-driven",
  "artifactsDir": "changes",
  "schemaPath": null,
  "changeRoot": "/path/to/project/loopspec/changes/add-payment",
  "artifactRoot": "/path/to/project/loopspec/changes/add-payment",
  "statePath": "/path/to/project/loopspec/changes/add-payment/state.md",
  "metadataPath": "/path/to/project/loopspec/changes/add-payment/.workflow.yaml",
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

其他失败：名称不是 kebab-case 时报 `invalid_change_name`，目录已存在时报 `change_exists`。

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

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `changeName` | string | change 的名称。 |
| `schemaName` | string | 该 change 当前生效的 schema。 |
| `artifactsDir` | string | `config.yaml` 中 `artifacts_dir` 的取值。 |
| `schemaPath` | string or null | schema 引用声明的产物子目录，如果有。 |
| `changeRoot` | string | change 目录的绝对路径。 |
| `artifactRoot` | string | 产物解析所基于的绝对路径。 |
| `statePath` | string | `state.md` 的绝对路径。 |
| `stateExists` | boolean | `state.md` 是否存在。 |
| `isComplete` | boolean | 只有全部节点都 `done` 时才为真。 |
| `nodes` | array of object | 每个节点一条，按构建序排列。 |
| `nodes[].id` | string | 节点 id。 |
| `nodes[].status` | string | `blocked`、`ready`、`done`、`failed` 或 `exhausted`。 |
| `nodes[].outputPath` | string or object | 声明的产物。普通节点为字符串；门禁为 `{pass, fail}`。 |
| `nodes[].resolvedOutputPath` | string or object | 同上，但解析为绝对路径。 |
| `nodes[].existingOutputPaths` | array of string | 上述产物中当前实际存在于磁盘的那些。 |
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
| `dependencies[].resolvedPath` | string or null | 同上，绝对路径。 |
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
| `resolvedOutputPath` | string or object | 同上，绝对路径。 |
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
| `change_exists` | `loopspec new` 收到的名称对应的目录已存在。 | 换一个名称，或继续那个已有的 change。 |
| `invalid_change_name` | change 名称不是 kebab-case。 | 改成符合 `^[a-z][a-z0-9]*(-[a-z0-9]+)*$` 的名称。 |
| `node_not_found` | `loopspec instructions` 收到的节点 id 未在 schema 中定义。 | 用 `loopspec schemas show` 列出真实的节点 id。 |
| `gate_output_conflict` | 同一门禁的 PASS 与 FAIL 文件同时存在，裁决因此歧义。 | 删掉不反映真实裁决的那一个文件。 |
| `no_failed_gate` | 执行 `loopspec rollback` 时没有任何门禁处于 `failed`。 | 用 `loopspec status` 看清该 change 真正需要什么。 |
| `retries_exhausted` | 执行 `loopspec rollback` 时唯一可处理的门禁已是 `exhausted`。 | 查阅 `loopspec history` 并升级给人类。 |
| `archive_conflict` | 归档目标路径已存在。 | 先重命名或移除已归档的同名副本。 |
| `archive_unsafe` | 在所给参数下该 change 不合格归档。 | 先完成该 change，或在适用时传 `--exhausted` / `--include-pending-failures`。 |
