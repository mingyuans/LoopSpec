> 标注说明：**[SEC]** 标记涉及外部输入、凭据、权限或第三方依赖的任务，供 `security` 节点重点审阅。
>
> 第 4 轮。相对第 3 轮的改动：新增 **6.7**（表达式插值边界，D18）与验证 **9.10**；**6.9** 的默认分支名改为动态取得；**6.8** 明确 tag 名经 `$GITHUB_ENV` 传递而非插值。其余任务原样保留——第 2–5 组与 D8/D13/D14 相关的所有约束是第 1 轮 `security` FAIL 的修复成果，不得稀释。

## 1. 版本一致性校验器

- [x] 1.1 新增 `scripts/check_version.py`：用 `tomllib` 读 `pyproject.toml` 的 `project.version`，用 `ast` 解析 `src/loopspec/__init__.py` 的 `__version__`（不 import 该包）；仅用标准库，不新增依赖
- [x] 1.2 **[SEC]** 加入版本号格式校验，正则 `^[0-9]+\.[0-9]+\.[0-9]+([._-]?(a|b|rc|alpha|beta|dev|post)[0-9]+)?$`；非法即非零退出，防止畸形字符串被拼进 Release 名或文件路径
- [x] 1.3 无参调用：两处一致且格式合法时把版本号打到 stdout 并以 0 退出；漂移或非法时把两处实际值打到 stderr 并非零退出
- [x] 1.4 **[SEC]** 支持 `--expect <version>`（发布路径用，值为 tag 名去掉 `v` 前缀）：追加断言两处均等于该值，不等时把 tag 值与两处文件值一并打到 stderr 并非零退出
- [x] 1.5 新增 `tests/test_check_version.py`：覆盖两处一致、两处漂移、格式非法、`--expect` 匹配、`--expect` 不匹配、以及"未安装依赖也能取值"（不 import 包）六个场景

## 2. 构建后端约束

- [x] 2.1 **[SEC]** 把 `pyproject.toml` 的 `[build-system] requires` 从裸 `"hatchling"` 改为 `"hatchling>=1.31,<2"`（下界为本次验证所用版本，上界排除下一主版本），缩小每次构建时从 PyPI 解析并执行的第三方构建后端代码范围
- [x] 2.2 本地 `uv build` 验证加约束后仍能正常构建，且产物名符合命名契约

## 3. 安装脚本骨架与安全形态

- [x] 3.1 新增 `install.sh`（`#!/bin/sh` + `set -eu`），全部逻辑封装进函数，文件末尾才调用入口函数——防止 `curl | sh` 传输中断时执行半个脚本
- [x] 3.2 **[SEC]** 用 `mktemp -d` 创建临时目录（不使用固定可预测路径），`trap` 在 `EXIT`/`INT`/`TERM` 时清理
- [x] 3.3 **[SEC]** 统一下载函数：`curl -fsSL --proto '=https' --tlsv1.2`，仅走 HTTPS、禁止协议降级、失败返回非零；确认脚本中无 `eval`、无 `sudo`、不写系统级目录
- [x] 3.4 `chmod +x install.sh`

## 4. 安装脚本的完整性校验

- [x] 4.1 **[SEC]** 从 `checksums.txt` 中筛选文件名字段**恰好等于**目标 wheel 基名的记录（精确相等，不用子串匹配——否则 `0.1.0` 会命中 `0.1.0.post1`），结果写入单行文件
- [x] 4.2 **[SEC]** 断言筛选结果行数**等于 1**：为 0（条目缺失 / 下载到错误页面 / 空文件）或大于 1（重复、歧义）时立即非零退出——"没校验到"必须等于"校验失败"
- [x] 4.3 **[SEC]** 把该单行文件交给 `sha256sum -c` 或 `shasum -a 256 -c`（按 `command -v` 探测），并以临时目录为工作目录执行（`checksums.txt` 中记录的是基名）；**不使用 `--ignore-missing`**（macOS 的 `shasum` 不支持，且"零个文件被校验"时行为不一致）
- [x] 4.4 **[SEC]** 三步中任一失败即中止非零退出；两种校验工具都不存在时同样中止非零退出——不实现任何跳过校验的开关、环境变量或降级路径

## 5. 安装脚本的版本解析与安装

