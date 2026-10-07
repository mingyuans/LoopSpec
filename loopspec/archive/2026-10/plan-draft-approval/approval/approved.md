# 人工审批：批准实施

## 向人呈现的方案

- new 只建 Change；随后选择 Fragment/Profile，通过 plans create 保存任务草稿，与人确认后 plans approve 定稿，再进入 next。
- 所有新 Plan 与修订都需确认；不再由模板偏离决定是否审批，不在 new 接收审批文件。
- 草稿自包含不可执行，精确摘要防止确认期间替换；项目最低保障、Gate 证据、冻结链、预算与安全扩张约束保持。
- 25 项任务依次实施模型/草稿快照、命令、明确确认与事务、执行/修订、资源/英文 Skill/双语文档及完整验证。
- 设计级安全复审通过；同权限本地记录不构成身份认证。旧 Change 不自动迁移，旧 --schema 不能覆盖新格式 Change。
- 只修改 builtin/skills 英文源，不刷新真实本地/全局安装目录；不包含提交、发布或归档授权。

## 人工原话

> approve

## 非阻塞建议

无新增附加条件。

## state.md 回写

- Decision Log：第 1 轮，批准实施；原话以本文件为准。
- Frozen Decisions：以上流程、确认与执行边界、兼容/安全约束、语言及安装目录范围。
- Artifact Notes：approval/approved.md 为通过记录，开始逐项实施，不代写 Gate 验证结果。
