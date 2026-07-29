# secure-spec-driven

> 覆盖范围：内置工作流——它的七个节点、每个节点必须产出什么，以及每个门禁为什么重置它所重置的东西。
> 适用读者：用默认工作流推进变更的人类与 LLM agent。
> 语言：[English](../../en/workflows/secure-spec-driven.md) · **中文**

`secure-spec-driven` 是 `loopspec init` 安装、`config.yaml` 默认使用的 schema。它把一次变更从"我们为什么要做这件事"推进到"代码写完且测试通过"，其中安全评审、人类签核与实现步骤都是 [门禁](../overview.md#术语表)。

## 节点图

```text
proposal ──┬──> specs ──┐
           └──> design ─┴──> tasks ──> security ──> approval ──> apply
```

| 节点 | 类型 | requires | 产物 |
| --- | --- | --- | --- |
| `proposal` | 普通 | — | `proposal.md` |
| `specs` | 普通 | `proposal` | `specs/**/*.md` |
| `design` | 普通 | `proposal` | `design.md` |
| `tasks` | 普通 | `specs`, `design` | `tasks.md` |
| `security` | 门禁 | `tasks` | `security/pass.md` 或 `security/fail.md` |
| `approval` | 门禁 | `security` | `approval/approved.md` 或 `approval/changes-requested.md` |
| `apply` | 门禁 | `approval` | `apply/report.md` 或 `apply/blocked.md` |

`apply` 还声明了 `tracks: tasks.md`，因此只有 `tasks.md` 中每个 checkbox 都被勾选时它才 `done`。每个节点都从 `instructions/<node>.md` 加载指令文本，每个门禁都为两种裁决各提供一份模板。

由于 `specs` 与 `design` 都只依赖 `proposal`，它们会同时变为 `ready`。你先写哪个都无所谓；`tasks` 会等两者都完成。

## 各个节点

### proposal

确立**为什么**。小节：`Why`、`What Changes`、`Capabilities`、`Impact`。

`Capabilities` 一节是承重的：它是本节点与 `specs` 之间的契约。列在那里的每个新能力会变成一个 `specs/<name>/spec.md`，每个被修改的能力需要一份针对既有 spec 的 delta。填写之前先调研项目已有的 spec；在这里凭空编一个能力名，后面会产出一个孤立的 spec 文件。

控制在一到两页，并且把实现细节留给 `design`。

### specs

定义系统**应当做什么**：提案列出的每个能力一份 spec 文件，位于 `specs/<capability>/spec.md`。

工具链依赖的格式规则：

- 每条需求是 `### Requirement: <name>`，后接使用 SHALL 或 MUST 的规范性文本。
- 每个场景是 `#### Scenario: <name>`，带 `- **WHEN**` / `- **THEN**` 列表项。
- 场景必须恰好用四个井号。用三个井号或列表项会静默失效。
- 每条需求至少要有一个场景。每个场景都是一个潜在的测试用例。

针对既有 spec 的 delta 使用 `## ADDED Requirements`、`## MODIFIED Requirements`、 `## REMOVED Requirements` 与 `## RENAMED Requirements`。MODIFIED 的需求必须携带整段更新后的需求块，而不是只写改动的那句话——部分内容会永久丢失细节。REMOVED 需要 `**Reason**` 与 `**Migration**`。

### design

解释**怎么做**，并且只在变更确有必要时才写：跨模块的变更、新的架构模式、新的外部依赖、显著的数据模型变更、安全或性能或迁移复杂度，或者确实值得在写码前定下来的歧义。

小节：`Context`、`Goals / Non-Goals`、`Decisions`、`Risks / Trade-offs`、`Migration Plan`、 `Open Questions`。每个决策都应给出考虑过的替代方案以及它们为何落选——"为什么"才是真正有用地留存下来的部分。

一条实务提示：`security` 门禁会读这份文件。凡是设计触及认证、授权、输入处理、密钥或外部集成的地方都要明确点出来，因为评审要找的正是这些。

### tasks

把工作拆成清单。格式很重要——进度追踪要解析它：

- 用 `## <number>. <group name>` 标题分组。
- 每个任务都是一个 checkbox：`- [ ] X.Y 描述`。
- 不是 checkbox 的行不会被追踪。
- 按依赖排序；顺序编码了什么必须先做。
- 每个任务应小到能一次坐下做完，且可验证到你知道它何时算完成。

`security` 门禁同样会读这份文件，因此凡是涉及认证、授权、外部输入、密钥或第三方依赖的任务都要容易被发现。

### security

第一个门禁。评审 `design.md` 与 `tasks.md`，并且只写 `security/pass.md` 与 `security/fail.md` 中的一个。

它检查什么：来自不可信输入的注入风险、认证与授权缺口、密钥处理、路径遍历、不安全的反序列化、新第三方依赖风险，以及数据暴露。

FAIL 时，`Blocking Issues` 下的每个列表项会成为下一次尝试 `priorAttempts` 中的一条，因此每一项都必须自包含且可执行——一个列表项对应一个具体问题，而不是一整段。重试时要核实先前列出的每一项是否真的被处理了；换个说法但风险依旧的，不得放过。

| 配置 | 取值 | 理由 |
| --- | --- | --- |
| `reset` | `[design]` | 安全发现几乎总是"怎么做"的问题。重置 `design` 会通过闭包同时重置 `tasks` 与门禁自身，于是计划从造成问题的那个决策处重建。`specs` 保留，因为评审反对的很少是*在做什么*。 |
| `max_retries` | `3` | 够做几轮真正的迭代；再多说明设计很可能有结构性问题，该让人类看看。 |
| `on_exhausted` | `escalate` | 交给人类，而不是静默停止。 |

### approval

人类签核门禁——唯一一个裁决不由 agent 决定的节点。

agent 读完至此产出的全部产物，把计划总结成人类几分钟能读完的篇幅，并用宿主工具的交互提问能力请求一个明确选择。批准则写 `approval/approved.md`；要求调整则写 `approval/changes-requested.md`。无论哪种，裁决都会被记入 `state.md`——经过蒸馏、去掉代词——而人类的逐字原话留在裁决文件里。

agent 被明确要求永不代替人类批准。没有办法联系到人类时，该节点就停在 `ready` 等待，这正是"正在等一个人"的正确状态。

| 配置 | 取值 | 理由 |
| --- | --- | --- |
| `reset` | `[specs, design]` | 此处的人类反馈经常触及*在做什么*而不只是*怎么做*，因此两者都重做。 |
| `max_retries` | `5` | 比安全门禁更高：几轮人类反馈是正常的，而且相比重建一个实现要便宜得多。 |
| `on_exhausted` | `escalate` | 五份被否的计划该开一次会谈，而不是继续跑循环。 |

### apply

实现门禁，也是唯一会碰源码的节点。

agent 读完全部产物——`instructions` 响应中的 `contextFiles` 会把真实路径交给它——边做边勾 `tasks.md` 的 checkbox，跑项目的测试与检查，然后写 `apply/report.md`。这份报告是本次变更对代码库做了什么的唯一记录，因此它要列出改动的文件、真实的测试输出，以及任何偏离设计之处及其原因。

如果计划本身被证明行不通，它改写 `apply/blocked.md`。那份报告必须记下已经做出的代码改动：回退归档的是变更目录内的产物文件，一行代码都不会被回滚，因此缺了这份记录，下一轮就会对着一棵谁也没描述过的工作树做计划。

由于 `tracks: tasks.md`，提前写出报告并不能让节点完成：`apply` 停在 `ready`，`isComplete` 保持 `false`， `loopspec archive` 会持续以 `archive_unsafe` 拒绝。

| 配置 | 取值 | 理由 |
| --- | --- | --- |
| `reset` | `[design]` | 实现受阻几乎总是"怎么做"的问题。真正的"做什么"问题会在下游的 `approval` 门禁被再次拦住，它就坐在 `design` 与 `apply` 之间。 |
| `max_retries` | `2` | 三者中最低：返工一个已部分建成的实现是最昂贵的重试。 |
| `on_exhausted` | `escalate` | 两次实现失败意味着该让人类看看这份计划。 |

## 走一遍完整流程

```bash
loopspec new add-payment --json
loopspec status add-payment --json
loopspec instructions proposal --change add-payment --json
# write proposal.md, update state.md, then loop back to status
```

`status` 每次都会指名下一个节点，因此顺序自然而然：`proposal`，然后 `specs` 与 `design`（先后随意），然后 `tasks`，然后三个门禁。若 `security` 或 `approval` 失败，`status` 会给你一条 `pendingRollback` 命令；执行它，然后带着 `priorAttempts` 重做被重置的节点。当 `isComplete` 变为 `true`：

```bash
loopspec archive add-payment --json
```

## 下一步

- [Agent 协议](../agent-protocol.md)——逐字段展开的循环细节。
- [Schema 参考](../schema-reference.md)——如何修改这份 schema 或编写自己的。
