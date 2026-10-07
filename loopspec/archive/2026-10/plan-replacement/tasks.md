## 1. 测试计划与模型

- [x] 1.1 编写测试计划（范围、用例、类型、验收标准），覆盖 design D3–D12 与旧 Schema 流程删除，取得用户确认后再开始编码。
- [x] 1.2 新增 Change 级状态模型（format_version 4：baseline、repository、active_plan、open_plan、next_plan）与推导函数（unplanned/planning/active/complete/interrupted）；format_version 3 与旧 Schema Change 返回 unsupported_format。
- [x] 1.3 新增 plan.yaml 模型（meta：plan、status（draft/approved/archived）、revision、digest、approved_at、note、created、archived_at、archive_note；spec：based_on、flow、nodes），spec 规范摘要与加载时完整性校验（plan_integrity）。
- [x] 1.4 【安全】Change 名、Plan 编号（三位数字）与节点实例路径用固定正则校验后才拼接路径；-f 请求文件限制在 Home 内；所有读写沿用目录描述符访问且不跟随符号链接。
- [x] 1.5 精简 config.yaml 模型为 artifacts_dir 与 workflow（required_fragments、assurance_rules、generated_dirs），拒绝 schema、schemas、schema_selection、context、rules、default_profile。

## 2. 编译与 on_fail

- [x] 2.1 编译结果写入精简 spec：删除 baseline、repository、engine_version、instances、project、resources、reasons；成员树改为由 nodes 推导。
- [x] 2.2 on_fail 编译下放：引用节点与 flow 条目的 on_fail 下放到范围内每个 Gate，reset 展开为叶子；同一 Gate 多条时报 on_fail_conflict。
- [x] 2.3 删除能力版本：min_engine_version、编译器 engine_version 参数、unsupported_capability；删除 manual-v1 Profile 与 delivery-review Fragment。
- [x] 2.4 删除受保护步骤：Profile protected、请求 deviations、protected_omissions/bindings、legacy_protection、workflow_approval.py、requiresApproval/readyToApply；删除 reasons 必填校验。
- [x] 2.5 项目约束改为在 plan create 与 plan approve 时按当前 config.yaml 检查，执行期读取最新配置；指令、模板与保障规则执行时读取最新内容。

## 3. 命令树与 Plan 生命周期

- [x] 3.1 重写 cli.py 为 `loopspec <资源> <动作>` 命令树（change、plan、node、gate、fragment、profile）与参数约定（-c、-p、-n、-f、--digest、--note）；工作流命令统一输出 JSON 与错误信封；保留 version 与 init 的人类可读输出。
- [x] 3.2 change new/status/next：创建 format_version 4 Change；status 返回 Change 状态、活动 Plan、节点状态、历史 Plan 摘要与 nextSteps；没有活动 Plan 时执行类命令返回 plan_not_active 与下一步。
- [x] 3.3 plan validate -c -f：只读编译与检查，不写文件；无 approved Plan 时返回编译结果与约束检查；有 approved Plan 时按修订执行冻结校验并返回新摘要、新增实例与将重新执行的节点。
- [x] 3.4 plan create -c -f [--note]：无未结束 Plan 时新建 draft Plan，首次创建时固定 Change 基线与仓库；已有 draft 时覆盖 spec；已有 approved Plan 时拒绝并提示 plan validate/approve -f 或 plan archive。
- [x] 3.5 plan show/list：show 展示未结束或指定 Plan 的 meta、spec、digest 与基线；list 列出全部 Plan。
- [x] 3.6 plan approve -c -p [-f] --digest：确认 draft Plan，或重新编译并比对摘要后确认修订；删除 --message。
- [x] 3.7 【安全】plan archive -c -p [--note]：适用于 draft 与 approved，置为 archived 并清空相应指针，不触及 Plan 目录内运行时数据与业务代码；删除 discard 与 discarded 状态。
- [x] 3.8 change history/artifacts：history 列出活动或指定 Plan 的 .attempts/ 重做记录；artifacts 按 Plan 编号列出产物。
- [x] 3.9 change archive [--force] [--dry-run] 与 --all [--older-than]：默认只归档 complete 的 Change 并复核证据；--force 归档未完成 Change 并标明；删除 --exhausted、--include-pending-failures 与 bulk-archive 命令。

