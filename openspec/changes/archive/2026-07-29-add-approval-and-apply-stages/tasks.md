## 1. schema 节点新增 tracks 字段与校验（workflow-schema）

- [x] 1.1 在 `src/loopspec/models.py` 的 `NodeSpec` 上新增可选字段 `tracks: str | None = None`（保持 `extra: "forbid"`，不影响既有字段）
- [x] 1.2 在 `src/loopspec/schema_loader.py` 中新增 `_validate_tracks(node, nodes, graph)`：校验 `tracks` 为安全相对路径（复用 `_is_safe_relative_path`）、非 glob（复用 `outputs.is_glob`）、等于某个节点的 `generates`、且该节点是本节点的祖先（复用 `graph.ancestors`）；失败抛 `SchemaValidationError` 并带可执行的 `fix`
- [x] 1.3 在 `load_schema()` 的节点校验循环中接入 `_validate_tracks`（放在 graph 构建之后，因为需要 `ancestors`）
- [x] 1.4 在 `tests/test_schema_loader.py` 补测试：`tracks` 指向祖先节点产物加载通过；`tracks` 为 glob / 绝对路径 / 含 `..` / 不对应任何 `generates` / 指向非祖先节点分别报 `schema_invalid`；未声明 `tracks` 的 schema 加载结果不变

## 2. checkbox 任务进度解析（artifact-state）

- [x] 2.1 新增 `src/loopspec/task_tracking.py`：定义 `TaskItem`（`id`/`description`/`done`）与 `TaskProgress`（`path`/`resolved_path`/`total`/`complete`/`remaining`/`tasks`）
- [x] 2.2 实现 `parse_tasks(text: str) -> list[TaskItem]`：识别 `^[-*]\s*\[( |x|X)\]\s*(.+)$`，按出现顺序从 1 编号，`description` 去掉 checkbox 标记与首尾空白；非 checkbox 行忽略
- [x] 2.3 实现 `read_task_progress(artifact_dir: Path, tracks: str) -> TaskProgress`：文件不存在或读取失败时返回空 `tasks` + 全 0 进度，不抛异常
- [x] 2.4 实现 `tracked_work_complete(progress) -> bool`：`total > 0 and remaining == 0`
- [x] 2.5 新增 `tests/test_task_tracking.py`：混合勾选状态计数正确、`- [X]` 大写视为完成、`*` 前缀同样识别、分组标题/普通段落/无 checkbox 的 `- 列表项` 不计入、文件缺失返回全 0 且不抛异常、任务编号与顺序正确

## 3. tracks 完成性硬约束（artifact-state）

- [x] 3.1 在 `src/loopspec/state.py` 的 `compute_states()` 第一趟中接入约束：普通节点产物存在、或 gate 判定 PASS 之后，若 `node.tracks` 非空则额外要求 `tracked_work_complete(read_task_progress(artifact_dir, node.tracks))`，否则不加入 `completed`
- [x] 3.2 确认 gate FAIL 分支不受影响：fail 产物存在时仍按 `rollbacks_used` 推导 `failed`/`exhausted`，与被追踪任务进度无关
- [x] 3.3 在 `tests/test_state.py` 补测试：pass 产物存在但仍有未勾选任务 → `ready` 且 `is_complete()` 为 `False`；全部勾选 → `done`；被追踪文件无任何 checkbox → 不 `done`；被追踪文件缺失 → 不 `done`；fail 产物存在时无论进度如何都是 `failed`/`exhausted`；未声明 `tracks` 的节点判定与改动前一致

## 4. instructions 新增 contextFiles 与 taskProgress（loopspec-cli）

