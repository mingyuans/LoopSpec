# LoopSpec 手册

> 覆盖范围：中文手册索引——每一篇覆盖什么、面向谁。
> 适用读者：人类与 LLM agent；从这里开始。
> 语言：[English](../en/README.md) · **中文**

LoopSpec 是一个用于门禁式产物工作流的 CLI：你用 YAML 声明一次变更必须产出的文档图，agent 逐个生成它们，门禁节点可以带着记录在案的理由把工作打回去。

## 各篇

| 文档 | 覆盖 | 面向 |
| --- | --- | --- |
| [总览](overview.md) | LoopSpec 是什么、解决什么问题、核心模型（节点、产物、门禁、回退、状态从文件系统推导），以及手册其余各篇使用的术语表。 | 所有人，第一篇。 |
| [CLI 参考](cli-reference.md) | 每条命令与选项、每个 `--json` 响应字段、真实响应示例、失败契约，以及全部 15 个错误码。 | 任何查参数或响应结构的人。 |
| [配置](configuration.md) | `config.yaml` 每个字段的类型、必填性、默认值与校验规则；新建与既有 change 两条不同的 schema 解析路径；四个递进示例。 | 搭建或排查项目配置。 |
| [Schema 参考](schema-reference.md) | `schema.yaml` 每个字段、schema 目录布局、`tracks` 与门禁语义、全部加载期校验及其错误码，以及一份完整的最小 schema。 | 编写或修复工作流。 |
| [Agent 协议](agent-protocol.md) | status/instructions 循环、回退支线、每一步该读哪个响应字段，以及 agent 最容易搞错的行为。 | LLM agent，以及为其写提示词的人。 |
| [secure-spec-driven](workflows/secure-spec-driven.md) | 内置工作流：七个节点、每个节点必须产出什么，以及每个门禁为什么重置它所重置的东西。 | 用默认流程推进变更。 |

## 快速定位

上手：

```bash
loopspec init ./loopspec
loopspec new add-payment --json
loopspec status add-payment --json
```

`status` 每一轮都会指名唯一的下一条命令。照它执行，写出 `loopspec instructions` 所描述的产物，再回到 `status`——这就是全部循环。细节见 [Agent 协议](agent-protocol.md)，其余一切见 [CLI 参考](cli-reference.md)。

带着具体问题去哪里找：

- *这个参数是干什么的？*——[CLI 参考](cli-reference.md)
- *`config.yaml` 里能写什么？*——[配置](configuration.md)
- *怎么编写自己的工作流？*——[Schema 参考](schema-reference.md)
- *我的 agent 下一步该做什么？*——[Agent 协议](agent-protocol.md)
- *这个节点应该产出什么？*——[secure-spec-driven](workflows/secure-spec-driven.md)
- *这个术语是什么意思？*——[总览术语表](overview.md#术语表)
