# Change State

## Current Focus
- apply：第 9 组（去掉 interrupted 状态）已实施并验证（make test 794 passed；make lint 通过），apply/report.md 已更新。未提交、未发布 2.0.0、未归档本变更。

## Frozen Decisions
- （2026-10-07 用户确认调整，取代下方“中断后重新执行同一命令即可收敛”与 format 4 指针字段）每条命令只有一次生效写入，中断后状态只有之前或之后，不设 interrupted 状态；.workflow.yaml 只存 change_name、created、baseline、repository，Plan 指针由 plan.yaml status 推导；生效后的归档搬运由后续命令按记录补完。
- （round 2 审批冻结，后续节点不得悄悄改变，改变需另一轮审批）任务层级 Change → Plan → Revision，组织层级 Node → Fragment → Profile → Plan，执行图即 plan.yaml 的 spec。
- Change 级 .workflow.yaml format_version 4（baseline、repository、active_plan、open_plan、next_plan，状态推导含 interrupted）；一份 Plan 一个 plans/<NNN>/plan.yaml（meta：plan、status draft/approved/archived、revision、digest、approved_at、note、created、archived_at、archive_note；spec：based_on、flow、nodes，on_fail 在 Gate 内且每 Gate 最多一条）；每份 Plan 有 state.md 与运行时目录（artifacts、.gates、.gate-rounds、.attempts）。
- 修订：plan validate -f 只读预览，plan approve -f --digest 确认；冻结节点只能增加 requires，增加依赖的节点及下游重新执行，有效 FAIL 必须在重新执行范围内；重做记录统一在 .attempts（kind rollback/revision）。
- 重新规划：经人同意 plan archive（draft 与 approved 均适用）后按初次规划流程新建 Plan；新 Plan 从空状态开始并沿用 Change 基线；资源与 config.yaml 实时读取。
- 中断后重新执行同一命令即可收敛；不设 .transaction.yaml 与 recover。
- 命令树 loopspec <资源> <动作>（change、plan、node、gate、fragment、profile），参数 -c/-p/-n/-f/--digest/--note；保障节点通过 gate record；工作流命令统一输出 JSON。
- 删除旧 Schema 流程并发布 2.0.0；按 design D11 删除新工作流中的兼容代码与重复机制；保留 change-assurance 节点、Gate 两步证据与 tracks。
- 一个 Change 保存多份 Plan，同一时间最多一个 active Plan；修订号继续作为 Plan 身份，不新增身份字段。
- 新增完整替换模式（plans create --replace）；普通重组与安全扩张的冻结规则不变。
- 替换默认不继承：旧 Plan 全部节点的产物、Gate 报告与证据归档，只有 replaces.reuse 声明的产物在摘要校验后复制。
- 替换必须草稿展示 + 明确确认；固定基线、仓库身份、项目约束不能改变；复用现有确认事务与 recover 保证原子切换。

