## Context

`loopspec status` 目前的输出分支只有一个：`cli._emit(result, as_json)`。`as_json` 为真时 `json.dumps`，为假时对顶层 dict 逐键 `typer.echo(f"{key}: {value}")`。`status` 的 payload 里 `nodes` 是一个 dict 列表，于是非 JSON 模式会把整个节点列表 `str()` 成一行 Python repr——既不是给人看的，也不是给机器解析的。真正的调用方是 `/lpsx:*` skill 里的 LLM，它每一轮循环都执行一次 `status`，因此只能一律加 `--json`。

现状的两个既有约束限定了设计空间：

- `presentation.py` 的模块契约是**人类可读专用**：返回 rich `Text`、带颜色与 glyph、经 `Console` 打印（会解析 markup、按终端宽度 soft-wrap）。其文档字符串明写"Nothing here may be used on a `--json` code path"，并刻意不给任何函数 `as_json` 参数。
- `loopspec-cli` 规格已声明「`--json` 是 LLM/Agent 消费的主协议，人类可读输出为次要形式，二者返回的信息内容 SHALL 保持一致」。本次改动要动的正是这条定位。

`status` 的 payload 形状（本设计需全部覆盖）：顶层 `changeName`/`schemaName`/`artifactsDir`/`schemaPath`/`changeRoot`/`artifactRoot`/`statePath`/`stateExists`/`isComplete`/`nodes`/`pendingRollback`/`nextSteps`；节点条目含 `id`/`status`/`outputPath`/`resolvedOutputPath`/`existingOutputPaths`，并按情况附加 `taskProgress`（声明 `tracks` 时）、`missingDeps`（`blocked` 时）、`gate`（`failed`/`exhausted` 时，内含 `verdict`/`summary`/`blockingIssues`/`rollbacksUsed`/`maxRetries`/`resetDeclared`/`resetClosure`）。gate 节点的 `outputPath`/`resolvedOutputPath` 是 `{pass, fail}` 双路径而非字符串。

## Goals / Non-Goals

**Goals:**
- `loopspec status <change>`（不带 `--json`）输出一份版式固定的纯文本 Markdown 报告，LLM 读完即可判断进度并执行下一条命令，无需解析 JSON。
- 报告与 `--json` 的**信息一致**由机制保证，而不是靠作者手工同步：两者渲染自同一个 payload，且新增字段时测试会失败。
- 报告是纯文本：无 ANSI 颜色、无 glyph、无 spinner，不随终端宽度或 `NO_COLOR` 改变字节。
- `--json` 的字段契约一字不改。

**Non-Goals:**
- 不改 `new`/`rollback`/`history`/`instructions`/`artifacts` 等其他命令的默认输出（`artifacts` 已有自己的人类可读渲染，本次不动）。
- 不引入 `--format` 之类的输出格式开关。
- 不在报告里内联任何产物文件的正文——`loopspec-cli` 已要求 `status` 不返回模板正文，本设计维持该边界（见 R4）。
- 不改 `presentation.py` 既有的人类可读渲染行为（`init`、`artifacts` 的输出保持原样）。

## Decisions

### D1 · 新建 `status_report.py`，不扩展 `presentation.py`

面向 LLM 的渲染与 `presentation.py` 的契约在三处直接冲突：需要**不着色**、需要**不经 rich `Console`**（避免 markup 解析与按宽度 soft-wrap）、需要**字节稳定**。放进 `presentation.py` 就得放宽它"一切都返回带样式的 `Text`"的不变量，而那条不变量正是它防止 markup 注入的结构性保证。

新模块 `src/loopspec/status_report.py` 只做一件事：`render_status_report(payload: dict) -> str`，返回一整串 Markdown 文本，由 `cli.status` 交给 `typer.echo` 原样打印。

**复用而非重写**：控制字符消毒沿用 `presentation.sanitize()`（把 `\x00-\x1f\x7f-\x9f` 改写成可见的 `\xNN`）。这是两个模块的共同需求，不该有第二份实现。

*备选*：在 `presentation.py` 里加 `plain=True` 分支——被否，等于给该模块开一个绕过其安全不变量的后门，且 `Console` 的 soft-wrap 仍在。

### D2 · 单一 payload，两种编码；字段覆盖由测试锁死

`cli.status` 依旧构造现在那个 `result` dict，然后二选一：`as_json` 为真 → `json.dumps`；为假 → `render_status_report(result)`。渲染器只读这个 dict，不重新访问文件系统、不重算状态。

