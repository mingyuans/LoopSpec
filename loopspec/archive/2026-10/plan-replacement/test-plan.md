# plan-replacement 测试计划（任务 1.1）

## 1. 范围

覆盖 design D3–D12 的全部新行为、D11 的删除项与旧 Schema 流程删除；不改动与本变更无关的能力（版本号计算、安装脚本、发布流程、工具注册与选择器、脚手架写入），只在其断言涉及 Schema 时同步修改。

测试类型：

| 类型 | 说明 | 工具 |
|---|---|---|
| 单元 | 模型、编译、摘要、推导函数，不依赖 Git | pytest |
| 集成 | 通过 CLI（Typer CliRunner）调用命令，使用临时工作区 | pytest + CliRunner |
| 端到端 | 临时 Git 仓库中按真实命令跑完整流程 | pytest + 现有 `init_repository` 辅助函数 |
| 中断注入 | 用 monkeypatch 让第 N 次文件写入或移动抛出异常，验证重新执行收敛 | pytest monkeypatch |
| 契约 | 内置资源、文档示例、Skill 文本与代码一致 | pytest |

## 2. 现有测试的处理

| 处理 | 测试文件 |
|---|---|
| 删除（旧 Schema 流程） | `test_artifacts.py`、`test_attempts.py`、`test_builtin_schema.py`、`test_change_state.py`、`test_config.py`、`test_gate_outcome.py`、`test_graph.py`、`test_instructions.py`、`test_outputs.py`、`test_policy.py`、`test_rollback.py`、`test_schema_loader.py`、`test_state.py`、`test_status_report.py`、`test_task_tracking.py` |
| 删除（被取代的新工作流机制） | `test_workflow_approval.py`（受保护步骤）、`test_workflow_snapshot.py`（快照） |
| 重写为新行为 | `test_cli.py`（改为新命令树）、`test_workflow_cli.py`、`test_workflow_lifecycle.py`、`test_workflow_confirmation.py`、`test_workflow_revision.py`、`test_workflow_recovery.py`、`test_workflow_e2e.py` |
| 保留并按需调整 | `test_workflow_compiler.py`、`test_workflow_planning.py`、`test_workflow_models.py`、`test_workflow_catalog.py`、`test_workflow_diff.py`、`test_workflow_assurance.py`、`test_workflow_evidence.py`、`test_workflow_runtime.py`、`test_workflow_resources.py`、`test_workflow_io.py`、`test_workflow_git.py`、`test_workflow_errors.py`、`test_workflow_builtin.py`、`test_builtin_fragments.py`、`test_builtin_resources.py`、`test_docs_consistency.py`、`test_skill_templates.py`、`test_presentation.py`（init 输出） |
| 不变 | `test_hatch_version.py`、`test_install_script.py`、`test_release_workflow.py`、`test_scaffold.py`、`test_tool_picker.py`、`test_tool_registry.py`、`test_tools_arg.py` |

删除前先确认被删测试覆盖的行为在新设计中确实不存在，或已由下文新用例覆盖。

## 3. 用例

### 3.1 Change 级状态与 plan.yaml（单元）

| # | 用例 | 预期 |
|---|---|---|
| C1 | `change new` 写出的 `.workflow.yaml` | format_version 4，指针为空，next_plan 为 1 |
| C2 | 状态推导：无 Plan / draft / approved 未完成 / approved 完成 / 半完成 | 分别为 unplanned、planning、active、complete、interrupted |
| C3 | 读取 format_version 3 或含 `schema` 字段的 Change | `unsupported_format`，带处理指引 |
| C4 | plan.yaml 往返读写 | meta 与 spec 字段与 D4 一致；status 只接受 draft/approved/archived |
| C5 | 手改 `spec.nodes` 或 `spec.flow` | 加载返回 `plan_integrity` |
| C6 | 旧字段出现在 plan.yaml、请求或 config.yaml（reasons、recovery、protected、min_engine_version、schema、schemas、context、rules、default_profile、approval、history、pending） | 按未知字段拒绝 |
| C7 | 【安全】非法 Change 名、Plan 编号（非三位数字、含 `..`）、节点路径、Home 外的 `-f` 路径、符号链接 Plan 目录 | 拒绝，不读写目录外文件 |

### 3.2 编译与 on_fail（单元）

