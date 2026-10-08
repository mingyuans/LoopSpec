# 工作流组合

> 覆盖范围：编写 Fragment、Profile 与 Plan 请求；`on_fail` 如何到达 Gate；代码证据与保障。
> 适用读者：工作流作者与起草 Plan 的 Agent。
> 语言：**中文** · [English](../en/workflow-composition.md)

## 层级

| 层级 | 文件 | 作用 |
| --- | --- | --- |
| Node | `fragment.yaml` 内 | 一个步骤：产物（`generates`）或 Gate（`gate`），或用 `use` 引用另一个 Fragment。 |
| Fragment | `fragments/<name>/fragment.yaml` | 可复用、自包含的一组节点，带自己的指令与模板。 |
| Profile | `profiles/<name>.yaml` | 可复用的 Fragment 实例 `flow`；是模板，不强制使用。 |
| Plan | `changes/<change>/plans/<NNN>/plan.yaml` | 某个 Change 已确认的执行图，见 [Plan 参考](plan-reference.md)。 |

执行只按 Plan 的 `spec.nodes` 进行。修改 Fragment 或 Profile 定义不会改变已确认 Plan 的图；但指令、模板与保障规则在节点执行时实时读取。

## Fragment

Fragment 是一个目录：`fragment.yaml` 加上它引用的资源（`<node>.instruction.md`、`<node>.template.md`、`<node>.pass.md`、`<node>.fail.md`、规则文件）。资源路径相对该目录，不能越出。一个 `nodes` 列表同时容纳直接节点与 `use` 引用，没有单独的接口或包含列表。

<!-- loopspec:example=fragment -->
```yaml
version: 1
name: backend-implementation
description: 后端实现、测试、安全审查与代码审查
nodes:
- id: code
  use: backend-code
- id: tests
  use: backend-tests
  requires: [code]
  on_fail: {reset: [code], max_retries: 3}
- id: security
  use: security-review
  requires: [tests]
  on_fail: {reset: [code], max_retries: 3}
- id: review
  use: backend-pr-review
  requires: [security]
  on_fail: {reset: [code], max_retries: 3}
```

### Fragment 字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `version` | 整数 | 否 | `1` | 格式版本，只接受 `1`。 |
| `name` | kebab-case 字符串 | 是 | - | 必须与目录名一致。 |
| `description` | 字符串 | 否 | `""` | `fragment list` 显示。 |
| `nodes` | Node 列表 | 是 | - | 1 到 256 个节点，`id` 唯一。 |

### Node 字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | kebab-case 字符串 | 是 | - | 在 Fragment 内唯一。 |
| `description` | 字符串 | 否 | `""` | 说明文字。 |
| `use` | kebab-case 字符串 | 否 | - | 引用另一个 Fragment；与下列执行字段互斥。 |
| `requires` | 节点 id 列表 | 否 | `[]` | 必须先完成的兄弟节点。 |
| `generates` | 相对路径或通配 | `generates`/`gate` 二选一 | - | 产物路径，位于 `artifacts/<实例>/` 下。 |
| `instruction` | 相对路径 | 否 | - | 本 Fragment 目录内的指令文件。 |
| `template` | 相对路径 | 否 | - | 本 Fragment 目录内的产物模板。 |
| `tracks` | 相对路径 | 否 | - | 同一实例上游产出的清单；全部勾选后节点才算完成。 |
| `gate` | Gate | `generates`/`gate` 二选一 | - | 使节点成为 Gate。 |
| `on_fail` | FailurePolicy | 否 | - | 返工策略；写在引用节点上时作用于其内部每个 Gate。产物节点不能写。 |

### Gate 字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `outputs` | GateOutputs | 是 | - | PASS 与 FAIL 报告路径，不能相同。 |
| `templates` | GateTemplates | 否 | - | PASS 与 FAIL 报告模板。 |
| `evidence` | CodeEvidence | 否 | - | 使其成为代码 Gate，结论需要记录审查轮次。 |
| `assurance` | 相对路径 | 否 | - | 使其成为保障节点，指向规则文件；与 `evidence` 互斥。 |

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `pass` | 相对路径 | 是 | - | PASS 报告（在 `outputs` 中）或模板（在 `templates` 中）。 |
| `fail` | 相对路径 | 是 | - | FAIL 报告或模板。 |

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `provides` | kebab-case 名称列表 | 是 | - | PASS 证明的能力，例如 `backend-tests`。 |
| `paths` | 通配列表 | 是 | - | 本 Gate 审查的代码路径；审查轮次固定它们的当前内容。 |

### FailurePolicy 字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `reset` | id 列表 | 是 | - | 需要重做的上游兄弟节点（或 flow 实例），编译时展开为叶子节点。 |
| `max_retries` | 整数 | 否 | `3` | 它所到达的每个 Gate 允许的返工次数，0 到 100。 |

