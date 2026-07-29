## Context

`README.md` 是仓库唯一的文档，覆盖定位、安装、quick start 与 `init` 的交互式选择；CLI 全表面（10 个子命令、参数、`--json` 响应字段、15 个错误码）与两份配置格式（`config.yaml` 6 字段、`schema.yaml` 的节点/gate/tracks 全字段与加载期语义校验）没有任何文档，今天只能读 `src/loopspec/` 获得。

约束与现状：

- **两类读者，一份内容**。人类要"能上手 + 能自定义 schema"；LLM/Agent 要"能靠文档独立驱动 `status → instructions → 写产物` 循环，并能自己写出合法的 `schema.yaml`"。二者对同一事实的需求一致，差异只在**检索方式**（人类顺序阅读、LLM 局部读取），因此不做两套内容。
- **两个语言版本（round 1 人类反馈新增）**。文档集必须提供中文与英文两版且内容等价。这把"防漂移"从"文档 vs 代码"一个维度，扩展成"文档 vs 代码"与"中文版 vs 英文版"两个维度——后者是本轮设计新增的主要复杂度来源。
- **事实源在代码里**。`cli.py`（Typer 命令树）、`models.py`（Pydantic 模型 + alias）、`errors.py`（错误码）、`schema_loader.py`（语义校验）、`paths.py`（路径安全）是唯一权威；`openspec/specs/` 下 10 份 spec 是开发者契约，不是用户手册。
- **文档最大的失效模式是漂移**，而不是写得不够多。本仓库已有 `make test` / `make lint` 门禁，可以把"文档覆盖代码"与"两版等价"都变成测试。
- **纯文档变更**：`src/loopspec/**` 不动，无新增依赖（`pytest` + `pyyaml` + 项目自身的 `load_schema`/`WorkflowConfig` 已足够）。

## Goals / Non-Goals

**Goals:**

- 一份 `docs/` 手册，读完能回答四个问题：loopspec 是什么 / 提供哪些能力 / 每条命令怎么用 / 两份配置每个字段怎么写。
- **中英双语并列，两版内容等价**，且"等价"落到可自动断言的结构化事实上，而不是靠人工承诺。
- `config.yaml` 与 `schema.yaml` 的**字段级**参考：类型、必填性、默认值、校验规则、失败时的错误码，配可直接复制运行的示例。
- 一份显式的 Agent 驱动契约（`agent-protocol.md`），使 LLM 不必读源码即可跑完主循环与 gate 失败支线。
- 文档与代码、以及两个语言版本之间的一致性由测试保证：新增命令/参数/字段/错误码而漏写文档，或只更新了一个语言版本，`make test` 都失败。
- 每个文档文件自包含，可单独喂给 LLM 而不丢上下文。

**Non-Goals:**

- 不生成 HTML/静态站点，不引入 `mkdocs`/`sphinx` 或任何新依赖。
- **不引入 i18n 框架、翻译工具链或机器翻译流水线**：两个语言版本是并列的手写 Markdown 目录，不做 gettext/po、不做构建期合成。
- 不支持 zh/en 之外的第三种语言（本变更只固定"如何并列维护多语言"的机制；新增语言是后续变更）。
- 不从 Typer 自动生成 CLI 参考（生成不出 `--json` 响应字段表与用法示例）。
- 不改动任何 CLI 行为、`--json` 结构、schema 语义或脚手架行为。
- 不写教程式长篇 walkthrough（quick start 留在 README）。
- 不在本变更内修复实现与 spec 的冲突（若发现，记录到 Open Questions）。

## Decisions

### D1 双语布局：语言并列子目录，跨语言文件名完全同名

```
docs/
  README.md                 # 唯一的非语言目录文件：极简双语语言入口
  en/
    README.md               # 英文索引
    overview.md
    cli-reference.md
    configuration.md
    schema-reference.md
    agent-protocol.md
    workflows/secure-spec-driven.md
  zh/
    README.md               # 中文索引，文件名与 en/ 逐一同名
    overview.md
    cli-reference.md
    configuration.md
    schema-reference.md
    agent-protocol.md
    workflows/secure-spec-driven.md
```

**为什么同名并列目录**：跨语言等价性因此退化为**机械的集合比对**——"文件清单相等"是一行断言（`en/` 与 `zh/` 的相对路径集合相等），"某篇漏译"必然当场失败；一致性测试的其余四组断言也能用同一份代码对两个语言目录分别跑，不需要按语言分叉。

