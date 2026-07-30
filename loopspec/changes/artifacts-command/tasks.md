## 1. 路径安全：输入侧校验（D8）

- [x] 1.1 在 `paths.py` 新增 `safe_change_name(name)`：校验 change 名为安全相对路径（非绝对、无 `..`），不合法抛 `InvalidChangeNameError`。**这是本变更的第一道外部输入校验点。**
- [x] 1.2 在 `paths.py` 新增 `archive_locations(workflow_home, change_name)`：枚举 `<home>/archive/*/<change>/` 下真实存在的目录，返回 `(month, dir)` 按月份升序。
- [x] 1.3 为 1.1/1.2 写单测：`..`/绝对路径/空名被拒；多月份归档按升序返回；`archive/` 不存在时返回空。

## 2. 路径安全：输出侧收口（D11，第 1 轮阻塞项 a 的修复）

- [x] 2.1 在 `artifacts.py` 实现单一判定 `_contained(home_resolved, path)`：路径 `resolve()` 后必须等于 home 或位于 home 之下。**这是全部对外路径的唯一收口点。**
- [x] 2.2 把 2.1 接入**全部三个**路径入口：schema 产物解析结果（4.4）、轮次目录内文件（3.2）、未认领文件遍历（4.6）；另外用于位置目录本身（3.1），使指向 home 外的 `archive/<month>` 符号链接被整体拒绝。
- [x] 2.3 逃出的路径不进入任何返回结构，改为追加一条 warning；**warning 文本只含该文件相对 change 目录的名字，不含解析后的目标路径**（否则修复本身又泄露了 home 外的路径）。
- [x] 2.4 为 2.1–2.3 写单测（用 `tmp_path` 造真实符号链接）：被声明为产物的外部链接被跳过；未认领遍历中的外部链接被跳过；同目录其余正常产物不受影响；指向外部的归档月份目录整体不被报告；断言全部 warning 文本中不出现 home 之外的任何路径片段。
- [x] 2.5 补一条**符号链接目录环**的测试：在 change 目录内造一个指向自身祖先的目录符号链接，断言遍历在有限时间内终止且不重复报告同一文件。标准库的 `rglob`/`glob` 对 `**` 不跟随目录符号链接，本测试把这份依赖钉成回归断言而不是口头假设。

## 3. 位置发现与元数据降级（D2 / D9 / D12）

- [x] 3.1 实现 `discover_locations(home, artifacts_dir, change_name)`：活跃目录 + `archive_locations` 的并集，经 2.2 收口，按 D2 顺序（归档月份升序在前、活跃在最后）；全空时抛 `ChangeNotFoundError`。
- [x] 3.2 实现轮次收集，**自己遍历 `.attempts/round-*` 而不调用 `attempts.list_rounds`**（D12）：轮次号从目录名解析，因此缺 `_meta.yaml` 的轮次目录仍被报告（门禁/裁决为空），其文件不会丢。
- [x] 3.3 实现统一的元数据安全读取（D9，第 1 轮阻塞项 b 的修复）：对 `.workflow.yaml` 与 `_meta.yaml` 一律处理缺失、`yaml.YAMLError`、以及**顶层不是映射**三种情况，全部降级为 warning，绝不抛非 `LoopspecError` 异常。
- [x] 3.4 单测：位置发现的仅活跃/仅归档/两者并存/多归档月份/全不存在（`change_not_found`）/顺序断言。
- [x] 3.5 单测（降级）：`.workflow.yaml` 缺失、`.workflow.yaml` 校验失败、`_meta.yaml` 缺失、`_meta.yaml` 内容为 YAML 列表、`_meta.yaml` 非法 YAML——五种情况均成功返回、带 warning，且该轮/该位置的文件照常报告。

## 4. 发现逻辑核心（D1 / D4 / D5 / D6）

- [x] 4.1 定义结果 dataclass：`ArtifactReport` / `ChangeLocation` / `SchemaArtifacts` / `NodeArtifacts` / `AttemptRound`，字段与 `specs/loopspec-cli` 的 `--json` 契约一一对应。
- [x] 4.2 实现 `resolve_requested_schemas(raw)`：逗号分隔、`strip`、丢空段、去重保序；strip 后为空抛 `ConfigValidationError`；**每段过 `models.KEBAB_RE`**，不合法抛 `ConfigValidationError`（D8 第二道输入校验点，同时挡掉 `../../etc` 与 `a/b`）。
- [x] 4.3 实现被考察 schema 集合解析（D5）：点名时用点名集合、加载失败即抛 `SchemaNotFoundError`/`SchemaValidationError`；未点名时用 config 候选 ∪ 各位置自报 schema，加载失败降级为 warning 并跳过。
- [x] 4.4 实现 schema × 位置的产物探测（D1/D4）：artifact root 由 `config.schema_path_for` + `paths.artifact_root` 得出，逐节点用 `outputs.node_output_patterns` + `outputs.resolve_outputs` 解析现存文件，结果过 2.2 收口。
- [x] 4.5 实现多方认领检测：同一路径被两个以上 schema 认领时追加 warning；位置级与全局 `files` 汇总去重并稳定排序。
- [x] 4.6 实现未认领文件枚举（D6）：遍历位置目录，沿用 `outputs` 的候选判定（排除 `.attempts/` 与保留名），过 2.2 收口，减去已被认领的路径集合；不额外过滤隐藏文件。

