> **已被 `plan-replacement` 取代（2.0.0）。** 下列内容以 `loopspec/changes/plan-replacement/design.md` 为准：
> - 草稿不可变快照目录、确认记录目录、`PlanMetadata`/`DraftBinding`/`ConfirmationRecord` 与 Change 格式 3 → 每份 Plan 一个 `plan.yaml`，`meta.status` 为 `draft`/`approved`/`archived`，确认只写 `meta.digest` 与 `meta.approved_at`；Change 级 `.workflow.yaml` 格式 4（D3、D4）。
> - `plans create/show/approve/recompose`、`--expected-digest`、`--message`、`--safety-expansion` → `plan create/show/approve`（`--digest`），修订用 `plan validate -f` 预览、`plan approve -f --digest` 确认（D5、D12）。
> - 确认事务与 `recover --inspect/--resume` → 固定写入顺序、最后一步为生效点，重新执行同一命令收敛（D8）。
> - 一个 Change 只有一份 Plan → 一个 Change 可有多份 Plan、同一时间最多一份未结束；任务变化时经人同意 `plan archive` 后重新规划（D3、D9）。

## MODIFIED Requirements

### Requirement: Profile 是可复用的 Fragment 工作流模板
Profile SHALL 以 flow 声明 Fragment 实例及依赖，支持串行/并行、说明、LLM 指引和有限恢复规则。Profile SHALL NOT 保存状态或审批结果，SHALL NOT 通过 protected 承担模板偏离许可。目录发现、校验、保存与复用 SHALL 保留。

#### Scenario: 前后端并行模板
- **WHEN** fe、be 同时依赖 design，qa 依赖 fe 与 be
- **THEN** 批准后的执行图允许 FE/BE 并行，任一分支未完成时 QA 不能执行

#### Scenario: 保存批准计划为模板
- **WHEN** 从活动 Plan 保存 Profile
- **THEN** 保存定义、路由和指引，不保存审批、证据、预算、状态或模板偏离保护字段

### Requirement: LLM 可直接采用或参考 Profile 生成 Plan
请求 SHALL 完整指定 flow、recovery 和 reasons，based_on SHALL 可选。系统 SHALL 校验项目要求而不从 prose 推断执行边；任何合法提议 SHALL 先为草稿，不能从模板选择推断为已批准。

#### Scenario: 自行组合小需求
- **WHEN** LLM 仅选择相关 FE 修复、QA 和保障 Fragment
- **THEN** 可构建满足项目最低约束的轻量草稿，不强制采用大型模板，并等待人类确认

#### Scenario: 自行组合
- **WHEN** 请求不指定 based_on，但定义合法 Fragment 图与每个实例的 reasons
- **THEN** 项目最低约束满足时可以创建草稿，仍需本轮人类确认

### Requirement: 项目最低保护不能通过换模板绕过
项目配置的最低保障 SHALL 固化并强制校验，SHALL NOT 通过模板选择、deviations 或人工原话豁免。模板偏离不再触发另一套可选审批；全部 Plan SHALL 通过统一确认。未知路径失败、证据一致性及最终保障覆盖 SHALL 保持。

#### Scenario: 轻量模板缺少项目必需保障
- **WHEN** 草稿缺少项目 required_fragments 或 assurance_rules 要求的系统保障
- **THEN** 草稿创建或确认拒绝，不因提供 approve 或 message 而放行

### Requirement: 自包含不可变计划
Plan SHALL 保存叶子 DAG、引用树、归属、恢复候选链、资源、约束、固定基线与修订来源；草稿与活动使用同一有效快照语义。摘要 SHALL 覆盖有效执行内容、限额、理由、资源哈希及修订失效上下文。Plan SHALL NOT 保存完成状态，引用 SHALL 不具有黑盒执行或独立 PASS 证据。

#### Scenario: 基线保持
- **WHEN** 创建草稿后 HEAD 改变再批准
- **THEN** 批准使用草稿固定基线和缓存，不静默改用新 HEAD

### Requirement: 原子激活与并发隔离
草稿保存和确认 SHALL 使用写锁、有界缓存、安全暂存、排他目录、清单复核和原子绑定。只有明确批准的草稿 SHALL 激活；失败 SHALL NOT 暴露部分可执行计划。

#### Scenario: 两个并发批准
- **WHEN** 两个调用确认同一基础版本的候选计划
- **THEN** 只能激活一个下一修订，重复同草稿幂等，不同陈旧草稿拒绝覆盖

### Requirement: 旧格式兼容适配
旧 Schema Change 与既有活动 Plan SHALL 保留原执行生命周期，不自动重写或要求补签。新待规划元数据 SHALL 明确标识，未知格式 SHALL 拒绝而不是回退旧引擎。新修订 SHALL 走草稿确认流程。

#### Scenario: 旧活动计划继续执行
- **WHEN** 加载本轮修改前已经激活的 Plan
- **THEN** 它作为既有生效配置继续执行，新建修订草稿仍需本轮人工确认

#### Scenario: 旧 Change 回归
- **WHEN** 对已有旧 Schema Change 执行 status/instructions/rollback/archive
- **THEN** 原路径、进度推导及判定行为不变，不自动迁移到新草稿生命周期