**否决 文件名后缀（`cli-reference.md` + `cli-reference.zh.md`）**：两版混放在同一目录，相对链接容易在语言间交叉（中文页链到英文页而不自知）；"漏译"表现为少一个文件而非集合不等，需要额外的命名约定解析；`workflows/` 子目录还要再叠一层后缀。

**否决 单文件双语并排（同一文件内中英分节）**：人类要滚动跳过另一种语言；LLM 每次局部读取都吞双倍 token，直接抵消 D3 拆分文件所换来的收益；代码块会在同一文件里重复两遍，使"示例校验"与"示例逐字相等"两组断言互相打架。

**否决 只翻译索引 / 部分翻译**：人类要求两版等价，不是"中文导览 + 英文正文"。

**顶层 `docs/README.md` 保持极简且本身双语**：只承担语言选择与一句话导航（两行链接 + 一句说明），不承载任何事实性内容——否则它会成为第三份需要同步维护的内容。

### D2 英文为规范源，中文为等价译本，但两版受同一套断言约束

`docs/en/**` 是 normative source：`README.md`、代码注释、CLI `--help` 文案、错误码的 `fix` 建议全是英文，英文版与实现术语同源，能避免"中文术语 → 英文标识符"的二次翻译损耗。`docs/zh/**` 是等价译本。

但**中文版不是次要文档**：它必须通过与英文版完全相同的全部一致性断言（命令覆盖、字段覆盖、错误码覆盖、示例可校验），加上跨语言等价断言。"规范源"只决定**撰写顺序与冲突时以谁为准**，不降低任何一版的质量要求。

撰写顺序因此固定为**先 en 后 zh**：英文版要与代码术语反复对照（这是主要工作量），中文版是在已定稿的事实之上做等价转写。反序会导致中文先行确定措辞、英文再回译，术语反而更容易与代码脱节。

### D3 文档集内部布局：多文件 + 索引，按"读者要解决的问题"切分

每个语言目录内固定 7 个文件：

| 文件 | 覆盖范围 | 主要读者 |
| --- | --- | --- |
| `<lang>/README.md` | 索引：每篇一句话说明覆盖范围与适用读者 | 两者（语言内入口） |
| `<lang>/overview.md` | 是什么 / 解决什么问题 / 核心模型 / 术语表 | 两者 |
| `<lang>/cli-reference.md` | 全命令：语法、参数表、`--json` 字段表、退出码、错误码总表 | 两者 |
| `<lang>/configuration.md` | `config.yaml` 全字段 + 解析优先级 + 4 个递进示例 | 两者 |
| `<lang>/schema-reference.md` | `schema.yaml` 全字段 + 语义校验清单 + 手写最小 schema 示例 | 两者 |
| `<lang>/agent-protocol.md` | 主循环 / 回退支线 / `tracks` / `approval` 禁令 / `state.md` 约定 | LLM 为主 |
| `<lang>/workflows/secure-spec-driven.md` | 内置 schema 的节点图与 7 节点语义、三个 gate 的取值理由 | 两者 |

**为什么不是单文件**：CLI 参考、config 参考、schema 参考三块各自都长，合成一份会让 LLM 每次局部提问都读入大量无关章节；也与本仓库既有的"按能力切分 spec"习惯一致。双语之后这一点更明显：单文件方案的体量会直接翻倍。
**为什么 `workflows/` 单独一层**：`schema-reference.md` 讲"怎么写一份 schema"（格式），`workflows/secure-spec-driven.md` 讲"内置这份 schema 是什么"（实例）。两者混写会让想自定义 schema 的读者被内置节点细节淹没；分层后也为未来新增内置 schema 留了位置。

### D4 双读者的写法约定（同一份内容同时满足人类与 LLM）

统一以下可检查的约定，写进 `usage-docs` 的 spec：

- 每个文件**首屏**给出三样东西：覆盖范围一行、适用读者一行、**指向对侧语言同名文件的链接**一行，让 LLM 单文件读取时立刻知道边界与另一语言版本的位置。
- 所有配置字段以**表格**呈现，列固定为五列且**顺序固定**：字段 / 类型 / 必填 / 默认值 / 说明；字段名 SHALL 出现在**首列**并以反引号包裹。表头词按语言固定（en：`Field` / `Type` / `Required` / `Default` / `Description`；zh：`字段` / `类型` / `必填` / `默认值` / `说明`），但一致性测试按**列位置**而非表头文字定位字段名，使断言与语言无关。
- 所有代码块标注语言（```yaml / ```bash / ```json）；示例可直接复制运行，不使用 `...` 省略号占位（需要省略时用注释说明省略了什么）。
- 不使用图片、emoji、框线表格与 ASCII 图；层级用 Markdown 标题（最深三级），列表用 `-`。
- 术语首次出现给一句定义并链到同语言目录的 `overview.md` 术语表锚点（英文 `#glossary` / 中文 `#术语表`）。
- 每条命令一节，节标题固定为 `## loopspec <command>`——**两种语言都用这个英文标题**，因为它是标识符而非散文；LLM 与测试都能按命令名跨语言定位。
- 跨文档引用使用**同语言目录内**的相对链接；唯一允许跨语言目录的链接是首屏的语言切换链接与 `docs/README.md` 的两条入口链接。这条既防"中文页把读者甩到英文页"，也让链接检查可以断言。

