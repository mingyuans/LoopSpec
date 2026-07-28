## 1. 项目脚手架

- [x] 1.1 初始化 `pyproject.toml`（包名 `loopspec`，CLI 入口 `loopspec`），声明依赖 `pydantic>=2`、`pyyaml`、`typer`、`rich`（可选）、`pytest`（dev）
- [x] 1.2 创建源码目录骨架 `src/loopspec/`（空的 `__init__.py` 及各模块占位文件）与 `tests/` 目录
- [x] 1.3 编写 `Makefile`：`install`（`uv sync`）、`dev`（`uv run loopspec --help`）、`test`（`uv run pytest -v`）、`lint`（`ruff check` + `mypy`）、`build`（`uv build`）、`clean`
- [x] 1.4 配置 `ruff`/`mypy` 基础规则（`pyproject.toml` 或独立配置文件），确保 `make lint` 可运行

## 2. Schema 定义与加载（workflow-schema）

- [x] 2.1 在 `models.py` 中实现 Pydantic 模型：`OnExhausted`、`OnFailSpec`、`GateOutputs`、`GateTemplates`、`GateSpec`、`InstructionRef`、`NodeSpec`、`WorkflowSchema`、`ConfigSchemaRef`、`SchemaSelectionSpec`、`WorkflowConfig`，全部 `extra: "forbid"`，`id`/`name` 字段用 kebab-case 正则约束
- [x] 2.2 在 `errors.py` 中定义异常类型（`SchemaValidationError`、`ConfigValidationError`、`TemplateLoadError`、`InstructionLoadError`、`GateOutputConflictError` 等）与错误码常量，统一映射到 `{error, message, fix}` 输出格式
- [x] 2.3 在 `schema_loader.py` 中实现结构校验（Pydantic）→ 语义校验（14 条规则，按文档顺序逐条实现：节点唯一性、requires 存在性、无环、普通节点 generates/template、gate outputs/templates 完整性与 glob 排除、on_fail.reset 存在性与祖先关系、模板/指令路径安全、保留路径排除）
- [x] 2.4 实现 `instruction` 字段的内联字符串与 `{file: ...}` 两种加载路径，展开为最终字符串，校验路径安全（禁止绝对路径、`..`、空路径段）
- [x] 2.5 编写 `tests/test_schema_loader.py`，覆盖 `workflow-schema` spec 中列出的全部场景（合法 schema、重复 ID、环检测、gate 校验、on_fail.reset 祖先校验、instruction 加载、路径安全、未知字段报错）

## 3. 依赖图算法（workflow-graph）

- [x] 3.1 在 `graph.py` 中实现 `WorkflowGraph` 类：从 `WorkflowSchema` 构建内部依赖表
- [x] 3.2 实现无环校验（DFS 三色标记），环路径以正确顺序回溯并抛出 `SchemaValidationError`
- [x] 3.3 实现 `build_order()`（Kahn 拓扑排序，同层按节点 ID 字典序）
- [x] 3.4 实现 `ancestors(node_id)` 与 `dependents(node_id)` 查询
- [x] 3.5 编写 `tests/test_graph.py`，覆盖线性链、菱形依赖、祖先/后继查询、空 requires 根节点等场景

## 4. 产物探测与 Gate 判定（artifact-state 基础）

- [x] 4.1 在 `outputs.py` 中实现 `is_glob`、`resolve_outputs`（非 glob 直接判定文件存在；glob 用 `Path.glob` 匹配并排序）、`outputs_exist`、`node_output_patterns`
- [x] 4.2 在 `resolve_outputs` 中统一过滤 `.attempts/` 目录下的文件与保留路径（`.workflow.yaml`、`state.md`），确保宽泛 glob 不会误判归档文件或 change 元数据为产物
- [x] 4.3 在 `gate_outcome.py` 中实现 `read_gate_outcome`（pass/fail 存在性判定，同时存在抛 `GateOutputConflictError`）与 `extract_failure_notes`（从 Markdown 提取一级标题作 summary、无序列表作 blockingIssues，提取失败不抛错）
- [x] 4.4 编写 `tests/test_outputs.py`（或归入 `test_state.py`）覆盖 glob 匹配、`.attempts` 排除、`state.md` 排除场景
- [x] 4.5 编写 `tests/test_gate_outcome.py`，覆盖 PASS/FAIL/None/冲突四种产物存在性组合与摘要提取的三种场景

## 5. 节点状态推导（artifact-state 核心）

- [x] 5.1 在 `state.py` 中定义 `NodeState` 数据结构（`id`/`status`/`missing_deps`/`verdict`/`rollbacks_used`/`max_retries`）
- [x] 5.2 实现 `count_rollbacks(change_dir, gate_id)`：扫描 `.attempts/round-*/_meta.yaml`，只统计存在且 `meta.gate == gate_id` 的 round
- [x] 5.3 实现 `compute_states(graph, change_dir, artifact_dir)` 两趟算法：第一趟确定 `completed` 集合（非 gate 产物存在 / gate PASS），第二趟按拓扑序推导 `blocked`/`ready`/`done`/`failed`/`exhausted` 五态
- [x] 5.4 确保多 gate 场景下各 gate 独立判定，互不影响；确保 gate 失败时下游节点自动因 `completed` 缺失而保持 `blocked`
- [x] 5.5 编写 `tests/test_state.py`，完整覆盖 `artifact-state` spec 中列出的全部场景（空 change、首节点完成、gate PASS/FAIL/exhausted、max_retries=0、重启后一致性、`.attempts` 不完整 round、state.md 矛盾场景、全部完成）

