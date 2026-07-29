# Human Approval: CHANGES REQUESTED

## Changes Requested

- `docs/` 文档集必须提供中文（zh）与英文（en）两个语言版本，两版内容等价；原计划只规划了单一语言版本，需要在 `specs/usage-docs/spec.md`、`design.md`、`tasks.md` 三份产物中全部体现。
- 在 `design.md` 中新增一条决策，明确双语的**目录布局**（语言并列的子目录 vs 文件名后缀 vs 单文件双语并排），并说明为何否决其余方案；`specs/usage-docs/spec.md` 中「文档集的文件清单与职责边界」需求的文件清单必须据此重写为双语清单（含语言入口文件的归属）。
- 在 `specs/usage-docs/spec.md` 中新增「双语版本等价性」需求：两个语言版本的文件清单必须一致；命令小节标题、配置/schema 字段名、错误码这三类代码标识符在两版中不翻译且集合必须相等；可校验的 YAML 示例块在两版中必须内容一致；每篇文档必须能跳转到对侧语言的同名文档。每条需求都要配可测的 `#### Scenario`。
- 扩展 `tests/test_docs_consistency.py` 的断言范围：原有四组断言（命令与参数、模型字段、错误码、示例可校验）必须对**每个语言版本**分别执行，并新增一组跨语言等价性断言；`design.md` 的 D4 需相应更新。
- 重排 `tasks.md`：文档撰写任务量从 7 篇变为双语共 14 篇加语言入口，需明确两版的产出顺序（先写哪一版、另一版如何对照）与语言入口文件的任务归属。
- 在 `design.md` 的 Goals / Non-Goals 中把「不做 i18n（单一语言版本）」这条 Non-Goal 删除或改写——该条与本次要求直接冲突，不能留在重做后的产物里。

## Human's Words

> 补充，文档提供 zh/en 两个语言版本约束

（人类未附加任何限定条件或例外；除双语要求外未对 round 1 计划的其他部分提出异议。）

## Summary Presented to the Human

向人类呈现的 round 1 计划摘要包含：

- **问题**：`README.md` 是唯一文档；10 个子命令中 `history`/`schemas *`/`version` 从未被提及；`config.yaml` 实际 6 个字段而仅 2 个有示例；`schema.yaml` 全字段与加载期语义校验只能读 `src/` 获得；`--json` 作为主协议却无字段级文档，15 个错误码只存在于代码与 spec 中。后果是人类要自定义 schema 得读源码，LLM 要驱动循环只能整读 `src/`。
- **能力**：新增 `usage-docs`（文档集的结构与内容契约）；不修改任何既有能力的 spec 级行为。
- **关键决策与取舍**：(1) 多文件 + 索引共 7 篇（`docs/README.md`、`overview.md`、`cli-reference.md`、`configuration.md`、`schema-reference.md`、`agent-protocol.md`、`workflows/secure-spec-driven.md`），取舍是跨文档跳转变多、换取 LLM 局部读取成本低，否决单文件 `MANUAL.md` 与 `mkdocs` 建站；(2) 一份内容服务人类与 LLM 双读者，靠可检查的写法约定落地，否决额外产出 `llms.txt`；(3) 一致性测试做单向覆盖（代码 → 文档）四组断言并纳入 `make test`，取舍是不做反向断言、文档可能残留过时描述；(4) 手写文档而非从 Typer 自动生成，理由是生成不出 `--json` 字段表与用法示例。
- **任务量**：4 组 25 个任务，顺序为采集真实事实源 → 撰写 7 篇文档 → 一致性测试 → 收敛 `README.md`/`Makefile` 并验收。
- **security 结论**：PASS，无阻塞项；接受 4 条非阻塞建议（`schema-dir` 示例物化前校验相对路径安全性、凭据断言失败只报文件与行号、采集样例时显式传 `--home <tmpdir>` 以免 `archive`/`rollback` 作用于仓库内真实工作流主目录、未来可对错误码与字段两类闭集追加反向断言）。
- **明确告知的猜测**：分支名 `19a5-docs-add-cli-gui` 中的 "gui" 被理解为 guide/手册，计划中不含任何图形界面。
- **留给人类的开放问题**：`--json` 响应示例暂不做自动校验（构造 fixture change 目录成本高于收益）是否可接受。

## Suggested Direction

- 双语布局建议优先评估"语言并列子目录"（`docs/en/**` 与 `docs/zh/**` 下文件名完全同名），因为同名可让一致性测试对两版跑同一组断言、并使跨语言等价性退化为机械的集合比对；文件名后缀方案与单文件双语并排方案的代价应在 `design.md` 中说明后再否决。
- 双语等价性的可测抓手在于"代码标识符不翻译"：命令名、字段名、错误码、YAML 示例在两版中本就应逐字相同，因此适合做成集合相等断言；散文部分不做逐句比对。
- 顶层语言入口文件（如 `docs/README.md`）建议保持极简且本身双语，只承担语言选择与一句话导航，避免它成为第三份需要同步维护的内容。
- 人类未就 round 1 的其他决策提出异议，重做时除双语相关部分外应保留原有决策（多文件拆分、单向覆盖的一致性测试、示例标记约定、README 收敛、Makefile 新增 `docs-check`），不要借机改动未被质疑的部分。

## state.md Write-Back

- Decision Log: round 1 - changes requested（要求文档集提供 zh/en 双语版本；verdict 见 `approval/changes-requested.md`）
- Rejected Options: 单一语言版本的 `docs/` 文档集（round 1 计划）；`design.md` 中「不做 i18n」这条 Non-Goal
- Open Questions: 双语目录布局的最终选型（语言并列子目录 / 文件名后缀 / 单文件双语并排）；两个语言版本中散文部分的等价程度要求（逐句对应还是仅要求覆盖同一组事实）；`--json` 响应示例是否自动校验（round 1 提出后人类未表态，仍未决）
- Current Focus: redo specs/design per round 1 feedback
- Artifact Notes: `approval/changes-requested.md` - changes requested
