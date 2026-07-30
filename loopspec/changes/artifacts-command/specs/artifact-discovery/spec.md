## ADDED Requirements

### Requirement: 产物位置枚举

一个 change 的产物 SHALL 被视为可能分布在多个**位置**（location）上，而不是单一目录。发现逻辑 SHALL 枚举两类位置：

- **活跃位置**：`<home>/<artifacts_dir>/<change>/`，最多一个。
- **归档位置**：`<home>/archive/<YYYY-MM>/<change>/`，因归档目录按年月分片、而 `loopspec archive` 只在同一月内拒绝重名，同名 change SHALL 允许在多个月份下各有一份，全部都要被枚举。

枚举 SHALL 只把真实存在的目录计为位置；不存在的位置 SHALL 被跳过而不是报告为空位置。当两类位置都没有任何命中时，发现逻辑 SHALL 以 `change_not_found` 失败。

归档月份目录名 SHALL NOT 被要求匹配 `YYYY-MM`：归档目录下任何直接子目录只要包含同名 change 子目录就算一个归档位置，月份原样报告。这使人工整理过的归档目录不会导致产物凭空消失。

#### Scenario: 只存在活跃位置
- **WHEN** change 只存在于 `<home>/changes/<change>/`
- **THEN** 返回恰好一个位置，标记为活跃，归档月份为空

#### Scenario: 归档后仍能发现产物
- **WHEN** change 已被 `loopspec archive` 移动到 `<home>/archive/2026-07/<change>/`，活跃目录下已不存在
- **THEN** 返回恰好一个位置，标记为归档，归档月份为 `2026-07`，且其中的产物路径全部指向归档目录下的真实文件

#### Scenario: 同名 change 同时存在活跃与归档两份
- **WHEN** `<home>/changes/<change>/` 与 `<home>/archive/2026-06/<change>/` 同时存在
- **THEN** 返回两个位置，各自独立报告自己的产物

#### Scenario: 同名 change 存在于多个归档月份
- **WHEN** `<home>/archive/2026-06/<change>/` 与 `<home>/archive/2026-07/<change>/` 同时存在
- **THEN** 两个归档位置都被返回，各自带自己的月份

#### Scenario: 任何位置都不存在
- **WHEN** 活跃目录与全部归档月份下都不存在该名字的目录
- **THEN** 以 `change_not_found` 失败

### Requirement: 位置按时间顺序排列

位置 SHALL 按「从早到晚」排列：全部归档位置按其月份目录名升序在前，活跃位置在最后。

顺序是契约而非实现细节：接力工作流读取前序产物的自然顺序是从最早的一段读到当前一段，把当前位置放在末尾使消费方可以顺序读取而无需自己重排。

#### Scenario: 归档位置早于活跃位置
- **WHEN** 同时存在 `archive/2026-06/<change>/`、`archive/2026-07/<change>/` 与活跃目录
- **THEN** 返回顺序为 `2026-06` 归档、`2026-07` 归档、活跃位置

### Requirement: schema 归属由产物模式探测决定

产物到 schema 的归属 SHALL 通过**探测**确定，而不是依赖位置内 `.workflow.yaml` 记录的那一个 schema：对每个被考察的 schema，以该 schema 在 `config.yaml` 中的 `schemas[*].path` 解析出的 artifact root 为根，用该 schema 每个节点的产物模式（普通节点的 `generates`，门禁节点的 `pass` 与 `fail` 产物，以及门禁自身声明的 `generates`）去匹配磁盘上真实存在的文件；匹配到的文件即归属于该 schema 的该节点。

探测 SHALL 复用既有的产物解析规则，包括 glob 展开与保留文件排除，使 `artifacts` 报告的路径与 `status` 对同一 schema 报告的路径一致。

之所以不依赖 `.workflow.yaml`：该文件只有一个 `schema` 字段，把 change 迁到另一条工作流时前一个 schema 名被覆盖，历史无处可查；而对已经归档的 change，任何新增的历史字段都永远补不上。探测法对存量数据零迁移即刻生效。

