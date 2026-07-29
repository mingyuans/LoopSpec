> 第 3 轮。第 1 轮被 `security` gate 判 FAIL；第 2 轮通过 `security` 但在 `approval` 被人要求修改——发布改为 **tag 驱动**，发布版本号直接取自 tag 名。
>
> 本轮改动：**D2**（触发与版本号来源，整条重写）、**D3**（发布命令的版本号来源）、**D5**（`check_version.py` 从"版本号来源"改为"三方一致性校验器"）、**D12**（README 的发布流程）为重写；**D15**（被打 tag 的 commit 必须可从默认分支到达）、**D16**（Release 已存在 → 失败而非跳过）、**D17**（`workflow_dispatch` 语义）为新增。
>
> **D4、D6~D11、D13、D14 未受本次裁决影响，原样保留**——其中 D13（令牌可见性边界）、D14（构建后端约束）、D8（完整性校验三步断言）、D3 的资产白名单是第 1 轮 `security` FAIL 的修复成果，不得在本轮被稀释。第 1、2 轮原文分别存于 `.attempts/round-001/`、`.attempts/round-002/`。

## Context

仓库当前没有 `.github/`、没有 CI、没有任何分发产物。`make build`（`uv build`）产出的 wheel/sdist 只留在本地 `dist/`，README 的 "Install" 教的是 `make install`（`uv sync` 建开发虚拟环境）。用户想用这个 CLI，必须 clone + 装 uv + sync。

约束与既有事实：

- 包是**纯 Python**（`requires-python >= 3.11`，hatchling 构建，无扩展模块），产出的 `py3-none-any` wheel 天然跨平台——不需要按平台分发二进制。
- wheel 通过 `[tool.hatch.build.targets.wheel.force-include]` 把仓库根的 `schemas/` 打进 `loopspec/builtin_schemas`，所以**必须走正规构建**（`uv build` 已覆盖）。
- 版本号现在有**三处**，这是本轮设计的核心张力：
  1. **git tag 名**（如 `v0.1.0`）——按本轮裁决，它是**发布版本号的权威来源**；
  2. `pyproject.toml` 的 `project.version`——它决定 **wheel/sdist 的文件名**，构建产物名绕不开它；
  3. `src/loopspec/__init__.py` 的 `__version__`——`loopspec version` 在源码 checkout 下的 fallback。

  三者不一致的后果是具体而非抽象的：tag 打成 `v0.2.0` 而 `pyproject.toml` 还是 `0.1.0` 时，构建产出的是 `loopspec-0.1.0-py3-none-any.whl`，而 Release 叫 `v0.2.0`——用户下载到的文件名与版本号对不上。
- `[build-system] requires = ["hatchling"]` 目前**没有任何版本约束**，构建后端在每次构建时从 PyPI 重新解析。
- 仓库默认分支是 `main`（`origin/HEAD -> origin/main`）。裁决原话说的是"master 分支提交 tag"，本仓库没有 `master`，故默认分支按 `main` 处理。
- **git 的 tag 不属于任何分支**——"在 master 分支上打 tag"在 git 里没有直接对应的概念，只能表达为"被打 tag 的 commit 可从默认分支到达"。见 D15。
- 已有 `Makefile` 作为统一任务入口（`install`/`dev`/`test`/`lint`/`build`/`clean`）。

**信任边界**（security gate 的重点，先在此点明）：

1. **CI 内执行的代码**：第三方 GitHub Action、`pyproject.toml` 声明的构建后端、仓库自己的测试代码。凭据是自动注入的 `GITHUB_TOKEN`。核心问题是**令牌能被哪些代码看见**（D13、D14）。
2. **tag 名是新引入的外部输入**（本轮新增）：它流入 Release 名、构建产物名断言与资产路径。`on.push.tags` 的 glob 过滤**不是**严格校验（glob 无法表达"三段数字"），因此 tag 名必须过与 `LOOPSPEC_VERSION` 相同的正则闸门（D6）。
3. **"谁能推 tag 就能发布"是本轮引入的新授权假设**（见 Risks）。
4. **用户机器上执行的脚本**：`curl ... | sh`，输入是 `LOOPSPEC_VERSION` 与 GitHub API 返回的 `tag_name`。

## Goals / Non-Goals

**Goals:**

