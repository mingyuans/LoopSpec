---
verdict: PASS
summary: "make test 全量 1131 passed（含新增 test_self_update.py 50 个用例与中英文文档一致性检查），make lint 通过"
---

# 后端测试：通过

## 审查输入

- 轮次 `001.1:be/tests/check:1`，基线 `b1d59372a81aae5dabef4a4a39f7403a440c0e17`，scopeDigest `c5c49cb7…421e`。
- 固定路径：`src/loopspec/cli.py`、`src/loopspec/errors.py`、`src/loopspec/self_update.py`（新增）、`tests/test_self_update.py`（新增）、`tests/test_workflow_cli.py`。没有 warnings。

## 执行的测试

- `make test`（`uv run pytest -v`，在本轮 begin 之后执行）：`1131 passed in 723.37s`，0 failed。
- `uv run pytest tests/test_self_update.py -q`：50 passed。覆盖：
  - 版本白名单（合法与非法，含 `;`、`..`、空串、换行、`$(id)`）；
  - checksums 解析（`*` 前缀、无 wheel 行、恰好一行、前缀相同的近似文件名、非 hex digest）；
  - 已最新时不下载、不安装；`--check` 只读；uv 安装参数及安装后清理临时文件；pipx 回退；无安装器；
  - 篡改的 wheel 不安装；缺 checksum 条目时不下载 wheel；固定版本走 tag URL 并重装；非法固定版本不发请求；
  - 恶意 latest 版本不再请求 wheel；checksums 解码失败；安装器非零退出；
  - `https_fetch` 的超时参数、大小上限、拒绝非 https、四类网络异常映射、重定向不能离开 https；
  - CLI 的 help、JSON 成功与失败、人类模式输出、失败退出码为 1。
- `uv run pytest tests/test_docs_consistency.py tests/test_cli.py tests/test_self_update.py -q`：121 passed（新命令、选项和 5 个错误码在中英文文档中都有记录）。
- `make lint`：ruff “All checks passed!”；mypy “Success: no issues found in 35 source files”。

## 剩余风险

- 测试全部注入假的 fetch、runner、opener，没有覆盖真实 GitHub 下载和真实 uv/pipx 安装；建议在 QA 节点用只读的 `loopspec update --check --json` 对真实 Release 做一次联网冒烟。
- 测试没有覆盖 Windows 下的 uv/pipx 调用。
