## ADDED Requirements

### Requirement: Markdown checkbox 任务进度解析
系统 SHALL 从被追踪文件的 Markdown 内容中解析任务清单：以 `-` 或 `*` 开头、紧跟 `[ ]`/`[x]`/`[X]` 的行 SHALL 被识别为一条任务（`[x]`/`[X]` 视为已完成，大小写不敏感），其余行 SHALL 被忽略。解析结果 SHALL 包含按出现顺序编号的任务列表（每条含序号 `id`、去除 checkbox 标记后的描述 `description`、完成标记 `done`）与聚合进度 `total`/`complete`/`remaining`。文件不存在或读取失败 SHALL 返回空任务列表与全 0 进度，且不抛出异常。

#### Scenario: 混合勾选状态的任务文件
- **WHEN** 被追踪文件含 3 条 `- [x]` 与 2 条 `- [ ]` 任务行
- **THEN** 解析结果 `total` 为 5、`complete` 为 3、`remaining` 为 2，任务列表按出现顺序编号

#### Scenario: 非 checkbox 行被忽略
- **WHEN** 被追踪文件含 `## 1. 分组标题`、普通段落、以及不带 checkbox 的 `- 列表项`
- **THEN** 这些行都不计入 `total`

#### Scenario: 大写 X 视为已完成
- **WHEN** 某任务行写作 `- [X] 任务描述`
- **THEN** 该任务的 `done` 为 `true`

#### Scenario: 被追踪文件不存在
- **WHEN** 被追踪文件在 artifact 根目录下不存在
- **THEN** 返回空任务列表与 `total`/`complete`/`remaining` 全为 0，不抛出异常

### Requirement: 声明 tracks 的节点的完成性硬约束
对声明了 `tracks` 的节点，系统在推导 `completed` 集合时 SHALL 在原有产物存在性判定（普通节点产物存在 / gate 判定为 PASS）之外，额外要求被追踪文件的任务全部完成：被追踪文件不存在、其中没有任何 checkbox（`total == 0`）、或存在未勾选的 checkbox（`remaining > 0`）时，该节点 SHALL 不被计入 `completed`，因而不判定为 `done`；此时若其依赖均已完成，该节点状态为 `ready`（即"还有任务没做完，继续做"）。

gate 的 FAIL 判定 SHALL 优先于本约束：被追踪任务是否完成不影响"fail 产物存在 → `failed`/`exhausted`"的判定。

#### Scenario: 产物已写出但任务未全部勾选
- **WHEN** 某声明 `tracks` 的 gate 节点的 pass 产物已存在，但被追踪文件中仍有未勾选的 checkbox
- **THEN** 该节点状态为 `ready` 而非 `done`，`isComplete` 为 `false`

#### Scenario: 产物已写出且任务全部勾选
- **WHEN** pass 产物存在且被追踪文件的全部 checkbox 均已勾选
- **THEN** 该节点状态为 `done`

#### Scenario: 被追踪文件没有任何任务
- **WHEN** pass 产物存在，但被追踪文件中不含任何 checkbox 行
- **THEN** 该节点不判定为 `done`（视为"无可执行任务，需先补齐任务清单"）

#### Scenario: fail 产物优先于任务进度
- **WHEN** 某声明 `tracks` 的 gate 节点的 fail 产物存在，无论被追踪任务勾选到什么程度
- **THEN** 该节点状态按回退次数推导为 `failed` 或 `exhausted`

#### Scenario: 未声明 tracks 的节点判定不变
- **WHEN** 某节点未声明 `tracks`，其产物已存在
- **THEN** 该节点判定为 `done`，与本约束引入前完全一致