- **发布是显式动作**：只有推送 `v<version>` 形式的 tag 才创建 Release；日常 commit 不会产生任何 Release。
- **持续校验不因此丢失**：默认分支的普通 push 仍然跑 lint + test + 构建校验（只是不发布）。
- 发布版本号取自 tag 名；三处版本号不一致时**明确失败**，不发出名不副实的产物。
- 用户能用一条命令完成安装，且**同一条命令**用于更新。
- 安装链路端到端可验证完整性：Release 里带 SHA256，脚本校验后才装；**校验不成立时必须失败**，而不是"没校验到"就放过。
- CI 侧不新增任何 secret；权限按 job 最小化；令牌不暴露给任何执行仓库代码或第三方构建代码的步骤。
- 本地能预演 CI 的可本地验证部分（`make release-dry-run`），包括可选地预演"某个 tag 名是否与两处版本号一致"。

**Non-Goals:**

- 不发布到 PyPI（需要账号与 trusted publisher 配置，留作后续变更）。
- 不做平台专属二进制打包——纯 Python wheel 已够。
- 不提供 `install.ps1`；Windows 用户在 README 里被指引直接用 `uv tool install`。
- 不自动打 tag、不自动 bump 版本号、不维护手写 changelog（release notes 用 `--generate-notes`）。
- 不引入 Dependabot / renovate 跟进 action 版本。
- 不在 PR 上跑这套工作流。
- 不对安装时解析的**运行时依赖**做哈希固定（见 Risks）。
- **不引入 `hatch-vcs` 一类从 tag 派生版本号的方案**（见 D5 的替代方案讨论）。

## Decisions

### D1 — 一个 workflow 文件，两个 job：`verify`（只读）→ `release`（可写，仅在 tag 上运行）

`.github/workflows/release.yml` 顶层声明 `permissions: contents: read`。`verify` job 在**所有**触发下运行；`release` job 声明 `needs: verify`、单独提升为 `permissions: contents: write`，并用 ref 条件把自己限制在 tag 上：

```yaml
release:
  needs: verify
  if: startsWith(github.ref, 'refs/tags/v')
  permissions:
    contents: write
```

- **为什么不是单 job**：GitHub Actions 的 `permissions` 粒度是 job。单 job 意味着 lint/test 这些"执行仓库里任意代码"的步骤也带着 `contents: write` 跑。
- **为什么 `release` 用 ref 条件而不是拆成第二个 workflow 文件**：同一份 `verify` 定义要同时服务"分支 push 校验"与"tag 发布前校验"，拆文件就得复制一遍。ref 条件一行解决，且天然覆盖"在 tag 上手动 dispatch"这种情形（D17）。
- **`release` job 重新构建，而不是用 artifact 传递**（沿用前两轮结论，理由见 D14）：跨 job 传产物要引入 `actions/upload-artifact` + `actions/download-artifact` 两个额外 action 依赖，而 `uv build` 对同一 commit 是确定性的、耗时以秒计。

### D2 — 触发与版本号来源：tag 驱动（第 3 轮整条重写）

```yaml
on:
  push:
    branches: [main]                        # 只跑 verify
    tags: ['v[0-9]+.[0-9]+.[0-9]+*']        # 跑 verify + release
  workflow_dispatch:
```

发布路径的版本号 SHALL 取自 tag 名：`GITHUB_REF_NAME` 去掉 `v` 前缀（tag push 时 `GITHUB_REF_NAME` 就是 tag 名），随后过 D6 的正则闸门，再交给 D5 做三方一致性校验。

- **为什么保留 `branches: [main]`**：本轮裁决改的是**发布**的触发方式，不是"要不要持续校验"。若只留 `on.push.tags`，`main` 上的普通 commit 将完全没有 CI——那是相对第 2 轮方案的功能退化，而不是裁决要求的东西。两个触发器共用同一个 `verify` job，`release` 靠 D1 的 ref 条件缺席。
- **为什么 tag 模式写成 `v[0-9]+.[0-9]+.[0-9]+*` 而不是 `v*`**：`v*` 会把 `vendor-snapshot` 这类 tag 也拖进发布路径。收窄 glob 是第一道闸门，但它**不是**校验——glob 里的 `+` 在 GitHub 的 ref 过滤语法中并非正则量词，且尾部 `*` 放行任意后缀。真正的把关是 D6 的正则。这一点必须写清楚，否则容易误以为 `on.push.tags` 已经做了校验。
- **为什么不再需要"读 `pyproject.toml` 决定要不要发"**：tag 的存在本身就是发布意图的表达，不需要再去推断。这同时消掉了旧方案里"忘记 bump 版本号 → 以为发了其实没发"这一整类问题。
- **代价**：发布多了一个手工步骤（打 tag 并推送）。这是裁决明确选择的取舍——把发布从"改一行版本号的副作用"变成一个独立、可审计、可被 GitHub tag 保护规则管控的动作。

