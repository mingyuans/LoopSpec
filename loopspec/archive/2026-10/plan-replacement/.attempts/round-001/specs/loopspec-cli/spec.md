## ADDED Requirements

### Requirement: 替换与撤销命令面
CLI SHALL 提供 `plans create --replace` 与 `plans discard`，并支持 --json 及统一 error/message/fix 信封。plans show 对替换草稿 SHALL 返回旧修订摘要、replaces 处置、将归档文件数、沿用摘要与覆盖检查结果。status SHALL 返回 suspended 与 pendingReplacement；被暂停拒绝的命令 SHALL 返回错误码 plan_suspended 与“展示草稿或 discard”的纠正指引。

#### Scenario: 展示替换草稿
- **WHEN** 执行 plans show 查看替换草稿
- **THEN** 返回 mode: replace、旧修订号与摘要、reuse/carry/retire、archivedFileCount 与 coverage 结果

#### Scenario: 暂停期间推进
- **WHEN** 存在替换草稿时执行 loopspec next
- **THEN** 返回 plan_suspended，fix 指向 plans show 或 plans discard
