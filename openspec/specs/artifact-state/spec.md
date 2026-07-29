# artifact-state Specification

## Purpose
TBD - created by archiving change gated-artifact-workflow. Update Purpose after archive.
## Requirements
### Requirement: 产物存在性判定
系统 SHALL 通过扫描 artifact 根目录判定某节点的产物是否存在：非 glob 的 `generates` 直接检查目标文件是否存在；glob 形式的 `generates` 使用 `Path.glob` 匹配并按路径排序返回全部匹配文件。判定 SHALL 排除 `.attempts/` 目录下的任何文件，以及 change 级保留文件（`.workflow.yaml`、`state.md`），即使它们落在 glob 匹配范围内。

#### Scenario: glob 节点匹配到多个文件
- **WHEN** 节点 `generates` 为 glob 模式且在 artifact 根目录下匹配到一个或多个文件
- **THEN** 节点判定为产物存在（`done`），返回全部匹配文件路径且已排序

#### Scenario: glob 节点无匹配
- **WHEN** 节点 `generates` 为 glob 模式但没有匹配到任何文件
- **THEN** 节点判定为产物不存在

#### Scenario: .attempts 目录下的归档文件不计入产物
- **WHEN** 节点 `generates` 为宽泛 glob（如 `**/*.md`），且 `.attempts/round-001/` 下存在同名归档文件
- **THEN** 该归档文件不被计入该节点的产物存在性判定

#### Scenario: state.md 不计入任何节点产物
- **WHEN** 节点 `generates` 为宽泛 glob 且 `state.md` 恰好匹配该模式
- **THEN** `state.md` 不被计入该节点的产物存在性判定

### Requirement: Gate 判定的产物互斥规则
系统 SHALL 依据 `gate.outputs.pass`/`gate.outputs.fail` 两个具体路径的存在性判定 gate 结果：仅 pass 存在 → `PASS`；仅 fail 存在 → `FAIL`；两者都不存在 → 尚无判定（`None`）；两者同时存在 SHALL 抛出 `gate_output_conflict` 错误。

#### Scenario: 仅 pass 产物存在
- **WHEN** gate 的 pass 文件存在，fail 文件不存在
- **THEN** 判定结果为 `passed=True, status=PASS`

#### Scenario: 仅 fail 产物存在
- **WHEN** gate 的 fail 文件存在，pass 文件不存在
- **THEN** 判定结果为 `passed=False, status=FAIL`

#### Scenario: pass/fail 都不存在
- **WHEN** gate 的 pass、fail 文件都不存在
- **THEN** 判定结果为 `None`（尚未产出判定）

#### Scenario: pass/fail 同时存在
- **WHEN** gate 的 pass、fail 文件同时存在
- **THEN** 系统抛出 `gate_output_conflict` 错误

### Requirement: Gate 失败摘要提取
系统 SHALL 尽力从 gate 的 fail 产物 Markdown 内容中提取摘要（首个一级标题文本）与阻断问题列表（无序列表项）；提取失败（无可提取内容）SHALL 不阻塞状态推导，摘要返回 `None`，阻断问题列表返回空数组。

#### Scenario: fail Markdown 含一级标题
- **WHEN** fail 产物内容以 `# 标题文本` 开头
- **THEN** 提取的 `summary` 为该标题文本（去除 `#` 与首尾空格）

#### Scenario: fail Markdown 含无序列表
- **WHEN** fail 产物内容包含形如 `- 问题描述` 的行
- **THEN** 每一行被提取为 `blockingIssues` 数组中的一项

#### Scenario: fail Markdown 无可提取内容
- **WHEN** fail 产物内容既无一级标题也无无序列表
- **THEN** `summary` 为 `None`，`blockingIssues` 为空数组，且不抛出异常

### Requirement: 节点五态推导
系统 SHALL 按拓扑序两趟计算节点状态：第一趟确定 `completed` 集合（非 gate 节点产物存在，或 gate 判定为 PASS）；第二趟据此为每个节点计算对外状态 `blocked`（存在未完成依赖）、`ready`（依赖齐备且产物尚未生成或已被回退清空）、`done`（已完成）、`failed`（仅 gate：fail 产物存在且回退次数未耗尽）、`exhausted`（仅 gate：fail 产物存在且回退次数已耗尽）。