### D3 — 用 `gh release create`，版本号取自 tag，并按命名契约**显式列出**待发布文件

`gh` 预装在 GitHub-hosted runner 上，一条命令同时完成"建 Release + 上传资产"。**不使用 `dist/*` 通配符**——上传前先按契约拼出三个确定的文件路径，逐个断言存在，缺任何一个即失败：

```
VERSION="${GITHUB_REF_NAME#v}"          # 已过 D6 正则闸门与 D5 三方校验
WHEEL="dist/loopspec-$VERSION-py3-none-any.whl"
SDIST="dist/loopspec-$VERSION.tar.gz"
for f in "$WHEEL" "$SDIST" checksums.txt; do
  [ -f "$f" ] || { echo "missing asset: $f" >&2; exit 1; }
done
gh release create "$GITHUB_REF_NAME" "$WHEEL" "$SDIST" checksums.txt \
  --title "$GITHUB_REF_NAME" --generate-notes
```

- **与前两轮的差别**：tag 已经存在（是它触发了本次运行），所以 `gh release create` 不再需要 `--target $GITHUB_SHA` 去创建 tag——它是在为一个既有 tag 建 Release。这少了一处"tag 指向哪个 commit"的歧义。
- **为什么不是 `dist/*`**（第 1 轮的写法，被 security gate 判为阻塞）：通配符把"发布哪些文件"的决定权交给构建目录的实际内容。spec 的资产契约是"上传**且仅上传**"三个文件，通配符表达不出这个"仅"；任何意外落入 `dist/` 的东西——包括被篡改的构建后端刻意多写的文件——都会被公开发布。
- **显式列出的附带收益**：它就是"tag 名与构建产物名一致"的最后一道断言。若 D5 因任何原因被绕过，这里也会因为 `dist/loopspec-<tag版本>-...whl` 不存在而失败——**失败方向是关闭**（报错，而不是发出一个名字对不上的资产）。
- **替代方案** `softprops/action-gh-release`：更声明式，但是第三方 action，等于为了省几行 YAML 引入一个新的供应链依赖。

### D4 — 第三方 action 一律 pin 到 commit SHA

只用两个 action，都按 `<action>@<40位 SHA> # <tag>` 的形式写：

- `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1` # v7.0.1
- `astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9` # v9.0.0

（两个 SHA 已通过 `gh api repos/<repo>/git/ref/tags/<tag>` 核对为对应 tag 指向的 commit。）

- **为什么 pin SHA 而不是 `@v7`**：可变 tag 可以被重新指向，SHA 不能。CI 里执行的第三方代码是最直接的供应链入口。
- **代价**：SHA 不会自动跟进上游修复。缓解：行尾注释保留人类可读的 tag，本文件记录更新方式（重跑 `gh api repos/<repo>/git/ref/tags/<tag>` 取新 SHA）。
- `setup-uv` 选自 Astral 官方（uv 的作者），而非社区 action；开启其内建 cache 以缩短 `uv sync` 时间。

### D5 — `scripts/check_version.py` 从"版本号来源"改为"三方一致性校验器"（第 3 轮重写）

脚本仍然只用标准库（`tomllib` 读 `pyproject.toml`、`ast` 解析 `__init__.py`，不 import 该包），但职责变了：

- **无参调用**：校验 `pyproject.toml` 与 `__init__.py` 两处一致且格式合法，把版本号打到 stdout，以 0 退出。用于 `verify` job（两种触发下都跑）与 `make release-dry-run`。
- **`--expect <version>` 调用**：在上述校验之外，追加断言两处都等于 `<version>`（即 tag 名去掉 `v` 后的值）。任一不等即把三处实际值打到 stderr 并非零退出。用于 `release` job。

