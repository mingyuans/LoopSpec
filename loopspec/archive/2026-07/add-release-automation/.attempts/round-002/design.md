> 第 2 轮。第 1 轮被 `security` gate 判 FAIL，4 项阻塞问题分别由 **D13**（令牌可见性边界）、**D14**（构建后端版本约束 + 特权 job 内的构建隔离）、**D8**（校验条目必须存在，改写）、**D3**（按契约显式列出待发布文件，改写）回应。第 1 轮的原文存于 `.attempts/round-001/`。

## Context

仓库当前没有 `.github/`、没有 CI、没有任何分发产物。`make build`（`uv build`）产出的 wheel/sdist 只留在本地 `dist/`，README 的 "Install" 教的是 `make install`（`uv sync` 建开发虚拟环境）。用户想用这个 CLI，必须 clone + 装 uv + sync。

约束与既有事实：

- 包是**纯 Python**（`requires-python >= 3.11`，hatchling 构建，无扩展模块），产出的 `py3-none-any` wheel 天然跨平台——不需要按平台分发二进制。
- wheel 通过 `[tool.hatch.build.targets.wheel.force-include]` 把仓库根的 `schemas/` 打进 `loopspec/builtin_schemas`，所以**必须走正规构建**（`uv build` 已覆盖）。
- 版本号有**两处**：`pyproject.toml` 的 `project.version` 与 `src/loopspec/__init__.py` 的 `__version__`（当前都是 `0.1.0`）。`loopspec version` 优先读 `importlib.metadata`，只在源码 checkout 下回退到 `__version__`——两者漂移不会让安装版报错，只会让源码版静默撒谎。
- `[build-system] requires = ["hatchling"]` 目前**没有任何版本约束**，构建后端在每次构建时从 PyPI 重新解析。
- 仓库默认分支是 `main`（`origin/HEAD -> origin/main`），需求原文说的 `master` 在本仓库不存在。
- 已有 `Makefile` 作为统一任务入口（`install`/`dev`/`test`/`lint`/`build`/`clean`），新增能力应挂在这里而不是另起脚本入口。

**信任边界**（security gate 的重点，先在此点明）：本变更引入两处新的信任边界，且**都不涉及 authn/authz 变更**。

1. **CI 内执行的代码**：第三方 GitHub Action、`pyproject.toml` 声明的构建后端、以及仓库自己的测试代码。凭据是自动注入的 `GITHUB_TOKEN`。这条边界的核心问题不是"谁能触发发布"（由 GitHub 的仓库权限模型承载），而是**令牌能被哪些代码看见**——见 D13、D14。
2. **用户机器上执行的脚本**：`curl ... | sh`，输入包括环境变量 `LOOPSPEC_VERSION` 与从 GitHub API 拿到的 `tag_name`，输出是往用户机器上装一个可执行文件。

## Goals / Non-Goals

**Goals:**

- 默认分支收到 push 时自动跑 lint + test + 构建，红了就红在 CI 里，不靠提交者的自觉。
- 版本号是新的时候自动创建 GitHub Release，附 wheel、sdist、`checksums.txt`；版本号没变则什么都不发，且**不算失败**。
- 用户能用一条命令完成安装，且**同一条命令**用于更新。
- 安装链路端到端可验证完整性：Release 里带 SHA256，脚本校验后才装；**校验不成立时必须失败，而不是"没校验到"就放过**。
- CI 侧不新增任何 secret；权限按 job 最小化；**令牌不暴露给任何执行仓库代码或第三方构建代码的步骤**。
- 本地能预演 CI 的可本地验证部分（`make release-dry-run`），不必"推上去看会不会红"。

**Non-Goals:**

- 不发布到 PyPI（需要账号与 trusted publisher 配置，留作后续变更）。
- 不做平台专属二进制打包（PyInstaller/Nuitka 等）——纯 Python wheel 已够。
- 不提供 `install.ps1`；Windows 用户在 README 里被指引直接用 `uv tool install`。
- 不自动 bump 版本号、不维护手写 changelog（release notes 用 GitHub 的 `--generate-notes`）。
- 不引入 Dependabot / renovate 来跟进 action 版本（本次只留注释说明如何手动更新）。
- 不在 PR 上跑这套工作流（本次只覆盖默认分支 push 与手动触发）。
- 不对安装时解析的**运行时依赖**做哈希固定（`uv tool install` 会从 PyPI 解析 `pydantic`/`typer`/... ——那需要 `--require-hashes` 级别的方案，超出本次范围；见 Risks）。