#### Scenario: 空 change 目录
- **WHEN** change 刚创建，尚无任何产物文件
- **THEN** 拓扑序中第一个节点（无依赖）状态为 `ready`，其余节点状态为 `blocked`

#### Scenario: 首节点产物存在
- **WHEN** 拓扑序第一个节点的产物文件已生成
- **THEN** 该节点状态为 `done`，其直接后继（依赖已齐备）状态变为 `ready`

#### Scenario: gate pass 产物存在
- **WHEN** 某 gate 的 pass 产物存在
- **THEN** 该 gate 状态为 `done`，其下游节点按 `requires` 继续推进为 `ready`/`blocked`

#### Scenario: gate 不是最后节点时仍可继续推进
- **WHEN** 某 gate PASS 且该 gate 存在下游节点
- **THEN** `isComplete` 的判定仍取决于全部节点是否都完成，不因该 gate 完成而提前判定为 `true`

#### Scenario: gate fail 产物存在且未达重试上限
- **WHEN** 某 gate 的 fail 产物存在，且该 gate 已用回退次数 `< max_retries`
- **THEN** 该 gate 状态为 `failed`，其下游节点保持 `blocked`

#### Scenario: gate FAIL 且回退次数达到上限
- **WHEN** 某 gate 的 fail 产物存在，且已用回退次数 `== max_retries`
- **THEN** 该 gate 状态为 `exhausted`

#### Scenario: max_retries 为 0 且首次 FAIL
- **WHEN** 某 gate 的 `on_fail.max_retries` 配置为 `0`，且首次判定为 FAIL
- **THEN** 该 gate 直接状态为 `exhausted`（不允许任何回退）

#### Scenario: gate 依赖未满足
- **WHEN** 某 gate 节点的 `requires` 尚未全部完成
- **THEN** 该 gate 状态为 `blocked`，系统不读取该 gate 的产物判定结果

#### Scenario: 多个 gate 独立推导
- **WHEN** schema 中含多个 gate 节点
- **THEN** 每个 gate 各自独立按自身 pass/fail 产物推导状态，互不影响

#### Scenario: 全部节点完成
- **WHEN** schema 中所有节点状态均为 `done`
- **THEN** `isComplete` 为 `true`

### Requirement: 回退次数持久化统计
系统 SHALL 通过扫描 change 目录下 `.attempts/round-*/_meta.yaml` 文件，统计 `meta.gate == <gate_id>` 的 round 数量作为该 gate 的 `rollbacksUsed`；不完整的 round（缺少 `_meta.yaml`）SHALL 不计入统计。该统计 SHALL 在进程重启、Agent 会话中断后仍从磁盘重新计算，得到与中断前一致的结果。

#### Scenario: 重启后再次 status 得到相同回退次数
- **WHEN** Human 或 Agent 进程重启后，对同一 change 执行 `loopspec status`
- **THEN** 返回的 `rollbacksUsed` 与 `exhausted`/`failed` 判定与重启前完全一致

#### Scenario: 缺少 _meta.yaml 的 round 不计数
- **WHEN** `.attempts/round-002/` 目录存在但缺少 `_meta.yaml` 文件
- **THEN** 该 round 不计入对应 gate 的 `rollbacksUsed`

### Requirement: state.md 内容不参与状态判定
系统在推导任何节点状态时 SHALL 完全忽略 `state.md` 的正文内容，即使正文中标注某 artifact 为 `approved` 或包含其他语义标签。

#### Scenario: state.md 标注与实际产物矛盾
- **WHEN** `state.md` 中标注某 artifact 为 `approved`，但对应的产物文件实际不存在
- **THEN** 该节点状态仍以产物文件推导为 `ready` 或 `blocked`（而非 `done`），不受 `state.md` 标注影响

#### Scenario: 删除或清空 state.md 不影响节点状态
- **WHEN** `state.md` 被删除或清空
- **THEN** 所有节点的完成状态推导结果不变，仅 `instructions` 响应中的 `state` 上下文受影响

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