- **为什么"版本号读 tag"并不能免掉这个校验**：wheel/sdist 的文件名由 `pyproject.toml` 的 `version` 决定，不是由 tag 决定。tag `v0.2.0` 配上 `pyproject.toml` 里的 `0.1.0`，构建出来就是 `loopspec-0.1.0-py3-none-any.whl`——要么发布失败（被 D3 的存在性断言拦下），要么发出一个文件名与 Release 版本号矛盾的资产。把它拦在构建之前，报错信息比"资产文件不存在"清楚得多。
- **单一入口仍然成立**：`verify` job、`release` job、`make release-dry-run` 共用这一个脚本，只是传参不同，避免"CI 用 grep、Makefile 用 sed"的多份实现漂移。
- **替代方案：`hatch-vcs` 一类从 git tag 派生版本号的方案** —— 被否。它能真正做到"版本号只有 tag 一个来源"，代价是：① 新增一个构建期依赖（与 D14 想收缩的构建后端信任面方向相反）；② 会改变 `loopspec version` 在源码 checkout 下的 fallback 语义（现在有意保留 `__version__` 作为 fallback，改为 vcs 派生后，没有 tag 的 checkout 会得到 `0.1.dev…+g<sha>` 一类值）；③ sdist 与 git 元数据的耦合会让"从 sdist 再构建"这条路多一个坑。本变更的目标是把分发链路补上，不是重构版本号方案。**这条留作后续变更**，本轮用"tag 权威 + CI 强制三方一致"达到等价的正确性保证。

### D6 — 版本号与 tag 名的格式校验（输入校验，三处都做）

同一条正则贯穿全链路：

```
^[0-9]+\.[0-9]+\.[0-9]+([._-]?(a|b|rc|alpha|beta|dev|post)[0-9]+)?$
```

校验对象：

- **tag 名**（本轮新增）：`GITHUB_REF_NAME` 去掉 `v` 前缀后的值，在被拼进 Release 名、文件路径或任何命令参数**之前**校验。
- `pyproject.toml` 的 `project.version`（由 `check_version.py` 校验）。
- 客户端的 `LOOPSPEC_VERSION`，以及 `install.sh` 从 GitHub API 响应里提取出的 `tag_name`。

- **为什么 tag 名必须校验**：它是外部输入。`on.push.tags` 的 glob 收窄了一部分，但 glob 表达不了"三段数字"，尾部 `*` 也放行任意后缀。校验前它是"一段将被拼进文件路径与命令参数的字符串"；校验后它只可能是 `[0-9a-z._-]` 的子集。
- **为什么 API 返回值也要校验**：同理——未校验就拼接，等于把 `../` 或 shell 元字符的处置权交给上游响应。

### D7 — `install.sh` 的产物定位：先解析 `tag_name`，再拼固定命名的 URL

1. 若 `LOOPSPEC_VERSION` 已给 → 校验格式，直接用，**不调 API**。
2. 否则 `GET https://api.github.com/repos/mingyuans/LoopSpec/releases/latest`，从响应里抽 `"tag_name": "vX.Y.Z"`，剥掉 `v` 前缀 → 校验格式。
3. 用版本号拼出两个确定的 URL：
   - `.../releases/download/v$V/loopspec-$V-py3-none-any.whl`
   - `.../releases/download/v$V/checksums.txt`

- **为什么不依赖 `jq`**：`jq` 不是 macOS/精简容器的默认组件。只抽一个形如 `"tag_name": "v0.1.0"` 的字段，用 `sed` 足够，且抽出的结果立刻过 D6 的正则闸门——**解析宽松、校验严格**。抽取失败得到空串同样会被拒。
- **为什么不用 `/releases/latest/download/<file>` 重定向**：那个路径要求文件名已知，而文件名含版本号，绕不开先拿版本号这一步。
- **为什么只装 wheel 不装 sdist**：wheel 是 `py3-none-any`，无需在用户机器上跑构建后端。sdist 仍然发布，供需要从源码构建的场景使用。
- 资产文件名由 hatchling 的标准命名规则决定（`loopspec-<version>-py3-none-any.whl` / `loopspec-<version>.tar.gz`），这构成 CI 与脚本之间的**命名契约**，D3 的显式文件列表与 D7 的 URL 拼接都是它的消费者。

### D8 — 完整性校验：条目必须存在，校验必须实际发生

wheel 与 `checksums.txt` 都下到 `mktemp -d` 的目录。校验分成三个**都必须成功**的步骤，任一失败即非零退出：

