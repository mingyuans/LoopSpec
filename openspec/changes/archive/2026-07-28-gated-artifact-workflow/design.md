## Context

LoopSpec 要实现一个纯 Python、面向 LLM 消费的 CLI（`loopspec`），把"用户声明 artifact 依赖图 → LLM 依次生成 → 质量门禁失败可回退重做"的协议固化为可测试的代码。参考实现思路来自内部文档《Gated Artifact Workflow —— Python 实现技术方案》，该文档已给出完整的数据模型、算法伪代码、目录布局、CLI JSON 契约与测试用例清单，本设计据此转写为工程决策，不重复贴原文伪代码。

当前仓库是全新的空骨架项目（仅有 `README.md`、`LICENSE`、`openspec/` 规划目录），没有既有代码约束，可以按参考方案的模块划分直接落地。

## Goals / Non-Goals

**Goals:**
- 实现一套可从磁盘完全重建的状态机：节点完成状态、gate PASS/FAIL、回退次数均由文件系统推导，不引入独立的进度数据库。
- 静态依赖图（`requires`）保持无环、可拓扑排序；"回退"建模为运行时把已完成节点移出 `completed` 集合，而不是在图上引入环。
- 回退必须是真实的文件移动（归档到 `.attempts/round-NNN/`），并携带失败原因（`priorAttempts`），使重试可收敛而非"重掷骰子"。
- 所有 CLI 命令提供 `--json` 结构化输出，作为 LLM/Agent 消费的主协议；人类可读输出是次要形式。
- 提供一个内置 schema（`secure-spec-driven`：`proposal → {specs, design} → tasks → security gate`）用于端到端验证；其中 `proposal`/`specs`/`design`/`tasks` 四个节点直接复用 OpenSpec 项目已验证的内置 schema `spec-driven`。

**Non-Goals（同参考方案"有意排除的能力"）:**
- 不支持按失败类型走向不同修复节点的条件分支（`on_fail` 仍是单一固定 reset 目标）。
- 不支持并行执行多个 ready 节点。
- 不提供"撤销回退"命令（归档文件人工 `mv` 回去即可）。
- 不支持跨 change 引用、不引入远程/数据库状态存储。
- `status` 等读命令不产生副作用；回退必须显式触发。
- `loopspec schemas show <name>` 不提供图形化（ASCII）依赖图渲染；v1 只返回结构化的节点列表与 `requires` 依赖关系。

## Decisions

### D1. 状态完全由文件系统推导，不维护内存/数据库状态
**决策**：节点完成态、gate PASS/FAIL、回退次数（`rollbacksUsed`）均通过扫描 `artifact_dir` 与 `.attempts/round-*/_meta.yaml` 实时计算，不缓存、不持久化到独立文件。
**理由**：状态文件与实际产物容易漂移（用户手工删文件、`git checkout` 切分支等），"扫描文件系统"是唯一不会漂移的真相源。
**代价**：每次 `status`/`instructions` 调用都要重新做文件系统扫描 + glob 匹配，但节点数通常 < 200，性能可忽略。

### D2. 环只存在于运行时语义，不进入静态依赖图
**决策**：`requires` 必须构成 DAG（加载期强制校验、拒绝有环 schema）。gate 失败触发的"回退"不建模为图上的边，而是把 reset closure 内节点的产物从磁盘移走，让原有的"`requires` 全部完成 → ready"判定自动重新生效。
**备选方案**：把 `on_fail.reset` 建模为反向边，将图变成有环图，再实现一个通用状态机解释器。
**取舍理由**：一旦允许成环，拓扑排序、就绪判定等成熟 DAG 算法全部失效，需要重新发明状态机，复杂度和测试成本远高于"文件移动 + 复用现有算法"。

### D3. gate 通过双路径（pass/fail）表达判定，不用单文件内字段
**决策**：gate 节点声明 `gate.outputs.pass` 与 `gate.outputs.fail` 两个具体（非 glob）路径；哪个文件存在即代表哪个判定。两者同时存在报 `gate_output_conflict`，两者都不存在且依赖满足则为 `ready`。
**理由**：延续"文件系统是唯一真相"——判定不依赖解析 Markdown 正文里的关键词或 frontmatter 字段，避免解析歧义和注入风险。

