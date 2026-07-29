## Context

仓库当前没有 `.github/`、没有 CI、没有任何分发产物。`make build`（`uv build`）产出的 wheel/sdist 只留在本地 `dist/`，README 的 "Install" 教的是 `make install`（`uv sync` 建开发虚拟环境）。用户想用这个 CLI，必须 clone + 装 uv + sync。

约束与既有事实：

- 包是**纯 Python**（`requires-python >= 3.11`，hatchling 构建，无扩展模块），产出的 `py3-none-any` wheel 天然跨平台——不需要按平台分发二进制。
- wheel 通过 `[tool.hatch.build.targets.wheel.force-include]` 把仓库根的 `schemas/` 打进 `loopspec/builtin_schemas`，所以**必须走正规构建**，不能靠 `pip install git+...` 之外的土办法绕过（`uv build` 已覆盖）。
- 版本号有**两处**：`pyproject.toml` 的 `project.version` 与 `src/loopspec/__init__.py` 的 `__version__`（当前都是 `0.1.0`）。`loopspec version` 优先读 `importlib.metadata`，只在源码 checkout 下回退到 `__version__`——两者漂移不会让安装版报错，只会让源码版静默撒谎。
- 仓库默认分支是 `main`（`origin/HEAD -> origin/main`），需求原文说的 `master` 在本仓库不存在。
- 已有 `Makefile` 作为统一任务入口（`install`/`dev`/`test`/`lint`/`build`/`clean`），新增能力应挂在这里而不是另起脚本入口。

**信任边界**（security gate 的重点，先在此点明）：本变更引入两处新的信任边界，且**都不涉及 authn/authz 变更**。

1. **CI 内执行的代码**：第三方 GitHub Action 与 GitHub API 调用，凭据是自动注入的 `GITHUB_TOKEN`。
2. **用户机器上执行的脚本**：`curl ... | sh`，输入包括环境变量 `LOOPSPEC_VERSION` 与从 GitHub API 拿到的 `tag_name`，输出是往用户机器上装一个可执行文件。

## Goals / Non-Goals

**Goals:**

- 默认分支收到 push 时自动跑 lint + test + 构建，红了就红在 CI 里，不靠提交者的自觉。
- 版本号是新的时候自动创建 GitHub Release，附 wheel、sdist、`checksums.txt`；版本号没变则什么都不发，且**不算失败**。
- 用户能用一条命令完成安装，且**同一条命令**用于更新。
- 安装链路端到端可验证完整性：Release 里带 SHA256，脚本校验后才装。
- CI 侧不新增任何 secret；权限按 job 最小化。
- 本地能预演 CI 的可本地验证部分（`make release-dry-run`），不必"推上去看会不会红"。

**Non-Goals:**

- 不发布到 PyPI（需要账号与 trusted publisher 配置，留作后续变更）。
- 不做平台专属二进制打包（PyInstaller/Nuitka 等）——纯 Python wheel 已够。
- 不提供 `install.ps1`；Windows 用户在 README 里被指引直接用 `uv tool install`。
- 不自动 bump 版本号、不自动生成 changelog 正文之外的内容（release notes 用 GitHub 的 `--generate-notes`）。
- 不引入 Dependabot / renovate 来跟进 action 版本（本次只留注释说明如何手动更新）。
- 不在 PR 上跑这套工作流（本次只覆盖默认分支 push 与手动触发；PR 校验留作后续变更）。

## Decisions

### D1 — 一个 workflow 文件，两个 job：`verify`（只读）→ `release`（可写）

`.github/workflows/release.yml` 顶层声明 `permissions: contents: read`，`verify` job 继承它跑版本校验 + lint + test + 构建；`release` job 声明 `needs: verify` 并单独提升为 `permissions: contents: write`。

- **为什么不是单 job**：GitHub Actions 的 `permissions` 粒度是 job，单 job 意味着 lint/test 这些"执行仓库里任意代码"的步骤也带着 `contents: write` 跑。拆开后写权限只覆盖"判定 + 发布"这几步。
- **`release` job 重新构建，而不是用 artifact 传递**：跨 job 传产物要引入 `actions/upload-artifact` + `actions/download-artifact` 两个额外 action 依赖，而 `uv build` 对同一 commit 是确定性的、耗时以秒计。少两个供应链面比省几秒更值。`release` job 自己算 `checksums.txt`，发布的产物和校验的产物同源。
- **替代方案**：两个独立 workflow 文件（`ci.yml` + `release.yml`）——被否，会重复 checkout/setup 且 `needs` 关系要靠 `workflow_run` 表达，复杂度更高。

