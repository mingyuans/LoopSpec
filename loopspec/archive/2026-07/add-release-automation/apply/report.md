# Implementation Report

全部 54 个任务已完成并勾选。

## Tasks Implemented

**1. 版本一致性校验器（1.1–1.5）** — `scripts/check_version.py`：`tomllib` 读 `pyproject.toml` 的 `project.version`，`ast` 解析 `src/loopspec/__init__.py` 的 `__version__`（不 import 该包，因为 CI 在 `uv sync` 之前就要跑它）；两处一致且格式合法时把版本号打到 stdout；`--expect <version>` 追加断言两处均等于 tag 版本号。`tests/test_check_version.py` 11 个用例覆盖一致/漂移/格式非法/`--expect` 匹配与不匹配/预发布版本/不导入包也能取值/缺字段报错，外加一条守真实仓库的用例。

**2. 构建后端约束（2.1–2.2）** — `[build-system] requires` 由裸 `"hatchling"` 改为 `"hatchling>=1.31,<2"`；`uv build` 验证仍能构建，产物名符合契约。

**3. 安装脚本骨架与安全形态（3.1–3.4）** — `install.sh`：`#!/bin/sh` + `set -eu`，全部逻辑在函数内、`main "$@"` 是最后一行；`mktemp -d` + `trap ... EXIT INT TERM`；下载统一走 `curl -fsSL --proto '=https' --tlsv1.2`；无 `eval`、无 `sudo`、不写系统目录；已 `chmod +x`。

**4. 完整性校验（4.1–4.4）** — `extract_checksum_line` 用 `awk` 按**基名精确相等**筛选（并剥掉 `sha256sum -b` 的 `*` 标记），断言结果**恰好 1 行**（0 行与 >1 行都致命），再交给 `sha256sum -c` 或 `shasum -a 256 -c`，以临时目录为 CWD 执行。无 `--ignore-missing`，无任何跳过开关。

**5. 版本解析与安装（5.1–5.8）** — `validate_version` 为唯一闸门，对 `LOOPSPEC_VERSION` 与 API 抽出的 `tag_name` 都调用；`LOOPSPEC_VERSION` 已设置时不发请求；否则 `sed` 抽 `tag_name`（不依赖 `jq`），抽取失败得空串同样被拒；查询失败时报错并提示用 `LOOPSPEC_VERSION` 跳过；安装器按 `uv tool install --force` → `pipx install --force` 探测，参数是**本地已校验的 wheel 路径**；两者都缺则打印 uv 官方安装命令并非零退出；安装后 `loopspec version` 自检，不在 PATH 时打印提示但仍以 0 退出。

**6. GitHub Actions 工作流（6.1–6.15）** — `.github/workflows/release.yml`：`on.push.branches: [main]`（只 `verify`）与 `on.push.tags: ['v[0-9]+.[0-9]+.[0-9]+*']`（`verify` + `release`），加 `workflow_dispatch`；顶层 `permissions: contents: read`，仅 `release` 提升为 `write` 且 `if: startsWith(github.ref, 'refs/tags/v')`；两处 `checkout` 都 `persist-credentials: false`；两个 action 都 pin 到 commit SHA；`run:` 脚本体内零 `${{ }}` 插值，tag 名从 `GITHUB_REF_NAME` 环境变量取得、**先严格校验再写 `$GITHUB_ENV`**；`gh api` 动态取默认分支名后做可达性比较（仅 `identical`/`behind` 放行）；`check_version.py --expect` 置于构建之前；Release 已存在则失败并给出出路；`GH_TOKEN` 只绑定在三个调用 `gh` 的 step 上；`checksums.txt` 在 `dist/` 内生成故记录为基名；发布时显式列出三个资产路径并逐个断言存在，不用 `dist/*`、不传 `--target`。

**7. 本地任务入口（7.1–7.2）** — `make release-dry-run`（支持 `TAG=v0.2.0`）：版本校验 → `sh -n install.sh` → `shellcheck`（缺失则提示跳过）→ `uv build`；已加入 `.PHONY`。

