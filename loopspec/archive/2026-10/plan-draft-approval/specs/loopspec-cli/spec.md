> **已被 `plan-replacement` 取代（2.0.0）。** 下列内容以 `loopspec/changes/plan-replacement/design.md` 为准：
> - 草稿不可变快照目录、确认记录目录、`PlanMetadata`/`DraftBinding`/`ConfirmationRecord` 与 Change 格式 3 → 每份 Plan 一个 `plan.yaml`，`meta.status` 为 `draft`/`approved`/`archived`，确认只写 `meta.digest` 与 `meta.approved_at`；Change 级 `.workflow.yaml` 格式 4（D3、D4）。
> - `plans create/show/approve/recompose`、`--expected-digest`、`--message`、`--safety-expansion` → `plan create/show/approve`（`--digest`），修订用 `plan validate -f` 预览、`plan approve -f --digest` 确认（D5、D12）。
> - 确认事务与 `recover --inspect/--resume` → 固定写入顺序、最后一步为生效点，重新执行同一命令收敛（D8）。
> - 一个 Change 只有一份 Plan → 一个 Change 可有多份 Plan、同一时间最多一份未结束；任务变化时经人同意 `plan archive` 后重新规划（D3、D9）。

## MODIFIED Requirements

### Requirement: 四层模型命令面
CLI SHALL 支持现有目录命令以及 plans create/approve/show/history/validate；新默认 new SHALL 只建 Change。所有新命令 SHALL 支持 --home、--json 和安全的 error/message/fix 错误信封；入口 SHALL 不回显不可信原值或 Traceback。

#### Scenario: 创建任务草稿
- **WHEN** 执行 plans create AFD1111 --plan request.yaml
- **THEN** 返回草稿身份、planDigest、规划图、确认阶段及可供展示的规范请求，不激活 Plan

#### Scenario: 查看活动与草稿
- **WHEN** 同时存在活动 Plan 和待确认草稿
- **THEN** plans show 默认展示草稿，--active 展示原活动图，两者响应均明确阶段

### Requirement: 新建与旧接口互斥兼容
新默认 new SHALL 不接受 --plan/--profile/--approval/--expected-digest；--schema SHALL 是明确的旧式入口，不触发新计划批准或旧 Change 自动迁移。

--schema SHALL NOT 覆盖同一新格式 Change 的未规划、草稿或活动绑定，以免绕过明确确认与项目约束。

#### Scenario: 沿用旧一体化参数
- **WHEN** 对 new 使用 --approval 或 --plan
- **THEN** 返回用法或结构化迁移错误，指引先 new、再 plans create/approve，不创建活动 Plan

#### Scenario: 旧入口不能降级新 Change
- **WHEN** 对已有新格式 Change 使用 --schema 尝试复用
- **THEN** 命令拒绝模式重绑，不覆盖原元数据、不通过旧流程跳过确认

### Requirement: 执行结果暴露关键上下文
status/next SHALL 区分规划阶段与 Node 五态，初次待规划/待确认 SHALL 保持 isComplete: false 并返回规划指引。活动计划 SHALL 继续返回计划版本、摘要、规范叶子、引用链与实例汇总；草稿不能被默认为执行图。

#### Scenario: 草稿尚未确认
- **WHEN** next 被调用且没有活动 Plan
- **THEN** 返回展示或创建草稿的指引与等待确认信息，不执行 Node，也不把 approve 当作可自动执行的下一步

### Requirement: 初始化与文档契约
内置目录与初始化 SHALL 支持新生命周期，中英文文档 SHALL 一致描述命令、字段、错误、BREAKING 迁移、确认与业务 Gate 的区别。docs/en SHALL 使用英文，docs/zh SHALL 使用中文。

#### Scenario: 双语示例
- **WHEN** 校验新生命周期文档
- **THEN** 两种语言的命令与执行结构一致，英文正文/示例说明无中文，语言切换标签除外