### D2 — 发布判定：`gh release view v<version>` 存在即跳过

`release` job 第一步查 `v$VERSION` 这个 Release 是否已存在：存在 → 写一行 job summary（`skipped: v0.1.0 already released`）并正常结束；不存在 → 发布。

- **为什么以版本号而非 commit 为发布单位**：每次 push 都发会把 Release 列表刷成 commit 列表，版本号也就失去意义。抬 `version` 就是"我要发布"这个意图的唯一表达。
- **为什么查 Release 而不查 tag**：`gh release create` 会顺带创建 tag，所以 Release 存在 ⊇ tag 存在；查 Release 一次调用就够，也不需要 `fetch-tags`。
- **跳过必须是成功退出**：否则默认分支每个不带版本变更的 commit 都会亮红叉，CI 信号很快就被无视。

### D3 — 用 `gh release create` 而不是第三方发布 action

`gh` 预装在 GitHub-hosted runner 上，一条命令同时完成"建 tag + 建 Release + 上传资产"：

```
gh release create "v$VERSION" dist/* checksums.txt --target "$GITHUB_SHA" --title "v$VERSION" --generate-notes
```

- **替代方案** `softprops/action-gh-release`：更声明式，但是第三方 action，等于为了省几行 YAML 引入一个新的供应链依赖。本变更的目标之一就是压缩这个面。
- 副作用：tag 由 `gh` 用 `--target $GITHUB_SHA` 创建，不需要 `git push --tags`，也不需要为 git 配用户身份。

### D4 — 第三方 action 一律 pin 到 commit SHA

只用两个 action，都按 `<action>@<40位 SHA> # <tag>` 的形式写：

- `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1` # v7.0.1
- `astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9` # v9.0.0

（两个 SHA 已通过 `gh api repos/<repo>/git/ref/tags/<tag>` 核对为对应 tag 指向的 commit。）

- **为什么 pin SHA 而不是 `@v7`**：可变 tag 可以被重新指向，SHA 不能。CI 里执行的第三方代码是最直接的供应链入口。
- **代价**：SHA 不会自动跟进上游修复。缓解：行尾注释保留人类可读的 tag，README/design 记录更新方式（重跑 `gh api` 取新 SHA）。
- `setup-uv` 选自 Astral 官方（uv 的作者），而非社区 action；开启其内建 cache 以缩短 `uv sync` 时间。

### D5 — 版本号的单一读取入口：`scripts/check_version.py`

新增一个标准库脚本（`tomllib` 是 3.11+ 内建，无新依赖）：读 `pyproject.toml` 的 `project.version`，读 `src/loopspec/__init__.py` 的 `__version__`，两者一致则把版本号打到 stdout 并以 0 退出，不一致则打错误到 stderr 并以非零退出。

- CI 的 `verify` job、`release` job、以及 `make release-dry-run` **共用这一个脚本**，避免"CI 用 grep、Makefile 用 sed"这种多份实现漂移。
- `__version__` 的读取用 `ast` 解析而不是 `import loopspec`——CI 的 `verify` job 在装依赖之前就要能跑这个校验，且解析源码比导入包更少副作用。
- **替代方案**：让 `__init__.py` 从 `importlib.metadata` 单向派生版本号，彻底消灭第二处。被否：那会改变 `loopspec version` 在源码 checkout 下的既有行为（现在有意保留 `__version__` 作为 fallback），属于超出本变更范围的行为变更。这里只加约束，不改语义。

### D6 — 版本号格式校验（输入校验，两侧都做）

版本字符串在被拼进 git tag、URL 或文件名之前，必须匹配：

```
^[0-9]+\.[0-9]+\.[0-9]+([._-]?(a|b|rc|alpha|beta|dev|post)[0-9]+)?$
```

- CI 侧：`scripts/check_version.py` 校验 `pyproject.toml` 里的值（防止一个手滑的版本号变成畸形 tag）。
- 客户端侧：`install.sh` 校验 **两个**来源——用户给的 `LOOPSPEC_VERSION`，以及从 GitHub API 响应里提取出的 `tag_name`。
- **为什么 API 返回值也要校验**：它是外部输入。校验前它是"一段将被拼进下载 URL 和本地文件名的字符串"，未校验就拼接等于把 `../` 或 shell 元字符的处置权交给上游响应。校验之后它只可能是 `[0-9a-z._-]` 的子集。

### D7 — `install.sh` 的产物定位：先解析 `tag_name`，再拼固定命名的 URL