## 4. 中断收敛

- [x] 4.1 按 design D8 固定 plan create、plan approve（draft 与修订）、plan rollback、plan archive 的写入顺序，最后一步为生效点；所有写入在逐 Change 写锁内完成。
- [x] 4.2 实现“只做了一半”的识别：change status 返回 interrupted 与需要重新执行的命令；执行类命令拒绝推进；重新执行同一命令补完剩余步骤，不新建记录、不重复计次。
- [x] 4.3 【安全】重做记录先写待归档清单与摘要；重新执行时按摘要核对，目标内容不符返回 history_integrity；只允许归档 Plan 目录内的工作流路径。
- [x] 4.4 删除 .transaction.yaml、recover 命令与确认、返工、修订三套旧事务实现。

## 5. 运行时、修订与返工

- [x] 5.1 运行时根改为活动 Plan 目录：产物、.gates、.gate-rounds、.attempts 相对 Plan 目录解析；node instructions -c -n 只作用于活动 Plan。
- [x] 5.2 【安全】Diff 使用 Change 级 baseline 并核对 repository；控制目录排除改为 Change 根下 .workflow.yaml、state.md 与整个 plans/，加上 config.yaml 的工具生成目录，拒绝业务目录排除。
- [x] 5.3 plan rollback -c -p 只按失败 Gate 自身的 gate.on_fail 执行，次数按 Plan 内 Gate ID 统计 kind: rollback；删除处理链排序、传播层级、共享次数与处理者 ID。
- [x] 5.4 修订冻结规则：冻结节点不能删除、改名或改执行定义，requires 只能增加；增加依赖的冻结节点及下游在确认时归档到 .attempts/<序号>/（kind: revision）并重新执行；有效 FAIL 必须在重新执行范围内；删除安全扩张模式。
- [x] 5.5 重做记录作为 priorAttempts 提供给重跑节点并标注为不可信数据；有返工记录的 Gate 修订时不能改名或删除。
- [x] 5.6 gate begin/record 改用 -c -n；保障节点通过 gate record 执行确定性检查并写出系统 PASS/FAIL，只接受活动 Plan 的有效证据；删除 assurance check 命令。
- [x] 5.7 删除快照、草稿与确认记录存储：PlanMetadata、DraftBinding、ConfirmationRecord、Manifest、materialize/暂存/.unactivated-* 处理、workflow_drafts.py、activate_plan 与 Plan 版本 1/2 分支。

## 6. 删除旧 Schema 流程

- [x] 6.1 删除旧流程模块：schema_loader.py、legacy_workflow.py、instructions.py、rollback.py、attempts.py、state.py、gate_outcome.py、outputs.py、policy.py、graph.py、task_tracking.py、status_report.py、artifacts.py、change_state.py、config.py；删除 models.py 中的旧 Schema 模型；删除 workflow_cli.py 中回退旧流程的分支；清理 errors.py 中只服务旧流程的错误码。
- [x] 6.2 删除 builtin/schemas/ 与 init 的 Schema 复制、schemas/ 目录创建和 --no-builtin；init 摘要不再显示 Schema 名。
- [x] 6.3 删除旧流程的全部测试（schema、旧 status 报告、跨 Schema 产物、旧 instructions/rollback/archive 等）。
- [x] 6.4 删除 docs/{zh,en}/schema-reference.md 与 docs/{zh,en}/workflows/secure-spec-driven.md，并清理概览、配置、CLI 参考、Agent 协议与 README 中的旧流程内容。
- [x] 6.5 将版本提升为 2.0.0，编写 release notes：旧 Schema Change 不再支持、升级前用 v1.x 完成归档、config.yaml 需删除的字段、命令树变化。
- [x] 6.6 处理因旧流程删除而失去意义的变更：add-schema-sources（只有方案、未实现）与 artifacts-command（已实现于 v1.0.3），处理方式经用户确认后执行。

