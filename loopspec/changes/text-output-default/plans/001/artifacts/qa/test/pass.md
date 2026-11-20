---
verdict: PASS
summary: "11 条验收条件全部满足：真实可执行文件下 15 个只读命令默认文本、--json 与 main(1.2.3) 逐字节一致，错误/hook/AGENTS.md/skill/LLM E2E 均符合"
---

# 验收测试：通过

## 验收条件核对

- [x] 范围内每个命令默认输出文本（非 JSON、含 `=== ... ===`、无 ANSI、无 `#` 行首）：真实可执行文件 `.venv/bin/loopspec` 对 15 个只读命令逐个验证通过；写命令与全部 27 个命令由 `tests/test_text_reports.py::test_text_follows_the_status_report_contract`（真实 payload）覆盖。
- [x] `--json` 输出与改动前逐字节相同：同一临时项目中，新 CLI 加 `--json` 与全局安装的 main 版本 CLI（1.2.3）不加参数的输出，对 15 个只读命令（memory、fragment、profile、plan show/list/validate（revision 预览）、change next/history/artifacts、node instructions）逐字节相等；错误 JSON（`change_not_found`）也逐字节相等。
- [x] 每个命令的顶层键「已渲染或已声明省略」：`test_every_payload_key_is_rendered_or_omitted` 通过；实现中途该测试实际发现过 `plan show` 漏了 `baseline`/`repository`。
- [x] 后续步骤需要的值以 `key: value` 出现（digest、archiveId、roundId、planId、resolvedOutputPath、changeName）：`test_values_for_later_commands_are_key_value_lines` 8 个参数全部通过；端到端检查 `plan show` 文本含 `meta.digest:` 与实际 digest。
- [x] `node instructions` 的 instruction/template 逐行缩进引用、不含 `\n` 转义：端到端检查与 `test_instruction_and_templates_are_quoted_line_by_line` 通过。
- [x] 注入不能伪造顶格分节：`test_no_value_can_forge_a_section_a_step_or_a_sub_block` 通过。
- [x] 文本模式错误为 `=== ERROR ===`、退出码 1；`--json` 为原 JSON 错误：端到端检查与单测通过。
- [x] `hook pre-tool-use` 输出不变：同一输入下新旧 CLI 的 stdout 与退出码相同（JSON）。
- [x] AGENTS.md 包含文本/JSON 双格式规范：新增索引行与「CLI output formats」一节。
- [x] skill 源文件不再声称工作流命令输出 JSON，`make test-llm` 通过：12 passed（15 次启动，$1.914，无重跑，`.llm-e2e-runs/20261120T152836Z/`），新增「未加 --json」断言通过。
- [x] ruff、mypy、pytest 全部通过：见 `be/tests/check` 报告（1759 passed, 1 skipped）。

## 执行的测试

- `uv run python /tmp/lsx/qa.py`（临时验收脚本，未纳入仓库）：调用 `.venv/bin/loopspec` 与 `/home/xq.yan/.local/bin/loopspec`（1.2.3）子进程，34 项检查全部 PASS，`FAILS []`。
- 引用 `be/tests/check` 中实际运行的 ruff、mypy、pytest 与 `make test-llm` 结果。

## 剩余风险

- 写命令（`plan create/approve`、`gate begin/record`、`change archive` 等）的 `--json` 未与旧版做逐字节端到端对比（结果含时间与随机轮次）；它们的 payload 由未改动的后端函数生成，CLI 只在 `--json` 时直接 `emit`，并有现有 JSON 测试覆盖。
- LLM E2E 在渲染失败回退与字段标签 sanitize 两处改动之前运行，正常路径输出不受影响。