## 6. 门禁回退（gate-rollback）

- [x] 6.1 在 `rollback.py` 中实现 `compute_reset_closure(graph, gate_id)`：种子为 `on_fail.reset` ∪ gate 自身，计算全部传递后继，按拓扑序返回
- [x] 6.2 实现 `execute_rollback(...)`：按闭包移动产物到 `.attempts/round-NNN/`（保留相对路径结构）、`mkdir(exist_ok=False)` 防重复、归档后清理空目录（排除 `.attempts/`）、最后写入 `_meta.yaml`
- [x] 6.3 实现回退前置校验：无 `failed` gate 时报 `no_failed_gate`；目标 gate 已 `exhausted` 时报 `retries_exhausted`
- [x] 6.4 在 `attempts.py` 中实现 `priorAttempts` 构造：扫描 `_meta.yaml`，筛选 `archived_files` 命中当前节点产物路径的轮次，按 round 升序返回 `verdict`/`summary`/`blockingIssues`/`archivedPath`
- [x] 6.5 编写 `tests/test_rollback.py`，覆盖闭包计算（含 gate 自身、下游自动纳入）、归档执行（原路径消失、归档路径出现、连续两次回退编号递增、空目录清理、`state.md` 不归档）、前置校验失败场景、多 gate 场景下的隔离回退
- [x] 6.6 编写 `tests/test_attempts.py`（或归入 `test_instructions.py`）覆盖 `priorAttempts` 为空/单条/多条（按 round 排序）的场景

## 7. change 工作记忆（change-memory）

- [x] 7.1 在 `change_state.py` 中定义 `STATE_TEMPLATE`（含 Current Focus / Frozen Decisions / Decision Log / Rejected Options / Open Questions / Artifact Notes）
- [x] 7.2 实现 `create_initial_state(change_dir)` 与 `read_state_for_instruction(change_dir)`（缺失时返回 `None` 与 `state_missing` warning）
- [x] 7.3 编写 `tests/test_change_state.py`，覆盖初始创建内容完整性、正常读取、缺失降级、语义标签不解析、与产物矛盾时不影响状态判定

## 8. 指令生成与 nextSteps 策略

- [x] 8.1 在 `instructions.py` 中实现普通节点指令响应组装（`template`/`resolvedOutputPath`/`description`/`instruction`/`context`/`rules`/`dependencies`/`unlocks`/`state`/`statePath`/`warnings`/`priorAttempts`）
- [x] 8.2 实现 gate 节点指令响应组装（`templates.pass/fail`/`resolvedOutputPath.pass/fail`，指令文案要求二选一）
- [x] 8.3 实现 `config.yaml` 的 `context` 注入与按节点 ID 匹配的 `rules` 注入；`rules` 引用未知节点 ID 时输出告警但不中断
- [x] 8.4 在 `policy.py` 中实现 `build_next_steps(...)`：按拓扑序遍历，`exhausted` > `failed` > `ready` > 全部完成的优先级返回第一条命中分支
- [x] 8.5 编写 `tests/test_instructions.py`，覆盖普通/gate 节点结构、`instruction.file` 不暴露原始路径、context/rules 注入与告警、dependencies/unlocks 正确性、priorAttempts 注入
- [x] 8.6 编写 `tests/test_policy.py`，覆盖 `failed` 优先于 `ready`、多个 gate 同时失败时只返回拓扑序最早一个的场景

## 9. 路径解析与配置加载

- [x] 9.1 在 `paths.py` 中实现 workflow home / `artifacts_dir` / change 根目录 / artifact 根目录（含 schema 二级 `path`）的解析与路径安全校验（禁止绝对路径、`..`、空路径段，normalize 后必须仍在允许根目录内）
- [x] 9.2 在 `config.py` 中实现 `config.yaml` 加载（`WorkflowConfig` 模型校验，`schema`/`schemas` 互斥与兼容规则）与 `.workflow.yaml` 的读写
- [x] 9.3 实现 schema 解析顺序：已有 change 走"命令行 `--schema` → `.workflow.yaml.schema` → `config.yaml.schema` → 报错"；创建 change 走"命令行 `--schema` → 单候选默认值 → 多候选返回 `schema_selection_required` → 报错"
- [x] 9.4 编写 `tests/test_config.py`，覆盖单/多 schema 配置、`artifacts_dir` 默认值与自定义、`schemas[*].path` 解析、`schema`/`schemas` 一致性校验、路径遍历防护、候选名重复/无法加载等 `config_invalid` 场景

## 10. CLI 命令实现（loopspec-cli）

