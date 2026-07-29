# Change State

## Current Focus
- `apply` 完成，54/54 任务已勾选，`isComplete: true`。可执行 `loopspec archive add-release-automation`。

## Frozen Decisions
- ~~发布**版本号驱动**：工作流读 `pyproject.toml` 的 `version`，tag `v<version>` 已存在则只做构建校验并跳过发布（不算失败），不存在则打 tag 并创建 Release。~~ ← 已被 `approval` 第 1 轮否决，见下方 tag 驱动条目。
- **发布 tag 驱动（`approval` 第 1 轮裁决）**：`on.push.tags: ['v[0-9]+.[0-9]+.[0-9]+*']` 触发发布，发布版本号取自 `GITHUB_REF_NAME` 去掉 `v` 前缀；`on.push.branches: [main]` 仍触发但只跑 `verify` 不发布（保住持续校验，裁决改的是发布触发方式而非是否校验）。
- **tag 名是外部输入**：`on.push.tags` 的 glob 只是收窄不是校验，tag 名去掉 `v` 后必须过与 `LOOPSPEC_VERSION` 同一条正则。
- **`check_version.py` 是三方一致性校验器**：无参 = 校验 `pyproject.toml` 与 `__init__.py` 一致；`--expect <v>` = 追加断言两处均等于 tag 版本号。发布路径必须在**构建之前**调用带 `--expect` 的形式（wheel 文件名由 `pyproject.toml` 决定）。
- **Release 已存在 → 失败**（不再跳过）：tag 推送即明确发布意图，静默跳过会掩盖失败；失败信息须给出 `gh release delete v<x> --cleanup-tag` 或改版本号两条出路。
- **被打 tag 的 commit 必须可从 `main` 到达**：走 `gh api repos/<repo>/compare/main...$GITHUB_SHA`，仅 `identical`/`behind` 放行。用 API 而非 `git merge-base`，避免为此加深 checkout 或额外 `git fetch`（后者在 `persist-credentials: false` 下于私有仓库会缺凭据）。
- **表达式插值边界（D18，第 4 轮新增）**：workflow 的 `run:` 脚本体内不得出现 `${{ github.* }}` / `${{ env.* }}` / `${{ inputs.* }}` 插值；值一律经 step 级 `env:` 绑定后以带引号变量展开引用；step 间传值走 `$GITHUB_ENV` / `$GITHUB_OUTPUT`。`if:`、`env:` 的值、`uses:`/`with:` 不在此限（不进 shell 脚本）。**与 D6 的正则闸门是两个阶段，不可互相替代**：`${{ }}` 在生成脚本文件之前就展开为字面量，载荷在格式校验之前即已执行。
- **可达性校验的默认分支名动态取得**（`gh api repos/$GITHUB_REPOSITORY --jq .default_branch`），不硬编码 `main`。
- **`workflow_dispatch` 语义由 ref 决定**：tag ref 上手动触发 = 校验 + 发布（补发入口）；分支 ref 上 = 只校验。没有 tag 就没有发布版本号，不留例外。
- 触发分支为 **`main`**（仓库 `origin/HEAD -> origin/main`），裁决原话说的 `master` 在本仓库不存在。
- 分发渠道只做 **GitHub Release**，不发 PyPI。
- 安装后端优先 `uv tool install`，回退 `pipx install`；两者都缺时报错退出，不回退到 `pip --user` 或 `sudo`。
- 只用 GitHub 自动注入的 `GITHUB_TOKEN`，不引入任何新 secret；默认 `contents: read`，仅发布 job 提升为 `contents: write`。
- Release 资产固定为 wheel + sdist + `checksums.txt`（SHA256）；安装脚本必须校验 checksum。
- 单 workflow 文件 + 两个 job：`verify`（`contents: read`，跑版本校验/lint/test/构建/shell 静态检查）→ `release`（`contents: write`，重新构建并发布）。跨 job 不传 artifact，靠重新构建，以少两个 action 依赖。
- 第三方 action 一律 pin 到 commit SHA：`actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1`（v7.0.1）、`astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9`（v9.0.0）。
- 发布用预装的 `gh release create`，不引第三方发布 action；tag 由 `gh --target $GITHUB_SHA` 顺带创建。
- 版本号读取只有一个入口 `scripts/check_version.py`（`tomllib` + `ast`，无新依赖），CI 与 `make release-dry-run` 共用。
- 版本号格式正则 `^[0-9]+\.[0-9]+\.[0-9]+([._-]?(a|b|rc|alpha|beta|dev|post)[0-9]+)?$`，CI 侧校验 pyproject 值，客户端侧校验 `LOOPSPEC_VERSION` 与 API 返回的 `tag_name`（拼 URL/文件名之前）。
- 安装器只接受**本地已校验**的 wheel 路径，不让 uv/pipx 直接从 URL 装（否则 checksum 校验形同虚设）。
- 无 sha256 校验工具时**中止**，不提供跳过校验的降级或开关。
- `install.sh` 用 `#!/bin/sh` + `set -eu`，全部逻辑包在 `main()` 内、末尾才调用（防半个脚本被执行）；`mktemp -d` + `trap` 清理；`curl -fsSL --proto '=https' --tlsv1.2`；无 `eval`、无 `sudo`。
- Release 资产命名契约：`loopspec-<version>-py3-none-any.whl` / `loopspec-<version>.tar.gz` / `checksums.txt`。
- **令牌可见性边界（D13）**：每处 `actions/checkout` 都 `persist-credentials: false`；令牌只以 step 级 `env: GH_TOKEN` 绑定在调用 `gh` 的 step；执行仓库代码或第三方代码的 step（pytest/ruff/mypy/uv sync/uv build/shellcheck）一律无令牌。
- **构建后端版本约束（D14）**：`[build-system] requires = ["hatchling>=1.31,<2"]`；这不是哈希固定，残余风险显式接受，靠"构建 step 无令牌"+"发布走文件名白名单"抵消。
- **完整性校验三步都必须成功（D8）**：精确匹配文件名定位条目 → 断言恰好 1 条 → 交给校验工具。0 条或 >1 条即失败；禁用 `--ignore-missing`。"没校验到"必须等于"校验失败"。
- **发布按契约显式列出三个文件路径并断言存在（D3）**，不用 `dist/*` 通配符。

