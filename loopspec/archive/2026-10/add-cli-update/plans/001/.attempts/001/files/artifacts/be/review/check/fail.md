---
verdict: FAIL
summary: "安装阶段的 OSError（安装器缺失或不可执行、临时目录不可写）未映射为 LoopspecError，会以 traceback 退出，违反 {error,message,fix} 契约"
---

# 后端代码审查：失败

## 阻塞问题

- `src/loopspec/self_update.py` 的 `run_update` 安装段（`TemporaryDirectory()`、`wheel_path.write_bytes`、`run(argv)`）没有处理 `OSError`。`shutil.which` 找到 uv 之后，如果 uv 被移走或没有执行权限，`subprocess.run` 会抛 `FileNotFoundError` 或 `PermissionError`；磁盘满或 TMPDIR 不可写时也会抛 `OSError`。`cli.update` 只捕获 `LoopspecError`，所以用户看到的是 Python traceback，`--json` 模式也拿不到 `{error,message,fix}`。这违反了 proposal 中的验收条件「`--json` 失败时输出 `{error, message, fix}`，退出码为 1」。需要把这些异常映射为 `update_installer_missing`（`FileNotFoundError`）或 `update_install_failed`（其他 `OSError`），并补充测试。

## 审查输入

- 轮次 `001.1:be/review/check:1`，基线 `b1d59372a81aae5dabef4a4a39f7403a440c0e17`，scopeDigest `c5c49cb7ee09…`；由独立审查 agent 读代码完成，结论经人工核实。

## 建议修复方向

- 同一轮一并处理以下非阻塞项：
  - `--check --version X` 返回 `available` 时，提示应为 `loopspec update --version X`，而不是 `loopspec update`；
  - 补充测试：`--check` 与 `--version` 组合；CLI 层确认 JSON 模式下 `run` 绑定了 `stdout=sys.stderr`，人类模式传入 `on_download`；CLI 非法 `--version` 走 JSON 失败路径；`default_runner` 的 `stdout` 透传。