## Decision Log
- 2026-10-07 用户确认（“approve”）：去掉 Change 的 interrupted 状态。理由：用户提出中断后状态停在之前、由 Agent 照常推进即可；方案为单一生效写入 + 去掉 Plan 指针 + 返工/修订归档延后补完。design D3、D6、D7、D8、S1、S4–S6、D12、D14 与 change-plan-lifecycle、loopspec-cli、workflow-planning、lpsx-skills 规范及 proposal 已更新，tasks 新增第 9 组。
- 2026-10-07 apply 6.6：用户选择“标注取代并保留”。artifacts-command 的 proposal、design 与 specs 顶部加注被取代，state.md 追加说明，目录保留在 changes/，不审批不归档；add-schema-sources 按用户要求不处理。
- 2026-10-07 apply 实施：按 design 重写持久化与命令树——新增 workflow_state（Change v4、plan.yaml 摘要校验、中断识别）、workflow_plans（validate/create/show/list/approve/archive/rollback 与冻结规则）、workflow_attempts（.attempts 重做记录，先写记录再按摘要归档，重新执行补完）；运行时、证据、保障、Diff 改为 Plan 目录为根、Change 级基线、实时资源与配置；编译器把 on_fail 下放到 Gate 并检测 on_fail_conflict；删除旧 Schema 模块、paths.py、快照/草稿/确认/修订/恢复模块与 builtin/schemas、manual-v1、delivery-review。paths.py 原计划保留，但新代码已不再使用，作为死代码一并删除。
- 2026-10-07 apply 实施：测试请求文件放在 changes/<change>/plans/ 下（Git Diff 已排除）；写锁移到 plans/.write.lock，避免控制文件进入 Diff。
- 2026-10-07 apply 性能：Diff 扫描对未变化路径用本地计算的 Git blob ID 比对，不再逐个 cat-file，单个内置 Profile 端到端测试从约 38s 降到约 12s，语义不变（Diff 测试全部通过）。
- 2026-10-07 apply 6.5：版本号由 Git tag 决定（hatch_version.py），仓库内无版本声明可改；已写 docs/{en,zh}/release-notes.md，发布 2.0.0 需维护者推送 v2.0.0 tag，本次未执行。
- 2026-10-07 apply 7.4：dynamic-workflow-composition 与 plan-draft-approval 的 design.md 与 specs 顶部加注被本变更取代的决策与需求，state.md 追加说明；不改写其历史正文。
- 2026-10-07 approval round 2：approved（approval/approved.md）。用户原话：“进入实施； add-schema-sources 先不管。” tasks 6.6 中 add-schema-sources 本变更不处理；artifacts-command 的处理方式待执行到 6.6 时再确认。
- 2026-10-07 用户确认恢复 plan validate -c -f：只读编译与检查，不写文件；有 approved Plan 时按修订返回预览（新摘要、新增实例、将重新执行的节点）；plan create 只负责新建或覆盖 draft Plan，有 approved Plan 时拒绝。修订流程为 plan validate -f 预览 → plan approve -f 确认。tasks 增至 44 项。
- 2026-10-07 用户决定：本变更完全删除旧 Schema 流程（schemas 命令、旧 Change 的执行、builtin/schemas/），发布为不兼容的 2.0.0；旧 Change 不自动迁移，升级前用 v1.x 完成归档。连带删除 status-report（工作流命令统一输出 JSON）与 artifact-discovery 能力、usage-docs 中 schema 参考与内置工作流文档要求；add-schema-sources 与 artifacts-command 两个变更失去意义，处理方式待用户确认（tasks 6.6）。proposal、design、specs、tasks 已整体更新。
- 2026-10-07 CLI 与恢复调整（用户确认）：命令改为 loopspec <资源> <动作>（change/plan/node/gate/fragment/profile 单数）；plan create、plan list 用 -c 指定 Change，plan approve/archive/show/rollback 另用 -p 指定 Plan 编号，node instructions 与 gate 用 -c -n；--reason 改为 --note（meta.note）；-f 为请求文件，有活动 Plan 时 plan create 只返回修订预览不写文件（取代 plans show --plan）；plan archive 适用于 draft 与 approved，删除 discard 与 discarded 状态；rollback 改为 plan rollback；删除 assurance check，保障节点通过 gate record 执行；不设 recover 与 .transaction.yaml，中断后重新执行同一命令即可收敛（固定写入顺序、最后一步为生效点、重做记录先写充当清单，change status 报告 interrupted）；change archive 去掉 --exhausted/--include-pending-failures，改为 --force，bulk-archive 改为 change archive --all；new 与 artifacts 不再处理 --schema/--schemas。design 已整体重写。
- 2026-10-07 整体 review 后用户确认：删除 pending（修订请求文件 + plans show/approve --plan）；采纳 A1 受保护步骤、A2 Plan 版本 1 与直接激活、A3 快照/草稿/确认记录存储、A4 plans validate 与 recompose、A5 V1/V2 能力版本（含 manual-v1 与 delivery-review）、删除 config.yaml 的 default_profile；采纳 B2 安全扩张并入普通修订（冻结节点 requires 只增不减，增加依赖的节点及下游重新执行，有效 FAIL 必须在重新执行范围内）、B3 统一事务、B4 on_fail 单条按 Gate 统计的连带清理；不采纳 B1，保障仍为 change-assurance 流程节点；tracks 保留；变更保持 plan-replacement 名称并包含全部简化项。design 与 proposal 已整体重写（D1–D14）。
- 2026-10-07 用户确认：approval 段合并为 meta.approved_at（摘要即 meta.digest）；每份 Plan 保留人可读的 state.md；plans archive 执行前必须先取得人的明确同意。
- 2026-10-07 design（round 2 精简）：on_fail 与原 Schema 一致，放在节点的 gate.on_fail 内（reset、max_retries），每个 Gate 最多一条；删除 spec 顶层 on_fail 列表；引用节点与 flow 条目上声明的 on_fail 编译时下放到范围内的 Gate，重叠时报 on_fail_conflict；不再有由内向外的处理链与引用节点共享次数，返工次数按 Gate 统计；需同步修订 dynamic-workflow-composition D1.2 及相关实现与测试。
- 2026-10-07 design（round 2 精简）：删除逐实例的 reasons（spec 与 Plan 请求都不再包含或要求），Plan 级原因只记录在 meta.reason（plans create --reason）与 pending.reason；D4 补充 flow 与 nodes 的区别，明确 CLI 执行只看 nodes 与 on_fail。
- 2026-10-07 design（round 2 精简）：删除 meta.approval.message 与 meta.history；同一 Plan 只保留当前修订（以前修订的内容与摘要都不保留，需要时查 Git 历史，重做记录仍在 .attempts/）；plans approve 去掉 --message；plans history 只列出各 Plan 的编号、状态、当前修订号、原因与归档信息。
- 2026-10-07 design（round 2 精简）：spec 只保留 based_on、flow、reasons、nodes、on_fail（原 recovery 改名）；删除 spec 中的 baseline、repository、engine_version、instances、project——基线与仓库只在 Change 级并在第一次 plans create 时固定，引擎能力只在编译时检查，引用成员树由 nodes 推导，项目约束执行时读取最新 config.yaml；删除 .revisions/，修订失效归档并入 .attempts/（kind: rollback | revision，重试计数只统计 rollback）。
- 2026-10-07 design（round 2 细化）：一份 Plan 只有一个 plans/<NNN>/plan.yaml（meta + spec + pending），不再保存 revisions/、drafts/、approvals/、manifest.yaml、resources/；执行时读取最新 Fragment 资源，不固化、不校验资源哈希；同一 Plan 内修订草稿写入 pending；meta.approval.digest 绑定 spec 摘要，加载时校验，不一致返回 plan_integrity；meta.status 只记录人的决定（draft/approved/archived/discarded），completed 由 status 实时推导不落盘。
- 2026-10-07 design（round 2）：任务层级 Change → Plan → Revision，组织层级 Node → Fragment → Profile → Plan（执行图 = 某个 Revision 的快照）；Change 级 .workflow.yaml v4（baseline、repository、active_plan、open_plan、next_plan）与 Plan 级 plans/<NNN>/state.yaml（draft/active/archived/discarded）+ state.md；Plan 目录自包含运行时，运行时根为 Plan 目录，Diff 与基线按 Change；plans archive 只改状态不移动文件；最多一个未结束 Plan；Change 级事务 + recover；format_version 3 不迁移。proposal 同步改写。
- 2026-10-07 approval round 1：changes requested。去掉完整替换模式；任务变化时 plans archive 归档活动 Plan 后按初次规划流程新建 Plan；状态分 Change 级（.workflow.yaml：固定基线、仓库、唯一活动 Plan 指针、下一个 Plan 编号）与 Plan 级（plans/<NNN>/state.yaml：draft/active/archived/discarded 等）；保留 Revision 层，任务层级为 Change → Plan → Revision，工作流组织层级为 Node → Fragment → Profile → Plan；design 需完整说明层级并给出 mermaid 时序图。详见 approval/changes-requested.md。
- 2026-10-07 design：RevisionContext.mode 区分 initial/revise/expand/replace，Plan 版本 3；validate_replacement 与 validate_frozen 并列；替换草稿使活动 Plan suspended；plans discard 写 .workflow/discards 记录；确认事务新增 copies 并归档旧 Plan 全部节点；返工记录按 history_boundary 分区；替换前用新 Plan 能力对当前 Diff 做覆盖检查。
- 2026-10-07 proposal：采用评估中的默认建议——reuse 只限产物节点，Gate 结论（普通 PASS 与代码证据）一律重跑；替换后重试计数从 0 开始，靠人工确认与“exhausted 只能 retire”防止清空预算；plans discard 同时可撤销普通修订草稿与替换草稿。

