# 需求记录

跨 Plan 的背景、边界、重要决策与待解决问题；引擎在末尾追加 Plan 记录。
优先用 `loopspec state add` 追加；`loopspec change status` 原样输出全文，引擎不解析内容。

## 背景

<!-- 问题来源、现状与触发原因。用 `loopspec state add --section background` 追加。 -->
- 2026-11-19 registry 模式下，registry update/apply 会把 fragments/profiles 全量写进项目的 loopspec 目录，文件多且需要提交。若项目把这两个目录 gitignore、只提交 registry.lock.yaml，新 clone/worktree 无法恢复：update 走快速路径直接返回 upToDate；--full 时三方分类把缺失文件判为 local-deleted，apply 不写入；而运行时 resource_text 现场读取 fragment 文件，进行中的 change 会直接失败。

## 目标与边界

<!-- 预期结果、范围与明确不做的事。用 `loopspec state add --section goals` 追加。 -->
- 2026-11-19 registry 模式下，registry 的 fragments/profiles 不再放在项目内，改为维护在用户级全局目录（如 ~/.loopspec）下，按来源和 commit 存放；项目内只保留 config.yaml 中的 registry 配置和 registry.lock.yaml。新 clone/worktree 只凭 lock 即可得到确定版本的定义。不考虑本地修改 registry 定义的场景。非目标：不改非 registry 项目的现有行为。

## 决策

<!-- 重要取舍与确认：`- YYYY-MM-DD [HUMAN: 用户] 内容` 或 `- YYYY-MM-DD [MODEL: BE] 内容`。主体是实际作出决策的人或 Agent 角色，不是代写者。用 `loopspec state add --section decision` 追加。 -->
- 2026-11-19 [HUMAN: xq.yan] 采用方案二：registry 模式下定义存放在用户级全局目录，项目只保留 lock；不考虑本地修改 registry 定义。
- 2026-11-19 [HUMAN: xq.yan] 存量迁移：项目内存在与 registry 同名的本地 fragment/profile 时直接报错，由用户手动删除项目内副本后再使用；不自动清理，也不做本地覆盖。
- 2026-11-19 [HUMAN: xq.yan] Plan 需要独立测试环节：在 be 之后加入 qa-testing，失败退回 be。
- 2026-11-19 [HUMAN: xq.yan] 全局存储缺少 lock 指定 commit 时自动拉取：读取定义时按 lock 的 commit 自动从 registry 拉取并校验 hash，无需显式安装命令。
- 2026-11-19 [MODEL: ENG-claude-remote] Plan 001 design/design：经 Codex 只读评审后采纳 14 条修订（可信文件表、不自动修复损坏快照、项目级写锁、存储根权限、v1 迁移计划、apply 预检含活动 Plan 引用、计划 schema、基线审阅、严格拉取、命令级 bundle 缓存、大小上限、测试补充），不采纳为活动 Plan 持久化资源来源。update 允许写自带 .gitignore 的 .cache/registry/，proposal 验收同步调整。
- 2026-11-19 [HUMAN: xq.yan] Plan 001 完成后的仓库迁移：本仓库 loopspec/ 的 4 个定义含项目路径定制（代码 Gate evidence.paths、change-assurance 规则），新模型不支持本地覆盖，决定本仓库不再使用 registry：去掉 config.yaml 的 registry 并删除 registry.lock.yaml，定义按普通本地项目保留。项目级路径配置能力留待后续。
- 2026-11-19 [HUMAN: xq.yan] Plan 001 完成后追加：全局存储的 source-id 改为「可读前缀 + 短 hash」，形如 <仓库名>[-<path>]-<sha256 前 8 位>，例如 docs-coke-context-channels-loopspec-2d42f67b。

## 待解决问题

<!-- 跨 Plan 仍需追踪的问题；解决或移交时追加新条目并引用原问题。用 `loopspec state add --section open-question --scope change` 追加。 -->

## 参考

<!-- 相关 issue / PR / 讨论 / 产物入口及用途。用 `loopspec state add --section reference` 追加。 -->
- 2026-11-19 用户原始需求（2026-11-19）：开一个 worktree 来做，按方案二，如果项目走的 registry 模式，那么直接将 registry 的 fragment / profile 维护在比如 ~/.loopspec 目录下，不再放原项目内。项目里边只保留 lock。前置讨论见本 Desk 频道上一轮：gitignore fragments/profiles 但提交 lock 的失败路径分析（registry_sync.update 快速路径、classify 的 local-deleted、workflow_runtime.resource_text 运行时读取）。
- 2026-11-19 No relevant memory（loopspec memory list 为空）

## Plan 记录

<!-- 引擎自动追加 Plan 沿革，请勿手工编辑，也勿在此段之后新增段落。 -->