## 5. 核心逻辑单测 `tests/test_artifacts.py`

- [x] 5.1 `resolve_requested_schemas` 全分支：正常多值、空白容忍、去重保序、空取值报错、`../../etc` 报错、`a/b` 报错。
- [x] 5.2 探测归属：单 schema 全节点、glob 多文件展开、门禁只报存在的一侧、声明但未产出的不出现。
- [x] 5.3 接力场景：两个 schema 用不同 `path` 子目录，各自产物正确归属且 artifact root 不同。
- [x] 5.4 schema 集合：未点名覆盖全部候选、纳入自报但已不在候选的 schema、点名过滤、点名不存在时抛 `SchemaNotFoundError`、未点名时加载失败降级为 warning。
- [x] 5.5 保留文件与轮次：`state.md`/`.workflow.yaml` 既不入产物也不入未认领；`state.md` 单独报告；`.attempts/round-001` 逐轮报告。
- [x] 5.6 未认领与歧义：不匹配任何模式的文件进未认领；点名过滤后被排除的产物落入未认领；两个 schema 认领同一文件时双报 + warning + 汇总去重。
- [x] 5.7 只读断言：执行前后对 workflow home 做目录快照对比，断言完全一致（覆盖 D3 刻意绕开 `mkdir` 这一点），且对**归档位置**也跑一遍。

## 6. CLI 命令与人类可读渲染（D7）

- [x] 6.1 在 `cli.py` 注册 `artifacts` 命令：位置参数 `change_name`，选项 `--schemas` / `--home` / `--json`；全部 `LoopspecError` 走既有 `_fail` 统一错误契约。
- [x] 6.2 实现 dataclass → JSON 载荷的转换，字段名与 `specs/loopspec-cli` 契约逐字对齐；全部路径为绝对路径。
- [x] 6.3 在 `presentation.py` 新增 `render_artifacts_summary`：按位置分节渲染（类型/月份/路径、每 schema 文件计数、轮次数、未认领计数、末尾总计与 warning 计数），不接受 `as_json` 参数（沿用该模块既有约束）。
- [x] 6.4 人类可读路径的安全断言测试：产物名含 rich markup（如 `[red]out.md`）与控制字符时原样可见、不被吞掉、不注入转义序列。

## 7. 端到端 CLI 测试（扩展 `tests/test_cli.py`）

- [x] 7.1 活跃 change 全产物列出；归档后仍可查询（真实跑一遍 `loopspec archive` 再查）。
- [x] 7.2 `--schemas` 过滤、多值、点名不存在报 `schema_not_found`、空值报 `config_invalid`、不安全名报 `config_invalid`。
- [x] 7.3 `change_not_found` 与 `invalid_change_name`（`../../etc`）两条失败路径，断言输出不含 home 之外的路径。
- [x] 7.4 人类可读模式：不出现 JSON 字段名与 Python 容器字面量，且被聚合掉的明细在 `--json` 下仍可取到。

## 8. 文档同步（中英双份，由 docs 一致性测试兜底）

- [x] 8.1 `docs/en/cli-reference.md` 与 `docs/zh/cli-reference.md` 增加 `## loopspec artifacts` 小节：语法、选项表、`--json` 响应字段表、示例、失败情形；两语言首列标识符必须完全一致。
- [x] 8.2 `docs/en/agent-protocol.md` 与 `docs/zh/agent-protocol.md` 的「读一个不是你创建的 change」一节改以本命令为入口，说明接力工作流先读什么。
- [x] 8.3 明确记录三项已知代价：归属是「对当前 schema 定义的一次投影」而非历史事实；未认领文件的兜底作用；解析后逃出 home 的路径会被跳过并只在 `warnings` 中指名。

## 9. 验收

- [x] 9.1 `make lint` 通过（ruff + mypy）。
- [x] 9.2 `make test` 全绿，含文档一致性测试。
- [x] 9.3 在本仓库真实数据上手动验证：对 `loopspec/archive/2026-07/` 下某个已归档 change 执行 `loopspec artifacts <name>`，确认能列出其全部产物路径。
- [x] 9.4 复核 `design.md` 的 Open Questions 已在文档或后续跟进中留痕（`attempts.list_rounds` 的加固不在本次范围）。
