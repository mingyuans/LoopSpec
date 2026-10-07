# Plan 参考

> 覆盖范围：逐字段说明 `plan.yaml`、Change 级 `.workflow.yaml` 与重做记录；修订、重新规划与命令中断后的状态。
> 适用读者：评审 Plan 的人，以及负责修订与重新规划的 Agent。
> 语言：**中文** · [English](../en/plan-reference.md)

## 一份 Plan 一个文件

每份 Plan 就是一个 `changes/<change>/plans/<NNN>/plan.yaml`，分两部分：`meta` 记录人的决定，`spec` 是执行图。每次写入都是整文件原子替换。每次加载时 CLI 重新计算 `spec` 的 SHA-256 摘要并要求等于 `meta.digest`；手改 `spec` 会得到 `plan_integrity`。

`spec.flow` 是 Agent 请求的实例粒度流程，用于评审、修订与 `profile save`；`spec.nodes` 是编译后的叶子执行图。**CLI 只按 `nodes` 导航**（含每个 Gate 的 `on_fail`）。产物与报告路径相对 Plan 目录；`instruction`、`template`、`assurance` 是工作区内的路径，执行时实时读取。基线与仓库不在 spec 中，属于 Change。

## 完整示例

Change `AFD1111` 修复一个越权缺陷。Plan 001 按前端问题规划，经人同意后归档；Plan 002 采用内置 `bugfix` Profile 起草并已确认。`nodes` 是该请求的真实编译结果。

<!-- loopspec:example=plan-file -->
```yaml
meta:
  plan: "002"
  status: approved
  revision: 1
  digest: 630c3781333a5cc0ba1635107e6875f55b95e34db6b0b69ba3cd0f4565b5576e
  approved_at: "2026-10-07T10:20:00+00:00"
  note: Plan 001 按前端问题规划；排查确认是后端缺少归属校验，改为后端缺陷修复
  created: "2026-10-07T10:05:00+00:00"
  archived_at: null
  archive_note: null
spec:
  based_on: bugfix
  flow:
  - id: requirements
    use: requirements
    requires: []
  - id: be
    use: backend-implementation
    requires: [requirements]
  - id: qa
    use: qa-testing
    requires: [be]
    on_fail:
      reset: [be]
      max_retries: 3
  - id: assurance
    use: change-assurance
    requires: [qa]
  nodes:
  - id: requirements/proposal
    fragment: requirements
    requires: []
    generates: artifacts/requirements/proposal.md
    instruction: fragments/requirements/proposal.instruction.md
    template: fragments/requirements/proposal.template.md
  - id: be/code/implement
    fragment: be/code
    requires: [requirements/proposal]
    generates: artifacts/be/code/implementation.md
    instruction: fragments/backend-code/implement.instruction.md
    template: fragments/backend-code/implement.template.md
  - id: be/tests/check
    fragment: be/tests
    requires: [be/code/implement]
    instruction: fragments/backend-tests/check.instruction.md
    gate:
      outputs: {pass: artifacts/be/tests/check/pass.md, fail: artifacts/be/tests/check/fail.md}
      templates: {pass: fragments/backend-tests/check.pass.md, fail: fragments/backend-tests/check.fail.md}
      evidence:
        provides: [backend-tests]
        paths: [src/backend/**, backend/**, tests/backend/**]
      on_fail:
        reset: [be/code/implement]
        max_retries: 3
  - id: be/security/check
    fragment: be/security
    requires: [be/tests/check]
    instruction: fragments/security-review/check.instruction.md
    gate:
      outputs: {pass: artifacts/be/security/check/pass.md, fail: artifacts/be/security/check/fail.md}
      templates: {pass: fragments/security-review/check.pass.md, fail: fragments/security-review/check.fail.md}
      evidence:
        provides: [security-review]
        paths: [src/backend/**, backend/**, tests/backend/**]
      on_fail:
        reset: [be/code/implement]
        max_retries: 3
  - id: be/review/check
    fragment: be/review
    requires: [be/security/check]
    instruction: fragments/backend-pr-review/check.instruction.md
    gate:
      outputs: {pass: artifacts/be/review/check/pass.md, fail: artifacts/be/review/check/fail.md}
      templates: {pass: fragments/backend-pr-review/check.pass.md, fail: fragments/backend-pr-review/check.fail.md}
      evidence:
        provides: [pr-review]
        paths: [src/backend/**, backend/**, tests/backend/**]
      on_fail:
        reset: [be/code/implement]
        max_retries: 3
  - id: qa/test
    fragment: qa
    requires: [be/review/check]
    instruction: fragments/qa-testing/test.instruction.md
    gate:
      outputs: {pass: artifacts/qa/test/pass.md, fail: artifacts/qa/test/fail.md}
      templates: {pass: fragments/qa-testing/test.pass.md, fail: fragments/qa-testing/test.fail.md}
      on_fail:
        reset: [be/code/implement, be/review/check, be/security/check, be/tests/check]
        max_retries: 3
  - id: assurance/check
    fragment: assurance
    requires: [qa/test]
    instruction: fragments/change-assurance/check.instruction.md
    gate:
      outputs: {pass: artifacts/assurance/check/pass.md, fail: artifacts/assurance/check/fail.md}
      assurance: fragments/change-assurance/rules.yaml
```

