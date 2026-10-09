## 背景与目标

本设计解决两个实际问题：固定的大需求模板无法适配前端小需求、局部 Bugfix 等场景；QA 发现问题后的修复必须重新经过相应实现流程内的关键 Gate，并在交付边界确认全部实际代码改动都有有效审查证据。

对外只保留四个概念：

| 概念 | 定义与职责 |
|---|---|
| Node | 最小执行单位，定义产物、指令、依赖或 Gate；只在 Fragment 内定义 |
| Fragment | 最小文件配置、复用与返工边界，可以定义一个或多个 Node，并组合其他 Fragment |
| Profile | 推荐的 Fragment 工作流模板，包含正常依赖、失败路由和保障约束，供 LLM 直接采用或参考 |
| Plan | 单个需求经校验后固化的完整执行图，包含展开的 Node、Fragment 归属、恢复规则和资源快照 |

LLM 负责理解场景、选择及解释调整；LoopSpec 负责校验与执行。新设计的 Plan 不依赖来源文件继续存在。旧 Schema 作为内部兼容输入，旧 Change 的行为保持可用。

**目标：**自适应流程、可复用定义、QA 返工闭环、当前 Diff 的证据覆盖、可审计的修订和安全输入处理。

**非目标：**任意脚本或 Hook、独立 Node 配置文件、Fragment 黑盒接口、通用条件执行 DSL、自动证明审查质量或审查者身份，以及控制所有外部 Git 提交。

## D1：Fragment 允许同时定义 Node 与组合其他 Fragment

文件路径为 `<home>/fragments/<name>.yaml`。必须至少有一个 Node 或一个被组合的 Fragment；允许二者同时存在，符合“一个节点或多个节点组合”的用途。依赖采用局部名称，名称在同一容器内唯一。以下示例采用新的 Node 格式，旧 Schema 通过适配器映射：

```yaml
version: 1
name: prd-generation
description: 编写 PRD 并检查需求质量
nodes:
  - id: write
    generates: prd.md
    instruction: instructions/prd-write.md
  - id: qa
    requires: [write]
    instruction: instructions/prd-qa.md
    gate:
      outputs:
        pass: qa/pass.md
        fail: qa/fail.md
      on_fail:
        reset: [write]
        max_retries: 3
```

Node 的 `requires` 引用本容器的 Node，或本容器的子 Fragment 实例；引用子 Fragment 表示依赖其全部终端 Node。局部 Gate `reset` 使用相同引用规则，但目标必须是该 Gate 的祖先。编译器校验引用、依赖环、产物冲突、模板和任务跟踪关系。

组合 Fragment 通过 `includes` 声明实例及它们的依赖：

```yaml
version: 1
name: be-implementation
description: 后端实现、测试、安全审查与代码审查
includes:
  - id: code
    use: backend-code
  - id: tests
    use: backend-tests
    requires: [code]
  - id: security
    use: security-review
    requires: [tests]
  - id: review
    use: pr-review
    requires: [security]
recovery:
  - from: security/check
    cases:
      revise: [code]
    max_retries: 3
  - from: review/check
    cases:
      revise: [code]
    max_retries: 3
```

列表位置只影响稳定展示，不代表执行依赖。这样既能串行，也能表达 FE/BE 并行，不必引入 `interface`、`entry/success/reset` 或另一套 Node-level `links`。Fragment 的根与终端由 Graph 推导。

引用配置是有向无环结构；编译设深度、展开数量和累计资源字节限制。Fragment 自引用或互相引用失败。

组合 Fragment 也可以声明同格式的 recovery，以便其中安全审查或 PR Review 失败时回到本 Fragment 的 code，并重跑 tests/security/review。Profile 负责 QA 等跨 Fragment 路由，内部 recovery 随 Fragment 一起复用并固化；不能在 Profile 中静默覆盖掉必要内部恢复规则。没有局部 reset 的 Gate 必须有唯一适用的容器 recovery，否则编译失败。

## D2：可复用定义生成独立实例

同一个 Fragment 可以在不同位置多次引用。每次出现都生成独立实例，不按 Fragment 名全局去重：

```text
fe/review/check    ← pr-review 定义的一个实例
be/review/check    ← pr-review 定义的另一个实例
```

实例路径是 Node 的规范身份。同一容器中重复 `id` 拒绝；不同实例内同名局部 Node 合法。递归引用环检查针对定义，执行归属针对实例，两者分开处理。

