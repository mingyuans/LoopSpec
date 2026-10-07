## Context

- 现状：schema 目录由 `paths.schema_dir(home, name)` 写死为 `<home>/schemas/<name>`。调用点分布在 `cli.py`（`_load_change_context`、`schemas show/validate`、`new`）、`artifacts.py`（`_load_schemas`）、`config.py`（加载配置时校验每个候选 schema 可加载）。`schemas list` 自行遍历 `<home>/schemas/`，其 JSON 中已预留 `source` 字段，但恒为 `local`。
- schema 内部读取已有包含性保护：`schema_loader._resolve_instruction` 与 `_check_template_exists` 都会 `resolve()` 后检查目标是否仍在 `<schema_dir>/instructions|templates/` 下；`instructions._read_template` 只读已通过该校验的模板名。
- 潜在缺口：`WorkflowMetadata.schema_name`（`.workflow.yaml` 的 `schema`）**没有** kebab-case 约束，今天就会被直接拼到 `<home>/schemas/` 后面。引入外部源后，同一个名字还会被拼到 home 之外的目录上，这个缺口必须在本次一并收口。
- 约束：不新增依赖；`.workflow.yaml` 与 change 磁盘布局不变；无 `schema_sources` 时行为逐字节一致（`schemas list` 输出除外——见 D7，仅新增字段）。

## Goals / Non-Goals

**Goals:**
- 多个项目通过 `config.yaml` 的 `schema_sources` 引用同一个本地共享 schema 目录。
- 所有「按名称加载 schema」的路径只经过**一个**解析入口，保证行为一致、安全检查不被绕过。
- 明确、可预测的优先级与遮蔽规则，并在 `schemas list` 中可见。

**Non-Goals:**
- 远程源（git / HTTP）、拉取、缓存、版本锁定。
- 用户级全局源配置、环境变量驱动的源路径。
- 把内置 schema（`builtin/schemas`）作为一个隐式源；`init` 的复制行为不变。
- loopspec 向任何外部源目录**写入**内容。

## Decisions

### D1：新增模块 `schema_sources.py` 作为唯一解析入口
提供：
- `SchemaSource`（`name`、`root: Path`，已规范化的绝对路径）。
- `sources_for(home, config) -> list[SchemaSource]`：`local`（`<home>/schemas`）在首位，其后按 `config.schema_sources` 声明顺序。
- `resolve_schema_dir(home, config, name) -> ResolvedSchema(name, source, dir)`：按顺序查找第一个含 `<name>/schema.yaml` 的源；都没有则抛 `SchemaNotFoundError`（沿用既有 schema-not-found 错误码），消息列出已搜索的源名称。
- `list_schemas(home, config)`：供 `schemas list` 使用，返回包含遮蔽信息的全部条目。

所有调用点（`cli.py`、`artifacts.py`、`config.py`）改为调用它。`paths.schema_dir` 保留为 `local` 源的实现细节（测试大量使用），但生产代码中不再直接调用。
- 备选：在 `paths.schema_dir` 内部加查找逻辑。否决：它不接收 config，改签名会波及 75 处测试调用，且把配置语义混进纯路径模块。

### D2：配置形态
```yaml
schema_sources:
  - name: team-shared
    path: ~/work/team-loopspec-schemas
    description: 团队共享 schema（可选）
```
- `name`：必填，`KEBAB_RE`，唯一；`local` 为保留名。
- `path`：必填、非空字符串。允许三种写法：绝对路径；以 `~` 开头（仅 `Path.expanduser()` 语义）；相对路径——**相对于 workflow home**（即 `config.yaml` 所在目录）解析，允许 `..`，以支持 `../../shared-schemas` 这种同级 checkout。
- `description`：可选，回显在 `schemas list` 中。
- 未知字段拒绝（`extra: forbid`），与既有模型一致。
- 备选：只允许绝对路径。否决：绝对路径随机器而变，写进仓库的 `config.yaml` 无法在团队间共享——违背本次目的。

### D3：名称在拼接前统一校验（安全）
`resolve_schema_dir` 在把 `name` 拼到任何源根之前，先用 `KEBAB_RE` 校验；不合法直接 `config_invalid`（消息：`Invalid schema name: <name>`）。这同时覆盖 `--schema`、`config.yaml` 以及此前未校验的 `.workflow.yaml` `schema`。另外给 `WorkflowMetadata.schema_name` 加上相同的 pattern，使非法值在读取元数据时即被拒绝（纵深防御）。
- 备选：只在 `WorkflowMetadata` 上加 pattern。否决：解析入口不能依赖所有上游都记得校验。

