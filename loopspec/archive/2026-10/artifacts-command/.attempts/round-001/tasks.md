## 1. 路径安全基础（D8，含外部输入校验）

- [ ] 1.1 在 `paths.py` 新增 `safe_change_name(name)`：校验 change 名为安全相对路径（非绝对、无 `..`），不合法抛 `InvalidChangeNameError`。**这是本变更的第一道外部输入校验点。**
- [ ] 1.2 在 `paths.py` 新增 `archive_locations(workflow_home, change_name)`：枚举 `<home>/archive/*/<change>/` 下真实存在的目录，返回 `(month, dir)` 按月份升序；每个结果经 `resolve_within(workflow_home, ...)` 断言仍在 home 内。
- [ ] 1.3 为 1.1/1.2 写单测：`..`/绝对路径/空名被拒；多月份归档按升序返回；`archive/` 不存在时返回空；构造一个 symlink 或 `..` 形式的月份目录名，断言不会返回 home 之外的路径。

## 2. 发现逻辑核心模块 `artifacts.py`

- [ ] 2.1 定义结果 dataclass：`ArtifactReport` / `ChangeLocation` / `SchemaArtifacts` / `NodeArtifacts` / `AttemptRound`，字段与 `specs/loopspec-cli` 的 `--json` 契约一一对应。
- [ ] 2.2 实现 `resolve_requested_schemas(raw)`：逗号分隔、`strip`、丢空段、去重保序；strip 后为空抛 `ConfigValidationError`；**每段过 `is_safe_relative_path`，不合法抛 `ConfigValidationError`（D8 第二道外部输入校验点，防 `--schemas ../../etc`）**。
- [ ] 2.3 实现 `discover_locations(home, artifacts_dir, change_name)`：活跃目录 + `archive_locations` 的并集，按 D2 顺序（归档升序在前、活跃在最后）；全空时抛 `ChangeNotFoundError`。
- [ ] 2.4 实现每个位置的元数据读取：`config.read_metadata` 捕获 `ConfigValidationError` 降级为 warning 并按缺失处理（D9）。
- [ ] 2.5 实现被考察 schema 集合解析（D5）：点名时用点名集合、加载失败即抛；未点名时用 config 候选 ∪ 各位置自报 schema，加载失败降级为 warning 并跳过。
- [ ] 2.6 实现 schema × 位置的产物探测（D1/D4）：artifact root 由 `config.schema_path_for` + `paths.artifact_root` 得出，逐节点用 `outputs.node_output_patterns` + `outputs.resolve_outputs` 解析现存文件。
- [ ] 2.7 实现 `.attempts` 轮次收集：复用 `attempts.list_rounds`，每轮给出 round/gate/verdict/archiveDir 与该轮目录下的真实文件路径。
- [ ] 2.8 实现未认领文件枚举（D6）：遍历位置目录，沿用 `outputs` 的候选判定（排除 `.attempts/` 与保留名），减去已被认领的路径集合；不额外过滤隐藏文件。
- [ ] 2.9 实现多方认领检测：同一路径被两个以上 schema 认领时追加 warning；位置级与全局 `files` 汇总去重并稳定排序。

## 3. 核心逻辑单测 `tests/test_artifacts.py`

- [ ] 3.1 `resolve_requested_schemas` 的全部分支：正常多值、空白容忍、去重、空取值报错、不安全名报错。
- [ ] 3.2 位置发现：仅活跃、仅归档、两者并存、多归档月份、全不存在（`change_not_found`）、顺序断言。
- [ ] 3.3 探测归属：单 schema 全节点、glob 多文件展开、门禁只报存在的一侧、声明但未产出的不出现。
- [ ] 3.4 接力场景：两个 schema 用不同 `path` 子目录，各自产物正确归属且 artifact root 不同。
- [ ] 3.5 schema 集合：未点名覆盖全部候选、纳入自报但已不在候选的 schema、点名过滤、点名不存在时抛 `SchemaNotFoundError`、未点名时加载失败降级为 warning。
- [ ] 3.6 保留文件与轮次：`state.md`/`.workflow.yaml` 不入产物也不入未认领；`state.md` 单独报告；`.attempts/round-001` 逐轮报告。
- [ ] 3.7 未认领与歧义：不匹配任何模式的文件进未认领；点名过滤后被排除的产物落入未认领；两个 schema 认领同一文件时双报 + warning + 汇总去重。
- [ ] 3.8 降级：元数据缺失与元数据损坏两种情况均成功返回并带 warning。
- [ ] 3.9 只读断言：命令执行前后对 workflow home 做一次目录快照对比，断言完全一致（覆盖 D3 刻意绕开 `mkdir` 这一点）。

## 4. CLI 命令与人类可读渲染

- [ ] 4.1 在 `cli.py` 注册 `artifacts` 命令：位置参数 `change_name`，选项 `--schemas` / `--home` / `--json`；全部 `LoopspecError` 走既有 `_fail` 统一错误契约。
- [ ] 4.2 实现 dataclass → JSON 载荷的转换，字段名与 `specs/loopspec-cli` 契约逐字对齐；全部路径为绝对路径。
- [ ] 4.3 在 `presentation.py` 新增 `render_artifacts_summary`：按位置分节渲染（类型/月份/路径、每 schema 文件计数、轮次数、未认领计数、末尾总计），不接受 `as_json` 参数（沿用该模块的既有约束）。
- [ ] 4.4 人类可读路径的安全断言测试：产物名含 rich markup（如 `[red]out.md`）与控制字符时原样可见、不被吞掉、不注入转义序列。

## 5. 端到端 CLI 测试（扩展 `tests/test_cli.py`）

- [ ] 5.1 活跃 change 全产物列出；归档后仍可查询（真实跑一遍 `archive` 再查）。
- [ ] 5.2 `--schemas` 过滤、多值、点名不存在报 `schema_not_found`、空值报 `config_invalid`、不安全名报 `config_invalid`。
- [ ] 5.3 `change_not_found` 与 `invalid_change_name`（`../../etc`）两条失败路径，断言输出不含 home 之外的路径。
- [ ] 5.4 人类可读模式：不出现 JSON 字段名与 Python 容器字面量，且被聚合掉的明细在 `--json` 下仍可取到。

## 6. 文档同步（中英双份，由 docs 一致性测试兜底）

- [ ] 6.1 `docs/en/cli-reference.md` 与 `docs/zh/cli-reference.md` 增加 `## loopspec artifacts` 小节：语法、选项表、`--json` 响应字段表、示例、失败情形；两语言首列标识符必须完全一致。
- [ ] 6.2 `docs/en/agent-protocol.md` 与 `docs/zh/agent-protocol.md` 的「读一个不是你创建的 change」一节改以本命令为入口，说明接力工作流先读什么。
- [ ] 6.3 明确记录归属是「对当前 schema 定义的一次投影」而非历史事实，以及未认领文件的兜底作用（D1 的已知代价）。

## 7. 验收

- [ ] 7.1 `make lint` 通过（ruff + mypy）。
- [ ] 7.2 `make test` 全绿，含文档一致性测试。
- [ ] 7.3 在本仓库真实数据上手动验证：对 `loopspec/archive/2026-07/` 下某个已归档 change 执行 `loopspec artifacts <name>`，确认能列出其全部产物路径。
