# LoopSpec 手册

> 覆盖范围：中文手册索引——每页讲什么、适合谁读。
> 适用读者：人与 LLM Agent；从这里开始。
> 语言：**中文** · [English](../en/README.md)

LoopSpec 是用于 LLM Agent 的计划驱动、带 Gate 的交付 CLI。每个 Change 由 Agent 用可复用的 Fragment 与 Profile 为完整任务起草一份 Plan，经人确认后逐个节点执行已确认的图；代码 Gate 绑定审查证据，最后由保障节点按完整 Git Diff 做确定性检查。

## 页面

| 页面 | 内容 | 读者 |
| --- | --- | --- |
| [概览](overview.md) | 两套层级（Change、Plan、Revision；Node、Fragment、Profile、Plan）、推导状态、目录布局与术语表。 | 所有人，第一篇。 |
| [工作流组合](workflow-composition.md) | 编写 Fragment、Profile 与 Plan 请求；`on_fail` 如何下放到 Gate；代码证据与保障。 | 工作流作者与负责规划的 Agent。 |
| [Plan 参考](plan-reference.md) | 逐字段说明 `plan.yaml`、`.workflow.yaml` 与重做记录，附完整示例；修订与重新规划规则。 | 阅读或评审 Plan 的人。 |
| [配置](configuration.md) | 逐字段说明 `config.yaml` 与保障规则文件；哪些内容实时读取。 | 配置项目的人。 |
| [CLI 参考](cli-reference.md) | 全部命令与参数、JSON 输出与全部错误码。 | 查命令的人。 |
| [Agent 协议](agent-protocol.md) | Agent 的循环：规划、确认、执行、返工、修订、重新规划与命令中断后的处理。 | LLM Agent 与编写其提示词的人。 |
| [版本说明](release-notes.md) | 2.0.0 的变化以及如何从 1.x 升级。 | 升级的用户。 |

## 快速上手

```bash
loopspec init ./loopspec --tools claude
loopspec change new AFD1111
loopspec profile show bugfix
# write changes/AFD1111/plans/request.yaml for the whole task, then:
loopspec plan validate -c AFD1111 -f changes/AFD1111/plans/request.yaml
loopspec plan create -c AFD1111 -f changes/AFD1111/plans/request.yaml
loopspec plan show -c AFD1111 -p 001
# show it to a human and wait for explicit confirmation, then:
loopspec plan approve -c AFD1111 -p 001 --digest "<shown digest>"
loopspec change status AFD1111
```

按问题查找：

- *这个命令做什么？* —— [CLI 参考](cli-reference.md)
- *怎么写 Fragment 或 Plan 请求？* —— [工作流组合](workflow-composition.md)
- *`plan.yaml` 里有什么？* —— [Plan 参考](plan-reference.md)
- *`config.yaml` 能写什么？* —— [配置](configuration.md)
- *Agent 下一步该做什么？* —— [Agent 协议](agent-protocol.md)
- *这个术语是什么意思？* —— [概览术语表](overview.md#术语表)
