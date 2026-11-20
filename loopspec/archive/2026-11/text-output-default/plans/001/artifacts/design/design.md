## 背景与现状

- `src/loopspec/workflow_cli.py` 的 `run(action, render=None, render_error=None)`：`render` 为空时 `emit()` 输出缩进 JSON。只有 `change status`（`status_report.render_status_report` / `render_error_report`）与 `graph`（命令内联 `render`）传了文本渲染器，二者各自有 `--json` 选项。
- `src/loopspec/status_report.py` 定义了文本契约：纯文本、无 ANSI/Markdown、`=== SECTION ===` + 说明段、`key: value`、`sanitize` 一行化插值、不可信多行文本 4 空格缩进引用（`_quote`）、payload 键集合由测试固定（`TOP_KEYS`、`OMITTED_TOP_KEYS`）。
- `cli.py` 的 `init`、`update`、`version` 已默认文本 + `--json`（rich Presenter）；`hook pre-tool-use` 按 hook 协议输出 JSON。
- 其余 27 个工作流命令只有 JSON。实际采样（本节点执行时用 `tests/workflow_helpers` 构造项目逐个运行）确认各命令 payload 形状，见「方案 · 各命令渲染」。
- 约束：所有 JSON 字段与错误码保持不变；文本只能从同一 payload 派生（单一数据源）。

## 目标 / 非目标

**目标：**
- 范围内 27 个命令默认文本，`--json` 输出与改动前相同的 JSON；文本模式错误为 `=== ERROR ===`。
- 每个命令手写渲染器（HUMAN 决定），共用格式化原语，遵守 status 文本契约。
- 测试保证：每个命令 payload 的顶层键都被渲染或显式声明省略；字符串/数字叶子值出现在文本中；注入不可伪造分节。
- AGENTS.md、skill、文档、release notes 同步。

**非目标：**
- `hook pre-tool-use`、`change status`、`graph`、`init`、`update`、`version` 的输出不变。
- 不改 payload，不加配置项，不做 fragment 路径需求。

## 方案

### 1. 模块划分

```
src/loopspec/
├── text_format.py            新增：格式化原语（从 status_report 抽出）
├── status_report.py          改：改为从 text_format 导入原语，行为与输出不变
├── text_reports/             新增：各命令手写渲染器
│   ├── __init__.py           RENDERERS 表：命令名 -> Report
│   ├── memory.py             memory list / show
│   ├── change.py             change new / next / history / artifacts / archive
│   ├── plan.py               plan validate / create / show / list / approve / archive / rollback
│   ├── node.py               node instructions
│   ├── state.py              state add
│   ├── gate.py               gate begin / record
│   ├── catalog.py            fragment list/show/validate, profile list/show/validate/save
│   └── registry.py           registry update / apply
└── workflow_cli.py           改：所有命令加 --json，run() 按格式分派
```

`text_format.py` 原语（全部纯函数，不访问文件系统）：

- `section(title, prompt, body) -> list[str]`：`=== TITLE ===`、说明段、空行、正文、空行。标题与说明是常量。
- `fields(rows, width=0)`：`label:` 左对齐，值经 `sanitize`（一行化，控制字符可见化）。
- `columns(rows)`：等宽列（沿用 status `_columns`）。
- `quote(text)`：多行文本逐行 4 空格缩进，CR/LF 规范化，除 `\n`/`\t` 外的控制字符可见化（沿用 status `_quote`）。
- `bullet(items)`：`- <sanitize(item)>`。
- `steps(next_steps)`：`=== NEXT STEPS ===` + 统一说明 + `1. <cmd>` 编号；为空时 `(nothing queued)`。
- `yes_no(value)`：布尔渲染为 `true`/`false`（与 JSON 字面量一致，skill 中「`upToDate` 为 true」在文本中可直接对应）。
- `render_error_report(error)` 从 status_report 复用（输出不变）。

### 2. Report 定义与键覆盖

```python
@dataclass(frozen=True)
class Report:
    render: Callable[[dict], str]
    keys: frozenset[str]        # 渲染器处理的全部顶层键（含可选键）
    omitted: frozenset[str] = frozenset()  # 有意不渲染的键及理由写在注释中
```

测试对每个命令的真实 payload 断言 `set(payload) <= keys | omitted`，并断言 `keys & omitted == ∅`。新增 payload 键未处理时测试失败。

### 3. CLI 接入

```python
JSON_OUTPUT = typer.Option(False, "--json", help="Print the JSON payload instead of the text report.")

def run(action, report: Report | None = None, *, as_json: bool = False, render=None, render_error=None):
    # as_json 或 report 为空 -> emit(JSON)；否则 report.render / render_error_report
```