| # | 用例 | 预期 |
|---|---|---|
| K1 | 编译 bugfix Profile | spec 只有 based_on、flow、nodes；Gate 内 on_fail 与 design 示例一致 |
| K2 | 引用节点 on_fail 下放 | be/tests、be/security、be/review 的 Gate 各得 `reset: [be/code/implement]` |
| K3 | flow 条目 on_fail 下放 | qa/test 的 reset 展开为 be 的四个叶子 |
| K4 | 同一 Gate 收到两条 on_fail | `on_fail_conflict` |
| K5 | flow on_fail 指向下游、自身或不存在实例 | 编译错误 |
| K6 | 成员树推导 | 前缀成员、起点与终点与原 instances 结果一致 |
| K7 | 内置 Fragment/Profile 全部可编译 | 无 conflict、无 min_engine_version |
| K8 | 资源实时读取 | 确认后修改指令文件，`node instructions` 返回新内容；修改 fragment.yaml 不影响已确认图 |

### 3.3 Plan 命令（集成）

| # | 用例 | 预期 |
|---|---|---|
| P1 | `plan validate` 无 Plan 时 | 返回 flow、nodes、digest、约束结果；工作区文件无任何变化 |
| P2 | `plan validate` 有 approved Plan 时 | 返回修订预览（新摘要、新增实例、将重新执行的节点）；不写文件 |
| P3 | `plan create` 无未结束 Plan | 新建 `plans/001/plan.yaml`（draft），首次固定 baseline/repository，open_plan=001 |
| P4 | `plan create` 已有 draft | 覆盖同一 Plan 的 spec，编号不变 |
| P5 | `plan create` 已有 approved | 拒绝并提示 validate/approve -f 或 archive |
| P6 | `plan create` 缺少 required_fragments 或保障节点 | `project_constraint` |
| P7 | `plan approve` draft，摘要一致 / 不一致 | approved 且 active_plan 设置 / `plan_changed` 不变 |
| P8 | `plan approve` 重复提交相同摘要 | 返回已确认，不改变 revision |
| P9 | `plan show`、`plan list` | 字段完整；`-p` 查看历史 Plan |
| P10 | `plan archive` approved Plan | archived，指针清空，Plan 目录内文件逐字节不变 |
| P11 | `plan archive` draft Plan | archived，open_plan 清空，下一次 create 为 002 |
| P12 | 重新规划后新 Plan | 同名节点为 ready；返工次数为 0；baseline 不变 |
| P13 | 没有活动 Plan 时执行 `node instructions`、`gate`、`plan rollback` | `plan_not_active` 与对应 nextSteps |
| P14 | `-p` 指定非活动 Plan 执行 rollback | `plan_not_active` |

### 3.4 修订（集成）

| # | 用例 | 预期 |
|---|---|---|
| R1 | 只调整未开始部分 | approve -f 后 revision=2，已完成节点保持 done |
| R2 | 冻结节点增加 requires | 该节点及下游归档到 `.attempts/<序号>/`（kind: revision）并变为待执行 |
| R3 | 冻结节点删除、改名、改执行定义或减少 requires | `node_frozen`，提示归档后重新规划 |
| R4 | 有效 FAIL 未落在重新执行范围 | 拒绝；落在范围内则允许（保障缺后端场景） |
| R5 | base_revision 过期、并发修订 | `stale_revision`，先确认者生效 |
| R6 | 修订后代码 Gate 证据 | 因 digest 变化失效，需要重新 begin/record |
| R7 | 修订不清零返工次数 | 原 Gate 次数保留 |

### 3.5 返工与证据（集成）

| # | 用例 | 预期 |
|---|---|---|
| G1 | Gate 有效 FAIL 后 `plan rollback` | 按 Gate 自身 on_fail 重置；归档到 `.attempts`（kind: rollback）；业务代码不变；并行分支保留 |
| G2 | 次数用完、没有 on_fail | exhausted；rollback 拒绝 |
| G3 | 失败报告含 route_case 或多余字段 | `invalid_verdict` |
| G4 | `gate begin/record` 正常、审查期间改代码、复用旧 roundId | PASS / 拒绝要求重新 begin / 拒绝 |
| G5 | 保障节点 `gate record` | 系统写出 PASS/FAIL；手写 pass.md 不算；只接受活动 Plan 证据 |
| G6 | 重新规划后旧 Plan 的证据 | 新 Plan 保障要求重新取得 |
| G7 | 重做记录作为 priorAttempts | 出现在重跑节点的 instructions 中并标注不可信 |
| G8 | 【安全】Diff 控制目录 | `plans/` 与 Change 根控制文件被排除；把业务目录配置为工具生成目录被拒绝 |