默认产物根为 `artifacts/<instance-path>/`，`generates` 和 Gate 输出相对于所属实例根解析。指令中通过运行时返回的依赖产物路径访问上游，模板资源也按实例/定义安全映射。请求不能覆盖任意仓库路径。产物通配符不得进入计划、证据或 Attempts 目录，模糊重叠归属保守拒绝。

重置 `be` 会重置其全部子实例及 Node，包括独立的 `be/security` 和 `be/review`；不把 `fe/review` 当成同一份 Gate 证据。

## D3：Profile 声明 Fragment 级依赖与有限失败路由

Profile 为 `profiles/<name>.yaml`，结构示例：

```yaml
version: 1
name: fullstack-feature
description: 前后端开发与 QA 闭环
flow:
  - id: proposal
    use: proposal
  - id: design
    use: technical-design
    requires: [proposal]
  - id: fe
    use: fe-implementation
    requires: [design]
  - id: be
    use: be-implementation
    requires: [design]
  - id: qa
    use: qa-testing
    requires: [fe, be]
  - id: assurance
    use: change-assurance
    requires: [qa]
recovery:
  - from: qa/test
    cases:
      frontend: [fe]
      backend: [be]
      fullstack: [fe, be]
    max_retries: 3
protected: [assurance]
guidance:
  - 仅前端小需求优先参考 frontend-small-change
```

`flow[*].requires` 表达 Fragment 实例级前置条件。编译为“上游终端 Node → 下游根 Node”的依赖边。Profile 可以覆盖真正的并行需求；无需只支持线性流程。

`recovery.from` 指明哪个具体 Gate 提供失败报告，因为一个 Fragment 可以有多个 Gate。这里直接使用稳定的实例内 Node 路径，没有额外接口字段。报告只提供 `route_case`，目标从 Plan 的 `cases` 解析。未知分类不路由并继续阻塞；路由目标必须是已存在且执行上位于失败 Gate 之前的 Fragment。

Profile 不包含进度、审批结果或执行代码。选择 Profile 会带入其模板；参考后调整的最终 `flow/recovery` 仍需写入完整 Plan 请求，LoopSpec 不从 LLM 的描述推断依赖。

## D4：Profile 是建议模板，项目约束保障必要 Gate

不能只用 Profile 的 `protected` 保证项目审查要求：换用更轻的 Profile 可能绕过原要求。现有 `config.yaml` 因此增加项目最低约束，包括指定的最终保障 Fragment 与保障规则资源；这些仍是配置字段，不是第五个领域概念。

Profile 可增加约束。最终 Plan 的约束是项目约束和 Profile 约束的并集，LLM 无权自动削弱。受保护偏离必须说明理由并取得内容摘要绑定的人工决定；本次代码保障流程中的“未知路径失败、证据摘要检查、最终保障依赖所有交付分支”不可通过省略理由关闭。

规则与必需 Gate 绑定写入 Plan 摘要。项目设置由维护者管理；LoopSpec 不声称能对拥有本地文件写权限的恶意操作者建立独立安全边界。内置 Profile 提供模板，项目需要初始化真实的 FE/BE 路径映射，不能假设每个仓库都叫 `frontend/` 或 `backend/`。

## D5：Plan 请求完整表达最终图，来源 Profile 可选

LLM 可以直接用 Profile，也可以参考一个 Profile 调整，或在项目约束下从 Fragment 自行建立 Plan。因此请求中的 `based_on` 可选；有值时保存来源 Profile 的内容摘要和偏离记录，没有值时仍执行项目约束。

```yaml
version: 1
based_on: frontend-small-change
flow:
  - id: fe
    use: fe-implementation
  - id: qa
    use: frontend-testing
    requires: [fe]
  - id: assurance
    use: change-assurance
    requires: [qa]
reasons:
  fe: 只需修复前端表单交互
  qa: 校验交互和回归
  assurance: 校验实际 Diff 的审查证据
recovery:
  - from: qa/test
    cases:
      frontend: [fe]
    max_retries: 3
```

请求路径必须相对于 Home、安全且受目录约束。全部模型拒绝未知字段、重复键和不安全名称；拒绝 YAML 任意对象构造。包括 Profile 偏离和审批在内的配置都有明确字节/条目限制。

文件打开时也需验证目录归属和文件身份，不能仅在先前 resolve 检查后再不受保护地打开路径；源路径或其父目录被并发替换时拒绝读取。暂存目录和元数据写入使用相同的目录身份保护。

