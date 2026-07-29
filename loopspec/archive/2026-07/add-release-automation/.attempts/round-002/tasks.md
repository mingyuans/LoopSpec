> 标注说明：**[SEC]** 标记涉及外部输入、凭据、权限或第三方依赖的任务，供 `security` 节点重点审阅。
>
> 第 2 轮。第 1 轮被 `security` gate 判 FAIL，本轮新增/改写的任务：**2.5**（构建后端版本约束）、**4.1–4.3**（校验条目必须恰好一条）、**6.2/6.5/6.8**（令牌可见性边界）、**6.10**（按契约显式列出待发布文件）、**9.5–9.7**（针对上述控制的验证）。

## 1. 版本号单一入口

- [ ] 1.1 新增 `scripts/check_version.py`：用 `tomllib` 读 `pyproject.toml` 的 `project.version`，用 `ast` 解析 `src/loopspec/__init__.py` 的 `__version__`（不 import 该包）；仅用标准库，不新增依赖
- [ ] 1.2 **[SEC]** 在该脚本中加入版本号格式校验，正则 `^[0-9]+\.[0-9]+\.[0-9]+([._-]?(a|b|rc|alpha|beta|dev|post)[0-9]+)?$`；非法即非零退出，防止畸形字符串被拼进 tag/URL
- [ ] 1.3 一致且合法时把版本号打到 stdout 并以 0 退出；漂移或非法时把两处实际值打到 stderr 并非零退出
- [ ] 1.4 新增 `tests/test_check_version.py`：覆盖一致、漂移、格式非法、以及"未安装依赖也能取值"（不 import 包）四个场景

## 2. 构建后端约束

- [ ] 2.1 **[SEC]** 把 `pyproject.toml` 的 `[build-system] requires` 从裸 `"hatchling"` 改为 `"hatchling>=1.31,<2"`（下界为本次验证所用版本，上界排除下一主版本），缩小每次构建时从 PyPI 解析并执行的第三方构建后端代码范围
- [ ] 2.2 本地 `uv build` 验证加约束后仍能正常构建，且产物名符合命名契约

## 3. 安装脚本骨架与安全形态

- [ ] 3.1 新增 `install.sh`（`#!/bin/sh` + `set -eu`），全部逻辑封装进函数，文件末尾才调用入口函数——防止 `curl | sh` 传输中断时执行半个脚本
- [ ] 3.2 **[SEC]** 用 `mktemp -d` 创建临时目录（不使用固定可预测路径），`trap` 在 `EXIT`/`INT`/`TERM` 时清理
- [ ] 3.3 **[SEC]** 统一下载函数：`curl -fsSL --proto '=https' --tlsv1.2`，仅走 HTTPS、禁止协议降级、失败返回非零；确认脚本中无 `eval`、无 `sudo`、不写系统级目录
- [ ] 3.4 `chmod +x install.sh`

## 4. 安装脚本的完整性校验（本轮重点改写）

- [ ] 4.1 **[SEC]** 从 `checksums.txt` 中筛选文件名字段**恰好等于**目标 wheel 基名的记录（精确相等，不用子串匹配——否则 `0.1.0` 会命中 `0.1.0.post1`），结果写入单行文件
- [ ] 4.2 **[SEC]** 断言筛选结果行数**等于 1**：为 0（条目缺失 / 下载到错误页面 / 空文件）或大于 1（重复、歧义）时立即非零退出——"没校验到"必须等于"校验失败"
- [ ] 4.3 **[SEC]** 把该单行文件交给 `sha256sum -c` 或 `shasum -a 256 -c`（按 `command -v` 探测），依退出码判定；**不使用 `--ignore-missing`**（macOS 的 `shasum` 不支持，且"零个文件被校验"时行为不一致）
- [ ] 4.4 **[SEC]** 三步中任一失败即中止非零退出；两种校验工具都不存在时同样中止非零退出——不实现任何跳过校验的开关、环境变量或降级路径

## 5. 安装脚本的版本解析与安装

- [ ] 5.1 **[SEC]** 实现版本号格式校验函数（与 1.2 同一正则），并对 `LOOPSPEC_VERSION` 与 API 提取出的 `tag_name` 分别调用；校验通过后才允许参与 URL/文件名拼接
- [ ] 5.2 `LOOPSPEC_VERSION` 已设置时直接使用该值，不发起 GitHub API 请求
- [ ] 5.3 **[SEC]** 未设置时请求 `https://api.github.com/repos/mingyuans/LoopSpec/releases/latest`，用 `sed` 抽取 `tag_name`（不依赖 `jq`），剥掉 `v` 前缀后走 5.1 的校验（抽取失败得到空串同样会被正则拒绝）
- [ ] 5.4 查询失败（网络错误 / API 速率限制）时非零退出，并提示可用 `LOOPSPEC_VERSION=x.y.z` 跳过该查询
- [ ] 5.5 用校验后的版本号拼出 wheel 与 `checksums.txt` 的下载 URL（`.../releases/download/v$V/loopspec-$V-py3-none-any.whl`）
- [ ] 5.6 **[SEC]** 安装后端按 `uv tool install --force` → `pipx install --force` 顺序探测，参数传入**本地已校验的 wheel 路径**而非远端 URL（否则校验的字节与安装的字节不同源）
- [ ] 5.7 **[SEC]** 两种后端都缺失时打印 uv 的官方安装命令并非零退出：不自动替用户安装 uv/pipx，不回退到 `pip install --user`
- [ ] 5.8 安装后执行 `loopspec version` 自检；`command -v loopspec` 找不到时打印 PATH 补全提示（uv 场景另提 `uv tool update-shell`）但仍以 0 退出