## Rejected Options
- 统一事务文件 .transaction.yaml 与 recover --inspect/--resume：改为中断后重新执行同一命令即可收敛。
- plans discard 与 discarded 状态：复用 plan archive。
- 独立的 assurance check 命令：保障节点通过 gate record 执行。
- 修订草稿 pending 段：改为修订请求文件 + plans show/approve --plan。
- 保障从流程节点改为完成条件（B1）：用户选择保留 change-assurance 节点。
- spec 顶层的编译后返工规则列表（id、owner、sources、targets）与由内向外逐层接手的处理链：改为 Gate 内单条 on_fail（round 2 精简）。
- 逐实例选择理由 reasons：意义不大，已删除（round 2 精简）。
- 确认说明 message 与修订历史 meta.history：没有实际用途，已删除（round 2 精简）。
- spec 中保存 baseline、repository、engine_version、instances、project 快照：冗余或可推导，已删除（round 2 精简）。
- 独立的 .revisions/ 目录：并入 .attempts/（round 2 精简）。
- Plan 内不可变快照目录（revisions/、drafts/、approvals/、manifest.yaml、resources/）与 plans/<NNN>/state.yaml：改为单个 plan.yaml（round 2 细化）。
- 固化 Fragment 资源字节或校验资源哈希：执行时直接读取最新 Fragment（round 2 细化）。
- completed 落盘：由 status 实时推导（round 2 细化）。
- 完整替换模式（plans create --replace、replaces 的 reuse/carry/retire、suspended、history_boundary、确认事务 copies、RevisionContext.mode 与 Plan 快照版本 3）：过于复杂，由“归档后重新规划”替代（approval round 1）。
- 按阶段滚动规划（只规划当前阶段、逐步追加）：初始 Plan 必须覆盖完整任务。
- 多个 Plan 同时执行：同一时间最多一个 active Plan。
- 为多 Plan 引入新的通用执行引擎或新的 Plan 身份字段：修订号与现有快照/事务已足够。
- 按文件存在隐式继承旧成果：同名节点会误继承完成状态，必须显式 reuse。

