> **已被 `plan-replacement` 部分取代（2.0.0）。** 下列内容以 `loopspec/changes/plan-replacement/design.md` 为准：
> - D1.2 由内向外的恢复处理链 → 编译时把 `on_fail` 下放到每个 Gate，每个 Gate 最多一条，重叠报 `on_fail_conflict`；次数按 Gate 统计（plan-replacement D4、D11 B4）。
> - D4 Profile `protected` 与请求 `deviations` → 删除；项目最低要求只由 `config.yaml` 的 `required_fragments` 与保障规则保证（D11 A1）。
> - D5 请求中的 `reasons` 与 `baseline` → 删除；基线在 Change 级 `.workflow.yaml` 固定（D3）。
> - D6 自包含快照、资源字节固化与原子激活 → 每份 Plan 一个 `plan.yaml`（`meta` + `spec`，摘要校验），指令、模板与保障规则执行时实时读取（D4）。
> - D10 每份 Plan 的基线 → Change 级基线；Diff 控制目录排除改为 Change 根下 `.workflow.yaml`、`state.md` 与 `plans/`（D3、D7）。
> - D11 修订快照、修订事务与安全扩张 → `plan validate -f` 预览、`plan approve -f --digest` 确认，冻结节点只能增加 `requires`；中断后重新执行同一命令收敛，删除 `recover`（D5、D8）。
> - V1/V2 能力版本（`min_engine_version`、`manual-v1`、`delivery-review`）、`assurance check` 命令与平铺/复数命令 → 删除；命令树改为 `loopspec <资源> <动作>`，保障节点用 `gate record` 执行（D11、D12）。

## ADDED Requirements

### Requirement: Fragment 是最小配置单位
系统 SHALL 从自包含目录 `fragments/<name>/fragment.yaml` 加载严格声明式 Fragment，平铺的 `fragments/<name>.yaml` SHALL NOT 被识别为 Fragment。Fragment SHALL 仅以非空 nodes 列表编排，列表 SHALL 允许混合直接定义执行内容的 Node 与通过 use 引用 Fragment 的 Node；独立 includes 字段 SHALL 被拒绝。Node SHALL 在 Fragment 内定义，SHALL NOT 要求独立配置文件。Fragment 名称 SHALL 与目录名一致，未知字段和重复 YAML 键 SHALL 被拒绝。Fragment 的 instruction、template、Gate templates 与 assurance 资源 SHALL 相对于所属 Fragment 目录解析，SHALL NOT 读取目录外文件。

#### Scenario: 单节点与混合 Fragment
- **WHEN** nodes 只定义一个直接 Node，或混合本地 implement 和 use: security-review
- **THEN** 系统均能加载并校验完整局部图

#### Scenario: 无定义或未知字段
- **WHEN** Fragment 的 nodes 为空，或声明 includes、command、hook 字段
- **THEN** 校验以结构化错误失败且不执行任何清单内容

#### Scenario: 资源只能位于所属 Fragment 目录
- **WHEN** Fragment 引用 `../other/x.md`、绝对路径或符号链接资源，或 Fragment 目录本身是符号链接
- **THEN** 加载以 unsafe_path 拒绝，不读取目录外内容

#### Scenario: 与 Schema 一致的模板
- **WHEN** 产物节点声明 template，Gate 声明 templates.pass/fail
- **THEN** Plan 固化模板字节；instructions 对产物节点返回 template，对 Gate 同时返回 templates.pass 与 templates.fail

#### Scenario: 引用和执行定义互斥
- **WHEN** 同一个 Node 同时声明 use 与 instruction、generates、template、任务跟踪或 gate
- **THEN** 校验拒绝该定义，不静默覆盖被引用 Fragment

### Requirement: 局部依赖与递归展开
直接节点和引用节点 SHALL 共用 id/requires，requires SHALL 引用同一 Fragment 的兄弟 Node。引用节点 SHALL 递归展开，依赖 SHALL 连接上游全部终端与下游全部根；完成条件 SHALL 覆盖引用全部成员。列表顺序 SHALL NOT 隐式增加依赖。引用定义与展开执行图 SHALL 分别检查环，并限制递归深度、实例数和资源总量。

#### Scenario: 后端实现组合
- **WHEN** be-implementation 包含 code、tests、security、review，且依赖顺序依次连接
- **THEN** 编译图要求实现完成后执行测试、安全审查和 PR Review

#### Scenario: 递归环
- **WHEN** a 引用 b 且 b 引用 a
- **THEN** 编译报告引用链并在落盘前失败

### Requirement: 独立实例与产物归属
每次 Fragment 引用 SHALL 创建独立实例，以实例路径作为 Node 规范身份。系统 SHALL 对同一容器内重复实例/Node 名失败，SHALL 允许不同实例下的同名 Node。产物 SHALL 受所属实例根 `artifacts/<instance-path>/` 约束，资源和输出归属 SHALL 不能覆盖其他实例或控制目录。