## 7. 内置资源、Skill 与文档

- [x] 7.1 内置 Fragment/Profile 去掉 min_engine_version；Profile 中的 on_fail 保持在 flow 条目；确认编译后无 on_fail_conflict。
- [x] 7.2 更新 builtin/skills 的 new、continue、archive、bulk-archive：使用新命令树；完整任务规划与 --note；请求先 plan validate 检查，修订用 plan validate -f 预览再 plan approve -f；任务变化先取得人同意再 plan archive；归档 Skill 使用 change archive 与 --all，--force 只在用户明确要求时使用。
- [x] 7.3 更新 docs/{zh,en} 的概览、工作流组合、Agent 协议、配置与 CLI 参考：两套层级、两级状态、plan.yaml 示例、修订与重新规划、中断后重新执行、命令树、实时资源与配置的取舍、本地记录不认证身份。
- [x] 7.4 同步修订 dynamic-workflow-composition 与 plan-draft-approval 的设计与规范中被本变更替代的内容。

## 8. 验证

- [x] 8.1 端到端（临时 Git 仓库）：change new → plan create/show/approve → 执行与返工 → 同一 Plan 内修订（含补后端使保障重新执行）→ 任务变化 plan archive 并重新规划 → 新 Plan 从空状态开始且沿用 Change 基线 → 保障通过 → change archive。
- [x] 8.2 中断收敛：plan create、plan approve（draft 与修订）、plan rollback、plan archive 在每个写入步骤之后中断，change status 返回 interrupted，重新执行同一命令后状态与一次完成相同，且任何时刻只有一个 approved Plan。
- [x] 8.3 负向：手改 plan.yaml、过期摘要确认、无活动 Plan 时执行、指定非活动 Plan、修订改写冻结节点或绕过有效 FAIL、on_fail 重叠、归档清单含业务路径或摘要不符、format_version 3 与旧 Schema Change、旧字段（protected、min_engine_version、reasons、recovery、schema）。
- [x] 8.4 运行完整 pytest、ruff、mypy 与双语文档契约检查并修复失败。

## 9. 去掉中断状态（2026-10-07 用户确认的设计调整）

- [x] 9.1 Change 级 `.workflow.yaml` 去掉 active_plan、open_plan、next_plan；未结束与活动 Plan 由各 plan.yaml 的 status 推导，新编号为已有 plan.yaml 最大编号加 1；多于一个未结束 Plan 返回 history_integrity。
- [x] 9.2 plan create/approve/archive 改为单一生效写入（create 首次先固定基线，再写 state.md，最后 plan.yaml）；删除 interrupted 状态、interrupted 错误码与中断识别。
- [x] 9.3 【安全】rollback 以 record.yaml 为生效点；修订先写记录、再替换 plan.yaml（生效点）、最后归档；未生效的 revision 记录不计入历史与 priorAttempts，重新确认时复用或覆盖；已生效记录中未搬走的源文件在推导状态时视为不存在。
- [x] 9.4 【安全】node instructions、gate、plan rollback/approve/archive、change archive 在写锁内先按记录摘要补完未搬走的文件；摘要不符返回 history_integrity。
- [x] 9.5 测试：每个写入点中断后状态等于之前或之后、Agent 按 nextSteps 继续即可完成、返工不重复计次、补完时篡改返回 history_integrity；更新 Skill（continue、archive、bulk-archive）与 docs/{zh,en} 中的 interrupted 内容；运行 make test 与 make lint。

