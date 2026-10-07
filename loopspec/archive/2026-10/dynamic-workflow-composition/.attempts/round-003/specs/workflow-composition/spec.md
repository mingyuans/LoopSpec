## ADDED Requirements

### Requirement: 严格组合请求
组合请求 SHALL 是工作流 Home 相对路径下的 YAML 文件，包含 `version: 1`、唯一且非空的 `fragments` 列表、每个选中片段的非空理由、`omissions` 映射、可选审批数据和可选 `base_revision`。系统 SHALL 拒绝未知字段、不安全路径、无效名称、缺失理由以及针对未选片段的纳入理由。

#### Scenario: 完整请求
- **WHEN** 每个选中片段都有非空理由且全部字段有效
- **THEN** 请求进入工作流图编译

#### Scenario: 缺少纳入理由
- **WHEN** 某个选中片段没有对应理由
- **THEN** 校验在写入任何变更或计划目录之前失败

#### Scenario: 不安全请求路径
- **WHEN** `--composition` 是绝对路径、包含 `..` 或解析到工作流 Home 之外
- **THEN** 命令失败，且不读取外部目标

### Requirement: 完整有效图校验
编译器 SHALL 合并所选来源节点，并对完整图应用全部现有 Schema 不变量，包括唯一 ID、依赖存在、无环、安全输出、资源存在、门禁重置祖先关系和跟踪文件祖先关系。编译器还 SHALL 拒绝具体输出冲突，并保守拒绝含糊重叠的输出模式。

#### Scenario: 选择片段后依赖缺失
- **WHEN** 选择 `tasks` 但没有片段提供其依赖的 `design` 节点
- **THEN** 编译拒绝请求，并指出缺失依赖

#### Scenario: 输出归属冲突
- **WHEN** 两个选中节点可能声明同一个具体产物路径
- **THEN** 编译在落盘之前拒绝请求

### Requirement: 规范计划摘要
编译器 SHALL 把每个选中片段的清单、Schema、指令和模板各读取一次，形成一个经过校验的内存资源包。编译器 SHALL 对规范 JSON 计算 SHA-256 `planDigest`；规范 JSON 包含有效 Schema、所选片段身份与版本、纳入理由、受保护片段的省略理由，以及每个落盘资源的目标相对路径、字节长度和 SHA-256 内容哈希。审批数据、文件系统时间戳、绝对路径和 YAML 格式 SHALL NOT 影响摘要。审批检查和落盘 SHALL 使用同一个缓存资源包，并且 SHALL NOT 重新打开来源资源。

#### Scenario: 等价格式
- **WHEN** 两个请求文件仅在 YAML 格式或映射顺序上不同
- **THEN** 校验返回相同的计划摘要

#### Scenario: 实质计划变化
- **WHEN** 片段版本、节点定义、选择理由、省略理由、指令字节或模板字节发生变化
- **THEN** 校验返回不同的计划摘要

#### Scenario: 资源包解析后来源变化
- **WHEN** 编译器缓存并求哈希后，磁盘上的来源资源发生变化
- **THEN** 当前操作落盘摘要所绑定的缓存字节，后续操作读取新字节并生成新摘要

### Requirement: 受保护片段省略审批
目录中每个标记为受保护的片段 SHALL 被选中，或在 `omissions` 中具有非空理由。省略受保护片段的请求 SHALL 报告 `requiresApproval: true`，并且在审批包含 `decision: approved`、非空人工原话 `human_words` 且 `plan_digest` 等于当前计算摘要之前 SHALL NOT 可应用。选择全部受保护片段的请求 SHALL 不需要组合审批。

#### Scenario: 首次校验请求人工判断
- **WHEN** 有效请求以理由省略 `security-review` 但没有审批
- **THEN** 校验作为提议成功，返回计划摘要并报告 `readyToApply: false`

