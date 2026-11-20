## 背景与现状

- 编译后的 Plan 节点（`ResolvedNode`）中，`instruction`、`template`、`gate.templates.pass/fail` 是相对 workflow home 的路径，形如 `fragments/<fragment 名>/<文件>`；嵌套 fragment 已展开为实际定义节点的 fragment（如 `fragments/backend-code/implement.instruction.md`）。
- `workflow_runtime.instructions()` 用一个 `definition_bundle(home)` 读取这些文件：非 registry 模式为 `ResourceBundle(home)`（`root=home`）；registry 模式为 `DefinitionBundle`，registry 定义从已校验的快照 `bundle.snapshot` 读取并逐文件核对 lock 中的哈希，其余从 home 读。
- 输出中没有 fragment 名与目录。

## 目标 / 非目标

**目标：** `node instructions` 新增 `fragmentName`、`fragmentDir`、`instructionPath`、`templatePath`、`templatePaths`；文本报告展示并说明相对引用的解析基准；skill、文档同步。

**非目标：** 改写指令文本、映射旧路径、修改上游 registry、调整快照权限、改变 `fragment` 字段含义。

## 方案

1. `workflow_io.ResourceBundle` 新增 `location(path: str) -> Path`：返回 `relative_path(path)` 在 `self.root` 下的绝对路径（`root.resolve()`，不跟随最后一级以外的检查，仅拼接）。`DefinitionBundle` 覆盖：`is_registry(path)` 时返回 `self.snapshot.resolve() / path`，否则调用父类。调用方必须先 `read()` 成功（证明该文件存在且通过校验），再取 `location()`。
2. `workflow_runtime`：
   - `fragment_name(node)`：取 `instruction`、`template`、`gate.templates.pass` 中第一个非空路径，按 `owning_key` 规则解析出 `fragments/<name>` 的 `<name>`；都没有时为 `None`。
   - `instructions()` 在已有 `resource_text(..., bundle)` 读取之后加入：
     - `fragmentName`、`fragmentDir`（`bundle.location("fragments/<name>")`，无名称时两者为 `null`）；
     - `instructionPath`（有 `node.instruction` 时）、`templatePath`（有 `node.template` 时）、`templatePaths: {pass, fail}`（有 Gate 模板时）。
   - 新增键全部放在已有键之后，旧键与值不变。
3. 文本渲染器 `text_reports/node.py`：NODE 节加入 `fragmentName`、`fragmentDir`、`instructionPath`、`templatePath`、`templatePaths.pass/fail` 字段（`key: value`，值经 `sanitize`）；`PROMPT_INSTRUCTION` 增加一句：指令中出现的相对路径（如 `references/…`、`scripts/…`）或只写文件名的引用，都相对 `fragmentDir` 解析；`INSTRUCTIONS.keys` 登记新键。
4. skill `builtin/skills/continue.md` 第 2 步补充：指令引用的辅助文件按 `fragmentDir` 定位。文档：`docs/{zh,en}/cli-reference.md` 的 `node instructions` 字段说明、`agent-protocol.md` 对应条目、`release-notes.md`。

## 归属与路径

BE：`src/loopspec/workflow_io.py`、`src/loopspec/registry_store.py`、`src/loopspec/workflow_runtime.py`、`src/loopspec/text_reports/node.py`、`builtin/skills/continue.md`（副本由 `uv run loopspec` 同步）、`tests/**`、`docs/**`。

## 安全边界

- 路径只来自已编译、已批准的 Plan 中的节点定义，并先经过 `bundle.read()`（`relative_path` 校验、registry 文件哈希校验），之后才计算绝对路径；不接受用户输入路径。
- 新输出只是路径字符串，不新增读写；文本模式经 `sanitize`。
- 剩余风险：模型按路径直接读取快照文件时不再经过哈希校验（快照物化时已完整校验，位于权限受控的用户目录）。

## 验证方案

- 单测（`tests/test_workflow_runtime.py` 或新文件）：本地模式 `fragmentDir == home.resolve()/fragments/requirements`；嵌套 `be/code/implement` 的 `fragmentName == backend-code`；Gate 节点 `templatePaths` 内容与 `templates` 相同；`instructionPath` 内容与 `instruction` 相同。
- registry 模式（`tests/registry_helpers.registry_project` + `sync`）：`fragmentDir` 位于 `LOOPSPEC_REGISTRY_STORE` 之下、存在，`instructionPath` 内容与 `instruction` 相同。
- `tests/test_text_reports.py` 的键覆盖与叶子值测试自动覆盖新字段；新增断言 INSTRUCTION 说明提到 `fragmentDir`。
- BDD：`node_gate.feature` 新增「执行指令给出 fragment 的绝对目录」场景。
- LLM E2E：`make test-llm` 全部通过（skill 文本有改动）。

## 风险与取舍

- 选择「只给绝对路径」，不改写正文：实现简单、正文保持原样；依赖模型按说明拼路径，由 skill 与文本说明引导。
- `location()` 只拼接路径，不再次检查文件存在；存在性由此前的 `read()` 保证（目录本身由 fragment 定义保证）。
