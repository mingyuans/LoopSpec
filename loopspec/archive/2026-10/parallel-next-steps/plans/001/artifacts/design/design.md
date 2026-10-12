## 背景与现状

- `src/loopspec/workflow_runtime.py` `status()`：遍历 `loaded.spec.nodes`（编译期已按依赖排序）为每个叶子算出 `status`；结尾 `ready = next(...)` 只取第一个 ready 叶子生成 `nextSteps`。rollback 优先、exhausted 时为空。
- `src/loopspec/workflow_changes.py` `status()`：active 时透传 runtime 的 `nextSteps`；complete 时改为 `change archive`。`next_step()`（`loopspec change next`）返回单个 `node`。
- `src/loopspec/status_report.py`：`TOP_KEYS` / `OMITTED_TOP_KEYS` 约束 payload 每个顶层字段必须被渲染或显式忽略；`PROMPT_NODES` 写着 “act on the one named in NEXT STEPS”，`PROMPT_NEXT_STEPS` 写着 “Run these in order; the first one is enough”。
- `builtin/skills/continue.md` 是 continue skill 的唯一来源，`loopspec init` 生成 `.claude/skills/loopspec-continue/SKILL.md`、`.codex/skills/...` 等副本（本仓库内副本与源文件逐字相同）。
- `src/loopspec/workflow_io.py` `write_lock`：`LOCK_NB`，并发写报 `concurrent_write`（本次不改）。
- 文档：`docs/{en,zh}/agent-protocol.md` 写 “run the single command in nextSteps”；`docs/{en,zh}/cli-reference.md` 写 `nextSteps` 给出“唯一下一条命令”；`docs/{en,zh}/workflow-composition.md` 介绍 Plan 请求。

## 目标 / 非目标

**目标：**
- `nextSteps` 列出全部 ready 叶子，新增 `parallel` 布尔字段。
- `change next` 新增 `nodes`。
- 文本报告与 continue skill 支持并行派发语义。
- 文档同步，并给出扇出 / 扇入评审示例。

**非目标：**
- `nextSteps` 结构不变（仍为字符串列表）；写锁不变；不新增 Fragment / Profile；rollback / exhausted 优先级不变；ready 判定不变。

## 方案

### 1. runtime（`workflow_runtime.status`）

```python
if rollback:
    next_steps = [f"loopspec plan rollback -c {name} -p {plan}"]
elif any(entry["status"] == "exhausted" for entry in entries.values()):
    next_steps = []
else:
    ready = [key for key, item in entries.items() if item["status"] == "ready"]
    next_steps = [f"loopspec node instructions -c {name} -n {key}" for key in ready]
...
"nextSteps": next_steps,
"parallel": not rollback and len(next_steps) > 1,
```

`entries` 按 `spec.nodes` 的依赖顺序插入，因此列表顺序稳定、与 NODES 段一致。`parallel` 只在 ≥2 条节点命令时为 true。

说明：同时 ready 的叶子之间不存在依赖（否则其中一个必为 blocked），因此可安全并行。

### 2. change 层（`workflow_changes`）

- `status()`：unplanned / planning 分支补 `"parallel": False`；active 透传 runtime 的 `parallel`；complete 时 `nextSteps` 为 archive，`parallel` 置 `False`。
- `next_step()`：
  ```python
  targets = [rollback gate] if pendingRollback else [ready 节点...] or [exhausted 节点...]
  return {..., "node": targets[0] if targets else None, "nodes": targets,
          "parallel": report["parallel"], "nextSteps": report["nextSteps"]}
  ```
  `node` 语义保持不变（rollback Gate → 第一个 ready/exhausted），`nodes` 为 rollback 时 `[gate]`；否则全部 ready 节点；无 ready 时为全部 exhausted 节点。

### 3. 文本报告（`status_report`）

- `TOP_KEYS` 加入 `parallel`（由 NEXT STEPS 段渲染，不列入 OMITTED）。
- `PROMPT_NODES` 末句改为 “Do not pick nodes yourself -- act only on the nodes named in NEXT STEPS.”
- 新增 `PROMPT_NEXT_STEPS_PARALLEL`：
  ```
  These steps are independent of each other: run them in parallel, for example
  one sub agent per step, each working only on its own node. A write command that
  fails with concurrent_write can simply be retried. When all of them have
  finished, read the status report again before doing anything else.
  ```
- `_next_steps` 选择提示：`isComplete` → COMPLETE；`parallel` → PARALLEL；否则原 `PROMPT_NEXT_STEPS`（单步语义不变，措辞保持现状以免影响现有用户）。

### 4. Skill（`builtin/skills/continue.md`）

在第 2 步之后补充一段（保持英文，与原文风格一致）：