- [x] 4.1 在 `src/loopspec/instructions.py` 中构造 `contextFiles`：遍历 `loaded.graph.node_ids()`，对每个节点用 `node_output_patterns` + `resolve_outputs` 收集现存产物绝对路径，省略空列表的节点
- [x] 4.2 在同一响应中，当 `node.tracks` 非空时加入 `taskProgress`（含逐条 `tasks` 数组）；被追踪文件不存在时进度全 0、`tasks` 为空，并往 `warnings` 追加一条说明该文件缺失的告警
- [x] 4.3 未声明 `tracks` 的节点响应中不出现 `taskProgress` 键
- [x] 4.4 在 `tests/test_instructions.py` 补测试：`contextFiles` 覆盖 glob 节点的多个文件与 gate 的现存产物、省略无产物节点；`taskProgress.tasks` 逐条正确且与 `total`/`complete`/`remaining` 一致；被追踪文件缺失时降级为告警且命令成功返回；未声明 `tracks` 时无该字段

## 5. status 节点条目新增 taskProgress 摘要（loopspec-cli）

- [x] 5.1 在 `src/loopspec/cli.py` 的 `_node_output_summary`（或 `status` 的节点循环）中，为声明了 `tracks` 的节点附加 `taskProgress` 摘要：`path`/`resolvedPath`/`total`/`complete`/`remaining`，不含逐条任务列表
- [x] 5.2 在 `tests/test_cli.py` 补测试：声明 `tracks` 的节点条目含进度摘要且数值正确、不含 `tasks` 列表；未声明 `tracks` 的节点条目无 `taskProgress` 键

## 6. 内置 schema 新增 approval 人类审批门禁（builtin-schema）

- [x] 6.1 在 `schemas/secure-spec-driven/schema.yaml` 新增 `approval` gate 节点：`requires: [security]`、`generates: null`、`template: null`、`instruction: {file: approval.md}`、`gate.outputs.pass: approval/approved.md`、`gate.outputs.fail: approval/changes-requested.md`、`gate.templates.pass: approval-approved.md`、`gate.templates.fail: approval-changes-requested.md`、`on_fail: {reset: [specs, design], max_retries: 5, on_exhausted: escalate}`
- [x] 6.2 新增 `schemas/secure-spec-driven/instructions/approval.md`：要求先读齐 `contextFiles` 中全部上游产物并汇总成人类可读摘要（要解决什么 / 新增修改哪些能力 / 关键决策与取舍 / 任务规模与顺序 / 安全结论与遗留风险）；再通过宿主工具的交互提问能力（例如 Claude Code 的 `AskUserQuestion`）请人类在"按此计划执行"与"需要调整"之间明确表态；只能二选一写入；写 FAIL 时把人类的每项意见写成一条自包含、可执行的阻断条目
- [x] 6.3 在同一指令中写明红线：拿不到真人回答（无交互提问能力、非交互式运行、人类未回答）时，两个产物都不写，停在该节点等待人类，**严禁自行签核 PASS**；并说明 FAIL 会回退重做 `specs`/`design`/`tasks` 并把人类意见带给重做节点
- [x] 6.4 在同一指令中写明 `state.md` 回写要求（对应 `change-memory` 与 `builtin-schema` 的留痕需求）：写出判定产物**之后**，把判定追加到 `state.md`——`Decision Log` 记一条"第 N 轮 / 认可或要求调整 / **提炼后的判定要点** / 产物路径"（N = `priorAttempts` 中属于本 gate 的条目数 + 1）；认可时把已签核要点追加到 `Frozen Decisions` 并注明后续不得擅自变更；要求调整时把否决的做法追加到 `Rejected Options`、未定论问题追加到 `Open Questions`、`Current Focus` 改写为"按人类第 N 轮意见重做 specs/design"；`Artifact Notes` 记产物路径与结论；一律追加不得删改历史条目；`warnings` 含 `state_missing` 时先按标准小节重建 `state.md` 再追加
- [x] 6.5 在同一指令中写明两条载体分工与改写规则：（a）人类**原话摘录只写进 pass/fail 产物**，`state.md` 只写提炼结果 + 指向该产物的路径，不搬运原话；（b）写入 `state.md` 的每条记录必须**去指代、自包含**——把原话里的"这个/那个/它/上面说的/刚才那条/这里"全部替换为具体所指（能力名、文件路径、任务编号、需求名、决策编号），并在指令里给出正反例（反例：`- 这个先不做，那个要补测试`；正例：`- 暂不实现 <能力名>（原任务 3.2）；为 <模块路径> 补测试`）；提炼时必须保住人类意见里的限定与例外条件
- [x] 6.6 新增 `schemas/secure-spec-driven/templates/approval-approved.md`：一级标题（供 `summary` 提取）+ 「已汇报给人类的摘要要点」「人类的确认原话摘录」「人类提出的非阻断建议（如有）」「state.md 回写记录」小节
- [x] 6.7 新增 `schemas/secure-spec-driven/templates/approval-changes-requested.md`：一级标题 + 「需要调整的事项」无序列表小节（供 `extract_failure_notes` 提取 `blockingIssues`，一条意见一个 bullet，去指代后的具体表述）+ 「人类原话摘录」「建议的调整方向」「state.md 回写记录」小节
- [x] 6.8 在 `tests/test_builtin_schema.py`（见 7.7）中加断言：`instructions/approval.md` 文案覆盖四件事——通过宿主工具提问能力向人类确认、禁止自行签核 PASS、判定后回写 `state.md` 的各小节（`Decision Log`/`Frozen Decisions`/`Rejected Options`/`Open Questions`/`Current Focus`/`Artifact Notes`）、原话归产物且 `state.md` 条目必须去指代自包含；两份 approval 模板均含「人类原话摘录」与「state.md 回写记录」小节，且 fail 模板含可被 `extract_failure_notes` 提取的无序列表小节

