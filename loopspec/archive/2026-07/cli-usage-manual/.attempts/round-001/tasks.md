## 1. 采集事实源（先取真实数据，避免手写臆造）

- [ ] 1.1 运行 `loopspec` 全部 10 个命令（`version`/`init`/`schemas list|show|validate`/`new`/`status`/`instructions`/`rollback`/`history`/`archive`/`bulk-archive`）的 `--json`，在临时目录中造一个 change 并制造一次 gate 失败，采集每条命令的真实 JSON 响应样例留作文档示例（**只在临时目录操作，不污染仓库工作区**）
- [ ] 1.2 从 `src/loopspec/models.py` 整理 `WorkflowConfig`/`ConfigSchemaRef`/`SchemaSelectionSpec` 与 `WorkflowSchema`/`NodeSpec`/`GateSpec`/`GateOutputs`/`GateTemplates`/`OnFailSpec` 的字段清单，逐字段记录类型、必填性、默认值与**对外别名**（`schema`←`schema_name`、`pass`←`pass_`）
- [ ] 1.3 从 `src/loopspec/schema_loader.py` 与 `paths.py` 整理加载期全部语义校验，逐条对应到 `errors.py` 的错误码
- [ ] 1.4 从 `src/loopspec/errors.py` 整理全部错误码清单，从 `cli.py` 整理默认值常量（`DEFAULT_HOME`、`DEFAULT_SCHEMA_NAME`）

## 2. 撰写参考文档

- [ ] 2.1 写 `docs/overview.md`：定位、核心模型（节点图/产物/gate/回退/状态由文件系统推导）、术语表（workflow home、change、node、gate、artifact root、reset closure、attempts round）
- [ ] 2.2 写 `docs/cli-reference.md` 的命令部分：每条命令一个 `## loopspec <command>` 小节，含用途、语法、参数表、`--json` 响应字段表、以及来自任务 1.1 的真实响应示例
- [ ] 2.3 写 `docs/cli-reference.md` 的错误码总表：覆盖全部错误码，每条含触发条件与修复方向；并说明失败契约（退出码 1 + `error`/`message`/`fix`）
- [ ] 2.4 写 `docs/configuration.md`：`config.yaml` 全字段表（对外名称）、校验规则、schema 解析优先级（**区分新建 change 与既有 change 两条路径**）、4 个递进示例并加 `<!-- loopspec:example=config -->` 标记
- [ ] 2.5 写 `docs/schema-reference.md`：`schema.yaml` 全字段表、`instruction` 两种写法、`generates` 的 glob、`tracks` 语义与约束、`templates/`+`instructions/` 目录约定、保留产物名、语义校验清单（每条注明错误码）
- [ ] 2.6 为 `docs/schema-reference.md` 补最小可用 schema 完整示例（1 普通节点 + 1 gate）并加 `<!-- loopspec:example=schema-dir -->` 标记，附配套目录结构说明
- [ ] 2.7 写 `docs/agent-protocol.md`：主循环与每步该读的字段、gate 失败支线（`pendingRollback` → `rollback` → `priorAttempts`）、`tracks` 节点"报告已写但 checkbox 未全勾仍为 ready 且拒绝归档"、`approval` 节点禁止代替人类批准、`state.md` 读写约定
- [ ] 2.8 写 `docs/workflows/secure-spec-driven.md`：7 节点图表格（类型/依赖/产物）、逐节点语义、三个 gate 的 `reset`/`max_retries`/`on_exhausted` 取值及理由
- [ ] 2.9 写 `docs/README.md` 索引：逐篇列出文件 + 一句话覆盖范围 + 适用读者，补全相对链接
- [ ] 2.10 自检双读者约定（spec 第 2 条）：每篇首屏的覆盖范围/适用读者两行、字段表固定五列且字段名在首列反引号、代码块均带语言标注、无图片/emoji/框线、标题不超三级、术语首现有定义或链接

## 3. 文档一致性测试

- [ ] 3.1 新建 `tests/test_docs_consistency.py` 骨架与共享 fixture：定位 `docs/` 路径、解析 Markdown 小节与表格首列的工具函数（**结构化位置匹配，不用全文裸子串包含**）
- [ ] 3.2 实现命令与参数覆盖断言：经 `typer.main.get_command(app)` 递归遍历命令树与 `.params`（**禁止 `import click`：typer 0.27 已把 click 内置为 `typer._click`，顶层 import 会 ModuleNotFoundError；也禁止依赖 `typer._click` 私有路径**），断言每命令有小节、每选项在其小节内
- [ ] 3.3 实现模型字段覆盖断言：Pydantic `model_fields` 取**别名优先**的对外名，config 系列 → `docs/configuration.md`，schema 系列 → `docs/schema-reference.md`，比对字段表首列
- [ ] 3.4 实现错误码覆盖断言：遍历 `LoopspecError` 全部子类的 `code`，断言出现在 `docs/cli-reference.md` 错误码表中
- [ ] 3.5 实现示例可校验断言：提取带 `<!-- loopspec:example=... -->` 标记的 YAML 块，`config` → `WorkflowConfig.model_validate`，`schema` → `WorkflowSchema.model_validate`，`schema-dir` → 在 `tmp_path` 物化 `templates/`+`instructions/` 后过 `load_schema`（**只做 yaml.safe_load + Pydantic 校验；严禁执行文档中的任何 shell 命令；严禁写入仓库工作区**）
- [ ] 3.6 实现默认值对齐断言：`cli.DEFAULT_HOME`、`cli.DEFAULT_SCHEMA_NAME` 与模型字段默认值须与文档中记录的默认值一致
- [ ] 3.7 实现文档结构断言：7 个必需文件存在、`docs/README.md` 链接到其余 6 篇且全部链接目标存在、每篇首屏含覆盖范围与适用读者、代码块均有语言标注
- [ ] 3.8 实现凭据与占位检查：断言示例中不含真实凭据/令牌/内网地址形态的字符串（只使用占位名与仓库内相对路径）
- [ ] 3.9 跑 `make test`，把测试暴露的文档遗漏回填到第 2 组各文档，直到全绿

## 4. 收敛与验收

- [ ] 4.1 收敛 `README.md`：保留定位/安装/quick start，删除与手册重复的 CLI 参数明细与配置字段明细，新增指向 `docs/README.md` 的完整手册链接
- [ ] 4.2 `Makefile` 新增 `docs-check` target（`uv run pytest tests/test_docs_consistency.py -v`）并加入 `.PHONY`
- [ ] 4.3 跑 `make lint` 与 `make test` 全绿；再跑 `make docs-check` 确认可单独执行
- [ ] 4.4 逐条对照 `specs/usage-docs/spec.md` 的 13 条需求做验收自查，未被自动化覆盖的场景（如"README 不重复字段明细"、"术语首现有定义"）人工确认并记录结论