### 3.6 中断收敛（中断注入）

对下列命令，在每一次文件写入或移动之后注入异常，然后：`change status` 返回 interrupted 且给出该命令；执行类命令拒绝推进；重新执行同一命令后，最终文件状态与“一次完成”逐字节一致，且任何时刻最多一个 approved Plan。

| # | 命令 | 中断点 |
|---|---|---|
| I1 | `plan create`（新建 draft） | plan.yaml 写入后 |
| I2 | `plan approve`（draft） | plan.yaml 改为 approved 后 |
| I3 | `plan approve -f`（修订） | record.yaml 写入后；归档到一半；plan.yaml 替换前 |
| I4 | `plan rollback` | record.yaml 写入后；归档到一半；失败报告归档前 |
| I5 | `plan archive` | plan.yaml 改为 archived 后 |
| I6 | 重新执行时返工次数 | 只计一次，不新建重复记录 |
| I7 | 【安全】归档目标被篡改或记录清单含 Plan 目录外路径 | `history_integrity`，不覆盖、不移动 |

### 3.7 命令树与输出（集成）

| # | 用例 | 预期 |
|---|---|---|
| T1 | `--help` 列出的命令 | 只有 version、init、change、plan、node、gate、fragment、profile 及其动作 |
| T2 | 已删除命令（schemas、assurance、recover、旧平铺命令、plans/fragments/profiles 复数组、bulk-archive） | 不存在 |
| T3 | 工作流命令输出 | 总是 JSON；失败为 error/message/fix 信封且退出码非 0 |
| T4 | `change history -p`、`change artifacts` | 按 Plan 列出重做记录与产物 |
| T5 | `change archive` 未完成 / `--force` / `--dry-run` / `--all --older-than` | 拒绝 / 归档并标明未完成 / 只预览 / 只处理符合条件的 complete Change |
| T6 | `init` | 创建 config.yaml、fragments、profiles、changes；无 schemas；无 `--no-builtin`；摘要不含 Schema 名；工具脚手架行为不变 |
| T7 | `profile save` | 保存 spec.flow 与 flow 条目 on_fail，不覆盖同名 Profile |

### 3.8 端到端（临时 Git 仓库）

| # | 场景 |
|---|---|
| E1 | 初次规划（validate → create → show → approve）→ 执行 → QA 失败 rollback → 修复 → 保障通过 → complete → `change archive` |
| E2 | 执行中修订：保障报告缺后端 → validate -f 预览 → approve -f → be 执行、assurance 重新执行 → 完成 |
| E3 | 任务变化：plan archive 001 → create/approve 002 → 新 Plan 从空状态执行，旧代码改动要求重新审查 → 完成 |
| E4 | 三个内置 Profile（large-feature、frontend-small-change、bugfix）各自跑通 |

### 3.9 契约

| # | 用例 | 预期 |
|---|---|---|
| D1 | docs 中的 plan.yaml、请求文件与 Profile 示例 | 能被新模型解析与编译 |
| D2 | CLI 参考覆盖全部命令与参数 | 与 Typer 注册的命令一一对应 |
| D3 | docs、README、Skill 中不再出现已删除命令与字段 | 搜索结果为 0（删除清单与 release notes 除外） |
| D4 | Skill 文本 | 使用新命令树；包含“归档前取得人同意”“不得自行确认”；修订先 validate 再 approve -f |
| D5 | 被删除模块不可导入 | `schema_loader` 等模块导入失败 |

## 4. 验收标准

1. 上述用例全部实现并通过；被删除的测试已逐一确认无需保留或已由新用例覆盖。
2. `make test`（完整 pytest）、`make lint`（ruff + mypy）全部通过，报告中记录真实输出。
3. 中断注入用例证明：所有多文件命令在任一中断点后重新执行都收敛，且从不出现两个 approved Plan。
4. 代码与文档中不再存在 D11 删除清单与旧 Schema 流程的命令、字段与模块（release notes 除外）。
5. 测试不依赖真实网络或全局环境，可在干净环境中重复运行。