### D4. 回退闭包由系统计算，用户只声明起点
**决策**：`on_fail.reset` 只需声明回退起点节点 ID 列表；实际归档的节点集合 = `{reset 起点} ∪ {gate 自身}` 的全部传递后继，按拓扑序执行归档。
**理由**：防止用户漏写导致状态矛盾（例如只回退 `design` 但保留依赖它的 `tasks`，会出现"依赖未完成但自身已完成"的悖论状态）；gate 自身必须在闭包内，否则 fail 产物不会被移走，回退后立刻又判定失败，形成死循环。

### D5. `state.md` 是 LLM 工作记忆，不参与完成度判定
**决策**：`state.md` 由 `loopspec new` 创建初始模板，`loopspec instructions` 读取其正文并原样注入响应；`loopspec status` 只返回 `statePath`/`stateExists`，从不解析正文来判定任何节点状态。
**理由**：把"给 LLM 的决策日志/记忆"和"给系统的完成度权威数据"严格分层，避免 LLM 在正文里写错话（如误标 approved）导致状态机产生错误判断；状态判断永远以产物文件为准，`state.md` 只是辅助上下文。

### D6. `priorAttempts` 是回退机制收敛的必要字段，不是可选项
**决策**：`loopspec instructions <node>` 在该节点历史上被回退过时，必须返回按 round 升序排列的 `priorAttempts` 数组，每项含 `verdict`/`summary`/`blockingIssues`/`archivedPath`。
**理由**：没有这个字段，LLM 重做节点时看不到上次失败原因，大概率产出与上次雷同的内容，直到耗尽 `max_retries` 才被迫升级到人工介入；这违背"回退应该让下一轮更接近通过"的设计目的。

### D7. 命令行技术选型：Pydantic v2 + Typer + PyYAML
**决策**：Schema/Config 用 Pydantic v2（`extra: "forbid"` 强制未知字段报错），CLI 框架用 Typer，YAML 解析用 PyYAML，文件操作用标准库 `pathlib`/`shutil`。
**备选方案**：`click` + 手写 dataclass 校验；`ruamel.yaml`。
**取舍理由**：Pydantic v2 的字段校验、别名（`pass_`/`pass`）、`model_validator` 能直接覆盖 14 条语义校验中的大部分结构性检查，减少手写校验代码；Typer 基于 Click 但天然支持类型标注和 `--json` 双模式输出，符合"所有命令必须支持 `--json`"的接口契约。

### D8. Python 包名与 CLI 入口统一为 `loopspec`
**决策**：Python 包名与 CLI 入口均为 `loopspec`（`src/loopspec/`），与仓库名 LoopSpec 保持一致，不使用 `gated_workflow` 作为包名。
**理由**：避免包名与仓库名/CLI 命令名不一致造成的认知负担；用户安装后 `pip show loopspec`、`import loopspec`、命令行 `loopspec` 三者名称统一。

### D9. change 名称禁止包含 `/`，不支持嵌套目录
**决策**：change 名、schema 名、节点 ID 统一使用 `^[a-z][a-z0-9]*(-[a-z0-9]+)*$`，change 目录只有一层。
**理由**：允许嵌套路径会让"列出所有 change"的目录扫描逻辑复杂化，且与"change 名是唯一标识"的语义冲突；需要分组时用命名前缀即可（如 `prd-payment`）。

### D10. 内置 schema 的节点图与基础模板移植自 OpenSpec 的 `spec-driven` schema
**决策**：内置 schema `secure-spec-driven` 的节点图为 `proposal → {specs, design} → tasks → security`（5 节点，`specs` 与 `design` 并列，均只依赖 `proposal`；`tasks` 依赖二者；`security` 是 gate，依赖 `tasks`，`on_fail.reset: [design]`，`max_retries: 3`）。其中 `proposal`/`specs`/`design`/`tasks` 四个节点的 `generates`、`template`、`instruction` 内容直接移植自 OpenSpec 仓库的内置 schema `schemas/spec-driven/schema.yaml` 及其 `templates/{proposal,spec,design,tasks}.md`——该 schema 已在 OpenSpec 生产环境中验证过措辞与结构；只有 `security` 节点（`gate.templates.pass/fail`、`gate.outputs.pass/fail`、审查指令）是本方案新增内容，用于演示 gate/回退机制。
**备选方案**：沿用参考设计文档 4.1 节给出的简化四节点例子（`proposal → design → tasks → security`，无 `specs` 节点）。
**取舍理由**：直接复用已验证的真实 schema 能降低模板措辞质量风险，并让 `secure-spec-driven` 与用户熟悉的 OpenSpec `spec-driven` 工作流保持概念一致（同一套 proposal/specs/design/tasks 语义），迁移成本更低；`specs` 与 `design` 并行推进也更贴近真实规范驱动开发的产出节奏。

