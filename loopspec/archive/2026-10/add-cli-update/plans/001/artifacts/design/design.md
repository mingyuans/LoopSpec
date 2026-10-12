## 背景与现状

- CLI 入口在 `src/loopspec/cli.py`（Typer）。顶层只有 `version`、`init` 与 `hook` 组，其余资源命令由 `workflow_cli.register(app)` 注册。
- 已装版本来自 `loopspec.__version__`（读取 distribution metadata，源码树中为 `0.0.0.dev0`）。
- 升级现在只能通过 `install.sh` 完成：先下载 checksums.txt 并解析版本，再下载 wheel，按文件名精确匹配校验 SHA256，最后用 `uv tool install --force` 或 `pipx install --force` 安装本地文件。
- 错误统一走 `LoopspecError` 的 `{error, message, fix}`。`tests/test_docs_consistency.py` 通过 `LoopspecError` 的子类 `code` 和 `WorkflowError("<code>")` 字面量发现错误码，要求中英文 cli-reference 都有记录；命令和选项也必须各有一节文档。
- 项目没有 HTTP 客户端依赖，只能用标准库 `urllib.request`。

## 目标 / 非目标

**目标：**
- 新增 `loopspec update [--version X.Y.Z] [--check] [--json]`，把 `install.sh` 的升级流程用 Python 实现在 CLI 内。
- 网络与子进程可注入，测试不联网、不真实安装。

**非目标：**
- 项目刷新（Skill、hook、内置资源）、别名命令、修改 install.sh、自定义 Release 源或代理、跳过校验的开关。

## 方案

### 新模块 `src/loopspec/self_update.py`

常量：
```python
REPO_URL = "https://github.com/mingyuans/LoopSpec"
RELEASES = f"{REPO_URL}/releases"
LATEST_CHECKSUMS_URL = f"{RELEASES}/latest/download/checksums.txt"
VERSION_PATTERN = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:[._-]?(?:a|b|rc|alpha|beta|dev|post)[0-9]+)?")  # 用 fullmatch，等价 install.sh
MAX_CHECKSUMS_BYTES = 64 * 1024
MAX_WHEEL_BYTES = 50 * 1024 * 1024
TIMEOUT_SECONDS = 30
```

类型（可注入）：
```python
Fetcher = Callable[[str, int], bytes]           # (url, max_bytes) -> body
Runner = Callable[[list[str]], int]             # argv -> returncode
Which = Callable[[str], str | None]             # shutil.which
```

函数：
- `validate_version(value) -> str`：不能 `fullmatch` 时抛 `UpdateInvalidVersionError`。
- `version_from_checksums(text) -> str`：逐行读取，第二列去掉 `*` 前缀后匹配 `loopspec-(.+)-py3-none-any.whl`，取第一个匹配并校验；没有匹配时抛 `UpdateFetchFailedError`（checksums 中没有 wheel 条目）。
- `expected_digest(text, wheel_name) -> str`：按文件名精确匹配（去掉 `*`），必须**恰好一行**，且 digest 必须是 64 位 hex；0 行或多行时抛 `UpdateVerifyFailedError`。
- `https_fetch(url, max_bytes) -> bytes`：默认 fetcher。用 `urllib.request.build_opener` 加自定义 `HTTPRedirectHandler`（`redirect_request` 检查新 URL 的 scheme 必须是 `https`，否则抛错），起始 URL 也必须是 https；`timeout=TIMEOUT_SECONDS`；按块读取，累计超过 `max_bytes` 时立即中止。`URLError`、`HTTPError`、`TimeoutError`、`OSError` 都转成 `UpdateFetchFailedError`，message 只包含 URL，不包含响应内容。
- `pick_installer(wheel, which) -> tuple[str, list[str]]`：有 `uv` 时返回 `("uv", ["uv","tool","install","--force",wheel])`；否则有 `pipx` 时返回 `("pipx", ["pipx","install","--force",wheel])`；两者都没有时抛 `UpdateInstallerMissingError`。argv 第 0 项用命令名，不用 which 返回的路径，与 install.sh 一致，也便于测试断言。
- `default_runner(argv) -> int`：`subprocess.run(argv, check=False).returncode`，不设 `shell=True`，安装器输出直接透传到终端。
- `run_update(current, *, version=None, check=False, fetch=https_fetch, run=default_runner, which=shutil.which) -> UpdateResult`：
  1. 指定 `version` 时先 `validate_version`，checksums URL 为 `{RELEASES}/download/v{version}/checksums.txt`；否则用 `LATEST_CHECKSUMS_URL`。
  2. `fetch(checksums_url, MAX_CHECKSUMS_BYTES)`，按 UTF-8 解码（失败时抛 `UpdateFetchFailedError`）；没有指定版本时用 `version_from_checksums` 得到 latest；指定版本时 latest = 指定值。
  3. `pinned = version is not None`。
     - `not pinned and latest == current`：返回 `up_to_date`。
     - `check`：返回 `up_to_date`（latest == current）或 `available`。
  4. `wheel_name = f"loopspec-{latest}-py3-none-any.whl"`，先用 `expected_digest` 确认条目存在（缺失时在下载 wheel 之前失败），然后 `fetch(f"{RELEASES}/download/v{latest}/{wheel_name}", MAX_WHEEL_BYTES)`。
  5. 用 `hashlib.sha256` 比较（`hmac.compare_digest`），不一致时抛 `UpdateVerifyFailedError`。
  6. 在 `tempfile.TemporaryDirectory()` 中写入 wheel，`pick_installer`，执行 `run(argv)`；返回码非 0 时抛 `UpdateInstallFailedError`。
  7. 返回 `updated`。

