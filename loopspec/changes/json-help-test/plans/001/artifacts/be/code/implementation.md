## 完成的任务

- `test_every_rendered_command_takes_json` 改为遍历 `typer.main.get_group(app)` 的命令对象，检查每个渲染命令的参数 `opts` 中有 `--json`。

## 改动文件

- `tests/test_text_reports.py`

## 执行的检查

- `FORCE_COLOR=1 TERM=xterm-256color uv run pytest tests/test_text_reports.py -k takes_json`：修复前 1 failed（复现 CI），修复后 1 passed。
- `uv run ruff check tests/test_text_reports.py`：通过。

## 与设计的偏差

- 无（缺陷修复流程无设计节点）。
