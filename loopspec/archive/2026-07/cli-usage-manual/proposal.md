## Why

`README.md` 是目前唯一的文档，它讲清了"装什么、跑什么"（install / quick start / init 的交互式选择 / 两个非"写文件"节点），但**没有任何一处完整记录过 CLI 表面与配置格式**：

- 10 个子命令（`version`/`init`/`schemas list|show|validate`/`new`/`status`/`instructions`/`rollback`/`history`/`archive`/`bulk-archive`）中只有 6 个在 README 里出现过，`history`、`schemas *`、`version` 从未被提及；`--dry-run`/`--exhausted`/`--include-pending-failures`/`--no-builtin`/`--project-root` 等参数同样没有归档说明。
- `config.yaml` 只有 `artifacts_dir` + `schema` 两行示例被 `init` 生成，而实际支持 6 个字段（含 `schemas` 多候选、`schema_selection`、`context`、`rules`）——这些字段今天只能靠读 `src/loopspec/models.py` 才能发现。
- `schema.yaml` 是本工具的核心可配置面（节点图、`generates`/`template`/`requires`/`instruction`/`gate`/`tracks`、`on_fail` 的三个字段、以及加载期的语义校验与保留路径），README 只用一句话指向 `schemas/secure-spec-driven/schema.yaml` 让读者自己看源码。
- `--json` 是驱动 loopspec 的**主协议**，但 `status`/`instructions` 响应里的字段（`nextSteps`、`pendingRollback`、`taskProgress`、`contextFiles`、`priorAttempts`、`warnings`、gate 的 `verdict`/`rollbacksUsed`）没有任何字段级文档；15 个错误码只存在于 `errors.py` 和 spec 里。

于是两类读者都被卡住：**人类**要自定义工作流就得读 Python 源码；**LLM/Agent** 想自己写一份 schema 或读懂 `status` 响应，只能靠猜或把 `src/` 整个读进上下文——而后者恰恰是这个工具的第一类使用者。同时 `loopspec init` 的收尾已经在打印 `Learn more: https://github.com/mingyuans/LoopSpec`，落地页却没有一份可跳转的手册。

## What Changes

- **新增 `docs/` 文档集**，一份同时面向人类与 LLM 的使用+配置手册，**提供中英两个语言版本**（`docs/en/**` 与 `docs/zh/**` 语言并列子目录、跨语言文件名逐一同名），按"读者要解决的问题"分文件，每个文件自包含（可单独喂给 LLM 而不丢上下文）。以下清单为**每个语言目录内部**的文件构成：
  - `docs/README.md`：极简双语语言入口。只做语言选择与一句话导航，不承载事实性内容。
  - `docs/<lang>/README.md`：该语言版本的索引与导航。列出同语言目录下全部文档、每篇一句话说明其覆盖范围与适用读者。
  - `docs/overview.md`：loopspec 是什么、解决什么问题、核心模型（节点图 / 产物 / gate / 回退 / 状态由文件系统推导）、术语表（workflow home、change、node、gate、artifact root、reset closure、attempts round）。
  - `docs/cli-reference.md`：**全命令参考**。每条命令一节，统一给出用途、语法、参数表（名称/类型/默认值/说明）、`--json` 响应字段表、人类可读输出示例、常见失败与退出码；附错误码总表（15 个码 → 触发条件 → `fix` 建议）。
  - `docs/configuration.md`：**`config.yaml` 全字段参考**。逐字段给出类型、是否必填、默认值、校验规则（kebab-case、安全相对路径、`schema` 必须属于 `schemas[*].name`、名称唯一）、以及 `schema`/`schemas`/`--schema`/`.workflow.yaml` 的优先级解析规则；配 4 个递进示例（最小配置、多 schema 候选 + `schema_selection`、`context` + 按节点 `rules`、`artifacts_dir` 与 `schemas[*].path` 的自定义布局）。
  - `docs/schema-reference.md`：**`schema.yaml` 全字段参考**。顶层字段、`nodes[*]` 全字段、`gate` 与 `on_fail`（`reset`/`max_retries`/`on_exhausted`）、`tracks` 的语义与约束、`instruction` 的两种写法（内联字符串 vs `{file: ...}`）、`generates` 的 glob 支持、`templates/` 与 `instructions/` 的目录约定、保留产物路径（`state.md`/`.workflow.yaml`）、以及加载期全部语义校验清单（含每条失败对应的错误码）；配一个"从零手写最小 schema（2 节点 + 1 gate）"的完整可运行示例。
  - `docs/agent-protocol.md`：**给 LLM/Agent 的驱动契约**。`status → nextSteps → instructions → 写产物 → 回到 status` 的主循环、gate 失败时的 `pendingRollback → rollback → priorAttempts` 支线、`tracks` 节点为何"写完报告仍是 ready"、`approval` 节点禁止代替人类批准、`state.md` 的读写约定，以及每一步该读响应里的哪个字段。
  - `docs/workflows/secure-spec-driven.md`：内置 schema 的节点图、7 个节点各自的产物与语义、三个 gate 的 `reset`/`max_retries` 取值及其理由。
