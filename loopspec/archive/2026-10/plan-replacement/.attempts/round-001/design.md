## Context

`dynamic-workflow-composition` 与 `plan-draft-approval`（均未归档、未发布）已经提供：

- 每个修订是 `.workflow/plans/<NNN>/` 下的不可变快照，`previous_digest` 串成摘要链（`workflow_snapshot.materialize`）。
- `.workflow.yaml` 的 `ChangeLifecycle` 只有一个 `active` 指针与一个 `draft` 绑定。
- 草稿是 `.workflow/drafts/<draft-id>/` 下的不可变快照；`plans approve --expected-digest` 通过 `ConfirmationTransaction` 激活：先写 `.workflow/transaction.yaml`，再按 `Move` 归档失效节点的产物与 Gate 文件、写 `.workflow/revisions/<NNN>/record.yaml`、切换指针、删除事务文件；`inspect` 只读校验，`finish` 幂等，`recover` 只续做已确认事务。
- 修订只有两种：普通重组（`validate_frozen` 冻结完成/当前/失败/有历史的节点、实例边界与恢复链）和安全扩张（只增加诊断建议的 Fragment）；有效 FAIL 未处理时两者均拒绝。

缺口（见 proposal）：任务变化后无法重组已执行部分；状态按文件存在推导，新 Plan 同名节点会隐式继承旧完成状态；`.attempts` 按处理者 ID 跨全部历史累计，且 `instructions` 遇到不属于当前 Plan 的历史来源会报 `history_integrity`；草稿等待确认期间旧图仍可推进；无法撤销草稿。

约束：本地 CLI；请求、报告、路径为不可信输入；保留四层模型与 requires + on_fail；不引入新执行引擎；旧 Schema Change 不受影响。

## Goals / Non-Goals

**Goals:**
- 一个 Change 保存多份 Plan，同一时间最多一个 active Plan，历史完整保留。
- 任务变化后可构建完整替换 Plan，经草稿展示与明确确认后原子切换。
- 旧成果默认不继承，沿用、承接、放弃都显式声明并校验。
- 替换不能绕过固定基线、项目约束、已有改动的保障覆盖与人工确认。
- 切换中断后可检查、可续做，任何时刻只有一个活动指针。

**Non-Goals:**
- 多个 Plan 同时执行或按阶段滚动规划。
- 跨 Change 迁移成果；更换固定基线或仓库。
- 沿用任何 Gate 结论（普通 PASS 或代码证据）。
- 自动判断旧成果是否仍然正确；沿用由 LLM 提议、人确认。

## Decisions

### D1：修订号仍是 Plan 身份，用 mode 区分修订类型

`RevisionContext` 用 `mode: initial | revise | expand | replace` 替代 `safety_expansion` 布尔值，并新增：

- `history_boundary: int`：替换草稿创建时 `.attempts` 的最大轮次；`revise`/`expand` 从基础修订原样继承，`initial` 为 0。
- `replacement: Replacement | None`：仅 `mode: replace` 时存在，记录处置清单（D2）。

`Plan.version` 升为 3 承载以上字段。版本 2 快照仍按原字段读取、按原 `plan_payload` 计算摘要；加载时把 `safety_expansion` 映射为 `expand`/`revise`、`history_boundary` 视为 0。`ChangeLifecycle` 与 `PlanMetadata` 不变。

**备选**：新增 `plan_id` / epoch 字段。拒绝：修订号单调、连续且已用于快照、确认与审计目录，替换只是 mode 不同的修订，额外身份只会产生第二套编号。

### D2：替换请求与校验

`plans create <change> --plan <request> --replace`，与 `--safety-expansion` 互斥。请求必须带 `base_revision`（等于当前活动修订）与 `replaces`：

```yaml
replaces:
  reason: 需求从仅后端改为前后端，并取消导出功能
  reuse:                       # 新产物节点 ← 旧产物节点
    requirements/proposal: requirements/proposal
  carry:                       # 旧 Gate 的有效 FAIL → 新 flow 实例
    qa/test: be
  retire:                      # 旧 flow 实例 → 放弃原因
    export: 导出功能已取消
```

