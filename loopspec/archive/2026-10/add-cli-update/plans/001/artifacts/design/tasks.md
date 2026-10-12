## 1. 测试先行

- [x] 1.1 新增 `tests/test_self_update.py`，覆盖设计「验证方案」第 1–11 项；验证：先运行，确认因模块不存在而失败（红）。

## 2. 核心实现

- [x] 2.1 `src/loopspec/errors.py` 新增 5 个 `Update*Error` 子类（`update_invalid_version`、`update_fetch_failed`、`update_verify_failed`、`update_installer_missing`、`update_install_failed`），每个都带默认 `fix`；验证：`pytest tests/test_self_update.py` 中的错误码断言通过。
- [x] 2.2 新增 `src/loopspec/self_update.py`：`validate_version`、`version_from_checksums`、`expected_digest`、`https_fetch`（仅 https、重定向不降级、超时、大小上限）、`pick_installer`、`default_runner`（不使用 shell）、`run_update`、`UpdateResult`；验证：`pytest tests/test_self_update.py` 中的单元用例全部通过。
- [x] 2.3 `src/loopspec/cli.py` 新增 `update` 命令（`--version`、`--check`、`--json`），JSON 模式下安装器的 stdout 改走 stderr；验证：CLI 用例通过，`uv run loopspec update --help` 列出三个选项。

## 3. 文档

- [x] 3.1 中英文 `cli-reference.md`：在约定段补上 `update`，新增 `## loopspec update` 一节，错误码表新增 5 行；验证：`make docs-check` 通过。
- [x] 3.2 README 的 “Update and uninstall” 小节加入 `loopspec update` 用法；验证：人工检查内容与行为一致。

## 4. 回归

- [x] 4.1 运行 `make test`，全部通过；记录真实输出摘要。
- [x] 4.2 运行 `make lint`（ruff + mypy），无错误；记录真实输出摘要。