"信息一致"不能靠人盯。渲染器内部声明它已知的顶层键与节点键集合，测试断言该集合与 `status` 实际产出的键集合**相等**。日后给 payload 加字段而没决定它在报告里怎么呈现，测试就会红——强制作者显式处理（呈现它，或把它写进"有意省略"名单）。

*备选*：渲染器接收领域对象（`states`、`loaded.graph`）自行组织——被否，那是第二条数据通路，正是漂移的来源。

### D3 · 版式：标准 Markdown 标题分节，固定节序

顶层 `# LoopSpec Status: <change>`，其下按固定顺序分节：

| 顺序 | 节标题 | 是否恒在 | 内容 |
|---|---|---|---|
| 1 | `## Overview` | 恒在 | schema、change root、`state.md` 是否存在、`isComplete` |
| 2 | `## Nodes` | 恒在 | 逐节点一行的表格（见 D5） |
| 3 | `## Gate Failures` | 条件 | 仅当存在 `failed`/`exhausted` gate |
| 4 | `## Pending Rollback` | 条件 | 仅当 `pendingRollback` 非 null |
| 5 | `## Next Steps` | 恒在 | `nextSteps` 逐条编号列表 |

**恒在 vs 条件的取舍**：`Overview`/`Nodes`/`Next Steps` 三节无条件出现（即便 `nextSteps` 为空也打印占位行），让 LLM 有稳定的锚点；`Gate Failures`/`Pending Rollback` 只在有内容时出现——它们的出现本身就是信号，而空节会让"一切正常"和"有失败但没细节"看起来一样。

用标准 Markdown 标题而非提案讨论中提到的 `--- xxx ---` 形式：`---` 在 Markdown 里是水平线/YAML front-matter 分隔符，用它当节标题会与正文里可能出现的 Markdown 结构混淆；`##` 是 LLM 训练数据中最无歧义的分节记法。**此项列入 Open Questions 交由 `approval` 裁定**，因为它是提出者明确举例过的形态；若被否，改动范围仅限于渲染器里的节标题常量与相应测试。

### D4 · 路径：根目录给绝对路径一次，节点行给相对路径

`Overview` 打印一次 change root 的绝对路径；`Nodes` 表格里的产物路径用相对 artifact root 的形式（即 payload 里的 `outputPath`，正是 schema 声明的相对路径）。理由是 token 成本：七个节点各带一条百余字符的绝对路径，绝大部分是重复前缀，而 LLM 真正要写文件时会去调 `instructions`，那里给的是绝对路径。

例外：`existingOutputPaths`（glob 节点实际匹配到的文件）在表格里以**文件名计数**呈现（如 `3 files`），完整清单留给 `--json` 与 `instructions`。这是本设计唯一一处"信息在报告中被压缩"的地方，需在 spec 中如实写明，不能声称两种输出逐字段等价。

### D5 · 节点用 Markdown 表格，列固定为四列

`| Node | Status | Output | Notes |`。`Notes` 列按节点情况取**恰好一种**内容：`blocked` → `needs: a, b`；有 `taskProgress` → `tasks: 3/12`；`failed`/`exhausted` → `see Gate Failures`；否则空。多种情况互斥（`blocked` 节点不会同时是失败 gate），因此不需要在单元格里堆叠。

表格的代价是**单元格分隔符**：内容里出现 `|` 会撕裂表格。渲染器必须把单元格内的 `|` 转义为 `\|`，换行则已由 `sanitize()` 转成 `\x0a`。change 名受 `KEBAB_RE` 约束不含 `|`，但 `outputPath` 来自 schema 作者、`existingOutputPaths` 来自文件系统，都不受此约束——所以这是必须实现的规则，不是理论洁癖。

*备选*：改用嵌套无序列表，天然无 `|` 问题——被否，七到十个节点的列表比表格长三倍，而表格恰是 LLM 最擅长扫读的密集结构；转义规则只有一行代码，且会被单测直接覆盖。

### D6 · gate 失败详情独立成节，`blockingIssues` 逐条列出

`Gate Failures` 每个失败 gate 一个 `### <gate-id>` 子节，给出 `verdict`、`summary`、`blockingIssues`（无序列表逐条）、`rollbacksUsed / maxRetries`、`resetClosure`。这些正是 LLM 决定"能否回退、要重做哪些节点"所需，且长度不可预测——放进表格单元格必然撕裂版面。

### D7 · 错误路径同样 Markdown 化

`_fail()` 在非 JSON 模式下当前也走 `key: value`。`status` 失败（如 `change_not_found`）时 LLM 拿到的必须同样是可读文本。做法：`_fail` 的非 JSON 分支渲染 `# Error` + `error` / `message` / `fix` 三项。