1. 若 `LOOPSPEC_VERSION` 已给 → 校验格式，直接用，**不调 API**。
2. 否则 `GET https://api.github.com/repos/mingyuans/LoopSpec/releases/latest`，从响应里抽 `"tag_name": "vX.Y.Z"`，剥掉 `v` 前缀 → 校验格式。
3. 用版本号拼出三个确定的 URL：
   - `.../releases/download/v$V/loopspec-$V-py3-none-any.whl`
   - `.../releases/download/v$V/checksums.txt`

- **为什么不依赖 `jq`**：`jq` 不是 macOS/精简容器的默认组件。只抽一个形如 `"tag_name": "v0.1.0"` 的字段，用 `sed` 足够，且抽出的结果立刻过 D6 的正则闸门——解析宽松、校验严格。
- **为什么不用 `/releases/latest/download/<file>` 重定向**：那个路径要求文件名已知，而文件名含版本号，绕不开先拿版本号这一步。
- **为什么只装 wheel 不装 sdist**：wheel 是 `py3-none-any`，无需在用户机器上跑构建后端。sdist 仍然发布，供需要从源码构建的场景使用。
- Release 资产的文件名由 hatchling 的标准命名规则决定（`loopspec-<version>-py3-none-any.whl` / `loopspec-<version>.tar.gz`），这构成 CI 与脚本之间的**命名契约**，写进 spec。

### D8 — 完整性校验：先下载到临时目录校验 SHA256，再交给安装器

wheel 与 `checksums.txt` 都下到 `mktemp -d` 的目录，用 `sha256sum -c` 或 `shasum -a 256 -c` 校验（按 `command -v` 探测，Linux/macOS 各覆盖其一），通过后才把**本地文件路径**交给安装器。

- **为什么不让 `uv tool install <URL>` 直接从远端装**：那样 checksum 校验就成了摆设——校验的字节和安装的字节不是同一次下载。
- **两种校验工具都不存在时：中止，退出码非零。** 明确不提供"跳过校验继续安装"的降级路径，也不提供跳过校验的开关。这是本变更里最不该被"便利性"侵蚀的一条。
- `checksums.txt` 与产物同源（同一个 `release` job 现算现发），它验证的是"传输/镜像过程没被改"，不是"发布者可信"——后者由 GitHub Release 的来源保证。这个边界写进 spec，避免过度承诺。

### D9 — 安装后端：`uv tool install --force` 优先，回退 `pipx install --force`，都没有则失败

- `--force` 让"安装"和"更新"是同一条路径：已装则覆盖到目标版本，未装则新装。脚本因此天然幂等，README 里"更新"和"安装"是同一条命令。
- **不回退到 `pip install --user`**：会污染用户的 default Python 环境，且和 CLI 工具应有的隔离语义（uv tool / pipx 都建独立环境）相悖。
- **绝不使用 `sudo`**、绝不写系统目录。脚本没有任何提权路径。
- 两者都缺 → 打印 uv 的官方安装命令并以非零码退出。**不**自动去装 uv：那是在用户没同意的情况下扩大安装范围。

### D10 — `install.sh` 的执行安全形态

- `#!/bin/sh` + `set -eu`（不写 `pipefail`——POSIX sh 没有；管道处一律用显式返回值判断）。目标是 dash/bash/zsh 都能跑，不额外要求 bash。
- 全部逻辑包在 `main() { ... }` 里，文件末尾才 `main "$@"`。这样 `curl | sh` 遇到连接中断、只收到半个脚本时，`main` 不会被调用，不会执行"半个安装"。
- `trap 'rm -rf "$tmp"' EXIT INT TERM` 清理临时目录；临时目录由 `mktemp -d` 创建，不用可预测路径（避免 `/tmp/loopspec` 这类被抢占的固定名）。
- 所有下载：`curl -fsSL --proto '=https' --tlsv1.2`（有 `--proto` 则强制只走 https，杜绝被重定向到 http）。
- **无 `eval`、无 `curl | sh` 的二次嵌套、不下载并执行任何除 wheel 之外的东西。**
- 静态检查：`shellcheck`（若可用）+ `sh -n` 语法校验，纳入 `verify` job；`shellcheck` 在 GitHub-hosted runner 上预装，本地缺失时 `make release-dry-run` 只跳过它并给出提示（本地缺工具不该阻塞开发者，但 CI 上它是硬要求）。

### D11 — PATH 未就绪时警告但不失败