> When `nextSteps` lists several `node instructions` commands (the report says they are independent, `parallel: true` in JSON), you may run them in parallel: give each to its own sub agent, which handles only that one node -- its instruction, artifact, and Gate protocol -- and never advances other nodes or runs rollback. If a write command fails with `concurrent_write`, retry the same command shortly. Wait for every sub agent to finish, then re-read status yourself; rollbacks, revisions, and human decisions stay with you.

然后用 `loopspec init`（或等效复制）重新生成 `.claude/skills/loopspec-continue/SKILL.md` 与 `.codex/skills/loopspec-continue/SKILL.md`，保证与源文件一致。

### 5. 文档

- `docs/{en,zh}/agent-protocol.md`：把 “run the single command in nextSteps” 改为“运行 nextSteps 中的命令；`parallel` 为 true 时可并行派发”，并新增一小节“并行步骤”。
- `docs/{en,zh}/cli-reference.md`：`change status --json` 增加 `parallel` 说明，`nextSteps` 改为“全部可执行的下一条命令”；`change next` 增加 `nodes`、`parallel`。
- `docs/{en,zh}/workflow-composition.md` Plan 请求一节：新增扇出 / 扇入示例：
  ```yaml
  flow:
  - {id: prd, use: requirements, requires: []}
  - {id: fe-review, use: <fe 评审 Fragment>, requires: [prd]}
  - {id: be-review, use: <be 评审 Fragment>, requires: [prd]}
  - {id: qa-review, use: <qa 评审 Fragment>, requires: [prd]}
  - id: review-gate
    use: <综合评审 Gate Fragment>
    requires: [fe-review, be-review, qa-review]
    on_fail: {reset: [prd], max_retries: 2}
  ```
  说明 prd 完成后三个评审叶子同时出现在 `nextSteps`、`parallel: true`；review-gate FAIL 时重置 prd 及其全部下游（含三份评审），再次并行评审。示例 Fragment 名用占位说明，不新增 Fragment。
- `docs/{en,zh}/release-notes.md`：追加条目。

## 归属与路径

全部为 BE / CLI：
- `src/loopspec/workflow_runtime.py`、`src/loopspec/workflow_changes.py`、`src/loopspec/status_report.py`
- `builtin/skills/continue.md`
- `tests/test_workflow_runtime.py`、`tests/test_workflow_cli.py`、`tests/test_status_report.py`、`tests/test_skill_templates.py`（如需）
- 文档 / `.claude/**` / `.codex/**` 在 `excluded_paths` 中，不进入保障 Diff。

以上路径均落在 `backend-tests` / `security-review` / `backend-pr-review` 的 `evidence.paths`（`src/**`、`tests/**`、`builtin/**`）内，无前端路径。

## 安全边界

- 无新增外部输入：节点 id 来自已校验的 Plan，命令字符串由引擎拼接；文本报告继续经 `sanitize` 输出。
- 不改写锁、证据与 Gate 协议；并行仅为调度提示，不放宽任何校验。
- skill 明确 sub agent 不得执行 rollback / 修订 / 归档或替人决策，避免并行带来的越权推进。

## 验证方案

单元 / 集成测试（pytest，`make test`）：
1. runtime：构造扇出 Plan（A → B、C、D → Gate E），A done 后 `nextSteps` == B、C、D 三条命令且 `parallel` 为 True；写入 B 产物后只剩 C、D；再写 C 只剩 D、`parallel` False；E 在 B/C/D 全部完成前 blocked。
2. runtime：线性 Plan `parallel` False 且 `nextSteps` 与旧行为一致。
3. runtime：扇出中某分支 Gate FAIL 且有重试 → `nextSteps` 只有 rollback、`parallel` False；无重试 → `nextSteps` 为空、`parallel` False。
4. change 层：unplanned / planning / complete 下 `parallel` 为 False；`change next` 返回 `nodes`（并行时 3 个、rollback 时为 Gate、exhausted 时为 exhausted 节点）且 `node` 不变。
5. status_report：`parallel` True 时含并行提示并列出全部步骤；单步时提示不变；`TOP_KEYS` 覆盖 `parallel`；NODES 提示新文案。
6. skill：`builtin/skills/continue.md` 含并行与 `concurrent_write` 说明；生成副本与源一致（现有 skill template 测试覆盖）。
7. 全量 `make test` 与 lint 通过。

## 风险与取舍

- **结构化分组 vs 字符串列表**：分组语义更强，但破坏现有契约；用户已确认采用字符串列表 + `parallel`。
- **写锁阻塞等待 vs 快速失败**：用户确认保持快速失败，由 skill 指引重试；代价是并行 sub agent 偶发需重试。
- **共享工作区证据**：并行 code-evidence Gate 均基于同一工作区 Diff，某分支改代码会让其他分支 round 失效需重新 begin；现有机制已检测，skill 中提示。
- **旧调用方**：按原 “first one is enough” 串行执行仍正确，只是不并行。