## Decisions

### D1 — 一个 workflow 文件，两个 job：`verify`（只读）→ `release`（可写）

`.github/workflows/release.yml` 顶层声明 `permissions: contents: read`，`verify` job 继承它跑版本校验 + lint + test + shell 静态检查 + 构建；`release` job 声明 `needs: verify` 并单独提升为 `permissions: contents: write`。

- **为什么不是单 job**：GitHub Actions 的 `permissions` 粒度是 job，单 job 意味着 lint/test 这些"执行仓库里任意代码"的步骤也带着 `contents: write` 跑。拆开后写权限只覆盖"判定 + 发布"这几步。
- **`release` job 重新构建，而不是用 artifact 传递**（第 1 轮已定，本轮复核后保留，理由见 D14）：跨 job 传产物要引入 `actions/upload-artifact` + `actions/download-artifact` 两个额外 action 依赖，而 `uv build` 对同一 commit 是确定性的、耗时以秒计。
- **替代方案**：两个独立 workflow 文件（`ci.yml` + `release.yml`）——被否，会重复 checkout/setup 且 `needs` 关系要靠 `workflow_run` 表达，复杂度更高。

### D2 — 发布判定：`gh release view v<version>` 存在即跳过

`release` job 第一步查 `v$VERSION` 这个 Release 是否已存在：存在 → 写一行 job summary（`skipped: v0.1.0 already released`）并正常结束；不存在 → 发布。

- **为什么以版本号而非 commit 为发布单位**：每次 push 都发会把 Release 列表刷成 commit 列表，版本号也就失去意义。抬 `version` 就是"我要发布"这个意图的唯一表达。
- **为什么查 Release 而不查 tag**：`gh release create` 会顺带创建 tag，所以 Release 存在 ⊇ tag 存在；查 Release 一次调用就够，也不需要 `fetch-tags`。
- **跳过必须是成功退出**：否则默认分支每个不带版本变更的 commit 都会亮红叉，CI 信号很快就被无视。
- **必须区分"明确不存在"与"查询本身失败"**：只有 `gh release view` 返回明确的"不存在"才走发布，只有明确的"已存在"才走跳过；其余错误（网络、5xx、权限）一律失败。

### D3 — 用 `gh release create`，且按命名契约**显式列出**待发布文件（第 2 轮改写）

`gh` 预装在 GitHub-hosted runner 上，一条命令同时完成"建 tag + 建 Release + 上传资产"。**不使用 `dist/*` 通配符**——上传前先按契约拼出三个确定的文件路径，逐个断言存在，缺任何一个即失败，然后把这三个路径显式传给 `gh`：

```
WHEEL="dist/loopspec-$VERSION-py3-none-any.whl"
SDIST="dist/loopspec-$VERSION.tar.gz"
for f in "$WHEEL" "$SDIST" checksums.txt; do [ -f "$f" ] || { echo "missing asset: $f" >&2; exit 1; }; done
gh release create "v$VERSION" "$WHEEL" "$SDIST" checksums.txt \
  --target "$GITHUB_SHA" --title "v$VERSION" --generate-notes
```

- **为什么不是 `dist/*`**（第 1 轮的写法，被 security gate 判为阻塞）：通配符把"发布哪些文件"的决定权交给构建目录的实际内容。spec 的资产契约是"上传**且仅上传**"三个文件，通配符表达不出这个"仅"；任何意外落入 `dist/` 的东西——包括被篡改的构建后端刻意多写的文件——都会被公开发布。显式列出把发布内容与契约变成一一对应，顺带还免费得到"构建产物名与预期版本号不符"这个断言（例如版本号读取与构建产物名不一致时会直接失败，而不是发出一个名字对不上的资产）。
- **替代方案** `softprops/action-gh-release`：更声明式，但是第三方 action，等于为了省几行 YAML 引入一个新的供应链依赖。本变更的目标之一就是压缩这个面。
- 副作用：tag 由 `gh` 用 `--target $GITHUB_SHA` 创建，不需要 `git push --tags`，也不需要为 git 配用户身份——这一点与 D13 的 `persist-credentials: false` 互补：整条流程不依赖 git 的推送凭据。

