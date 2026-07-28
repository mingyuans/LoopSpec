## ADDED Requirements

### Requirement: 归档只允许移动，不允许删除
`loopspec archive` 与 `loopspec bulk-archive` SHALL 只把 change 目录**移动**到 `<workflow_home>/archive/YYYY-MM/`，任何情况下 SHALL 不删除原始文件；`YYYY-MM` SHALL 取归档执行时刻所在的年月。

#### Scenario: 归档执行后文件被移动而非删除
- **WHEN** 对一个可归档的 change 执行 `loopspec archive <change-name>`（未传 `--dry-run`）
- **THEN** 该 change 目录出现在 `<workflow_home>/archive/YYYY-MM/<change-name>/`，原 `changes/<change-name>/` 路径不再存在，且没有任何文件被物理删除

### Requirement: 默认直接执行，可选 --dry-run 预览
`loopspec archive <change-name>` 与 `loopspec bulk-archive [filters]` SHALL 默认直接执行归档：通过安全拦截规则（见下）后立即把符合条件的 change 移动到归档目录，不要求任何额外的确认参数（不提供、不要求 `--apply`）。两个命令 SHALL 都支持可选的 `--dry-run` 标志，传入时只计算并返回将被移动的 change 及其目标路径，不产生任何文件系统变更。

#### Scenario: 单个归档默认直接执行
- **WHEN** 执行 `loopspec archive <change-name> --json`（未传 `--dry-run`）且该 change 通过安全拦截规则
- **THEN** 该 change 目录立即被移动到归档路径，响应中 `moved: true`

#### Scenario: 单个归档传入 --dry-run 时不移动
- **WHEN** 执行 `loopspec archive <change-name> --dry-run --json`
- **THEN** 返回 `dryRun: true` 及计算出的 `source`/`destination`，该 change 目录未被移动

#### Scenario: 批量归档默认直接执行
- **WHEN** 执行 `loopspec bulk-archive --json`（未传 `--dry-run`）
- **THEN** 立即移动全部满足过滤条件且通过安全拦截规则的候选 change，其余 change 不受影响

#### Scenario: 批量归档传入 --dry-run 时不移动
- **WHEN** 执行 `loopspec bulk-archive --dry-run --json`
- **THEN** 返回全部候选 change 的 `source`/`destination` 列表，不移动任何文件

### Requirement: 归档安全拦截规则
`loopspec archive`/`loopspec bulk-archive` 默认 SHALL 只允许归档已 `isComplete` 的 change；已 `exhausted` 的 change SHALL 需要显式传入 `--exhausted` 才能被归档；存在 `failed`（尚可回退）状态节点的 change SHALL 默认拒绝归档并报 `archive_unsafe`，除非显式传入 `--include-pending-failures`——即便传入该参数，仍只能移动而不能删除。

#### Scenario: 默认只归档已完成 change
- **WHEN** 执行 `loopspec archive <change-name>`，该 change 未完成（存在 `blocked`/`ready` 节点）
- **THEN** 报 `archive_unsafe`

#### Scenario: exhausted change 需要显式参数
- **WHEN** 目标 change 存在处于 `exhausted` 状态的 gate，且未传 `--exhausted`
- **THEN** 报 `archive_unsafe`；传入 `--exhausted` 后可正常归档

#### Scenario: 存在待回退的 failed change 默认拒绝
- **WHEN** 目标 change 存在处于 `failed` 状态（尚可执行 rollback）的 gate，且未传 `--include-pending-failures`
- **THEN** 报 `archive_unsafe`

#### Scenario: 显式允许 pending failure 仍只移动
- **WHEN** 传入 `--include-pending-failures` 归档一个存在 `failed` gate 的 change
- **THEN** change 目录被移动到归档路径，产物文件不被删除或修改

### Requirement: bulk-archive 过滤参数
`loopspec bulk-archive` SHALL 支持以下过滤参数：`--complete`（只归档已完成 change，默认开启）、`--exhausted`（包含已重试耗尽的 change）、`--older-than DAYS`（只归档最后修改时间早于指定天数的 change）、`--dry-run`（只预览候选并计算目标路径，不执行移动；未传时直接执行移动）。

#### Scenario: 按最后修改时间过滤
- **WHEN** 传入 `--older-than 30`
- **THEN** 候选列表只包含最后修改时间早于 30 天前的已完成 change

### Requirement: 归档目标冲突检测
若归档目标路径 `<workflow_home>/archive/YYYY-MM/<change-name>/` 已存在，`loopspec archive`/`loopspec bulk-archive` SHALL 报 `archive_conflict`，不覆盖已有归档内容。

#### Scenario: 归档目标已存在
- **WHEN** 目标归档路径下已存在同名 change 目录
- **THEN** 系统报 `archive_conflict`，不执行移动、不覆盖已有内容

### Requirement: 归档响应契约
归档命令的响应 SHALL 包含足够信息供调用方确认操作结果：单个归档含 `dryRun`/`changeName`/`schemaName`/`reason`/`source`/`destination`/（实际执行时的）`moved`/`nextSteps`；批量归档含 `dryRun`/`archiveRoot`/`candidates`（每项含 `changeName`/`schemaName`/`reason`/`source`/`destination`）/（实际执行时的）`moved` 列表/`nextSteps`。

#### Scenario: 直接执行后的响应提示后续动作
- **WHEN** 归档命令未传 `--dry-run` 并成功移动了 change
- **THEN** 响应中 `moved: true`，`nextSteps` 提示后续可执行的动作（如查看归档目录），不提示需要额外确认参数

#### Scenario: dry-run 响应提示下一步
- **WHEN** 执行任意归档命令并传入 `--dry-run`
- **THEN** 响应中 `dryRun: true`，`nextSteps` 明确提示"确认无误后去掉 `--dry-run` 重新执行以真正移动"
