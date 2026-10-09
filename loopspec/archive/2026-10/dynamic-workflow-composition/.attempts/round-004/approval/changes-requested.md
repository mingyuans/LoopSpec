# 人工审批：要求修改

## Changes Requested

- Fragment 配置取消独立 includes 列表，统一在 nodes 中混合直接定义 Node 与通过 use 引用 Fragment；引用节点通过 id/requires 与直接定义节点共同编排，执行时递归展开。
- 引用节点可声明 on_fail.reset 指向同一 Fragment 中的上游直接定义节点或引用节点；失败重置目标及其下游，包含引用节点的内部产物与 Gate 证据，但不回退业务代码。
- 引用节点由内部有效结果汇总状态：全部完成才成功，内部未处理 Gate FAIL 才失败，未执行不等于失败，损坏或冲突结果作为系统错误阻塞。内部恢复优先，无处理规则或重试耗尽后向外传播；同一失败只由一条规则处理，嵌套重试不能清零绕过限额。
- 同步提案、设计示例、五份规格、任务清单、中文评审摘要和安全复审；保留四层模型、旧格式兼容和 V1/V2 边界，不开始实现代码。

## Human's Words

> 不对，你先按照是，单独用 includes 把 fragment 引用和 nodes 编排分开了。我期望是，把外部 fragment 也作为一个 node 来编排。
>
> 所以是 nodes 里边可以混合外部 fragment.

> 按这个设计，修改方案文档

## Summary Presented to the Human

上一版文档用 nodes 与 includes 分开配置直接定义与 Fragment 引用。本轮讨论收敛为统一 nodes，引用项用 use 指定 Fragment，可在本次引用上设置 on_fail；内部 Gate 状态向上汇总，内部恢复优先处理，不能把缺少产物或系统错误当成业务失败。

## Suggested Direction

引用节点属于统一 Node 配置的引用形式，不新增第五个公共概念；来源定义不因引用场景的恢复绑定而修改。

## state.md Write-Back

- Decision Log：第 3 轮要求修改；采用统一 nodes 和引用节点状态/失败传播。
- Rejected Options：否决 nodes/includes 分离编排与要求额外 Fragment 成败接口。
- Open Questions：没有新增需由用户决定的开放问题。
- Current Focus：按第 3 轮反馈重做规格、设计、任务和安全复审；仅修改材料。
- Artifact Notes：approval/changes-requested.md——要求修改。