## Decision Log
- 2026-07-29 · `proposal` · 拆出两个新 capability：`release-automation`（CI 侧发布链路）与 `cli-installation`（用户侧安装脚本）。二者信任边界不同（CI 凭据 vs `curl | sh` 的本机执行），分开成规格便于 security gate 分别审。
- 2026-07-29 · `proposal` · 加入 `pyproject.toml` 与 `src/loopspec/__init__.py` 的版本一致性 CI 校验：两处目前靠人手同步，漂移会让源码 checkout 下的 `loopspec version` 输出错误版本。
- 2026-07-29 · `proposal` · Modified Capabilities 留空：README 属文档产物，`loopspec version` 行为不变（安装脚本只是其消费者）。
- 2026-07-29 · `design` · 「跳过发布」必须是**成功**退出：否则默认分支上每个不带版本变更的 commit 都亮红叉，CI 信号会被无视。跳过与失败靠 job summary 文案区分。
- 2026-07-29 · `design` · 不让 `__init__.__version__` 从 `importlib.metadata` 单向派生（那样能彻底消灭第二处版本号）：会改变 `loopspec version` 在源码 checkout 下的既有 fallback 语义，属超范围行为变更。本次只加 CI 一致性约束。
- 2026-07-29 · `design` · `install.sh` 不依赖 `jq`（macOS/精简容器无预装）：用 `sed` 宽松抽取 `tag_name`，随后用严格正则校验——解析宽松、校验严格。
- 2026-07-29 · `design` · 不自动替用户安装 uv：在用户未同意时扩大安装范围。改为打印官方安装命令并非零退出。
- 2026-07-29 · `design` · `checksums.txt` 保证的是「传输未被篡改」，不是「发布者可信」（它与产物同源、同 job 生成）。spec 里如实写，不过度承诺。
- 2026-07-29 · `security` · 判定 FAIL，4 项阻塞问题：① checkout 默认持久化令牌到 `.git/config`，而 `verify` 跑 pytest、`release` 跑 `uv build`，都能读到它；② `release` job 持写令牌的同时从 PyPI 解析并执行未固定版本的构建后端；③ 完整性校验缺「wheel 条目必须存在于 `checksums.txt`」要求，存在空校验假通过（且 spec 场景与资产契约自相矛盾，macOS `shasum` 无 `--ignore-missing`）；④ `gh release create dist/*` 用通配符，无法满足「上传且仅上传三个资产」。
- 2026-07-29 · `security` · 明确通过项（重做时原样保留）：版本号两侧正则闸门、无跳过校验的降级路径、action pin 到 SHA、`mktemp -d` + `trap`、无 `eval`/`sudo`、不监听 `pull_request`（无 fork PR 执行面）。
- 2026-07-29 · `design`（第 2 轮）· 对 gate 第 ② 项**不采纳**"改从 `verify` 传产物"这条路：那只是把同一段构建后端代码搬到另一个 job 执行，风险实质未消除，却要多引入两个 action 依赖。改为对因下药——令牌对构建 step 不可见 + 发布内容按文件名白名单 + 构建后端加版本上下界。
- 2026-07-29 · `design`（第 2 轮）· 完整性校验改为三步显式断言，核心原则写死为「"没校验到"必须等于"校验失败"」；定位条目用**精确文件名相等**而非子串匹配，否则 `0.1.0` 会命中 `0.1.0.post1`。
- 2026-07-29 · `security`（第 2 轮）· 判定 PASS。4 项阻塞问题逐条核验为已落到可检查的约束（非重述）。留 5 条非阻塞实现提醒：① `checksums.txt` 用基名 → 校验须以临时目录为 CWD，CI 侧生成时也别带 `dist/` 前缀；② 给 `gh` step 加 `GH_REPO: ${{ github.repository }}`，别依赖从 remote 推断；③ 预发布版本号（`0.1.0-rc1`）会被 PEP 440 规范化为 `0.1.0rc1`，D3 的存在性断言会失败——失败方向可接受，但要留注释；④ 运行时依赖树不在完整性保证范围内（已如实声明）；⑤ `hatchling` 版本下界日后需手动跟进，与 action SHA 是同一类维护负担。
- 2026-07-29 · `design`（第 2 轮）· 新增两条如实记录的残余风险：构建时仍会在版本范围内解析第三方构建后端（非哈希固定）；`uv tool install` 解析的运行时依赖树不在本次完整性保证范围内。

