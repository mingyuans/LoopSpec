# 实施报告

## 已实施任务

tasks.md 的 53 项任务全部完成。

- 第一版本（1—4）：新增四层领域模型、统一 nodes 混合编排、递归 Fragment 实例展开、Profile/完整 Plan 校验、项目最低约束、精确摘要人工审批、自包含不可变快照和命令接入。提供 manual-v1 及三类需求模板；V1 明确拒绝未支持的 V2 能力。
- 第二版本（5—8）：新增叶子/嵌套引用/分类恢复的唯一处理者、共享历史预算、产物与证据归档、可恢复事务、固定 Git 基线、begin/record 审查证据、全量 Diff Assurance、未来工作重组和诊断驱动的增加型安全扩张。
- 收尾（9）：四个 builtin/skills 源使用英文；投影在临时目录验证，不更新本地安装。产品文档的两个语言入口同步新增中文方案说明与 CLI/配置契约。完成三类模板、QA 后端返工、FE 意外改 BE、证据过期、修订与中断恢复验证和实施代码复审。

同一 Fragment 的多次引用以实例 ID 链隔离产物与证据。以 AFD1111 为例，后端 security 实例的输出为 loopspec/changes/AFD1111/artifacts/be/security/check/pass.md，而另一个实例具有另一条实例路径。Profile 不产生自己的产物命名空间。

## 文件变更

以下按区域列出本次实现及其材料；没有删除源文件。需求既往 Attempts 作为历史保留，不是本轮源码修改目标。

### 核心实现（新增）

- `src/loopspec/legacy_workflow.py`
- `src/loopspec/workflow_approval.py`
- `src/loopspec/workflow_archive.py`
- `src/loopspec/workflow_assurance.py`
- `src/loopspec/workflow_catalog.py`
- `src/loopspec/workflow_cli.py`
- `src/loopspec/workflow_compiler.py`
- `src/loopspec/workflow_diff.py`
- `src/loopspec/workflow_evidence.py`
- `src/loopspec/workflow_git.py`
- `src/loopspec/workflow_io.py`
- `src/loopspec/workflow_models.py`
- `src/loopspec/workflow_planning.py`
- `src/loopspec/workflow_recovery.py`
- `src/loopspec/workflow_resources.py`
- `src/loopspec/workflow_revision.py`
- `src/loopspec/workflow_runtime.py`
- `src/loopspec/workflow_snapshot.py`
- `src/loopspec/workflow_yaml.py`

### 核心接入（修改）

- `src/loopspec/cli.py`
- `src/loopspec/errors.py`
- `src/loopspec/models.py`

### 内置资源（新增）

- `builtin/fragments/backend-code.yaml`
- `builtin/fragments/backend-implementation.yaml`
- `builtin/fragments/backend-tests.yaml`
- `builtin/fragments/change-assurance.yaml`
- `builtin/fragments/delivery-review.yaml`
- `builtin/fragments/design.yaml`
- `builtin/fragments/frontend-code.yaml`
- `builtin/fragments/frontend-implementation.yaml`
- `builtin/fragments/frontend-pr-review.yaml`
- `builtin/fragments/frontend-tests.yaml`
- `builtin/fragments/pr-review.yaml`
- `builtin/fragments/qa-testing.yaml`
- `builtin/fragments/requirements.yaml`
- `builtin/fragments/security-review.yaml`
- `builtin/fragments/README.md`
- `builtin/fragments/rules/code-assurance.yaml`
- `builtin/fragments/instructions/backend-code.md`
- `builtin/fragments/instructions/change-assurance.md`
- `builtin/fragments/instructions/delivery-review.md`
- `builtin/fragments/instructions/design.md`
- `builtin/fragments/instructions/frontend-code.md`
- `builtin/fragments/instructions/pr-review.md`
- `builtin/fragments/instructions/qa-testing.md`
- `builtin/fragments/instructions/requirements.md`
- `builtin/fragments/instructions/security-review.md`
- `builtin/fragments/instructions/tasks.md`
- `builtin/fragments/instructions/tests.md`
- `builtin/profiles/bugfix.yaml`
- `builtin/profiles/frontend-small-change.yaml`
- `builtin/profiles/large-feature.yaml`
- `builtin/profiles/manual-v1.yaml`