**替代方案**：为 LLM 单独产出 `llms.txt` 或 JSON 化的字段清单（否决：等于第三、四份事实源，双语之后翻倍；`<lang>/README.md` 本身已是纯文本索引，`--json` 输出本身已是机器契约）。

### D5 单一事实源与去重

- CLI 细节只存在于 `<lang>/cli-reference.md`；`README.md` 收敛为"定位 + 安装 + quick start + 指向 `docs/README.md`"，删除与手册重复的 CLI/配置细节。
- `docs/` 面向使用者，**不复制** `openspec/specs/` 的 SHALL 语句；需要时以链接引用 spec 文件，避免规范与手册双份维护后互相矛盾。
- 默认值（如 workflow home 默认 `./loopspec`）在文档中出现处由一致性测试对齐代码常量（`cli.DEFAULT_HOME`、`DEFAULT_SCHEMA_NAME`、Pydantic 字段默认值），不允许手写路径漂移；两个语言版本各自受此约束。

### D6 一致性测试：四组"代码 → 文档"断言按语言分别执行，加一组跨语言等价断言

`tests/test_docs_consistency.py`。前四组对 `docs/en` 与 `docs/zh` **各跑一遍**（参数化 lang）：

1. **命令与参数覆盖**：用 `typer.main.get_command(app)` 取到命令树，递归遍历 `.commands` 与 `.params`，断言每个命令有 `## loopspec <command>` 小节，且每个 `--flag` 出现在该小节内。
   *关键实现约束*：本项目的 `typer==0.27` **把 click 内置为 `typer._click`，顶层 `import click` 会 `ModuleNotFoundError`*（已实测）。因此测试只允许经由 `typer.main.get_command` 获取命令对象，通过鸭子类型访问 `.commands`/`.params`/`.opts`，**不得** `import click`，也不得依赖 `typer._click` 私有路径。
2. **模型字段覆盖**：`WorkflowConfig`/`SchemaSelectionSpec`/`ConfigSchemaRef` → `<lang>/configuration.md`，`WorkflowSchema`/`NodeSpec`/`GateSpec`/`GateOutputs`/`GateTemplates`/`OnFailSpec` → `<lang>/schema-reference.md`。字段名取 Pydantic `model_fields` 的 **alias 优先**（`schema_name` 的对外名是 `schema`，`pass_` 是 `pass`——文档必须写 YAML 里真实出现的名字）。
3. **错误码覆盖**：遍历 `LoopspecError` 的全部子类，断言每个 `code` 出现在 `<lang>/cli-reference.md` 的错误码表中。
4. **示例可校验**：提取文档中被标记的 YAML 示例块，`config` 类交给 `WorkflowConfig.model_validate`，`schema` 类交给 `WorkflowSchema.model_validate`，`schema-dir` 类在 tmp 目录物化 `templates/`+`instructions/` 后过 `load_schema`。

第五组是**跨语言等价断言**（`en` vs `zh`）：

5. a) `en/**` 与 `zh/**` 的相对路径集合相等；b) 两版 `cli-reference.md` 的 `## loopspec <command>` 小节标题集合相等；c) 每对同名文件的字段表首列标识符集合相等；d) 两版错误码集合相等；e) 带标记的 YAML 示例块**按出现顺序逐字相等**；f) 每篇首屏含指向对侧语言同名文件的相对链接且目标存在；g) 除首屏语言链接与 `docs/README.md` 外，不存在跨语言目录的链接。

**为什么"代码 → 文档"只做单向**：文档必然包含 Typer 之外的事实（`NO_COLOR`、非 TTY 降级、目录约定、术语），反向断言"文档不得出现代码里没有的名字"会持续误报。单向覆盖精确命中真正想防的失效：**改了代码忘了改文档**。
**为什么第五组能做双向**：跨语言比对的两侧都是文档，且比对对象限定为标识符与示例这类**闭集**，不涉及散文，因此双向集合相等是精确而非近似的。