编译器一次性读取并缓存所有所需定义与资源，展开完整 Graph、实例成员、恢复目标和保障规则；校验完整图后生成 `planDigest`。规范摘要覆盖有效模型、选择理由、资源目标/长度/哈希，以及代码 Plan 的固定基线。无关 YAML 格式、时间戳和审批本身不参与摘要。后续审批检查与落盘只使用同一个解析资源包。

校验提议时确定并返回基线，后续批准/创建必须使用该精确基线；否则 HEAD 变化会导致提议与实际创建不一致。

## D6：Plan 自包含、不可变且原子激活

目录为 `<change>/.workflow/plans/001/`，包含 `plan.yaml`、`manifest.yaml` 和全部所需指令/模板/规则。元数据记录 `plan_revision`、相对计划路径和摘要。目录、资源清单和哈希必须完整校验后才能激活。

通过逐变更写锁、基础修订版检查、排他创建和原子元数据替换处理并发。暂存只写缓存字节；失败不改变活动指针。旧计划永不原地更新；运行时验证活动清单完整性。尚未激活的残留目录不会被当成活动历史。

`status`、`next`、`instructions` 和 `rollback` 只读取活动 Plan 和当前文件证据。Plan 保存结构，不存进度；状态仍由产物、Gate、任务复选框、Attempts 和证据推导。

旧元数据不含 Plan 时使用兼容适配器，既有目录和状态契约继续可读。新接口内部可复用图校验器，但不直接受旧 Node ID 正则或 Schema 文件形态束缚。

## D7：依赖 DAG 与返工边分开

执行依赖 Graph 必须无环。返工规则可以返回已执行阶段，但属于受次数限制的恢复动作，不能作为反向依赖边插入 DAG。

QA Failure 结构化头部示例：

```yaml
verdict: FAIL
route_case: backend
summary: 支付确认接口返回错误状态
```

`rollback` 根据失败 Gate 与分类查找固化的规则，重置目标 Fragment 的全部成员、失败 Gate 及这些 Node 的传递下游。BE 与 FE 并行时，BE 返工不重置独立 FE 分支；QA 和 Assurance 因依赖 BE 而重置。FE 在修复期间被实际修改时，最终保障会检查其证据是否仍有效。

归档范围包括报告、产物、Gate 证据及受影响的保障证据，不回退业务代码。Attempts 记录 Gate、路由分类、目标实例、重置闭包和归档文件，并成为下一轮指令上下文。操作使用写锁和可恢复事务记录；中途失败阻塞继续执行，可恢复后再推进，不能把部分归档当作完整重置。

每条恢复规则规定 `max_retries`。超过上限、分类非法、元数据损坏或目标不安全时停止并报告。普通 Gate 仍可使用 Fragment 内的局部 `on_fail.reset`。

## D8：Gate 证据绑定“审查开始时的内容”

仅在提交 PASS 报告时计算当前摘要不足以证明审查覆盖了该版本。采用两步协议：

1. `gate begin` 为就绪 Gate 冻结审查输入，返回只读 Diff 清单、当前匹配内容摘要、报告上下文和审查令牌；令牌绑定 Change、Plan、Gate、范围规则及本轮执行。
2. 人或 Agent 对该输入完成审查/测试，调用 `gate record` 提交报告和令牌。LoopSpec 再次检查当前内容、规则、Plan 和尝试轮次与 begin 一致，才记录 PASS。期间修改代码则拒绝 PASS，要求重新 begin。
3. begin 与 record 均检查 Gate 就绪状态；审查令牌只供当前轮次一次性记录，不能覆盖已有终态或跨 Gate/Change 重放。

测试结果也是 Gate 证据；只有产物存在的普通 Node 不会自动被当成测试 PASS。证据含 Gate 规范实例 ID、Plan 摘要、审查输入摘要、规则摘要、基线、匹配文件及状态、报告哈希和本轮令牌。报告不能自报 `scope_digest` 或覆盖系统字段，原始证据记录原子写入。

声明代码证据的 Gate 只有报告与系统证据同时有效才是 done；新修订、返工或已确认的范围摘要变化使它回到 ready，其下游重新阻塞。历史报告仍可归档，但存在旧 pass.md 不能阻止必要重审，也不能通过 Gate 就绪检查复用旧结果。状态优先处理未恢复事务和待处理失败路由，再选择合法就绪 Node。

开始与记录命令没有自动认证审查者身份。协议证明记录所绑定的输入一致，不能证明模型真的审查充分或所有测试真实执行。维护者可在 CI 验证同一证据契约；本版本不安装 Hook。