## 7. 内置 schema 新增 apply 实现门禁（builtin-schema）

- [x] 7.1 在 `schemas/secure-spec-driven/schema.yaml` 新增 `apply` gate 节点：`requires: [approval]`、`generates: null`、`template: null`、`tracks: tasks.md`、`instruction: {file: apply.md}`、`gate.outputs.pass: apply/report.md`、`gate.outputs.fail: apply/blocked.md`、`gate.templates.pass: apply-report.md`、`gate.templates.fail: apply-blocked.md`、`on_fail: {reset: [design], max_retries: 2, on_exhausted: escalate}`
- [x] 7.2 新增 `schemas/secure-spec-driven/instructions/apply.md`，按 `.claude/skills/openspec-apply-change` 的循环编写：读齐 `contextFiles` 全部产物 → 依 `taskProgress` 找出未勾选任务 → 按声明顺序逐条实现（每条只做最小改动）→ 每完成一条立刻把 `- [ ]` 改成 `- [x]`（不攒到最后）→ 按项目约定运行测试/校验并如实记录结果 → 全部勾选后写 `apply/report.md`
- [x] 7.3 在同一指令中写明：任务本身不清楚、发现设计有硬伤或需求矛盾时，写 `apply/blocked.md` 而不是硬凑实现；FAIL 产物必须记录此前已经落到代码库里的改动，因为回退只归档 change 目录内的产物、不会撤销任何代码改动；并说明只有 `tasks.md` 全部勾选后该节点才会判定为 `done`
- [x] 7.4 新增 `schemas/secure-spec-driven/templates/apply-report.md`：一级标题 + 「已实现的任务」「改动的文件」「测试/校验实际结果」「与设计的偏离及原因」小节
- [x] 7.5 新增 `schemas/secure-spec-driven/templates/apply-blocked.md`：一级标题 + 「阻断问题」无序列表小节（一条一个 bullet）+ 「已落地的代码改动」「已完成到第几条任务」「建议的调整方向」小节
- [x] 7.6 执行 `loopspec schemas validate secure-spec-driven --home <临时 home> --json` 确认 `valid: true` 且 `buildOrder` 为 7 个节点、`approval` 在 `security` 之后、`apply` 在 `approval` 之后
- [x] 7.7 在 `tests/test_cli.py`（或新增 `tests/test_builtin_schema.py`）加一条针对内置 schema 的结构断言测试：节点集合、依赖关系、两个新 gate 的 pass/fail 路径、`apply.tracks == "tasks.md"`、两个 `on_fail` 配置与内置指令/模板文件均存在

