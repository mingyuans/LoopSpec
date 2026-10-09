# Change State

## Current Focus
- Pending first node.

## Frozen Decisions
- None yet.

## Decision Log
- None yet.

## Rejected Options
- None yet.

## Open Questions
- None yet.

## Artifact Notes
- None yet.

## 用户明确的生命周期要求

- 2026-10-06：new 只创建 Change；之后 LLM 查看 Fragments/Profiles、针对任务创建草稿 Plan，与人类确认后调用 plans approve 定稿。
- 当前变更：plan-draft-approval，采用现有 secure-spec-driven 兼容入口记录实施需求；新 commands 尚未实现，不能把记录本次变更的旧入口当作新生命周期已经交付。
- 冻结方向：所有新 Plan 统一确认，不再从 new 接收审批文件；Profile 是参考模板，项目最低保障与 Gate 证据仍独立校验。
- 语言与范围：需求材料中文，docs/en 与 builtin/skills 英文，docs/zh 中文；不改真实安装投影，不动既有用户修改。
- 当前关注：编写设计、规格与任务，执行设计安全复审，随后停在实际人工确认节点，不能代写批准结果。

## 设计与规格完成

- design.md 明确 new、plans create、plans show、plans approve 的分工，草稿不可执行、首次确认与修订确认，以及并发/摘要/项目政策/事务边界。
- 新增 workflow-plan-approval 规格，并更新 workflow-planning、loopspec-cli 与 lpsx-skills；原已完成变更及其报告不被重写。
- 冻结方向：草稿自包含且不可变；批准消费展示的缓存，不重编译来源；确认固定资源、基线及失效影响，不能豁免项目最低要求。
- 当前关注：形成可验证的实施任务并做设计安全复审；本轮仍未实现新 CLI，未批准自己的实施计划。

## 实施任务已形成

- tasks.md 按模型/快照、草稿命令、明确确认、执行/修订、Skill/文档、验证分组；实现任务尚未开始，不能将材料完成误记为代码完成。
- 所有可能激活 Plan 的入口，包括普通修订、安全扩张和事务恢复，必须区分草稿与已确认活动配置，并且确认不能替代 Gate。
- 下一步：按当前 security 节点指令对完整材料做设计复审，再呈现真实人工确认选项。

## 设计安全复审通过，待实际人工确认

- security/pass.md 为设计级 PASS，不代表代码已经实现或测试通过；没有生成 approval/approved.md 或实施报告。
- 复审收紧：旧 --schema 不得将同一新格式 Change 降级/重绑；message 为有界可选数据，不提供额外权限，不记录秘密或推断身份。
- 已有草稿、项目政策、基准和修订失效影响须摘要绑定并复核；恢复不能批准未确认草稿；项目 Gate 与预算不能靠批准豁免。
- 当前关注：停在现有工作流的 approval 节点，把实施方向、待实现命令和兼容选择呈现给用户，等待真实决定。

## 评审摘要与当前检查

- review.md 已整理命令流程、所有 Plan 统一确认、草稿/活动区分、修订确认、旧兼容与 25 项任务顺序；四份规格包含 19 条需求、36 个场景。
- 当前检查：现有文档/Skill/投影专项 88 passed in 1.19s，git diff --check 通过。仅验证本轮规划没有破坏既有材料约束，不声称新命令已实现。
- 当前状态：approval ready、apply blocked，25 项实施任务未完成。等待实际人类决定，不自行生成批准或要求修改记录。

## 人工审批第 1 轮：批准实施

