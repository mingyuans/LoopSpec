## Context

内置 schema `secure-spec-driven` 当前是 `proposal → {specs, design} → tasks → security`，全部 5 个节点都在产出"计划类文档"。实现阶段不在图内，人类也没有明确的签核点。

用户要求：参照 `.claude/skills/openspec-apply-change` 的实现给内置 schema 加上 `apply` 环节，并在 `apply` 之前插入一个 `approval` 环节——由 LLM 把当前结果与产物汇总给人类，人类审查并确认执行计划是否需要调整；无需调整则继续 `apply`。

调研 OpenSpec 源码（`/Users/xq.yan/otherprojects/OpenSpec`）确认其 apply 机制如下：

- `schemas/spec-driven/schema.yaml` 里 `apply` **不是** artifact，而是与 `artifacts:` 并列的独立块：`apply: {requires: [tasks], tracks: tasks.md, instruction: ...}`（见 `src/core/artifact-graph/types.ts` 的 `ApplyPhaseSchema`）。
- 专用命令 `openspec instructions apply` 走 `generateApplyInstructions()`（`src/commands/workflow/instructions.ts:331`），返回 `contextFiles`（artifact id → 实际文件路径数组）、`progress{total,complete,remaining}`、`tasks[]`、以及一个由当前状态推导出的 `state`（`blocked`/`ready`/`all_done`）与动态 `instruction`。
- checkbox 解析在 `src/utils/task-progress.ts`：`/^[-*]\s+\[[\sx]\]/i` 计总数、`/^[-*]\s+\[x\]/i` 计完成数。
- skill 正文（`openspec-apply-change`）的循环是：选 change → `status` 认 schema → `instructions apply` → 读 `contextFiles` 全部文件 → 报进度 → 逐条实现并即时把 `- [ ]` 改 `- [x]` → 遇阻塞就停下问人。
- OpenSpec 里 apply 阶段**没有**"实现完了写一份产物"的概念，也没有回退机制：卡住就是暂停问人，靠人接手。

loopspec 与 OpenSpec 的关键结构差异决定了不能照搬：loopspec 里"节点完成"完全由文件系统推导，gate 节点用 PASS/FAIL 两个互斥产物表达判定，FAIL 触发 `on_fail.reset` 回退闭环并把失败原因通过 `priorAttempts` 喂回重做节点。这套机制恰好是 OpenSpec apply 阶段缺失的那一半（"实现中发现计划不对怎么办"），所以本设计把 apply 纳入节点图，而不是移植一个平行的 `apply:` 块。

## Goals / Non-Goals

**Goals:**
- 内置 schema 覆盖到实现阶段：`... → security → approval → apply`，`apply` 完成即代码已落地、任务全部勾选。
- `approval` 是真正的人类签核点：LLM 汇总产物 → 通过宿主工具的交互提问能力问人 → 依人类回答二选一写 PASS/FAIL；拿不到真人回答时绝不自行签核。
- 人类要求调整时能自动回到"重做计划"，且重做时能看到人类的原话（复用 `rollback` + `priorAttempts`）。
- 实现阶段可恢复、可观测：任何时刻 `status`/`instructions` 都能报出"还剩几条任务"，Agent 会话中断后重新进来能接着做。
- 引擎层新增的能力（`tracks` + 进度解析 + `contextFiles`）保持 schema 无关，自定义 schema 可以复用，不为内置 schema 开后门。

**Non-Goals:**
- 不移植 OpenSpec 的独立 `apply:` 块与 `openspec instructions apply` 子命令；loopspec 用统一的 `instructions <node>` 表达。
- 不移植 OpenSpec 的 `state: blocked|ready|all_done` 字段——loopspec 的五态（`blocked`/`ready`/`done`/`failed`/`exhausted`）已经覆盖，再加一个平行状态机只会产生歧义。
- 不做代码改动的回滚/撤销。loopspec 只管 change 目录内的产物，`apply` FAIL 时已落地的代码改动由人类/git 处理，本设计只要求把它记录清楚。
- 不校验"报告里声称的改动是否真的发生"。引擎不读代码库、不跑测试，`tracks` 只能保证 checkbox 层面的完整性。
- 不引入新的节点类型（如"人类节点"）、不引入新的 CLI 子命令、不引入新依赖。
- 不自动改写既有 change 或既有 workflow home 里的 schema 拷贝。