- 2026-07-29 · `approval` 第 1 轮 · **要求修改**（裁决文件 `approval/changes-requested.md`，人的原话存于其中）。裁决要点：发布触发方式从"默认分支 push + 读 `pyproject.toml` 的 `version`"改为 **tag 驱动**——推送 `v<version>` 形式的 tag 才触发发布，且发布版本号直接取自 tag 名。连带需重新裁定的点：「Release 已存在则跳过且算成功」这条语义（其存在理由随 tag 驱动而消失）、`scripts/check_version.py` 的职责（从"版本号来源"变为"tag 名与 `pyproject.toml`/`__init__.py` 三者一致性校验器"）、tag 名作为新的外部输入需纳入正则闸门。

- 2026-07-29 · `design`（第 3 轮）· 「版本号读 tag」**不能**免掉与 `pyproject.toml` 的一致性校验：wheel/sdist 的文件名由 `pyproject.toml` 的 `version` 决定，tag `v0.2.0` 配 `pyproject.toml` 里的 `0.1.0` 会产出 `loopspec-0.1.0-py3-none-any.whl`，即 Release 版本号与资产文件名矛盾。故保留 `check_version.py` 但改为三方校验器，并前移到构建之前。
- 2026-07-29 · `design`（第 3 轮）· 保留 `on.push.branches: [main]` 只跑 `verify`：裁决改的是发布触发方式，不是"要不要持续校验"。只留 `on.push.tags` 会让 `main` 上的普通 commit 完全没有 CI，那是相对第 2 轮方案的功能退化而非裁决要求。
- 2026-07-29 · `design`（第 3 轮）· D15（tag 可从 `main` 到达）是对裁决原话"master 分支提交 tag"的落实方式，**非裁决明确要求**，已列入 Open Questions 待下一轮 approval 单独接受或否掉；若否掉只需删掉那一个 step。
- 2026-07-29 · `design`（第 3 轮）· `gh api compare` 而非 `git merge-base --is-ancestor` 做可达性校验：后者需 `fetch-depth: 0` 加一次 `git fetch origin main`，而在 `persist-credentials: false` 之下额外的 `git fetch` 于私有仓库会缺凭据；`gh api` 这一步本就允许持有令牌。

