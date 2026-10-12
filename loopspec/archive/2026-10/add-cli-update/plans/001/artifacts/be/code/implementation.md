## 完成的任务

- 1.1 新增 `tests/test_self_update.py`；第一轮先运行确认收集失败（红），返工轮新增用例时同样先确认 6 个用例失败。
- 2.1 `errors.py` 新增 5 个 `Update*Error`（`update_invalid_version`、`update_fetch_failed`、`update_verify_failed`、`update_installer_missing`、`update_install_failed`），每个都带默认 `fix`。
- 2.2 新增 `self_update.py`：
  - 版本白名单与 install.sh 一致；
  - checksums 精确匹配恰好一行，digest 为 64 位 hex；
  - `https_fetch`：仅 https，重定向不能离开 https，30 秒超时，大小上限，异常统一映射；
  - `pick_installer`：先 uv 后 pipx；`default_runner`：不经 shell；
  - `run_update`：已最新时不下载；`--check` 只读；先确认 checksum 条目再下载 wheel；用 `hmac.compare_digest` 比较；在临时目录安装后清理。
- 2.3 `cli.py` 新增 `update`（`--version`、`--check`、`--json`）。JSON 模式下安装器输出走 stderr；人类模式下载前输出提示。
- 3.1 / 3.2 中英文 cli-reference 与 README 已更新。
- **返工（attempt 1，来自 be/review/check FAIL）：**
  - `run_update` 安装段捕获 `OSError`：暂存 wheel 失败（磁盘满、TMPDIR 不可写）时报 `update_install_failed`；安装器启动时 `FileNotFoundError` 报 `update_installer_missing`；其他 `OSError` 报 `update_install_failed`。不再以 traceback 退出。
  - 在 `--check --version X` 下返回 `available` 时，提示改为 `loopspec update --version X`。
  - 补充 10 个用例：安装器无法启动（3 种）、临时目录不可写、`--check` 加固定版本、`default_runner` 传参且不使用 shell、CLI 在 JSON 模式下 runner 绑定 `stdout`、人类模式的 runner 与下载提示、CLI 非法 `--version` 的 JSON 失败路径、固定版本提示文案。

## 改动文件

- 新增：`src/loopspec/self_update.py`、`tests/test_self_update.py`
- 修改：`src/loopspec/errors.py`、`src/loopspec/cli.py`、`tests/test_workflow_cli.py`（顶层命令集合加入 `update`）
- 文档：`docs/en/cli-reference.md`、`docs/zh/cli-reference.md`、`README.md`

## 执行的检查

- 返工前：`uv run pytest tests/test_self_update.py -q` → 6 failed、54 passed（新用例为红，符合预期）。
- 返工后：`uv run pytest tests/test_self_update.py -q` → 60 passed。
- `uv run pytest tests/test_self_update.py tests/test_cli.py tests/test_docs_consistency.py tests/test_workflow_cli.py -q` → 176 passed。
- `make lint` → ruff 通过；mypy “Success: no issues found in 35 source files”。
- 全量 `make test` 留给 be/tests/check 门禁执行（第一轮在同等范围的代码上为 1131 passed）。

## 与设计的偏差

- `run_update` 增加了可选回调 `on_download`，用于人类模式下的下载提示（下载发生在 `run_update` 内部）。
- `tests/test_workflow_cli.py` 固定了顶层命令集合，必须同步加入 `update`。
- 安装阶段的 `OSError` 映射是设计中遗漏的异常路径，返工补上。

## 后续事项

- 版本只做字符串相等比较（没有新增 `packaging` 依赖）；`--check` 在本地版本比 Release 新时也会报 `available`。可后续引入版本比较。
- 联网冒烟测试（只读的 `--check`）留给 QA 节点。
