# Change State

## Current Focus
- Security review passed after the resource-binding correction; present the exact plan for human approval.
- 按人工审批第 1 轮反馈重新编写规格与设计，并将当前活动材料统一为中文表达。
- 按人工审批第 2 轮反馈重新设计 `Node`、`Fragment`、`Profile`、`Plan` 四层模型以及 QA 返工与 Diff-Gate 保障闭环。
- 当前有效设计见下文“当前有效设计”；已补齐新版五份规格与任务，进入安全复审。前述关注项保留为历史记录。

## Frozen Decisions
- The LLM proposes workflow shape; LoopSpec validates, records, and executes it deterministically.
- Existing complete schemas and existing changes remain supported.
- Node progress remains derived from artifacts; a plan record is configuration, not a progress database.
- Protected-gate omission requires a human decision bound to the exact plan digest.
- In-flight recomposition may change only pending future work and must preserve prior plan revisions.

## Decision Log
- 2026-10-05: Deliver static composition and in-flight recomposition in one change, with staged implementation tasks.
- 2026-10-05: Use declarative fragments only; fragments cannot execute code or override validation rules.
- 2026-10-05: Fragments reference nodes from validated schemas; effective plans copy and namespace required resources.
- 2026-10-05: Composition requests are workflow-home-relative YAML, and approval is a second pass bound to the validator-produced digest.
- 2026-10-05: Recomposition uses immutable numbered plan revisions and freezes executed/history-bearing nodes plus the current cursor.
- 2026-10-05: Profiles never preserve or replay human approval records.
- 2026-10-05: Security review rejected digesting only schema/metadata because copied instruction and template bytes were not approval-bound.
- 2026-10-05: The compiler will read each selected source once into a resolved bundle; digest, approval validation, and materialization all consume the same buffered bytes.
- 2026-10-05: Security review round 2 passed; the prior resource-substitution issue is covered by design, specification, tasks, and negative tests.
- 2026-10-05：人工审批第 1 轮要求修改；`dynamic-workflow-composition` 的当前活动材料须统一使用中文表达，技术标识保持原样；判定见 `approval/changes-requested.md`。
- 2026-10-05：人工审批第 2 轮要求修改；新设计须收敛为 `Node`、`Fragment`、`Profile`、`Plan`，由 Profile 承载 Fragment 级流程和失败路由，由最终保障 Fragment 校验全部 Diff 的 Gate 证据；判定见 `approval/changes-requested.md`。
- 2026-10-05：第 2 轮重设计采用允许 nodes/includes 混合定义的 Fragment、实例级依赖 DAG 和独立 PR Review 实例；覆盖此前“只允许线性且两种形态互斥”的草案。
- 2026-10-05：第 2 轮重设计增加 gate begin/record 两步证据、项目最低保障约束、精确控制目录与可恢复修订；“冻结节点绝不改变”的旧限制仅适用普通重组，安全扩张需显式失效受影响 QA/Assurance。
- 2026-10-05：重新设计的安全复审通过，结论见 security/pass.md；材料结构校验通过，五份规格含 32 条需求、51 个场景，任务清单含 53 项。当前等待重新设计方案的人工决定。

## Rejected Options
- Retiring complete schemas and forcing a one-time migration; compatibility is lower risk and keeps presets useful.
- Re-running LLM composition during every status call; each plan revision is compiled and frozen instead.
- Copying AI-DLC's explicit progress database, hook system, and numeric risk thresholds.
- 人工审批第 1 轮否决继续以英文作为 `dynamic-workflow-composition` 当前活动材料的主要叙述语言。
- 人工审批第 2 轮否决让 `Schema` 继续作为新架构核心概念、Fragment 黑盒 `interface`、Profile Node-level 通用 `links`，以及仅依赖 QA 分类保证审查覆盖的方案。

## Open Questions
- None.

## Artifact Notes
- Proposal introduces workflow-fragment-catalog, workflow-composition, workflow-recomposition, loopspec-cli, and lpsx-skills specifications.
- design.md defines fragment manifests, request/approval shapes, self-contained plan snapshots, CLI integration, recomposition freezing, and profile semantics.
- Five capability specs define catalog, composition, recomposition/profile, CLI, and skill behavior with safety and compatibility scenarios.
- tasks.md stages implementation into domain/catalog, version 1 composition, version 2 recomposition/profiles, CLI, docs, and verification.
- Security revision adds bounded single-read resource buffering, resource hashes in the plan digest, and same-buffer materialization tasks.
- `security/pass.md` records the successful retry review and the implementation-time checks that remain mandatory.
- `approval/changes-requested.md`：人工审批第 1 轮要求修改，需将当前活动材料统一改为中文表达。
- `proposal.md` 与 `design.md` 已按人工审批第 1 轮要求改为中文叙述，功能范围与安全决策保持不变。
- 五份能力规格已按人工审批第 1 轮要求改为中文叙述；`Requirement`、`Scenario`、`WHEN`、`THEN`、`SHALL` 与 `MUST` 等协议关键字保持原样。
- `tasks.md` 已用中文重建，仍保留 39 项可追踪任务以及第一版本、第二版本的实现顺序。
- `security/pass.md` 已用中文重建；重新审查确认语言转换没有改变已通过的安全设计。
- `approval/changes-requested.md`：人工审批第 2 轮要求围绕四层模型、Fragment 级返工和提交前 Diff-Gate 保障闭环重新设计。
- `proposal.md` 与 `design.md` 已按人工审批第 2 轮重写：新架构仅暴露四个领域概念，第一版本交付自适应 Plan，第二版本交付 QA 返工、Gate 证据和全量 Diff Assurance。
- 已生成 workflow-fragments、workflow-planning、workflow-recovery-assurance、loopspec-cli 和 lpsx-skills 五份新版规格；tasks.md 为两版本的实现与验证清单。
- security/pass.md 为当前重新设计后的通过结论；此结论只覆盖设计，不代表 V1/V2 代码已经实现或通过测试。