- 2026-07-29 · `security`（第 3 轮）· 判定 FAIL，1 项阻塞：tag 名是攻击者可影响的输入（`on.push.tags` 的 glob 尾部 `*` 放行任意后缀，`v1.0.0$(...)` 也能触发），但没有任何需求禁止它以 `${{ github.ref_name }}` 形式插值进入 `run:` 脚本体——那是 GitHub Actions 的模板注入路径，且**发生在正则校验之前**（载荷在表达式展开的那一刻就已执行）。正则是"用途闸门"，不是注入防线，两者不可互相替代。design 的 D3 片段恰好写了安全形态（经 `env` 传入、带引号变量展开），但未被固定为需求。
- 2026-07-29 · `security`（第 3 轮）· 核对确认第 1 轮的 4 项修复在本轮未被稀释：D13 令牌可见性边界、D14 构建后端约束、D8 完整性校验三步断言、D3 发布文件名白名单。
- 2026-07-29 · `security`（第 3 轮）· 认定 tag 驱动下的**版本混淆/降级攻击已被闭环堵死**，这是三条约束的联合效果而非任何单条的目标：D15（tag 必须可从 `main` 到达）+ D5 的 `--expect`（该 commit 的两处版本号必须都等于 tag 版本号）+ D16（同名 Release 不得已存在）⇒ 能推 tag 者只能发布"main 历史上某个自己声明了该版本号、且尚未发布过的 commit"，无法凭空造高版本号。**否掉 D15 会同时削弱这层防护**，下一轮 approval 判断 D15 时需知晓此连带影响。

- 2026-07-29 · `design`（第 4 轮）· D18 写成"禁止插值"而非"对插值做转义"：转义要逐处判断 shell 引号层级与嵌套命令替换的上下文，容易漏；`env:` 绑定是结构性的一次性正确。
- 2026-07-29 · `design`（第 4 轮）· 可达性校验（D15）**只能**放在 `release` job，不能前移到 `verify` 的第一步：它要调 GitHub API，而 `verify` 按 D13 第 3 条不持有令牌；前移就得给 `verify` 注入令牌，等于用更重要的约束换次要的时序优化。后果如实记录：给未合入默认分支的 commit 打 tag 仍会让该 commit 的代码在 `verify` 中执行一次（影响有界：无令牌、只读、Actions cache 作用域不向默认分支回写）。

- 2026-07-29 · `security`（第 4 轮）· 判定 **PASS**。插值边界已落到可机械检查的约束（D18 + spec 需求 + tasks 6.7 + 验证 9.10），且核验了 `$GITHUB_ENV` 写入顺序（先校验后写入，不构成换行伪造环境变量的二次注入点）。第 1 轮的 4 项修复成果经核对未被稀释。留 5 条非阻塞实现提醒：① D18 目前靠人工 grep，建议后续另起变更引入 `zizmor`/`actionlint` 做自动护栏；② tasks 6.14 的 `$TAG` 来源未写明，建议用已校验的 `VERSION` 重建为 `v$VERSION`（与原值等价）；③ CI 侧生成 `checksums.txt` 时注意 `sha256sum dist/*.whl` 会带 `dist/` 前缀；④ 预发布版本号（`0.1.0-rc1`）会被 PEP 440 规范化为 `0.1.0rc1`，D3 的存在性断言会失败——方向可接受但要留注释；⑤ 运行时依赖树不在完整性保证范围内、`hatchling` 版本下界需手动跟进。

