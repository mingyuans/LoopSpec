## 背景

Plan 是 DAG，`flow` 已能表达扇出 / 扇入：例如 PRD 生成后，fe / be / qa 三个评审节点都只依赖 PRD，综合 Gate 依赖三者。`workflow_runtime.status()` 也会把依赖已满足的叶子全部标为 `ready`。

但对外的“下一步”只给一个：

- `workflow_runtime.status()` 用 `next(...)` 只取第一个 ready 叶子生成 `nextSteps`；
- `workflow_changes.next_step()`（`loopspec change next`）只返回单个 `node`；
- `change status` 文本报告的 NODES 提示 “act on the one named in NEXT STEPS”，NEXT STEPS 提示 “Run these in order; the first one is enough”；
- `loopspec-continue` skill 只描述串行推进。

结果是调用方（LLM）只会逐个串行执行本可并行的节点，无法实现“多个 sub agent 并行评审，再由一个 Gate 汇总”的流程。

## 用户场景

- 编排者（主 LLM）运行 `loopspec change status <change>`，看到 fe-review / be-review / qa-review 三个叶子同时 ready，并被明确告知它们彼此独立、可以并行；于是为每个叶子各派一个 sub agent 执行，全部结束后重新读 status，再推进综合 Gate。
- 综合 Gate FAIL 时，按其 `on_fail` 执行 rollback，重置 PRD 及三份评审，重新进入并行评审。
- 现有只读取 `nextSteps[0]` 或串行执行 `nextSteps` 的调用方行为不被破坏。

## 范围

1. **引擎（`workflow_runtime.status`）**：无待执行 rollback 且无 exhausted Gate 时，`nextSteps` 按节点依赖顺序列出**全部** ready 叶子的 `loopspec node instructions -c <change> -n <node>` 命令（仍为字符串列表）。新增布尔字段 `parallel`：当且仅当 `nextSteps` 中有 ≥2 条节点命令时为 `true`，否则 `false`。rollback / exhausted / complete / unplanned / planning 等分支 `parallel` 均为 `false`。
2. **`change status --json` 与 `change next`**：透出 `parallel`；`change next` 在保留单个 `node` 字段的同时新增 `nodes`，列出 `nextSteps` 对应的全部节点（rollback 时为该 Gate，exhausted 时为 exhausted 节点）。
3. **文本报告（`status_report`）**：
   - `parallel` 为 true 时，NEXT STEPS 提示改为说明这些步骤互相独立、可以并行执行（例如每个步骤派一个 sub agent），并在所有步骤结束后重新读取 status；
   - NODES 提示语从“只执行 NEXT STEPS 中的那一个”改为“只执行 NEXT STEPS 中列出的节点”；
   - 单步时保持原语义。
4. **Skill**：`builtin/skills/continue.md`（以及由其生成 / 同步的 `.claude/skills/loopspec-continue`、`.codex` 等副本，若由 `skill_templates` 生成则改模板）补充并行规则：`parallel` 为 true 时为每条命令派一个 sub agent，每个 sub agent 只负责一个叶子、不推进其他节点；写命令遇到 `concurrent_write` 时稍后重试同一命令；全部完成后由编排者重新读 status。
5. **文档**：在 docs 中给出“PRD → fe/be/qa 并行评审 → 综合 Gate（`on_fail` 回退 PRD）”的 request 示例，说明扇出 / 扇入如何对应并行 nextSteps。

## 非目标

- 不把 `nextSteps` 改为结构化对象或分组。
- 不改变写锁语义（仍 `LOCK_NB` 快速失败报 `concurrent_write`）。
- 不新增 PRD 评审相关 Fragment / Profile（属于 registry 仓库）。
- 不改变 rollback 优先级：存在 `pendingRollback` 时 `nextSteps` 仍只有 rollback 命令；存在 exhausted Gate 时仍为空。
- 不改变节点 ready / blocked 的判定逻辑、Gate 协议与证据校验。

## 验收条件

- [ ] 扇出 Plan（A → B、C、D 并行 → Gate E）在 A done 后：`change status --json` 的 `nextSteps` 恰好为 B、C、D 三条 `node instructions` 命令（依赖顺序），`parallel` 为 `true`。
- [ ] 线性 Plan 中只有一个 ready 叶子时：`nextSteps` 只有一条命令，`parallel` 为 `false`（与现状输出一致，仅新增字段）。
- [ ] 并行分支中 B 已 done、C/D 仍 ready 时：`nextSteps` 只含 C、D，`parallel` 为 `true`；只剩一个时 `parallel` 为 `false`。
- [ ] 存在 `pendingRollback` 时：`nextSteps` 只有 `loopspec plan rollback ...`，`parallel` 为 `false`，即使其他分支仍有 ready 叶子。
- [ ] 存在 exhausted Gate 时：`nextSteps` 为空，`parallel` 为 `false`。
- [ ] 文本报告：`parallel` 为 true 时 NEXT STEPS 段出现并行执行提示并列出全部命令；单步时提示与现状一致；NODES 提示语不再要求“只执行一个”。
- [ ] `loopspec change next` 输出包含 `nodes` 数组，并行时含全部 ready 节点；原 `node` 字段保持不变。
- [ ] 并行 sub agent 分别对 B、C、D 执行 `node instructions` 与写产物不互相影响；综合 Gate E 在 B、C、D 全部完成前保持 blocked。
- [ ] continue skill 源文件与生成副本包含并行派发与 `concurrent_write` 重试说明，`tests/test_skill_templates.py` 等相关测试通过。
- [ ] 全量 `make test` 通过。

## 风险

- **兼容性**：`nextSteps` 由单条变为多条。按原提示“first one is enough”串行执行的调用方仍能正确推进；新增字段对 JSON 消费方为纯增量。
- **并发写冲突**：多个 sub agent 同时执行 `gate begin/record`、`plan rollback` 等写命令会触发 `concurrent_write`。写锁保持快速失败，依赖 skill 指引重试；命令为单次原子写，失败不留半成品。
- **共享工作区的代码证据**：并行的 code-evidence Gate 都基于同一工作区 Diff；若一个分支在另一个分支评审期间修改代码，后者的 round 会失效，需要重新 begin（现有机制已覆盖，skill 中提示）。
- **sub agent 越权推进**：sub agent 可能顺手执行其他节点。skill 明确每个 sub agent 只处理分配给它的叶子，汇合与后续推进由编排者负责。
- **安全**：不新增外部输入路径；节点 id 来自已校验的 Plan，文本报告继续经 `sanitize` 输出。
