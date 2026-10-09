# Implementation Report

## Tasks Implemented

tasks.md 共 44 项，全部勾选。

- **1 测试计划与模型**：1.1 测试计划（test-plan.md，用户确认）；1.2 Change 级状态 format_version 4 与推导（unplanned/planning/active/complete/interrupted），旧 Schema 与 format 3 返回 unsupported_format；1.3 plan.yaml 的 `meta`/`spec` 模型与摘要完整性校验（plan_integrity）；1.4 Change 名、三位 Plan 编号正则校验，`-f` 限制在 Home 内，沿用目录描述符读写；1.5 config.yaml 精简为 artifacts_dir 与 workflow，旧字段返回 config_invalid。
- **2 编译与 on_fail**：2.1 spec 只含 based_on/flow/nodes，成员树由节点路径推导；2.2 引用节点与 flow 条目的 on_fail 下放到每个 Gate、reset 展开为叶子，重叠报 on_fail_conflict；2.3 删除 min_engine_version、engine_version 参数、manual-v1 与 delivery-review；2.4 删除 protected/deviations/reasons 与 workflow_approval；2.5 约束在 create/approve 时按当前 config 检查，指令、模板、保障规则与生成目录执行时实时读取。
- **3 命令树与 Plan 生命周期**：3.1 重写 cli.py 为 `loopspec <资源> <动作>`，工作流命令统一 JSON 与错误信封；3.2–3.9 change new/status/next/history/artifacts/archive（--force/--dry-run/--all/--older-than），plan validate/create/show/list/approve（含 -f 修订）/archive/rollback。
- **4 中断收敛**：按 design D8 固定写入顺序；`interruption()` 识别半完成状态，change status 返回 interrupted 与重新执行命令，执行类命令拒绝推进；重做记录先写清单与摘要，重新执行按摘要核对，越界或不符返回 history_integrity；删除事务文件与 recover。
- **5 运行时、修订与返工**：运行时根改为 Plan 目录（artifacts、.gates、.gate-rounds、.attempts）；Diff 用 Change 级基线并核对仓库，排除 Change 根 `.workflow.yaml`、`state.md`、`plans/` 与配置的生成目录；rollback 只按失败 Gate 自身 on_fail、次数按 Gate 统计；修订冻结规则（只能增加 requires，有效 FAIL 必须在重跑范围）；priorAttempts 标注不可信；保障节点经 gate record 执行；删除快照/草稿/确认记录/激活与版本分支。
- **6 删除旧 Schema 流程**：删除旧流程模块与测试、builtin/schemas、init 的 Schema 复制与 --no-builtin、旧文档页；release notes 写明 2.0.0 不兼容与升级步骤；6.6 按用户决定为 artifacts-command 标注被取代并保留，add-schema-sources 不处理。
- **7 内置资源、Skill 与文档**：内置 Profile 无 min_engine_version 且编译无冲突、guidance 与保障指令更新；四个 Skill 改用新命令树（规划完整任务、validate 后 create、修订先预览再 approve -f、归档 approved Plan 前取得同意、--force 仅在明确要求时使用）；docs/{en,zh} 重写；dynamic-workflow-composition 与 plan-draft-approval 加注被取代内容。
- **8 验证**：端到端、中断注入、负向用例与完整 pytest/ruff/mypy/文档契约检查。
- **9 去掉中断状态（用户确认的设计调整）**：`.workflow.yaml` 只存 change_name、created、baseline、repository，未结束/活动 Plan 由 plan.yaml 的 status 推导，新编号为最大编号加 1；create/approve/archive 为单一生效写入；rollback 以 record.yaml 为生效点，修订以替换 plan.yaml 为生效点（记录先写、文件后搬）；已生效记录中未搬走的文件在推导时视为不存在，由 node instructions、gate、plan 与 change archive 在写锁内按摘要补完；未生效的修订记录被忽略并由下一条记录替换；删除 interrupted 状态与错误码、中断识别；node instructions 改为持写锁。