### Skill 源（修改，英文）

- `builtin/skills/new.md`
- `builtin/skills/continue.md`
- `builtin/skills/archive.md`
- `builtin/skills/bulk-archive.md`

### 产品文档（修改及新增）

- `README.md`
- `docs/en/README.md`
- `docs/en/agent-protocol.md`
- `docs/en/cli-reference.md`
- `docs/en/configuration.md`
- `docs/en/overview.md`
- `docs/en/schema-reference.md`
- `docs/en/workflow-composition.md`
- `docs/zh/README.md`
- `docs/zh/agent-protocol.md`
- `docs/zh/cli-reference.md`
- `docs/zh/configuration.md`
- `docs/zh/overview.md`
- `docs/zh/schema-reference.md`
- `docs/zh/workflow-composition.md`

### 回归测试（新增及修改）

- `tests/test_workflow_approval.py`
- `tests/test_workflow_assurance.py`
- `tests/test_workflow_builtin.py`
- `tests/test_workflow_catalog.py`
- `tests/test_workflow_cli.py`
- `tests/test_workflow_compiler.py`
- `tests/test_workflow_diff.py`
- `tests/test_workflow_e2e.py`
- `tests/test_workflow_errors.py`
- `tests/test_workflow_evidence.py`
- `tests/test_workflow_git.py`
- `tests/test_workflow_io.py`
- `tests/test_workflow_models.py`
- `tests/test_workflow_planning.py`
- `tests/test_workflow_recovery.py`
- `tests/test_workflow_resources.py`
- `tests/test_workflow_revision.py`
- `tests/test_workflow_runtime.py`
- `tests/test_workflow_snapshot.py`
- `tests/test_docs_consistency.py`
- `tests/test_scaffold.py`
- `tests/test_skill_templates.py`

### 需求材料与本轮报告

- `loopspec/changes/dynamic-workflow-composition/proposal.md`
- `loopspec/changes/dynamic-workflow-composition/design.md`
- `loopspec/changes/dynamic-workflow-composition/review.md`
- `loopspec/changes/dynamic-workflow-composition/tasks.md`
- `loopspec/changes/dynamic-workflow-composition/state.md`
- `loopspec/changes/dynamic-workflow-composition/approval/approved.md`
- `loopspec/changes/dynamic-workflow-composition/security/pass.md`
- `loopspec/changes/dynamic-workflow-composition/specs/workflow-fragments/spec.md`
- `loopspec/changes/dynamic-workflow-composition/specs/workflow-planning/spec.md`
- `loopspec/changes/dynamic-workflow-composition/specs/workflow-recovery-assurance/spec.md`
- `loopspec/changes/dynamic-workflow-composition/specs/loopspec-cli/spec.md`
- `loopspec/changes/dynamic-workflow-composition/specs/lpsx-skills/spec.md`
- `loopspec/changes/dynamic-workflow-composition/apply/security-audit.md`
- `loopspec/changes/dynamic-workflow-composition/apply/report.md`

## 测试与检查

### 最终有效结果

- `env -u NO_COLOR .venv/bin/pytest -q --tb=short`：`936 passed in 302.53s (0:05:02)`。这是最后一次代码更改后的完整测试，包含旧生命周期与全部新增工作流测试。
- 最后一段英文 Skill 不可信数据指引补充后，再跑 `.venv/bin/pytest -q tests/test_docs_consistency.py tests/test_skill_templates.py tests/test_scaffold.py --tb=short`：`87 passed in 1.52s`。
- CLI 兼容与新入口专项 `env -u NO_COLOR .venv/bin/pytest -q tests/test_workflow_cli.py tests/test_cli.py --tb=short`：`76 passed in 14.22s`。
- 内置模板端到端专项：`4 passed in 187.61s`。在隔离 Git 仓库模拟 Gate 结论，验证大型需求、FE 小需求、Bugfix 和 QA 后端返工；并非对某真实业务系统做安全认证。
- 快照、非活动快照重试与恢复专项：`15 passed in 14.36s`；代码恢复与 CLI 专项：`15 passed in 7.02s`；文档与 inspect/resume 专项：`43 passed in 1.86s`。
- `make lint`（uv 在沙箱外运行）：ruff 输出 `All checks passed!`，mypy 输出 `Success: no issues found in 45 source files`。最终源码修改后直接重跑同样的 `.venv/bin/ruff check src tests hatch_version.py` 与 `.venv/bin/mypy src hatch_version.py`，结果相同。
- `git diff --check`：无输出，退出成功。
- 四个 Skill 的临时目录结构验证输出 `Skill is valid!`；最新正文的英文/投影测试由上述 87 项专项再次复核。