## 6. GitHub Actions 工作流

- [ ] 6.1 新增 `.github/workflows/release.yml`：`on.push.branches: [main]` + `on.workflow_dispatch`；**[SEC]** 顶层声明 `permissions: contents: read`
- [ ] 6.2 **[SEC]** 每一处 `actions/checkout` 都显式加 `with: persist-credentials: false`——默认行为会把令牌以 `http.extraheader` 写进工作目录的 `.git/config`，同 job 内任何代码都能读
- [ ] 6.3 **[SEC]** 所有第三方 action pin 到 commit SHA 并附版本注释：`actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1`（v7.0.1）、`astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9`（v9.0.0）
- [ ] 6.4 `verify` job：checkout → setup-uv（开启 cache）→ `python scripts/check_version.py` → `uv sync` → `ruff check` + `mypy` → `pytest` → `sh -n install.sh` + `shellcheck install.sh` → `uv build`
- [ ] 6.5 **[SEC]** `verify` job 的所有步骤都不注入任何令牌（它执行的是仓库自己的测试与静态检查代码）
- [ ] 6.6 **[SEC]** `release` job：`needs: verify`，单独声明 `permissions: contents: write`（全工作流唯一持写权限者）；仅使用自动注入的 `GITHUB_TOKEN`，不声明任何额外 secret
- [ ] 6.7 `release` job 用 `gh release view "v$VERSION"` 判定：已存在则往 `$GITHUB_STEP_SUMMARY` 写明"跳过 + 版本号"并以**成功**结束；查询本身出错（非"明确不存在"）时失败，不误判为已存在/不存在
- [ ] 6.8 **[SEC]** 令牌只以 step 级 `env: GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}` 注入调用 `gh` 的那几个 step；**不放在 workflow 级或 job 级 `env`**，因此 `uv build`（会执行构建后端钩子代码）所在的 step 看不到令牌
- [ ] 6.9 未发布时重新 `uv build`，用 `sha256sum` 对自己产出的 wheel 与 sdist 生成 `checksums.txt`（记录中的文件名用不含目录前缀的基名，格式需可被 `sha256sum -c` / `shasum -a 256 -c` 直接校验）
- [ ] 6.10 **[SEC]** 按命名契约显式拼出 `dist/loopspec-$VERSION-py3-none-any.whl`、`dist/loopspec-$VERSION.tar.gz`、`checksums.txt` 三个路径，逐个断言存在（缺任一即失败），再传给 `gh release create ... --target "$GITHUB_SHA" --title "v$VERSION" --generate-notes`；**不使用 `dist/*` 通配符**
- [ ] 6.11 **[SEC]** 不引入第三方发布 action，不使用 artifact 上传/下载 action 跨 job 传产物
- [ ] 6.12 检查工作流全部步骤不把 token 写入日志、文件或命令行参数

## 7. 本地任务入口

- [ ] 7.1 `Makefile` 新增 `release-dry-run`：跑 `scripts/check_version.py` → `sh -n install.sh` →（`shellcheck` 存在则跑，缺失则打印提示并跳过、不失败）→ `uv build`
- [ ] 7.2 把 `release-dry-run` 加进 `.PHONY`

## 8. README

- [ ] 8.1 重写 "Install" 一节为面向用户：一行式 `curl -fsSL <raw install.sh URL> | sh`；"先下载、审阅、再执行"的两步替代命令；手动 `uv tool install` / `pipx install`；更新（同一条命令）；卸载（`uv tool uninstall loopspec` / `pipx uninstall loopspec`）；Windows 用户直接用 `uv tool install`
- [ ] 8.2 新增 "Releases" 一节：说明发布由版本号驱动（抬版本号才发）、Release 资产清单（wheel / sdist / `checksums.txt`）、**[SEC]** 以及仓库设置前置条件（`Settings → Actions → General → Workflow permissions` 需允许 `Read and write`，否则 `gh release create` 会 403）
- [ ] 8.3 把 `make install` 移到 "Development" 一节，并补上 `make release-dry-run`

## 9. 验证

- [ ] 9.1 本地跑 `make lint` 与 `make test`，全绿
- [ ] 9.2 本地跑 `make release-dry-run`，确认版本一致性校验与构建通过；另手动制造一次版本漂移确认它会失败，然后改回
- [ ] 9.3 用 `sh -n install.sh` 校验语法；`shellcheck` 可用时跑一遍并修掉告警（或加带理由的行内 disable）
- [ ] 9.4 交叉核对 workflow、`install.sh`、spec 三处的资产文件名完全一致（`loopspec-<version>-py3-none-any.whl` / `loopspec-<version>.tar.gz` / `checksums.txt`）
- [ ] 9.5 **[SEC]** 构造本地夹具验证 4.2 的断言真的生效：分别用「缺少 wheel 条目的 `checksums.txt`」「空文件」「含两条重复条目」「只含 `0.1.0.post1` 条目而目标为 `0.1.0`」四种输入跑校验逻辑，确认四种都非零退出而不是静默通过
- [ ] 9.6 **[SEC]** 逐行审 workflow：每个 `actions/checkout` 都有 `persist-credentials: false`；`GH_TOKEN`/`GITHUB_TOKEN` 只出现在调用 `gh` 的 step 的 `env` 下；`uv build`/`pytest`/`ruff`/`mypy`/`uv sync`/`shellcheck` 所在 step 无任何令牌
- [ ] 9.7 **[SEC]** 在 `dist/` 里放一个多余文件后走一遍 6.10 的路径，确认它不会被列入待上传清单