#### Scenario: 审批匹配
- **WHEN** 人审阅已展示的提议，且请求记录其原话和返回的摘要
- **THEN** 再次校验报告 `readyToApply: true`

#### Scenario: 审批过期
- **WHEN** 审批后任何参与摘要的计划内容发生变化
- **THEN** 旧审批被判定为过期，必须重新决定

### Requirement: 自包含不可变计划落盘
应用就绪的组合 SHALL 创建不可变的编号计划目录，其中包含完整 `schema.yaml`、`manifest.yaml`，以及所有引用指令和模板的命名空间化副本。副本 SHALL 只从摘要绑定的内存资源包写入，Manifest SHALL 记录并重新校验其哈希。复制完成后 SHALL 校验落盘的 Schema。运行时命令 SHALL 只加载落盘快照，且 SHALL NOT 依赖片段或来源 Schema 后续仍然存在。

#### Scenario: 创建后来源变化
- **WHEN** 创建组合变更后，来源片段、Schema、模板或指令发生变化
- **THEN** 该变更的 `status` 和 `instructions` 继续使用原计划字节

#### Scenario: 落盘资源缺失
- **WHEN** 暂存阶段无法复制或校验任一必需资源
- **THEN** 计划激活失败，且没有活动元数据指向不完整目录

### Requirement: 原子计划激活
计划落盘 SHALL 使用暂存目录、排他式最终修订版创建和原子元数据替换。在元数据替换前任一步骤失败 SHALL 保持原工作流绑定不变。元数据中的计划路径 SHALL 安全、相对且受变更目录约束。

#### Scenario: 创建中断
- **WHEN** 落盘在替换 `.workflow.yaml` 前失败
- **THEN** 旧式变更仍绑定原 Schema，已有组合变更仍绑定前一修订版

#### Scenario: 计划路径被篡改
- **WHEN** 元数据指定绝对路径或逃逸路径作为计划路径
- **THEN** 加载变更以 `config_invalid` 失败，且不读取变更目录之外的内容

### Requirement: 旧式 Schema 兼容
元数据中只有 `schema` 和 `created` 的变更 SHALL 保持当前行为。`loopspec new <change> [--schema <name>]` SHALL 继续受支持，完整 Schema SHALL 能与组合能力并存，并继续支持列表、校验和使用。

#### Scenario: 升级后的现有变更
- **WHEN** 对组合能力引入前的变更执行 `status`、`instructions`、`rollback`、`history` 或 `archive`
- **THEN** 结果与本功能引入前一致

#### Scenario: 新建旧式变更
- **WHEN** 执行 `loopspec new example --schema secure-spec-driven` 且不提供组合选项
- **THEN** 系统创建传统元数据且不创建计划目录

### Requirement: 支持组合的变更创建
`loopspec new` SHALL 接受 `--composition <relative-request>`，并与 `--schema`、`--profile` 相互排斥。命令 SHALL 在创建变更目录前完整解析和校验请求，拒绝尚未就绪的提议，并在成功时返回计划修订版、摘要、所选片段、省略项和既有的第一步指引。

#### Scenario: 创建组合变更
- **WHEN** `new --composition` 收到已就绪请求
- **THEN** 系统落盘修订版 1，且 `status` 报告有效图中的第一个就绪节点

#### Scenario: 未审批的省略
- **WHEN** `new --composition` 收到仍需要审批的有效提议
- **THEN** 命令以 `composition_approval_required` 失败，且不写入变更目录

### Requirement: 进度继续由文件系统推导
活动计划 SHALL 只定义结构。节点完成状态、门禁判定、回滚次数、任务进度、就绪状态和整体完成状态 SHALL 在每次调用时继续根据产物、判定文件、复选框和 Attempts 文件计算。

#### Scenario: 手动删除产物
- **WHEN** 删除已完成组合节点所拥有的产物
- **THEN** 下一次 `status` 在不修改计划元数据的情况下把该节点重新计算为未完成