范围界定：`_fail` 是所有命令共用的，改它会一并改掉其他命令的非 JSON 错误输出。这是可接受且符合意图的（错误文案本就该可读），但要在 spec 里写明这一处是**全命令生效**，避免 review 时误以为越界。`loopspec-cli` 现有的错误码要求只约束"结构化模式下"的 JSON 三字段，不与此冲突。

### D8 · 指向 `status` 的 `nextSteps` 文案去掉 `--json`

`policy.build_next_steps` 与 `new`/`rollback` 的 `nextSteps` 里有若干 "Run \`loopspec status <change> --json\`"。默认输出既然为 LLM 而设，这些自我指涉的提示必须同步去掉 `--json`，否则 CLI 自己在教 LLM 走旧路。

**只改指向 `status` 的那些**。指向 `loopspec instructions ... --json` 的文案保留 `--json`——`instructions` 的默认输出不在本次范围内，改它的提示词会把 LLM 引向一个仍是 `key: value` 的输出。

### D9 · skill 模板同步，旧 skill 平滑降级

`skill_templates.py` 里三处 `loopspec status <change-name> --json` 去掉 `--json`。已经 scaffold 到用户 `.claude/skills/` 等目录下的旧 skill 文件**不会**自动更新，需要用户重跑 `loopspec init`——但旧 skill 带着 `--json` 依然完全可用（JSON 契约未变），所以这是平滑降级而非破坏，不需要迁移脚本或版本门。

## Risks / Trade-offs

- **[默认输出格式是 BREAKING 变更]** → 任何按行 grep `status` 非 JSON 输出的外部脚本会失效。缓解：`--json` 是文档里一贯推荐给程序化调用方的形式（README 与全部 docs 示例都带 `--json`），受众极小；在 spec 与发布说明中如实标注 BREAKING。
- **[表格单元格分隔符撕裂版面]** → 见 D5，转义 `|` 为 `\|`，并对含 `|` 的路径写专门的单测。
- **[报告内容进入 LLM 上下文，构成 prompt injection 面]** → 报告会内插 change 名、schema 名与**文件系统中的路径名**。攻击者若能在 change 目录下创建文件，文件名会出现在 `existingOutputPaths` 里，从而以自然语言形态进入 LLM 上下文（例如一个名为 `ignore-previous-instructions.md` 的文件）。缓解有三层，且都是既有边界的延续而非新发明：① 报告只呈现路径与状态，**绝不内联任何文件正文**（`loopspec-cli` 已要求 `status` 不返回模板正文）；② 全部内插值经 `sanitize()`，控制字符不可能改写终端或伪造换行；③ D4 把 `existingOutputPaths` 压成计数，进一步缩小了攻击者可控文本进入报告的面。残余风险如实接受：`outputPath` 与节点 ID 来自 schema 作者，schema 本就是可信输入（其内容已能直接指挥 LLM）。
- **[两种输出漂移]** → D2 的键集合断言把漂移变成测试失败而非静默不一致。
- **[双语文档必须同步]** → `test_docs_consistency.py` 对 `docs/en` 与 `docs/zh` 做双向集合相等与示例块逐字节比对，改一处 `status` 示例就必须改两处。这是既有约束，任务清单里要显式列出，否则实现阶段必然踩。

## Migration Plan

无持久化数据、无 schema 版本变更、无外部 API 变更，因此没有迁移步骤，只有同步项：

1. 实现 `status_report.py` 与 `cli.status` 的分支切换，`--json` 路径不动。
2. 同步 `policy.py`/`cli.py` 中指向 `status` 的 `nextSteps` 文案（D8）。
3. 同步 `skill_templates.py`（D9）。
4. 同步 `README.md`、`docs/en/**`、`docs/zh/**` 中的 `loopspec status` 示例与 CLI 参考。

回滚策略：改动集中在一个新模块与若干处文案，`git revert` 即可完全回退；`--json` 未被触碰，因此回退不影响任何已按 JSON 契约集成的调用方。

## Open Questions

- **节标题记法**（D3）：标准 Markdown `## Section` vs 提出者举例的 `--- Section ---`。设计选前者并给出理由，但这是提出者明确表达过偏好的点，留待 `approval` 裁定。
- **glob 节点的详略权衡**（D4）：`existingOutputPaths` 压成计数是否可接受，还是 glob 节点应完整列出匹配文件。设计选压缩，交由 `approval` 确认。