- **`README.md` 收敛为入口**：保留定位、安装、quick start，把 CLI 细节/配置细节替换为指向 `docs/` 的链接，避免同一事实两处维护后漂移。
- **新增文档一致性测试**（`tests/test_docs_consistency.py`），两类断言：
  - **代码 → 文档的单向覆盖**，对每个语言版本分别执行——Typer app 注册的每个命令与参数都出现在 `cli-reference.md`；`WorkflowConfig`/`WorkflowSchema`/`NodeSpec`/`GateSpec`/`OnFailSpec` 的每个字段名都出现在对应参考文档；`errors.py` 的每个错误码都出现在错误码总表；文档中的每个 schema/config YAML 示例块都能被真实的加载器校验通过。
  - **语言版本之间的双向等价**——文件清单、命令小节标题、字段名、错误码四类集合相等，带标记的示例块逐字相等，每篇可跳转到对侧语言同名文件。
- **`Makefile` 新增 `make docs-check`**：只跑文档一致性测试，便于改完 CLI 或补完译本后单独验证。
- 明确非目标：不生成 HTML/静态站点（纯 Markdown，仓库内可读）；不引入文档生成器、i18n 框架或翻译工具链，也不引入任何新依赖；不支持 zh/en 之外的第三种语言；不改动任何 CLI 行为、`--json` 结构或 schema 语义（纯文档 + 测试变更）。

## Capabilities

### New Capabilities
- `usage-docs`: 使用与配置手册的**结构与内容契约**——`docs/` 文档集的双语布局与文件清单、中英两版的等价性要求（哪些内容不翻译、等价性如何被自动断言）、每个 CLI 命令/参数/JSON 响应字段/错误码必须被记录、`config.yaml` 与 `schema.yaml` 的每个字段必须给出类型/必填性/默认值/校验规则、示例必须可校验通过、README 必须作为入口链接到索引、以及文档与代码不漂移、两个语言版本互不漂移的自动化校验要求。

### Modified Capabilities
（无。本变更不修改任何既有能力的 spec 级行为：CLI 命令、`--json` 结构、schema 语义、脚手架行为均保持不变。）

## Impact

- **新增文件**（15 个文档 + 1 个测试）：`docs/README.md`（双语语言入口）；`docs/en/` 与 `docs/zh/` 下各 7 篇同名文件（`README.md`、`overview.md`、`cli-reference.md`、`configuration.md`、`schema-reference.md`、`agent-protocol.md`、`workflows/secure-spec-driven.md`）；`tests/test_docs_consistency.py`。
- **修改文件**：`README.md`（收敛为入口 + 文档链接）、`Makefile`（新增 `docs-check` target）。
- **不涉及**：`src/loopspec/**` 无任何改动，无新增运行时依赖（一致性测试复用已有 `pytest` + `yaml` + 项目自身的 `load_schema`/`WorkflowConfig`）。
- **信息来源**：文档内容以 `src/loopspec/` 实现与 `openspec/specs/` 下 10 份既有 spec 为准；若撰写过程中发现实现与 spec 冲突，记录为 Open Question 而不在本变更内改代码。
- **维护成本**：新增两处需同步更新的面——随 CLI 变更更新文档、以及两个语言版本互相同步。两者都由一致性测试兜底，使漂移在 `make test` 阶段即失败而非事后被用户发现；代价是每次 CLI 变更需要改动两个语言版本（通过"标识符不翻译"把改动量压到散文与说明列）。