## Open Questions
- 已解决：artifacts-command 标注取代并保留；add-schema-sources 本变更不处理。
- 无（Plan 级 state.md 与 archive 前人工同意均已确认）。
- 无（第一轮）。carry 以新 flow 实例为目标并挂在其根节点；撤销的草稿快照原地保留并写 .workflow/discards/<draft-id>.yaml；无保障规则时跳过覆盖检查（均已在 design 确定）。

## Artifact Notes
- apply/report.md（更新）：补充第 9 组实施与测试结果；tasks 49/49。
- test-plan.md 中 I1–I6 的预期由“返回 interrupted 并重新执行”改为“状态等于之前或之后、后续命令补完”，对应测试见 tests/test_workflow_recovery.py。
- apply/report.md：实施报告（任务、文件、真实测试输出与过程中的失败、与 design 的偏离、后续事项）。
- tasks.md：44/44 已勾选。
- 文档：docs/{en,zh} 重写为 README、overview、workflow-composition、plan-reference（新增）、configuration、cli-reference、agent-protocol、release-notes（新增）；删除 schema-reference 与 workflows/secure-spec-driven；文档契约测试改为按新模型、示例真实编译与已删除命令检查。
- builtin/skills：new、continue、archive、bulk-archive 改用新命令树（英文）。
- test-plan.md：任务 1.1 的测试计划（现有测试处理方式、9 类用例约 70 条、验收标准），等待用户确认。
- approval/approved.md：round 2 approved。
- security/pass.md（最终版重审）：无阻塞问题；残余风险 5 条（实时资源与配置、本地完整性边界、人工同意由 Skill 约束、最低保障依赖 required_fragments、不兼容发布的迁移提示）。
- specs/（旧流程删除后重写）：change-plan-lifecycle 8 条；修改 workflow-plan-approval、workflow-planning、workflow-recovery-assurance、workflow-fragments、loopspec-cli、lpsx-skills；REMOVED status-report（12）、artifact-discovery（10）、usage-docs（2）。
- tasks.md（重写）：8 组 43 项，含删除旧 Schema 流程（第 6 组）与 2.0.0 发布说明。
- design.md D12：改为完整的 CLI 命令与 Skill 一览（工作区、Change、Plan 生命周期、执行、证据与保障、恢复与归档、目录与模板、旧 Schema 兼容、删除项；4 个 Skill 的用途、步骤与变化）；核对发现 history 与 artifacts 目前只支持旧 Schema，标为新增支持并补充 tasks 4.8。
- security/pass.md（round 2）：无阻塞问题；残余风险 4 条（实时资源与配置立即生效、本地完整性边界、人工同意由 Skill 约束、删除受保护步骤后最低保障依赖 required_fragments）。
- specs/（round 2）：新增 change-plan-lifecycle（9 条）；修改 workflow-plan-approval（REMOVED 草稿为独立不可变快照、安全扩张批准前无返工副作用）、workflow-planning（REMOVED 模板引擎能力版本可验证）、workflow-recovery-assurance（REMOVED 嵌套失败按最近处理者唯一恢复）、workflow-fragments、loopspec-cli、lpsx-skills。
- tasks.md（round 2）：7 组 33 项，安全相关标注【安全】，1.1 先确认测试计划，6.4 同步修订关联变更。
- design.md（整体重写）：D1 层级、D2 目录、D3 Change 状态、D4 plan.yaml 与完整示例、D5 修订、D6 不变量、D7 运行时根、D8 统一事务、D9 六个时序、D10 历史与预算、D11 简化与移除清单、D12 CLI、D13 兼容、D14 安全边界；7 张 mermaid 图已渲染校验。
- proposal.md（重写）：能力改为 change-plan-lifecycle，修改 workflow-plan-approval、workflow-planning、workflow-recovery-assurance、workflow-fragments、loopspec-cli、lpsx-skills。
- design.md D4：新增完整 plan.yaml 示例（AFD1111，Plan 002 采用 bugfix，nodes 与 on_fail 取自编译器实际输出，已用严格 YAML 解析校验）及 pending 段示例。
- design.md（round 2 细化）：按单个 plan.yaml 重写 D1–D11 与全部时序图，7 张 mermaid 图已用 mermaid-cli 渲染校验。
- proposal.md：同步为 plan.yaml 单文件结构。
- design.md（round 2）：D1 两套层级与衔接点、D2 目录、D3 Change 级状态、D4 Plan 级状态与状态图、D5 不变量、D6 运行时根、D7 六个时序（初次规划、执行返工、Plan 内修订、归档重新规划、放弃草稿、中断恢复，含 mermaid 且已用 mermaid-cli 渲染校验）、D8 历史与预算、D9 CLI、D10 兼容、D11 安全边界。
- proposal.md（round 2 改写）：新增 change-plan-lifecycle，替代原 plan-replacement 能力。
- approval/changes-requested.md：round 1，changes requested。
- security/pass.md：无阻塞问题；非阻塞注意事项 4 条（复制使用安全读写与大小上限、事务条目上限先校验、discard 需人同意、继承失败报告标注不可信）。
- specs/：新增 plan-replacement（6 条需求）；workflow-plan-approval、workflow-planning、loopspec-cli、lpsx-skills 以 ADDED 补充；workflow-recovery-assurance MODIFIED“恢复边不破坏执行 DAG”“修订与安全扩张”。
- tasks.md：7 组 25 项，安全相关任务标注【安全】；1.1 要求先确认测试计划。
- design.md：D1 mode 与版本、D2 替换请求与校验、D3 暂停、D4 撤销、D5 切换事务、D6 历史边界与预算、D7 CLI/Skill、D8 安全边界。
- proposal.md：新增 plan-replacement；修改 workflow-plan-approval、workflow-planning、workflow-recovery-assurance、loopspec-cli、lpsx-skills。
