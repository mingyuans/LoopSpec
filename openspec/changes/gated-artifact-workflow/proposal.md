## Why

LLM 驱动的规范驱动开发（proposal → design → tasks → security review 等）目前缺少一个通用、可落地的编排框架:用户需要按 YAML 声明一串产物（artifact）及其依赖关系，由 LLM 依次生成，其中安全审查等质量门禁（gate）产出 PASS/FAIL 判定，FAIL 时需要回退到指定上游节点重做，并把上一轮失败原因带给 LLM 避免重复踩坑。当前没有这样一个"文件系统即真相、状态可从磁盘重建、回退可审计"的最小实现，团队只能靠 ad-hoc 脚本或人工协调多轮生成流程。LoopSpec 要从零实现这一 Python CLI 框架（`loopspec`），把这套协议固化下来，供 Agent skill（如 `/lpsx:*`）薄包装调用。

## What Changes

- 新增 Schema 定义与加载：YAML → Pydantic 模型，含 14 条语义校验（节点唯一性、`requires` 无环、gate 输出/模板完整性、`on_fail.reset` 必须指向祖先节点、路径安全等）。
- 新增依赖图算法：拓扑排序（Kahn，同层按字典序）、祖先/后继查询，用于状态推导与回退闭包计算。
- 新增节点状态推导（核心）：完全由产物文件存在性推导 `blocked/ready/done/failed/exhausted` 五态，不引入独立状态数据库；gate 通过 pass/fail 两个互斥产物路径判定 PASS/FAIL，两者同时存在报 `gate_output_conflict`。
- 新增门禁回退机制：失败时计算 reset closure（声明起点 + gate 自身 + 全部传递后继），把闭包内产物**移动**（非删除）到 `.attempts/round-NNN/`，写 `_meta.yaml` 记录 verdict/summary/blocking_issues；回退次数从 `.attempts` 目录重新统计，跨进程/重启持久。
- 新增 change 级工作记忆 `state.md`：记录当前焦点、冻结结论、决策日志、否决方案、开放问题；**不参与**完成度判定，仅作为 `instructions` 返回给 LLM 的上下文。
- 新增 `priorAttempts` 注入：重做节点时携带历次失败摘要、阻断问题列表和归档产物路径，避免"纯重掷骰子"式重试。
- 新增 `loopspec` CLI 及其 `--json` 契约：`init` / `schemas list|show|validate` / `new` / `status` / `instructions` / `rollback` / `history` / `archive` / `bulk-archive` / `version`，所有命令支持结构化输出，统一错误码格式（`error/message/fix`）。
- 新增内置 schema `secure-spec-driven`：节点图与 `proposal`/`specs`/`design`/`tasks` 四个节点的模板、指令直接移植自 OpenSpec 项目已验证的内置 schema `schemas/spec-driven/schema.yaml`（`proposal → {specs, design} → tasks`），在 `tasks` 之后新增一个 `security` gate 节点（`on_fail.reset: [design]`）演示回退机制；随 schema 一并提供全部模板与指令文件，用作端到端验证。
- 新增 change/schema 归档能力：默认直接执行、把符合条件的 change 移动到 `<workflow_home>/archive/YYYY-MM/`（可选 `--dry-run` 预览而不移动）；对未完成或待回退 change 默认拒绝归档。

## Capabilities

### New Capabilities
- `workflow-schema`: Schema 的 YAML 格式、Pydantic 模型定义、加载顺序（结构校验→语义校验）与 14 条语义校验规则、`config.yaml` 多 schema 候选与选择协议、路径安全规则。
- `workflow-graph`: 依赖图的无环校验、拓扑排序（Kahn 算法）、祖先/后继查询，供状态推导与回退闭包复用。
- `artifact-state`: 基于文件系统的产物存在性判定（含 glob 支持与 `.attempts`/`state.md`/`.workflow.yaml` 排除规则）、gate pass/fail 判定与失败摘要提取、节点五态推导算法。
- `gate-rollback`: reset closure 计算（起点 ∪ gate 自身 的传递后继）、回退执行（归档移动 + `_meta.yaml` 写入 + 空目录清理）、回退次数持久化统计（`max_retries`/`exhausted`）、`priorAttempts` 构造。
- `change-memory`: `state.md` 的创建、读取与在 `instructions` 响应中的注入；明确不参与节点完成度判定，仅提供跨轮上下文。
- `loopspec-cli`: 完整 CLI 命令集（`init`/`schemas`/`new`/`status`/`instructions`/`rollback`/`history`/`archive`/`bulk-archive`/`version`）及其 `--json` 输出契约、`nextSteps` 生成策略（`exhausted`/`failed` 优先于 `ready`）、统一错误码。
- `change-archiving`: 单个/批量 change 归档，默认直接执行（可选 `--dry-run` 预览），仅允许移动（不删除），对未完成或待回退 change 的安全拦截规则。

### Modified Capabilities
- (none — 全新项目，无既有 spec 需要修改)

## Impact

- 新建 Python 包 `loopspec`（包名与 CLI 入口一致），依赖 `pydantic>=2`、`pyyaml`、`typer`、`rich`（可选）、`pytest`（测试）。
- 新建内置 schema 目录 `schemas/secure-spec-driven/`（`schema.yaml` + `templates/` + `instructions/`），随 `loopspec init` 复制到用户 workflow home；其中 `proposal`/`specs`/`design`/`tasks` 四项模板与指令内容移植自 OpenSpec 仓库 `schemas/spec-driven/`，仅 `security` 门禁部分为新增。
- 新建 `Makefile`（`install`/`dev`/`test`/`build`/`lint`/`clean`）作为统一任务入口。
- 用户侧新增目录结构：`<workflow_home>/{config.yaml, schemas/, changes/}`，每个 change 下新增 `.workflow.yaml`、`state.md`、`.attempts/round-NNN/`。
- 不影响任何现有代码路径（当前仓库为空骨架项目），无破坏性变更。