### 实际发生过的失败与处理

- 首次沙箱内 `make test` 未进入 pytest，uv 的 macOS 系统配置读取发生 panic，原输出包含：`Attempted to create a NULL object.`、`Tokio executor failed, was there a panic?: Any { .. }` 以及 `make: *** [test] Error 101`。在沙箱外运行该命令后进入正常测试。
- 首次完整 `make test` 的真实结果为 `1 failed, 923 passed in 109.77s (0:01:49)`，失败项 `test_colour_is_applied_when_the_console_allows_it`，原断言为 `AssertionError: assert '\\x1b[' in '✔ done\\n'`。环境中设置了 NO_COLOR；只在测试子进程移除这个变量后，该单项为 `1 passed in 0.07s`，完整重跑随后分别为 931、933，最终 936 项通过。没有更改项目颜色显示逻辑，也没有修改用户环境配置。
- 新增端到端测试首轮为 `4 failed, 28 passed in 132.94s (0:02:12)`。测试脚本误将 status/rollback/assurance 的需求位置参数写成 --change，使 CLI 用法错误且没有 JSON stdout；原错误为 `JSONDecodeError: Expecting value: line 1 column 1 (char 0)`。修正测试调用后四个端到端场景全部通过。
- 一次专项命令误写不存在的文件，实际输出为 `ERROR: file or directory not found: tests/test_lifecycle_e2e.py`、`no tests ran in 0.00s`。随后按真实文件名重跑 CLI 专项，并由最终全量测试覆盖全部现有测试。
- 增加引用归属链时 mypy 曾要求局部列表的类型标注；已补全，最终无类型问题。调整恢复测试为真实 CLI resume 后 ruff 曾报告未使用 recover 导入，已移除并复核通过。

## 方案调整与安全复审

- 用户最新澄清覆盖 Skill 语言与修改目标：内置源英文，需求材料中文，不刷新 .codex/skills、.claude/skills 或全局目录。设计、提案、规格、任务与状态记录已同步。
- 实施复审补齐冻结处理链不得插入新处理者、代码 Gate 全部先于 Assurance、空白 FAIL 摘要拒绝、新建日志先于激活、非活动完整快照保留重试，以及返工上下文中的哈希校验失败报告路径/必重跑 Gate。这些是原安全约束的收紧，没有增加新的对外领域概念。
- 实施代码复审见 apply/security-audit.md；设计阶段 security/pass.md 不被误当成实现测试结论。
- 旧 Schema/Change 不自动迁移；历史与产物仍是进度来源，不增加外部进度数据库。Plan 状态、证据与恢复预算不是人工审批或审查质量的证明。

## 非阻塞后续事项与边界

- 使用自动代码模板前，维护者需把 evidence.paths、保障 paths 和修复 Fragment 映射到真实代码、测试、文档及支持文件目录。内置路径是示例；不认识的路径默认阻塞，而不是静默通过。
- Git 扫描保守限制文件数、单文件和累计输入大小，拒绝合并冲突、子模块等不支持输入；安全文件辅助目前依赖 POSIX。后续可优化批量 Git 对象读取，但不能削弱输入摘要与一致性复核。
- 本地同权限主体的认证、真实审查质量、外部终端提交/部署、多工作树和受保护分支/独立 CI 不在本次强制边界内。
- legacy history/artifacts 仍面向旧 Schema；新 Plan 修订使用 plans history，返工记录通过 instructions.priorAttempts 和 Attempts 查看。本次没有承诺迁移所有旧查询命令。
- 保留用户已有 .gitignore、AI-DLC 安装/配置及 add-schema-sources 需求。没有全局安装、仓库提交、发布或自行归档本需求。