`validate_replacement(active, proposed)` 与 `validate_frozen` 并列，替换模式不调用后者。校验（全部失败均拒绝创建草稿，确认时重新执行并要求结果一致）：

1. 固定约束：`project`、`assurance_rules`、`baseline`、`repository` 与旧 Plan 相同；`engine_version` 不降低。
2. `reuse`：键为新 Plan 中 `generates` 不含通配符的产物节点，值为旧 Plan 中状态为 done 的产物节点且恰有一个输出文件；记录旧路径、`sha256`、`size` 到 `replacement.reuse` 并参与摘要。Gate 节点不能出现在 `reuse` 的任何一侧。
3. `carry`：键为旧 Plan 中状态为 failed（有效 FAIL 且仍有处理者预算）的 Gate，值为新 flow 实例 ID；记录失败报告路径与摘要。状态为 exhausted 的 Gate 不能 carry。
4. `retire`：旧 flow 中 ID 不再出现在新 flow 的实例必须列出且原因非空；列出新 flow 中仍存在的 ID 被拒绝。旧 flow 中每个有效 FAIL 或 exhausted 的 Gate 必须被 `carry`，或其所属实例被 `retire`。
5. 覆盖检查：Plan 有保障规则时，用当前全量 Diff 对照**新 Plan** 的能力提供者运行保障诊断；`missing_fragments` 或 `unknown_paths` 非空即拒绝（`coverage_missing`），防止替换遗漏已有改动。无保障规则时跳过，与现有保障一致。
6. `history_boundary` 取当前 `.attempts` 最大轮次；确认时若出现更大轮次则拒绝（D3 保证暂停期间不会出现）。

字符串（reason、retire 原因）有长度上限；所有键值先通过实例/节点身份正则与“存在于对应 Plan”校验，不作为路径直接使用。

### D3：替换草稿使活动 Plan 暂停

存在 `mode: replace` 的草稿时，Change 处于 suspended（由草稿推导，不新增持久字段）。`status` 返回 `suspended: true` 与 `pendingReplacement`，`nextSteps` 只指向 `plans show`。`instructions`、`next`、`gate begin/record`、`rollback`、`assurance check` 统一经 `require_runnable(root)` 检查并返回 `plan_suspended`。普通修订与安全扩张草稿不暂停（行为不变）。

### D4：撤销草稿

新增 `plans discard <change> [--expected-digest <digest>]`：在写锁内、无未完成事务时，清除 `draft` 绑定并写 `.workflow/discards/<draft-id>.yaml`（草稿 ID、摘要、时间、可选说明）；草稿快照原地保留。适用于任何模式的草稿；撤销替换草稿即恢复执行当前活动 Plan。

### D5：替换切换复用确认事务

`approve` 对替换草稿：

1. 复核 D2 全部校验，结果须与草稿一致。
2. `moves` = 旧 Plan **全部节点**的 `closure_files`（产物、PASS/FAIL 报告、`.workflow/gates/<id>/` 下的 begin/evidence/assurance），目标 `.workflow/revisions/<NNN>/files/<原路径>`。
3. 新增 `copies: list[Copy]`（`source` 为沿用产物的归档路径，`target` 为新节点输出路径，`sha256`）。
4. `finish` 依次：执行剩余 moves → 对每个 copy，若 target 不存在则从 source 复制并校验摘要 → 写审计记录 → 切换 `active`/清空 `draft`/写 `approval` → 删除事务文件。

`inspect` 额外校验：copies 的 target 必须是新 Plan 中被 reuse 的产物路径、source 必须是本事务 moves 的目标；target 已存在时摘要必须一致；source 在 move 前或后都按 `sha256` 校验。`ConfirmationTransaction` 新增 `copies` 字段（默认空，旧事务文件仍可读）。`.workflow/gate-rounds/` 历史不移动：其轮次号按 Gate 身份继续递增，证据绑定 Plan 摘要，不会被新 Plan 继承。

