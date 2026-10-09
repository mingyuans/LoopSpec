# 人工审批：通过

## 向人工展示的方案摘要

为前端小需求、Bugfix 与大型需求生成不同 Plan，并使 QA 返工重跑必要 Gate；交付前以全部实际 Diff 的当前审查证据兜底。

- 对外采用 Node、Fragment、Profile、Plan 四层模型；Fragment 在统一 nodes 中混合直接定义与 use 引用，取消独立 includes。
- 引用节点状态由全部成员及有效 Gate 证据推导；内部恢复优先，无规则或耗尽后向外传播，同一失败只处理一次，父级重置不清零内层预算。
- 产物位于需求目录的 artifacts/<所属 Fragment 实例路径>/；不同任务隔离，同容器 ID 唯一，多次引用生成独立实例。
- Plan 固化完整图、成员关系、恢复规则、项目约束、资源字节和 Git 基线；旧 Schema/Change 保持兼容。
- Gate begin/record 绑定审查输入；最终 Assurance 确定性校验全部 Diff，缺失或过期证据阻塞，必要时扩张 Plan 后重新执行 QA/保障。
- 任务共 53 项：V1 模型/编译/快照/CLI 23 项，V2 恢复/证据/保障/修订 24 项，公共文档与验证 6 项。
- 设计级安全复审通过；内容摘要不能证明审查质量、测试真实性或审查者身份，本地流程不控制外部直接提交，默认范围为单 Git 工作树。

具体材料：proposal.md、design.md、五份 specs/*/spec.md、tasks.md、review.md、security/pass.md。已向用户解释统一编排、失败判定与实例产物路径，用户未提出额外实施条件。

## 人工原话

> approved

## 非阻断建议

无。

## state.md 写回

- Decision Log：人工审批第 4 轮通过。
- Frozen Decisions：统一 nodes/use、引用状态与嵌套恢复、实例路径隔离、不可变 Plan、Gate/Diff 保障与旧格式兼容。
- Artifact Notes：approval/approved.md——通过；进入两版本实现。
