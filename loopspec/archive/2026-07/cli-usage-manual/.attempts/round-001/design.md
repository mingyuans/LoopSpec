## Context

`README.md` 是仓库唯一的文档，覆盖定位、安装、quick start 与 `init` 的交互式选择；CLI 全表面（10 个子命令、参数、`--json` 响应字段、15 个错误码）与两份配置格式（`config.yaml` 6 字段、`schema.yaml` 的节点/gate/tracks 全字段与加载期语义校验）没有任何文档，今天只能读 `src/loopspec/` 获得。

约束与现状：

- **两类读者，一份内容**。人类要"能上手 + 能自定义 schema"；LLM/Agent 要"能靠文档独立驱动 `status → instructions → 写产物` 循环，并能自己写出合法的 `schema.yaml`"。二者对同一事实的需求一致，差异只在**检索方式**（人类顺序阅读、LLM 局部读取），因此不做两套文档。
- **事实源在代码里**。`cli.py`（Typer 命令树）、`models.py`（Pydantic 模型 + alias）、`errors.py`（错误码）、`schema_loader.py`（语义校验）、`paths.py`（路径安全）是唯一权威；`openspec/specs/` 下 10 份 spec 是开发者契约，不是用户手册。
- **文档最大的失效模式是漂移**，而不是写得不够多。本仓库已有 `make test` / `make lint` 门禁，可以把"文档覆盖代码"变成测试。
- **纯文档变更**：`src/loopspec/**` 不动，无新增依赖（`pytest` + `pyyaml` + 项目自身的 `load_schema`/`WorkflowConfig` 已足够）。

## Goals / Non-Goals

**Goals:**

- 一份 `docs/` 手册，读完能回答四个问题：loopspec 是什么 / 提供哪些能力 / 每条命令怎么用 / 两份配置每个字段怎么写。
- `config.yaml` 与 `schema.yaml` 的**字段级**参考：类型、必填性、默认值、校验规则、失败时的错误码，配可直接复制运行的示例。
- 一份显式的 Agent 驱动契约（`docs/agent-protocol.md`），使 LLM 不必读源码即可跑完主循环与 gate 失败支线。
- 文档与代码的一致性由测试保证：新增命令/参数/字段/错误码而漏写文档时，`make test` 失败。
- 每个文档文件自包含，可单独喂给 LLM 而不丢上下文。

**Non-Goals:**

- 不生成 HTML/静态站点，不引入 `mkdocs`/`sphinx` 或任何新依赖。
- 不从 Typer 自动生成 CLI 参考（生成不出 `--json` 响应字段表与用法示例）。
- 不改动任何 CLI 行为、`--json` 结构、schema 语义或脚手架行为。
- 不做 i18n（单一语言版本）；不写教程式长篇 walkthrough（quick start 留在 README）。
- 不在本变更内修复实现与 spec 的冲突（若发现，记录到 Open Questions）。

## Decisions

### D1 文档集布局：多文件 + 索引，按"读者要解决的问题"切分

| 文件 | 覆盖范围 | 主要读者 |
| --- | --- | --- |
| `docs/README.md` | 索引：每篇一句话说明覆盖范围与适用读者 | 两者（唯一入口） |
| `docs/overview.md` | 是什么 / 解决什么问题 / 核心模型 / 术语表 | 两者 |
| `docs/cli-reference.md` | 全命令：语法、参数表、`--json` 字段表、退出码、错误码总表 | 两者 |
| `docs/configuration.md` | `config.yaml` 全字段 + 解析优先级 + 4 个递进示例 | 两者 |
| `docs/schema-reference.md` | `schema.yaml` 全字段 + 语义校验清单 + 手写最小 schema 示例 | 两者 |
| `docs/agent-protocol.md` | 主循环 / 回退支线 / `tracks` / `approval` 禁令 / `state.md` 约定 | LLM 为主 |
| `docs/workflows/secure-spec-driven.md` | 内置 schema 的节点图与 7 节点语义、三个 gate 的取值理由 | 两者 |

**为什么不是单文件**：CLI 参考、config 参考、schema 参考三块各自都长，合成一份会让 LLM 每次局部提问都读入大量无关章节；也与本仓库既有的"按能力切分 spec"习惯一致。
**为什么 `docs/workflows/` 单独一层**：`schema-reference.md` 讲"怎么写一份 schema"（格式），`workflows/secure-spec-driven.md` 讲"内置这份 schema 是什么"（实例）。两者混写会让想自定义 schema 的读者被内置节点细节淹没；分层后也为未来新增内置 schema 留了位置。
**替代方案**：单文件 `docs/MANUAL.md`（否决：LLM 局部读取成本高）；把内容并回 `README.md`（否决：README 已是入口，继续膨胀会淹没 quick start）。

### D2 双读者的写法约定（同一份内容同时满足两者）

统一以下可检查的约定，写进 `usage-docs` 的 spec：