## 8. loopspec-continue skill 正文补充（lpsx-skills）

- [x] 8.1 修改 `src/loopspec/skill_templates.py` 的 `_CONTINUE_BODY`：把"写产物到 `resolvedOutputPath`"扩写为"按返回的 `instruction` 行事——可能是写产物文件，可能需要先用你的提问能力向人类确认再二选一写入，也可能需要直接改动代码库并更新被追踪的任务清单"，保持 schema 无关、不出现 `approval`/`apply` 节点名
- [x] 8.2 在 `tests/test_skill_templates.py` 补测试：`continue` 正文包含人类确认与代码改动两类动作的说明，且不含 `approval`/`apply` 字样；4 个模板与命名转换等既有断言保持通过

## 9. 文档同步

- [x] 9.1 更新 `README.md` 结尾对内置 schema 节点图的描述：`proposal` → `{specs, design}` → `tasks` → `security` gate → `approval` gate（人类审批）→ `apply` gate（实现，`tracks: tasks.md`）
- [x] 9.2 在 `README.md` 的 Quick start 之后补一小段说明：`approval` 需要 Agent 用宿主工具的提问能力向人类确认，`apply` 会真正改动代码并要求 `tasks.md` 全部勾选后才判定完成

## 10. 全量验证

- [x] 10.1 运行 `make test`，全部测试通过（含本次新增的 schema/state/instructions/cli/skill/task-tracking 测试）
- [x] 10.2 运行 `make lint`（`ruff check src tests` + `mypy src`）无告警
- [x] 10.3 运行 `make build` 确认 wheel 打包包含新增的 `instructions/approval.md`、`instructions/apply.md` 与 4 份新模板（解包 `dist/*.whl` 中的 `loopspec/builtin_schemas/secure-spec-driven/` 核对）
- [x] 10.4 端到端演练（在临时目录，不污染仓库）：`loopspec init` → `new` → 依次伪造 proposal/specs/design/tasks/security-pass 产物 → 确认 `approval` 为 `ready` 且 `apply` 为 `blocked` → 写 `approval/approved.md` → 确认 `apply` 为 `ready` 且其 `taskProgress` 反映 `tasks.md` 的勾选情况 → 只写 `apply/report.md`（任务未全勾）确认 `apply` 仍为 `ready`、`isComplete` 为 `false`、`archive` 被拒 → 勾完全部任务后确认 `isComplete` 为 `true`
- [x] 10.5 端到端回退演练：写 `approval/changes-requested.md` → `loopspec status` 的 `pendingRollback` 指向 `approval` → `loopspec rollback` 后确认 reset 闭环为 `specs`/`design`/`tasks`/`security`/`approval`/`apply` 且 `proposal.md` 未被归档 → 对 `specs` 调 `instructions` 确认 `priorAttempts` 含人类意见；同样演练 `apply/blocked.md` 的回退闭环为 `design`/`tasks`/`security`/`approval`/`apply`
- [x] 10.6 核对 `state.md` 留痕：回退后确认 `state.md` 仍在 change 根目录（未被归档进 `.attempts/`），且手工按 6.4/6.5 的格式追加一轮记录后再走第二轮 `approval` 时，第一轮记录仍完整保留、第二轮以轮次 2 追加在其后；确认原话只出现在 approval 产物中而 `state.md` 只有提炼要点 + 产物路径、且条目内无未解析的指代词；确认 `state.md` 中写有"人类已认可"但 pass 产物不存在时，`status` 仍把 `approval` 判为 `ready`
