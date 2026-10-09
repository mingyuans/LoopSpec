## ADDED Requirements

### Requirement: Fragment 是最小配置单位
系统 SHALL 从 `fragments/<name>.yaml` 加载严格声明式 Fragment。Fragment SHALL 至少包含一个 Node 或一个被引用的 Fragment，并允许同时包含 `nodes` 与 `includes`。Node SHALL 在 Fragment 内定义，SHALL NOT 要求独立配置文件。Fragment 名称 SHALL 与文件名一致，未知字段和重复 YAML 键 SHALL 被拒绝。

#### Scenario: 单节点与混合 Fragment
- **WHEN** Fragment 只定义一个 Node，或同时定义本地 Node 与 includes
- **THEN** 系统均能加载并校验完整局部图

#### Scenario: 无定义或未知字段
- **WHEN** Fragment 没有 Node 和 includes，或声明 command/hook 字段
- **THEN** 校验以结构化错误失败且不执行任何清单内容

### Requirement: 局部依赖与递归展开
Node 和 included Fragment 的 `requires` SHALL 引用同一容器内的局部 Node 或子 Fragment 实例。依赖 Fragment SHALL 展开为其全部终端 Node 到依赖者根 Node 的边。列表顺序 SHALL NOT 隐式增加依赖。引用定义与展开执行图 SHALL 分别检查环，并限制递归深度、实例数和资源总量。

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
展开图 SHALL 校验依赖存在、无环、Gate reset 祖先关系、任务跟踪关系、模板/指令存在以及具体和模糊输出归属。局部 reset SHALL 能引用 Node 或子 Fragment，但 SHALL 只能指向失败 Gate 的执行祖先。
组合 Fragment SHALL 能声明内部 recovery；其规则 SHALL 随定义复用并在 Plan 中保留。没有局部 reset 的 Gate SHALL 有唯一合法的容器 recovery，否则编译失败。

#### Scenario: 重置非法目标
- **WHEN** QA Gate 的局部 reset 指向无关分支
- **THEN** 编译失败并说明非法恢复目标

#### Scenario: 实现 Fragment 内安全审查失败
- **WHEN** be/security/check 失败且 be 内声明回到 code 的恢复规则
- **THEN** 系统重跑该 BE 的 code、tests、security、review，不需要 QA 失败才能返工

### Requirement: 有界安全加载与内容绑定
所有定义和资源 SHALL 作为不可信数据加载，路径 SHALL 在配置根内规范化并检查符号链接，读取 SHALL 有单文件与累计限制。每个来源 SHALL 在一次编译中只读取并缓存一次；摘要校验、审批校验和落盘 SHALL 使用同一缓存字节。

#### Scenario: 编译后来源变化
- **WHEN** 指令文件在解析资源包完成后被替换
- **THEN** 本次操作仍落盘已缓存且摘要绑定的字节，下次编译产生新摘要

#### Scenario: 恶意路径与资源超限
- **WHEN** 资源逃逸根目录或超过读取限制
- **THEN** 系统不读取逃逸内容，并返回明确校验错误

### Requirement: 目录命令与内置资源
系统 SHALL 提供 fragments list/show/validate 的人类可读与 JSON 输出，并提供需求、设计、FE/BE 实现、测试、审查、QA 和保障构件。init SHALL 复制缺失定义并保留本地修改。内置路径规则 SHALL 由项目初始化时映射实际仓库布局。

#### Scenario: 再次初始化
- **WHEN** 用户修改了内置 Fragment 后再次 init
- **THEN** 本地修改保留，未安装构件按版本能力复制
