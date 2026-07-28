# workflow-graph Specification

## Purpose
TBD - created by archiving change gated-artifact-workflow. Update Purpose after archive.
## Requirements
### Requirement: 依赖图的无环校验
系统 SHALL 在 schema 加载期对 `requires` 关系执行有向图环检测（DFS 三色标记法），发现环时 SHALL 抛出 `SchemaValidationError`，错误信息包含完整、顺序正确的环路径（如 `design → tasks → design`）。

#### Scenario: 两节点互相 requires 成环
- **WHEN** 节点 A 的 `requires` 包含 B，且 B 的 `requires` 包含 A
- **THEN** 系统报错，环路径为 `A → B → A`（或等价顺序）

#### Scenario: 三节点成环
- **WHEN** A→B→C→A 构成一个三节点环
- **THEN** 系统报错，环路径顺序正确反映实际依赖链

### Requirement: 拓扑排序
系统 SHALL 提供基于 Kahn 算法的拓扑排序（`build_order()`），用于确定节点展示顺序、状态推导遍历顺序与归档顺序；同一入度层级的节点 SHALL 按节点 ID 字典序排列，保证输出在多次调用间稳定、可测试。

#### Scenario: 线性依赖链的拓扑排序
- **WHEN** 节点关系为 A→B→C（B requires A，C requires B）
- **THEN** `build_order()` 返回 `[A, B, C]`

#### Scenario: 菱形依赖的拓扑排序
- **WHEN** 节点关系构成菱形（A 是 B、C 的依赖，D 依赖 B 和 C）
- **THEN** `build_order()` 返回一个拓扑有效的顺序，且同一层级节点按字典序排列

### Requirement: 祖先与后继查询
系统 SHALL 提供 `ancestors(node_id)`（返回该节点全部传递依赖，不含自身）与 `dependents(node_id)`（返回该节点的直接后继）查询，供 schema 校验（`on_fail.reset` 祖先关系判定）与回退闭包计算复用。

#### Scenario: ancestors 返回传递依赖
- **WHEN** 查询某节点的 `ancestors`
- **THEN** 返回结果包含该节点全部直接与间接依赖节点 ID，不包含节点自身

#### Scenario: dependents 返回直接后继
- **WHEN** 查询某节点的 `dependents`
- **THEN** 返回结果只包含直接依赖于该节点的节点 ID（不含传递后继去重前的重复项）

### Requirement: 根节点的入度处理
系统 SHALL 正确处理 `requires` 为空列表的根节点：其在拓扑排序中的入度为 0，且排序结果中位于其所有后继之前。

#### Scenario: 空 requires 的根节点
- **WHEN** 一个节点的 `requires` 为空列表
- **THEN** 该节点在拓扑排序中的入度计算为 0，且总是可以最先被处理

