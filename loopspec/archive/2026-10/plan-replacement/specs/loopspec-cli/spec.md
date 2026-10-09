## MODIFIED Requirements

### Requirement: 四层模型命令面
CLI SHALL 统一为 `loopspec <资源> <动作>`，提供：`version`、`init`；`change new/status/next/history/artifacts/archive`；`plan validate/create/show/list/approve/archive/rollback`；`node instructions`；`gate begin/record`；`fragment list/show/validate`；`profile list/show/validate/save`。参数 SHALL 为：`-c/--change` 指定 Change（change 组以位置参数给出），`-p/--plan` 指定 Plan 编号，`-n/--node` 指定节点或 Gate，`-f/--file` 指定请求文件，`--digest` 绑定确认内容，`--note` 可选说明。工作流命令 SHALL 统一输出 JSON，失败时为统一的 error/message/fix 信封与非 0 退出码。plan validate SHALL 只读，SHALL NOT 写任何文件；存在 approved Plan 时 SHALL 按修订返回预览。CLI SHALL NOT 提供 schemas、assurance check、recover、plans recompose、plans discard、--safety-expansion 与 --message。

#### Scenario: 修订预览
- **WHEN** 存在 approved Plan 时执行 plan validate -c AFD1111 -f revision.yaml
- **THEN** 返回 planDigest、flow、nodes、新增实例与将重新执行的节点，且不写入任何文件

#### Scenario: 查看重做记录
- **WHEN** 执行 change history AFD1111 -p 001
- **THEN** 返回 Plan 001 的 rollback 与 revision 记录，含来源 Gate、重置节点与归档文件

#### Scenario: 校验失败
- **WHEN** 配置、路径、图或冻结规则不合法
- **THEN** 命令返回结构化错误和纠正指引，不显示未处理 Traceback

### Requirement: 新建与旧接口互斥兼容
`change new <change>` SHALL 只创建 format_version 4 的 Change，SHALL NOT 接受 --schema。读取到旧 Schema Change 或 format_version 3 的 Change 时 SHALL 返回 unsupported_format 与处理指引，SHALL NOT 自动迁移。

#### Scenario: 旧 Change
- **WHEN** 对 v1.x 用 Schema 创建的 Change 执行 change status
- **THEN** 返回 unsupported_format，提示用 v1.x 完成归档或重新建立

### Requirement: 执行结果暴露关键上下文
`change status`、`change next` 与 `node instructions` SHALL 返回 Change 状态（unplanned/planning/active/complete）、活动 Plan 编号、revision、planDigest、实际叶子 Node 规范身份、所属实例与引用链、引用节点汇总状态、证据状态、历史 Plan 摘要和确定性 nextSteps；就绪引用 SHALL 导航到实际叶子指令。没有活动 Plan 时执行类命令 SHALL 返回 plan_not_active 与下一步。plan rollback SHALL 展示来源 Gate、重置节点与重置实例，SHALL NOT 返回处理者、传播层级或 routeCase。

#### Scenario: QA 返工指引
- **WHEN** qa/test 记录有效 FAIL，其 gate.on_fail.reset 包含 be 与 fe 的叶子
- **THEN** nextSteps 指向 plan rollback，后续 node instructions 包含失败报告与必须重跑的 BE、FE Gate

#### Scenario: 无活动 Plan
- **WHEN** Plan 001 已归档且尚未建立新 Plan，执行 node instructions -c AFD1111 -n be/code/implement
- **THEN** 返回 plan_not_active，nextSteps 提示 plan create

### Requirement: loopspec init 初始化 workflow home
`loopspec init [path] [--tools TOOLS] [--project-root DIR]` SHALL 在指定路径（缺省为 `./loopspec`）创建 workflow home，包含 `config.yaml`（含默认 `artifacts_dir: changes` 与空的 `workflow` 段）、`fragments/`、`profiles/` 与 `changes/`，并复制缺失的内置 Fragment 与 Profile，不覆盖已有内容；SHALL NOT 创建 `schemas/` 或复制 Schema，SHALL NOT 提供 `--no-builtin`。`--tools`、交互式欢迎屏与工具选择器、工具脚手架写入项目根、人类可读摘要与 `--json` 行为 SHALL 保持原有规则，摘要中的配置文件状态行 SHALL NOT 再显示 Schema 名。

#### Scenario: 默认初始化
- **WHEN** 执行 `loopspec init ./loopspec`
- **THEN** 生成 config.yaml、fragments/、profiles/、changes/，fragments/ 与 profiles/ 下包含内置构件，不存在 schemas/

#### Scenario: 非交互且未传 --tools
- **WHEN** 在非交互环境下执行 `loopspec init ./loopspec`
- **THEN** 只初始化工作区，不渲染欢迎屏、不启动选择器、不写入任何工具目录

#### Scenario: --tools 传入未注册的工具 id
- **WHEN** 执行 `loopspec init ./loopspec --tools not-a-real-tool`
- **THEN** 命令报错，fix 中列出全部合法工具 id，且不产生任何文件系统变更

## ADDED Requirements

### Requirement: Plan 与 Change 归档命令
`plan archive -c <change> -p <NNN> [--note]` SHALL 返回 Plan 编号、新状态与 Change 状态；`plan list -c <change>` SHALL 列出全部 Plan 的编号、状态、当前修订号、说明与时间；`change archive <change> [--force] [--dry-run]` SHALL 默认只归档 complete 的 Change，`--force` 归档未完成或失败的 Change 并在结果中标明，`--dry-run` 只预览；`change archive --all [--older-than <天数>] [--dry-run]` SHALL 批量归档 complete 的 Change；`change artifacts <change>` SHALL 按 Plan 编号列出全部产物路径。

#### Scenario: 归档活动 Plan
- **WHEN** 对 approved 的 Plan 001 执行 plan archive -c AFD1111 -p 001
- **THEN** 返回 plan 001、status archived、changeStatus unplanned

#### Scenario: 强制归档未完成 Change
- **WHEN** 对 active 但未完成的 Change 执行 change archive AFD1111
- **THEN** 拒绝并提示需要 --force；带 --force 时归档并在结果中标明未完成

## REMOVED Requirements

### Requirement: loopspec status 查看状态
**Reason**: 旧平铺命令与旧 Schema 状态输出删除。
**Migration**: 使用 `loopspec change status <change>`，见“执行结果暴露关键上下文”。

### Requirement: nextSteps 中指向 status 的命令不带 --json
**Reason**: 纯文本状态报告随旧 Schema 流程删除，工作流命令统一输出 JSON。
**Migration**: nextSteps 中的命令按新命令树书写，无需区分 --json。

### Requirement: loopspec artifacts 查看一个 change 的全部产物路径
**Reason**: 跨 Schema 的产物发现随旧 Schema 流程删除。
**Migration**: 使用 `loopspec change artifacts <change>` 按 Plan 编号列出产物。