## Decisions

### D1. `approval` 与 `apply` 都做成 gate 节点，而不是普通节点或独立的 `apply:` 块
**决策**：两者都是 `gate` 节点，`generates: null`、`template: null`，各自声明一对互斥产物：
- `approval`：pass `approval/approved.md`、fail `approval/changes-requested.md`
- `apply`：pass `apply/report.md`、fail `apply/blocked.md`

**备选方案 A**：仿 OpenSpec 在 schema 顶层加 `apply:` 块 + 新增 `loopspec instructions apply` 子命令。
**备选方案 B**：`apply` 做成普通节点，只产出一份 `apply/report.md`。

**取舍理由**：
- 方案 A 会在 loopspec 里凭空造出第二套状态机（apply 不在 `build_order` 里、不参与 `isComplete`、不能被 `requires` 引用、无法回退），与"一切皆节点、状态皆推导自文件系统"的核心设计冲突；而 loopspec 的每一条既有能力（`status`/`instructions`/`rollback`/`history`/`archive`）都是围绕节点图写的，加一个平行概念要动的地方远比加两个节点多。
- 方案 B 无法表达"实现中发现计划走不通"这一真实且高频的结果。gate 的二选一恰好表达"要么做完了（report），要么被计划本身卡住了（blocked）"，且 FAIL 自动带来回退闭环 + `priorAttempts` 反哺——这正是 loopspec 相对 OpenSpec 的增量价值所在。
- `approval` 天然是二值判定（人类点头/要求调整），本来就是 gate 语义，且 FAIL 需要携带"人类意见"列表回到上游，与 `security` gate 的 `blockingIssues` 机制完全同构，零新增引擎代码。

### D2. `approval` 依赖宿主工具的交互提问能力，并设"禁止自行签核"红线
**决策**：`approval` 的指令要求 LLM (1) 先把 `contextFiles` 里全部产物读齐并汇总成人类可读摘要（要解决什么 / 新增修改哪些能力 / 关键决策与取舍 / 任务规模与顺序 / 安全结论与遗留风险）；(2) 通过宿主工具的交互提问能力向人类提出"按此计划执行 / 需要调整"的选择——Claude Code 用 `AskUserQuestion`，其他工具用其等价机制，指令里以"你的宿主工具的交互提问能力（例如 Claude Code 的 `AskUserQuestion`）"表述；(3) 只有拿到真人明确回答后才写对应产物。**没有真人回答就两个产物都不写**，节点停在 `ready` 等人。

**备选方案**：引擎新增一种"人类节点"类型，由 CLI 自己去 stdin 读人类输入。
**取舍理由**：loopspec 的 CLI 是被 Agent 以 `--json` 方式调用的非交互工具（`tools_cli.py` 里唯一的交互逻辑只服务于 `init` 的工具选择），把审批交互放进 CLI 会同时破坏 JSON 协议和"Agent 驱动"模型。相反，"让 Agent 用它自己的提问工具去问人"完全落在指令文案层，零引擎改动，且天然适配全部 5 个已支持工具。红线写进指令文案是必要的：这是唯一一个判定依据不在文件系统里、而在真人脑子里的节点，必须显式禁止 Agent 自证。

### D3. `approval` 的 `on_fail.reset: [specs, design]`，`max_retries: 5`
**决策**：人类要求调整 → 回退闭环 `specs`/`design`/`tasks`/`security`/`approval`/`apply`，保留 `proposal`；重试上限 5，耗尽后 `escalate`。