## D9：Assurance 规则匹配实际 Diff 和审查能力

`change-assurance` 是包含系统确定性保障 Gate 的普通 Fragment。其 Node 配置关联随 Plan 快照的规则文件：

```yaml
version: 1
unknown_paths: fail
rules:
  - id: backend-change
    paths: [backend/**, api/**]
    requires: [backend-tests, security-review, pr-review]
    repair_fragment: be-implementation
  - id: frontend-change
    paths: [frontend/**, web/**]
    requires: [frontend-tests, pr-review]
    repair_fragment: fe-implementation
```

`requires` 在规则文件中是审查能力名称，Fragment 的具体 Gate 声明所提供能力及实际覆盖范围；Plan 编译将每个能力绑定到具体 Gate 实例。这与 Node `requires` 的执行依赖语义在模型中分开。一个 FE 的 PR Review PASS 不能覆盖它没审过的 BE 文件。

规则覆盖是全量 Diff 中每个路径所有命中规则的要求并集。每项要求需具有具体 Gate 的有效 PASS，绑定当前匹配变更集、内容/删除状态、文件类型/模式、基线和规则摘要。必要 Gate 不在活动 Plan 中时允许完成提议校验，但 Plan 标记该能力未提供；实际 Diff 一旦命中必须保障失败并要求扩张，绝不能当作无需检查。

Assurance 输出按 `missing_evidence`、`stale_evidence`、`unknown_paths`、`missing_fragments` 分类。已有修复实例按预声明恢复规则重跑；没有对应实例则生成需要扩张的诊断，LLM 提议新 Plan。修复完成后返回受影响的 QA，再重新 Assurance，不能审查后跳过回归测试。

Assurance 的 PASS 只能由确定性验证命令产生，手写 `pass.md` 无法让保障 Gate 完成。其证据绑定全量 `diff_digest`。最终保障必须依赖所有代码交付分支，且位于交付 Node 之前。`next`、完成判断和归档前复核其摘要；Diff 变化时按五态协议将该 Gate 重新就绪，并输出 `evidence_stale` 原因，后续交付节点阻塞。

## D10：基线、完整性与自引用处理

默认代码基线是创建 Plan 时固定的 HEAD Commit/Tree；这覆盖此前尚未提交的修改和之后的全部变更，包含已经在 Plan 执行期间提交的修改。已有分支上的需求可显式选择已校验的基准 Commit，不能自动推测用户希望覆盖哪段历史。已有脏工作树纳入检查并在提议中展示，不悄悄丢弃。

从固定基线到当前工作树枚举所有已跟踪及未跟踪文件，同时区分 Index 内容：已暂存内容与最终工作树不同且拟提交 Index 时必须单独校验 Index 摘要。重命名以旧路径删除和新路径新增进入覆盖检查；删除、执行位、符号链接目标、大小写差异均进入摘要。

不运行 Git diff 外部驱动、textconv、过滤器或任何工作区脚本；Git 子进程通过固定参数数组调用，路径作为数据，输出使用 NUL 分隔。读取不跟随仓库外符号链接，未知类型、子模块内部修改、不可解码路径或不稳定扫描在本版中明确失败并报告限制。开始/结束扫描校验 HEAD、Index 与读取条目一致，发现并发变化失败而不是使用混合摘要。

LoopSpec 生成报告本身会改变 Diff，因此计划定义的精确控制目录单独分类为管理产物，并由范围固定、类型校验及资源完整性校验处理；不要求业务 Gate 覆盖它们。该排除目录在摘要与审批中可见，不能接受任意 exclude Glob，更不能把源代码目录伪装成控制目录。Snapshot、Gate Evidence、Attempts 等采用独立管理区，避免保障 PASS 写入后使自身摘要立即过期。框架代码、可执行配置、Profile、Fragment 或规则源文件若在本需求中修改，仍按项目规则审查，不一概排除整个 Home。

对忽略文件不可静默遗漏：只跳过固化的工具生成目录；其他忽略文件默认报告未覆盖，或由维护者显式分类。扫描有文件数、单文件和累计字节上限；超限默认失败。报告输出清单、状态和哈希，不输出源代码、Secret 值或不必要 Diff 内容。

代码保障要求 Git 工作树；非代码 Profile 可以不启用代码保障，但仍执行项目对应约束。LoopSpec 控制的边界只对读取时刻的代码/Index 提供保证，用户在其外部修改或提交需要 CI/提交工具复核；文档不得把本地流程描述成不可绕过的提交防线。