#### Scenario: 未被当前 schema 声明的前序产物仍被归属
- **WHEN** 一个 change 先由 schema A 产出产物、`.workflow.yaml` 随后被迁移为 schema B，且 A 与 B 的产物落在不同的 `path` 子目录下
- **THEN** A 与 B 的产物各自被归属到对应 schema，各自带自己的 artifact root

#### Scenario: glob 产物逐个展开
- **WHEN** 某节点的产物模式为 `specs/**/*.md` 且磁盘上有多个匹配文件
- **THEN** 每个匹配文件都作为该节点的一条产物路径出现

#### Scenario: 门禁只报告真实存在的那一侧
- **WHEN** 某门禁声明了 `pass` 与 `fail` 两个产物，磁盘上只存在 `fail` 那一个
- **THEN** 该门禁节点只报告 `fail` 文件，`pass` 不出现

#### Scenario: 声明了但未产出的产物不出现
- **WHEN** 某节点的产物在磁盘上不存在
- **THEN** 该节点不贡献任何产物路径

### Requirement: 被考察的 schema 集合

被考察的 schema 集合 SHALL 按以下规则确定：

- 调用方显式点名时（`--schemas`），集合就是点名的那些，且 SHALL NOT 被扩充。点名了一个加载不出来的 schema SHALL 以 `schema_not_found` 或 `schema_invalid` 失败——显式点名的东西不存在是错误，不是空结果。
- 未点名时，集合 SHALL 为 `config.yaml` 的全部候选（`schemas[*].name` 与 `schema` 的并集）加上各位置 `.workflow.yaml` 自报的 schema 的并集。自报的 schema 即使已不在候选列表里也 SHALL 被纳入，否则从 `config.yaml` 删掉一条候选就会让历史 change 的产物凭空消失。
- 集合内加载不出来的 schema，在未点名的情况下 SHALL 被降级为一条 warning 并跳过，而不是让整个命令失败。

被考察的 schema SHALL 应用于**每一个**位置，而不只是自报它的那个位置：接力的前一个 schema 在后一个位置里也可能留有产物。

#### Scenario: 未点名时覆盖全部候选
- **WHEN** `config.yaml` 列了两个候选 schema，change 的产物分属两者
- **THEN** 两个 schema 的产物都被报告

#### Scenario: 未点名时纳入位置自报的 schema
- **WHEN** 某位置的 `.workflow.yaml` 记录的 schema 已从 `config.yaml` 的候选中移除，但该 schema 目录仍可加载
- **THEN** 该 schema 仍被考察，其产物照常报告

#### Scenario: 点名过滤
- **WHEN** 显式点名两个已知 schema 中的一个
- **THEN** 只报告被点名 schema 的产物，另一个 schema 的产物不出现

#### Scenario: 点名一个不存在的 schema
- **WHEN** 显式点名一个在 `<home>/schemas/` 下不存在的 schema
- **THEN** 以 `schema_not_found` 失败，不返回部分结果

#### Scenario: 未点名时加载失败的 schema 降级为警告
- **WHEN** 某位置自报的 schema 目录已被删除，且未显式点名任何 schema
- **THEN** 命令成功返回，该 schema 被跳过，并附一条说明它无法加载的警告

### Requirement: 保留文件与回退轮次不计入 schema 产物

`state.md` 与 `.workflow.yaml` SHALL NOT 被计为产物，`.attempts/` 下的任何文件也 SHALL NOT 被计为某个 schema 节点的当前产物——沿用既有产物解析的保留规则，使 `artifacts` 与 `status` 对「什么是产物」保持同一判断。

但两者都 SHALL 以专门的形式被报告，因为跨工作流接力时它们与产物同样必须可达：

- 每个位置 SHALL 报告自己 `state.md` 的路径与是否存在。`state.md` 是该 change 的工作记忆，接力工作流需要它来知道前一段做过什么决定。
- 每个位置 SHALL 把 `.attempts/round-NNN/` 逐轮报告，每轮附该轮的轮次号、失败门禁、裁决与被移入该轮的文件路径。轮次号 SHALL 可以从目录名得出，因此**缺少 `_meta.yaml` 的轮次目录仍 SHALL 被报告**（门禁与裁决为空）——否则该目录下的文件会从清单里消失，与产物清单的完整性目标冲突。