**备选方案**：`reset: [design]`（与 `security` 一致，只重做设计与任务）或 `reset: [proposal]`（全部重做）。
**取舍理由**：`on_fail.reset` 在 schema 里是静态的，Agent 无法按人类意见动态选择回退范围，所以只能取"够用的最小上界"。人类在这个关卡看到的是完整计划，意见很可能是"这个范围不对/还要覆盖 X"（属于 specs）而不只是"实现方式换一种"（属于 design）；reset 少了会导致人类的意见根本无法落地（specs 不动，tasks 重做也还是老需求），reset 到 `proposal` 则连"为什么做"都推翻，代价过高。回退是归档而非删除（`.attempts/round-NNN/`），且重做时能看到上一轮内容与人类意见，因此多回退一层 specs 的成本可控。上限取 5（高于 `security` 的 3）是因为这是与真人来回打磨的关卡，反复几轮属正常。

### D3b. 人类的判定必须由 LLM 回写 `state.md`：原话归产物、`state.md` 只记提炼且去指代的信息
**决策**：`approval` 写出判定产物后，LLM 必须把人类的判定回写 `state.md`：`Decision Log` 追加一条"第 N 轮 / 认可或要求调整 / **提炼后的判定要点** / 产物路径"；认可时把已签核要点追加到 `Frozen Decisions`（后续节点不得擅自改动，要改需重走 approval）；要求调整时把否决的做法追加到 `Rejected Options`、未定论的问题追加到 `Open Questions`、并把 `Current Focus` 改写为"按人类第 N 轮意见重做 specs/design"；`Artifact Notes` 记产物路径与结论。轮次 N 由 `instructions` 响应里 `priorAttempts` 中属于本 gate 的条目数 +1 推导。一律追加，不得删改历史条目。

两条配套约束：
- **原话摘录只进产物，不进 `state.md`**：人类的原话写在 `approval/approved.md` / `approval/changes-requested.md` 里，`state.md` 只放提炼结果 + 指向该产物的路径。
- **`state.md` 的每条记录必须去指代、自包含**：原话里的"这个/那个/它/上面说的/刚才那条/这里"必须替换成具体所指（能力名、文件路径、任务编号、需求名、决策编号）。例：人类说"这个先不做，那个要补测试" → `state.md` 写"暂不实现 `<具体能力名>`（原任务 3.2）；为 `<具体模块路径>` 补测试"。

两份 approval 模板各加一个「state.md 回写记录」小节。

**备选方案 A**：只把人类结论写在 gate 产物里，不动 `state.md`。
**备选方案 B**：`state.md` 里也照录原话（追求保真）。
**备选方案 C**：引擎解析 `state.md` 并自动维护这些记录。

**取舍理由**：
- 方案 A 会丢信息：`approval` FAIL 后回退会把 `approval/changes-requested.md` 连同 specs/design/tasks 一起 `move` 进 `.attempts/round-NNN/`，人类的意见只能通过重做节点的 `priorAttempts` 看到——而 `priorAttempts` 是**按节点**过滤的（`prior_attempts_for_node` 用节点产物路径匹配归档文件），下游节点（如后来的 `apply`）根本看不到当初人类说过什么。`state.md` 恰恰是唯一"不属于任何节点产物、回退时不被归档"的文件（`change-memory` 已有明确要求），因此是跨轮次承载决策记忆的唯一合适载体。
- 方案 B 混淆了两种载体的职责。**保真**的需求由产物承担：产物是一次性写入、内容不再变动、回退后仍在 `.attempts/round-NNN/` 里可查（`priorAttempts.archivedPath` 直接指向它），是原话的正确归档地。**可用**的需求由 `state.md` 承担：它是被后续每个节点反复读取的工作记忆，越紧凑越有用，照录一段口语会让它迅速膨胀成聊天记录，且同一信息出现两份还会产生"以哪份为准"的歧义。所以分工是：想看人类到底怎么说的 → 去产物；想知道现在受哪些约束 → 读 `state.md`。
- **去指代**是这套分工能成立的前提：口语里的"这个/那个"依赖当时的对话上下文，而读 `state.md` 的下游节点（重做的 `specs`、后来的 `apply`）根本没有那段上下文。保留指代词的条目等于不可解析的死文本——比不写更糟，因为它看起来像有信息。把指代消解成具体的能力名/任务编号/文件路径，这条记录才真正可被后续节点执行。提炼时要保住限定词（"可以，但 X 必须先做"里的"但 X 必须先做"），失真风险由产物里的原话作为兜底。
- "追加不覆盖"是关键约束：人类第二轮的意见常常是对第一轮的补充或修正，覆盖会让重做节点误以为只有最后一条要求；而 `state.md` 又不像产物那样有 `.attempts/` 历史可回溯，一旦被改写就永久丢失。
- 方案 C 与既有设计直接冲突：`artifact-state` 与 `change-memory` 都已明确规定引擎不解析 `state.md`、不用它驱动状态判定。让引擎去写它就必须先解析它，等于开一个"第二状态源"的口子。因此这条规则落在指令文案层，靠模板的「state.md 回写记录」小节提供可审计性——评审产物时就能看出回写有没有做。
- 这条规则同时明确了一个反向边界：`state.md` 里写着"人类已认可"但 pass 产物不在，节点状态依然是 `ready`。记录是记录，判定永远只看产物文件。