## 当前有效设计

本节为人工审批第 2 轮重新设计后的有效说明。此前英文决策和材料说明保留作历史，不再作为当前架构定义；包括“Fragment 从 Schema 引用节点”等已被本轮方案替代的决策。

- 对外只使用 Node、Fragment、Profile、Plan；旧 Schema 通过内部兼容适配器读取。
- Fragment 文件允许 nodes 与 includes 共存，实例依赖表达组合，Node 不单独存盘。
- Profile 的 flow 定义实例 DAG，recovery 定义有限失败分类和上游返工目标；无需 interface 或通用 links。
- 同一个定义的多次引用生成独立实例、产物和证据，FE/BE 的 PR Review 不混用。
- Plan 固化展开图、归属、恢复规则、基线和资源；执行状态继续由文件系统推导。
- QA 失败重跑相应 Implementation Fragment 全部成员及下游，独立并行分支保留。
- Gate begin 冻结待审输入，record 确认输入一致后记录 PASS；最终 Assurance 验证所有实际 Diff 的有效覆盖。
- 项目最低保护不随更换 Profile 消失；未知路径、过期证据和计划外审查要求默认阻塞。
- 普通重组只改未来工作；安全扩张显式增加流程并重置受影响 QA/Assurance，新计划不自动继承旧代码 Gate PASS。
- V1 交付自适应 Plan；V2 交付返工、证据、Assurance 和修订事务；外部直接提交不在本地流程的强制边界内。

## 评审材料收口

- 2026-10-05：已完整读取当前审批节点所列提案、设计、五份规格、任务清单和安全结论；新增 `review.md` 中文评审摘要，统一提案中的失败分类字段为 `route_case`。
- 当前关注：新版设计材料已经收口，等待人工明确选择按新版方案实施或先调整；审批节点保持 ready，不代写审批结果，53 项实现任务仍未完成。
- 材料说明：`review.md` 为人工评审辅助材料，不是审批判定；此前关注项和决策保留为历史记录。

## 第 3 轮人工修改决定

- Decision Log：用户要求修改方案文档，Fragment 统一 nodes 编排，引用项 use 指向其他 Fragment；引用节点支持 on_fail，结果从内部 Gate 汇总，内部恢复优先、失败可向外传播。人工判定见 `approval/changes-requested.md`。
- Rejected Options：nodes/includes 分开编排，以及依靠额外 Fragment 接口或 Agent 自报判断引用节点成败。
- Open Questions：无新增需人工决定的开放问题。
- Current Focus：按第 3 轮反馈重做设计、规格与任务并复审安全；当前请求只授权文档修改，不进入 V1/V2 实现。
- Artifact Notes：`approval/changes-requested.md` 记录第 3 轮要求修改；此前“当前有效设计”和评审收口段落保留为历史，本轮新的有效设计将在后文追加。

## 最新有效设计：统一 nodes 与引用结果

本节取代前述 nodes/includes 分离编排说明；既往决策、统计和评审结论保留为历史。人工反馈编号为第 3 轮，LoopSpec 本次归档目录编号为 round-004，包含之前的安全回滚记录。