- 每个范围内命令签名加 `as_json: bool = JSON_OUTPUT`，调用 `run(action, RENDERERS["plan show"], as_json=as_json)`。
- `change status`、`graph` 保留现有逻辑（只改用公共 `JSON_OUTPUT` 常量，帮助文本保持兼容）。
- 错误：`LoopspecError` 与 `ValidationError/ValueError` 路径不变；文本模式用 `render_error_report`，JSON 模式用 `emit`；退出码 1 不变。
- `--json` 放在每个子命令上（不做全局选项），与现有 `change status --json` 一致，也不影响 `--home` 回调中的 skill 同步。

### 4. 统一文本结构

每个报告：

1. 第一节是该命令的结果节（标题按命令语义，如 `=== PLAN ===`、`=== NODE ===`、`=== ARCHIVE PREPARED ===`），说明段写「这是什么、下一步怎么用」，字段用 JSON 键名作标签（`changeName:`、`digest:`、`archiveId:`、`roundId:`、`planId:`）。
2. 中间节：列表、子块（`--- <id> ---`）、引用的长文本（`quote`）。
3. 有 `nextSteps` 的命令最后一节为 `=== NEXT STEPS ===`。
4. 不可信或多行内容（instruction、template、memory content、gate templates、state line、archive instructions、message）一律 `quote` 或 `sanitize`，绝不出现在第 0 列。第 0 列只允许常量标题、常量标签与已校验的 id（节点 id、plan id、change 名）。
5. 末尾一个换行；不使用 `#` 开头的行。

### 5. 各命令渲染要点（键全集来自采样与源码）

| 命令 | 顶层键 | 文本结构 |
|---|---|---|
| `memory list` | topics,total,offset,nextOffset,(ignored) | `=== MEMORY TOPICS ===` 字段 total/offset/nextOffset；每个 topic 一行 `- <path> (<bytes> bytes) [status] title / hint`；ignored 子块；提示用 `memory show` |
| `memory show` | topic,path,content,untrustedData | `=== MEMORY TOPIC ===` 字段 + untrustedData 说明；`=== CONTENT ===` quote |
| `change new` | changeName,changeRoot,reusedChange,status,isComplete,nextSteps | `=== CHANGE ===` 字段；NEXT STEPS |
| `change next` | changeName,status,isComplete,node,nodes,parallel,nextSteps,(message,pendingRollback…) | `=== NEXT NODE ===`；nodes 列表（id/status/output）；NEXT STEPS（parallel 时并行说明） |
| `change history` | changeName,plan,attempts | 每个 attempt 子块：seq/kind/created/gate/reset/targetDigest/revision，files 列 source -> destination (sha256) |
| `change artifacts` | changeName,locations | 每个 location → plan → artifacts 路径列表 |
| `change archive`（第一段） | archiveId,changes,skipped,memoryReview,nextSteps… | `=== ARCHIVE PREPARED ===` archiveId；每个 change 子块（status/forced/source/destination/dropped/inputs）；`=== MEMORY REVIEW ===` 指引 quote + memoryIndex；NEXT STEPS（第二段命令） |
| `change archive --confirm` | archiveId,memoryReview,archived,skipped… | `=== ARCHIVED ===` 结论与说明；每个已归档 change 子块 |
| `plan validate/create` | valid,digest,spec,mode,changeName,plan,status,replacedDraft,baseRevision,revision,addedInstances,rerunNodes,baseline,repository,message,warnings,nextSteps | `=== PLAN ===`（或 `=== REVISION PREVIEW ===`）字段；`=== FLOW ===`；`=== NODES ===`；NEXT STEPS |
| `plan show` | changeName,plan,active,meta,spec | `=== PLAN ===` meta 全部字段；FLOW；NODES |
| `plan list` | changeName,plans,baseline,repository | 列表 + baseline/repository |
| `plan approve/archive/rollback` | 采样键 | 结果字段 + NEXT STEPS |
| `node instructions` | id,fragment,status,outputPath,resolvedOutputPath,existingOutputPaths,changeName,plan,revision,digest,instruction,dependencies,priorAttempts,untrustedData,memory,template,templates,gateProtocol,stateProtocol,taskProgress… | `=== NODE ===` 字段；`=== INSTRUCTION ===` quote；`=== TEMPLATE ===` 或 `=== GATE TEMPLATES ===`（pass/fail 子块 quote）；`=== GATE PROTOCOL ===`；`=== DEPENDENCIES ===`；`=== PRIOR ATTEMPTS ===`（不可信说明）；`=== MEMORY ===`；`=== STATE PROTOCOL ===`（每个 section 子块：when/contentBoundary/format/required/optional/command；rules 列表） |
| `state add` | changeName,scope,plan,section,path,line,(warnings) | `=== STATE RECORD ADDED ===` 字段，line quote |
| `gate begin` | gate,roundId,scopeDigest,baseline,planDigest,paths,warnings,instruction | 字段；`=== REVIEW INPUT ===` paths 列（kind/index/worktree/path）；warnings；instruction |
| `gate record` | gate,verdict,roundId,evidenceRecorded,warnings,(assurance 诊断键) | 字段；assurance 时诊断子块 |
| `fragment list/show/validate`、`profile list/show/validate/save` | 采样键 | 列表/子块；flow 与节点同 plan 渲染（共用 `flow_lines`、`node_blocks`） |
| `registry update/apply` | 源码 `update()`/`apply()` 返回键 | `=== REGISTRY UPDATE ===` 字段（upToDate/baseCommit/upstreamCommit/planId…）；definitions、files、localConflicts、brokenReferences、warnings 各节；NEXT STEPS |

