# 概览

> 覆盖范围：LoopSpec 是什么、两套层级、推导状态、目录布局与术语表。
> 适用读者：人与 LLM Agent，第一篇。
> 语言：**中文** · [English](../en/overview.md)

## LoopSpec 是什么

LoopSpec 是让 LLM Agent 按人确认过的计划工作的命令行工具。它本身不生成任何内容，每次调用只回答一个问题：*按磁盘上的现状，已确认 Plan 的下一个节点是什么、用什么指令执行？* 写文档和代码是 Agent 的事；排序、Gate、返工记录与最终保障检查由 LoopSpec 负责。

它从结构上应对 Agent 交付的常见问题：

- **跳步。** 执行按已确认的依赖图进行；输入未完成的节点保持 `blocked`。
- **未经确认的计划。** 每份 Plan、每次修订、每次重新规划都只在提交人看到的摘要后生效。
- **未审查的代码。** 代码 Gate 记录绑定到被审查文件的证据；最终保障节点按 Change 固定基线检查完整 Git Diff。
- **被遗忘的反对意见。** 失败 Gate 的报告随返工归档，并作为 `priorAttempts` 交给重做的节点。
- **进度漂移。** 没有进度数据库：节点状态每次都由文件推导。

## 两套层级

**任务层级：Change、Plan、Revision。** *Change* 是一项工作（通常对应一个工单），随时间可以有多份 *Plan*，但同一时间最多一份未结束（draft 或 approved）。Plan 通过 *Revision* 原地调整；任务本身变化时，经人同意归档旧 Plan，从空状态起草新 Plan。

**工作流层级：Node、Fragment、Profile、Plan。** *Node* 是一个可执行步骤（产物或 Gate）。*Fragment* 是可复用的一组节点，可以引用其他 Fragment。*Profile* 是可复用的 Fragment 实例 `flow`，作为模板使用。*Plan* 是某个 Change 的具体执行图：`spec` 记录 Agent 写的 `flow` 与 CLI 实际执行的展开后叶子 `nodes`。

## 状态

Change 的状态由它的各份 Plan 推导，不存储：

| 状态 | 含义 | 下一步 |
| --- | --- | --- |
| `unplanned` | 没有未结束的 Plan。 | 用 `plan create` 起草 Plan。 |
| `planning` | 未结束的 Plan 是草稿。 | `plan show`，人确认，`plan approve`。 |
| `active` | 有未完成的已确认 Plan。 | 按 `nextSteps` 执行。 |
| `complete` | 活动 Plan 的全部节点（含保障）已完成。 | `change archive`。 |

活动 Plan 的每个叶子节点处于五种状态之一：

| 状态 | 含义 |
| --- | --- |
| `blocked` | 依赖的节点尚未 `done`。 |
| `ready` | 输入已完成，输出缺失或已过期。 |
| `done` | 产物存在，或 Gate 有带有效证据的 PASS。 |
| `failed` | 有效 FAIL，且该 Gate 的 `on_fail` 还有返工次数；执行 `plan rollback`。 |
| `exhausted` | 有效 FAIL，但没有 `on_fail` 或次数已用完；交给人决定。 |

Plan 自身的 `meta.status` 只记录人的决定：`draft`、`approved` 或 `archived`。未结束 Plan 是 draft 或 approved 的那份，活动 Plan 是 approved 的那份，都不另存指针。“已完成”从不落盘；完成后再修改代码，推导结果会自然回到未完成。

每条命令只有一次决定状态的写入。命令中途中断时，Change 要么保持命令之前的样子，要么已是命令之后的样子，不会处于中间状态，Agent 照常从 `change status` 继续即可。

## 目录布局

```text
<project root>/
  loopspec/                      # workflow home (default ./loopspec)
    config.yaml
    fragments/<name>/            # fragment.yaml plus its instructions and templates
    profiles/<name>.yaml
    changes/AFD1111/
      .workflow.yaml             # Change-level state (machine)
      state.md                   # Change-level notes (human)
      plans/
        request.yaml             # request files the agent writes
        001/
          plan.yaml              # meta + spec of one Plan
          state.md               # Plan-level notes (human)
          artifacts/             # this Plan's artifacts
          .gates/                # code Gate evidence and assurance diagnostics
          .gate-rounds/          # review round history
          .attempts/             # rework records (rollback and revision)
    archive/2026-10/AFD1111/     # archived Changes
```

代码 Gate 与保障检查的 Git Diff 只排除当前 Change 根下的 `.workflow.yaml`、`state.md` 与 `plans/`、`<home>/.cache/`，以及 `config.yaml` 的 `workflow.excluded_paths` 声明的路径。其他一切（包括 Fragment 与 Profile 文件）都算作改动。被 Git 忽略的文件不计入 Diff；未在 `excluded_paths` 中声明的会作为告警写进保障报告。Diff 比较的是固定基线与工作树中的交付内容：`git add` 与 `git commit` 不改变证据摘要，Gate 通过后可以先提交再归档。但交付前 HEAD 中每个文件的内容必须等于基线或工作区内容，否则保障判 FAIL（`diverged_commits`）。

## LoopSpec 不做什么

- 不调用 LLM，也不运行测试；只给出指令并记录结果。
- 从不移动、复制或删除业务代码。返工只归档 Plan 目录内的工作流文件。
- 本地记录不认证身份。摘要只能证明确认的内容就是展示的内容，不能证明是谁确认的。

## 术语表

| 术语 | 含义 |
| --- | --- |
| **工作区（workflow home）** | 存放 `config.yaml`、`fragments/`、`profiles/`、`changes/` 与 `archive/` 的目录，默认 `./loopspec`；每个命令都接受 `--home`。 |
| **Change（需求）** | 一项工作，位于 `<home>/changes/<name>/`。名称由字母、数字、`_` 与 `-` 组成，例如 `AFD1111`。 |
| **Plan（计划）** | Change 的一份编号计划，`plans/<NNN>/plan.yaml`。同一时间最多一份未结束。 |
| **活动 Plan** | 已确认的 Plan；执行类命令只作用于它。 |
| **修订（revision）** | 已确认 Plan 的 `spec` 的原地修改，凭摘要确认。 |
| **基线（baseline）** | 第一次 `plan create` 时固定的完整 Commit 哈希；Change 的所有 Plan 都以它计算 Diff。 |
| **Fragment** | 可复用的一组节点，位于 `fragments/<name>/fragment.yaml`。 |
| **Profile** | 可复用的 `flow` 模板，位于 `profiles/<name>.yaml`。 |
| **实例（instance）** | flow 中对某个 Fragment 的一次使用，以路径命名，例如 `be` 或 `be/tests`。 |
| **Gate** | 结果为 PASS 或 FAIL 报告而非产物的节点。 |
| **代码 Gate** | 带 `evidence` 的 Gate：只有对固定代码记录了审查轮次，结论才有效。 |
| **保障节点** | 带 `assurance` 的最终 Gate：由 CLI 按规则检查完整 Diff 并自行写出结论。 |
| **on_fail** | Gate 的返工策略：重置哪些叶子节点、最多几次。 |
| **重做记录** | `.attempts/<NNN>/record.yaml`，列出一次返工或修订归档的文件。 |
| **摘要（digest）** | Plan `spec` 的 SHA-256；确认绑定的就是它。 |
