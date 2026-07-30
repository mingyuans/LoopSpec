## Why

一个 change 的产物并不只属于一条工作流。真实用法里，多个 schema 会在**同一个 change 名下接力**：先用 `secure-spec-driven` 走完方案与实现，之后换一条更轻的工作流做后续迭代；或者反过来，先用 `docs-only` 起草，再切到完整流程。文档已经把「改 `.workflow.yaml` 的 `schema` 把进行中的 change 迁到另一条工作流」列为受支持的做法。

问题是：**接力工作流读不到前面工作流的产物**。今天 CLI 给出产物路径的只有两处，两处都被锁在「当前那一个 schema」里：

- `loopspec status <change>` 的 `nodes[].existingOutputPaths`——只解析 `.workflow.yaml` 记录的那一个 schema 的节点。
- `loopspec instructions <node> --change <change>` 的 `contextFiles`——同样只覆盖当前 schema 的节点，注释里写明它的目的是「让一个节点无需猜文件名即可读到整个 change」，但这个「整个 change」的边界止于当前 schema。

于是接力发生的那一刻，两件事同时丢失：

1. **前一个 schema 的 schema 名丢失**。`.workflow.yaml` 只有一个 `schema` 字段，迁移时被覆盖，历史无处可查。
2. **前一个 schema 的产物路径丢失**。它们的 artifact root 可能是另一个 `schemas[*].path` 子目录，当前 schema 的节点模式匹配不到，于是不出现在任何响应里——文件明明躺在磁盘上，agent 却只能靠 `ls` 猜。

更糟的一层是**归档**。`loopspec archive` 把整个 change 目录**移动**到 `<home>/archive/<YYYY-MM>/<change>/`。前一段工作流完成并归档后，同名 change 在 `changes/` 下重新开始，此时前面的产物已经不在 `status` / `instructions` 能看见的任何路径下——它们在另一个月份目录里。后续工作流想读「上一轮到底决定了什么」，除了自己遍历 `archive/*/` 别无他法。而这恰恰是接力最常见的形态：一段工作做完、归档、下一段接着做。

现有命令都补不上这个缺口，因为它们的契约都以「当前 schema 的当前位置」为前提：`history` 只覆盖 change 内部的 `.attempts/round-NNN/` 回退轮次，与 schema 接力和目录归档是两件事；`status` 在 change 目录不存在时直接以 `change_not_found` 失败，根本走不到归档目录。

## What Changes

- **新增 `loopspec artifacts <change-name>` 命令**，一次给出该 change **全部**产物的真实路径，跨越三个维度：

  | 维度 | 覆盖方式 |
  | --- | --- |
  | 位置 | 同时扫描活跃目录 `<home>/<artifacts_dir>/<change>/` 与全部归档月份 `<home>/archive/*/<change>/`；每个命中作为一条 location，标注是活跃还是归档、归档月份为何 |
  | schema | 不依赖 `.workflow.yaml` 的单一记录，改用**探测**：拿每个候选 schema 的 `schemas[*].path` 作为 artifact root，用该 schema 各节点的 `generates`/gate 产物模式去匹配磁盘上真实存在的文件 |
  | 轮次 | 回退归档的 `.attempts/round-NNN/` 单独成节，附该轮的门禁、裁决与被移走的文件 |