#### Scenario: 保留文件不出现在产物清单
- **WHEN** 某位置存在 `state.md` 与 `.workflow.yaml`
- **THEN** 两者都不出现在任何 schema 节点的产物路径中，也不出现在未认领文件中

#### Scenario: state.md 单独报告
- **WHEN** 某位置存在 `state.md`
- **THEN** 该位置报告它的绝对路径，并标记为存在

#### Scenario: 回退轮次逐轮报告
- **WHEN** 某位置有一轮回退归档 `.attempts/round-001/`，其 `_meta.yaml` 记录门禁为 `security`、裁决为 `FAIL`
- **THEN** 报告一条轮次记录，含轮次号 1、门禁 `security`、裁决 `FAIL`，以及该轮目录下被归档文件的路径

#### Scenario: 缺少元数据的轮次目录仍被报告
- **WHEN** 某位置存在 `.attempts/round-002/` 但其中没有 `_meta.yaml`
- **THEN** 仍报告一条轮次记录，轮次号为 2、门禁与裁决为空，且该目录下的文件全部出现在该轮的文件清单中

### Requirement: 未被认领的文件必须被报告

位置下真实存在、但没有被任何被考察 schema 的节点模式匹配到的文件（保留文件与 `.attempts/` 下的文件除外）SHALL 作为**未认领文件**单独报告。

没有这一项，「一个 change 所有的产物路径」就名不副实：被删掉的 schema 留下的产物、改名后不再匹配任何模式的文件、以及人工放进 change 目录的附件都会静默消失。

#### Scenario: 不匹配任何模式的文件被报告为未认领
- **WHEN** 某位置存在一个不被任何被考察 schema 的产物模式匹配的文件
- **THEN** 该文件出现在未认领文件清单中

#### Scenario: 点名过滤后未认领范围随之扩大
- **WHEN** 显式点名两个 schema 中的一个，另一个 schema 的产物因此不被认领
- **THEN** 那些产物出现在未认领文件清单中，而不是从清单里消失

### Requirement: 多 schema 认领同一文件时如实报告

当两个被考察 schema 的产物模式在同一 artifact root 下匹配到同一个文件时（例如两者都不设 `path` 且都声明 `proposal.md`），该文件 SHALL 在两个 schema 下各自报告一次，并 SHALL 附一条指出该文件被多方认领的警告。

发现逻辑 SHALL NOT 替调用方挑一个归属：探测法下归属本就是歧义的，如实报告两处认领比猜一个更诚实。位置级与全局的产物汇总清单 SHALL 对同一路径去重。

#### Scenario: 同名产物被两个 schema 认领
- **WHEN** 两个都不设 `path` 的 schema 都声明了 `proposal.md`，且该文件存在
- **THEN** 两个 schema 各自报告该文件，附一条多方认领警告，且汇总清单中该路径只出现一次

### Requirement: change 名与路径安全

发现逻辑要把 change 名拼进活跃目录与多个归档月份目录，因此在任何拼接之前 SHALL 校验它是安全相对路径（非绝对路径、不含 `..`）；不合法 SHALL 以 `invalid_change_name` 拒绝。

解析出的每一个位置目录 SHALL 被断言仍位于 workflow home 之内；任何逃出 home 的解析结果 SHALL 被拒绝而不是被报告。

被考察的 schema 名同样会成为 `<home>/schemas/<name>` 的路径分量，因此每个 schema 名在被用于加载之前 SHALL 校验为 kebab-case（与 `config.yaml` 对 `schemas[*].name` 的既有约束同一条规则）；不合法 SHALL 以 `config_invalid` 拒绝，SHALL NOT 触及 workflow home 之外的任何目录。

#### Scenario: 含 .. 的 change 名被拒
- **WHEN** change 名为 `../../etc`
- **THEN** 以 `invalid_change_name` 失败，且不访问也不报告 workflow home 之外的任何路径

#### Scenario: 绝对路径形式的 change 名被拒
- **WHEN** change 名是一个绝对路径
- **THEN** 以 `invalid_change_name` 失败

