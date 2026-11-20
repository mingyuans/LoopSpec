## 1. 格式化原语与 CLI 接入

- [x] 1.1 新增 `text_format.py`（section/fields/columns/quote/bullet/steps/yes_no），`status_report.py` 改为复用；验证：`tests/test_status_report.py` 全部通过。
- [x] 1.2 `workflow_cli.py`：公共 `JSON_OUTPUT` 选项、`run()` 按 `as_json`/Report 分派；所有范围内命令加 `--json`；验证：`--help` 显示 `--json`，`--json` 输出与改动前一致。

## 2. 各命令渲染器

- [x] 2.1 `memory list|show`
- [x] 2.2 `change new|next|history|artifacts|archive`（两段）
- [x] 2.3 `plan validate|create|show|list|approve|archive|rollback`（含 revision 预览）
- [x] 2.4 `node instructions`（普通节点、code-evidence Gate、assurance Gate、有 priorAttempts/taskProgress）
- [x] 2.5 `state add`、`gate begin|record`
- [x] 2.6 `fragment list|show|validate`、`profile list|show|validate|save`
- [x] 2.7 `registry update|apply`

## 3. 测试

- [x] 3.1 helper `invoke` 及所有解析 stdout JSON 的测试/steps 改用 `--json`；验证：原有测试全部通过。
- [x] 3.2 `tests/test_text_reports.py`：每个命令键覆盖、叶子值出现、结构约束、关键值、注入防护、文本/JSON 错误输出。
- [x] 3.3 BDD `features/text_output.feature` + `steps/text_output_steps.py`。
- [ ] 3.4 LLM E2E 检查并修正依赖 JSON 的断言；`make test-llm` 通过。

## 4. 文档与 skill

- [x] 4.1 AGENTS.md 增加「CLI 输出格式」规范与索引行。
- [x] 4.2 skill 源文件（new/update-registry/continue 等）更新表述，执行 CLI 同步生成副本。
- [x] 4.3 `docs/{zh,en}/cli-reference.md`、`agent-protocol.md`、`release-notes.md` 更新；`test_docs_consistency` 通过。

## 5. 检查

- [x] 5.1 ruff、mypy、`pytest -n 2 -m "not timing and not llm"` 全部通过，记录真实结果。
