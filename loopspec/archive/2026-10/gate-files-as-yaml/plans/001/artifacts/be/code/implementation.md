## 完成的任务

本 bugfix Plan 无 tasks.md，按 `proposal.md` 的验收条件与已确认的测试计划（Y1–Y6）执行：

- 先写 `tests/test_gate_file_format.py`（Y1–Y5）并运行：Y1、Y2、Y3/Y4 共 3 个用例失败（文件为单行 JSON），Y5（旧 JSON 文件可读）通过。
- `src/loopspec/workflow_evidence.py` 4 处（round 文件、`begin.yaml` ×2、`evidence.yaml`）与 `src/loopspec/workflow_assurance.py` 3 处（round 文件、`assurance.yaml`、`evidence.yaml`）由 `write_json()` 改为 `write_yaml()`，导入同步替换，参数（含 `exclusive=True`）不变。
- 读取侧未改：仍为 `ResourceBundle.model()` → `parse_yaml()`，旧 JSON 内容文件照常解析。

## 改动文件

- `src/loopspec/workflow_evidence.py`
- `src/loopspec/workflow_assurance.py`
- `tests/test_gate_file_format.py`（新增）

## 执行的检查

- 修复前：`uv run pytest -q tests/test_gate_file_format.py`：3 failed, 1 passed。
- 修复后：`uv run pytest -q tests/test_gate_file_format.py tests/test_workflow_evidence.py tests/test_workflow_assurance.py tests/test_workflow_e2e.py`：46 passed。
- `make lint`：ruff 通过；mypy `Success: no issues found in 33 source files`。
- 全量 `make test` 在 `be/tests/check` gate begin 之后执行。

## 与设计的偏差

- 测试计划中 Y3 与 Y4 合并为一个用例 `test_assurance_record_writes_yaml_and_no_json_remains`（同一场景推进到保障通过后先检查三个文件，再遍历全部 `.yaml`）。

## 后续事项

无。
