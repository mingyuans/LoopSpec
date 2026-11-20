## 完成的任务

- 1.1 `ResourceBundle.location(path)`（`workflow_io.py`）返回 `root.resolve()/relative_path(path)`；`DefinitionBundle.location`（`registry_store.py`）对 registry 定义返回 `snapshot.resolve()/path`，其余交给父类。
- 1.2 `workflow_runtime.fragment_paths(node, bundle)`：按 `instruction`、`template`、Gate pass 模板中第一个 `fragments/<name>/...` 路径确定 `fragmentName`，`fragmentDir` 由该文件在 bundle 中的实际位置向上推出（registry 定义因此落在快照中，而不是 home）；另给出 `instructionPath`、`templatePath`、Gate 的 `templatePaths.pass/fail`。`instructions()` 在读完资源后追加这些键，旧键不变。
- 1.3 `text_reports/node.py`：NODE 节显示 `fragmentName`、`fragmentDir`、`instructionPath`、`templatePath`、`templatePaths.pass/fail`；INSTRUCTION 说明写明相对路径按 `fragmentDir` 解析、只写文件名的在 `fragmentDir`（可能在 `references/` 等子目录）中；`INSTRUCTIONS.keys` 登记新键。
- 2.1 新增 `tests/test_fragment_paths.py`（5 项）：本地模式、嵌套 `be/code/implement` → `backend-code`、Gate `templatePaths`、registry 模式指向全局快照且项目无 `fragments/`、文本报告字段与说明。`tests/test_text_reports.py` 的键覆盖与叶子值测试自动覆盖新字段。
- 2.2 BDD：`node_gate.feature` 新增「执行指令给出节点所属 Fragment 的绝对目录与文件路径」。
- 2.3 LLM E2E：新增场景「指令引用的辅助文件按 fragmentDir 在注册表快照中找到」（registry 模式，requirements 指令要求把 `references/rules.md` 的口令写进产物）；`make test-llm` 在测试关卡运行。
- 3.1 `builtin/skills/continue.md` 第 2 步补充按 `fragmentDir` 定位辅助文件（副本经 `uv run loopspec` 同步）；`docs/{zh,en}/cli-reference.md`、`agent-protocol.md`、`release-notes.md`。

## 改动文件

- 代码：`src/loopspec/workflow_io.py`、`src/loopspec/registry_store.py`、`src/loopspec/workflow_runtime.py`、`src/loopspec/text_reports/node.py`
- skill：`builtin/skills/continue.md` 及 `.claude/skills/loopspec-continue/SKILL.md`、`.claude/commands/lpsx/continue.md`、`.codex/skills/loopspec-continue/SKILL.md`
- 测试：`tests/test_fragment_paths.py`（新增）、`tests/features/node_gate.feature`、`tests/steps/node_gate_steps.py`、`tests/features/llm_skills.feature`、`tests/steps/llm_steps.py`
- 文档：`docs/{zh,en}/{cli-reference,agent-protocol,release-notes}.md`

## 执行的检查

- `uv run ruff check src tests hatch_version.py`：All checks passed!
- `uv run mypy src hatch_version.py`：Success: no issues found in 51 source files
- `uv run pytest -q -n 2 -m "not timing and not llm"`：1765 passed, 1 skipped
- 实测：在锁定 aftership-channels registry（7b6cc1b）的演示项目中，`qa/clarify` 的 `fragmentName` 为 `qa-testcases`，`fragmentDir` 为 `~/.loopspec/registry/docs-coke-context-channels-loopspec-2d42f67b/7b6cc1b…/fragments/qa-testcases`，其 `references/` 下有指令引用的 `doc-writing-rules.md`、`case-writing-rules.md`。

## 与设计的偏差

- 设计中 `fragmentDir` 用 `bundle.location("fragments/<name>")` 计算；实现改为从文件位置向上推导，因为 `fragments/<name>` 本身不被 `owning_key` 识别为 registry 定义，会错误地指向 home。
- INSTRUCTION 说明补充了「只写文件名的引用可能在子目录中」：实测 `qa-testcases` 指令只写 `doc-writing-rules.md`，文件实际在 `references/` 下。

## 后续事项

- 模型按路径直接读取快照文件时不经过 CLI 的哈希校验；快照只读化可另行讨论。