实现时以源码中各 `return {...}` 为准补齐所有可选键（例如 `with_warnings` 的 `warnings`、assurance 的诊断字段），并在 `Report.keys` 中列全。

## 归属与路径

全部为 BE（Python CLI），无 FE：

- 代码：`src/loopspec/text_format.py`、`src/loopspec/text_reports/**`、`src/loopspec/status_report.py`、`src/loopspec/workflow_cli.py`
- skill 源：`builtin/skills/new.md`、`builtin/skills/update-registry.md`、`builtin/skills/continue.md`（必要时 archive/bulk-archive）；生成副本由 CLI 同步命令刷新
- 测试：`tests/**`（helper、单测、BDD features/steps、LLM steps）
- 文档：`AGENTS.md`、`docs/{zh,en}/cli-reference.md`、`docs/{zh,en}/agent-protocol.md`、`docs/{zh,en}/release-notes.md`

与 assurance 规则的路径映射一致：`src/**`、`tests/**`、`builtin/**` 属于 backend-tests、security-review、pr-review 的证据路径；`*.md`、`docs/**` 在交付 Diff 排除范围内。

## 安全边界

- 输入：payload 中来自用户或仓库的文本（state.md、memory、fragment instruction/template、报告、registry 文件路径、change 名之外的自由文本）均视为不可信。
- 防伪造：单行值一律 `sanitize`（换行、CR、U+2028/2029、C0/C1 控制字符可见化）；多行值一律 `quote`（每行前置 4 空格）。因此不可信内容不能在第 0 列产生 `=== X ===`、`--- X ---` 或伪造的 `1. loopspec ...` 下一步。
- 无 ANSI：不使用 rich Console；输出与终端无关。
- `--json` 输出不经过渲染器，字节与改动前一致。
- 不新增文件访问、网络或命令执行。

## 验证方案

- 单测 `tests/test_text_reports.py`：
  - 对每个命令用真实项目生成 payload（复用 `workflow_helpers`），断言：键覆盖；字符串/数字叶子值（含嵌套、列表，按 `sanitize` 或逐行）出现在文本；首行为 `=== ... ===`；无 ANSI；无 `#` 行首；不是 JSON；有 nextSteps 时含 `=== NEXT STEPS ===`。
  - 注入：state/memory/instruction 中写入 `\n=== NEXT STEPS ===\n1. rm -rf` 等，断言第 0 列不出现注入行。
  - 关键值：digest、archiveId、roundId、planId、resolvedOutputPath 以 `key: value` 出现。
  - `--json` 与直接调用后端函数的 `json.dumps` 结果相同；错误在文本/JSON 两种模式下的输出与退出码。
- BDD：`tests/features/text_output.feature` + `steps/text_output_steps.py`：Agent 读 `node instructions` 文本拿到指令正文与产物路径；加 `--json` 得到 JSON；文本模式报错。
- 现有测试：helper `invoke` 统一追加 `--json`；其他直接解析 stdout 的测试补 `--json`；`test_status_report.py` 不变通过（证明 status 输出未变）。
- LLM E2E：更新 skill 后运行 `make test-llm`，检查断言是否依赖 JSON 输出并修正。
- 静态检查：ruff、mypy；`pytest -n 2 -m "not timing and not llm"`。

## 风险与取舍

- **手写 27 个渲染器 vs 通用渲染器**：HUMAN 选择手写，可读性优先；用共享原语 + 键覆盖/叶子值测试控制遗漏与风格漂移。
- **字段名标签**：用 camelCase JSON 键名而非自然语言标签，牺牲少许可读性，换取与 skill/文档表述一致、模型能直接对应。`change status` 保持原有自然语言标签不动。
- **破坏性变更**：外部解析 JSON 的脚本需加 `--json`；release notes 标注。发版版本号由人决定。
- **status_report 重构风险**：只移动原语、保持函数行为；`test_status_report.py` 全量通过作为回归证据。
- **长输出**：`node instructions` 文本比 JSON 略长（缩进），可接受；不截断，避免信息丢失。