`UpdateResult`（dataclass）：`status: Literal["up_to_date","available","updated"]`、`current`、`latest`、`installer: str | None`，以及 `to_dict()`。

版本比较只做字符串相等：不新增 `packaging` 依赖。与 install.sh 一样，未固定版本时“不同即安装 latest”。本地开发版（如 `0.0.0.dev0`）执行 update 会装成最新 Release，这符合预期。

### 错误码（`src/loopspec/errors.py`）

| 类 | code | 场景 |
| --- | --- | --- |
| `UpdateInvalidVersionError` | `update_invalid_version` | `--version` 或 checksums 中的版本不合法 |
| `UpdateFetchFailedError` | `update_fetch_failed` | 网络、超时、超限、非 https、解码失败、checksums 中没有 wheel 条目 |
| `UpdateVerifyFailedError` | `update_verify_failed` | checksums 中没有对应行或有多行、digest 格式不对、SHA256 不一致 |
| `UpdateInstallerMissingError` | `update_installer_missing` | 既没有 uv 也没有 pipx |
| `UpdateInstallFailedError` | `update_install_failed` | 安装器返回非 0 |

每个错误都带 `fix`，例如网络失败时建议检查网络或改用 install.sh。

### CLI（`src/loopspec/cli.py`）

```python
@app.command()
def update(
    version: str | None = typer.Option(None, "--version", help="Install this exact version instead of the latest release."),
    check: bool = typer.Option(False, "--check", help="Only report whether a newer release exists; install nothing."),
    as_json: bool = JsonOption,
) -> None:
```
- 调用 `run_update(__version__, version=..., check=...)`，捕获 `LoopspecError` 后用 `_fail`。
- JSON 模式输出 `result.to_dict()`；非 JSON 模式输出一行文本：
  - `up_to_date`：`loopspec X is up to date.`
  - `available`：`loopspec Y is available (installed: X). Run \`loopspec update\` to install it.`
  - `updated`：`Updated loopspec X -> Y with uv.`
- 非 JSON 且需要下载时，先输出 `Downloading loopspec Y...`；JSON 模式下 stdout 只输出 JSON。安装器输出会透传到终端，所以 JSON 模式下安装器的子进程 stdout 要重定向到 stderr，避免污染 JSON（`default_runner` 在 JSON 模式下传 `stdout=sys.stderr`）。

### 文档

- `docs/zh/cli-reference.md` 与 `docs/en/cli-reference.md`：在约定段把 `update` 加入“单独使用”的命令列表，新增 `## loopspec update` 一节（参数、行为、JSON 结构），并在错误码表中新增 5 行。
- README 的 “Update and uninstall” 小节增加 `loopspec update` 用法，保留 install.sh 方式（首次安装或 CLI 损坏时使用）。