- 2026-07-29 · `approval` 第 2 轮 · **APPROVED**（裁决文件 `approval/approved.md`，人的原话存于其中）。人同时给出一条威胁模型判断：能推送 tag 的只有 repo owner，故 tag 名被恶意构造不是需要重点防范的风险。该判断**不改变已批准的方案**——D6 格式闸门与 D18 插值边界都是零成本写法约束，且 D6 还是 D3/D5"tag 名与构建产物名一致"断言的前置，D18 还统一了 step 间传值路径，删掉收益为零。**D15 随方案原样批准**（人未单独否掉）；注意人的判断针对"谁可以发布"，而 D15 约束的是"哪些 commit 可被发布"，两者相邻但不重合。
- 2026-07-29 · `approval` 第 2 轮 · 冻结点：后续节点不得静默改动 Frozen Decisions 里的任何一条；改动需再走一轮 approval。

- 2026-07-29 · `apply` · 完成 54/54 任务，`make lint` clean、`make test` 567 passed、`make release-dry-run` 通过（`TAG=v9.9.9` 按预期失败）、`shellcheck install.sh` clean。报告见 `apply/report.md`。6 处偏离设计已在报告中记录，其中最主要的一条：tasks 9.5–9.10 原为人工核对动作，改为固化成 62 个 pytest 用例（`tests/test_check_version.py`、`tests/test_install_script.py`、`tests/test_release_workflow.py`），使令牌可见性、插值边界、资产白名单、checksum"恰好一条"断言等约束变成回归护栏而非一次性检查。
- 2026-07-29 · `apply` · `scripts/check_version.py` 增加 `--repo-root`（设计未提）：原实现从 `__file__` 推导仓库根，无法对夹具仓库测试。默认值不变，CI 调用方式不变。
- 2026-07-29 · `apply` · workflow 的 lint/test/build 走 `make` 目标而非原始命令，避免"改了 Makefile 而 CI 没跟上"的漂移；仅 `uv sync --frozen` 与 `sh -n`/`shellcheck` 保留显式写法（前者 CI 专用，后者在 CI 是硬要求而本地容忍缺失）。
- 2026-07-29 · `apply` · "Release 已存在"改用单次 `gh api repos/.../releases/tags/$TAG` 而非 `gh release view`：需要区分"明确 404"与"查询本身失败"，单次调用即可做到，语义与 D16 一致。