- Fragment 仅有统一 nodes 列表；Node 可以直接定义执行内容或通过 use 引用 Fragment，两种形式互斥且共用 id/requires。执行时运行 Plan 编译展开的叶子，不重新读取来源定义。
- 引用节点保留身份、成员树与汇总状态；全部成员及必要证据有效才 done，有未处理有效 FAIL 才 failed，未完成不是失败，系统错误阻塞。引用节点不另产生成败文件或 Gate 证据。
- 直接 Gate 与引用 Node 均在 Node 顶层声明 on_fail；reset 指向本 Fragment 的上游直接/引用节点。Fragment 不另设顶层 recovery，Profile 保留有限分类的跨 Fragment recovery。
- 内部最近处理者优先，无规则或局部预算耗尽时向外传播，最后考虑 Profile；一次失败只处理一次。父级重置和重命名修订不能清零历史预算，所有允许层级耗尽时停止自动返工。
- 返工重置目标、失败来源、选中引用边界全部成员及下游的产物/证据，不回退业务代码。来源 Fragment 不因引用场景的 on_fail 绑定而改变。
- Plan 固化叶子 DAG、成员树、处理链、限额及全部资源字节；原四层模型、QA/Diff 保障、项目最低约束、事务与旧格式兼容决策保持有效。
- V1 交付统一 nodes、引用基本状态及直接 Gate 局部恢复；V2 交付引用 on_fail 的嵌套传播、分类恢复和系统保障。V1 对未支持能力明确拒绝。
- Artifact Notes：提案、设计、五份规格、任务与 review.md 已同步；规格共 34 条需求、63 个场景，任务保持 53 项未完成，七段 YAML 示例及三份 Fragment 局部结构检查通过。
- Decision Log：统一 nodes 和嵌套恢复的设计级安全复审通过，当前结论为 security/pass.md；此前设计与判定可在 .attempts/round-004 恢复。
- Current Focus：文档调整已完成，代码未修改；人工实施审批保持待决定，本次不代写审批 PASS，也不执行实现任务。

## 人工审批第 4 轮：批准实施

- Decision Log：用户明确批准当前统一 nodes 的四层模型与 V1/V2 实施计划，人工原话见 approval/approved.md。
- Frozen Decisions：Fragment 单一 nodes 列表；直接定义与 use 引用互斥；引用由内部有效结果汇总；最近内部恢复优先且预算不因父级重置清零；同容器 ID 唯一，产物按需求与所属 Fragment 实例隔离。
- Frozen Decisions：Plan 自包含不可变修订、精确资源字节摘要与固定 Git 基线；Gate begin/record、全量 Diff Assurance、受限恢复/修订和项目最低约束；旧 Schema/Change 继续兼容。
- Artifact Notes：approval/approved.md 为当前人工通过记录；此前“仅修改文档”和“等待决定”保留为历史，已被本轮批准替代。
- Current Focus：先实现 V1 编译与快照/CLI，再实现 V2 恢复、证据、保障和修订，执行专项与完整回归；保留用户 AI-DLC 安装和无关修改。

## 实施进展与内置 Skill 澄清

- Decision Log：用户要求内置 Skill 使用英文，源文件只修改 builtin/skills，不更新 .codex/skills。该要求覆盖此前材料语言说明中的 Skill 部分；需求、设计、规格和实施报告仍使用中文。
- Artifact Notes：四个内置 Skill 源已更新；投影测试在临时目录完成，保留真实本地/全局安装内容以及用户已有的 .gitignore、AI-DLC 文件和 add-schema-sources 需求。
- Artifact Notes：V1 编译、实例隔离、自包含快照与 CLI，以及 V2 嵌套恢复、代码证据、Diff Assurance 和可恢复修订已实现。任务 1—8 与 9.1—9.4 共 51 项已完成，最新源代码的全量回归和最终复审尚在收尾。
- Decision Log：最终检查补齐冻结处理链禁止插入新处理者、代码 Gate 必须先于 Assurance、完整非活动修订快照的保留重试，以及返工指令中的校验失败报告路径和必重跑 Gate。
- Current Focus：完成最终测试与安全检查后写 apply/report.md；不提交业务代码，不自行归档需求。

## V1/V2 实施完成

- Artifact Notes：tasks.md 的 53 项任务全部完成；apply/report.md 记录实现文件、实际测试输出及失败处理，apply/security-audit.md 记录实施代码复审和边界。
- Decision Log：最终完整回归为 936 passed in 302.53s；文档/英文 Skill/隔离投影专项最终为 87 passed in 1.52s；ruff 通过，mypy 在 45 个源码文件中未发现问题。
- Decision Log：make test 首次遇到 uv 沙箱系统配置 panic，后续实际测试曾因 NO_COLOR 导致颜色测试失败；通过仅隔离测试子进程环境的等价 pytest 重跑验证，不改动产品颜色逻辑。全部失败与真实处理写入报告。
- Frozen Decisions：内置 Skill 的源码为 builtin/skills 且使用英文；需求与方案材料使用中文；不刷新真实本地/全局安装目录，不改动用户已有 AI-DLC、.gitignore 和其他需求。
- Current Focus：实施完成，准备交付；没有执行仓库提交、全局安装、发布或需求归档。实际项目启用代码 Profile 前仍需维护者核对路径映射，外部提交需独立 CI/权限保障。

## 被 plan-replacement 取代

- Decision Log：2.0.0 的 `plan-replacement` 变更删除旧 Schema 流程并重做持久化、确认、修订与命令树；本需求 design.md 与 specs 顶部已标注被取代的决策与需求，以 plan-replacement 为准。实现代码已按新设计替换。