1. **定位条目**：从 `checksums.txt` 中过滤出文件名字段**恰好等于**目标 wheel 基名的行，写入一个单行文件。
2. **断言恰好一条**：该过滤结果的行数必须**等于 1**。为 0（条目缺失、下载到的是错误页面、文件为空）或大于 1（重复/歧义条目）都必须失败。
3. **执行校验**：把这个单行文件交给 `sha256sum -c` 或 `shasum -a 256 -c`（按 `command -v` 探测），依其退出码判定。

- **为什么把"恰好一条"提升为独立断言**（第 1 轮 security FAIL 的修复，本轮原样保留）：只说"用 `sha256sum -c checksums.txt` 校验"会逼出两条不安全的实现——`--ignore-missing`（macOS 的 `shasum` 是 Perl 脚本，不支持该选项；且"零个文件被校验"时各实现行为不一致），或 `grep` 抠行后比对（匹配不到时得到空串，不显式判空就成了"空 vs 空"的假通过）。**"没校验到"必须等于"校验失败"。**
- **精确匹配而非子串匹配**：比对的是行内文件名字段与目标 wheel 基名**相等**，不是 `grep <version>` 这类子串匹配——否则 `0.1.0` 会同时命中 `0.1.0` 与 `0.1.0.post1`。
- **为什么不让 `uv tool install <URL>` 直接从远端装**：那样校验的字节和安装的字节不是同一次下载，校验成了摆设。
- **两种校验工具都不存在时：中止，退出码非零。** 不提供跳过校验的降级路径，也不提供开关。这是本变更里最不该被"便利性"侵蚀的一条。
- **诚实的边界**：`checksums.txt` 与 wheel 来自同一个 Release、同一条 TLS 通道，由同一个 job 现算现发。它保证的是"两个文件是同一次发布的、传输中没有一方被单独替换"，**不是**"发布者可信"，也不能对抗"能改写整个 Release 的攻击者"。承载来源可信的是 GitHub 的权限模型与 TLS。

### D9 — 安装后端：`uv tool install --force` 优先，回退 `pipx install --force`，都没有则失败

- `--force` 让"安装"和"更新"是同一条路径：已装则覆盖到目标版本，未装则新装。脚本因此天然幂等。
- **不回退到 `pip install --user`**：会污染用户的 default Python 环境，与 CLI 工具应有的隔离语义相悖。
- **绝不使用 `sudo`**、绝不写系统目录。
- 两者都缺 → 打印 uv 的官方安装命令并以非零码退出。**不**自动去装 uv：那是在用户没同意的情况下扩大安装范围。

### D10 — `install.sh` 的执行安全形态

- `#!/bin/sh` + `set -eu`（不写 `pipefail`——POSIX sh 没有；管道处用显式返回值判断）。dash/bash/zsh 都能跑。
- 全部逻辑包在 `main() { ... }` 里，文件末尾才 `main "$@"`。`curl | sh` 遇到连接中断、只收到半个脚本时，`main` 不会被调用。
- `trap 'rm -rf "$tmp"' EXIT INT TERM` 清理临时目录；临时目录由 `mktemp -d` 创建，不用可预测路径。
- 所有下载：`curl -fsSL --proto '=https' --tlsv1.2`——强制只走 https，杜绝被重定向到 http。
- **无 `eval`、无嵌套的 `curl | sh`、不下载并执行除目标 wheel 之外的任何东西。**
- 静态检查：`shellcheck` + `sh -n` 在 CI 中**都是硬要求**；本地 `make release-dry-run` 在 `shellcheck` 缺失时跳过它并提示。

### D11 — PATH 未就绪时警告但不失败

安装成功后执行 `loopspec version` 自检。若 `command -v loopspec` 找不到，打印 `~/.local/bin` 加入 PATH 的提示（uv 场景另提 `uv tool update-shell`），**退出码仍为 0**——包确实装好了，问题在当前 shell 的 PATH。

### D12 — README 结构：用户视角的 Install、发布者视角的 Releases、贡献者视角的 Development（第 3 轮更新）

- **Install**：一行式脚本（含"先下载再审阅"的两步替代命令）、`uv tool install` / `pipx` 手动路径、更新（同一条命令）、卸载、Windows 说明。
- **Releases**：发布流程改为显式三步，必须按序：
  1. 把 `pyproject.toml` 与 `src/loopspec/__init__.py` 的版本号同时改成目标版本，合并到 `main`；
  2. `git tag v<version> <main 上的 commit>`；
  3. `git push origin v<version>`。

  并说明：只有第 3 步会触发发布；tag 名与两处版本号不一致会失败；Release 资产清单；**仓库设置前置条件**（`Settings → Actions → General → Workflow permissions` 需允许 `Read and write`，否则 `gh release create` 会 403）；以及"谁能推 `v*` tag 就能发布，建议用 GitHub 的 tag 保护规则（ruleset）收紧"这条提示（见 Risks）。
