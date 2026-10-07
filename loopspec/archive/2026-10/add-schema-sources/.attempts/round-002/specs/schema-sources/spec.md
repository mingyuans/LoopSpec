## ADDED Requirements

### Requirement: 在 config.yaml 中声明 schema 源

`config.yaml` SHALL 接受可选的顶层字段 `schema_sources`，其值为对象列表。每个条目 SHALL 包含必填的 `name`（kebab-case）与必填的非空 `path`，以及可选的 `description`；条目中出现其他字段 SHALL 以 `config_invalid` 拒绝。`schema_sources[*].name` SHALL 唯一，且 SHALL NOT 为保留名 `local`。缺省或空列表时，系统行为 SHALL 与未引入本能力时一致。

#### Scenario: 声明一个外部源
- **WHEN** `config.yaml` 包含 `schema_sources: [{name: team-shared, path: /srv/schemas}]` 且 `/srv/schemas` 是存在的目录
- **THEN** 配置加载成功，可用源依次为 `local`、`team-shared`

#### Scenario: 源名称重复
- **WHEN** `schema_sources` 中两个条目的 `name` 相同
- **THEN** 以退出码 1 与 `config_invalid` 失败

#### Scenario: 使用保留名 local
- **WHEN** 某条目 `name` 为 `local`
- **THEN** 以退出码 1 与 `config_invalid` 失败

#### Scenario: 条目含未知字段
- **WHEN** 某条目包含 `url: https://example.com/schemas`
- **THEN** 以退出码 1 与 `config_invalid` 失败，不发起任何网络访问

#### Scenario: 未配置 schema_sources
- **WHEN** `config.yaml` 不含 `schema_sources`
- **THEN** 仅存在 `local` 源，所有命令的 schema 解析结果与既有行为一致

### Requirement: 源路径的解析与校验

`path` SHALL 按以下规则解析为源根目录：以 `~` 开头时按用户主目录展开；绝对路径原样使用；其他相对路径 SHALL 相对于 workflow home 解析（允许 `..`）；最后 SHALL 解析符号链接得到规范化绝对路径。系统 SHALL NOT 对 `path` 做环境变量展开。解析结果不存在或不是目录时，配置加载 SHALL 以 `config_invalid` 失败，错误消息 SHALL 包含源名称与配置中书写的原始 `path` 值。

#### Scenario: 相对于 workflow home 的路径
- **WHEN** workflow home 为 `<proj>/loopspec`，某源 `path` 为 `../../shared-schemas` 且该目录存在
- **THEN** 该源根解析为 `<proj>/../shared-schemas` 的规范化绝对路径

#### Scenario: 波浪号路径
- **WHEN** 某源 `path` 为 `~/team-schemas` 且该目录存在于用户主目录下
- **THEN** 该源根解析为用户主目录下的 `team-schemas`

#### Scenario: 不展开环境变量
- **WHEN** 某源 `path` 为 `$SCHEMA_HOME/shared`
- **THEN** 该值按字面路径处理（相对于 workflow home），通常因目录不存在而以 `config_invalid` 失败，且错误消息中出现的是原始字符串 `$SCHEMA_HOME/shared`

#### Scenario: 源目录不存在
- **WHEN** 某源 `path` 指向不存在的目录
- **THEN** 以退出码 1 与 `config_invalid` 失败，消息包含该源名称与原始 `path`

#### Scenario: 源路径是文件
- **WHEN** 某源 `path` 指向一个普通文件
- **THEN** 以退出码 1 与 `config_invalid` 失败

### Requirement: 按有序源解析 schema 名称

系统 SHALL 通过单一解析入口把 schema 名称映射到 schema 目录。查找顺序 SHALL 为：`local`（`<home>/schemas/`）在先，其后按 `schema_sources` 的声明顺序；第一个包含 `<name>/schema.yaml` 的源 SHALL 胜出。所有按名称加载 schema 的场景（`new`、`status`、`instructions`、`rollback`、`history`、`archive`、`bulk-archive`、`artifacts`、`schemas show`、`schemas validate`，以及配置加载时对候选 schema 的校验）SHALL 使用该入口。任何源都不包含该名称时 SHALL 以 `schema_not_found` 失败，消息 SHALL 列出已搜索的源名称。

#### Scenario: 仅外部源提供
- **WHEN** `<home>/schemas/` 下没有 `team-flow`，而源 `team-shared` 的根下有 `team-flow/schema.yaml`
- **THEN** `team-flow` 解析到 `team-shared` 中的目录，命令正常加载该 schema

#### Scenario: local 遮蔽外部同名 schema
- **WHEN** `<home>/schemas/team-flow/` 与 `team-shared` 源中的 `team-flow/` 同时存在
- **THEN** 解析结果为 `local` 中的副本

#### Scenario: 多个外部源按声明顺序
- **WHEN** 源 `a` 与源 `b`（按此顺序声明）都提供 `team-flow`，`local` 不提供
- **THEN** 解析结果为源 `a` 中的副本

#### Scenario: 候选 schema 仅存在于外部源
- **WHEN** `config.yaml` 的 `schema: team-flow`，而 `team-flow` 只存在于某外部源
- **THEN** 配置加载成功，`loopspec new <change>` 使用该 schema 创建 change

