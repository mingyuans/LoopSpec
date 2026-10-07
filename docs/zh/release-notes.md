# 版本说明

> 覆盖范围：LoopSpec 2.0.0 的变化以及如何从 1.x 升级。
> 适用读者：升级已有安装或工作区的用户。
> 语言：**中文** · [English](../en/release-notes.md)

## 2.0.0

2.0.0 与 1.x 不兼容。基于 Schema 的工作流已删除；所有 Change 都由 Fragment 与 Profile 组合出的 Plan 驱动。

### 不兼容变化

- **删除 Schema 工作流。** `loopspec schemas ...`、`builtin/schemas/` 与 `secure-spec-driven` Schema 已删除。1.x 创建的 Change（`.workflow.yaml` 含 `schema`）或开发版本创建的 Change（format 3）返回 `unsupported_format`。
- **命令树。** 命令改为 `loopspec <资源> <动作>`：`change`、`plan`、`node`、`gate`、`fragment`、`profile`。平铺命令（`new`、`status`、`next`、`instructions`、`rollback`、`history`、`artifacts`、`archive`、`bulk-archive`）、复数分组（`plans`、`fragments`、`profiles`）、`assurance check` 与 `recover` 已删除。参数显式指定：`-c/--change`、`-p/--plan`、`-n/--node`、`-f/--file`、`--digest`、`--note`。
- **只输出 JSON。** 工作流命令总是输出 JSON，不再接受 `--json`；`version` 与 `init` 保留人类可读输出，并支持 `--json`。
- **config.yaml。** 只接受 `artifacts_dir` 与 `workflow`（`required_fragments`、`assurance_rules`、`generated_dirs`）。删除 `schema`、`schemas`、`schema_selection`、`context`、`rules` 与 `workflow.default_profile`。
- **init。** 不再创建 `schemas/`，删除 `--no-builtin`；只补齐缺失的 Fragment 与 Profile，不覆盖已有文件。
- **归档。** `change archive` 取代 `archive` 与 `bulk-archive`（`--all`、`--older-than`）；`--force` 取代 `--exhausted` 与 `--include-pending-failures`。

### 新增

- 一个 Change 可有多份 Plan，同一时间最多一份未结束；重新规划需经人同意归档旧 Plan，并在同一基线上从空状态开始。
- 每份 Plan 一个 `plan.yaml`（`meta` + `spec`），带摘要完整性校验；产物、证据与重做记录按 Plan 隔离。
- 原地修订：`plan validate -f` 预览，`plan approve -f --digest` 确认。
- 每条命令只有一次生效写入：命令中断后 Change 要么是之前、要么是之后的状态，不再有事务文件、恢复命令或中断状态。
- `on_fail` 编译进每个 Gate；每个 Gate 一条策略，冲突即报错。

### 升级步骤

1. 升级前用 LoopSpec 1.x 完成并归档进行中的 1.x Change。2.0.0 不迁移它们；未完成的工作用 `loopspec change new` 重新建立并规划。
2. 删除 `config.yaml` 中的 1.x 字段；工作区中的 `schemas/` 不再读取，可以删除。
3. 执行 `loopspec init --tools <你的工具>`，补齐内置 Fragment 与 Profile 并刷新 Skill。
4. 按仓库实际目录调整代码审查 Fragment 的 `evidence.paths` 与 `change-assurance/rules.yaml` 的 `paths`。