安装成功后执行 `loopspec version` 自检。若 `command -v loopspec` 找不到，打印 `~/.local/bin` 加入 PATH 的提示（uv 场景另提 `uv tool update-shell`），**退出码仍为 0**——包确实装好了，问题在当前 shell 的 PATH，报失败会误导。

### D12 — README 结构：用户视角的 Install 与贡献者视角的 Development 分离

现有 README 把 `make install` 放在 "Install" 下，那实际是开发环境搭建。改为：

- **Install**：一行式脚本（含"先下载再审阅"的两步替代命令）、`uv tool install` / `pipx` 手动路径、更新（同一条命令）、卸载、Windows 说明。
- **Releases**：说明发布是版本号驱动的、Release 里有什么资产、以及**仓库设置前置条件**（`Settings → Actions → General → Workflow permissions` 需允许 `Read and write`，否则 `gh release create` 会 403）。
- **Development**：保留 `make install` / `test` / `lint` / `build` / `clean`，新增 `release-dry-run`。

## Risks / Trade-offs

- **[忘记 bump 版本号 → 以为发了其实没发]** → `release` job 在跳过时往 job summary 写明 `skipped: vX.Y.Z already released`，并在 README 的 Releases 一节写清"抬版本号才会发布"。
- **[仓库 Actions 权限没开 `Read and write` → 发布 403]** → 首次上线必踩，写进 README 前置条件；`release` job 的失败信息本身也指向权限设置。
- **[`curl | sh` 的固有信任问题]** → 无法根除，只能缩小：README 同时给出"下载 → 审阅 → 执行"的两步命令和完全手动的 `uv tool install` 路径；脚本本身不提权、不写系统目录、只装经 SHA256 校验的 wheel。
- **[pin 到 SHA 的 action 不会自动更新，可能长期停在有已知问题的版本]** → 行尾注释保留 tag，design 记录用 `gh api repos/<repo>/git/ref/tags/<tag>` 取新 SHA 的方法；后续可另起变更引入 Dependabot。
- **[`verify` 与 `release` 各构建一次，若构建非确定性则"校验的"与"发布的"不是同一份]** → hatchling 对同一 commit 的输出是确定的；且 `checksums.txt` 由 `release` job 对**自己**产出的文件计算，发布的资产与其校验值必然自洽。真正的残余风险仅是"verify 通过而 release 构建失败"，那会红在 CI 里，不会发出坏产物。
- **[GitHub API 未认证时有 60 次/小时/IP 的速率限制]** → 只在未指定 `LOOPSPEC_VERSION` 时调一次；被限流时 curl 失败，脚本报错并提示可用 `LOOPSPEC_VERSION=x.y.z` 跳过 API。
- **[`--generate-notes` 的 release notes 质量取决于 commit 信息]** → 接受。本变更不引入 changelog 维护流程。
- **[跳过发布用"成功退出"表达，可能掩盖真实的发布故障]** → 跳过与失败在 job summary 中文案不同（`skipped:` vs step 失败），且跳过只在 `gh release view` **明确返回已存在**时发生；API 调用本身出错走失败路径，不会被误判为"已存在"。

## Migration Plan

1. 新增 `.github/workflows/release.yml`、`install.sh`、`scripts/check_version.py`；改 `Makefile`、`README.md`。
2. 本地 `make release-dry-run` + `make lint` + `make test` 全绿。
3. 合并到 `main` 后工作流首次运行：当前 `0.1.0` 尚无 Release，因此会**立即创建 `v0.1.0`**。这是预期行为（首个可安装版本），不是意外。
4. 用 `curl -fsSL <raw install.sh URL> | sh` 在干净环境实测一次安装，再重跑一次验证更新路径幂等。
5. **回滚**：删除 `.github/workflows/release.yml` 即停止一切自动发布；已发出的 Release/tag 用 `gh release delete v<x> --cleanup-tag` 撤除。`install.sh` 留在仓库里不产生任何自动行为，可独立回滚。

注意：`install.sh` 的 raw URL 指向 `main` 分支，因此**脚本必须先合并进 `main` 才能被 README 里的命令下载到**——README 中的安装命令在合并前是无效链接，这是预期的时序，不是缺陷。

## Open Questions

- 触发分支最终确认为 `main`，还是要额外把 `master` 也列进 `on.push.branches`？当前实现只监听 `main`（仓库实际默认分支）。留待 `approval` 节点由人确认。
- 是否要在 PR 上也跑 `verify` job（`on.pull_request`）？本变更范围内不做，但 workflow 的 job 拆分已经为此留好了口子——后续只需加一个 `on` 触发条件。
