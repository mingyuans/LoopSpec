## 完成的任务

（本 Plan 未包含 design/tasks 节点，按 proposal 的范围与验收条件实现。）

- 新增 `resources_present(home)`：`fragments/` 或 `profiles/` 任一为非空真实目录即视为已有配置。
- `loopspec init` 新增 `--update-resources`；已有配置时：交互终端（非 `--json`）提示 `[y/N]`，仅 `y`/`yes` 同意，回车/其他/EOF 均拒绝；非交互或 `--json` 直接跳过；`--update-resources` 不询问直接执行原 `install_resources`。
- 跳过时人类输出提示 “Kept existing fragments/profiles; rerun with --update-resources ...”；JSON 新增 `resourcesUpdate`（`installed`/`skipped`），跳过时 `copiedWorkflowResources` 为 `[]`。
- 首次 init（目录不存在或为空）行为不变；Skill/命令脚手架、hooks、`config.yaml` 逻辑未改。
- 文档：中英文 `cli-reference.md` 补充用法与行为；`release-notes.md` 升级步骤改为带 `--update-resources`。

## 改动文件

- 源码：`src/loopspec/cli.py`、`src/loopspec/workflow_resources.py`
- 测试：`tests/test_cli.py`（新增 13 个用例，覆盖 AC1–AC9 及空目录场景）
- 文档：`docs/en/cli-reference.md`、`docs/zh/cli-reference.md`、`docs/en/release-notes.md`、`docs/zh/release-notes.md`

## 执行的检查

- 先写测试：实现前 `uv run pytest tests/test_cli.py -q` → 11 failed, 30 passed（新用例按预期失败）。
- 实现后 `uv run pytest tests/test_cli.py -q` → 41 passed。
- `make test` → 1154 passed in 476.16s。
- `make lint` → ruff: All checks passed（修复 1 处 import 后空行格式）；mypy: Success, no issues found in 35 source files。
- `uv run pytest tests/test_cli.py tests/test_docs_consistency.py tests/test_workflow_resources.py -q` → 86 passed。

## 与设计的偏差

无（无 design.md；与 proposal 一致）。额外增加了“两个目录存在但为空 → 视为首次 init”的测试。

## 后续事项

无。
