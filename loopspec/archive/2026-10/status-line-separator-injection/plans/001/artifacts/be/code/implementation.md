## 完成的任务

本 bugfix Plan 无 tasks.md，按 `proposal.md` 的验收条件与已确认的测试计划（U1、I1–I4）执行：

- 先写测试并确认失败：`tests/test_presentation.py::test_sanitize_escapes_unicode_line_separators`（U1）、`tests/test_status_report.py::test_note_line_separators_cannot_forge_sections`（I1）、`::test_state_line_separators_stay_quoted`（I2）、`::test_every_report_breaks_lines_only_on_newline`（I3，覆盖 unplanned / planning / active / 失败 Gate 四种报告），4 failed。
- `presentation._CONTROL_RE` 增加 U+2028、U+2029；新增 `escape_control()`：码点 ≤ 0xFF 输出 `\xNN`，否则输出 `\uXXXX`；`sanitize()` 改用它。
- `status_report._QUOTED_CONTROL` 增加 U+2028、U+2029，`_quote()` 改用 `escape_control()`，`state.md` 原文中的行分隔符以 ` ` / ` ` 显示在同一缩进行内。
- I4（`--json` 不变）由既有 `test_json_flag_returns_the_payload` 等用例覆盖。

## 改动文件

- `src/loopspec/presentation.py`：`_CONTROL_RE`、`escape_control()`、`sanitize()`
- `src/loopspec/status_report.py`：导入 `escape_control`、`_QUOTED_CONTROL`、`_quote()`
- `tests/test_presentation.py`：U1
- `tests/test_status_report.py`：I1–I3

## 执行的检查

- 修复前：`uv run pytest -q tests/test_presentation.py::test_sanitize_escapes_unicode_line_separators tests/test_status_report.py -k "line_separators or only_on_newline"`：4 failed。
- 修复后：`uv run pytest -q tests/test_presentation.py tests/test_status_report.py`：54 passed。
- `make lint`：ruff 通过；mypy `Success: no issues found in 33 source files`。
- 全量 `make test` 在 `be/tests/check` gate begin 之后执行。

## 与设计的偏差

无（本 Plan 无独立设计文档；实现与 `proposal.md` 范围一致）。

## 后续事项

无。