### D4 — 第三方 action 一律 pin 到 commit SHA

只用两个 action，都按 `<action>@<40位 SHA> # <tag>` 的形式写：

- `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1` # v7.0.1
- `astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9` # v9.0.0

（两个 SHA 已通过 `gh api repos/<repo>/git/ref/tags/<tag>` 核对为对应 tag 指向的 commit。）

- **为什么 pin SHA 而不是 `@v7`**：可变 tag 可以被重新指向，SHA 不能。CI 里执行的第三方代码是最直接的供应链入口。
- **代价**：SHA 不会自动跟进上游修复。缓解：行尾注释保留人类可读的 tag，本文件记录更新方式（重跑 `gh api repos/<repo>/git/ref/tags/<tag>` 取新 SHA）。
- `setup-uv` 选自 Astral 官方（uv 的作者），而非社区 action；开启其内建 cache 以缩短 `uv sync` 时间。

### D5 — 版本号的单一读取入口：`scripts/check_version.py`

新增一个标准库脚本（`tomllib` 是 3.11+ 内建，无新依赖）：读 `pyproject.toml` 的 `project.version`，读 `src/loopspec/__init__.py` 的 `__version__`，两者一致且格式合法则把版本号打到 stdout 并以 0 退出，否则打错误到 stderr 并以非零退出。

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
3. 用版本号拼出两个确定的 URL：
   - `.../releases/download/v$V/loopspec-$V-py3-none-any.whl`
   - `.../releases/download/v$V/checksums.txt`

- **为什么不依赖 `jq`**：`jq` 不是 macOS/精简容器的默认组件。只抽一个形如 `"tag_name": "v0.1.0"` 的字段，用 `sed` 足够，且抽出的结果立刻过 D6 的正则闸门——**解析宽松、校验严格**。抽取失败得到空串同样会被正则拒绝。
- **为什么不用 `/releases/latest/download/<file>` 重定向**：那个路径要求文件名已知，而文件名含版本号，绕不开先拿版本号这一步。
- **为什么只装 wheel 不装 sdist**：wheel 是 `py3-none-any`，无需在用户机器上跑构建后端。sdist 仍然发布，供需要从源码构建的场景使用。
- Release 资产的文件名由 hatchling 的标准命名规则决定（`loopspec-<version>-py3-none-any.whl` / `loopspec-<version>.tar.gz`），这构成 CI 与脚本之间的**命名契约**，写进 spec，两侧实现都以它为准（D3 的显式文件列表、D7 的 URL 拼接都是它的消费者）。

### D8 — 完整性校验：条目必须存在，校验必须实际发生（第 2 轮改写）

wheel 与 `checksums.txt` 都下到 `mktemp -d` 的目录。校验分成三个**都必须成功**的步骤，任一失败即非零退出：

1. **定位条目**：从 `checksums.txt` 中过滤出文件名恰好等于目标 wheel 文件名的行，写入一个单行的 `wheel.sha256`。
2. **断言恰好一条**：该过滤结果的行数必须**等于 1**。为 0（条目缺失、文件是错误页面、文件为空）或大于 1（重复/歧义条目）都必须失败。
3. **执行校验**：把这个单行文件交给 `sha256sum -c` 或 `shasum -a 256 -c`（按 `command -v` 探测，Linux/macOS 各覆盖其一），依其退出码判定。

