# 供人工确认的实施摘要

## 要解决的问题

让 Change 先建立，Plan 再由 LLM 针对任务构建并与人确认；不把选择完整模板或省略保护步骤当作是否需要确认的判断条件，也不在 new 接收审批文件。

## 拟实施流程

new → fragments/profiles 发现 → plans create 保存草稿 → plans show 展示并讨论 → 人明确确认 → plans approve 定稿 → status/next 执行。

所有新 Plan 都需要确认。草稿可以多次调整，但不能作为执行输入。批准使用展示过的缓存与摘要，不偷偷重编译来源。Skill 必须以准确摘要确认，不能自行代批。

## 关键选择与兼容

- new 移除 --plan/--profile/--approval/--expected-digest；显式 --schema 保留旧入口，但不能把同一新格式 Change 降级重绑。
- Profile 保持参考模板定位，移除对外 protected/deviations 审批机制；项目最低保障和 Gate 证据不因统一人工确认而被豁免。
- 后续普通修订与安全扩张也先创建草稿、确认后激活。已有活动图在批准前不被替换，失效旧 QA/Assurance 与新绑定在批准事务中完成。
- 旧 Schema Change 与既有活动 Plan 不自动迁移或补签；不保证旧一体化 new/recompose 自动化参数继续有效，迁移说明明确标记 BREAKING。
- 英文 builtin/skills 与 docs/en、中文 docs/zh；临时目录投影验证，不更新真实 .codex/skills 等安装目录。

## 实施规模和验证

25 项任务，先做生命周期/草稿快照，再接入 create/approve 与执行/修订，最后更新资源、Skill、双语文档并运行负向、并发、事务恢复、临时 Git 端到端与完整回归。

四份规格共 19 条需求、36 个场景。security/pass.md 是设计级通过，不是实现通过；本轮未修改 CLI/Skill 源码，所有实现任务仍待完成。

本轮对现有文档、Skill 模板和投影测试的检查为 88 passed in 1.19s，git diff --check 通过；这些结果不证明尚未实现的新命令可用。

## 人工决定与边界

请明确选择按当前方案实施，或先调整方案。当前没有 approval/approved.md，没有代写决定。

本地 approve 记录明确确认动作，不认证身份；不证明代码审查质量或阻止其他终端提交。项目安全 Gate、最终 Assurance、历史预算及冻结约束继续执行。本变更不包含提交、部署、发布、全局安装或归档授权。
