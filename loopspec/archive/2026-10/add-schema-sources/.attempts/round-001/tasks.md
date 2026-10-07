## 1. 配置模型与校验（D2 / D5）

- [ ] 1.1 在 `models.py` 新增 `SchemaSourceSpec`（`name: KEBAB_RE`、`path: str(min_length=1)`、`description: str | None`，`extra: forbid`），给 `WorkflowConfig` 增加 `schema_sources: list[SchemaSourceSpec]`（默认空）；模型校验器中检查 `schema_sources[*].name` 唯一且不为 `local`。
- [ ] 1.2 **安全：外部输入校验点 1** —— 在 `models.py` 给 `WorkflowMetadata.schema_name` 加上 `KEBAB_RE` pattern（D3），使 `.workflow.yaml` 中的 `../../etc` 在读取元数据时即以 `config_invalid` 失败。
- [ ] 1.3 单测 `tests/test_config.py`：源名重复、源名为 `local`、条目含未知字段（如 `url`）、`path` 为空串均以 `ConfigValidationError` 失败；缺省 `schema_sources` 时加载结果与现状一致；`.workflow.yaml` 中非 kebab 的 `schema` 被拒绝。

## 2. 源解析模块 `schema_sources.py`（D1 / D3 / D4 / D6）

- [ ] 2.1 实现 `SchemaSource` 与 `sources_for(home, config)`：`local`（`<home>/schemas`）在首位，其后按声明顺序。**安全：源根规范化** —— `path` 只做 `Path.expanduser()`，不做任何环境变量展开；相对路径拼到 workflow home；最后 `resolve()`。
- [ ] 2.2 实现源根存在性校验（供 `config.load_config` 调用）：解析结果不存在或不是目录时抛 `ConfigValidationError`，消息只包含源名与**配置中的原始 `path` 字符串**，不包含展开后的绝对路径。
- [ ] 2.3 实现 `resolve_schema_dir(home, config, name) -> ResolvedSchema(name, source, dir)`。**安全：外部输入校验点 2（唯一拼接入口）** —— 拼接前先用 `KEBAB_RE` 校验 `name`，不合法抛 `ConfigValidationError` 且不触碰任何源目录；每个候选目录 `resolve()` 后必须 `paths.contained_in(source.root, candidate)`，否则跳过该源并记录 warning；全部未命中抛 `SchemaNotFoundError`，消息列出已搜索的源名。
- [ ] 2.4 实现 `list_schemas(home, config)`：按源优先级、名称排序，返回每个可加载 schema 的 `(name, version, source, path, nodes, shadowed)`；无法加载或逃出源根的目录跳过。
- [ ] 2.5 单测 `tests/test_schema_sources.py`（新文件，全部用 `tmp_path` 造真实目录）：仅外部源提供；`local` 遮蔽外部；多外部源按声明顺序；`~` 路径（通过 monkeypatch `HOME` 指向 `tmp_path`）；相对 home 的 `../` 路径；`$VAR/x` 不被展开且报错消息含原始字符串；源路径不存在 / 是文件；`name` 为 `../x`、`a/b`、空串时抛 `ConfigValidationError` 且不访问源目录；源根下的 schema 目录是指向源外的符号链接时不被解析；`list_schemas` 的 `shadowed` 标记与排序。

## 3. 接入所有 schema 加载调用点（D1 / D5 / D7）

- [ ] 3.1 `config.load_config`：调用 2.2 校验每个源；候选 schema 可加载性校验改为经 `resolve_schema_dir`，未命中时 `config_invalid` 消息列出已搜索的源名。
- [ ] 3.2 `cli._load_change_context`、`cli.new`、`cli.schemas_show`、`cli.schemas_validate` 改为经 `resolve_schema_dir`；`ChangeContext` 携带源名，`new` 与 `status` JSON 新增 `schemaSource`，`schemas show/validate` JSON 新增 `source`。
- [ ] 3.3 `cli.schemas_list` 改为基于 `list_schemas`，`source` 为源名，新增 `shadowed`。注意：`schemas list` 当前不加载 config；改为在 config 可加载时使用其源，**config 加载失败时的行为保持与现状一致**（只列 `local`，不因源配置错误而让 `list` 失败——在 design 基础上的实现细节，需在测试中钉住）。
- [ ] 3.4 `artifacts._load_schemas` 改为经 `resolve_schema_dir`（向其传入 config）；未点名时加载失败仍降级为 warning。
- [ ] 3.5 全仓检索确认生产代码中已无 `paths_mod.schema_dir(` / `schema_dir(home` 的直接调用（测试除外）。
- [ ] 3.6 **安全：只读** —— 确认没有任何写路径（`init` 的 `copytree`、`rollback`、`archive`）指向外部源；`init` 仍只写 `<home>/schemas`。

## 4. CLI 集成测试 `tests/test_cli.py`

- [ ] 4.1 外部源提供 `team-flow`：`new --schema team-flow` → `status` → `instructions <node>` 全链路成功，`schemaSource` 为源名，instructions 与 templates 内容来自外部源。
- [ ] 4.2 `schemas list/show/validate` 在有外部源、有遮蔽、无外部源三种配置下的 JSON 输出（含向后兼容断言：无源时仅多出 `shadowed: false`）。
- [ ] 4.3 `.workflow.yaml` 为 `schema: ../../etc` 时 `status` 以 `config_invalid` 失败；`new --schema ../x` 以 `config_invalid` 失败。
- [ ] 4.4 外部源中 schema 的 `instruction.file` 为 `../../secret.md` 时以 `schema_invalid` 失败。
- [ ] 4.5 只读断言：使用外部源 schema 的 change 跑完 `new` → 写产物 → `rollback` → `archive`，前后对外部源目录做文件快照（路径 + 内容哈希）对比，完全一致。
- [ ] 4.6 源目录缺失时任意命令以 `config_invalid` 失败，消息含源名与原始 `path`。

## 5. 文档（`usage-docs`）

- [ ] 5.1 `docs/en|zh/configuration.md`：顶层字段表加入 `schema_sources`；新增 `schema_sources[]` 条目字段表、校验规则表新行、「源查找顺序与遮蔽」小节、`path` 解析规则（含不展开环境变量）、安全说明（外部源内容 = 受信任的 agent 指令）；新增「跨项目共享 schema 源」示例。
- [ ] 5.2 `docs/en|zh/cli-reference.md`：`schemas list` 的 `source` 说明改写并新增 `shadowed`；`schemas show/validate` 新增 `source`；`new` / `status` 新增 `schemaSource`。
- [ ] 5.3 `docs/en|zh/schema-reference.md`：说明 schema 目录可来自外部源，instructions/templates 的包含性规则同样适用。
- [ ] 5.4 如 `tests/test_docs_consistency.py` 校验示例或字段覆盖，新增示例标记并保证可被真实加载；示例中的路径使用占位目录，不含真实用户名或凭据。

## 6. 验证

- [ ] 6.1 运行 `make lint` 与 `make test`，全部通过，并在 apply 报告中附真实输出摘要。
- [ ] 6.2 手工冒烟：在 scratchpad 建两个 workflow home 共用一个外部源目录，分别 `loopspec new` 并确认两者解析到同一 schema 目录。
