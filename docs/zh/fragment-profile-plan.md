# Fragment、Profile 与 Plan

> 覆盖范围：Fragment、Profile、Plan 三者分别是什么、解决什么问题、如何协作，以及修改时会影响什么。
> 适用读者：第一次接触 LoopSpec 的人、工作流作者与负责规划的 Agent；字段细节见工作流组合与 Plan 参考。
> 语言：**中文** · [English](../en/fragment-profile-plan.md)

## 一句话区分

- **Fragment 是零件**：一组可复用的步骤（节点），自带指令、模板与 Gate 规则，例如"后端测试"或"安全审查"。
- **Profile 是装配图**：把若干 Fragment 按依赖排成 `flow` 的模板，例如 `bugfix`、`large-feature`，供规划时参考或照抄。
- **Plan 是这一次的施工单**：某个 Change 为完整任务确定的执行图，经人确认后冻结，CLI 只按它执行。

Fragment 与 Profile 属于项目（放在工作区，可被多个 Change 共用）；Plan 属于某个 Change（放在 Change 目录下，只服务这一项工作）。

## 对比

| 维度 | Fragment | Profile | Plan |
| --- | --- | --- | --- |
| 解决的问题 | 一类工作"怎么做、怎么验收"，只写一次到处复用 | 一类任务通常由哪些 Fragment、按什么顺序组成 | 这一项工作具体执行哪些节点、按什么顺序、失败退回哪里 |
| 文件位置 | `fragments/<name>/fragment.yaml` 及同目录资源 | `profiles/<name>.yaml` | `changes/<change>/plans/<NNN>/plan.yaml` |
| 主要内容 | `nodes`：产物节点、Gate 节点、对其他 Fragment 的 `use` 引用 | `flow`：Fragment 实例、`requires`、`on_fail`，以及给规划者的 `guidance` | `meta`（状态、修订号、摘要）与 `spec`（请求的 `flow` + 编译展开后的叶子 `nodes`） |
| 由谁编写 | 工作流作者；或经 `registry update` 从团队仓库同步 | 工作流作者；或经 registry 同步 | Agent 写请求，`plan create` 编译生成；人确认后由 CLI 维护 |
| 是否直接执行 | 否，只有被实例化进 Plan 后才执行 | 否，只是模板，可采用、调整或不用 | 是，CLI 只按已确认 Plan 的 `spec.nodes` 推进 |
| 是否需要人确认 | 否（作为项目代码评审） | 否（作为项目代码评审） | 是：草稿必须经人确认后 `plan approve`；修订与替换同样需要 |
| 生命周期 | 长期存在，随项目演进 | 长期存在，随项目演进 | draft → approved → archived；同一 Change 同时最多一份未结束 Plan |
| 粒度 | 一个能力单元（如一次测试 Gate） | 一种任务形态（如缺陷修复） | 一个具体任务的完整执行图 |
| 常用命令 | `fragment list / show / validate` | `profile list / show / validate / save` | `plan validate / create / show / approve / archive / rollback` |

## 三者如何协作

```text
fragments/                 profiles/                 changes/<change>/plans/
  requirements/  ─┐          bugfix.yaml  ── based_on ──┐
  backend-code/   │ use        large-feature.yaml         │
  backend-tests/  ├────────►   (flow 模板)                ▼
  security-review/│                                 request.yaml（Agent 为完整任务编写的 flow）
  ...            ─┘                                       │ plan create：按当前 Fragment 编译、展开
                                                          ▼
                                                    001/plan.yaml（草稿 → 人确认 → approved）
                                                          │ CLI 只按 spec.nodes 执行
                                                          ▼
                                                    artifacts/、.gates/、.attempts/
```

1. **挑选模板**：Agent 用 `profile list`、`profile show` 找到贴近任务的 Profile，例如缺陷修复用 `bugfix`。
2. **编写请求**：在 Change 的 `plans/` 下写一份覆盖完整任务的请求，`based_on` 记录参考了哪个 Profile，`flow` 可以照抄、增删实例或调整依赖。Profile 不会被自动合并，请求里写的 `flow` 就是全部。
3. **编译成草稿**：`plan create` 按当前 Fragment 定义把每个 `flow` 实例展开成叶子节点，把 `on_fail` 下放到每个 Gate，并计算 `digest`。
4. **人确认**：人看过 `plan show` 展示的范围、图、返工目标与 `digest` 后明确同意，Agent 才能 `plan approve`。确认时会重新编译，摘要不一致即拒绝。
5. **执行**：此后 CLI 只认这份 Plan 的 `spec.nodes`：依次给出节点指令、记录 Gate 证据、按 Gate 自己的 `on_fail` 返工，最后由保障节点检查完整 Diff。

## 一个例子：bugfix 如何变成 Plan

Profile `bugfix` 的 `flow` 只有 4 个实例：

```yaml
flow:
- {id: requirements, use: requirements}
- {id: be, use: backend-implementation, requires: [requirements]}
- {id: qa, use: qa-testing, requires: [be], on_fail: {reset: [be], max_retries: 3}}
- {id: assurance, use: change-assurance, requires: [qa]}
```

其中 `backend-implementation` 本身是一个引用其他 Fragment 的 Fragment（`backend-code`、`backend-tests`、`security-review`、`backend-pr-review`）。编译后，Plan 的 `spec.nodes` 是 7 个叶子节点，节点 id 以实例名为前缀：

```text
requirements/proposal → be/code/implement → be/tests/check → be/security/check
  → be/review/check → qa/test → assurance/check
```

`qa` 实例上的 `on_fail: {reset: [be]}` 被展开为 `qa/test` 这个 Gate 的返工目标：`be/code/implement` 与 `be` 内的三个 Gate。`backend-implementation` 内部为每个 Gate 声明的 `on_fail` 也一并下放，所以 `plan.yaml` 里每个 Gate 都带着自己明确的返工范围。

## 修改时会影响什么

| 你修改了 | 对已确认 Plan 的影响 | 对之后新建的 Plan 的影响 |
| --- | --- | --- |
| Fragment 的节点结构（增删节点、`requires`、`gate`、`on_fail`） | 不改变已确认 Plan 的图；但草稿在 `plan approve` 时重新编译，摘要变化会被拒绝（`plan_changed`），需重新 `plan create` 并再次确认 | 按新结构编译 |
| Fragment 的指令、模板 | 实时生效：节点执行时读取当前文件 | 同左 |
| 保障规则（`config.yaml` 指向的规则文件） | 实时生效：保障节点按当前规则判定（代码 Gate 审查的 `evidence.paths` 已写进 Plan，不随之变化） | 同左 |
| Profile | 无影响：Plan 不引用 Profile 的内容，`based_on` 只是记录 | 只影响之后参考它编写的请求 |
| Plan（任务范围变化） | 小调整用修订（带 `base_revision` 的请求，经人确认后 `plan approve -f`）；任务本身变了，经人同意 `plan archive` 后重新规划 | — |

## 什么时候改哪一个

- **团队对某类工作的做法变了**（例如测试要多跑一种检查、审查模板要加一项）：改 Fragment 的指令或模板。
- **某类任务的常见流程变了**（例如缺陷修复也要先写设计）：改或新增 Profile。
- **只是这一次任务需要不同的流程**：不必改 Profile，直接在这次的请求里调整 `flow`，按正常流程让人确认 Plan。
- **执行中发现计划不合适**：用修订或替换 Plan，不要手改 `plan.yaml`。

相关页面：字段与编写规则见 [工作流组合](workflow-composition.md)，`plan.yaml` 逐字段说明见 [Plan 参考](plan-reference.md)，术语见 [概览](overview.md)。