**示例块标记约定**：可校验的块在 fenced code block **前一行**加 HTML 注释，如 `<!-- loopspec:example=config -->` / `=schema` / `=schema-dir`。用 HTML 注释而非块内 `#` 注释，是为了不污染"复制即可用"的内容；渲染后人类不可见，而 LLM 与测试都能读到。未标记的 YAML 块视为片段，不参与校验。标记本身**不翻译**，两版一致。

**示例块内不得含翻译性注释**：因为第五组 (e) 要求两版示例逐字相等。需要解释示例的话，把解释写在示例块**外面**的散文里。

### D7 `make docs-check`

`Makefile` 新增 `docs-check: uv run pytest tests/test_docs_consistency.py -v`，`make test` 依旧覆盖它（`testpaths = ["tests"]`）。用途是改完 CLI 或补完译本后快速单独验证，不改变现有 target 语义。

### D8 内容深度的判定标准（避免"写了但不够用"）

每个参考文档以"读者不必打开 `src/` 即可完成任务"为验收线，具体落到 spec 的可检查要求（两个语言版本同等适用）：

- `cli-reference.md`：每条命令给出至少一个完整的 `--json` 响应示例（真实运行产出，不手写臆造；两版逐字相同）。
- `configuration.md`：给出 `schema` / `schemas` / `--schema` / `.workflow.yaml` 四者的**优先级表**（`new` 与既有 change 两条路径规则不同，这是最容易踩错的地方）。
- `schema-reference.md`：列出加载期全部语义校验（唯一 ID、`requires` 存在性、无环、plain 节点必须有 `generates`+`template`、gate 的 pass/fail 必须是不同且非 glob 的具体路径、模板/指令必须存在且不越出 `templates/`、`instructions/`、保留输出名、`on_fail.reset` 必须是 gate 的祖先、`tracks` 必须是某祖先节点 `generates` 的具体文件），每条注明触发的错误码。
- `agent-protocol.md`：明确 `tracks` 节点"写完 pass 报告但 checkbox 未全勾 → 仍为 `ready`，`archive` 会拒绝"这一反直觉行为，以及 `approval` 节点"无法联系人类时保持 `ready`、禁止代替人类批准"。

## Risks / Trade-offs

- **[文档随代码漂移]** → D6 前四组单向覆盖测试纳入 `make test`；默认值/命令/字段/错误码四类高频漂移点全部由代码反查，且两个语言版本各查一遍。
- **[两个语言版本互相漂移]**（只改了英文版忘了中文版）→ D6 第五组跨语言等价断言：漏译一篇、少一个字段、少一个错误码、示例改了一边，都会失败。**残余风险：散文部分不做逐句比对**，中文散文可能落后于英文散文而测试仍绿——这是刻意的取舍（逐句比对需要对齐机制或翻译记忆，成本远超收益），由人工 review 兜底，并在 spec 中明确等价性只覆盖结构化事实。
- **[翻译量翻倍导致维护成本上升]** → D2 固定单一规范源（英文）与撰写顺序；D4 规定标识符（命令名、字段名、错误码、示例、标记注释、`## loopspec <command>` 标题）**不翻译**，把需要翻译的部分压缩到散文与表格"说明"列。
- **[表头词硬编码使测试与语言耦合]** → D4 规定按**列位置**而非表头文字定位字段名；两种语言的表头词固定并写进 spec，测试中集中为一处常量，新增语言时只需扩一个映射。
- **[字符串包含判断产生假阳性通过]**（字段名恰好出现在无关句子里就算"已文档化"）→ 字段断言要求匹配表格首列形态而非裸子串；命令参数断言限定在该命令的小节范围内。
- **[依赖 Typer 内部结构导致测试脆弱]** → 只用 `typer.main.get_command` 这一公开入口 + 鸭子类型访问；已实测 `import click` 在本环境不可用，把"禁止 import click / 禁止 `typer._click`"写成显式约束。Typer 若变更结构，测试失败可见（不是静默通过），可接受。
- **[跨语言链接把读者甩到另一语言]** → D4 规定跨文档链接只在同语言目录内，语言切换只走首屏链接；D6 第五组 (g) 断言之。
- **[手册与 `openspec/specs/` 成为两份事实源]** → D5 规定 docs 只链接不复制 SHALL 语句；spec 面向开发者契约，docs 面向使用者。
- **[文档体量增大 LLM 上下文成本]** → D3 拆分 + D4 的首屏声明，使 LLM 只取需要的一两个文件；语言目录并列还额外保证 LLM 不会一次读到两种语言的同一内容（这是 D1 否决单文件双语的直接收益）。
- **[`--json` 示例过期]** → 示例要求由真实运行产出；一致性测试只校验 YAML 示例，**JSON 响应示例不做自动校验**（需要构造完整 change 目录，成本高于收益），改为在 spec 中要求响应字段表逐字段列出，字段名漂移由 D6 第 2/3 组间接兜住其中的模型字段部分；跨语言方面 JSON 示例仍受第五组 (e) 的逐字相等约束。这是本设计已知的覆盖缺口，明确接受。
- **[README 收敛后老链接失效]** → 只删除重复内容、保留全部现有锚点标题结构；README 顶部新增"完整手册见 `docs/`"。

