# Implementation Report

## Tasks Implemented

全部 7 组 57 条已勾选。按组：

**1. 渲染模块骨架（1.1–1.7）** — 新建 `src/loopspec/status_report.py`，导出 `render_status_report(payload) -> str` 与 `render_error_report(error, message, fix) -> str`，模块文档写明"纯文本 / 字节稳定 / 单一数据通路"三条契约。从 `presentation` re-export `sanitize` 作为报告与错误输出**共用**的消毒入口（1.2），并在模块文档里写下"消毒消灭换行 ⇒ 内插值无法开启新行 ⇒ 无法伪造 `=== SECTION ===`"这条推理链、注明它已是唯一结构防线、且显式点出 glob 匹配路径同样走这个入口。分节常量、字段覆盖集合（`TOP_LEVEL_FIELDS`/`NODE_FIELDS` 及两份"有意省略"名单，各带省略理由）、列对齐辅助、六段内置说明常量、逃逸占位符常量 `<outside artifact root>` 均集中定义。

**2. 各节渲染（2.1–2.13）** — OVERVIEW（artifact root 仅在与 change root 不同时出现）、NODES 首行（gate 产物两形态：无产物用 `dir/{pass,fail}.ext` 紧凑式，已产出给实际路径）、glob 多行（首个同行、其余缩进续行、顺序沿用 payload 不自行排序）、D17 相对化与逃逸占位符、D16 续行不顶格（并在渲染函数处写下理由注释）、备注固定优先级、GATE FAILURES 子块（`blockingIssues` 逐条编号缩进两格）、PENDING ROLLBACK、NEXT STEPS（空时占位行）、节序、每节说明加空行。2.13 的逐字核对见下节。

**3. CLI 接线（3.1–3.5）** — `cli.status` 的 `as_json` 假分支改走 `render_status_report(result)`，`result` 构造过程一字未改；`cli._fail` 的非 JSON 分支改走 `render_error_report`（`--json` 分支不动，此改动对全部子命令生效）；三处指向 `loopspec status` 的 `nextSteps` 文案去掉 `--json`（`cli.py:467`、`cli.py:637`、`cli.py:754`），指向 `instructions` 的保留。3.5 已核实：`schema_selection_required` 走 `_emit`（`cli.py:437`），未被 `_fail` 的改动触碰。

**4. Skill 模板（4.1–4.2）** — `skill_templates.py` 三处 `loopspec status <change-name> --json` 去掉 `--json`；测试新增两条断言（全部模板中 `loopspec status` 所在行不含 `--json`；`loopspec-continue` 的 `instructions` 调用仍含 `--json`）。

**5. 测试（5.1–5.24）** — 新建 `tests/test_status_report.py`，43 个测试，覆盖版式、条件节、多行 glob、续行不参与列宽、零匹配、备注优先级、gate 两形态、字节稳定性、字段覆盖并集、符号链接逃逸、消毒、行首规则、错误路径、`nextSteps` 文案、内置说明。5.24 回归：`tests/test_cli.py` 现有 `--json` 断言一条未改即通过。

**6. 文档（6.1–6.4）** — 双语 `cli-reference.md` 的 `loopspec status` 章节新增默认输出说明、一份带 `loopspec:example=status-report` 标记的字面示例、五节与 payload 字段的对应表、以及六条"读节点清单时注意"；双语 `agent-protocol.md` 改掉"总是传 `--json`"这条规则（`status` 例外）、去掉 6 处 `status --json`、新增「不带 `--json` 读 `status`」小节与分节↔字段映射表；`README.md`、双语 `README.md`/`schema-reference.md`/`workflows/secure-spec-driven.md` 的 `status` 示例去掉 `--json`；`README.md` 里"Omit `--json` for a plain-text summary intended for humans"一句改写为 `status` 例外的表述。

**7. 收尾（7.1–7.2）** — 见下节。

## Files Changed

新增：

- `src/loopspec/status_report.py`
- `tests/test_status_report.py`

修改（代码）：

- `src/loopspec/cli.py`
- `src/loopspec/skill_templates.py`
- `tests/test_skill_templates.py`

修改（文档）：

- `README.md`
- `docs/en/README.md`、`docs/en/agent-protocol.md`、`docs/en/cli-reference.md`、`docs/en/schema-reference.md`、`docs/en/workflows/secure-spec-driven.md`
- `docs/zh/README.md`、`docs/zh/agent-protocol.md`、`docs/zh/cli-reference.md`、`docs/zh/schema-reference.md`、`docs/zh/workflows/secure-spec-driven.md`

未触碰：`src/loopspec/presentation.py`（D1）、`src/loopspec/config.py` 与 `src/loopspec/models.py`（`config.yaml` 与 `WorkflowConfig` 按 `approval` 第 3 轮撤销的结论不动）、`src/loopspec/outputs.py`（D17 在渲染层解决，未改取值层）。

## Tests and Checks

**`make lint`：干净。**