- **新增 `--schemas` 参数**：接受逗号分隔的 schema 名列表，只报告这些 schema 认领的产物。省略时报告全部已知 schema（`config.yaml` 的候选并集，加上各 location 的 `.workflow.yaml` 自报的 schema——即使它已不在候选列表里）。
- **报告未被认领的文件**（`unclassifiedFiles`）：location 下存在、但没有任何被考察 schema 的节点模式匹配到的文件。没有它，「所有产物路径」就名不副实——被删掉的 schema、手工放进去的附件、改名后的产物都会静默消失。
- **保留文件不计入产物**：沿用既有约定，`state.md` 与 `.workflow.yaml` 不是产物；但 location 层面单独给出 `statePath` 与 `stateExists`，因为跨工作流接力时「上一段的决策记录」和产物一样是必须能拿到的东西。
- **change 名做路径安全校验**：本命令要按名字拼进 `archive/*/` 下的多个目录，因此在拼接前校验它是安全相对路径（非绝对、不含 `..`），不合法直接以 `invalid_change_name` 拒绝。
- **失败语义**：三个维度都没有命中任何位置时以 `change_not_found` 失败；`--schemas` 点名了一个加载不出来的 schema 时以既有的 `schema_not_found` / `schema_invalid` 失败，而不是静默跳过——显式点名的东西不存在是错误，不是空结果。
- **文档同步**（中英双份）：`cli-reference.md` 增加命令小节与响应字段表；`agent-protocol.md` 的「读一个不是你创建的 change」一节改为以本命令为入口，说明接力工作流该先读什么。
- 明确非目标：**不改动 `.workflow.yaml` 的数据模型**（不加 schema 历史字段）；不改 `status` / `instructions` 的既有响应结构；不改归档布局；不做产物内容解析（只给路径，不读文件）；不新增依赖。

**为什么用探测而不是给 `.workflow.yaml` 加历史字段**：加字段需要迁移，而且对**已经归档**的 change 永远补不上历史——那恰恰是本需求最关键的场景。探测法对存量数据（包括几个月前归档的 change）立即生效，零迁移。代价是同名产物的归属歧义：两个都不设 `path`、又都声明 `proposal.md` 的 schema 会各自认领同一个文件。命令如实报告为两处认领，并在扁平的 `files` 汇总里去重——这比猜一个归属更诚实。

## Capabilities

### New Capabilities
- `artifact-discovery`: 一个 change 全部产物的**发现契约**——扫描哪些位置（活跃目录与全部归档月份）、如何在不依赖 `.workflow.yaml` 单一记录的前提下把产物归属到 schema（探测规则、多 schema 同名产物的歧义处理）、哪些文件算产物哪些不算（保留文件、`.attempts` 轮次）、未被任何 schema 认领的文件如何报告、以及跨 schema 接力与跨归档位置读取时的路径安全约束。

### Modified Capabilities
- `loopspec-cli`: 新增一条 `loopspec artifacts` 命令的 CLI 表面要求（语法、`--schemas` 参数解析、`--json` 响应字段契约、失败码），并明确它与 `status` / `instructions` / `history` 的职责边界——后三者的契约本身不变。

## Impact

- **新增文件**：`src/loopspec/artifacts.py`（发现逻辑：位置枚举、schema 探测、产物归类）、`tests/test_artifacts.py`（发现逻辑的单元测试）。
- **修改文件**：`src/loopspec/cli.py`（注册 `artifacts` 命令）、`src/loopspec/paths.py`（归档月份枚举与 change 名安全校验的 helper）、`tests/test_cli.py`（端到端用例）、`docs/{en,zh}/cli-reference.md`、`docs/{en,zh}/agent-protocol.md`。
- **兼容性**：纯新增。既有命令的行为、`--json` 字段、schema 语义、归档布局均不变；不需要任何数据迁移，对已归档的历史 change 同样立即可用。
- **测试面**：`tests/test_docs_consistency.py` 会自动把新命令与新参数纳入覆盖检查（命令必须有小节、每个 `--option` 必须在本小节出现、两语言首列标识符必须一致），因此文档漏写会在 `make test` 阶段失败。
- **信息来源**：`outputs.py` 的产物解析与保留文件规则、`paths.py` 的 `resolve_within` 安全校验、`config.py` 的 schema 解析优先级——全部复用，不另起一套。
- **维护成本**：探测法把「schema 声明了什么产物」作为唯一归属依据，因此改动某个 schema 的 `generates` 会改变历史 change 的归类结果。这是可接受的：归类本就是对当前 schema 定义的一次投影，而 `unclassifiedFiles` 保证文件不会因为改了 schema 而从清单里消失。
