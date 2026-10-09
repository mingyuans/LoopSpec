# Security Review: PASS

## Scope Reviewed

- `design.md`（最终版）D1–D14：重点是 D3 Change 级状态与基线、D4 `plan.yaml` 完整性与实时资源/配置、D5 修订冻结规则、D7 运行时根与 Diff 控制目录、D8 中断后重新执行的写入顺序、D11 删除清单（含旧 Schema 流程）、D12 命令树与参数、D13 不兼容发布与迁移、D14 安全边界。
- `tasks.md` 全部 8 组 43 项，重点核对标注【安全】的 1.4、3.6、4.3、5.2，以及删除旧流程的第 6 组。
- 涉及的现有代码：`workflow_io.py`（目录描述符访问、原子写入、写锁、不跟随链接）、`workflow_yaml.py`（严格 YAML）、`workflow_diff.py`/`workflow_git.py`（固定基线、控制目录排除、无 Shell 的 Git 调用）、`workflow_evidence.py`/`workflow_assurance.py`（两步证据与保障）、`workflow_recovery.py`（将改为按记录重新执行的归档逻辑）、`cli.py`（将重写为新命令树）、`paths.py`（工作区与 Change 路径解析）。
- 第一轮审批意见（priorAttempts）均已在 design 中落实；之后的两轮讨论结论记录在 state.md。

## Checks Performed

- **注入**：不新增 Shell、SQL 或模板执行；Git 调用沿用无 Shell 参数数组与禁用外部驱动的实现。删除旧流程不引入新的执行路径。
- **不可信输入解析**：`plan.yaml`、请求文件、`config.yaml`、Fragment/Profile 与重做记录均走严格 YAML 与 strict 模型；已删除字段（protected、deviations、min_engine_version、reasons、recovery、schema 等）按未知字段拒绝，不会被静默忽略。
- **路径穿越**：新命令的 `-c`、`-p`、`-n` 都用固定正则校验后才拼接路径（Plan 编号限定为三位数字）；`-f` 请求文件限制在 Home 内；读写沿用目录描述符且不跟随符号链接（1.4）。
- **业务代码保护**：返工与修订先写含文件清单与摘要的重做记录，只允许归档 Plan 目录内的工作流路径；重新执行时按摘要核对，不符则返回 `history_integrity` 而不覆盖（D8、4.3）。`plan archive` 只改状态，不移动 Plan 目录内文件（3.6）。
- **原子性与中断**：所有写入在逐 Change 写锁内完成，每个文件原子替换；生效点固定为最后一步，活动指针在 `.workflow.yaml` 中最后写入，中断不会产生两个 approved Plan；中间状态由 `change status` 报告为 interrupted，执行类命令拒绝推进直到重新执行收敛（D8、4.1、4.2）。
- **授权与流程绕过**：初次规划、重新规划与修订都需 `--digest` 绑定人看到的内容；没有活动 Plan 时执行类命令返回 `plan_not_active`；修订不能删除、改名或改写冻结节点，有效 FAIL 必须落在重新执行范围内；保障节点只接受活动 Plan 的证据且只能由系统写出 PASS；所有 Plan 共用 Change 固定基线，重新规划不能遗漏已有改动（D3、D5、D7）。
- **Diff 完整性**：控制目录排除限定为 Change 根下精确路径、`plans/` 与配置声明的工具生成目录，拒绝把业务目录声明为生成目录（5.2）。
- **旧流程删除**：旧 Change 返回 `unsupported_format`，不尝试解析或迁移旧格式数据，避免在兼容代码中残留未维护的解析路径；`init` 不再复制 Schema。
- **只读预览**：`plan validate` 只编译与检查请求文件，不写任何文件；修订仍须经 `plan approve -f --digest` 重新编译比对摘要后才生效。
- **反序列化、密钥、依赖**：无任意对象构造；不新增密钥、网络访问或第三方依赖。

## Notes

以下为非阻塞的残余风险与实现注意事项：

1. **实时资源与配置会立即生效**：指令、模板、保障规则与 `config.yaml` 执行时读取最新内容，修改（包括放宽保障规则或 `required_fragments`）会立即影响正在执行的 Plan，且没有确认时的配置快照比对。这是设计明确接受的取舍；文档需提示这些文件的变更应按项目规则审查，可选在 CI 中保护。
2. **本地完整性边界**：`meta.digest` 与重做记录中的摘要只能发现意外或不一致的修改；拥有本地写权限的人可以同时改 `spec` 与摘要，或改写重做记录中的清单。实现时重新执行前应校验记录中的每个路径仍在 Plan 目录工作流路径内、序号符合固定格式；文档继续如实说明本地记录不认证身份、不构成防篡改边界。
3. **人工同意由 Skill 约束**：`plan archive`（approved Plan）与 `change archive --force` 的“先取得人同意”只能由 Skill 规则约束，CLI 无法验证调用者是人；Skill 文案需明确禁止自行调用。
4. **删除受保护步骤后的最低保障**：项目最低要求只由 `config.yaml` 的 `required_fragments` 与保障规则提供；需要强制非代码步骤（如文档评审）的项目应通过 `required_fragments` 声明。
5. **不兼容发布**：旧 Schema Change 在 2.0.0 中不可执行。release notes 与 `unsupported_format` 的纠正指引需明确“用 v1.x 完成归档”，避免用户误以为数据丢失而手工修改元数据。
