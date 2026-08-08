## Why

`loopspec status <change>` 的实际调用方是 LLM/Agent（`/lpsx:*` skills 每一轮循环都会执行它），但它当前的默认输出走的是 `_emit()` 的 `key: value` 逐字段打印：`nodes` 这类嵌套结构会被 `str()` 成一整行 Python repr，既不可读、也不可靠。于是 skills 只能一律追加 `--json`，让 LLM 去解析一份含绝对路径、`schemaPath`、`existingOutputPaths` 等大量它并不需要逐字读的 JSON——token 开销大且噪声高。

把默认输出改成一段版式固定的 Markdown，能让 LLM 直接"读"到当前进度和下一步动作，把 `--json` 留给真正需要精确字段的程序化调用方。

## What Changes

- `loopspec status <change>` 不带 `--json` 时，输出一段版式固定的分段纯文本报告，而不再是 `key: value` 逐字段列表。**BREAKING**（默认输出格式变更；`--json` 输出契约不变）。
- 报告按固定的分节顺序组织，节与节之间以固定的分隔行划分，内容包括：change 概览（名称、schema、artifact 根目录、`state.md` 是否存在、是否已完成）、节点状态清单（含 gate 判定、`taskProgress` 进度、`blocked` 节点的缺失依赖）、待回退提示（`pendingRollback`）、以及下一步动作（`nextSteps`）。
- 每个分节附带一段**内置说明文字**，向读到它的 LLM 交代该节是什么、各列含义、以及该据此做什么，使报告不依赖读者事先了解 loopspec 的内部概念。
- 该报告面向 LLM 消费，因此是纯文本：不使用 Markdown 语法，不带颜色、glyph、进度动画等任何仅对人眼有意义的终端装饰，也不随终端宽度改变换行。
- `--json` 保持现有字段契约完全不变，仍是精确字段的唯一来源；两种输出承载的信息保持一致。
- `/lpsx:*` skill 模板中调用 `loopspec status` 的步骤改为使用默认（Markdown）输出，不再追加 `--json`。

## Capabilities

### New Capabilities
- `status-report`: `loopspec status` 面向 LLM 的分段纯文本报告格式——分节的固定版式、各节的内置说明文字、各节的取值来源与省略规则、纯文本（无 Markdown 语法、无终端装饰）约束、内插值的消毒规则，以及它与 `--json` 之间"信息一致"的对应关系。

### Modified Capabilities
- `loopspec-cli`: `loopspec status 查看状态` 要求需补充默认（非 `--json`）输出为分段纯文本报告的约定；`全命令支持结构化 JSON 输出` 要求中"人类可读输出为次要形式"的定位需修订为 `status` 的默认输出以 LLM 消费为目标；`统一错误输出格式` 要求需补充非 JSON 模式下的呈现形态与消毒约束。
- `lpsx-skills`: `loopspec-continue` / `loopspec-new` skill 中读取 `status` 的步骤，从"解析 `--json`"改为"读取默认纯文本报告"。

## Impact

- 代码：`src/loopspec/cli.py`（`status` 命令的输出分支、`_fail` 的非 JSON 分支）、`src/loopspec/presentation.py`（其现有定位是"human-readable、rich 着色"，需要为不着色的 LLM 报告确立位置）、`src/loopspec/skill_templates.py`（skill 正文中的 `status` 调用）。`config.yaml` 与 `WorkflowConfig` 不被触碰。
- 测试：现有针对 `status` 非 JSON 输出的断言、以及 skill 模板内容的断言。
- 文档：`README.md` 及 `docs/` 中展示 `loopspec status` 输出的示例。
- 依赖与外部 API：无新增依赖；`--json` 协议不变，因此任何按 JSON 契约集成的调用方不受影响。
