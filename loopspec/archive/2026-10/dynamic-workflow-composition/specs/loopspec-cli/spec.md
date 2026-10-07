> **已被 `plan-replacement` 部分取代（2.0.0）。** 下列内容以 `loopspec/changes/plan-replacement/design.md` 为准：
> - D1.2 由内向外的恢复处理链 → 编译时把 `on_fail` 下放到每个 Gate，每个 Gate 最多一条，重叠报 `on_fail_conflict`；次数按 Gate 统计（plan-replacement D4、D11 B4）。
> - D4 Profile `protected` 与请求 `deviations` → 删除；项目最低要求只由 `config.yaml` 的 `required_fragments` 与保障规则保证（D11 A1）。
> - D5 请求中的 `reasons` 与 `baseline` → 删除；基线在 Change 级 `.workflow.yaml` 固定（D3）。
> - D6 自包含快照、资源字节固化与原子激活 → 每份 Plan 一个 `plan.yaml`（`meta` + `spec`，摘要校验），指令、模板与保障规则执行时实时读取（D4）。
> - D10 每份 Plan 的基线 → Change 级基线；Diff 控制目录排除改为 Change 根下 `.workflow.yaml`、`state.md` 与 `plans/`（D3、D7）。
> - D11 修订快照、修订事务与安全扩张 → `plan validate -f` 预览、`plan approve -f --digest` 确认，冻结节点只能增加 `requires`；中断后重新执行同一命令收敛，删除 `recover`（D5、D8）。
> - V1/V2 能力版本（`min_engine_version`、`manual-v1`、`delivery-review`）、`assurance check` 命令与平铺/复数命令 → 删除；命令树改为 `loopspec <资源> <动作>`，保障节点用 `gate record` 执行（D11、D12）。

## ADDED Requirements

### Requirement: 四层模型命令面
CLI SHALL 支持 fragments list/show/validate、profiles list/show/validate/save、plans validate/show/history、new --plan/--profile、next、recompose；第二版本 SHALL 增加 gate begin/record、assurance check 和恢复事务的 inspect/resume。所有新命令 SHALL 支持 --json 及统一 error/message/fix 信封。

#### Scenario: 校验计划提议
- **WHEN** plans validate 收到有效请求
- **THEN** 返回 valid、planDigest、requiresApproval、readyToApply、resolvedFlow、nodes、recovery（解析后的 on_fail 处理链）、baseline 和 unmetCapabilities

#### Scenario: 校验失败
- **WHEN** 配置、路径、图或审批不合法
- **THEN** 命令返回结构化错误和纠正指引，不显示未处理 Traceback

### Requirement: 新建与旧接口互斥兼容
new --plan 与 --profile SHALL 走新 Plan 编译入口，--schema SHALL 只作旧式兼容；选项 SHALL 相互排斥。Profile 直接采用 SHALL 先生成具体提议并执行同等校验。新格式选项 SHALL 不触发旧 Change 自动迁移。

#### Scenario: 新建失败不留活动 Change
- **WHEN** 计划未审批、图无效或资源落盘失败
- **THEN** new 不产生指向部分资源的活动 Change

### Requirement: 执行结果暴露关键上下文
status/next/instructions SHALL 返回 planRevision、planDigest、实际叶子 Node 规范身份、所属 Fragment 与引用链、引用节点汇总状态、证据状态和确定性 nextSteps；就绪引用 SHALL 导航到实际叶子指令。旧 Change SHALL 保留原字段与路径。rollback SHALL 对新 Plan 展示来源 Gate、唯一处理者、传播层级、resetFragments、resetNodes 和事务状态，SHALL NOT 返回 routeCase。

#### Scenario: QA 返工指引
- **WHEN** qa/test 记录有效 FAIL，qa 的 on_fail.reset 为 [be, fe]
- **THEN** nextSteps 指向受约束 rollback，后续 instructions 包含失败报告与必须重跑的 BE、FE Gate

#### Scenario: 引用节点内部失败
- **WHEN** security/check 的 FAIL 传播到 security 引用节点的 on_fail
- **THEN** nextSteps 展示所选 security 处理者及 implement/内部成员重置闭包，而不执行引用节点黑盒指令

### Requirement: 初始化与文档契约
init SHALL 安装缺失 Fragment/Profile，并帮助维护者映射仓库路径和项目保障约束。中英文文档 SHALL 区分 V1/V2 能力、旧 Schema 兼容、外部提交边界，并一致记录命令、字段、错误与典型三类场景。

#### Scenario: 模板没有真实项目路径
- **WHEN** 代码保障 Profile 尚未配置实际覆盖规则
- **THEN** 校验给出初始化指引，不使用空规则宣称保障通过