#### Scenario: 前后端复用 PR Review
- **WHEN** FE 与 BE 都引用 pr-review
- **THEN** 系统生成不同 Gate 实例、产物路径和证据，不复用同一份 PASS

#### Scenario: 输出逃逸
- **WHEN** 产物路径或 Glob 可进入其他实例、计划、证据或 Attempts 区
- **THEN** 编译拒绝该路径且不写入目标

### Requirement: 完整图保持原有安全不变量
展开图 SHALL 校验依赖存在、无环、reset 祖先关系、任务跟踪关系、模板/指令存在以及具体和模糊输出归属。直接 Gate 和引用 Node SHALL 在 Node 顶层使用 on_fail；reset SHALL 指向同一 Fragment 的上游直接节点或引用节点，不能越过所属容器自由指定路径。普通产物 Node SHALL 不声明业务失败恢复。Fragment SHALL 不另设顶层 recovery；Profile/Plan 的 flow 条目 SHALL 使用同一 on_fail 语法，reset 指向同一 flow 中的上游实例；引用节点 on_fail SHALL 只绑定当前实例，不修改来源定义。没有局部处理规则的 Gate SHALL 能向外传播失败，最终无处理者时停止自动推进。

#### Scenario: 重置非法目标
- **WHEN** QA Gate 的局部 reset 指向无关分支
- **THEN** 编译失败并说明非法恢复目标

#### Scenario: 实现 Fragment 内安全审查失败
- **WHEN** be/security/check 产生未被内部处理的 FAIL，且 be 的 security 引用节点声明 on_fail.reset: [code]
- **THEN** 系统重跑该 BE 的 code、tests、security、review，不需要 QA 失败才能返工

#### Scenario: 本地 Node 与引用 Node 之间返工
- **WHEN** implement 是直接定义 Node，security 是依赖 implement 的引用 Node，其 on_fail.reset 指向 implement
- **THEN** 有效传播失败重置 implement、security 的全部成员和下游，保留引用源文件及业务代码

### Requirement: 引用节点结果从内部状态汇总
Plan SHALL 保留引用节点成员树与展开叶子身份。引用节点 SHALL 仅在全部成员完成且必要 Gate/证据有效时为 done；存在待处理有效 Gate FAIL 时为 failed；其余 SHALL 根据前置依赖及可执行叶子汇总 ready/blocked。success/failure SHALL 不要求独立 Fragment 接口或结果文件。无产物 SHALL 不视为业务 FAIL；无效或冲突结果、读取错误及未恢复事务 SHALL 优先阻塞；过期证据 SHALL 重新计算状态而不伪造失败。最终 exhausted SHALL 表示失败已没有可用处理链。

#### Scenario: 多节点引用成功
- **WHEN** 被引用 Fragment 的一个 Gate 已通过，但其他成员还未完成
- **THEN** 引用节点不是 done，下游不得执行

#### Scenario: 普通 Node 未产生产物
- **WHEN** 被引用 Fragment 内普通 Node 的产物尚不存在，且没有有效 FAIL
- **THEN** 引用仍未完成，不触发引用 on_fail

#### Scenario: 通过和失败结果冲突
- **WHEN** 内部 Gate 同时存在 PASS 与 FAIL，或其报告无效
- **THEN** 结构化错误阻塞引用节点，不把错误当作可恢复的业务失败

### Requirement: 有界安全加载与内容绑定
所有定义和资源 SHALL 作为不可信数据加载，路径 SHALL 在配置根内规范化并检查符号链接，读取 SHALL 有单文件与累计限制。每个来源 SHALL 在一次编译中只读取并缓存一次；摘要校验、审批校验和落盘 SHALL 使用同一缓存字节。

#### Scenario: 编译后来源变化
- **WHEN** 指令文件在解析资源包完成后被替换
- **THEN** 本次操作仍落盘已缓存且摘要绑定的字节，下次编译产生新摘要

#### Scenario: 恶意路径与资源超限
- **WHEN** 资源逃逸根目录或超过读取限制
- **THEN** 系统不读取逃逸内容，并返回明确校验错误

### Requirement: 目录命令与内置资源
系统 SHALL 提供 fragments list/show/validate 的人类可读与 JSON 输出，并提供需求、设计、FE/BE 实现、测试、审查、QA 和保障构件；内置产物节点 SHALL 提供 template，除系统保障外的内置 Gate SHALL 提供带 verdict/summary 头部的 PASS/FAIL 模板，内容不同的 FE/BE 构件 SHALL 拆分为独立 Fragment 而不共用资源文件。init SHALL 复制缺失定义并保留本地修改。内置路径规则 SHALL 由项目初始化时映射实际仓库布局。

#### Scenario: 再次初始化
- **WHEN** 用户修改了内置 Fragment 后再次 init
- **THEN** 本地修改保留，未安装构件按版本能力复制