### 文档字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `meta` | PlanMeta | 是 | - | 关于这份 Plan 的人的决定。 |
| `spec` | PlanSpec | 是 | - | 执行图，受 `meta.digest` 约束。 |

### meta 字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `plan` | 三位数字字符串 | 是 | - | Plan 编号，等于目录名。 |
| `status` | `draft`、`approved` 或 `archived` | 是 | - | 只记录人的决定；完成状态实时推导，不落盘。 |
| `revision` | 整数 | 是 | - | 已确认的修订数；草稿为 `0`，首次确认后为 `1`。 |
| `digest` | 64 位十六进制 | 是 | - | `spec` 的摘要；确认绑定的就是它。 |
| `approved_at` | 时间或 null | 否 | `null` | 当前修订的确认时间。 |
| `note` | 字符串或 null | 否 | `null` | 新建这份 Plan 的原因，来自 `plan create --note`。 |
| `created` | 时间 | 是 | - | 创建时间。 |
| `archived_at` | 时间或 null | 否 | `null` | 只在归档时设置。 |
| `archive_note` | 字符串或 null | 否 | `null` | 来自 `plan archive --note`。 |

### spec 字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `based_on` | kebab-case 字符串 | 否 | - | 请求参考的 Profile。 |
| `flow` | flow 条目列表 | 是 | - | 请求的 flow，见 [工作流组合](workflow-composition.md#plan-请求)。 |
| `nodes` | 解析后的节点列表 | 是 | - | CLI 执行的编译后叶子图。 |

### 解析后节点字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | 实例路径 | 是 | - | 例如 `be/tests/check`。 |
| `fragment` | 实例路径 | 是 | - | 节点所属实例，例如 `be/tests`。 |
| `description` | 字符串 | 否 | - | 取自 Fragment。 |
| `requires` | 节点 id 列表 | 否 | `[]` | 展开后的叶子依赖。 |
| `generates` | 路径或通配 | `generates`/`gate` 二选一 | - | `artifacts/` 下的产物路径。 |
| `instruction` | 工作区路径 | 否 | - | 指令文件，实时读取。 |
| `template` | 工作区路径 | 否 | - | 产物模板，实时读取。 |
| `tracks` | 路径 | 否 | - | 必须全部勾选的清单产物。 |
| `gate` | 解析后的 Gate | `generates`/`gate` 二选一 | - | Gate 定义，含 `on_fail`。 |

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `outputs` | GateOutputs | 是 | - | `artifacts/` 下的 PASS 与 FAIL 报告路径。 |
| `templates` | GateTemplates | 否 | - | 报告模板，实时读取。 |
| `evidence` | CodeEvidence | 否 | - | 代码 Gate 的范围与能力。 |
| `assurance` | 工作区路径 | 否 | - | 保障节点的规则文件，实时读取。 |
| `on_fail` | FailurePolicy | 否 | - | 该 Gate 唯一的返工策略，`reset` 已展开为叶子。 |

## Change 级状态

`changes/<change>/.workflow.yaml` 只保存属于 Change 而非某份 Plan 的信息，不保存 Plan 指针：`meta.status` 为 `draft` 或 `approved` 的 Plan 是未结束 Plan，`approved` 的那份是活动 Plan，新 Plan 编号为已有最大编号加 1。出现两份未结束 Plan 时返回 `history_integrity`。Change 状态实时推导，从不存储。

<!-- loopspec:example=change-state -->
```yaml
format_version: 4
change_name: AFD1111
created: "2026-10-07T08:00:00+00:00"
baseline: 9f2c3e1d4b5a69788766554433221100ffeeddcc
repository: /path/to/project
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `format_version` | 整数 | 否 | `4` | 只接受 `4`；更早的 Change 返回 `unsupported_format`。 |
| `change_name` | 字符串 | 是 | - | 等于目录名。 |
| `created` | 时间 | 是 | - | 创建时间。 |
| `baseline` | 完整 Commit 哈希或 null | 否 | `null` | 第一次 `plan create` 时固定，之后不变；所有 Plan 以它计算 Diff。 |
| `repository` | 路径或 null | 否 | `null` | 与基线一起固定的仓库根目录；每次计算 Diff 都会核对。 |

## 重做记录

`plan rollback` 与需要重新执行节点的修订，都会把受影响节点的工作流文件归档到 `.attempts/<NNN>/files/`，并写 `.attempts/<NNN>/record.yaml` 说明。两种记录统一编号。只有 `rollback` 记录计入 Gate 的 `max_retries`；两种记录都会作为 `priorAttempts` 提供给重新执行的节点，并标注为不可信数据。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `seq` | 整数 | 是 | - | 记录序号，等于目录名。 |
| `kind` | `rollback` 或 `revision` | 是 | - | 返工的起因。 |
| `created` | 时间 | 是 | - | 记录写入时间。 |
| `plan_digest` | 64 位十六进制 | 是 | - | 当时 spec 的摘要。 |
| `reset` | 节点 id 列表 | 是 | - | 重新执行的节点。 |
| `files` | 移动清单 | 是 | - | 待归档文件，各带内容摘要。 |
| `gate` | 节点 id | 仅 rollback | - | 失败的 Gate。 |
| `failure_digest` | 64 位十六进制 | 仅 rollback | - | 归档的 FAIL 报告摘要。 |
| `target_digest` | 64 位十六进制 | 仅 revision | - | 修订后的 spec 摘要。 |
| `revision` | 整数 | 仅 revision | - | 修订后的修订号。 |

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `source` | 相对 Plan 的路径 | 是 | - | 重置节点的产物、Gate 报告或 `.gates/<node>/` 记录。 |
| `destination` | 相对 Plan 的路径 | 是 | - | 总是 `.attempts/<seq>/files/<source>`。 |
| `sha256` | 64 位十六进制 | 是 | - | 内容摘要，重新执行补完移动时核对。 |

## 修订

原计划仍然成立时，原地调整。Agent 编写带 `base_revision` 的修订请求，执行 `plan validate` 取得新摘要、新增实例与将重新执行的节点，展示给人；人确认后才执行 `plan approve -f <请求> --digest <摘要>`。此前不写任何文件。

- **冻结节点**：已完成、当前、失败过或有重做记录的节点。冻结节点不能删除、改名，执行定义（输出、Gate、`on_fail`、资源路径）不能改变。
- 冻结节点只能**增加** `requires`；它及全部下游会归档（`kind: revision`）并重新执行。
- 每个有效 FAIL 的 Gate 都必须在重新执行范围内，修订不能掩盖失败。
- `base_revision` 必须等于当前 `meta.revision`，否则返回 `stale_revision`。
- 代码 Gate 证据绑定摘要，修订后代码 Gate 需要重新审查。

## 重新规划

任务本身变化时，Agent 向人展示旧 Plan 的进度（已完成、失败、耗尽的 Gate），只有取得明确同意后才执行 `plan archive`。Plan 变为 `archived`，目录原样保留，Change 回到 `unplanned`。下一次 `plan create` 使用下一个编号，在同一基线上从空状态开始：产物、证据与返工次数都不继承，旧 Plan 期间改过的代码必须重新审查。

## 命令中断

没有事务文件，也没有中断状态。每条命令只有一次决定结果的写入（生效点）。生效点之前的写入不影响状态推导，再次执行时被覆盖或复用；生效点之后只做文件搬运，不改变推导结果。因此命令中断后，Change 要么保持命令之前的样子，要么已是命令之后的样子，Agent 照常从 `change status` 继续。

| 命令 | 写入顺序 | 生效点 |
| --- | --- | --- |
| `plan create`（新建草稿） | 首次时写 `.workflow.yaml` 的基线，然后 Plan 的 `state.md`，最后 `plan.yaml`。 | `plan.yaml` |
| `plan approve`（草稿） | `plan.yaml` 置为 approved。 | 同一次写入 |
| `plan archive` | `plan.yaml` 置为 archived。 | 同一次写入 |
| `plan rollback` | `record.yaml`，然后逐个归档清单中的文件，FAIL 报告最后。 | `record.yaml` |
| `plan approve -f`（修订） | `record.yaml`，然后替换 `plan.yaml`，最后逐个归档清单中的文件。 | `plan.yaml` |

- rollback 记录写入即生效；revision 记录在 `plan.yaml` 达到其修订号后生效。未生效的 revision 记录被忽略，不进入历史与 `priorAttempts`，并由下一条记录替换。
- 已生效记录中尚未搬走的文件视为不存在，所以被重置的节点立即可以重新执行。`node instructions`、`gate`、`plan rollback`、`plan approve`、`plan archive` 与 `change archive` 会在 Change 写锁内先补完这些搬运；`change status` 只读。
- 每次搬运都按记录中的摘要核对。源文件或已归档文件不符，或记录列出了重置节点工作流文件以外的路径时，命令以 `history_integrity` 停止，而不是猜测。