- Decision Log：用户明确批准 plan-draft-approval 的当前方案，原话见 approval/approved.md。
- Frozen Decisions：new 只建 Change，全部新 Plan/修订先存草稿，经真实人工确认后 plans approve 定稿；草稿不能执行，精确摘要和项目约束不可绕过。
- Frozen Decisions：保留旧 Change 执行兼容，禁止旧入口降级新格式 Change；预算、冻结链、代码 Gate 与全量保障保持，批准激活事务可恢复。
- Frozen Decisions：英文 builtin/skills 与 docs/en、中文 docs/zh，不刷新真实安装目录，不提交、发布或自动归档。
- Artifact Notes：approval/approved.md 已按用户真实决定建立；此前等待确认保留作历史。
- Current Focus：从任务 1.1 开始逐项实现，完成后立即打勾，并记录实际测试与复审结果。

## 生命周期、确认与修订实现

- 已实现版本 3 Change 元数据、独立不可变草稿、版本 2 Plan 摘要；旧活动快照仍验证原摘要，不自动补审批。
- new 只建 Change；plans create/show/approve、草稿优先展示与 --active、未批准 status/next 规划输出已接通。执行只加载活动快照，初次未批准执行/归档被拒绝。
- 确认消费缓存并复核项目政策、原基线、冻结边界与恢复预算。recompose 改为草稿别名；失效归档、确认见证和活动绑定切换共用可恢复事务。
- 恢复验证需求/摘要链、明确确认记录、归档源与目标摘要，以及全部仍存在的失效产物，不能经 recover 激活无确认草稿或移动业务代码。
- builtin/skills 英文源、Profile 模板与双语文档已同步，未修改真实安装目录或用户 AI-DLC 工作；旧 Schema 回归通过显式 --schema 进入。

## 验证进度与真实失败记录

- 初轮确认/生命周期/模型专项：52 passed in 12.28s；最新文档/Skill/临时投影/CLI/旧状态专项：206 passed in 15.99s。
- 首轮完整测试在文档更新尚未完成时启动，结果为 4 failed、965 passed in 377.68s；失败均是新命令 create/approve 缺少双语文档章节的契约检查，已补齐并专项验证。
- 旧专项首轮另有预期错误文本和 tracked Schema 夹具选错旧入口的失败；已修正夹具/断言，不恢复默认 new 的旧行为。
- make lint 首次因沙箱不能读取既有 uv 缓存失败，获准读取后通过：ruff 全通过，mypy 49 source files 无问题；未安装新依赖。
- 完整回归使用 env -u NO_COLOR，避免外部 NO_COLOR 设置影响原终端颜色测试；不改产品显示逻辑。make test 沙箱首次遇到同一缓存权限问题，已获准重跑。
- 当前关注：等待完整回归结果，完成实施安全复审，再形成真实实施报告；尚未写 PASS 实施报告。

## 最终验证与交付完成

- 最终 env -u NO_COLOR make test：977 passed in 359.73s (0:05:59)；make lint：ruff 全通过，mypy 49 source files 无问题；文档/Skill/投影专项：89 passed in 3.03s；git diff --check 通过。
- 新恢复遗漏产物测试首轮因模拟函数未复原失败，修正后单项通过，最终完整回归包含该场景并通过；中间实际失败和缓存权限重跑均写入 apply/report.md。
- 四份隔离投影通过 Skill 创建规范校验；临时 AFD1111 的 unplanned/draft next 均无执行叶子、isComplete false、不自动导航批准。
- security/implementation-review.md 已记录代码边界复审、修订影响完整性与本地同权限信任边界；没有把本地记录宣传为认证或审查质量证明。
- tasks.md 已完成 25/25，apply/report.md 记录真实实施、文件、测试、兼容与工作保护。没有写 apply/blocked.md，没有提交、发布、刷新真实安装或归档本需求。
- 当前关注：本次批准实施已完成，交付源码与文档；后续安装/提交/归档需要另行明确操作。

## 被 plan-replacement 取代

- Decision Log：2.0.0 的 `plan-replacement` 变更删除旧 Schema 流程并重做持久化、确认、修订与命令树；本需求 design.md 与 specs 顶部已标注被取代的决策与需求，以 plan-replacement 为准。实现代码已按新设计替换。