#### Scenario: 含 .. 的 schema 名被拒
- **WHEN** 被点名的 schema 名为 `../../etc`
- **THEN** 以 `config_invalid` 失败，且不尝试从 workflow home 之外加载任何 schema

#### Scenario: 不符合命名约定的 schema 名被拒
- **WHEN** 被点名的 schema 名为 `a/b`
- **THEN** 以 `config_invalid` 失败

### Requirement: 报告出来的每一条路径都收口在 workflow home 之内

发现逻辑对外报告的**每一条**路径——schema 产物、回退轮次内的文件、未认领文件、以及位置目录本身——SHALL 在进入结果之前统一判定为「解析后等于 workflow home 或位于其下」。判定 SHALL 在解析符号链接之后进行，因为路径解析（既有产物解析对结果调用的 `resolve()`）会把指向外部的符号链接展开成 workflow home 之外的绝对路径。

未通过判定的路径 SHALL NOT 被报告，并 SHALL 计一条 warning；该 warning SHALL 只指名该文件相对 change 目录的名字，SHALL NOT 包含解析后的目标路径——否则报告这条 warning 本身又泄露了 workflow home 之外的路径。

判定失败 SHALL NOT 让整条查询失败：一个被符号链接污染的 change 目录仍 SHALL 能列出其余的真实产物。

#### Scenario: 指向外部的符号链接产物被跳过
- **WHEN** 某位置下一个被 schema 声明的产物是指向 workflow home 之外的符号链接
- **THEN** 该路径不出现在任何清单中，命令成功返回，并附一条只指名该文件相对名字的警告

#### Scenario: 未认领文件中的外部符号链接被跳过
- **WHEN** 某位置下存在一个指向 workflow home 之外的符号链接、且不匹配任何产物模式
- **THEN** 该路径不出现在未认领文件中，且警告文本中不含 workflow home 之外的任何路径

#### Scenario: 污染不影响同目录其余产物
- **WHEN** 某位置同时存在一个指向外部的符号链接与若干正常产物
- **THEN** 全部正常产物照常报告，只有该符号链接被跳过

#### Scenario: 指向外部的归档月份目录被整体拒绝
- **WHEN** `<home>/archive/<month>` 是指向 workflow home 之外的符号链接
- **THEN** 该位置不被报告，且不列出其中的任何路径

### Requirement: 任何元数据缺失或损坏时降级而非失败

发现逻辑读取的**每一份**元数据 SHALL 按同一模式处理：缺失、无法解析、或解析出的顶层不是映射，都 SHALL 降级为一条警告并按「该份元数据不可用」继续，SHALL NOT 让整条查询失败，也 SHALL NOT 以未捕获异常终止。适用于两份元数据：

- **位置的 `.workflow.yaml`**：不可用时该位置的自报 schema 报告为空，其余部分照常报告。
- **轮次的 `.attempts/round-NNN/_meta.yaml`**：不可用时该轮的门禁与裁决报告为空，但该轮目录下的**文件仍 SHALL 照常报告**。

理由：本命令的价值恰在于读取**旧的、可能已归档**的位置，而一个几个月前归档的位置里有一份格式过时的元数据不应该让当前查询失败——产物路径本身仍然是准确可用的。

#### Scenario: 归档位置缺少元数据
- **WHEN** 某归档位置没有 `.workflow.yaml`
- **THEN** 命令成功，该位置自报 schema 为空，其产物仍按被考察的 schema 集合正常归属

#### Scenario: 元数据损坏降级为警告
- **WHEN** 某位置的 `.workflow.yaml` 无法通过校验
- **THEN** 命令成功返回，该位置自报 schema 为空，并附一条说明元数据不可读的警告

#### Scenario: 轮次元数据顶层不是映射
- **WHEN** 某轮 `.attempts/round-001/_meta.yaml` 的内容是一个合法 YAML 列表而不是映射
- **THEN** 命令成功返回，该轮门禁与裁决为空，该轮目录下的文件照常报告，并附一条警告

#### Scenario: 轮次元数据格式非法
- **WHEN** 某轮 `_meta.yaml` 不是合法 YAML
- **THEN** 命令成功返回而非以异常终止，该轮文件照常报告，并附一条警告
