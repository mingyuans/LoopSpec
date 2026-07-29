## ADDED Requirements

### Requirement: continue 模板需覆盖非产物类节点的动作
`loopspec-continue` 模板正文 SHALL 说明：`loopspec instructions` 返回的指令不一定是"写一份产物文件到 `resolvedOutputPath`"，也可能要求向人类提问并依据其回答二选一写入（人类审批类节点），或要求直接改动代码库并更新被追踪的任务清单（实现类节点）；Agent SHALL 以返回的 `instruction` 正文为准执行，而不是一律只写文件。

正文 SHALL 保持 schema 无关：不硬编码任何具体节点 ID（如 `approval`/`apply`），使模板同样适用于自定义 schema。

#### Scenario: continue 正文说明指令可能要求人类交互或代码实现
- **WHEN** 查看 `loopspec-continue` 模板正文
- **THEN** 正文中说明节点指令可能要求向人类提问确认，或要求改动代码库，而非只写产物文件

#### Scenario: continue 正文不绑定具体节点 ID
- **WHEN** 检查 `loopspec-continue` 模板正文
- **THEN** 正文中不出现 `approval`、`apply` 等内置 schema 专有的节点 ID