- **为什么第 1 轮的写法是漏洞**（security gate 判为阻塞）：原设计只说"用 `sha256sum -c checksums.txt` 校验 wheel"。但 `checksums.txt` 按契约含 wheel + sdist 两行，而脚本只下载 wheel，直接 `-c` 会因缺失 sdist 而失败——场景与契约自相矛盾。实现者绕过它只有两条不安全的路：`--ignore-missing`（macOS 的 `shasum` 是 Perl 脚本，不支持该选项，跨平台直接坏掉；且"没有任何文件被校验"时各实现行为不一致），或 `grep` 抠行后比对（`grep` 匹配不到时得到空串，不显式判空就成了"空 vs 空"的假通过）。**"没校验到"必须等于"校验失败"**，这就是把"恰好一条"提升为独立断言的原因。
- **精确匹配而非子串匹配**：过滤时比对的是行内的文件名字段与目标 wheel 文件名**相等**，不是 `grep <version>` 这类子串匹配——否则 `0.1.0` 会同时命中 `0.1.0` 与 `0.1.0.post1`。
- **为什么不让 `uv tool install <URL>` 直接从远端装**：那样 checksum 校验就成了摆设——校验的字节和安装的字节不是同一次下载。
- **两种校验工具都不存在时：中止，退出码非零。** 明确不提供"跳过校验继续安装"的降级路径，也不提供跳过校验的开关。这是本变更里最不该被"便利性"侵蚀的一条。
- **诚实的边界**：`checksums.txt` 与 wheel 来自同一个 Release、同一台主机、同一条 TLS 通道，且由同一个 job 现算现发。因此它保证的是"这两个文件是同一次发布的、传输过程中没有一方被单独替换"，**不是**"发布者可信"，也不是能对抗"能改写整个 Release 的攻击者"。真正承载来源可信的是 GitHub 的仓库权限模型与 TLS。spec 里如实写这个边界，不过度承诺。

### D9 — 安装后端：`uv tool install --force` 优先，回退 `pipx install --force`，都没有则失败

- `--force` 让"安装"和"更新"是同一条路径：已装则覆盖到目标版本，未装则新装。脚本因此天然幂等，README 里"更新"和"安装"是同一条命令。
- **不回退到 `pip install --user`**：会污染用户的 default Python 环境，且和 CLI 工具应有的隔离语义（uv tool / pipx 都建独立环境）相悖。
- **绝不使用 `sudo`**、绝不写系统目录。脚本没有任何提权路径。
- 两者都缺 → 打印 uv 的官方安装命令并以非零码退出。**不**自动去装 uv：那是在用户没同意的情况下扩大安装范围。

### D10 — `install.sh` 的执行安全形态

- `#!/bin/sh` + `set -eu`（不写 `pipefail`——POSIX sh 没有；管道处一律用显式返回值判断）。目标是 dash/bash/zsh 都能跑，不额外要求 bash。
- 全部逻辑包在 `main() { ... }` 里，文件末尾才 `main "$@"`。这样 `curl | sh` 遇到连接中断、只收到半个脚本时，`main` 不会被调用，不会执行"半个安装"。
- `trap 'rm -rf "$tmp"' EXIT INT TERM` 清理临时目录；临时目录由 `mktemp -d` 创建，不用可预测路径（避免 `/tmp/loopspec` 这类被抢占的固定名）。
- 所有下载：`curl -fsSL --proto '=https' --tlsv1.2`——强制只走 https，杜绝被重定向到 http。
- **无 `eval`、无 `curl | sh` 的二次嵌套、不下载并执行任何除目标 wheel 之外的东西。**
- 静态检查：`shellcheck` + `sh -n`，在 CI 中**都是硬要求**；本地 `make release-dry-run` 在 `shellcheck` 缺失时跳过它并提示（本地缺工具不该阻塞开发者）。

### D11 — PATH 未就绪时警告但不失败

安装成功后执行 `loopspec version` 自检。若 `command -v loopspec` 找不到，打印 `~/.local/bin` 加入 PATH 的提示（uv 场景另提 `uv tool update-shell`），**退出码仍为 0**——包确实装好了，问题在当前 shell 的 PATH，报失败会误导。

### D12 — README 结构：用户视角的 Install 与贡献者视角的 Development 分离

现有 README 把 `make install` 放在 "Install" 下，那实际是开发环境搭建。改为：

- **Install**：一行式脚本（含"先下载再审阅"的两步替代命令）、`uv tool install` / `pipx` 手动路径、更新（同一条命令）、卸载、Windows 说明。
- **Releases**：说明发布是版本号驱动的、Release 里有什么资产、以及**仓库设置前置条件**（`Settings → Actions → General → Workflow permissions` 需允许 `Read and write`，否则 `gh release create` 会 403）。
- **Development**：保留 `make install` / `test` / `lint` / `build` / `clean`，新增 `release-dry-run`。

### D13 — 令牌可见性边界：checkout 不持久化凭据，令牌只绑定在调用 `gh` 的 step 上（第 2 轮新增）