### D4. `apply` 的 `on_fail.reset: [design]`，`max_retries: 2`，并要求 FAIL 产物记录已落地的代码改动
**决策**：实现被卡住 → 回退闭环 `design`/`tasks`/`security`/`approval`/`apply`；重试上限 2，耗尽后 `escalate`。`apply/blocked.md` 模板包含"已落地的代码改动"小节。

**取舍理由**：实现阶段被卡住，几乎总是"怎么做"层面的问题（设计有硬伤、任务前提不成立），`design` 是恰当的回退起点；若真是需求层面错了，人类会在紧随其后的 `approval` 关卡再次拦下来。上限取 2 而非 3：一轮 `apply` 返工意味着已经写过一次代码，代价远高于重写一份文档，两轮不成应该尽早把人拉进来。**关键约束**：loopspec 的回退只 `shutil.move` change 目录内的产物文件，代码库改动完全不受影响；因此 FAIL 产物必须显式记录"我已经改了哪些文件"，否则下一轮重做设计时会在一个自己不知道的脏工作区上继续，这是本设计里最容易踩的坑。

### D5. 引入通用的节点字段 `tracks`，而不是让 `apply` 硬编码读 `tasks.md`
**决策**：`NodeSpec` 新增可选字段 `tracks: str | None`，值必须是某个节点 `generates` 声明的具体路径，且该节点必须是声明方的祖先。内置 schema 的 `apply` 声明 `tracks: tasks.md`。

**取舍理由**：直接对应 OpenSpec 的 `apply.tracks`，但落在节点上而不是顶层块上，因此任何 schema 的任何节点都能用（例如自定义 schema 里"逐条执行验收清单"的节点）。三条校验（非 glob、必须是某节点的 `generates`、必须是祖先）把"追踪一个还不存在或永远不会存在的文件"这类配置错误挡在加载期：非 glob 是因为进度必须来自一个确定文件（OpenSpec 允许 glob 聚合多文件，但那会让"哪个文件该被勾选"变得模糊）；必须是祖先是因为被追踪文件得在本节点开工前就已产出。

### D6. `tracks` 不只用于展示进度，而是节点完成性的硬约束
**决策**：声明了 `tracks` 的节点，在原有完成判定（普通节点产物存在 / gate PASS）之外，还必须满足"被追踪文件存在、`total > 0`、`remaining == 0`"才计入 `completed`；否则退回 `ready`。gate 的 FAIL 判定优先于本约束。