- [x] 10.1 在 `cli.py` 中搭建 Typer 应用骨架，所有子命令统一支持 `--json`，统一异常捕获并输出 `{error, message, fix}` + 退出码 1
- [x] 10.2 实现 `loopspec version [--json]`：从包元数据（`importlib.metadata.version("loopspec")`）读取版本号，人类可读模式打印字符串，`--json` 模式输出 `{"version": ...}`；不依赖 workflow home 是否已初始化
- [x] 10.3 实现 `loopspec init [path] [--no-builtin]`：生成 `config.yaml`/`schemas/`/`changes/`，默认复制内置 schema
- [x] 10.4 实现 `loopspec schemas list|show|validate`
- [x] 10.5 实现 `loopspec new <change-name> [--schema S]`：整合 2/9 节的加载与解析逻辑，处理多候选 schema 选择分支，写入 `.workflow.yaml` 与初始 `state.md`
- [x] 10.6 实现 `loopspec status <change-name>`：整合 5 节状态推导与 8 节 `nextSteps` 策略，输出完整节点数组、`pendingRollback`、`isComplete`
- [x] 10.7 实现 `loopspec instructions <node> --change <change>`：整合 8 节指令组装逻辑
- [x] 10.8 实现 `loopspec rollback <change-name>`：整合 6 节回退执行逻辑
- [x] 10.9 实现 `loopspec history <change-name>`：扫描 `.attempts/round-*/_meta.yaml` 按 round 升序输出
- [x] 10.10 编写 `tests/test_cli.py`（非归档部分），覆盖 `version`/`new`/`status`/`instructions`/`rollback`/`history` 的成功与全部错误路径（`invalid_change_name`/`change_exists`/`schema_selection_required`/`config_invalid` 等）

## 11. change 归档（change-archiving）

- [x] 11.1 在 `cli.py`（或独立 `archive.py`）中实现 `loopspec archive <change-name> [--dry-run] [--exhausted] [--include-pending-failures]`：默认直接执行移动，安全拦截未完成/exhausted/待回退 change，目标已存在时报 `archive_conflict`，`--dry-run` 时只预览不移动
- [x] 11.2 实现 `loopspec bulk-archive [--complete] [--exhausted] [--older-than DAYS] [--dry-run]`：候选过滤逻辑与批量移动，默认直接执行，`--dry-run` 时只预览不移动
- [x] 11.3 编写归档相关测试（`tests/test_cli.py` 内或独立 `test_archive.py`），覆盖默认直接执行、`--dry-run` 预览、安全拦截（`archive_unsafe`）、目标冲突（`archive_conflict`）、`--older-than` 过滤

## 12. 内置 schema 与端到端验证

- [x] 12.1 从 OpenSpec 仓库（`schemas/spec-driven/schema.yaml`）移植 `proposal`/`specs`/`design`/`tasks` 四个节点的 `generates`/`requires`/`instruction` 定义，改写为本方案的 `NodeSpec` 格式（`instruction` 从内联字符串拆分为 `instructions/*.md` 文件引用），写入 `schemas/secure-spec-driven/schema.yaml`
- [x] 12.2 从 OpenSpec 仓库（`schemas/spec-driven/templates/{proposal,spec,design,tasks}.md`）移植对应模板内容到 `schemas/secure-spec-driven/templates/`（`spec.md` 模板用于 `specs` 节点，其 `generates` 需保留为 glob `specs/**/*.md`）
- [x] 12.3 在 `schema.yaml` 中新增 `security` gate 节点：`requires: [tasks]`、`gate.outputs.pass: security/pass.md`、`gate.outputs.fail: security/fail.md`、`gate.templates.pass/fail`、`on_fail: {reset: [design], max_retries: 3, on_exhausted: escalate}`
- [x] 12.4 编写 `templates/security-pass.md`、`templates/security-fail.md` 与 `instructions/security.md`（新增内容，OpenSpec 无对应素材）
- [x] 12.5 编写端到端测试（`tests/test_cli.py` 内或独立文件），完整走通设计文档 10 章"端到端"用例：创建 change → 依次生成 proposal → specs/design（并行）→ tasks → 写 `security/fail.md` → status 显示 `pendingRollback` → rollback → design 变 `ready`、tasks/security 变 `blocked`（`specs` 因不在闭包内保持 `done`）→ `priorAttempts` 含 round 1 → 重写 design/tasks → 写 `security/pass.md` → `isComplete: true`
- [x] 12.6 运行 `loopspec schemas validate secure-spec-driven` 确认内置 schema（5 节点）通过全部 14 条语义校验

## 13. 收尾与文档

- [x] 13.1 补充 `README.md`：项目介绍、安装方式（`make install`）、快速开始（`loopspec init` → `new` → `status` → `instructions` 主循环示例）
- [x] 13.2 运行 `make lint` 与 `make test`，确保全部通过且无遗留 TODO
- [x] 13.3 检查 13 章"给实现者的三条提醒"对应的测试是否均已覆盖（保留路径排除、nextSteps 优先级顺序、priorAttempts 非空）
