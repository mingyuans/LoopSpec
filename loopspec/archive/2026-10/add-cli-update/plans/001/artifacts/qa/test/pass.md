---
verdict: PASS
summary: "对真实 GitHub Release 完成验收：--check、--json、非法版本、不存在的 tag 结果都符合预期；在隔离的 uv tool 目录中真实下载、校验并安装了 1.1.1；全量测试 1141 passed，lint 通过"
---

# 验收测试：通过

## 验收条件核对

- [x] `loopspec update --help` 列出 `--version`、`--check`、`--json`：真实执行 `uv run loopspec update --help`，三个选项都在。
- [x] 已是最新时结果为 `up_to_date`，不下载、不安装：单测 `test_up_to_date_downloads_nothing_and_installs_nothing` 通过。真实环境无法复现，因为工作树版本是 `0.0.0.dev0`，而已发布的 1.1.1 还没有 `update` 命令。
- [x] `--check` 有新版本时返回 `available`，不安装：真实执行 `uv run loopspec update --check --json` 输出 `{"status": "available", "current": "0.0.0.dev0", "latest": "1.1.1", "installer": null}`，exit 0；人类模式输出 “loopspec 1.1.1 is available (installed: 0.0.0.dev0). Run `loopspec update` to install it.”
- [x] 正常升级用 uv 安装并报告 `updated`：设置 `UV_TOOL_DIR`、`UV_TOOL_BIN_DIR` 指向 scratchpad 的隔离目录后，真实执行 `uv run loopspec update --json --version 1.1.1`：
  - 输出 `{"status": "updated", "current": "0.0.0.dev0", "latest": "1.1.1", "installer": "uv"}`，exit 0；
  - uv 的输出走 stderr，stdout 只有 JSON；
  - 隔离目录中的 `loopspec version` 为 `1.1.1`。
  
  不带 `--version` 在人类模式下执行，依次经过 latest 解析、重定向、下载、校验、安装，最后输出 “Updated loopspec 0.0.0.dev0 -> 1.1.1 with uv.”。uv 日志显示安装源为临时目录中的本地 wheel。安装后 `loopspec-update-*` 临时目录已清理。全局 `~/.local/bin/loopspec` 仍是 1.1.0，没有受影响。
- [x] pipx 回退、无安装器报 `update_installer_missing`：单测通过（本机未用 pipx 做真实验证）。
- [x] SHA256 不一致、缺少条目或有多行时报 `update_verify_failed`，且不安装：单测通过。真实安装时校验路径已实际执行并通过。
- [x] 非法版本报 `update_invalid_version`，且不发请求：真实执行 `uv run loopspec update --json --version '1.0;id'`，返回 `update_invalid_version`，exit 1。
- [x] 网络错误或不存在的 Release 报 `update_fetch_failed`：真实执行 `uv run loopspec update --check --json --version 99.0.0`，返回 `update_fetch_failed`，message 中有 “(HTTP 404)”，exit 1。超时、大小上限、http 重定向由单测覆盖。
- [x] 安装器非零退出或无法启动时报 `update_install_failed` / `update_installer_missing`：单测通过。
- [x] `--json` 失败时输出 `{error,message,fix}`，exit 1：见上面两条真实执行结果。
- [x] `make test` 全部通过、`make lint` 无错误：be/tests/check 第 2 轮为 `1141 passed`；`make lint` 中 ruff 与 mypy 都通过。

## 执行的测试

- `uv run loopspec update --help`
- `uv run loopspec update --check --json` → available，exit 0
- `uv run loopspec update --check` → 人类可读的 available 提示
- `uv run loopspec update --json --version '1.0;id'` → update_invalid_version，exit 1
- `uv run loopspec update --check --json --version 99.0.0` → update_fetch_failed（HTTP 404），exit 1
- `UV_TOOL_DIR=<scratch>/tools UV_TOOL_BIN_DIR=<scratch>/bin uv run loopspec update --json --version 1.1.1` → updated，exit 0；`<scratch>/bin/loopspec version` → 1.1.1
- 同样的隔离环境下 `uv run loopspec update` → “Updated loopspec 0.0.0.dev0 -> 1.1.1 with uv.”
- 临时目录残留检查 → `[]`
- `make test`（be/tests/check 第 2 轮）→ 1141 passed

## 剩余风险

- 已发布版本（≤1.1.1）还没有 `update` 命令，所以“已安装版本自身执行 update 且结果为 up_to_date”这条路径只有单测覆盖；需要等本功能发布后的下一个版本才能真实验证。
- pipx 路径和 Windows 没有做真实验证。
- 版本只做字符串比较：开发构建（0.0.0.dev0）会被视为“有新版本”，执行 update 后会装成最新 Release，这符合预期。