- **Development**：保留 `make install` / `test` / `lint` / `build` / `clean`，新增 `release-dry-run`（含 `TAG=v0.1.0` 的用法）。

### D13 — 令牌可见性边界：checkout 不持久化凭据，令牌只绑定在调用 `gh` 的 step 上

（第 1 轮 security FAIL 的修复，本轮原样保留。）三条规则缺一不可：

1. **两个 job 的 `actions/checkout` 都显式 `with: persist-credentials: false`。** 默认行为会把 `GITHUB_TOKEN` 以 `http.extraheader` 写进 `.git/config`——那是工作目录里的普通文件，同 job 内任何代码都能读。
2. **令牌只以 step 级 `env: GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}` 注入调用 `gh` 的 step**，不得出现在 workflow 级或 job 级 `env`。
3. **任何执行仓库代码或第三方代码的 step 都不得注入令牌**：`pytest`、`ruff`、`mypy`、`uv sync`、`uv build`、`shellcheck` 全部在无令牌的环境下运行。

- **与 D3、D15 的互补**：发布走 `gh` 而非 `git push`，D15 的祖先校验也走 `gh api` 而非 `git fetch`，所以整条流程本就不需要 git 的推送/拉取凭据——`persist-credentials: false` 不损失任何功能。
- **可验证性**：三条都能靠读 workflow 文件断言（每个 `uses: actions/checkout` 后必须有 `persist-credentials: false`；令牌只能出现在 `gh` step 的 `env` 下），因此可以写成 spec 需求。

### D14 — 构建后端的版本约束，以及在特权 job 内构建的隔离条件

（第 1 轮 security FAIL 的修复，本轮原样保留。结论：`release` job 继续自己构建，但补三层控制。）

1. **给构建后端加版本约束**：`pyproject.toml` 的 `[build-system] requires` 从裸 `"hatchling"` 改为 `"hatchling>=1.31,<2"`（1.31.0 是当前 PyPI 上的版本，也是本变更验证构建所用版本；上界排除下一个大版本）。
2. **构建 step 不得看到令牌**（D13 第 3 条）：`uv build` 会执行构建后端的钩子代码；该 step 环境中无令牌，工作目录 `.git/config` 中也无凭据。即使构建后端被投毒，它在这个 job 里也拿不到可改写仓库的凭据。
3. **构建产物不被通配符发布**（D3）：被投毒的后端即使往 `dist/` 多写文件，也不会被发布。

- **为什么不改成从 `verify` 传产物**：那只是把同一段构建后端代码搬到另一个 job 执行，"执行第三方构建代码"这件事没有消失，却要多引入两个 action 依赖——用一个新的供应链面去换一个没被真正消除的风险。
- **诚实的残余风险**：版本范围**不是**哈希固定——`pyproject.toml` 无法表达哈希，`uv build` 仍会在范围内解析到最新补丁版。这缩小了窗口（排除大版本跳跃与被撤回后重新占位的旧版本），但没有消除"构建时解析第三方代码"。显式接受；彻底解决需要在受控环境预装固定版本的构建后端，代价与本变更规模不匹配。

### D15 — 被打 tag 的 commit 必须可从默认分支到达（第 3 轮新增）

裁决原话是"master 分支提交 tag"，而 git 的 tag 不属于任何分支。落实这个意图的唯一准确表述是：**被打 tag 的 commit 必须可从默认分支到达**。`release` job 在发布之前 SHALL 做这项校验，不满足即失败。

实现走 `gh api`，而不是 git：

```
status=$(gh api "repos/$GITHUB_REPOSITORY/compare/main...$GITHUB_SHA" --jq '.status')
case "$status" in
  identical|behind) ;;                       # tag 指向 main 上的某个 commit
  *) echo "tag is not reachable from main (status: $status)" >&2; exit 1 ;;
esac
```