## Rejected Options
- **每次 push 都发 Release**：会把 Release 列表刷成 commit 列表，且版本号无意义。改为版本号驱动。
- **发布到 PyPI**：需要账号与 trusted publisher 配置，超出本次范围，留作后续变更。
- **多平台二进制打包（PyInstaller 等）**：纯 Python wheel 已跨平台，不值当。
- **`install.ps1`（Windows）**：README 指引 Windows 用户直接 `uv tool install`。
- **自动 bump 版本号**：版本号由人决定，工作流只消费不改写。
- **第三方发布 action（`softprops/action-gh-release`）**：为省几行 YAML 引入新供应链依赖，改用预装的 `gh`。
- **跨 job 用 `upload-artifact`/`download-artifact` 传产物**：多两个 action 依赖；`uv build` 重跑只需数秒。
- **`pip install --user` 作为第三个回退**：污染 default Python 环境，违背 CLI 工具的环境隔离语义。
- **`jq` 解析 GitHub API 响应**：非 macOS/精简容器默认组件。
- **让 `uv tool install <URL>` 直接从远端安装**：校验的字节与安装的字节不同源，checksum 形同虚设。
- **PR 上也跑工作流 / Dependabot 跟进 action 版本**：都超出本次范围，job 拆分已为前者留好口子。
- **`sha256sum --ignore-missing`**：macOS 的 `shasum` 是 Perl 脚本、不支持该选项；且"零个文件被校验"时各实现行为不一致，等于给假通过留门。
- **`grep <version>` 子串匹配定位 checksums 条目**：会让 `0.1.0` 同时命中 `0.1.0.post1`，且匹配不到时得到空串易致假通过。改为精确文件名相等 + 行数断言。
- **对运行时依赖做哈希固定**：需 `--require-hashes` 级方案，超出本次范围；spec 里如实声明不承诺。
- **（`approval` 第 1 轮由人否掉）「发布由 `pyproject.toml` 的 `version` 驱动 + Release 已存在则跳过且算成功」这一整套发布判定方式**：改为 tag 驱动，发布版本号取自 tag 名。原方案的两条支撑理由随之失效——"避免默认分支每个 commit 都刷 Release"（tag 驱动下不存在此问题）与"跳过必须算成功以免刷红叉"（一次 tag 推送即一次明确发布意图，静默跳过会掩盖失败）。
- **（第 3 轮否）`hatch-vcs` 一类从 git tag 派生版本号的方案**：它能真正做到版本号只有 tag 一个来源，但代价是新增构建期依赖（与 D14 收缩构建后端信任面的方向相反）、改变 `loopspec version` 在源码 checkout 下的 `__version__` fallback 语义、以及让"从 sdist 再构建"多一个 git 元数据耦合的坑。留作后续变更；本轮用"tag 权威 + CI 强制三方一致"取得等价的正确性保证。
- **（第 3 轮否）`on.push.tags: ['v*']`**：会把 `vendor-snapshot` 一类 tag 拖进发布路径。收窄为 `v[0-9]+.[0-9]+.[0-9]+*`，但明确记录该 glob 不是校验。
- **（第 3 轮否）分支 ref 上手动触发也能发布**：那要凭空读 `pyproject.toml` 猜一个版本号，等于把刚被否决的旧机制从后门放回来。没有 tag 就没有发布版本号。
- **（第 3 轮否）只留 `on.push.tags` 而丢掉分支 push 的校验**：会让 `main` 上的普通 commit 完全没有 CI。

## Open Questions
- 触发分支确认为 `main` 还是要额外监听 `master`？当前按 `main` 实现，留待 `approval` 人工确认。
- 是否要在 PR 上也跑 `verify` job？本次不做，后续加一个 `on.pull_request` 即可。
- （`approval` 第 1 轮提出，未settle）是否加一条"被打 tag 的 commit 必须可从默认分支到达"的校验？人的原话是"master 分支提交 tag"，但 git 的 tag 不属于任何分支，落实该意图需要这条校验（代价：checkout 需 `fetch-depth: 0`）。
- （`approval` 第 1 轮提出，未settle）tag 驱动下 `workflow_dispatch` 的语义如何定义？跑在分支 ref 上时没有 tag 名可读。
- （`approval` 第 1 轮提出，未settle）是否改用 `hatch-vcs` 一类方案，让 tag 成为版本号的唯一来源、彻底消灭 `pyproject.toml` 与 `__init__.py` 两处版本号？需评估新增构建依赖与对 `loopspec version` 源码 fallback 语义的影响。

