## 完成的任务

- 1.1 新增 `tests/test_self_update.py`（50 个用例）；首次运行时因 `loopspec.self_update` 不存在而收集失败（红）。
- 2.1 `errors.py` 新增 `UpdateInvalidVersionError`、`UpdateFetchFailedError`、`UpdateVerifyFailedError`、`UpdateInstallerMissingError`、`UpdateInstallFailedError`，每个都带默认 `fix`。
- 2.2 新增 `self_update.py`：版本白名单校验（`fullmatch`，规则与 install.sh 相同）、checksums 解析（精确文件名、恰好一行、64 位 hex）、`https_fetch`（仅 https，自定义重定向处理器拒绝离开 https，30s 超时，分块读取并设大小上限，网络异常统一映射为 `update_fetch_failed`）、`pick_installer`（uv → pipx）、`default_runner`（`subprocess.run(list)`，不经 shell）、`run_update`（未固定版本且与当前版本相同时不下载；`--check` 只读；先确认 checksum 条目存在再下载 wheel；`hmac.compare_digest` 校验；在临时目录中安装后清理）。
- 2.3 `cli.py` 新增顶层 `update` 命令（`--version`、`--check`、`--json`）。人类模式输出 “Downloading…” 和结果行；JSON 模式下 stdout 只输出 JSON，安装器输出改走 stderr。
- 3.1 中英文 `cli-reference.md`：约定段补上 `update`，新增 `## loopspec update` 一节，错误码表新增 5 行。
- 3.2 README 的 “Update and uninstall” 小节加入 `loopspec update` / `--check` / `--version` 用法，保留 install.sh 方式。
- 4.1 / 4.2 回归见下文。

## 改动文件

- 新增：`src/loopspec/self_update.py`、`tests/test_self_update.py`
- 修改：`src/loopspec/errors.py`、`src/loopspec/cli.py`、`tests/test_workflow_cli.py`（顶层命令集合加入 `update`）
- 文档：`docs/en/cli-reference.md`、`docs/zh/cli-reference.md`、`README.md`

## 执行的检查

- `uv run pytest tests/test_self_update.py -q`：首次（加实现前）收集错误（ImportError）；实现后 49 passed、1 failed（测试数据中的恶意版本带空格，被当成非法行跳过；改为不含空格的注入串后通过），最终 50 passed。
- `uv run pytest -q`（全量）：1130 passed、1 failed，失败的是 `test_workflow_cli.py::test_top_level_commands_are_resources`（固定顶层命令集合，不含 `update`）。更新期望值后 `uv run pytest tests/test_workflow_cli.py -q`：45 passed。
- `uv run pytest tests/test_docs_consistency.py tests/test_cli.py tests/test_self_update.py -q`：121 passed。
- `make lint`：ruff “All checks passed!”；mypy “Success: no issues found in 35 source files”。

## 与设计的偏差

- `run_update` 增加了可选回调 `on_download`，供 CLI 在人类模式下下载前输出 “Downloading loopspec X...”；设计中写的是 CLI 输出这一行，但下载发生在 `run_update` 内部，所以用回调实现。
- 设计中没有列出 `tests/test_workflow_cli.py`；这个已有测试固定了顶层命令集合，必须同步加入 `update`。

## 后续事项

- 未对真实 GitHub 做联网冒烟测试，留给 QA 节点执行（只读的 `--check`）。
