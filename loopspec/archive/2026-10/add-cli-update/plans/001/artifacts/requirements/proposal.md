## 背景

LoopSpec CLI 目前没有升级入口：升级只能重新执行 `curl -fsSL …/install.sh | sh`。用户需要记住这条命令；已有的 `loopspec registry update` 只同步外部 Fragment registry，与升级 CLI 无关，名字还容易让人误以为它会升级 CLI。用户明确要求新增 `loopspec update` 命令，用来升级 CLI 本身。

## 用户场景

- 已安装 LoopSpec 的开发者想升级到最新版本：执行 `loopspec update`，CLI 下载并校验最新 Release 后完成安装。
- 开发者只想知道有没有新版本：执行 `loopspec update --check`，只报告当前版本和最新版本，不做任何安装。
- 开发者需要固定到某个版本（回退或对齐团队版本）：执行 `loopspec update --version 2.0.1`。
- Agent 或脚本调用：加 `--json`，得到机器可读结果；失败时得到统一的 `{error, message, fix}` 结构，退出码为 1。

## 范围

- 新增顶层命令 `loopspec update [--version X.Y.Z] [--check] [--json]`。
- 版本解析与 `install.sh` 一致：
  - 不指定版本时，从 `https://github.com/mingyuans/LoopSpec/releases/latest/download/checksums.txt` 取得 checksums，并从中读出版本号；
  - 指定版本时，从 `releases/download/v<ver>/checksums.txt` 取得 checksums。
- 版本号必须先通过与 `install.sh` 相同的正则校验，才能进入 URL、文件名或命令参数。
- 不指定 `--version` 时，最新版本与已装版本相同则直接报告“已是最新”，不下载 wheel、不安装；指定 `--version` 时总是安装该版本。
- wheel 从对应 tag 的 URL 下载到临时目录，在 checksums.txt 中按文件名精确匹配**恰好一行**，SHA256 一致才继续。
- 安装器：存在 `uv` 时执行 `uv tool install --force <wheel>`，否则在存在 `pipx` 时执行 `pipx install --force <wheel>`，两者都没有则报错。以参数列表调用子进程，不经过 shell。
- 网络约束：只允许 https（重定向到非 https 地址时拒绝），设置超时，checksums 与 wheel 都有大小上限。
- 新增错误码，并同步更新中英文 `cli-reference.md` 与 README（含 README 的 update 说明）。
- 补充单元测试与 CLI 测试，不访问真实网络，也不执行真实安装。

## 非目标

- 不刷新项目内的 Skill、命令、hook 与内置 Fragment/Profile（仍由 `loopspec init --tools …` 负责）。
- 不新增 `self-update`、`upgrade` 等别名。
- 不修改 `install.sh` 的行为。
- 不提供跳过 checksum 校验的选项，也不支持自定义 Release 源或代理配置。
- 不检测或迁移通过 `pip install` 等非 uv/pipx 方式安装的副本。

## 验收条件

- [ ] `loopspec update --help` 列出 `--version`、`--check`、`--json` 三个选项；判定：CliRunner 输出包含这三个选项。
- [ ] 最新版本等于已装版本时，结果为 `status: up_to_date`，不下载 wheel、不调用安装器；判定：注入的 fetch 只被调用一次（checksums），runner 未被调用。
- [ ] `--check` 且有新版本时，结果为 `status: available`，包含 `current` 与 `latest`，不下载 wheel、不调用安装器；判定同上。
- [ ] 正常升级时 wheel 校验通过，并以 `["uv", "tool", "install", "--force", <wheel 路径>]` 调用安装器，结果为 `status: updated`；判定：断言 runner 收到的参数列表。
- [ ] 没有 uv、只有 pipx 时，以 `["pipx", "install", "--force", <wheel>]` 安装；两者都没有时返回 `update_installer_missing`；判定：单元测试。
- [ ] SHA256 不一致、checksums 中没有对应行或有多行时，返回 `update_verify_failed`，安装器不被调用；判定：单元测试。
- [ ] 非法版本号（如 `1.0;rm -rf /`、`../1.0.0`、空串），无论来自 `--version` 还是 checksums 内容，都返回 `update_invalid_version`，且不发起后续请求；判定：单元测试。
- [ ] 网络错误、超时、超过大小上限、重定向到 http 时，返回 `update_fetch_failed`；判定：单元测试。
- [ ] 安装器返回非零退出码时，返回 `update_install_failed`；判定：单元测试。
- [ ] `--json` 失败时输出 `{error, message, fix}`，退出码为 1；非 JSON 模式输出人类可读文本；判定：CliRunner 测试。
- [ ] `make test` 全部通过（含 `test_docs_consistency`：新命令、选项、错误码在中英文文档中都有记录）；`make lint`（ruff + mypy）无错误。

## 风险

- **供应链 / 篡改**：下载内容可能被篡改。应对：强制 SHA256 校验，按文件名精确匹配且必须恰好一行；只用 https 并拒绝降级重定向；安装的是已校验的本地文件，而不是让安装器自己去拉 URL。注意：checksums.txt 与 wheel 来自同一来源，校验能防传输损坏和半截下载，不能防 Release 本身被攻破，这一点与 `install.sh` 相同。
- **命令注入**：版本号来自外部（参数或远端文件）。应对：正则白名单校验后才使用；子进程以参数列表调用，不经 shell。
- **资源耗尽**：远端可能返回超大内容或一直不响应。应对：大小上限与超时。
- **安装位置不一致**：用户若用 pip 装在 venv 里，`uv tool install` 会另装一份。应对：与 `install.sh` 行为一致，并在文档中说明；本次不处理。
- **升级自身进程**：升级时正在运行的就是旧版本。uv/pipx 会替换 tool 环境，当前进程已加载的模块不受影响，安装结束后命令退出即可；需要在输出中提示新版本号。
- **兼容性**：只新增命令，不改已有命令，不影响工作区格式。
