# Change State

## Current Focus
- security 门禁第 2 轮 PASS（`security/pass.md`）。`approval` 节点**等待人类审批**：本次运行环境没有交互提问设施，按 approval 指令「无法询问人类时两个输出都不写」，故 `approval/approved.md` 与 `approval/changes-requested.md` 均未创建，节点停在 `ready`。实现工作已按 `tasks.md` 先行落地，但该 change 在拿到人类审批前不得归档。

## Frozen Decisions
- D1：schema 归属靠**探测**（schema 的产物模式 × artifact root 匹配磁盘现存文件），不给 `.workflow.yaml` 加历史字段。理由：已归档的 change 永远补不上历史字段，而那正是核心场景。
- D2：位置 = 活跃目录 ∪ `archive/*/<change>/`；顺序为归档月份升序在前、活跃在最后（时间顺序）。归档月份目录名不校验 `YYYY-MM` 格式。
- D3：发现逻辑放新模块 `artifacts.py`，CLI 是薄壳。**不复用 `_load_change_context`**——它会 `mkdir` artifact root，对只读命令是硬伤。
- D4：产物解析复用 `outputs.resolve_outputs` / `node_output_patterns`，使与 `status` 的一致性成为结构性事实。
- D5：未点名时被考察 schema = config 候选 ∪ 各位置自报 schema；点名时加载失败即硬失败，未点名时降级为 warning。
- D6：未被任何 schema 认领的文件必须报告，且不额外过滤隐藏文件。
- D7：人类可读模式走 `Presenter` 渲染聚合摘要，不用 `_emit`（既有 spec 禁止转印 JSON 字段名与容器字面量）。
- D8：change 名与 schema 名都必须过 `is_safe_relative_path`；位置目录必须过 `resolve_within`。
- D10：`--schemas` 逗号分隔、去重保序、不支持 `all`/`none`；空取值报 `config_invalid`。

## Decision Log
- **security 第 1 轮 FAIL（两条阻塞项）**：(a) design 声称输出路径全部限定在 workflow home 内，但 D8 的检查只覆盖位置目录，覆盖不到目录内部的符号链接——`.resolve()` 会把它解析成 home 外的绝对路径并打印出来；(b) D9 的元数据降级只覆盖 `.workflow.yaml`，没覆盖 `.attempts/round-NNN/_meta.yaml`，后者顶层不是映射时 `attempts.list_rounds` 会抛 `AttributeError` 而非 `LoopspecError`，命令以 traceback 终止。
- 修复方向（第 2 轮采纳）：新增 D11 在**输出边界**统一收口每一条对外路径（逃出 home 则不报告 + warning），而非在各调用点分别打补丁；D9 扩展到 `_meta.yaml`，且加固放在 `artifacts.py` 侧而不改 `attempts.list_rounds`，以免影响复用它的 `history` 与 `instructions`。
- 一并采纳评审的非阻塞建议：`--schemas` 每段的校验从「安全相对路径」收紧为 `KEBAB_RE`，与 `config.yaml` 对 schema 名的既有约束一致。
- 选独立命令而非扩展 `instructions.contextFiles`：后者每轮都被调用，改它的语义与体积风险与收益不成比例。
- `--schemas` 点名不存在的 schema 选择硬失败而非空结果：否则「没产物」与「名字打错」不可区分，对 agent 消费方是有害歧义。
- 归档月份目录名不做格式校验：人工整理过的归档目录不应让产物凭空消失。
- design 阶段自查发现 `--schemas` 的每段也是路径分量，回补进两份 spec（schema 名的安全校验 + 对应 scenario）。

## Rejected Options
- 给 `.workflow.yaml` 加 `schemas` 历史列表：需要迁移，且对已归档 change 无法回填。
- 把跨 schema 产物塞进 `status` / `instructions` 的既有字段：改动每轮被调用的响应契约。
- 未认领文件里过滤 `.DS_Store` 等隐藏文件：会在「所有产物路径」的承诺上开看不见的洞。
- `--schemas all` / `none` 关键字：省略即全部，语义已完整；「不考察任何 schema」无意义。

## Open Questions
- **`approval` 门禁待人类裁决**。运行环境无交互提问设施，未伪造 PASS（伪造会使该门禁完全失去意义）。人类批准后写 `approval/approved.md`、否则写 `approval/changes-requested.md`；后者会回退 specs/design/tasks。
- `attempts.list_rounds` 对损坏 `_meta.yaml` 的加固（影响 `history` 与 `instructions.priorAttempts`）留作后续独立变更，本次不动（见 `design.md` D12 与 `security/pass.md` 的 Notes）。

## Implementation Notes
- `tasks.md` 全部 41 项已勾选，实现落地如下：新增 `src/loopspec/artifacts.py`；`paths.py` 新增 `safe_change_name` / `contained_in` / `archive_locations`；`outputs.py` 新增 `resolve_output_entries` / `iter_artifact_candidates`（`resolve_outputs` 改为基于前者实现，行为不变）；`cli.py` 注册 `artifacts` 命令；`presentation.py` 新增 `ArtifactLocationSummary` / `render_artifacts_summary`。
- 实现期一处设计细化：`outputs.resolve_outputs` 只返回 resolved 路径，符号链接被剔除时拿不到相对名用于 warning。故在 `outputs.py` 抽出 `resolve_output_entries`（返回「相对名 + resolved 路径」），`resolve_outputs` 基于它实现——单一实现，`status`/`instructions` 行为不变，同时让 D11 的 warning 能只用相对名指名。
- 测试：`tests/test_artifacts.py` 55 项，`tests/test_cli.py` 新增 16 项。全量 695 passed / 1 skipped，`ruff` 与 `mypy` 均通过。
- 范围外、已留痕的后续跟进：`attempts.list_rounds` 对损坏 `_meta.yaml` 无防护（影响 `history` 与 `instructions.priorAttempts`）；`lpsx-skills` 的四个 skill 模板未提及本命令（新增第五个 skill 会改动该能力，本次不动）。

## Artifact Notes
- `proposal.md`：Why 部分逐条列出今天路径丢失的两个代码位置（`status` 的 `existingOutputPaths`、`instructions` 的 `contextFiles`）与归档放大效应。
- `specs/artifact-discovery/spec.md`：新能力，9 条 requirement 覆盖位置枚举、顺序、探测归属、schema 集合、保留文件、未认领、歧义、路径安全、降级。
- `specs/loopspec-cli/spec.md`：ADDED 一条命令要求，含完整 `--json` 字段契约与与 `status`/`instructions`/`history` 的职责边界。
- `design.md`（第 2 轮）：D1–D12 + 安全面自查小节。新增 D11（输出侧路径单一收口点）与 D12（轮次收集自己实现，不改 `attempts.list_rounds`），D9 扩展到 `_meta.yaml`，D8 的 `--schemas` 校验收紧为 `KEBAB_RE`。
- `security/pass.md`：第 2 轮 PASS，逐条复核第 1 轮两条阻塞项，并新增一项资源耗尽检查（符号链接目录环），要求钉成回归断言（已落为 tasks 2.5）。
- `.attempts/round-001/`：第 1 轮的 design/tasks 与 `security/fail.md`，含两条阻塞项原文。
