## 1. 采集事实源（先取真实数据，避免手写臆造）

- [x] 1.1 运行 `loopspec` 全部 10 个命令（`version`/`init`/`schemas list|show|validate`/`new`/`status`/`instructions`/`rollback`/`history`/`archive`/`bulk-archive`）的 `--json`，在临时目录中造一个 change 并制造一次 gate 失败，采集每条命令的真实 JSON 响应样例留作文档示例（**每条命令显式传 `--home <tmpdir>`；只在临时目录操作，不污染仓库工作区，避免 `archive`/`rollback` 作用于仓库内真实工作流主目录**）
- [x] 1.2 从 `src/loopspec/models.py` 整理 `WorkflowConfig`/`ConfigSchemaRef`/`SchemaSelectionSpec` 与 `WorkflowSchema`/`NodeSpec`/`GateSpec`/`GateOutputs`/`GateTemplates`/`OnFailSpec` 的字段清单，逐字段记录类型、必填性、默认值与**对外别名**（`schema`←`schema_name`、`pass`←`pass_`）
- [x] 1.3 从 `src/loopspec/schema_loader.py` 与 `paths.py` 整理加载期全部语义校验，逐条对应到 `errors.py` 的错误码
- [x] 1.4 从 `src/loopspec/errors.py` 整理全部错误码清单，从 `cli.py` 整理默认值常量（`DEFAULT_HOME`、`DEFAULT_SCHEMA_NAME`）
- [x] 1.5 冻结"不翻译清单"：命令名、选项名、字段名、错误码、示例块内容、示例标记注释、文件路径、`## loopspec <command>` 小节标题；以及两种语言的字段表表头词（en：`Field`/`Type`/`Required`/`Default`/`Description`；zh：`字段`/`类型`/`必填`/`默认值`/`说明`）——后续英文版与中文版都以此为准

## 2. 撰写英文版（规范源，`docs/en/`）

- [x] 2.1 写 `docs/en/overview.md`：定位、核心模型（节点图/产物/gate/回退/状态由文件系统推导）、术语表（`#glossary` 锚点，含 workflow home、change、node、gate、artifact root、reset closure、attempts round）
- [x] 2.2 写 `docs/en/cli-reference.md` 的命令部分：每条命令一个 `## loopspec <command>` 小节，含用途、语法、参数表、`--json` 响应字段表、以及来自任务 1.1 的真实响应示例
- [x] 2.3 写 `docs/en/cli-reference.md` 的错误码总表：覆盖全部错误码，每条含触发条件与修复方向；并说明失败契约（退出码 1 + `error`/`message`/`fix`）
- [x] 2.4 写 `docs/en/configuration.md`：`config.yaml` 全字段表（对外名称、五列固定顺序）、校验规则、schema 解析优先级（**区分新建 change 与既有 change 两条路径**）、4 个递进示例并加 `<!-- loopspec:example=config -->` 标记
- [x] 2.5 写 `docs/en/schema-reference.md`：`schema.yaml` 全字段表、`instruction` 两种写法、`generates` 的 glob、`tracks` 语义与约束、`templates/`+`instructions/` 目录约定、保留产物名、语义校验清单（每条注明错误码）
- [x] 2.6 为 `docs/en/schema-reference.md` 补最小可用 schema 完整示例（1 普通节点 + 1 gate）并加 `<!-- loopspec:example=schema-dir -->` 标记，附配套目录结构说明
- [x] 2.7 写 `docs/en/agent-protocol.md`：主循环与每步该读的字段、gate 失败支线（`pendingRollback` → `rollback` → `priorAttempts`）、`tracks` 节点"报告已写但 checkbox 未全勾仍为 ready 且拒绝归档"、`approval` 节点禁止代替人类批准、`state.md` 读写约定
- [x] 2.8 写 `docs/en/workflows/secure-spec-driven.md`：7 节点图表格（类型/依赖/产物）、逐节点语义、三个 gate 的 `reset`/`max_retries`/`on_exhausted` 取值及理由
- [x] 2.9 写 `docs/en/README.md` 索引：逐篇列出同语言目录下的文件 + 一句话覆盖范围 + 适用读者
- [x] 2.10 给 `docs/en/` 全部 7 篇补首屏三件套：覆盖范围、适用读者、指向 `../zh/<同名文件>` 的语言切换链接
- [x] 2.11 自检英文版写法约定：字段表五列固定顺序且字段名在首列反引号、代码块均带语言标注、无图片/emoji/框线、标题不超三级、术语首现链到 `#glossary`、除首屏语言链接外无跨语言链接、示例块内无解释性注释

## 3. 一致性测试（先只对英文版执行）