- [x] 5.1 **[SEC]** 实现版本号格式校验函数（与 1.2 同一正则），并对 `LOOPSPEC_VERSION` 与 API 提取出的 `tag_name` 分别调用；校验通过后才允许参与 URL/文件名拼接
- [x] 5.2 `LOOPSPEC_VERSION` 已设置时直接使用该值，不发起 GitHub API 请求
- [x] 5.3 **[SEC]** 未设置时请求 `https://api.github.com/repos/mingyuans/LoopSpec/releases/latest`，用 `sed` 抽取 `tag_name`（不依赖 `jq`），剥掉 `v` 前缀后走 5.1 的校验（抽取失败得到空串同样会被正则拒绝）
- [x] 5.4 查询失败（网络错误 / 速率限制 / 仓库尚无任何 Release）时非零退出，并提示可用 `LOOPSPEC_VERSION=x.y.z` 跳过该查询
- [x] 5.5 用校验后的版本号拼出 wheel 与 `checksums.txt` 的下载 URL（`.../releases/download/v$V/loopspec-$V-py3-none-any.whl`）
- [x] 5.6 **[SEC]** 安装后端按 `uv tool install --force` → `pipx install --force` 顺序探测，参数传入**本地已校验的 wheel 路径**而非远端 URL（否则校验的字节与安装的字节不同源）
- [x] 5.7 **[SEC]** 两种后端都缺失时打印 uv 的官方安装命令并非零退出：不自动替用户安装 uv/pipx，不回退到 `pip install --user`
- [x] 5.8 安装后执行 `loopspec version` 自检；`command -v loopspec` 找不到时打印 PATH 补全提示（uv 场景另提 `uv tool update-shell`）但仍以 0 退出

## 6. GitHub Actions 工作流（tag 驱动）

- [x] 6.1 新增 `.github/workflows/release.yml`，触发条件写成两条路径：`on.push.branches: [main]`（只校验）与 `on.push.tags: ['v[0-9]+.[0-9]+.[0-9]+*']`（校验 + 发布），外加 `workflow_dispatch`；**[SEC]** 顶层声明 `permissions: contents: read`
- [x] 6.2 **[SEC]** 每一处 `actions/checkout` 都显式加 `with: persist-credentials: false`——默认行为会把令牌以 `http.extraheader` 写进工作目录的 `.git/config`，同 job 内任何代码都能读
- [x] 6.3 **[SEC]** 所有第三方 action pin 到 commit SHA 并附版本注释：`actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1`（v7.0.1）、`astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9`（v9.0.0）
- [x] 6.4 `verify` job（所有触发下都跑）：checkout → setup-uv（开启 cache）→ `python scripts/check_version.py` → `uv sync` → `ruff check` + `mypy` → `pytest` → `sh -n install.sh` + `shellcheck install.sh`（二者均为硬要求）→ `uv build`
- [x] 6.5 **[SEC]** `verify` job 的所有步骤都不注入任何令牌（它执行的是仓库自己的测试与静态检查代码）
- [x] 6.6 **[SEC]** `release` job：`needs: verify`、`if: startsWith(github.ref, 'refs/tags/v')`、单独声明 `permissions: contents: write`（全工作流唯一持写权限者）；仅使用自动注入的 `GITHUB_TOKEN`，不声明任何额外 secret
- [x] 6.7 **[SEC]** 全工作流遵守表达式插值边界：`run:` 脚本体内**不出现** `${{ github.* }}` / `${{ env.* }}` / `${{ inputs.* }}` 插值，需要的值一律经该 step 的 `env:` 绑定后以带引号的变量展开引用；step 间传值走 `$GITHUB_ENV` / `$GITHUB_OUTPUT` 并以环境变量读取。（`if:` 条件、`env:` 的值、`uses:` 参数不在此限——它们不进 shell 脚本。）理由：`${{ }}` 在生成脚本文件之前就展开为字面量，`v1.0.0$(...)` 这类 tag 名能通过 6.1 的 glob，一旦插值进 `run:`，命令替换会在格式校验**之前**执行
- [x] 6.8 **[SEC]** `release` job 第一步：从 `GITHUB_REF_NAME`（环境变量，非插值）去掉 `v` 前缀取出版本号，用 1.2 的同一正则**严格校验**，再经 `$GITHUB_ENV` 传给后续 step——`on.push.tags` 的 glob 只是收窄，不是校验（glob 表达不了"三段数字"，尾部 `*` 放行任意后缀）
- [x] 6.9 **[SEC]** 校验被打 tag 的 commit 可从默认分支到达：先 `gh api "repos/$GITHUB_REPOSITORY" --jq .default_branch` 动态取默认分支名（不硬编码 `main`，改名后才不会失败在看似无关的地方），再 `gh api "repos/$GITHUB_REPOSITORY/compare/$DEFAULT_BRANCH...$GITHUB_SHA" --jq .status`，仅 `identical` 与 `behind` 放行，`ahead`/`diverged` 即失败（用 API 而非 `git merge-base`，避免为此加深 checkout 深度或额外 `git fetch`）
- [x] 6.10 **[SEC]** 用 `python scripts/check_version.py --expect "$VERSION"` 断言 tag 名与 `pyproject.toml`、`__init__.py` 三者一致，**放在构建之前**（构建产物名由 `pyproject.toml` 决定，提前拦住能给出清楚得多的诊断）
- [x] 6.11 检查该 tag 的 Release 是否已存在：已存在则**失败**并提示出路（`gh release delete v<x> --cleanup-tag` 后重推，或改用新版本号），**不静默跳过**；查询本身出错（非"明确不存在"）时也失败，不当作"不存在"继续发布
- [x] 6.12 **[SEC]** 令牌只以 step 级 `env: GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}` 注入调用 `gh` 的那几个 step（6.9、6.11、6.14）；**不放在 workflow 级或 job 级 `env`**，因此 `uv build`（会执行构建后端钩子代码）所在的 step 看不到令牌
- [x] 6.13 `uv build` 后用 `sha256sum` 对自己产出的 wheel 与 sdist 生成 `checksums.txt`（记录中的文件名用不含目录前缀的基名，格式需可被 `sha256sum -c` / `shasum -a 256 -c` 直接校验）
- [x] 6.14 **[SEC]** 按命名契约显式拼出 `dist/loopspec-$VERSION-py3-none-any.whl`、`dist/loopspec-$VERSION.tar.gz`、`checksums.txt` 三个路径，逐个断言存在（缺任一即失败），再传给 `gh release create "$TAG" ... --title "$TAG" --generate-notes`；**不使用 `dist/*` 通配符**，也**不传 `--target`**（tag 已存在，不需要创建）
- [x] 6.15 **[SEC]** 不引入第三方发布 action，不使用 artifact 上传/下载 action 跨 job 传产物；检查全部步骤不把 token 写入日志、文件或命令行参数