## Files Changed

- **新增源码**：`src/loopspec/workflow_state.py`、`src/loopspec/workflow_plans.py`、`src/loopspec/workflow_attempts.py`
- **重写或修改源码**：`src/loopspec/cli.py`、`src/loopspec/workflow_cli.py`、`src/loopspec/workflow_models.py`、`src/loopspec/workflow_planning.py`、`src/loopspec/workflow_compiler.py`、`src/loopspec/workflow_runtime.py`、`src/loopspec/workflow_evidence.py`、`src/loopspec/workflow_assurance.py`、`src/loopspec/workflow_diff.py`、`src/loopspec/workflow_changes.py`、`src/loopspec/workflow_archive.py`、`src/loopspec/workflow_io.py`、`src/loopspec/models.py`、`src/loopspec/errors.py`、`src/loopspec/presentation.py`、`src/loopspec/builtin_resources.py`
- **删除源码**：`schema_loader.py`、`legacy_workflow.py`、`instructions.py`、`rollback.py`、`attempts.py`、`state.py`、`gate_outcome.py`、`outputs.py`、`policy.py`、`graph.py`、`task_tracking.py`、`status_report.py`、`artifacts.py`、`change_state.py`、`config.py`、`paths.py`、`workflow_snapshot.py`、`workflow_lifecycle.py`、`workflow_confirmation.py`、`workflow_drafts.py`、`workflow_revision.py`、`workflow_recovery.py`、`workflow_approval.py`（均在 `src/loopspec/`）
- **内置资源**：删除 `builtin/schemas/`、`builtin/profiles/manual-v1.yaml`、`builtin/fragments/delivery-review/`；修改 `builtin/fragments/*/fragment.yaml`、`builtin/profiles/*.yaml`（去掉 min_engine_version、更新 guidance）、`builtin/fragments/README.md`、`builtin/fragments/change-assurance/check.instruction.md`、`builtin/skills/{new,continue,archive,bulk-archive}.md`
- **测试**：新增 `tests/workflow_helpers.py`、`tests/test_workflow_state.py`；重写 `tests/test_workflow_lifecycle.py`、`test_workflow_revision.py`、`test_workflow_recovery.py`、`test_workflow_cli.py`、`test_workflow_e2e.py`、`test_workflow_runtime.py`、`test_cli.py`、`test_docs_consistency.py`；修改 `test_workflow_compiler.py`、`test_workflow_planning.py`、`test_workflow_models.py`、`test_workflow_builtin.py`、`test_workflow_diff.py`、`test_workflow_evidence.py`、`test_workflow_assurance.py`、`test_builtin_fragments.py`、`test_builtin_resources.py`、`test_presentation.py`、`test_skill_templates.py`；删除 `test_artifacts.py`、`test_attempts.py`、`test_builtin_schema.py`、`test_change_state.py`、`test_config.py`、`test_gate_outcome.py`、`test_graph.py`、`test_instructions.py`、`test_outputs.py`、`test_policy.py`、`test_rollback.py`、`test_schema_loader.py`、`test_state.py`、`test_status_report.py`、`test_task_tracking.py`、`test_workflow_approval.py`、`test_workflow_snapshot.py`、`test_workflow_confirmation.py`
- **文档**：`README.md`；`docs/{en,zh}/README.md`、`overview.md`、`workflow-composition.md`、`configuration.md`、`cli-reference.md`、`agent-protocol.md`（重写）；新增 `docs/{en,zh}/plan-reference.md`、`docs/{en,zh}/release-notes.md`；删除 `docs/{en,zh}/schema-reference.md`、`docs/{en,zh}/workflows/secure-spec-driven.md`
- **关联变更记录**：`loopspec/changes/dynamic-workflow-composition/`、`loopspec/changes/plan-draft-approval/`、`loopspec/changes/artifacts-command/` 的 design/proposal/specs 顶部加注与 state.md 追加说明

## Tests and Checks