- **为什么用 `gh api compare` 而不是 `git merge-base --is-ancestor`**：后者需要本地有 `main` 的历史，意味着 `fetch-depth: 0` 外加一次 `git fetch origin main`；而在 `persist-credentials: false` 之下，额外的 `git fetch` 在私有仓库场景会缺凭据。`gh api` 这一步本来就允许持有令牌（D13 第 2 条），且不需要加深 checkout 深度。
- **`identical` 与 `behind` 都算通过**：`behind` 表示被比较的 commit 是 `main` 的祖先（即 tag 打在 `main` 历史上的某个较早 commit——补发旧版本时的正常情形）；`identical` 表示 tag 正好指向 `main` 的当前 HEAD。`ahead`/`diverged` 说明 tag 打在了未合入 `main` 的 commit 上，拒绝。
- **这条能挡住什么**：把一个未经评审的分支 commit 打上 `v0.9.9` 直接推 tag、从而发出一个"看起来是正式版"的 Release。少了这条，只要有 tag 推送权限就能发布任意 commit。
- **代价与可否决性**：多一次 API 调用；且如果将来出现"从维护分支发补丁版"的需求，这条会挡路（届时需扩展为"可从 `main` 或任一 `release/*` 分支到达"）。**这是本轮新增的约束，不是裁决明确要求的**——它是我对"在 master 分支打 tag"这句话的落实方式。若认为多余，删掉这一个 step 即可，其余设计不受影响。

### D16 — Release 已存在时失败，而不是跳过（第 3 轮新增，替换旧的跳过语义）

若 `v<version>` 的 Release 已存在，`release` job SHALL **失败**并给出可操作的提示，SHALL NOT 静默跳过。

- **为什么旧的"跳过且算成功"语义必须撤掉**：它存在的唯一理由是"默认分支每个 commit 都走发布路径，不能每次亮红叉"。tag 驱动之下，一次 tag 推送就是一次明确的发布意图——此时"我做不到"却报成功，是在掩盖失败。
- **什么情况会撞上**：重跑一个已成功的工作流；或删掉 tag 后重推同名 tag。前者应当报错（这次运行确实没能创建 Release）；后者是发布流程本身出了问题，更该响亮地失败。
- **提示要可操作**：失败信息应给出两条出路——`gh release delete v<x> --cleanup-tag` 后重推 tag，或改用新版本号。
- **仍然必须区分"明确不存在"与"查询本身失败"**：只有明确的"不存在"才继续发布；网络错误、5xx、权限问题一律失败，不得被当作"不存在"而误入发布路径。

### D17 — `workflow_dispatch` 的语义：只有在 tag ref 上才发布（第 3 轮新增）

保留 `workflow_dispatch`，语义由 D1 的 ref 条件自然确定，无需额外逻辑：

- **在 tag ref 上手动触发** → `verify` + `release` 都跑，等价于重新走一遍该 tag 的发布（受 D16 约束，若 Release 已存在则失败）。这是补发/重试的入口。
- **在分支 ref 上手动触发** → 只跑 `verify`，`release` job 被 `if` 条件跳过。

- **为什么不让分支上的手动触发也能发布**：那就得凭空猜一个版本号（读 `pyproject.toml`），等于把刚被裁决撤掉的旧机制从后门放回来。**没有 tag 就没有发布版本号**，这一点不留例外。
- GitHub 的 "Run workflow" 下拉框同时列出分支与 tag，因此"在 tag 上手动触发"是现成可用的操作，不需要额外加 `inputs`。

## Risks / Trade-offs