指针只有一个且原子写入，任何中断点要么仍指向旧修订（事务待续做），要么已指向新修订（只剩删除事务文件）；不存在两个活动 Plan。

### D6：历史边界与返工预算

- `attempt_records(root, boundary)` 只返回 `round > boundary` 的记录用于计数、`validate_attempt` 与 `priorAttempts`；`boundary` 取活动 Plan 的 `history_boundary`。边界之前的记录只读保留，`plans history` 按修订列出。
- 新 Plan 的处理者计数从 0 开始。防止借替换清空预算：替换必须人工确认；草稿展示旧 FAIL/exhausted 及其处置；exhausted 只能 retire。
- `carry` 的失败报告随归档移动到修订目录；`instructions` 对被承接实例的根节点返回 `inheritedFailures`（来源修订、Gate、报告路径与摘要），标注为不可信数据。
- 替换之后的普通修订/扩张继承同一 `history_boundary`，预算在新 Plan 内继续累计。

### D7：CLI 与 Skill

- `plans show`：替换草稿展示旧修订摘要、`replaces` 处置、将归档文件数、沿用摘要、覆盖检查结果。
- `plans history`：每个修订增加 `mode`、`reason`、`historyBoundary`、该修订期间的返工记录摘要。
- `status`：增加 `suspended`、`pendingReplacement`。
- `loopspec-new`：明确初始 Plan 覆盖完整任务。`loopspec-continue`：判断任务变化使 Plan 不适用时停止推进，构建替换请求，展示并等待确认；不得自行 discard 或 approve。

### D8：安全边界（供安全审查）

- **输入**：替换请求经严格 YAML 与 strict 模型加载；`reuse`/`carry`/`retire` 键值只能是两份 Plan 中已存在的规范身份，未知或越界一律拒绝；原因文本限长。
- **路径**：moves 与 copies 的源和目标都由引擎从 Plan 定义计算（`closure_files`、`generates` 输出、修订归档目录），请求不能提供路径；事务校验拒绝任何不属于旧节点输出或新沿用目标的路径，业务代码永远不在移动或复制范围内。
- **授权**：替换与撤销不放宽人工确认；Skill 不得替人 approve/discard；`--expected-digest` 防止确认被替换的草稿。本地记录不认证身份，文档如实说明。
- **完整性**：沿用内容绑定草稿摘要；确认时内容变化即拒绝；覆盖检查防止通过替换遗漏已改代码的审查。
- 不新增依赖、网络访问或 Shell 调用。

## Risks / Trade-offs

- [替换清空重试计数] → 人工确认 + exhausted 只能 retire + 草稿完整展示历史；记录全部保留可审计。
- [默认全部归档导致重复工作] → 用 reuse 显式沿用文档产物；Gate 重跑是有意的安全取舍。
- [暂停影响进度] → 只有替换草稿暂停；可随时 discard 恢复。
- [覆盖检查使草稿被拒] → 诊断返回缺失能力与建议 Fragment，LLM 修正请求后重建。
- [Plan 版本 3 增加读取分支] → 版本 2 读取路径不变，用已有快照测试覆盖。

## Migration Plan

1. 先加模型与版本 3 读取（保持版本 2 兼容），再加替换校验、暂停与撤销，最后接入确认事务与历史边界。
2. 旧 Schema Change 不涉及；开发期版本 1/2 Plan 按原方式读取，`history_boundary` 视为 0，无需迁移脚本。
3. 回滚：未发布前回滚提交即可恢复原有两种修订行为。

## Open Questions

- 无阻塞问题。proposal 中的三个待定点已在本设计确定：carry 以新 flow 实例为目标并挂在其根节点；撤销的草稿快照原地保留并写 discards 记录；无保障规则时跳过覆盖检查。