## 7. 本地任务入口

- [x] 7.1 `Makefile` 新增 `release-dry-run`：跑 `scripts/check_version.py`（若传入 `TAG=v0.2.0` 则改为 `--expect 0.2.0`）→ `sh -n install.sh` →（`shellcheck` 存在则跑，缺失则打印提示并跳过、不失败）→ `uv build`
- [x] 7.2 把 `release-dry-run` 加进 `.PHONY`

## 8. README

- [x] 8.1 重写 "Install" 一节为面向用户：一行式 `curl -fsSL <raw install.sh URL> | sh`；"先下载、审阅、再执行"的两步替代命令；手动 `uv tool install` / `pipx install`；更新（同一条命令）；卸载（`uv tool uninstall loopspec` / `pipx uninstall loopspec`）；Windows 用户直接用 `uv tool install`
- [x] 8.2 新增 "Releases" 一节：发布流程三步按序（① 同时改 `pyproject.toml` 与 `src/loopspec/__init__.py` 的版本号并合入 `main` → ② 对 `main` 上的 commit 打 `v<version>` tag → ③ 推送该 tag）；说明只有第 ③ 步触发发布、tag 名与两处版本号不一致会失败、Release 资产清单
- [x] 8.3 **[SEC]** 在 "Releases" 一节写明两条前置条件/告知：仓库 `Settings → Actions → General → Workflow permissions` 需允许 `Read and write`（否则 `gh release create` 会 403）；以及"能推送 `v*` tag 的人即能发布"，建议用 tag 保护规则（ruleset）收紧——**如实标注这是仓库配置建议，不是本变更已实施的控制**
- [x] 8.4 把 `make install` 移到 "Development" 一节，并补上 `make release-dry-run`（含 `TAG=v0.2.0` 用法）

## 9. 验证

- [x] 9.1 本地跑 `make lint` 与 `make test`，全绿
- [x] 9.2 本地跑 `make release-dry-run`，确认两处版本一致性校验与构建通过；再跑 `make release-dry-run TAG=v0.1.0` 确认三方校验通过，`TAG=v9.9.9` 确认它会失败
- [x] 9.3 用 `sh -n install.sh` 校验语法；`shellcheck` 可用时跑一遍并修掉告警（或加带理由的行内 disable）
- [x] 9.4 交叉核对 workflow、`install.sh`、spec 三处的资产文件名完全一致（`loopspec-<version>-py3-none-any.whl` / `loopspec-<version>.tar.gz` / `checksums.txt`）
- [x] 9.5 **[SEC]** 构造本地夹具验证 4.2 的断言真的生效：分别用「缺少 wheel 条目的 `checksums.txt`」「空文件」「含两条重复条目」「只含 `0.1.0.post1` 条目而目标为 `0.1.0`」四种输入跑校验逻辑，确认四种都非零退出而不是静默通过
- [x] 9.6 **[SEC]** 逐行审 workflow：每个 `actions/checkout` 都有 `persist-credentials: false`；`GH_TOKEN`/`GITHUB_TOKEN` 只出现在调用 `gh` 的 step 的 `env` 下；`uv build`/`pytest`/`ruff`/`mypy`/`uv sync`/`shellcheck` 所在 step 无任何令牌
- [x] 9.7 **[SEC]** 在 `dist/` 里放一个多余文件后走一遍 6.14 的路径，确认它不会被列入待上传清单
- [x] 9.8 **[SEC]** 用非法 tag 名（如 `v0.2`、`v0.2.0-my-branch`）走一遍 6.8 的校验逻辑，确认非零退出且该值不进入任何路径拼接
- [x] 9.9 核对 workflow 的两条触发路径：`main` 的 push 只跑 `verify` 且 `release` 因 ref 条件缺席；tag 推送会跑 `verify` + `release`
- [x] 9.10 **[SEC]** 断言插值边界：`grep -n '\${{' .github/workflows/release.yml` 逐条核对每一处出现的位置——只允许落在 `if:`、`env:`、`uses:`/`with:` 上，**`run:` 脚本体内一处都不允许**
