> **已被 `plan-replacement` 取代（2.0.0）。** 下列内容以 `loopspec/changes/plan-replacement/design.md` 为准：
> - 草稿不可变快照目录、确认记录目录、`PlanMetadata`/`DraftBinding`/`ConfirmationRecord` 与 Change 格式 3 → 每份 Plan 一个 `plan.yaml`，`meta.status` 为 `draft`/`approved`/`archived`，确认只写 `meta.digest` 与 `meta.approved_at`；Change 级 `.workflow.yaml` 格式 4（D3、D4）。
> - `plans create/show/approve/recompose`、`--expected-digest`、`--message`、`--safety-expansion` → `plan create/show/approve`（`--digest`），修订用 `plan validate -f` 预览、`plan approve -f --digest` 确认（D5、D12）。
> - 确认事务与 `recover --inspect/--resume` → 固定写入顺序、最后一步为生效点，重新执行同一命令收敛（D8）。
> - 一个 Change 只有一份 Plan → 一个 Change 可有多份 Plan、同一时间最多一份未结束；任务变化时经人同意 `plan archive` 后重新规划（D3、D9）。

## 背景

用户将 Plan 定位为 LLM 针对单个任务构建、与人确认后定稿的执行图。当前实现却在 new 中创建并激活 Plan，且 --approval 只处理受保护模板偏离。这不是目标生命周期，需要拆开 Change 创建、草稿保存和明确确认。

当前代码支持自包含 Plan 快照、摘要、原子活动指针和可恢复修订。沿用这些基础，不引入新的领域概念、进度数据库、外部审批服务或身份系统。

## 目标与非目标

### 目标

- new 先创建 Change，不要求在此时已有 Plan、已选模板或已有审批文件。
- plans create 针对已存在 Change 编译、校验并保存草稿；LLM 再展示草稿与人沟通。
- plans approve 在真实确认后定稿；任何新 Plan，包括直接采用 Profile 和 manual-v1，都不能省略确认阶段。
- 草稿编辑、确认、执行和后续修订有明确边界；所有源码、指令和规则快照与人确认的摘要一致。
- 保留项目最低保障、必要 Gate、恢复预算、代码证据、最终 Assurance 和旧 Change 的既有执行行为。

### 非目标

- 不让 CLI 自动推断任务图，不以 Profile 固定所有任务的流程。
- 不认证审批人身份、不提供签名或服务端授权；本地 approve 命令不能证明调用者确实是人。
- Plan 确认不替代业务设计审批 Node、代码 Gate、QA 或全量 Diff Assurance。
- 不提交业务代码、发布、归档需求或刷新本地/全局 Skill 安装目录。

## 设计决策

### 1. 命令分工

```bash
loopspec new AFD1111 --json
loopspec fragments list --json
loopspec profiles list --json
loopspec profiles show frontend-small-change --json
loopspec plans create AFD1111 --plan changes/AFD1111/.workflow/requests/plan.yaml --json
loopspec plans show AFD1111 --json
# LLM 展示草稿并取得本轮人工确认后，才运行下一条命令。
loopspec plans approve AFD1111 --expected-digest "<planDigest>" --json
loopspec next AFD1111 --json
```

- new：默认新模型只建立目录、state.md 与最小生命周期元数据。删除 new 的 --plan、--profile、--approval、--expected-digest。显式 --schema 保留旧 Schema 新建入口。
- 旧 --schema 只用于明确选择旧流程的新建或已有旧 Change，不能把同一新格式 Change 的未规划/草稿/活动元数据重绑成旧格式。Skill 不得用切换模式、改名或另建同一任务副本逃避本轮计划确认。
- plans create：--plan 指定 workflow-home 相对请求路径；--profile 可直接选完整模板，二者互斥。创建时完成与当前 plans validate 同等的图、路径、资源、版本、项目保障校验，结果始终是草稿。
- plans approve：只确认已经保存的草稿，不在确认时从 Profile/Fragment 重新生成图。--expected-digest 是可选的并发保护；Skill 必须传它，确保确认的正是之前展示的版本。--message 可选，用于保存真实人工原话，不重新引入审批文件。
- plans show：默认展示当前草稿；没有草稿才展示活动 Plan。新增 --active 明确读取已批准的活动计划，响应包含 planStatus、planDigest、草稿身份及修订上下文。
- plans validate：保留为无写入诊断，不是创建或批准；新计划的 requiresApproval 恒为 true，不能因没有模板偏离返回已可执行。
- plans recompose：不再作为无需本轮确认的激活入口；保留名称时转为修订草稿创建的兼容别名，明确返回 draft 而不是 approved。推荐流程统一为 plans create → plans approve。