**8. README（8.1–8.4）** — "Install" 改为面向用户（一行式命令、先下载再审阅的两步替代、手动 `uv tool install`/`pipx`、`LOOPSPEC_VERSION` 固定版本、Windows 说明、更新与卸载、PATH 提示）；新增 "Releases"（三步发布流程、tag 是版本号来源、三方一致性会拦、资产清单、仓库权限前置条件、"能推 `v*` tag 即能发布"及 ruleset 建议并注明属仓库配置）；`make install` 移入 "Development" 并补 `make release-dry-run`。

**9. 验证（9.1–9.10）** — 见下方 Tests and Checks。9.5–9.10 原计划为人工核对动作，实际改为**固化成 pytest 用例**（见 Deviations）。

## Files Changed

新增：

- `.github/workflows/release.yml`
- `install.sh`（可执行）
- `scripts/check_version.py`
- `tests/test_check_version.py`
- `tests/test_install_script.py`
- `tests/test_release_workflow.py`

修改：

- `pyproject.toml`（`[build-system] requires` 加版本上下界）
- `Makefile`（新增 `release-dry-run`；`.PHONY`；`lint` 的 ruff 目标加上 `scripts`）
- `README.md`（Install / Releases / Development 三节）

## Tests and Checks

`make lint`：

```
uv run ruff check src tests scripts
All checks passed!
uv run mypy src
Success: no issues found in 22 source files
```

`make test`：

```
567 passed in 7.10s
```

其中新增 62 个用例（`test_check_version.py` 11、`test_install_script.py` 24、`test_release_workflow.py` 27）。既有 505 个用例未改动、未失败。

单独跑 `make test` 时会出现 1 个 skip：`test_built_artifacts_match_the_contract` 在 `dist/` 不存在时跳过（它核对真实构建产物名，不主动触发构建）。先跑 `make build` 或 `make release-dry-run` 后即执行。

`make release-dry-run`：

```
0.1.0
sh -n install.sh
shellcheck: not installed, skipped (it is mandatory in CI)
uv build
Successfully built dist/loopspec-0.1.0.tar.gz
Successfully built dist/loopspec-0.1.0-py3-none-any.whl
```

`make release-dry-run TAG=v0.1.0` 通过；`TAG=v9.9.9` 按预期失败：

```
error: expected '9.9.9' (from the release tag) but pyproject.toml has '0.1.0', src/loopspec/__init__.py has '0.1.0'
make: *** [release-dry-run] Error 1
```

`shellcheck install.sh`：clean，无任何 finding（本机无 `shellcheck` 二进制，经 PyPI 的 `shellcheck-py` 包装器执行；该包由 pre-commit 生态维护，内含官方 shellcheck 二进制）。

workflow 的每个 `run:` 脚本体单独过 `bash -n`：13 个 step 全部 OK。

`grep -n '\${{' .github/workflows/release.yml` 共 4 处：1 处在文件头注释，3 处是三个 `gh` step 的 `env: GH_TOKEN`。**`run:` 脚本体内 0 处**。

## Deviations from the Design

1. **`scripts/check_version.py` 增加了 `--repo-root` 参数**（design/tasks 未提）。原实现从 `__file__` 推导仓库根，导致无法对夹具仓库做测试。加了这个参数后 `tests/test_check_version.py` 能针对临时目录构造的仓库跑真实子进程。默认值仍是脚本所在仓库，CI 与 `make release-dry-run` 的调用方式不变。

2. **workflow 的 lint/test/build 走 `make lint` / `make test` / `make build`**，而 tasks 6.4 列的是 `uv run ruff check` / `uv run mypy` / `uv run pytest -v` / `uv build` 这些原始命令。行为等价，但避免了"改了 Makefile 而 CI 没跟上"的漂移。仅 `uv sync --frozen` 保留显式写法（`make install` 是 `uv sync`，CI 需要 `--frozen`），`sh -n` + `shellcheck` 也保留显式写法（`make release-dry-run` 在本地容忍缺失 `shellcheck`，而 CI 要求它必须存在）。

3. **`make lint` 的 ruff 目标从 `src tests` 扩为 `src tests scripts`**（tasks 未提）。新增的 `scripts/` 否则完全不受 lint 覆盖。mypy 仍只查 `loopspec` 包（其 `packages` 配置在 `pyproject.toml`，改动它超出本变更范围）。

