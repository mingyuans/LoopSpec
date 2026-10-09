## 1. 测试计划与模型

- [ ] 1.1 编写测试计划（范围、用例、类型、验收标准）并取得用户确认后再开始编码。
- [ ] 1.2 RevisionContext 增加 mode（initial/revise/expand/replace）、history_boundary 与 replacement；Plan 快照版本 3；plan_payload 对版本 1/2 保持原摘要方式，版本 2 的 safety_expansion 映射为 mode。
- [ ] 1.3 【安全】新增 replaces 请求模型（reason、reuse、carry、retire）：strict 模型、身份正则、原因长度上限，只允许在 --replace 时出现。
- [ ] 1.4 ConfirmationTransaction 增加 copies（source、target、sha256），默认空以兼容旧事务文件。

## 2. 替换校验

- [ ] 2.1 实现 validate_replacement，与 validate_frozen 并列：固定基线/仓库/项目约束/保障规则不变，引擎版本不降低。
- [ ] 2.2 【安全】校验 reuse：旧节点为 done 且恰有一个输出、新节点 generates 不含通配符、两侧都不是 Gate；记录旧路径与摘要。
- [ ] 2.3 校验 carry 与 retire：有效 FAIL 必须 carry 或所属实例 retire，exhausted 只能 retire，消失的旧实例必须 retire 且原因非空，retire 不能指向仍存在的实例。
- [ ] 2.4 实现替换前覆盖检查：有保障规则时用当前全量 Diff 对照新 Plan 能力提供者诊断，missing_fragments/unknown_paths 返回 coverage_missing。
- [ ] 2.5 计算并记录 history_boundary；plans create --replace 接入 lifecycle.prepare，与 --safety-expansion 互斥，无活动 Plan 时拒绝。

## 3. 暂停与撤销

- [ ] 3.1 由替换草稿推导 suspended；status 返回 suspended 与 pendingReplacement，nextSteps 只指向 plans show。
- [ ] 3.2 实现 require_runnable，在 instructions、next、gate begin/record、rollback、assurance check 返回 plan_suspended。
- [ ] 3.3 【安全】实现 plans discard：写锁内、无事务时清除草稿绑定，校验 --expected-digest，写 .workflow/discards/<draft-id>.yaml，草稿快照保留。

## 4. 替换确认事务

- [ ] 4.1 approve 对替换草稿复核 validate_replacement 且结果与草稿一致；确认时出现边界之后的返工记录则拒绝。
- [ ] 4.2 【安全】moves 覆盖旧 Plan 全部节点的 closure_files；copies 的 source 必须是本事务 moves 目标、target 必须是新 Plan 被 reuse 的产物路径，拒绝其他路径。
- [ ] 4.3 finish 依次执行剩余 moves、按摘要复制 copies（目标已存在时只校验不覆盖）、写审计、切换指针、清除草稿、删除事务；inspect 只读覆盖全部中间状态。

## 5. 历史边界与承接

- [ ] 5.1 attempt_records 按活动 Plan 的 history_boundary 过滤计数、validate_attempt 与 priorAttempts；revise/expand 继承边界。
- [ ] 5.2 instructions 对 carry 目标实例的根节点返回 inheritedFailures（来源修订、Gate、归档报告路径与摘要），标注为不可信数据。
- [ ] 5.3 普通重组改写已完成节点时，node_frozen 错误提示使用 --replace。

## 6. CLI、Skill 与文档

- [ ] 6.1 plans show 展示替换处置、归档文件数、沿用摘要与覆盖结果；plans history 增加 mode、reason、historyBoundary 与各修订返工摘要。
- [ ] 6.2 更新 builtin/skills 的 new（初始 Plan 覆盖完整任务）与 continue（任务变化时构建替换草稿、不得自行 approve/discard）。
- [ ] 6.3 更新 docs/{zh,en} 的工作流组合、Agent 协议与 CLI 参考；说明修订模式边界、默认不继承与本地记录不认证身份。

## 7. 验证

- [ ] 7.1 端到端：执行中任务变化 → 替换草稿 → 暂停 → 确认 → 旧成果归档、沿用复制、新 Plan 唯一活动、业务代码不变。
- [ ] 7.2 中断恢复：快照后、事务写入后、归档中途、复制中途、指针切换后五个中断点，recover --inspect/--resume 均收敛到单一活动修订且幂等。
- [ ] 7.3 负向：缺少处置、承接 exhausted、沿用 Gate、沿用内容被改、覆盖缺失、更换基线、并发替换草稿、复制目标被篡改。
- [ ] 7.4 兼容：版本 2 快照的读取、执行与普通修订；运行完整 pytest、ruff、mypy 与双语文档契约检查。