**备选方案**：只在 `instructions`/`status` 里报告进度，完成性仍只看产物文件是否存在（OpenSpec 的做法——它的 `all_done` 只是提示，不阻止归档）。
**取舍理由**：不加这条约束，`apply` 就退化成"写一份报告即完成"，一条任务都没勾的 change 也能 `isComplete: true` 并被 `archive` 归档，这与 loopspec"状态推导自事实、不信声明"的整个立意相反（`artifact-state` 里已有"`state.md` 标注不参与状态判定"的同类要求）。实现代价极小：`compute_states` 的第一趟在把节点加入 `completed` 前多一次判断。副作用是会出现"pass 产物已存在但节点仍 `ready`"的状态——这正是我们想要的语义（"报告写了，但活没干完，继续干"），并且 `status` 的 `taskProgress` 会直接说明还剩几条，不会让人困惑。FAIL 优先是为了避免"被卡住 + 任务没做完"时状态从 `failed` 掉回 `ready`，那会让回退无从触发。

### D7. `instructions` 新增 `contextFiles`，覆盖全图已有产物，而不是靠冗余 `requires` 边
**决策**：`instructions` 响应新增 `contextFiles`（节点 ID → 现存产物绝对路径列表，省略无产物的节点），覆盖 schema 全部节点。

**备选方案**：把 `apply`/`approval` 的 `requires` 写成 `[approval, proposal, specs, design, tasks]`，借现有 `dependencies` 字段把路径带出来。
**取舍理由**：备选方案会往依赖图里塞进语义上冗余的边（`proposal` 已是 `apply` 的传递祖先），污染 `unlocks`、`build_order` 与 reset 闭环的可读性，只为搬运几个路径。`contextFiles` 直接对应 OpenSpec `generateApplyInstructions()` 里的同名字段，是"要读齐上游全部产物"这类节点的通用需求，实现只是对每个节点跑一次已有的 `resolve_outputs()`。

### D8. `status` 只带进度摘要，逐条任务只在 `instructions` 里给
**决策**：`status` 的节点条目在声明 `tracks` 时附 `taskProgress`（`path`/`resolvedPath`/`total`/`complete`/`remaining`）；逐条 `tasks[]` 只出现在 `instructions` 响应里。

**取舍理由**：`status` 是循环的枢纽、每一步都会被调用，把几十条任务正文塞进去会显著撑大每次响应；但"还剩几条"是驱动循环必须的信息（对应 skill 正文里的 "Progress: N/M tasks complete"），所以摘要留在 `status`。既有需求已明确 "`status` SHALL 不返回节点的模板正文"，本决策与那条边界一致。

### D9. skill 正文只做最小、schema 无关的补充
**决策**：`_CONTINUE_BODY` 里"写产物到 `resolvedOutputPath`"一句扩写为"按返回的 `instruction` 行事——可能是写产物文件，可能是先向人类提问确认后二选一写入，也可能是直接改动代码库并更新被追踪的任务清单"，不提 `approval`/`apply` 这两个节点名。

**取舍理由**：skill 模板是所有 schema 共用的（`lpsx-skills` 能力已规定"一份正文跨工具复用"），硬编码内置 schema 的节点名会让自定义 schema 的用户读到不适用的指令。真正的节点级指令由 `instructions` 的 `instruction` 字段下发——这本来就是 loopspec 的分层：skill 只教"怎么跑循环"，schema 教"每个节点做什么"。

### D10. 内置 schema 的指令与模板写成文件，而不是内联字符串
**决策**：新增 `instructions/approval.md`、`instructions/apply.md` 与 4 份 gate 模板文件（`approval-approved.md`、`approval-changes-requested.md`、`apply-report.md`、`apply-blocked.md`），沿用现有 `instruction: {file: ...}` 引用形式。

**取舍理由**：与既有 5 个节点保持完全一致（`schemas/secure-spec-driven/instructions/*.md` + `templates/*.md`），指令文案较长，内联进 YAML 会让 schema 难读难 diff。fail 模板必须包含一个"阻断问题"无序列表小节，因为 `extract_failure_notes()` 正是从 `- ` 列表项提取 `blockingIssues`、从首个 `#` 标题提取 `summary`——模板结构直接决定回退信息的质量。

## Risks / Trade-offs