## on_fail 如何到达 Gate

`on_fail` 可以写在直接 Gate、引用节点或 `flow` 条目上。编译时把它下放到范围内的每个 Gate，并把 `reset` 展开为叶子节点 id，因此 `plan.yaml` 中每个 Gate 最多带一条 `gate.on_fail`。某个 Gate 将收到两条策略时编译报错 `on_fail_conflict`，不做隐式优先级选择。Gate 记录有效 FAIL 后，`plan rollback` 只重置该 Gate 的 `reset` 节点、该 Gate 本身与全部下游；返工次数按 Gate 统计。

## Profile

<!-- loopspec:example=profile -->
```yaml
version: 1
name: bugfix
description: 缺陷修复，保留验收与保障
flow:
- id: requirements
  use: requirements
- id: be
  use: backend-implementation
  requires: [requirements]
- id: qa
  use: qa-testing
  requires: [be]
  on_fail: {reset: [be], max_retries: 3}
- id: assurance
  use: change-assurance
  requires: [qa]
guidance:
- 可直接采用或调整；Plan 仍需人确认。
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `version` | 整数 | 否 | `1` | 格式版本。 |
| `name` | kebab-case 字符串 | 是 | - | 必须与文件名一致。 |
| `description` | 字符串 | 否 | `""` | `profile list` 显示。 |
| `flow` | flow 条目列表 | 是 | - | Fragment 实例及其依赖。 |
| `guidance` | 字符串列表 | 否 | `[]` | 给规划 Agent 的建议；属于不可信数据。 |

### flow 条目字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | kebab-case 字符串 | 是 | - | 实例名，作为其所有节点与产物路径的前缀。 |
| `use` | kebab-case 字符串 | 是 | - | 要实例化的 Fragment。 |
| `requires` | 实例 id 列表 | 否 | `[]` | 必须先完成的实例。 |
| `on_fail` | FailurePolicy | 否 | - | 作用于实例内每个 Gate；`reset` 指向上游实例。 |

## Plan 请求

Agent 为完整任务编写一份请求，保存在 Change 的 `plans/` 目录下（Git Diff 不包含该目录）。`plan validate` 只检查不写文件；`plan create` 把它变成草稿 Plan。

<!-- loopspec:example=plan -->
```yaml
based_on: bugfix
flow:
- id: requirements
  use: requirements
- id: be
  use: backend-implementation
  requires: [requirements]
- id: qa
  use: qa-testing
  requires: [be]
  on_fail: {reset: [be], max_retries: 3}
- id: assurance
  use: change-assurance
  requires: [qa]
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `based_on` | kebab-case 字符串 | 否 | - | 请求参考的 Profile，必须存在。 |
| `flow` | flow 条目列表 | 是 | - | 完整任务的 flow。 |
| `base_revision` | 整数 | 仅修订 | - | 修订已确认 Plan 时，等于其当前 `meta.revision`。 |

修订请求是带 `base_revision` 的同一种文档，替换整个 `flow`；哪些内容可以修改见 [Plan 参考](plan-reference.md#修订)。

<!-- loopspec:example=plan -->
```yaml
base_revision: 1
flow:
- id: requirements
  use: requirements
- id: fe
  use: frontend-implementation
  requires: [requirements]
- id: be
  use: backend-implementation
  requires: [requirements]
- id: qa
  use: qa-testing
  requires: [fe]
  on_fail: {reset: [fe], max_retries: 3}
- id: assurance
  use: change-assurance
  requires: [qa, be]
```

## 代码证据与保障

代码 Gate 的结论只通过两条命令生效。`gate begin` 以 Change 基线为准固定该 Gate `evidence.paths` 范围内的内容，返回一次性的轮次编号；Agent 只审查或测试这部分内容；`gate record` 只接受头部仅含 `verdict` 与 `summary` 的报告，固定的代码发生变化则拒绝，否则写出 PASS 或 FAIL 报告与绑定 Plan 摘要的证据。之后再改代码，证据过期，Gate 回到 `ready`。

保障节点不做人工审查。对它执行 `gate record` 时，CLI 计算基线以来的完整 Diff，按保障规则求出每个改动路径需要的能力，并核对活动 Plan 中是否有带有效证据的代码 Gate 提供这些能力；然后写出系统 PASS，或带 `missing_evidence`、`stale_evidence`、`unknown_paths`、`missing_fragments`（含建议 Fragment）或 `diverged_commits` 的 FAIL。`diverged_commits` 列出 HEAD 中的提交内容既不是基线也不是工作区内容的文件，也就是会被推送但没有审查过的内容；提交最终内容或撤销这些中间提交后重新判定。保障 PASS 之后再出现这种提交，保障证据视为过期，需求不能归档。手写的 `pass.md` 永远无效。规则说明见 [配置](configuration.md#保障规则)。