- [x] 3.1 新建 `tests/test_docs_consistency.py` 骨架与共享 fixture：定位 `docs/` 与语言目录、解析 Markdown 小节与**表格首列**的工具函数（**结构化位置匹配，不用全文裸子串包含；按列位置定位字段名，不依赖表头文字**）
- [x] 3.2 实现命令与参数覆盖断言：经 `typer.main.get_command(app)` 递归遍历命令树与 `.params`（**禁止 `import click`：typer 0.27 已把 click 内置为 `typer._click`，顶层 import 会 ModuleNotFoundError；也禁止依赖 `typer._click` 私有路径**），断言每命令有小节、每选项在其小节内
- [x] 3.3 实现模型字段覆盖断言：Pydantic `model_fields` 取**别名优先**的对外名，config 系列 → `configuration.md`，schema 系列 → `schema-reference.md`，比对字段表首列
- [x] 3.4 实现错误码覆盖断言：遍历 `LoopspecError` 全部子类的 `code`，断言出现在 `cli-reference.md` 错误码表中
- [x] 3.5 实现示例可校验断言：提取带 `<!-- loopspec:example=... -->` 标记的 YAML 块，`config` → `WorkflowConfig.model_validate`，`schema` → `WorkflowSchema.model_validate`，`schema-dir` → 在 `tmp_path` 物化 `templates/`+`instructions/` 后过 `load_schema`（**物化前先用 `paths.is_safe_relative_path` 校验示例中声明的 `template`/`instruction.file` 文件名，非法直接断言失败；只做 yaml.safe_load + Pydantic 校验；严禁执行文档中的任何 shell 命令；严禁写入仓库工作区**）
- [x] 3.6 实现默认值对齐断言：`cli.DEFAULT_HOME`、`cli.DEFAULT_SCHEMA_NAME` 与模型字段默认值须与文档中记录的默认值一致
- [x] 3.7 实现文档结构断言：语言目录下 7 个必需文件存在、`<lang>/README.md` 链接到同语言其余 6 篇且全部链接目标存在、每篇首屏含覆盖范围/适用读者/语言切换链接、代码块均有语言标注、除首屏语言链接与 `docs/README.md` 外无跨语言链接
- [x] 3.8 实现凭据与占位检查：断言示例中不含真实凭据/令牌/内网地址形态的字符串（**失败信息只报文件路径、行号与命中的规则名，不回显命中内容**）
- [x] 3.9 把 3.2–3.8 全部断言**参数化到语言**（本阶段只传 `en`），跑 `make test` 直到全绿；测试暴露的遗漏回填到第 2 组英文文档

## 4. 撰写中文版（照译，`docs/zh/`）

- [x] 4.1 按任务 1.5 的不翻译清单，把 `docs/en/` 7 篇逐篇转写为 `docs/zh/` 同名文件：散文与表格说明列翻译，标识符/示例/标记注释/命令小节标题逐字沿用
- [x] 4.2 中文版字段表表头改用 `字段`/`类型`/`必填`/`默认值`/`说明`，保持五列固定顺序与首列反引号字段名
- [x] 4.3 中文版术语表锚点改为 `#术语表`，并把同语言目录内的术语首现链接全部指向该锚点
- [x] 4.4 给 `docs/zh/` 全部 7 篇补首屏三件套：覆盖范围、适用读者、指向 `../en/<同名文件>` 的语言切换链接
- [x] 4.5 写 `docs/README.md`：极简双语语言入口（指向 `en/README.md` 与 `zh/README.md` 的两条链接 + 一句话导航），**不承载任何事实性内容**

## 5. 双语等价性断言

- [x] 5.1 把第 3 组的全部断言参数化到 `en` 与 `zh` 两种语言分别执行
- [x] 5.2 实现跨语言等价断言 (a)(b)：两个语言目录相对路径集合相等；两版 `cli-reference.md` 的 `## loopspec <command>` 小节标题集合相等
- [x] 5.3 实现跨语言等价断言 (c)(d)：每对同名文件的字段表首列标识符集合相等；两版错误码集合相等
- [x] 5.4 实现跨语言等价断言 (e)：带标记的示例块按出现顺序逐字相等（含 JSON 响应示例块）
- [x] 5.5 实现跨语言等价断言 (f)(g)：每篇首屏含指向对侧语言同名文件的链接且目标存在；除首屏语言链接与 `docs/README.md` 外不存在跨语言链接
- [x] 5.6 跑 `make test` 直到全绿；等价断言暴露的差异回填到中文版（原则上不改英文版，除非英文版本身有错）

## 6. 收敛与验收

- [x] 6.1 收敛 `README.md`：保留定位/安装/quick start，删除与手册重复的 CLI 参数明细与配置字段明细，新增指向 `docs/README.md` 的完整手册链接并说明提供中英两版
- [x] 6.2 `Makefile` 新增 `docs-check` target（`uv run pytest tests/test_docs_consistency.py -v`）并加入 `.PHONY`
- [x] 6.3 跑 `make lint` 与 `make test` 全绿；再跑 `make docs-check` 确认可单独执行
- [x] 6.4 逐条对照 `specs/usage-docs/spec.md` 的 14 条需求（53 个 Scenario）做验收自查，未被自动化覆盖的场景（如"README 不重复字段明细"、"散文措辞不同不算失败"、"顶层入口不承载事实性内容"）人工确认并记录结论