## D11：返工与 Plan 修订是两种动作

返工沿已有规则重置证据与产物，不修改 Plan 结构。普通 `recompose` 只改变当前游标之后、没有执行或 Attempts 证据的工作；冻结节点定义、资源、身份、已生效依赖和规则保持相同。

实际改动扩展至 Plan 外的 BE 时，Assurance 诊断触发增加型安全扩张：保留旧节点定义和固定基线，新增所需 Fragment，并对受影响的 QA/Assurance 设置新的前置条件。必须显式列出因新增依赖而失效的旧节点；只允许这些旧节点添加新前置条件，并立即归档它们的旧产物/证据。不能一边改变旧依赖、一边声称所有旧节点都没变。

修订激活与失效归档在同一个受写锁保护的可恢复事务中完成。失败保留旧活动绑定或阻塞到事务恢复，不能激活新图却保留旧完成结果。证据绑定 Plan 摘要，因此 V2 的简单安全默认是新修订不继承旧代码 Gate PASS；所有当前 Diff 要求的 Gate 重新审查，未来才考虑经过严格证明的证据继承。

保护规则或审查定义变化不能伪装为增加型扩张。降低保护需单独人工批准。历史 Plan 与 Attempts 全部保留。

## D12：交付边界与具体场景

V1 交付四层模型、实例化/编译、Profile 发现和保存、不可变 Plan、计划生成/检查、旧 Change 兼容及内置大型需求、前端小需求、Bugfix 模板。V1 的代码流程尚不宣称具有 V2 的 Diff 证据保障；不能把未实现的保障 Node 作为通过结果展示。

内置模板按最低引擎能力版本声明：V1 使用人工 delivery-review 收尾；V2 模板使用系统 change-assurance。含有 assurance 或 V2 recovery 的请求在仅支持 V1 的引擎上以 unsupported_capability 拒绝，而不是生成一个无法完成或假装已检查的 Plan。完成两版后默认使用 V2 代码模板。

V2 交付有限失败路由、Fragment 重置闭包、Gate begin/record、固定基线的 Diff 清单、Assurance、证据过期、计划修订与安全扩张，完成以下路径：

| 场景 | 预期行为 |
|---|---|
| 前端小需求 | 选 FE、前端测试、最终保障，跳过不相关的大型 PRD/BE 流程 |
| QA 报后端问题 | 重跑 BE 包含的实现/测试/安全审查/PR Review，再 QA 和 Assurance |
| QA 判断 FE，但修复改了 BE | Assurance 要求 BE 证据；没有 BE 时增加型修订补入，之后重新 QA |
| 安全审查后 PR 修改 BE | 当前 Scope 与安全 PASS 不一致；最终保障阻塞并要求重审 |
| FE/BE 都引用 PR Review | 两个实例独立产物与证据，不互相覆盖 |
| 修改未分类路径 | 保障失败，由维护者完善覆盖规则并重新生成 Plan |
| 保障后代码变化 | 原保障重新就绪，交付/完成/归档被阻塞 |

## 风险与权衡

- Fragment 级重跑可能重复部分工作；以完整复用边界换取明确的返工顺序，支持拆分过大的 Fragment。
- Profile 选择是 LLM 判断，项目最低约束和 Diff 覆盖负责兜底；不能靠选择“轻模板”消除审查责任。
- YAML、资源、Git 路径都不可信；严格模型、目录约束、无 Shell 调用、单次缓存和读取限额承担输入边界。
- 内容摘要证明输入相同，无法证明审查质量；独立人员和 CI 仍承担真实审查责任。
- 变更多版本和可恢复重置增加实现成本；事务恢复与负向测试为第二版本的必需交付项。

## 实施与迁移顺序

先建立模型、兼容适配、Fragment/Profile 编译及快照，验证 V1 三类场景。再实现恢复、证据与 Diff 校验，最后处理修订、事务恢复和完整闭环。更新全部中文需求材料和中英文产品文档，不改动用户安装的 AI-DLC 文件。

新 Plan 采用新的格式版本；旧 CLI 无法识别时明确拒绝。旧 Schema 及旧 Change 不强制迁移。

## 设计假设

现阶段以单 Git 工作树为代码保障单位；跨仓库 Plan、子模块内部改动和外部提交原子控制不在 V2 范围。模板路径需要项目初始化配置。Profile 图可表达并行，但 Agent 的默认 next 仍按确定性拓扑顺序一次推进一个就绪 Node。