## Security Notes（供 security gate 审阅）

本变更不触及认证、授权、密钥或任何外部集成；无网络调用、无新依赖。双语化不引入新的安全面（不引入翻译服务调用、不引入构建期合成）。仍有四处与安全相关，明确约束：

- **文档示例中不得出现任何真实凭据**（token/密钥/内网地址/真实用户名）。所有示例只使用仓库内相对路径与占位名（`add-payment`、`my-schema`）。该检查对两个语言版本同等执行。
- **一致性测试只读仓库内文件并做纯解析**：`yaml.safe_load` + Pydantic 校验；**严禁执行文档中的任何 shell 命令**（```bash 块只作为文本被跳过），避免把文档变成任意命令执行面。
- **`schema-dir` 类示例只在 pytest `tmp_path` 下物化**，不写入仓库内路径；物化前先用 `paths.is_safe_relative_path` 校验示例里的 `template`/`instruction.file` 文件名，非法则直接断言失败（采纳 round 1 security 审阅的第 1 条建议，防止示例被误改成 `../../x.md` 后写入逸出临时目录）。
- **文档需要正面说明路径安全规则**：`artifacts_dir`、`schemas[*].path`、`node.template`、`instruction.file`、`tracks` 全部要求安全相对路径（非绝对、不含 `..`），且模板/指令必须留在 `templates/`、`instructions/` 之内，越界报 `config_invalid` / `schema_invalid`。把这条写进手册是防止用户配出越界路径的正向措施，而不是新增攻击面。

另采纳 round 1 security 审阅的其余建议：凭据断言失败时只报 `文件:行号` 与命中的规则名，不回显命中内容；采集 `--json` 样例时每条命令显式传 `--home <tmpdir>`，避免 `archive`/`rollback` 作用于仓库内真实的工作流主目录。

## Migration Plan

纯新增文档 + 一处测试 + 两处小改，无数据迁移、无运行时行为变化。按"英文全套 → 测试 → 中文全套 → 跨语言断言"推进，使每一步都有可验证的中间状态：

1. 采集事实源：跑一遍全部命令取真实 `--json` 样例（`--home <tmpdir>`），整理模型字段（alias 优先）、语义校验清单、错误码与默认值常量。
2. 写 `docs/en/` 全套 7 篇（规范源）。
3. 加 `tests/test_docs_consistency.py` 的前四组断言，先只对 `en` 执行，跑绿；暴露的遗漏回填英文版。
4. 写 `docs/zh/` 全套 7 篇（照译，标识符与示例逐字沿用）。
5. 把前四组断言参数化到两种语言，加第五组跨语言等价断言，跑绿。
6. 写 `docs/README.md` 双语语言入口；收敛 `README.md` 为入口并链接手册；`Makefile` 增 `docs-check`。

**回滚**：删除 `docs/`、`tests/test_docs_consistency.py`，还原 `README.md` 与 `Makefile` 两处改动即可，无残留状态。

## Open Questions

- 两个语言版本中**散文**部分的等价程度：本设计定为"只保证结构化事实等价，散文不做逐句比对"（见 Risks）。若后续发现中文散文实际落后严重，可考虑追加"段落数量相等"一类的弱结构断言——本轮不做。
- `--json` 响应示例是否值得做自动校验（构造 fixture change 目录后比对字段集合）？本次接受缺口（Risks 已记录），留作后续变更。round 1 曾向人类提出，人类未表态。
- 新增第三种语言时，D4 的表头词映射与 D6 第五组的两两比对是否需要改成"以 en 为基准逐一比对"？本轮只支持 zh/en，按两两比对实现即可，扩展时再改。
- 若撰写过程中发现 `src/loopspec/` 实现与 `openspec/specs/` 的某条 SHALL 冲突：本变更以**实现**为准撰写文档，并在此处追加记录，不改代码。
