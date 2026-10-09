## ADDED Requirements

### Requirement: 四层模型命令面
CLI SHALL 支持 fragments list/show/validate、profiles list/show/validate/save、plans validate/show/history、new --plan/--profile、next、recompose；第二版本 SHALL 增加 gate begin/record、assurance check 和恢复事务的 inspect/resume。所有新命令 SHALL 支持 --json 及统一 error/message/fix 信封。

#### Scenario: 校验计划提议
- **WHEN** plans validate 收到有效请求
- **THEN** 返回 valid、planDigest、requiresApproval、readyToApply、resolvedFlow、nodes、recovery、baseline 和 unmetCapabilities

#### Scenario: 校验失败
- **WHEN** 配置、路径、图或审批不合法
- **THEN** 命令返回结构化错误和纠正指引，不显示未处理 Traceback

### Requirement: 新建与旧接口互斥兼容
new --plan 与 --profile SHALL 走新 Plan 编译入口，--schema SHALL 只作旧式兼容；选项 SHALL 相互排斥。Profile 直接采用 SHALL 先生成具体提议并执行同等校验。新格式选项 SHALL 不触发旧 Change 自动迁移。

#### Scenario: 新建失败不留活动 Change
- **WHEN** 计划未审批、图无效或资源落盘失败
- **THEN** new 不产生指向部分资源的活动 Change

### Requirement: 执行结果暴露关键上下文
status/next/instructions SHALL 返回 planRevision、planDigest、Node 规范身份、所属 Fragment、证据状态和确定性 nextSteps。旧 Change SHALL 保留原字段与路径。rollback SHALL 对新 Plan 展示 routeCase、resetFragments、resetNodes 和事务状态。

#### Scenario: 后端 QA 返工指引
- **WHEN** QA 报告为 backend
- **THEN** nextSteps 指向受约束 rollback，后续 instructions 包含失败报告与必须重跑的 BE Gate

### Requirement: 初始化与文档契约
init SHALL 安装缺失 Fragment/Profile，并帮助维护者映射仓库路径和项目保障约束。中英文文档 SHALL 区分 V1/V2 能力、旧 Schema 兼容、外部提交边界，并一致记录命令、字段、错误与典型三类场景。

#### Scenario: 模板没有真实项目路径
- **WHEN** 代码保障 Profile 尚未配置实际覆盖规则
- **THEN** 校验给出初始化指引，不使用空规则宣称保障通过