这是对 security gate 第 1 项阻塞问题的回应。规则有三条，缺一不可：

1. **两个 job 的 `actions/checkout` 都显式 `with: persist-credentials: false`。** 默认行为会把 `GITHUB_TOKEN` 以 `http.extraheader` 的形式写进 `.git/config`——那是一个工作目录里的普通文件，任何在同一 job 里执行的代码都能读。
2. **令牌只以 step 级 `env: GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}` 注入调用 `gh` 的那几个 step**，SHALL NOT 出现在 workflow 级或 job 级 `env`。
3. **任何执行仓库代码或第三方代码的 step 都不得注入令牌**：`pytest`、`ruff`、`mypy`、`uv sync`、`uv build`、`shellcheck` 全部在无令牌的环境变量下运行。

- **为什么这条必须写成显式决策**：第 1 轮的「凭据与权限最小化」只约束了"不写入日志"和"按 job 分权限"，而 `.git/config` 与 job 级 `env` 都不是日志，两条既有约束都覆盖不到。`release` job 持有的是 `contents: write` 令牌，被读走即可改写仓库——这是本变更里影响最大的单点。
- **与 D3 的互补**：因为发布走 `gh` 而不是 `git push`，整条流程本就不需要 git 的推送凭据，`persist-credentials: false` 不会损失任何功能。
- **可验证性**：这三条都能靠读 workflow 文件断言（每个 `uses: actions/checkout` 后必须有 `persist-credentials: false`；`GH_TOKEN`/`GITHUB_TOKEN` 只能出现在 `gh` step 的 `env` 下），因此写成 spec 需求是可检查的，而不是一句愿望。

### D14 — 构建后端的版本约束，以及在特权 job 内构建的隔离条件（第 2 轮新增）

这是对 security gate 第 2 项阻塞问题的回应。**结论：保留 `release` job 自己构建（不推翻 D1），但补两条约束。**

1. **给构建后端加版本约束**：`pyproject.toml` 的 `[build-system] requires` 从裸 `"hatchling"` 改为 `"hatchling>=1.31,<2"`（1.31.0 是当前 PyPI 上的版本，也是本变更验证构建所用的版本；上界排除下一个大版本）。
2. **构建 step 不得看到令牌**（即 D13 第 3 条）：`uv build` 会执行构建后端的钩子代码，该 step 的环境中不注入任何令牌，工作目录的 `.git/config` 中也没有凭据（D13 第 1 条）。因此即使构建后端被投毒，它在这个 job 里也拿不到可用于改写仓库的凭据。
3. **构建产物不被通配符发布**（即 D3）：被投毒的构建后端即使往 `dist/` 里多写文件，也不会被发布——只有契约里的三个文件名会被上传。

- **为什么不改成从 `verify` 传产物**（gate 提出的另一条路）：那样只是把同一段构建后端代码搬到另一个 job 执行，问题的实质（执行第三方构建代码）没有消失，却要多引入两个 action 依赖，等于用一个新的供应链面去换一个没被真正消除的风险。相比之下，"令牌对构建 step 不可见 + 发布内容按契约白名单"是对因下药。
- **诚实的残余风险**：`[build-system] requires` 的版本范围**不是**哈希固定——`pyproject.toml` 无法表达哈希，`uv build` 仍会在范围内解析到最新的补丁版。这缩小了窗口（排除了大版本跳跃与被撤回后重新占位的旧版本），但没有消除"构建时解析第三方代码"这件事。这条残余风险在此显式记录并接受；彻底解决需要在受控环境预装固定版本的构建后端（例如 `uv build --no-build-isolation` 配合锁定的构建依赖），代价与本变更的规模不匹配，留作后续变更。
- **副作用（正向）**：加了版本约束后，本地 `make build` 与 CI 构建解析到的后端版本范围一致，减少"本地能构、CI 构不出"的偶发差异。

## Risks / Trade-offs

