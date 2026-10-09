## ADDED Requirements

### Requirement: 完整替换修订模式
系统 SHALL 支持 `plans create <change> --plan <request> --replace` 创建替换草稿，`--replace` 与 `--safety-expansion` SHALL 互斥。替换请求 SHALL 以当前活动修订为 `base_revision`，SHALL 包含 `replaces`（reason、reuse、carry、retire），SHALL 可以重新组织节点、依赖、实例与 on_fail。替换草稿 SHALL 记录 `mode: replace`，普通重组与安全扩张的冻结规则 SHALL 保持不变且不适用于替换模式。没有活动 Plan 时 SHALL 拒绝 `--replace`。

#### Scenario: 任务变化后重组已执行部分
- **WHEN** 活动修订 2 已完成 requirements 与 be/code，任务改为前后端并取消导出，请求以 base_revision 2 重新组织 flow 并给出完整 replaces
- **THEN** 系统保存 mode: replace 的修订 3 草稿，不要求旧节点冻结

#### Scenario: 选项冲突或缺少处置
- **WHEN** 同时使用 --replace 与 --safety-expansion，或替换请求缺少 replaces.reason
- **THEN** 命令以结构化错误拒绝，不保存草稿

### Requirement: 替换不放宽固定约束
替换草稿 SHALL 保持旧 Plan 的固定基线、仓库身份、项目约束与保障规则快照，引擎能力版本 SHALL 不降低。Plan 有保障规则时，系统 SHALL 用当前全量 Diff 对照新 Plan 的能力提供者执行保障诊断，存在 missing_fragments 或 unknown_paths 时 SHALL 以 coverage_missing 拒绝并返回诊断；无保障规则时 SHALL 跳过该检查。

#### Scenario: 替换遗漏已有后端改动
- **WHEN** 工作树已有 backend/ 改动，替换请求的新 Plan 不含提供 backend-tests 的 Gate
- **THEN** 草稿创建以 coverage_missing 拒绝，并列出缺失能力与建议 Fragment

#### Scenario: 替换试图更换基线
- **WHEN** 替换请求声明了不同的 baseline
- **THEN** 系统以 baseline_frozen 拒绝

### Requirement: 旧成果默认不继承
确认替换时，系统 SHALL 归档旧 Plan 全部节点的产物、PASS/FAIL 报告与 Gate 控制文件到 `.workflow/revisions/<新修订>/files/`，新 Plan SHALL 从空状态开始推导。新 Plan 中与旧节点同名的节点 SHALL NOT 因旧文件存在而视为完成。业务代码 SHALL NOT 被移动、复制、回退或删除。

#### Scenario: 同名节点重新执行
- **WHEN** 旧修订与新修订都有 be/code，旧 be/code 已完成，且未声明 reuse
- **THEN** 激活后 be/code 状态为 ready，旧产物位于修订归档目录，业务代码保持不变

### Requirement: 显式沿用旧产物
`replaces.reuse` SHALL 只把旧 Plan 中状态为 done 且恰有一个输出文件的产物节点映射到新 Plan 中 generates 不含通配符的产物节点。草稿 SHALL 记录旧路径、sha256 与大小并纳入 Plan 摘要。确认事务 SHALL 在归档后从归档位置复制到新路径并校验摘要。Gate 节点 SHALL NOT 出现在 reuse 的任何一侧；普通 PASS 与代码证据 SHALL 在新 Plan 中重新取得。

#### Scenario: 沿用需求文档
- **WHEN** reuse 声明 requirements/proposal ← requirements/proposal 且旧文件未变化
- **THEN** 激活后新 requirements/proposal 已完成，内容与旧文件摘要一致

#### Scenario: 沿用内容在确认前被修改
- **WHEN** 草稿创建后旧 proposal 文件被改写
- **THEN** approve 拒绝，活动指针不变

#### Scenario: 试图沿用 Gate 结论
- **WHEN** reuse 的任一侧是 Gate 节点
- **THEN** 草稿创建被拒绝

### Requirement: 未解决问题必须承接或放弃
旧 Plan 中每个处于 failed 的有效 FAIL Gate SHALL 通过 `replaces.carry` 指定一个新 flow 实例承接，或其所属旧实例被 `replaces.retire`。处于 exhausted 的 Gate SHALL 只能通过 retire 处置。旧 flow 中 ID 不再出现在新 flow 的实例 SHALL 列入 retire 并给出非空原因；retire 列出新 flow 中仍存在的 ID SHALL 被拒绝。被承接的失败报告 SHALL 在新实例根节点的 instructions 中作为 `inheritedFailures` 提供，并标注为不可信数据。

#### Scenario: 承接 QA 失败
- **WHEN** 旧 qa/test 有有效 FAIL，替换请求 carry qa/test → be
- **THEN** 激活后 instructions be 的根节点包含该失败报告的归档路径与摘要

#### Scenario: 遗漏处置
- **WHEN** 旧 export 实例不在新 flow 中且未列入 retire，或有效 FAIL 未被 carry 也未 retire
- **THEN** 草稿创建被拒绝并列出缺少处置的项

#### Scenario: 试图承接已耗尽的 Gate
- **WHEN** carry 的来源 Gate 状态为 exhausted
- **THEN** 草稿创建被拒绝，提示只能 retire

### Requirement: 替换后的返工历史与预算
替换修订 SHALL 记录 `history_boundary` 为草稿创建时返工记录的最大轮次，后续普通修订与安全扩张 SHALL 继承该边界。重试计数、返工记录校验与 priorAttempts SHALL 只使用边界之后的记录；边界之前的记录 SHALL 原地保留并在历史中展示。确认时若存在边界之后的新记录 SHALL 拒绝。

#### Scenario: 新 Plan 预算从零开始
- **WHEN** 旧修订中 qa 的 on_fail 已消耗 2 次，替换后新 Plan 同名处理者首次失败
- **THEN** 新处理者计数为 1，旧的 2 次记录仍可在 plans history 中查看

#### Scenario: 替换后普通修订保持预算
- **WHEN** 替换后的修订 3 消耗 1 次返工，再普通修订为修订 4
- **THEN** 修订 4 继续统计这 1 次，不清零
