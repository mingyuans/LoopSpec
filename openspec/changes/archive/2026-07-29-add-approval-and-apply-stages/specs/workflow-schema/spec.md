## ADDED Requirements

### Requirement: 节点可选 tracks 字段与校验
schema 的节点 SHALL 支持可选字段 `tracks`：值为一个具体的产物路径（相对 artifact 根目录），表示"本节点的完成度由该文件中的 Markdown checkbox 追踪"。普通节点与 gate 节点都可以声明 `tracks`；未声明 `tracks` 的节点行为与本字段引入前完全一致。

加载时 SHALL 对 `tracks` 执行以下语义校验，任一不满足即报 `schema_invalid`：
- `tracks` 必须是安全相对路径（禁止绝对路径、`..`、空路径段）；
- `tracks` 不得包含 glob 字符（`*`、`?`、`[`），因为进度必须来自一个确定的文件；
- `tracks` 必须等于 schema 中某个节点声明的 `generates` 值（即被追踪的文件必须是图中某个节点的产物，而不是凭空的路径）；
- 声明该 `generates` 的节点必须是 `tracks` 声明方在依赖图中的祖先（含直接依赖与传递依赖），否则该节点可能在被追踪节点尚未产出时就被判定进度。

#### Scenario: tracks 指向祖先节点的产物
- **WHEN** 某节点声明 `tracks: tasks.md`，且 `tasks` 节点（`generates: tasks.md`）是它的传递祖先
- **THEN** 加载通过

#### Scenario: 未声明 tracks 的 schema 不受影响
- **WHEN** schema 中所有节点都未声明 `tracks`
- **THEN** 加载与状态推导行为与本字段引入前完全一致

#### Scenario: tracks 是 glob
- **WHEN** 某节点声明 `tracks: "specs/**/*.md"`
- **THEN** 系统报 `schema_invalid`，提示 `tracks` 必须是具体文件路径

#### Scenario: tracks 路径不安全
- **WHEN** 某节点的 `tracks` 是绝对路径或包含 `..`
- **THEN** 系统报 `schema_invalid`

#### Scenario: tracks 不对应任何节点产物
- **WHEN** 某节点声明 `tracks: todo.md`，但 schema 中没有任何节点的 `generates` 为 `todo.md`
- **THEN** 系统报 `schema_invalid`，提示 `tracks` 必须指向某个节点声明的 `generates`

#### Scenario: tracks 指向非祖先节点的产物
- **WHEN** 某节点声明的 `tracks` 对应的产物属于一个与它没有依赖关系（或是其后继）的节点
- **THEN** 系统报 `schema_invalid`，提示被追踪的节点必须是该节点的祖先