```
uv run ruff check src tests hatch_version.py
All checks passed!
uv run mypy src hatch_version.py
Success: no issues found in 25 source files
```

**`make test`：756 passed。**

```
============================= 756 passed in 10.58s =============================
```

需要如实记录的一点：在**本次实现所用的 shell 会话**里直接跑 `make test` 会看到 `1 failed, 755 passed`，失败的是 `tests/test_cli.py::test_artifacts_human_output_renders_markup_like_paths_verbatim`（断言 `artifacts` 的人类可读输出不含 ANSI）。原因是该会话设置了强制彩色的环境变量，使 rich 即便在非 TTY 下也上色；`FORCE_COLOR= CLICOLOR_FORCE= make test` 即为上面那份 756 全绿的输出。三点证据表明它与本次改动无关：① 该测试属 `artifacts` 命令，本次未触碰；② 会话开始、任何代码改动之前跑同一条命令即已失败；③ 清掉那两个变量后全绿。另一侧对称的现象：强制 `NO_COLOR=1` 时改为 `tests/test_presentation.py` 的两条"断言颜色存在"的测试失败。两者都是既有的环境敏感性，不是本次引入的。

**`tests/test_docs_consistency.py`（6.4）：40 passed**，双语集合相等与带标记示例块的逐字节比对全部通过。

**`tests/test_status_report.py`：43 passed。**

**7.2 的逐字核对**：写了一个脚本从 `design.md` 提取五份 Rendered Examples，用对应 payload 渲染后逐字比较，结果全部 `IDENTICAL`：

```
example 1 (normal, multi-line glob): IDENTICAL
example 2 (gate FAIL): IDENTICAL
example 3 (zero matches): IDENTICAL
example 4 (escaped symlink, NODES only): IDENTICAL
example 5 (error output): IDENTICAL
```

另外对本 change 自己执行了 `loopspec status cli-status-markdown-output`（其 `specs` 节点正是一个匹配三个文件的 glob 节点），多行版式与续行缩进符合预期。

## Deviations from the Design

三处，都是 design 未规定而实现必须决定的细节，没有一处推翻 design 的裁定：

1. **gate 双产物不在同一目录或后缀不同时的退化形式。** D5 只规定了紧凑形式 `dir/{pass,fail}.ext`，而它无法表示两个分处不同目录的产物。实现的选择是退化为 `pass 路径 | fail 路径`（内置 schema 的每个 gate 都同目录同后缀，因此这条路径在实践中不会走到），并在函数 docstring 注明这是 design 未覆盖的情形。
2. **`=== NEXT STEPS ===` 为空时的占位文本。** spec 要求"一行占位说明"但未给字面文本，design 的样例也没有空 `nextSteps` 的例子。实现用常量 `(nothing queued)`。
3. **`fix` 为空时的错误输出。** design 样例里 `fix` 有值；实测 `change_not_found` 的 `fix` 为空字符串，而每行都做 `rstrip`，因此输出为裸标签 `fix:` 而不是 `fix:` 加尾随空格。这与"行尾不留尾随空白"一致，测试按此断言。

另有一处**实现期发现，不构成偏差但值得记录**：`resolve_outputs()` 按解析后的绝对路径排序，因此一个以 `=` 开头的文件名（如安全测试用的 `=== NEXT STEPS ===.md`）会排在最前，从而落在节点的**首行**产物列，而不是 D16/任务 5.18 描述里假设的缩进续行。防线仍然成立——首行以节点 ID 开头，产物列永不在第 0 列，因此该取值同样无法开启分隔行——测试断言已相应改为"含该文件名的任何行都不顶格"，比原描述更准确地表达了要保的性质。

## Follow-Ups

以下均为 `security` 与 `approval` 已判定为非阻塞、本次刻意未做的事：

- 指向 artifact 根目录**内部**的符号链接会显示其目标的相对路径而非链接自身的名字。要修需让 payload 携带未跟随符号链接的 relative name，会动 `--json` 契约，属后续 change。
- `_is_artifact_candidate()` 只按未解析路径排除 `.attempts/`，因此指向 `.attempts/` 内部的符号链接能绕过该过滤把归档产物列回当前节点（既有行为，压成计数时同样成立）。
- glob 列全不设上限（`approval` 第 5 轮签核）。批量建文件可把 `=== NEXT STEPS ===` 挤出 LLM 有效上下文，代价已知并接受。
- D11：`loopspec new` 的 `schema_selection_required` 仍走 `_emit`，因此非 JSON 错误输出存在 `=== ERROR ===` 与 `key: value` 两种形态。
- loopspec 自身的解析缺陷：`gate_outcome` 把裁决文件中 `## Blocking Issues` 之外各节的 `-` 列表项也收进 `blockingIssues`。
- 本仓库测试对终端彩色环境敏感（`test_cli.py` 的 markup 断言与 `test_presentation.py` 的颜色断言方向相反），在强制彩色或强制无色的 shell 里各有一侧会失败。与本次改动无关，但值得单独处理成一个 change。