- **[忘记 bump 版本号 → 以为发了其实没发]** → `release` job 在跳过时往 job summary 写明 `skipped: vX.Y.Z already released`，并在 README 的 Releases 一节写清"抬版本号才会发布"。
- **[仓库 Actions 权限没开 `Read and write` → 发布 403]** → 首次上线必踩，写进 README 前置条件；`release` job 的失败信息本身也指向权限设置。
- **[`curl | sh` 的固有信任问题]** → 无法根除，只能缩小：README 同时给出"下载 → 审阅 → 执行"的两步命令和完全手动的 `uv tool install` 路径；脚本本身不提权、不写系统目录、只装经 SHA256 校验的 wheel。
- **[构建时解析第三方构建后端（残余）]** → 见 D14：加版本上下界缩小窗口，令牌对构建 step 不可见，发布走文件名白名单。不做哈希固定，显式接受。
- **[安装时解析的运行时依赖未做哈希固定]** → `uv tool install <wheel>` 会从 PyPI 解析 `pydantic`/`typer`/`rich`/`pyyaml`/`questionary`。本变更只保证"你装到的 loopspec wheel 是我们发的那个"，不保证其依赖树。这与整个 Python 生态的默认信任模型一致，spec 里不做超出实现的承诺；若将来需要，方向是发布带哈希的约束文件。
- **[pin 到 SHA 的 action 不会自动更新，可能长期停在有已知问题的版本]** → 行尾注释保留 tag，本文件记录用 `gh api repos/<repo>/git/ref/tags/<tag>` 取新 SHA 的方法；后续可另起变更引入 Dependabot。
- **[`verify` 与 `release` 各构建一次，若构建非确定性则"校验的"与"发布的"不是同一份]** → hatchling 对同一 commit 的输出是确定的；`checksums.txt` 由 `release` job 对**自己**产出的文件计算，发布的资产与其校验值必然自洽。残余风险仅是"verify 通过而 release 构建失败"，那会红在 CI 里，不会发出坏产物。
- **[GitHub API 未认证时有 60 次/小时/IP 的速率限制]** → 只在未指定 `LOOPSPEC_VERSION` 时调一次；被限流时 curl 失败，脚本报错并提示可用 `LOOPSPEC_VERSION=x.y.z` 跳过 API。
- **[`--generate-notes` 的 release notes 质量取决于 commit 信息]** → 接受。本变更不引入 changelog 维护流程。
- **[跳过发布用"成功退出"表达，可能掩盖真实的发布故障]** → 跳过与失败在 job summary 中文案不同，且跳过只在 `gh release view` **明确返回已存在**时发生；查询本身出错走失败路径（D2）。

## Migration Plan

1. 新增 `.github/workflows/release.yml`、`install.sh`、`scripts/check_version.py`、`tests/test_check_version.py`；改 `pyproject.toml`（`[build-system] requires` 加版本约束）、`Makefile`、`README.md`。
2. 本地 `make release-dry-run` + `make lint` + `make test` 全绿；`uv build` 在加了版本约束后仍能构建（验证 D14 的约束没写错）。
3. 合并到 `main` 后工作流首次运行：当前 `0.1.0` 尚无 Release，因此会**立即创建 `v0.1.0`**。这是预期行为（首个可安装版本），不是意外。
4. 用 `curl -fsSL <raw install.sh URL> | sh` 在干净环境实测一次安装，再重跑一次验证更新路径幂等；另故意改坏本地 `checksums.txt` 验证校验会失败（确认 D8 的断言真的生效，而不是"看起来生效"）。
5. **回滚**：删除 `.github/workflows/release.yml` 即停止一切自动发布；已发出的 Release/tag 用 `gh release delete v<x> --cleanup-tag` 撤除。`install.sh` 留在仓库里不产生任何自动行为，可独立回滚。`[build-system]` 的版本约束可单独还原，与其余部分无耦合。

注意：`install.sh` 的 raw URL 指向 `main` 分支，因此**脚本必须先合并进 `main` 才能被 README 里的命令下载到**——README 中的安装命令在合并前是无效链接，这是预期的时序，不是缺陷。

## Open Questions

- 触发分支最终确认为 `main`，还是要额外把 `master` 也列进 `on.push.branches`？当前实现只监听 `main`（仓库实际默认分支）。留待 `approval` 节点由人确认。
- 是否要在 PR 上也跑 `verify` job（`on.pull_request`）？本变更范围内不做。**若将来加上，必须重新评估 fork PR 的执行面**——届时 `pull_request` 事件下的令牌是只读的，但 D13 的三条约束仍需保持，且不得改用 `pull_request_target`。
