## ADDED Requirements

### Requirement: 上报 Created 与 Refreshed 分组
脚手架结果 SHALL 把本次处理的工具划分为 created（本次首次生成）与 refreshed（此前已生成、本次被覆盖重写）两组并对外上报。判定 SHALL 在写入任何文件**之前**完成，依据是该工具的 skill 文件当时是否已存在于磁盘上——这与既有「某工具是否已配置始终通过检查其 skill 文件是否存在来判定」以及「不引入任何持久化工具选择记录」的规则一致，SHALL NOT 为此新增任何清单或状态文件。

#### Scenario: 首次生成的工具归入 created
- **WHEN** 对一个此前没有任何 skill 文件的工具执行脚手架生成
- **THEN** 该工具出现在 created 分组中，不出现在 refreshed 分组中

#### Scenario: 再次生成的工具归入 refreshed
- **WHEN** 对一个已存在 skill 文件的工具再次执行脚手架生成
- **THEN** 该工具出现在 refreshed 分组中，不出现在 created 分组中

#### Scenario: 判定发生在写入之前
- **WHEN** 对同一工具连续执行两次脚手架生成
- **THEN** 第一次归入 created、第二次归入 refreshed；由于写入是无条件覆盖的，该区分只能依赖写入前捕获的状态

#### Scenario: 混合场景下两组同时上报
- **WHEN** 一次调用同时处理一个已配置工具与一个未配置工具
- **THEN** 结果中 created 与 refreshed 两组各含对应的那一个工具

#### Scenario: 不产生额外的状态记录文件
- **WHEN** 完成一次带 created/refreshed 上报的脚手架生成
- **THEN** 磁盘上未新增任何用于记录工具配置状态的清单文件，状态判定仍完全依赖 skill 文件的存在性