- 每个文件**首屏**给出 `> 覆盖范围：...` 与 `> 适用读者：...` 两行，让 LLM 单文件读取时立刻知道边界。
- 所有配置字段以**表格**呈现，列固定为：字段 / 类型 / 必填 / 默认值 / 说明；字段名写作 `` `name` ``（表格首列），使一致性测试可用结构化模式匹配而非裸字符串包含。
- 所有代码块标注语言（```yaml / ```bash / ```json）；示例可直接复制运行，不使用 `...` 省略号占位（需要省略时用注释说明省略了什么）。
- 不使用图片、emoji、框线表格与 ASCII 图；层级用 Markdown 标题（最深三级），列表用 `-`。
- 术语首次出现给一句定义并链到 `docs/overview.md#术语表`；跨文档用**仓库内相对链接**（可在 GitHub 与本地 IDE 同时跳转）。
- 每条命令一节，节标题固定为 `## loopspec <command>`，使 LLM 与测试都能按命令名定位。

**替代方案**：为 LLM 单独产出 `docs/llms.txt` 或 JSON 化的字段清单（否决：等于第二份事实源，且 `docs/README.md` 本身已是纯文本索引；`--json` 输出本身已是机器契约）。

### D3 单一事实源与去重

- CLI 细节只存在于 `docs/cli-reference.md`；`README.md` 收敛为"定位 + 安装 + quick start + 指向 `docs/README.md`"，删除与手册重复的 CLI/配置细节。
- `docs/` 面向使用者，**不复制** `openspec/specs/` 的 SHALL 语句；需要时以链接引用 spec 文件，避免规范与手册双份维护后互相矛盾。
- 默认值（如 workflow home 默认 `./loopspec`）在文档中出现处由一致性测试对齐代码常量（`cli.DEFAULT_HOME`、`DEFAULT_SCHEMA_NAME`、Pydantic 字段默认值），不允许手写数字/路径漂移。

### D4 一致性测试：单向覆盖（代码 → 文档）

`tests/test_docs_consistency.py`，四组断言：

1. **命令与参数覆盖**：用 `typer.main.get_command(app)` 取到命令树，递归遍历 `.commands` 与 `.params`，断言每个命令有 `## loopspec <command>` 小节，且每个 `--flag` 出现在该小节内。
   *关键实现约束*：本项目的 `typer==0.27` **把 click 内置为 `typer._click`，顶层 `import click` 会 `ModuleNotFoundError`*（已实测）。因此测试只允许经由 `typer.main.get_command` 获取命令对象，通过鸭子类型访问 `.commands`/`.params`/`.opts`，**不得** `import click`，也不得依赖 `typer._click` 私有路径。
2. **模型字段覆盖**：遍历 `WorkflowConfig`/`SchemaSelectionSpec`/`ConfigSchemaRef` → `docs/configuration.md`，`WorkflowSchema`/`NodeSpec`/`GateSpec`/`GateOutputs`/`GateTemplates`/`OnFailSpec` → `docs/schema-reference.md`。字段名取 Pydantic `model_fields` 的 **alias 优先**（`schema_name` 的对外名是 `schema`，`pass_` 是 `pass`——文档必须写 YAML 里真实出现的名字）。
3. **错误码覆盖**：遍历 `LoopspecError` 的全部子类，断言每个 `code` 出现在 `docs/cli-reference.md` 的错误码表中。
4. **示例可校验**：提取文档中被标记的 YAML 示例块，`config` 类交给 `WorkflowConfig.model_validate`，`schema` 类交给 `WorkflowSchema.model_validate`（完整 schema 目录级示例另在 tmp 目录物化 `templates/`+`instructions/` 后过 `load_schema`），断言不抛异常。

**为什么单向**：文档必然包含 Typer 之外的事实（`NO_COLOR`、非 TTY 降级、目录约定、术语），反向断言"文档不得出现代码里没有的名字"会持续误报。单向覆盖精确命中真正想防的失效：**改了代码忘了改文档**。

**示例块标记约定**：可校验的块在 fenced code block **前一行**加 HTML 注释，如 `<!-- loopspec:example=config -->` / `=schema` / `=schema-dir`。用 HTML 注释而非块内 `#` 注释，是为了不污染"复制即可用"的内容；渲染后人类不可见，而 LLM 与测试都能读到。未标记的 YAML 块视为片段，不参与校验（片段仍应语法合法，但不必是完整文档）。

### D5 `make docs-check`

`Makefile` 新增 `docs-check: uv run pytest tests/test_docs_consistency.py -v`，`make test` 依旧覆盖它（`testpaths = ["tests"]`）。用途是改完 CLI 后快速单独验证文档，不改变现有 target 语义。

### D6 内容深度的判定标准（避免"写了但不够用"）

每个参考文档以"读者不必打开 `src/` 即可完成任务"为验收线，具体落到 spec 的可检查要求：