### D11. `archive`/`bulk-archive` 默认直接执行，不要求 `--apply`
**决策**：`loopspec archive`/`loopspec bulk-archive` 默认直接执行归档移动，不像参考设计文档 7.7/7.8 节那样默认 dry-run 并要求显式 `--apply`；改为提供可选的 `--dry-run` 标志用于预览。
**备选方案**：保留参考设计文档的"默认 dry-run + 显式 `--apply`"两步确认模式。
**取舍理由**：归档前已有独立的安全拦截规则把关（默认只归档 `isComplete` 的 change，`exhausted`/`failed` 状态需要显式的 `--exhausted`/`--include-pending-failures` 才能归档），且归档本身只移动不删除、目标冲突会报 `archive_conflict`，风险已被这些机制覆盖，不需要额外的两步确认；直接执行也让 Agent/LLM 驱动的调用链更短（不必先 dry-run 再重新调用一次 `--apply`）。需要人工确认的场景可自行加 `--dry-run` 预览。

## Risks / Trade-offs

- **[Risk] `generates` 配置成宽泛 glob（如 `**/*.md`）会把 `.attempts/`、`state.md`、`.workflow.yaml` 误判为产物，导致回退后节点仍显示 `done`，流程死锁。**
  → Mitigation：在 `resolve_outputs`（产物探测的唯一入口）里统一过滤这三类保留路径，并为此写专门的回归测试；schema 语义校验第 14 条同时禁止 `generates`/`gate.outputs` 直接声明这些保留路径。
- **[Risk] `nextSteps` 判定顺序错误（`ready` 优先于 `failed`/`exhausted`）会让 LLM 跳过归档直接覆写上游产物，丢失上一轮失败上下文。**
  → Mitigation：`build_next_steps` 按拓扑序遍历时，必须先检查 `exhausted`/`failed` 分支再检查 `ready` 分支；测试用例显式覆盖"gate 失败时上游物理上已具备 ready 条件"的场景。
- **[Risk] 回退归档中途失败（进程被杀/磁盘写满）导致 round 目录不完整，可能污染重试计数。**
  → Mitigation：`_meta.yaml` 作为归档的最后一步写入；`count_rollbacks` 只统计存在 `_meta.yaml` 且 `meta.gate == gate_id` 的 round，未完成的 round 不计数，允许人工修复后重跑。
- **[Risk] 多 gate schema 下，多个 gate 同时 failed 时如果都触发 rollback 会产生互相冲突的闭包。**
  → Mitigation：状态推导按拓扑序找到第一个 `failed`/`exhausted` gate 即返回，`nextSteps`/`pendingRollback` 只暴露这一个，其余 gate 的处理推迟到下一轮 `status`。
- **[Risk] Pydantic `extra: "forbid"` 可能在用户 YAML 存在拼写错误时报错信息不够定位到具体字段。**
  → Mitigation：`schema_loader` 捕获 `ValidationError` 后重新包装为统一的 `{error, message, fix}` 格式，`message` 中包含 Pydantic 给出的字段路径。

## Migration Plan

全新项目，无存量数据迁移需求。按 tasks.md 中的阶段顺序实现（models → graph → outputs/gate_outcome → state → attempts/rollback → change_state/instructions/policy → paths/config/cli → 内置 schema），每阶段完成后对应测试模块必须全绿才能进入下一阶段。首个可用版本发布后，`loopspec init --no-builtin` 提供不含内置 schema 的空骨架供用户自定义。

## Open Questions

- `rich` 是否作为强制依赖用于人类可读输出，还是保持可选（不影响 `--json` 主路径）。