- **既有未完成 change 会多出两个待办节点（破坏性）** → 每个 change 的 schema 从其 workflow home 的 `schemas/` 目录加载（`.workflow.yaml` 只记名字），所以不刷新本地 schema 拷贝的 change 完全不受影响；仓库内 `loopspec/changes/improve-init-display` 属于这种情况。刷新拷贝的动作留给使用者显式执行，本变更不自动改写任何 workflow home。
- **`approval` 在非交互/无提问能力的环境里会停滞** → 这是设计意图（人类签核不可代劳），但需要在指令里把"停下来等人"写成明确动作，避免 Agent 误以为自己陷入死循环而乱写产物。`status` 会一直显示该节点 `ready`，语义上就是"等人"。
- **LLM 可能忘记回写 `state.md`** → 引擎无法强制（它不解析 `state.md`）。缓解手段有两层：指令里把回写列为写出判定产物后的必做步骤；两份 approval 模板留一个「state.md 回写记录」小节，没回写就会在产物里留下空白，人类下一轮审阅时立刻可见。
- **"提炼"可能提炼过头，丢掉人类意见里的限定词** → 这是原话与提炼分离的固有代价。兜底是产物里保留了原话摘录、且 `Decision Log` 每条都带产物路径，任何时候都能回查原文核对；指令里也明确要求提炼时保住限定与例外条件。
- **`tracks` 只能保证 checkbox 被勾，不能保证代码真的改了** → 引擎不读代码库。缓解手段是把举证责任压在报告模板上（改动文件清单 + 测试实际输出），并依赖 `git diff`/后续人工核对；不试图在引擎层做无法做到的验证。
- **`reset: [specs, design]` 可能过度回退** → 人类只想微调任务顺序时也会重做 specs。静态 `reset` 的固有代价；已通过"回退是归档 + `priorAttempts` 携带上一轮内容"把重做成本压低。若将来引擎支持动态 reset，此处应改为按人类意见选择范围（列入 Open Questions）。
- **`status` 每次多读一个文件** → 只有声明 `tracks` 的节点会读，单文件、几 KB 量级，可忽略。
- **"pass 产物存在但节点 `ready`"是一个新的反直觉状态** → 靠 `taskProgress` 在同一份响应里解释原因；已在 `artifact-state` 与 `builtin-schema` 的场景里显式规定，避免被当成 bug。

## Migration Plan

1. 先落引擎侧（`tracks` 字段 + 校验 + 进度解析 + 状态约束 + `instructions`/`status` 字段），这一步对现有 schema 完全无感（`tracks` 可选，未声明即旧行为）。
2. 再改内置 schema（新增 2 节点 + 2 指令 + 4 模板），`loopspec schemas validate secure-spec-driven` 通过即生效。
3. 源码检出无需重装：`_builtin_schemas_source()` 在 editable 安装下解析到 `src/loopspec/builtin_schemas`（不存在），回落到仓库根 `schemas/`，改完立即生效；wheel 侧由 `[tool.hatch.build.targets.wheel.force-include]` 自动打包新增文件，`make build` 可验证。
4. 已初始化的 workflow home 需要手动刷新 schema 拷贝（删掉 `<home>/schemas/secure-spec-driven` 后重跑 `loopspec init <home>`，或直接覆盖该目录）。**刷新前请确认该 home 下没有正在进行、且不希望被追加两个新节点的 change。**
5. 回滚方式：还原 `schemas/secure-spec-driven/schema.yaml` 的 2 个节点即可让内置 schema 回到旧链路；引擎侧的 `tracks` 支持可以保留（无 schema 声明它就不生效）。

## Open Questions

- `approval`/`apply` 的 `max_retries`（5 / 2）目前硬编码在内置 schema 里。是否需要让项目级 `config.yaml` 覆盖 gate 的重试上限？本次不做，等出现真实诉求。
- `on_fail.reset` 是否值得支持"由 gate 的 FAIL 产物动态声明本轮回退范围"（让人类意见决定回退到哪一层）？这会改动 `gate-rollback` 能力的核心语义，本次不做。
- `tracks` 是否应支持 glob 以聚合多文件进度（OpenSpec 允许）？本次限定为单个具体文件，等出现"任务清单被拆成多文件"的真实 schema 再议。