CLI 拼写是 fragments；不增加 fragements 错拼别名。

### 2. 生命周期与进度的区别

| 阶段 | 状态来源 | 可做的操作 |
| --- | --- | --- |
| 尚无 Plan | Change 元数据没有草稿/活动绑定 | 发现目录、创建草稿、读取规划指引 |
| 草稿待确认 | 有完整草稿绑定，没有首次活动绑定 | 查看、讨论、重新创建草稿、明确批准 |
| Plan 已批准 | 有经确认激活的活动绑定 | 按活动图执行与检查 Gate，读取任务进度 |

planStatus 是配置的规划/确认阶段，不是 Node 的执行状态。Node 仍保持 done/ready/blocked/failed/exhausted，继续由产物与有效证据推导；不存放新的完成状态表。

首次 Plan 获批前，status/next 返回 isComplete: false、空执行叶子与规划阶段指引。不得给出可以绕过沟通的自动 approve 下一步；建议先展示草稿及等待人工确认。instructions、gate begin/record、assurance check、rollback 和完成归档返回 plan_not_approved，不加载草稿执行。

后续已有活动 Plan 时，新草稿不会覆盖或暂停已批准活动图。执行器只能运行原活动图，不能运行草稿；status 同时明确 pending draft。Skill 发起草稿后应等待本轮确认，不擅自进行新计划工作。此设计避免尚未批准的提案影响既有执行权限，并要求批准时重新检查冻结边界。

### 3. 不可变草稿与活动修订

- 草稿与活动修订分开：草稿在 .workflow/drafts/<draft-id>/，批准后活动修订在 .workflow/plans/001/。草稿 ID 独立于活动修订号，不能因为多次讨论占用或跳过修订号。
- 每次 plans create 都保存新的不可变草稿，完成暂存/清单/资源复核后原子切换当前草稿绑定。旧草稿保留，不覆盖历史，也不影响 Gate/Attempts。
- 草稿保存规范化请求、叶子 DAG、引用树、资源字节和哈希、项目约束、固定基线、基础活动摘要、修订模式与失效影响。单一 planDigest 绑定所有这些有效输入；确认记录的时间/原话不参与形成循环摘要。
- new 不捕获代码基线；plans create 在确实选择代码 Gate 时捕获固定 Commit，并把它写入草稿。后续 approve 不能随 HEAD 变化静默换基线。
- approve 只消费草稿缓存字节，来源 Fragment/Profile 后续变化或删除不替换已展示内容。
- 最小 Change 元数据采用新版本，允许草稿/活动引用为空。解析器明确区分旧 Schema、既有活动 Plan、新待规划 Change；未知格式与损坏新格式不能降级到旧引擎。
- new 必须在公开新目录前完整建立最小元数据，或用初始化标识阻止未完成创建被解释成旧流程。有新格式初始化痕迹但元数据缺失的残留目录，也必须报错而不是回退 Schema；不能让并发读取获得旧模式执行权限。

### 4. 批准与并发

批准持逐 Change 写锁，按以下顺序处理：

1. 安全读取生命周期元数据、当前草稿、清单和资源，复核完整性及 expected digest。
2. 检查草稿仍基于当前活动版本与摘要，复核冻结节点、引用边界、恢复处理链及历史预算。
3. 复核项目政策配置及政策规则摘要，与草稿固化输入不同则拒绝并要求新草稿；不得用人工确认绕过项目最低保障。普通选用 Fragment/Profile/指令仍读取草稿快照，不重新编译。
4. 将缓存资源安全落入下一活动修订，验证摘要；写入本地确认记录，原子激活该修订并清除当前草稿绑定。
5. 第二次对同一已批准草稿调用 approve 返回该已批准结果，不重复激活修订、不重置状态或预算；从来没有草稿则返回明确错误。

确认记录包含草稿身份、planDigest、活动修订、时间与可选 message。它记录调用者的明确确认操作，不声称验证了身份。Skill 必须先获得真实人工确认，不把“请实现这个需求”推断成“已确认稍后生成的 Plan”。

message 是有界的可选说明，作为普通数据处理，不执行、不插入 Shell，不索取或自动推断姓名/凭据；不应写入秘密或敏感个人信息。省略 message 不取消明确 approve 的确认动作。