- `cli-reference.md`：每条命令给出至少一个完整的 `--json` 响应示例（真实运行产出，不手写臆造）。
- `configuration.md`：给出 `schema` / `schemas` / `--schema` / `.workflow.yaml` 四者的**优先级表**（`new` 与既有 change 两条路径规则不同，这是最容易踩错的地方）。
- `schema-reference.md`：列出加载期全部语义校验（唯一 ID、`requires` 存在性、无环、plain 节点必须有 `generates`+`template`、gate 的 pass/fail 必须是不同且非 glob 的具体路径、模板/指令必须存在且不越出 `templates/`、`instructions/`、保留输出名、`on_fail.reset` 必须是 gate 的祖先、`tracks` 必须是某祖先节点 `generates` 的具体文件），每条注明触发的错误码。
- `agent-protocol.md`：明确 `tracks` 节点"写完 pass 报告但 checkbox 未全勾 → 仍为 `ready`，`archive` 会拒绝"这一反直觉行为，以及 `approval` 节点"无法联系人类时保持 `ready`、禁止代替人类批准"。

## Risks / Trade-offs

- **[文档随代码漂移]** → D4 的单向覆盖测试纳入 `make test`；默认值/命令/字段/错误码四类高频漂移点全部由代码反查。
- **[字符串包含判断产生假阳性通过]**（字段名恰好出现在无关句子里就算"已文档化"）→ 字段断言要求匹配表格首列形态（`| \`name\` |`）而非裸子串；命令参数断言限定在该命令的小节范围内。
- **[依赖 Typer 内部结构导致测试脆弱]** → 只用 `typer.main.get_command` 这一公开入口 + 鸭子类型访问；已实测 `import click` 在本环境不可用，把"禁止 import click / 禁止 `typer._click`"写成显式约束。Typer 若变更结构，测试失败可见（不是静默通过），可接受。
- **[手册与 `openspec/specs/` 成为两份事实源]** → D3 规定 docs 只链接不复制 SHALL 语句；spec 面向开发者契约，docs 面向使用者。
- **[文档体量增大 LLM 上下文成本]** → D1 拆分 + D2 的首屏"覆盖范围/适用读者"，使 LLM 能只取需要的一两个文件。代价是跨文档跳转变多，用相对链接与统一术语表缓解。
- **[`--json` 示例过期]** → 示例要求由真实运行产出；一致性测试只校验 YAML 示例，**JSON 响应示例不做自动校验**（需要构造完整 change 目录，成本高于收益），改为在 spec 中要求响应字段表逐字段列出，字段名漂移由 D4 第 2/3 组间接兜住其中的模型字段部分。这是本设计已知的覆盖缺口，明确接受。
- **[README 收敛后老链接失效]** → 只删除重复内容、保留全部现有锚点标题结构；README 顶部新增"完整手册见 `docs/`"。

## Security Notes（供 security gate 审阅）

本变更不触及认证、授权、密钥或任何外部集成；无网络调用、无新依赖。仍有三处与安全相关，明确约束：

- **文档示例中不得出现任何真实凭据**（token/密钥/内网地址/真实用户名）。所有示例只使用仓库内相对路径与占位名（`add-payment`、`my-schema`）。
- **一致性测试只读仓库内文件并做纯解析**：`yaml.safe_load` + Pydantic 校验；**严禁执行文档中的任何 shell 命令**（`docs/` 的 ```bash 块只作为文本被跳过），避免把文档变成任意命令执行面。`schema-dir` 类示例只在 pytest `tmp_path` 下物化文件后调用 `load_schema`，不写入仓库内路径。
- **文档需要正面说明路径安全规则**：`artifacts_dir`、`schemas[*].path`、`node.template`、`instruction.file`、`tracks` 全部要求安全相对路径（非绝对、不含 `..`），且模板/指令必须留在 `templates/`、`instructions/` 之内，越界报 `config_invalid` / `schema_invalid`。把这条写进手册是防止用户配出越界路径的正向措施，而不是新增攻击面。

## Migration Plan

纯新增文档 + 一处测试 + 两处小改，无数据迁移、无运行时行为变化，可分步落地且任一步都不破坏现有测试：

1. 写 `docs/overview.md`、`docs/cli-reference.md`、`docs/configuration.md`、`docs/schema-reference.md`、`docs/agent-protocol.md`、`docs/workflows/secure-spec-driven.md`（`--json` 示例由真实运行 `loopspec` 采集）。
2. 写 `docs/README.md` 索引，补齐相对链接。
3. 加 `tests/test_docs_consistency.py`，跑 `make test` 直到绿；测试暴露的遗漏回填到步骤 1 的文档。
4. 收敛 `README.md` 为入口并链接手册；`Makefile` 增 `docs-check`。

**回滚**：删除 `docs/`、`tests/test_docs_consistency.py`，还原 `README.md` 与 `Makefile` 两处改动即可，无残留状态。

## Open Questions

- `docs/README.md` 之外是否还需要 `docs/llms.txt` 一类的 LLM 专用索引？当前决定不需要（D2），若后续实际使用中 LLM 定位困难再补。
- `--json` 响应示例是否值得做自动校验（构造 fixture change 目录后比对字段集合）？本次接受缺口（Risks 一节已记录），留作后续变更。
- 若撰写过程中发现 `src/loopspec/` 实现与 `openspec/specs/` 的某条 SHALL 冲突：本变更以**实现**为准撰写文档，并在此处追加记录，不改代码。