### D4：路径规范化与包含性（安全）
- 源根：`expanduser()` → 相对路径拼到 home → `resolve()`（跟随符号链接）。**不做**环境变量展开（`$VAR`、`${VAR}` 原样保留，结果通常是不存在的路径并报错）：避免配置文件成为读取环境变量的通道，也让同一份配置在不同 shell 中行为一致。
- 候选 schema 目录 `<root>/<name>` 在 `resolve()` 后必须仍位于 `root` 之下（`paths.contained_in`）；否则该源视为不含此 schema 并产生 warning，而不是跟随链接读出源外内容。
- schema 内的 instructions / templates 继续由 `schema_loader` 既有检查约束在该 schema 目录内；本设计不放宽它们。
- 源只读：没有任何代码路径向源目录写入；`init` 仍只写 `<home>/schemas`。

### D5：配置加载时的校验与失败方式
加载 `config.yaml` 时，对每个源：名称唯一、非 `local`；解析后的根必须存在且为目录，否则 `config_invalid`：`schema_sources[<name>].path does not exist or is not a directory: <configured path>`。错误消息回显**配置中写的原值**，不回显展开后的绝对路径。候选 schema 可加载性校验改为经 `resolve_schema_dir`，消息改为 `Candidate schema '<name>' cannot be loaded: not found in sources [local, team-shared]`。
- 备选：源目录缺失时降级为 warning。否决：与既有「候选 schema 不可加载即失败」的快速失败原则不一致；静默降级会让同一 change 在不同机器上解析到不同 schema（或根本解析不到）。代价见 Risks。

### D6：优先级与遮蔽
`local` 永远第一，然后按声明顺序；先命中者胜出。允许项目用本地副本覆盖共享 schema（有意为之的逃生口）。遮蔽不是错误，但在 `schemas list` 中可见（D7）。
- 备选：同名即报错。否决：会让「临时在本地改一版共享 schema 试验」变得不可能。

### D7：`schemas list` / `show` / `validate` 输出
- `list`：遍历所有源；每条目 `source` 为源名称，`path` 为该 schema 目录的解析路径，新增 `shadowed: bool`（被更高优先级源遮蔽时为 `true`）。排序：先按源优先级，再按名称。无 `schema_sources` 时，既有条目仅多出 `shadowed: false`。
- `show` / `validate`：经 `resolve_schema_dir` 解析，响应新增 `source` 字段（加法变更）。
- `new` 与 `status` 的 JSON 新增 `schemaSource`（解析出的源名称），便于排查「这台机器上到底用的是哪一份」。

### D8：`.workflow.yaml` 不记录源
change 只记录 schema 名称，源在每次命令执行时按当前 `config.yaml` 解析。理由：源路径是机器相关的；记录源会让 change 与某次配置绑定，并需要迁移既有 change。

## Risks / Trade-offs

- [共享源目录被他人修改 → 进行中的 change 在不同时刻读到不同的 instructions] → 这是共享的本意；文档明确「源内容 = 受信任的 agent 指令」，建议共享源置于受版本控制的仓库中并按需固定 checkout。版本锁定列为后续工作。
- [外部源内容会作为指令交给 agent，可写该目录的任何人都能影响 agent 行为（提示注入面扩大）] → 文档在配置参考中加安全说明：只把自己信任、且写权限受控的目录配置为源；loopspec 不从网络拉取任何内容。
- [源目录缺失时所有命令失败（包括只用 local schema 的 change）] → 错误消息给出源名与配置原值，并附 fix：克隆共享仓库或移除该条目。接受此代价以换取确定性。
- [相对路径允许 `..` 会使源指向 home 之外] → 这是功能本身；D3/D4 保证「名字」与「schema 目录」不能再逃出源根，逃逸面仅限于配置作者显式写下的源根。
- [给 `WorkflowMetadata.schema_name` 加 pattern 可能让手改过的非法 `.workflow.yaml` 从「碰巧能用」变为报错] → 合法 schema 名本就要求 kebab-case（`config.yaml` 层面已强制），实际不可能存在合法却非 kebab 的 schema；错误消息指向 `.workflow.yaml`。

## Migration Plan

- 无需迁移：新字段可选，缺省即现状。
- 回滚：删除 `config.yaml` 中的 `schema_sources`（并把所需 schema 复制回 `<home>/schemas/`）即恢复原行为；代码回滚不影响任何 change 数据。

## Open Questions

- 无阻塞问题。后续可考虑：远程源与版本锁定、`loopspec schemas copy <name> --from <source>` 把共享 schema 固化为本地副本。
