## ADDED Requirements

### Requirement: 声明式片段目录
系统 SHALL 从 `<home>/fragments/<name>/fragment.yaml` 发现工作流片段。每个片段 SHALL 声明与目录名一致的 kebab-case `name`、正整数 `version`、非空 `description`、可选 `when`、默认值为 false 的 `protected`，以及非空的 `{schema, id}` 节点引用列表。系统 SHALL 拒绝未知字段。

#### Scenario: 列出有效片段
- **WHEN** 有效片段清单引用有效 Schema 中存在的节点
- **THEN** 片段列表返回名称、版本、说明、选择指引、保护状态、来源节点引用和解析后的节点 ID

#### Scenario: 清单身份不一致
- **WHEN** `fragments/security/fragment.yaml` 声明 `name: approval`
- **THEN** 片段校验失败，并通过结构化错误指出身份不一致

### Requirement: 片段来源解析
系统 SHALL 通过普通工作流所使用的同一 Schema 加载器和 Schema 来源解析器解析每个片段节点。无法解析引用的 Schema 或节点时，整个片段 SHALL 无效；系统 SHALL NOT 返回或组合部分片段。

#### Scenario: 未知来源节点
- **WHEN** 片段引用 Schema 中不存在的 `review` 节点
- **THEN** 校验拒绝该片段，并同时指出片段和缺失节点

#### Scenario: 无效来源 Schema
- **WHEN** 片段引用的 Schema 在模板、路径或图校验中失败
- **THEN** 校验使用底层 Schema 错误拒绝该片段，且不生成计划

### Requirement: 片段路径不得离开受信根目录
所有片段、Schema、指令和模板路径 SHALL 在符号链接解析后进行规范化，并确认仍位于声明的工作流 Home 根目录内。片段清单 SHALL 仅作为数据解析，并且 SHALL NOT 声明命令、Hook、可执行模块或远程 URL。

#### Scenario: 符号链接逃逸
- **WHEN** 片段或引用资源通过符号链接解析到工作流 Home 或已配置 Schema 来源之外
- **THEN** 校验拒绝该路径，且不读取或复制逃逸目标

#### Scenario: 清单包含可执行字段
- **WHEN** 片段清单包含未识别的命令或 Hook 字段
- **THEN** 严格模型校验拒绝该清单

### Requirement: 严格只增不改的组合面
片段 SHALL 只贡献完整来源节点。片段 SHALL NOT 补丁修改、替换、删除或放宽其他片段提供的节点字段。重复选择片段或产生重复节点 ID SHALL 构成组合错误，即使重复定义的字节完全相同。

#### Scenario: 节点身份重复
- **WHEN** 两个选中片段都贡献 `design` 节点
- **THEN** 组合失败，并把冲突归因到两个片段

#### Scenario: 不提供覆盖语义
- **WHEN** 一个片段尝试只修改另一个片段所提供节点的门禁策略
- **THEN** 系统拒绝该清单，而不是应用后写覆盖规则

### Requirement: 内置安全工作流片段
随附资源 SHALL 包含 `proposal`、`specs`、`design`、`tasks`、`security-review`、`approval` 和 `implementation` 片段，引用 `secure-spec-driven` 中相应节点。`security-review` 与 `approval` SHALL 标记为受保护。`loopspec init` SHALL 复制缺失的内置片段且不覆盖本地修改。

#### Scenario: 全新初始化
- **WHEN** 在启用内置资源的情况下初始化新工作流 Home
- **THEN** 七个片段全部可用，且现有完整 Schema 仍然可用

#### Scenario: 再次初始化保留自定义内容
- **WHEN** 内置片段路径已在本地存在并再次执行 `init`
- **THEN** 系统不覆盖该本地目录

### Requirement: 片段目录命令
`loopspec fragments list`、`loopspec fragments show <name>` 和 `loopspec fragments validate <name>` SHALL 支持 `--json`。列表 SHALL 按片段名确定性排序；`show` SHALL 暴露已校验清单和解析节点；`validate` SHALL 报告有效性以及该片段子图的解析构建顺序。

#### Scenario: 机器可读的目录发现
- **WHEN** Agent 执行 `loopspec fragments list --json`
- **THEN** Agent 收到包含全部有效片段的稳定数组，且元数据足以支持选择判断

#### Scenario: 未知片段
- **WHEN** Agent 请求 `fragments show missing --json`
- **THEN** 命令以结构化 `fragment_not_found` 错误退出，并给出纠正建议