#### Scenario: 所有源都没有
- **WHEN** 请求的 schema 名不在任何源中
- **THEN** 以退出码 1 与 `schema_not_found`（候选校验场景为 `config_invalid`）失败，消息列出 `local` 与所有已配置源的名称

#### Scenario: 既有 change 跟随当前配置
- **WHEN** 一个 change 的 `.workflow.yaml` 记录 `schema: team-flow`，之后 `local` 中新增了 `team-flow` 副本
- **THEN** 该 change 的后续命令解析到 `local` 副本，`.workflow.yaml` 内容不变

### Requirement: schema 名称与 schema 目录的安全边界

解析入口 SHALL 在把名称拼接到任何源根之前按 kebab-case 校验名称，不合法 SHALL 以 `config_invalid` 失败且 SHALL NOT 访问任何源目录；该校验 SHALL 覆盖来自 `--schema`、`config.yaml` 与 `.workflow.yaml` 的名称。`.workflow.yaml` 的 `schema` 字段 SHALL 同样要求 kebab-case。候选目录 `<源根>/<name>` 在解析符号链接后若不位于该源根之内，该源 SHALL 被视为不提供此 schema，并 SHALL 产生一条指名该源与 schema 的 warning（有 warnings 通道的命令）。系统 SHALL NOT 向任何外部源目录写入、移动或删除文件。

`schema.yaml`、每个 instruction 文件与每个 template 文件在解析符号链接后 SHALL 位于**已解析的 schema 目录**之内（而不仅是位于 `instructions/` 或 `templates/` 子目录解析后的位置之内），否则加载 SHALL 以 `schema_invalid` 失败；对 `schema.yaml` 的判定 SHALL 在读取其内容之前完成。template 在被 `loopspec instructions` 读取的时刻 SHALL 再次执行同一判定。该规则 SHALL 对 `local` 与外部源一视同仁；schema 目录内指向同一 schema 目录内部的符号链接 SHALL 仍被允许。

与源或 schema 路径相关的 warning 与错误消息 SHALL 只包含源名称、schema 名称、配置中书写的 `path` 原文以及相对于 schema 目录的文件名，SHALL NOT 包含任何符号链接解析后的目标路径。

#### Scenario: .workflow.yaml 中的非法 schema 名
- **WHEN** 某 change 的 `.workflow.yaml` 为 `schema: ../../etc`，执行 `loopspec status <change> --json`
- **THEN** 以退出码 1 与 `config_invalid` 失败，且不读取 workflow home 或任何源根之外的文件

#### Scenario: --schema 传入路径
- **WHEN** 执行 `loopspec new demo --schema ../x --json`
- **THEN** 以退出码 1 与 `config_invalid` 失败

#### Scenario: schema 目录是逃出源根的符号链接
- **WHEN** 源 `team-shared` 根下的 `team-flow` 是指向源根之外目录的符号链接，且没有其他源提供 `team-flow`
- **THEN** 解析以 `schema_not_found` 失败，不加载链接目标中的任何文件

#### Scenario: instruction 文件试图逃出外部 schema 目录
- **WHEN** 外部源中某 schema 的节点 `instruction.file` 为 `../../secret.md`
- **THEN** 加载该 schema 以 `schema_invalid` 失败，与本地 schema 的既有行为一致

#### Scenario: instructions 目录是外链
- **WHEN** 某 schema 的 `instructions/` 是指向 schema 目录之外（例如用户主目录下某目录）的符号链接，节点 `instruction.file` 指向其中的文件
- **THEN** 加载该 schema 以 `schema_invalid` 失败，响应中不出现该文件的任何内容，也不出现链接目标路径

#### Scenario: templates 目录是外链
- **WHEN** 某 schema 的 `templates/` 是指向 schema 目录之外的符号链接
- **THEN** 加载该 schema 以 `schema_invalid` 失败，且不输出目录外文件内容

#### Scenario: schema.yaml 是外链
- **WHEN** `<源根>/<name>/schema.yaml` 是指向 schema 目录之外某个可解析 YAML 文件的符号链接
- **THEN** 加载以 `schema_invalid` 失败，该外部文件的内容未被读取，错误消息中不含其任何字段值与链接目标路径

#### Scenario: 读取时刻模板被替换为外链
- **WHEN** schema 加载成功后、`loopspec instructions` 读取模板之前，某个模板文件被替换为指向 schema 目录之外的符号链接
- **THEN** 读取以 `schema_invalid` 失败，不输出目录外文件内容

#### Scenario: 目录内符号链接仍被允许
- **WHEN** 某 schema 的 `templates/a.md` 是指向同一 schema 目录内 `templates/shared/a.md` 的符号链接
- **THEN** 加载与读取均成功

#### Scenario: 诊断信息不含链接目标
- **WHEN** 以上任一包含性判定失败，或源根下 schema 目录外链被跳过并产生 warning
- **THEN** 错误消息与 warnings 的文本中不出现链接解析后的目标路径的任何片段

#### Scenario: 只读使用外部源
- **WHEN** 使用外部源 schema 的 change 完成 `new`、`rollback`、`archive` 全过程
- **THEN** 外部源目录中的文件集合与内容均未发生任何变化