4. **"Release 已存在"的判定改用单次 `gh api repos/.../releases/tags/$TAG`**，而 design D2/D16 提到的是 `gh release view`。原因：需要区分"明确 404"与"查询本身失败"，用 `gh release view` 要么再发一次请求、要么无法区分。现在一次调用即可——成功即已存在（失败退出），失败时只有输出含 `Not Found` 才继续，其余一律失败。语义与 D16 要求一致（不静默跳过、不把查询错误当作"不存在"）。

5. **tasks 9.5–9.10 由人工核对动作改为 pytest 用例**：
   - 9.5（checksum 四种坏输入）→ `test_install_script.py` 中缺失条目/空文件/HTML 错误页/重复条目/相似版本号五个用例，做法是剥掉 `install.sh` 末行 `main "$@"` 后 source 其函数。
   - 9.6（workflow 逐行审令牌与凭据）→ `test_checkout_never_persists_credentials`、`test_token_is_scoped_to_the_steps_that_call_gh`、`test_build_step_has_no_token`。
   - 9.7（`dist/` 多余文件不被发布）→ `test_publish_accepts_exactly_the_contracted_assets`（在 `dist/` 放了 `unexpected-extra-file.txt` 并断言它不进清单）。
   - 9.8（非法 tag 名）→ `test_invalid_tags_are_rejected_without_executing_anything`，输入含 `v1.0.0$(touch pwned)` 与 `v1.0.0; touch pwned`，并断言 `pwned` 文件未被创建、`$GITHUB_ENV` 未被写入。
   - 9.9（两条触发路径）→ `test_both_trigger_paths_are_declared`、`test_release_job_runs_only_on_tags`。
   - 9.10（插值边界）→ `test_no_expression_interpolation_inside_run_bodies`，另在实现过程中也跑过 `grep` 人工核对。

   改动方向是加强而非削弱：这些约束由此变成回归护栏，下一次有人改 workflow 或 `install.sh` 时会失败在 CI 里，而不是靠人记得再审一遍。这也部分回应了第 4 轮 `security` 的第一条非阻塞提醒（"D18 目前只靠人工 grep"）——`test_no_expression_interpolation_inside_run_bodies` 现在就是那条自动护栏，虽然不如 `zizmor`/`actionlint` 覆盖面广。

6. **`security/pass.md` 的两条非阻塞提醒已在实现中吸收**：`$TAG` 的来源（第 2 条）现在明确——由"Resolve and validate version from tag"这个 step 校验后写入 `$GITHUB_ENV`，而非在发布 step 里凭空引用；`checksums.txt` 的基名问题（第 3 条）通过在 `dist/` 内 `cd` 后再 `sha256sum` 解决，并有 `test_checksums_use_bare_filenames` 守住。

## Follow-Ups

- **`zizmor` 或 `actionlint` 进 CI**：`test_no_expression_interpolation_inside_run_bodies` 只覆盖插值这一条规则，专用工具还能查 pin、权限、缓存投毒等。引入新工具本身是供应链决策，值得单独评估（`security/pass.md` 的第 1 条提醒）。
- **预发布版本号的规范化差异**：正则允许 `0.1.0-rc1`，但 wheel 文件名会被 PEP 440 规范化为 `0.1.0rc1`，此时发布步骤的存在性断言会失败。失败方向是关闭的（报错而非发错名资产），首次发预发布版时需注意。
- **`hatchling>=1.31,<2` 的下界与两个 action 的 pin SHA 需人工跟进**，与 Dependabot 那个待议变更是同一类维护负担。
- **运行时依赖树不做哈希固定**：`uv tool install <wheel>` 仍会从 PyPI 解析 `pydantic`/`typer`/`rich`/`pyyaml`/`questionary`。本变更只保证 wheel 本身是发布的那一个。
- **D15 的维护分支场景**：若将来需要"从 `release/*` 分支发补丁版"，可达性校验需从"可从默认分支到达"扩展为"可从默认分支或任一 `release/*` 分支到达"。
- **首次发布的时序**：`install.sh` 合并进 `main` 后其 raw URL 才可下载；推出第一个 tag 之前 `releases/latest` 不存在，一行式安装命令会失败。这是预期窗口，README 未为此加特殊说明。
