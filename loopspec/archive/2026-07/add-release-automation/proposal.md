## Why

LoopSpec 已经是一个可用的 CLI，但它没有任何分发渠道：仓库里没有 `.github/`，没有 CI，`make build` 产出的 wheel 只留在本地 `dist/`，README 的 "Install" 一节只教了 `make install`（`uv sync` 到本地 virtualenv）——那是**开发者搭环境**的方式，不是**用户装工具**的方式。想用这个 CLI 的人必须 clone 仓库、装 uv、自己 sync，而且拿不到任何版本化的产物。

同时，每次推到默认分支都没有任何自动校验：`make test` / `make lint` 是否通过完全取决于提交者是否在本地跑过。本变更一次性补上"自动构建校验 + 版本化发布 + 一行式安装/更新"这条最小可用的分发链路。

## What Changes

- **新增 GitHub Actions 发布工作流**（`.github/workflows/release.yml`）：默认分支收到 push 时自动跑 lint + test，构建 wheel 与 sdist，并在版本号是新的时候创建 GitHub Release。
  - 发布由 **版本号驱动，而非每次 push 都发**：工作流读取 `pyproject.toml` 的 `project.version`，若 tag `v<version>` 已存在则只做构建校验并跳过发布（正常退出，不算失败）；若不存在则打 tag、创建 Release、上传产物。这样日常 commit 不会刷出一堆 Release，抬版本号就是发布动作。
  - Release 资产包含 `loopspec-<version>-py3-none-any.whl`、`loopspec-<version>.tar.gz` 和 `checksums.txt`（各产物的 SHA256）。
  - 新增版本一致性校验：`pyproject.toml` 的 `version` 与 `src/loopspec/__init__.py` 的 `__version__` 不一致时工作流失败——这两处目前靠人手同步，一旦漂移，`loopspec version` 在源码 checkout 下会撒谎。
  - 支持手动触发（`workflow_dispatch`），便于补发。
  - 权限最小化：默认 `permissions: contents: read`，仅发布 job 提升为 `contents: write`；只用 GitHub 自动注入的 `GITHUB_TOKEN`，不引入任何新密钥。
- **新增一行式安装脚本**（`install.sh`，仓库根目录）：
  ```bash
  curl -fsSL https://raw.githubusercontent.com/mingyuans/LoopSpec/main/install.sh | sh
  ```
  - 同一条命令既装也更新（幂等）：已装则升级到目标版本，未装则安装。
  - 默认装 latest Release；`LOOPSPEC_VERSION=0.2.0` 可指定版本，输入 SHALL 经格式校验后才拼进 URL。
  - 安装后端优先 `uv tool install`，回退 `pipx install`；两者都没有时给出明确的安装指引并以非零码退出，**不**自作主张改用 `pip install --user` 或 `sudo`。
  - 下载后依据 Release 里的 `checksums.txt` 校验 SHA256，校验失败即中止；全程仅走 HTTPS，产物只落在 `mktemp -d` 目录并在退出时清理。
  - 结尾执行 `loopspec version` 自检，并在可执行文件不在 `PATH` 时提示如何补上。
- **新增 `make release-dry-run`**：在本地跑一遍工作流的构建与版本一致性校验，避免"只有推上去才知道会不会红"。
- **更新 README**：把 "Install" 一节拆成面向用户的 "Install"（一行式脚本 + uv/pipx 手动安装 + 更新与卸载）和面向贡献者的 "Development"（保留 `make install`），并说明发布是版本号驱动的。
- 非目标（明确排除）：不发布到 PyPI（本变更只做 GitHub Release 分发，PyPI 需要账号与 trusted publisher 配置，留作后续变更）；不做多平台二进制打包（纯 Python wheel 已经跨平台）；不引入 Windows 的 `install.ps1`（README 中指引 Windows 用户直接用 `uv tool install`）；不自动 bump 版本号（版本号由人决定，工作流只消费它）。

## Capabilities

### New Capabilities
- `release-automation`: 默认分支 push 触发的自动化发布链路——构建校验（lint/test/版本一致性）、版本号驱动的发布判定（tag 已存在则跳过）、Release 产物与 checksums 的内容约定、GitHub Actions 权限与凭据约束、手动触发入口。
- `cli-installation`: 一行式安装/更新脚本的行为规范——安装后端选择与回退顺序、版本选择与输入校验、产物完整性校验、幂等的安装/更新语义、失败时的退出码与提示、临时文件清理。

### Modified Capabilities
<!-- 无：本变更不改变任何现有 capability 的需求。README 的安装文档属于文档产物，
     `loopspec version` 命令的行为不变（安装脚本只是它的消费者）。 -->

## Impact

- **新增文件**：`.github/workflows/release.yml`、`install.sh`（需 `chmod +x`）。
- **修改文件**：`README.md`（Install / Development 两节）、`Makefile`（新增 `release-dry-run` 目标）。
- **决策依赖 / 需确认**：仓库默认分支是 `main`（`origin/HEAD -> origin/main`），而需求原文说的是 `master`。本变更按 **`main`** 实现；若确实要监听 `master`，改 `on.push.branches` 一行即可。
- **发布前置条件**：Release 由 `GITHUB_TOKEN` 创建，无需配置 secrets；但仓库设置里 Actions 需允许 `contents: write`（`Settings → Actions → Workflow permissions`），否则发布步骤会 403。这一条要写进 README。
- **版本号同步**：`pyproject.toml` 与 `src/loopspec/__init__.py` 从此被 CI 强制一致——首次上线前需确认两处都是 `0.1.0`（当前确实一致）。
- **安全面**：新增两处外部可达的信任边界——CI 中执行的第三方 action（SHALL pin 到具体版本）和用户 `curl | sh` 执行的脚本（SHALL 做 checksum 校验、SHALL NOT 使用 `eval`/`sudo`、SHALL 校验环境变量输入）。security gate 需重点审这两处。
- **测试**：`install.sh` 不进 pytest（涉及网络与全局安装），改为 `shellcheck` 静态检查 + 工作流内的 `sh -n` 语法校验；`make release-dry-run` 覆盖构建与版本一致性这两条可本地验证的断言。
