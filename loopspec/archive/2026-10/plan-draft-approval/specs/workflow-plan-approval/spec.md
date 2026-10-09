> **已被 `plan-replacement` 取代（2.0.0）。** 下列内容以 `loopspec/changes/plan-replacement/design.md` 为准：
> - 草稿不可变快照目录、确认记录目录、`PlanMetadata`/`DraftBinding`/`ConfirmationRecord` 与 Change 格式 3 → 每份 Plan 一个 `plan.yaml`，`meta.status` 为 `draft`/`approved`/`archived`，确认只写 `meta.digest` 与 `meta.approved_at`；Change 级 `.workflow.yaml` 格式 4（D3、D4）。
> - `plans create/show/approve/recompose`、`--expected-digest`、`--message`、`--safety-expansion` → `plan create/show/approve`（`--digest`），修订用 `plan validate -f` 预览、`plan approve -f --digest` 确认（D5、D12）。
> - 确认事务与 `recover --inspect/--resume` → 固定写入顺序、最后一步为生效点，重新执行同一命令收敛（D8）。
> - 一个 Change 只有一份 Plan → 一个 Change 可有多份 Plan、同一时间最多一份未结束；任务变化时经人同意 `plan archive` 后重新规划（D3、D9）。

## ADDED Requirements

### Requirement: Change 先于 Plan 创建
默认 new SHALL 创建 Change 与最小元数据，SHALL NOT 选模板、编译或激活 Plan。缺少 Plan SHALL NOT 被解析成完成任务或旧 Schema 流程。

#### Scenario: 新需求尚未规划
- **WHEN** 用户执行 loopspec new AFD1111
- **THEN** Change 存在但没有活动 Plan，status 返回未规划、isComplete 为 false 和规划指引

#### Scenario: 新建元数据尚未完成
- **WHEN** new 初始化中断或与读取并发，留下可识别的新格式初始化目录
- **THEN** 未完成目录不可被解释为可执行旧 Schema Change，返回初始化/完整性错误

### Requirement: 草稿为独立不可变快照
plans create SHALL 对已存在 Change 保存校验通过的完整草稿，SHALL 绑定图、引用、理由、资源、约束、基线、基础摘要、修订模式及失效影响。草稿 ID SHALL 独立于活动修订号；创建草稿 SHALL NOT 激活或执行计划。

#### Scenario: 首次创建草稿
- **WHEN** 合法任务请求通过 plans create 保存
- **THEN** 返回 draft、planDigest、规划图与确认指引，活动绑定仍为空

#### Scenario: 讨论后调整草稿
- **WHEN** LLM 修改请求并再次 plans create
- **THEN** 系统保存新草稿并原子更新草稿绑定，旧草稿保留但不能通过旧摘要确认新内容

#### Scenario: 无效图或落盘中断
- **WHEN** 草稿无效、资源不安全或持久化失败
- **THEN** 不产生部分当前草稿，不改变已批准活动 Plan

### Requirement: 所有新计划明确确认
plans approve SHALL 只定稿已保存且完整的当前草稿，SHALL NOT 从来源重新生成计划或接受审批 YAML 文件。确认 SHALL 与该草稿摘要绑定，SHALL 记录修订、时间和可选真实原话；本地记录 SHALL NOT 声称认证了人的身份。

#### Scenario: 完整模板仍需确认
- **WHEN** plans create 直接采用完整 Profile 且没有偏离
- **THEN** Plan 仍为草稿，只有明确 approve 后才允许首次执行

#### Scenario: 精确摘要批准
- **WHEN** 人确认草稿且调用 approve 的 expected digest 与当前草稿匹配
- **THEN** 同一份草稿缓存被定稿为下一活动修订，返回 approved 与同一有效摘要

#### Scenario: 确认期间草稿被替换
- **WHEN** approve 提交先前展示的摘要，但当前草稿已变
- **THEN** 返回 plan_changed，活动绑定不变，要求确认新的草稿

#### Scenario: 同一批准重复提交
- **WHEN** 同一已定稿草稿的确认被重复提交
- **THEN** 返回既有批准结果，不新建修订、不重置产物或历史预算

### Requirement: 未批准草稿不能成为执行输入
首次活动 Plan 为空时，执行、代码 Gate、保障、返工与完成归档 SHALL 拒绝草稿。已有活动 Plan 时，执行器 SHALL 只读取原已批准图，SHALL NOT 自动采用待确认草稿。

#### Scenario: 草稿有手写 PASS
- **WHEN** 未批准 Change 的 artifacts 中已有产物或 PASS
- **THEN** instructions/Gate/保障/返工/完成归档返回 plan_not_approved，不能显示完成

#### Scenario: 新修订待确认
- **WHEN** 已批准修订 1 上保存修订草稿
- **THEN** 活动图与既有执行不变，status 明示待确认草稿，新图不能被执行

### Requirement: 确认复核固定约束
确认 SHALL 持逐 Change 写锁，检查草稿完整性、基础活动摘要/版本、项目政策及规则摘要、冻结节点/资源/恢复链和历史预算。源 Fragment/Profile/指令 SHALL 仍使用草稿缓存；HEAD 变化 SHALL NOT 改写原固定基线。

#### Scenario: 来源在确认前被删除
- **WHEN** 草稿完整但源 Fragment/Profile/指令删除
- **THEN** 在项目政策与基准仍有效时，可按原草稿缓存确认，不更换计划内容

#### Scenario: 项目政策改变
- **WHEN** 项目最低要求或政策规则字节在创建草稿后改变
- **THEN** approve 拒绝陈旧政策快照，要求重建草稿，不能用人工原话豁免最低要求

#### Scenario: 活动版本变化
- **WHEN** 另一个批准先更新活动计划
- **THEN** 旧基准草稿不能覆盖新活动计划，返回 stale_revision

### Requirement: 安全扩张批准前无返工副作用
修订和安全扩张 SHALL 先保存草稿并取得本轮确认；创建草稿 SHALL NOT 移动产物、失效 QA 或清零预算。批准 SHALL 再复核扩张授权，把必要失效与激活放入可恢复事务；恢复 SHALL NOT 批准未确认草稿。

#### Scenario: FE 扩张为 BE
- **WHEN** Assurance 建议增加 BE 且草稿包含完整修复及原 QA 新依赖
- **THEN** 草稿展示新增成员与失效影响，只有批准后才归档旧 QA/Assurance 并激活新图

#### Scenario: 批准事务中断
- **WHEN** 明确批准后的移动、激活或收尾中断
- **THEN** 执行被未恢复事务阻塞，recover 完成已批准事务而不回退业务代码或重复增加修订