## Artifact Notes
- `proposal.md` · 新 capability：`release-automation`、`cli-installation`；无 Modified。
- `design.md`（第 2 轮）· D1~D14。D3 与 D8 为回应 gate 而改写，D13（令牌可见性边界）、D14（构建后端约束与特权 job 内构建的隔离条件）为新增。第 1 轮原文在 `.attempts/round-001/`。
- `specs/release-automation/spec.md` · 12 条需求：触发条件、job 拆分与权限、版本一致性与格式校验、版本号驱动的发布判定、资产命名契约（含"显式列出不用通配符 + 存在性断言"）、凭据最小化、**令牌不得暴露给执行仓库/第三方代码的步骤**、**构建后端受版本范围约束**、action pin SHA、不引额外第三方 action、本地预演、文档。
- `specs/cli-installation/spec.md` · 11 条需求，其中「产物完整性校验」已改写为三步都必须成功（精确匹配定位 → 断言恰好 1 条 → 执行校验），并补了缺失条目/空文件/重复条目/相似版本号误匹配四个失败场景。
- `tasks.md`（第 2 轮）· 9 组共 41 个任务；本轮新增/改写 2.1–2.2、4.1–4.4、6.2、6.5、6.8、6.10、9.5–9.7。**[SEC]** 标注供 gate 定位。
- 影响面：新增 `.github/workflows/release.yml`、`install.sh`、`scripts/check_version.py`、`tests/test_check_version.py`；修改 `pyproject.toml`（`[build-system] requires`）、`README.md`、`Makefile`（`release-dry-run`）。
- 首次合并到 `main` 后会立即发出 `v0.1.0`（当前版本尚无 Release），属预期行为。
- README 里的一行式安装命令指向 `main` 分支的 raw URL，**合并前该链接无效**，属预期时序。
- security gate 重点：CI 凭据（只用 `GITHUB_TOKEN`、按 job 最小权限）、外部输入校验（版本号两侧正则）、供应链（action pin SHA）、产物完整性（SHA256 强制校验、无降级开关）。无 authn/authz 变更。
- `approval/changes-requested.md` · `approval` 第 1 轮判定「要求修改」，人的原话与向人展示的摘要均在该文件内（rollback 后原文存于 `.attempts/round-002/`）。
- `design.md`（第 3 轮）· D1~D17。D2/D3/D5/D12 按 tag 驱动重写；D15（tag 可从 `main` 到达）、D16（Release 已存在则失败）、D17（`workflow_dispatch` 语义）为新增；D4、D6~D11、D13、D14 原样保留。
- `specs/release-automation/spec.md`（第 3 轮）· 16 条需求。新增/重写：tag 触发与分支只校验、发布版本号取自 tag、tag 名格式校验、tag 必须可从默认分支到达、手动触发语义、三处版本号一致性、Release 已存在则失败、发布流程文档（含 tag 推送权限=发布权限的如实告知）。
- `specs/cli-installation/spec.md`（第 3 轮）· 11 条需求，内容与第 2 轮一致（安装脚本不受 tag 驱动影响），仅在"查询最新版本失败"场景补上"仓库尚无任何 Release"这一情形。
- `tasks.md`（第 3 轮）· 9 组共 49 个任务；本轮改动集中在第 1 组（1.4/1.5 新增 `--expect`）与第 6 组（6.1、6.7–6.11、6.13 按 tag 驱动改写），新增验证 9.8、9.9。
- 首次合并到 `main` **不再**发出任何 Release（相对前两轮的明确改善）；发首个版本需显式 `git tag v0.1.0 && git push origin v0.1.0`。
- 时序提醒：推出第一个 tag 之前 `releases/latest` 不存在，一行式安装命令会因查不到 latest Release 而失败——属预期窗口。
- `design.md`（第 4 轮）· D1~D18。新增 D18（插值边界）；D15 补上"联合承担版本混淆防护"与"为何只能放在 `release` job"两段；D2 补上"glob 尾部 `*` 放行任意后缀"的后果。
- `specs/release-automation/spec.md`（第 4 轮）· 17 条需求。新增「外部可影响的值不得以表达式插值进入脚本体」（3 个场景，含 `v1.0.0$(...)` 这一具体攻击输入）；「tag 名格式校验」改标题为"用途闸门"并写明与插值约束不可互相替代；「可从默认分支到达」补上默认分支名动态取得与版本混淆防护的联合关系。
- `tasks.md`（第 4 轮）· 9 组共 54 个任务。新增 6.7（插值边界）、9.10（`grep '\${{'` 逐条核对位置）；6.9 改为动态取默认分支名；6.8 明确"先校验再经 `$GITHUB_ENV` 传递"。
- `security/pass.md`（第 4 轮）· PASS，含 5 条非阻塞实现提醒。
- `approval/approved.md` · `approval` 第 2 轮 APPROVED，人的原话与威胁模型判断均在该文件内。
- `apply/report.md` · 54/54 任务完成；新增 `.github/workflows/release.yml`、`install.sh`、`scripts/check_version.py` 与三个测试文件；修改 `pyproject.toml`、`Makefile`、`README.md`。真实测试输出与 6 处设计偏离均在报告内。