## 归属与路径

全部属于 BE（Python CLI），没有 FE 改动。
- `src/loopspec/self_update.py`（新增）、`src/loopspec/errors.py`、`src/loopspec/cli.py`：对应保障规则 `backend`（`src/**`），需要 backend-tests、security-review、pr-review。
- `tests/test_self_update.py`（新增）：对应 `backend`（`tests/**`）。
- `docs/zh/cli-reference.md`、`docs/en/cli-reference.md`、`README.md`：对应 `project-support`，在 `excluded_paths` 中，不进入代码 Diff。

## 安全边界

- **输入校验**：版本号（参数与远端）必须通过白名单正则 `fullmatch`，才能用于 URL、文件名或 argv。checksums 中的 digest 必须是 64 位 hex。
- **传输**：只允许 https，重定向不能降级；有超时；读取有上限，避免内存耗尽。
- **完整性**：精确匹配恰好一行，用 `hmac.compare_digest` 比较；安装的是已校验的本地临时文件。没有跳过开关。
- **执行**：`subprocess.run(list)`，不使用 shell；wheel 路径来自 `TemporaryDirectory` 与已校验的版本号。
- **依赖**：只用标准库，不新增依赖。
- **敏感数据**：不读取环境变量，不发送任何本地信息（只发 GET 请求，使用默认 UA）；错误信息不回显远端内容。
- **信任边界说明**：checksums 与 wheel 来自同一个 Release，能防传输损坏和中途篡改，不能防 Release 本身被攻破。这与 install.sh 相同，文档中如实说明。

## 验证方案

`tests/test_self_update.py`（pytest，注入假的 fetch、run、which，不联网）：
1. `version_from_checksums`：普通行、`*` 前缀、多行时取 wheel 行；没有 wheel 行时报 `update_fetch_failed`。
2. 非法版本：`--version` 为 `1.0;rm -rf /`、`../1.0.0`、空串时报 `update_invalid_version`，且 fetch 未被调用；远端 checksums 给出非法版本时同样报错，且不再请求 wheel。
3. latest == current：结果为 `up_to_date`，fetch 只调用 1 次，run 未调用。
4. `--check` 且有新版本：结果为 `available`，fetch 1 次，run 未调用；`--check` 且已最新时为 `up_to_date`。
5. 正常升级（uv）：run 收到的 argv 为 `["uv","tool","install","--force",<path>]`，path 以 wheel 名结尾，调用时文件存在且内容一致；结果为 `updated`、`installer == "uv"`。
6. 只有 pipx 时 argv 为 pipx；都没有时报 `update_installer_missing`。
7. digest 不一致、没有对应行、有两行、digest 非 hex 时报 `update_verify_failed`，run 未调用；没有对应行时 wheel 也不下载。
8. 固定版本：请求的是 `/download/v<ver>/checksums.txt`；与 current 相同时也安装。
9. 安装器返回码为 1 时报 `update_install_failed`。
10. `https_fetch`：非 https 起始 URL、超过大小上限（用本地伪 opener 或 monkeypatch `urlopen` 返回的流）、重定向处理器拒绝 http 目标、`URLError` 时都报 `update_fetch_failed`。
11. CLI（CliRunner，monkeypatch `self_update.run_update` 或注入点）：`--json` 成功输出结构正确；失败时输出 `{error,message,fix}` 且退出码为 1；人类模式输出文本；`--help` 包含三个选项。
12. 回归：`make test`（含 docs consistency）与 `make lint` 全部通过。

## 风险与取舍

- **不引入 `packaging` 做版本大小比较**：避免新依赖。代价是本地版本比 latest 新时，执行 update 会降级。不过这种情况只出现在开发构建，接受。
- **不复用 install.sh**（例如在 CLI 内执行 `curl | sh`）：那样会把执行远端脚本引入 CLI，而且依赖 POSIX shell、curl，Windows 不可用，所以放弃。
- **JSON 模式下安装器输出改走 stderr**：保证 stdout 是纯 JSON。
- **升级正在运行的进程**：uv/pipx 会替换 tool venv，当前进程已经加载的模块不受影响；安装后不再导入新模块，直接退出。
