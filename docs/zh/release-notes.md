# 版本说明

> 覆盖范围：LoopSpec 2.0.0 的变化以及如何从 1.x 升级。
> 适用读者：升级已有安装或工作区的用户。
> 语言：**中文** · [English](../en/release-notes.md)

## 未发布

### 工作流命令自动同步项目 skill

- 接受 `--home` 的命令执行前，自动把项目中已配置 AI 工具的 loopspec skill/command 文件同步到当前 CLI 内置版本（过期的覆盖、缺失的补上），结果打印到 stderr；升级 CLI 后不再需要重新执行 `loopspec init` 刷新 skill。
- 与 CLI 内置内容一致的 skill/command 文件固定不计入交付 Diff。

### 归档改为两段式并强制 memory 审阅

- `loopspec change archive <change>`（或 `--all`）只做复核并返回 `archiveId` 与 memory 审阅指引，不再直接归档；用 `loopspec change archive --confirm <archiveId> --memory updated|none --note <说明>` 完成归档。CLI 核对 memory 是否与选择一致，并把审阅结论写入 Change 的 `state.md`。
- 删除 `--dry-run`（第一段即预览）。依赖旧用法的脚本需要改为两段；项目中的归档 skill 会在下一条工作流命令执行时自动同步。
- 归档时同时删除 `.attempts/`、`.gates/`、`.gate-rounds/` 与 Gate 的 PASS/FAIL 报告；结果字段为 `dropped`/`notDropped`。

### registry 模式：定义改存全局存储

- 配置了 `registry` 的项目不再把 fragments/profiles 写进项目。定义按「来源 + commit」存放在 `$LOOPSPEC_REGISTRY_STORE`（默认 `~/.loopspec/registry`），项目只提交 `config.yaml` 与 `registry.lock.yaml`。
- 新 clone 或新 worktree 读取定义时，按 lock 自动拉取并校验锁定的 commit，无需额外命令。
- `registry.lock.yaml` 升级为 `version: 2`（`commit`、`tag`、`files`）；`registry apply` 只写 lock，删除 `--resolve` 与 `--skip`，不再有本地三方合并。
- 项目内与 registry 同名的定义返回 `registry_local_conflict`；名称不同的本地定义继续可用，`fragment list`/`profile list` 新增 `source` 字段。
- registry 模式下 `loopspec init` 不复制内置定义。
- 迁移：删除项目内与 registry 同名的定义，运行 `registry update` 与 `registry apply`，提交删除与新的 lock（见[配置](configuration.md)）。

## 2.0.0

2.0.0 与 1.x 不兼容。基于 Schema 的工作流已删除；所有 Change 都由 Fragment 与 Profile 组合出的 Plan 驱动。

### 不兼容变化

- **删除 Schema 工作流。** `loopspec schemas ...`、`builtin/schemas/` 与 `secure-spec-driven` Schema 已删除。1.x 创建的 Change（`.workflow.yaml` 含 `schema`）或开发版本创建的 Change（format 3）返回 `unsupported_format`。
- **命令树。** 命令改为 `loopspec <资源> <动作>`：`change`、`plan`、`node`、`gate`、`fragment`、`profile`。平铺命令（`new`、`status`、`next`、`instructions`、`rollback`、`history`、`artifacts`、`archive`、`bulk-archive`）、复数分组（`plans`、`fragments`、`profiles`）、`assurance check` 与 `recover` 已删除。参数显式指定：`-c/--change`、`-p/--plan`、`-n/--node`、`-f/--file`、`--digest`、`--note`。
- **只输出 JSON。** 工作流命令总是输出 JSON，不再接受 `--json`；`version` 与 `init` 保留人类可读输出，并支持 `--json`。
- **config.yaml。** 只接受 `artifacts_dir` 与 `workflow`（`required_fragments`、`assurance_rules`、`excluded_paths`）。`workflow.generated_dirs` 已删除：把其中的名称原样移到 `excluded_paths`。删除 `schema`、`schemas`、`schema_selection`、`context`、`rules` 与 `workflow.default_profile`。
- **init。** 不再创建 `schemas/`，删除 `--no-builtin`；只补齐缺失的 Fragment 与 Profile，不覆盖已有文件。
- **归档。** `change archive` 取代 `archive` 与 `bulk-archive`（`--all`、`--older-than`）；`--force` 取代 `--exhausted` 与 `--include-pending-failures`。

### 新增

- 一个 Change 可有多份 Plan，同一时间最多一份未结束；重新规划需经人同意归档旧 Plan，并在同一基线上从空状态开始。
- 每份 Plan 一个 `plan.yaml`（`meta` + `spec`），带摘要完整性校验；产物、证据与重做记录按 Plan 隔离。
- 原地修订：`plan validate -f` 预览，`plan approve -f --digest` 确认。
- 每条命令只有一次生效写入：命令中断后 Change 要么是之前、要么是之后的状态，不再有事务文件、恢复命令或中断状态。
- `workflow.excluded_paths` 按名称或完整路径把任意路径排除出 Diff；被 Git 忽略但未排除的路径只作为告警写进保障报告，不再中止命令。
- 证据摘要只绑定基线与工作树中的交付内容，不再包含暂存区：Gate 通过后执行 `git add` 或 `git commit` 不会让证据失效；在基线之后提交再继续修改也不再报 `index_worktree_mismatch`；但 HEAD 中既不是基线也不是工作区内容的提交会使保障判 FAIL（`diverged_commits`），交付前需提交最终内容。此前开发版本记录的代码 Gate 与保障证据会失效，需要重跑。
- `on_fail` 编译进每个 Gate；每个 Gate 一条策略，冲突即报错。
- `nextSteps` 列出全部就绪叶子，`parallel: true` 表示这些步骤互相独立、可以并行（例如每个节点一个 sub agent）；`change next` 新增 `nodes`。

### 升级步骤

1. 升级前用 LoopSpec 1.x 完成并归档进行中的 1.x Change。2.0.0 不迁移它们；未完成的工作用 `loopspec change new` 重新建立并规划。
2. 删除 `config.yaml` 中的 1.x 字段；工作区中的 `schemas/` 不再读取，可以删除。
3. 执行 `loopspec init --tools <你的工具> --update-resources`，补齐内置 Fragment 与 Profile 并刷新 Skill。
4. 按仓库实际目录调整代码审查 Fragment 的 `evidence.paths` 与 `change-assurance/rules.yaml` 的 `paths`。
