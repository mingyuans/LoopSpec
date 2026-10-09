## MODIFIED Requirements

### Requirement: 完整图保持原有安全不变量
展开图 SHALL 校验依赖存在、无环、reset 祖先关系、任务跟踪关系、模板/指令存在以及具体和模糊输出归属。直接 Gate、引用 Node 与 Profile/Plan 的 flow 条目 SHALL 可声明 on_fail；reset SHALL 指向同一容器（Fragment 或 flow）中的上游节点或实例，不能越过所属容器自由指定路径。普通产物 Node SHALL 不声明业务失败恢复。编译时引用节点与 flow 条目上的 on_fail SHALL 下放到其范围内的每个 Gate 并展开为叶子节点；同一 Gate 收到多条 on_fail SHALL 以 on_fail_conflict 拒绝。引用节点 on_fail SHALL 只绑定当前实例，不修改来源定义。

#### Scenario: 重置非法目标
- **WHEN** 文档审查 Gate 的局部 reset 指向无关分支
- **THEN** 编译失败并说明非法恢复目标

#### Scenario: 实现 Fragment 内安全审查失败
- **WHEN** be 的 security 引用节点声明 on_fail.reset: [code]，be/security/check 记录有效 FAIL
- **THEN** be/security/check 的 gate.on_fail.reset 为 [be/code/implement]，系统重跑该 BE 的 code、tests、security、review 及下游

#### Scenario: on_fail 重叠
- **WHEN** security-review 内部 Gate 已声明 on_fail，be 的 security 引用节点也声明 on_fail
- **THEN** 编译返回 on_fail_conflict，不做隐式优先级选择

### Requirement: 引用节点结果从内部状态汇总
引用节点的成员 SHALL 由展开后叶子的实例路径前缀推导，起点与终点由 requires 推导。引用节点 SHALL 仅在全部成员完成且必要 Gate/证据有效时为 done；存在有效 Gate FAIL 时为 failed；成员 Gate 的 on_fail 次数用完或没有 on_fail 时为 exhausted；其余 SHALL 根据前置依赖及可执行叶子汇总 ready/blocked。无产物 SHALL 不视为业务 FAIL；无效或冲突结果、读取错误及中断状态 SHALL 优先阻塞；过期证据 SHALL 重新计算状态而不伪造失败。

#### Scenario: 多节点引用成功
- **WHEN** 被引用 Fragment 的一个 Gate 已通过，但其他成员还未完成
- **THEN** 引用节点不是 done，下游不得执行

#### Scenario: 普通 Node 未产生产物
- **WHEN** 被引用 Fragment 内普通 Node 的产物尚不存在，且没有有效 FAIL
- **THEN** 引用仍未完成，不触发返工

### Requirement: 目录命令与内置资源
系统 SHALL 提供 `fragment list/show/validate` 的 JSON 输出，并提供需求、设计、FE/BE 实现、测试、审查、QA 和保障构件；内置产物节点 SHALL 提供 template，除系统保障外的内置 Gate SHALL 提供带 verdict/summary 头部的 PASS/FAIL 模板，内容不同的 FE/BE 构件 SHALL 拆分为独立 Fragment 而不共用资源文件。Fragment SHALL NOT 声明 min_engine_version。init SHALL 复制缺失定义并保留本地修改。内置路径规则 SHALL 由项目初始化时映射实际仓库布局。

#### Scenario: 再次初始化
- **WHEN** 用户修改了内置 Fragment 后再次 init
- **THEN** 本地修改保留，缺失的内置构件被复制

#### Scenario: 旧字段
- **WHEN** Fragment 声明 min_engine_version
- **THEN** 校验以未知字段拒绝