- `make test`（第 9 组完成后）：`794 passed in 320.25s (0:05:20)`。此前第 1–8 组完成时为 `791 passed in 358.42s (0:05:58)`。
- 第 9 组：中断与状态相关专项 `99 passed in 36.48s`；文档与 Skill 专项 `79 passed in 2.44s`。实施中两处真实问题：替换上下文类时误删 `open_change`（mypy 报 6 处 attr-defined，已恢复）；测试模块文档字符串超长（ruff E501，已改短）。
- `make lint`：`uv run ruff check src tests hatch_version.py` → `All checks passed!`；`uv run mypy src hatch_version.py` → `Success: no issues found in 29 source files`。
- `uv run ruff format --check src tests`：`62 files already formatted`。
- 过程中的真实失败与处理：
  - 端到端测试首次运行超过 2 分钟后被我中止（exit 144）。性能分析显示每次 Diff 扫描对所有已跟踪文件逐个 `git cat-file`（约 57 次 Git 调用/扫描）。改为对工作树文件本地计算 Git blob ID，未变化路径不再读取对象；单个内置 Profile 端到端从 38.17s 降到 12.43s，6 个端到端用例 `6 passed in 135.60s`。
  - 改动初版 Diff 时 `worktree()` 引用了只在 `scan()` 内定义的 `index`，3 个 Diff 用例报 `NameError`，修正为传入参考对象后 `13 passed`。
  - 保障与 Diff 测试首次有 10 个失败：测试辅助函数把请求文件写在工作区根，进入了 Git Diff（`unknown_paths` 含 `loopspec/request.yaml`）。改为写到 Change 的 `plans/` 下（已排除的控制目录）后通过；Skill 与文档同样要求把请求放在 `plans/` 下。
  - 实时保障规则用例中修改规则文件本身也出现在 Diff，属正确行为，测试规则补充 `loopspec/**` 覆盖。
  - 文档契约首轮 4 个失败（默认 Home 写法、过宽的删除词“assurance check”、根 README 仍有旧命令），修正后 `43 passed`。
  - Skill 契约 3 个失败（continue 正文缺少 `/lpsx:continue` 引用），补充后 `36 passed`。

## Deviations from the Design

- **paths.py 删除**：design D11 列为保留，但新实现的 Change 路径解析在 `workflow_state.py`，`paths.py` 已无引用，作为死代码删除（同时删除只服务旧流程的错误类）。
- **写锁位置**：写锁从 Change 根 `.workflow/write.lock` 移到 `plans/.write.lock`，使其处于 Diff 已排除的控制目录内，Change 根不再出现 `.workflow/`。
- **请求文件位置**：design 只要求 `-f` 在 Home 内；实现与 Skill/文档约定把请求写在 `changes/<change>/plans/` 下，避免请求文件被保障检查当作未知改动。
- **修订记录**：修订不需要重新执行任何节点时不写 `.attempts` 记录，直接整文件替换 plan.yaml。revision 记录额外保存目标修订号 `revision`，用于判断是否已生效；重跑节点与文件清单按新 spec 计算，只包含仍存在于新 spec 中的节点。
- **基线固定**：首次 `plan create` 尝试固定基线；不在 Git 仓库且 Plan 不含代码 Gate/保障时允许暂不固定，含代码 Gate 时返回 baseline_required。
- **6.5 版本号**：版本号由 Git tag 决定，仓库内没有可修改的版本声明；本次只写 release notes，`v2.0.0` tag 需维护者发布时推送。

## Follow-Ups

- 发布 2.0.0：推送 `v2.0.0` tag（发布流程会自动生成 notes，可参考 `docs/en/release-notes.md`）。
- 本仓库 `loopspec/changes/` 下的变更仍由已安装的 v1.0.3 驱动；安装 2.0.0 前需用 v1.x 处理或接受它们在 2.0.0 中返回 unsupported_format。
- 内置代码审查 Fragment 的 `evidence.paths` 与 `change-assurance/rules.yaml` 仍是示例路径，启用前需按项目目录调整。