expected digest 不匹配、草稿基准过期、资源损坏、并发写入或未恢复事务均不改变活动绑定，且只返回结构化错误，不回显原始配置或业务代码。

### 5. 修订与安全扩张

- 活动 Plan 的后续计划调整通过 plans create 建草稿，请求显式带 base_revision；必须沿用原固定基线和基础摘要。
- 当前/已完成/失败/有 Attempts 的叶子、引用成员树、资源与候选恢复链保持既有冻结约束，不能通过新草稿重命名洗掉预算。
- 安全扩张使用 plans create --safety-expansion；仍只能添加当前 Assurance 诊断建议的完整修复 Fragment，让原 QA 依赖全部新增修复成员。草稿展示新增工作与 invalidatedNodes，摘要绑定该失效影响。
- 创建草稿不归档产物或使原 QA/PASS 失效；批准时重新复核当前诊断/冻结条件，再把失效归档与活动绑定变化放入同一可恢复事务。
- 代码 Gate PASS 默认不跨新 Plan 摘要继承；批准新修订后重新执行所需审查、QA 和最终保障。
- 事务恢复只完成此前明确批准且已记录的激活事务；不得将无确认记录的草稿通过 recover 自动批准。

### 6. 取代模板偏离审批

删除对外的 Profile.protected、Plan 请求 deviations 与审批文件流程；Profile 提供 flow、recovery 和 guidance，选择理由仍在 reasons。所有 Plan 都经统一人工确认，模板调整不再被误当成权限特例。

旧输入/快照中曾存在的保护和偏离字段，由兼容读取路径保留其摘要语义；新命令不再把这些字段作为可选审批开关。兼容行为须明确给出迁移指引，不静默解除项目 required_fragments、assurance_rules 或冻结约束。

### 7. Skill 与文档

只更新 builtin/skills 英文源。loopspec-new 顺序固定为：new → fragments/profiles 发现 → 构建任务请求 → plans create → plans show → 与人确认 → plans approve（精确摘要）→ status/next。

loopspec-continue 遇到无 Plan 或待确认草稿时进入规划/沟通，不把 status 的阶段指引当作批准权限；修订与安全扩张也先确认草稿。Archive Skill 不把未规划或未批准的首次 Change 当成完成。

docs/en 及其示例文字使用英文，docs/zh 使用中文。双语命令、字段、错误和执行结构保持一致；中文语言导航标签是英文文档的唯一允许中文例外。

## 风险与权衡

- [默认 new 行为变化] → 明确标记 BREAKING，保留显式 --schema 与既有 Change 的执行兼容；更新旧生命周期测试和迁移说明，不悄悄创建旧流程。
- [借旧入口降级逃避确认] → 同一新格式 Change 不能被 --schema 重绑，Skill 保持任务规范名称且不能复制任务或切模式跳过确认。
- [确认后批准了别的草稿] → Skill 必须传展示草稿的 expected digest，写锁内复核当前绑定。
- [人确认的资源被换成当前来源] → 草稿自包含，批准不重新解析选用的 Fragment/Profile/指令。
- [项目政策确认期间变更] → 单独复核项目政策和规则摘要；不一致要求重建草稿，不增加运行中政策迁移功能。
- [草稿保存或激活中断] → 复用安全暂存、清单、锁、排他创建与可恢复事务；不产生部分可执行计划，不回退业务代码。
- [人工确认被自动执行或伪造] → 导航不自动推进 approve，Skill 停止等待实际回答；承认本地同权限攻击者不在认证边界内。
- [新修订绕过 Gate 或预算] → 批准重新校验原冻结条件、历史和安全扩张闭包；归档与激活事务不清零预算。

## 迁移与回退

先完成领域/元数据和草稿存储，再接入新建、确认与运行时，最后统一修订、Skill 与文档。旧 Schema 元数据及旧活动 Plan 不自动重写；旧活动 Plan 视为既有生效配置继续执行，而新的修订必须走本轮确认。

旧自动化调用 new --plan/--profile/--approval 必须改为 new、plans create、人工确认、plans approve。旧 recompose 调用必须识别其现在仅创建草稿的结果。回退旧可执行文件前需检查新元数据兼容性，不允许不认识新版本的工具绕过确认执行草稿。

## 待人工确认

暂无无法从用户方向推导的开放问题；上述生命周期、显式旧 --schema 兼容和修订同样确认的选择，随本变更方案一并呈现给人类。当前未修改 CLI 源码或代写批准结果。