- **[谁能推 `v*` tag 就能发布 —— 本轮引入的新授权假设]** → 旧方案下发布需要把版本号变更合入 `main`（走 PR 与分支保护）；tag 驱动下，只要有仓库写权限就能推 tag 并触发发布。D15 把"能发布哪些 commit"限制在 `main` 的历史上，但"谁能发布"仍等于"谁能推 tag"。缓解：README 在 Releases 一节提示用 GitHub 的 tag 保护规则（ruleset）限制 `v*` 的推送者。**这是配置层面的建议，不由本变更的代码强制**——如实写明，不假装已解决。
- **[三处版本号需要人手同步]** → CI 强制 tag 名 = `pyproject.toml` = `__init__.py`，不一致即失败（D5），并且失败发生在构建之前、报错含三处实际值。代价是发布前要改两个文件；`hatch-vcs` 能消掉这个负担但代价更大（D5 的替代方案讨论）。
- **[打了 tag 但忘记先改版本号 → 发布失败]** → 这是 fail-closed 的正确方向，但会浪费一次 tag。缓解：`make release-dry-run TAG=v0.2.0` 可在本地预演三方校验；README 的发布流程把"先改版本号并合入 `main`"列为第 1 步。
- **[`on.push.tags` 的 glob 不是校验]** → 已在 D2/D6 显式点明，真正的把关是正则闸门。
- **[`curl | sh` 的固有信任问题]** → 无法根除，只能缩小：README 同时给出"下载 → 审阅 → 执行"的两步命令和完全手动的 `uv tool install` 路径；脚本不提权、不写系统目录、只装经 SHA256 校验的 wheel。
- **[构建时解析第三方构建后端（残余）]** → 见 D14：版本上下界缩小窗口，令牌对构建 step 不可见，发布走文件名白名单。不做哈希固定，显式接受。
- **[安装时解析的运行时依赖未做哈希固定]** → `uv tool install <wheel>` 会从 PyPI 解析 `pydantic`/`typer`/`rich`/`pyyaml`/`questionary`。本变更只保证"你装到的 loopspec wheel 是我们发的那个"，不保证其依赖树。spec 里不做超出实现的承诺。
- **[pin 到 SHA 的 action 不会自动更新]** → 行尾注释保留 tag，本文件记录用 `gh api repos/<repo>/git/ref/tags/<tag>` 取新 SHA 的方法。
- **[`verify` 与 `release` 各构建一次]** → hatchling 对同一 commit 的输出确定；`checksums.txt` 由 `release` job 对**自己**产出的文件计算，发布的资产与其校验值必然自洽。残余风险仅是"verify 通过而 release 构建失败"，那会红在 CI 里，不会发出坏产物。
- **[GitHub API 未认证时 60 次/小时/IP 的速率限制]**（仅影响 `install.sh`）→ 只在未指定 `LOOPSPEC_VERSION` 时调一次；被限流时报错并提示可用 `LOOPSPEC_VERSION=x.y.z` 跳过。
- **[`--generate-notes` 的质量取决于 commit 信息]** → 接受，本变更不引入 changelog 流程。

## Migration Plan

1. 新增 `.github/workflows/release.yml`、`install.sh`、`scripts/check_version.py`、`tests/test_check_version.py`；改 `pyproject.toml`（`[build-system] requires` 加版本约束）、`Makefile`、`README.md`。
2. 本地 `make lint`、`make test`、`make release-dry-run` 全绿；再跑 `make release-dry-run TAG=v0.1.0` 确认三方校验通过，以及 `TAG=v9.9.9` 确认它会失败。
3. 合并到 `main`：此时**不会发布任何东西**——只跑 `verify`。这是相对前两轮方案的一个明确改善（旧方案合并即发出 `v0.1.0`）。
4. 想发首个版本时显式执行：确认 `pyproject.toml` 与 `__init__.py` 都是 `0.1.0` → `git tag v0.1.0 <main 的 commit>` → `git push origin v0.1.0`。观察工作流创建 Release 并上传三个资产。
5. 用 `curl -fsSL <raw install.sh URL> | sh` 在干净环境实测一次安装，再重跑一次验证更新路径幂等；另故意改坏本地 `checksums.txt` 验证校验会失败（确认 D8 的断言真的生效）。
6. **回滚**：删除 `.github/workflows/release.yml` 即停止一切自动发布；已发出的 Release/tag 用 `gh release delete v<x> --cleanup-tag` 撤除。`install.sh` 留在仓库里不产生任何自动行为。`[build-system]` 的版本约束可单独还原。

注意：`install.sh` 的 raw URL 指向 `main` 分支，因此**脚本必须先合并进 `main` 才能被 README 里的命令下载到**；且在推出第一个 tag 之前，`releases/latest` 不存在，一行式安装命令会因查不到 latest Release 而失败。这是预期的时序（步骤 3 之后、步骤 4 之前的窗口），README 无需为此加特殊说明。

## Open Questions

- **D15（tag 必须可从 `main` 到达）是我对"在 master 分支打 tag"的落实方式，不是裁决明确要求的**。如果这条约束不需要，删掉那一个 step 即可。请在下一轮 approval 时明确接受或否掉。
- 是否要用 GitHub 的 tag 保护规则（ruleset）限制谁能推 `v*` tag？本变更只在 README 里给建议，不代为配置（那是仓库设置，不在代码里）。
- 是否要在 PR 上也跑 `verify` job（`on.pull_request`）？本变更范围内不做。若将来加上，D13 的三条约束仍需保持，且不得改用 `pull_request_target`。
