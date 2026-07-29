## ADDED Requirements

### Requirement: 默认分支 push 触发自动化工作流
系统 SHALL 提供一个 GitHub Actions 工作流，在默认分支 `main` 收到 push 时自动运行；工作流 SHALL 同时支持 `workflow_dispatch` 手动触发，以便在无新提交的情况下补发。工作流 SHALL NOT 在其他分支的 push 上运行。

#### Scenario: push 到默认分支触发工作流
- **WHEN** 有提交被推送到 `main`
- **THEN** 工作流被触发并执行构建校验流程

#### Scenario: push 到特性分支不触发工作流
- **WHEN** 有提交被推送到 `feat/xxx`
- **THEN** 该工作流不被触发

#### Scenario: 手动触发
- **WHEN** 维护者在 Actions 页面对该工作流执行 `Run workflow`
- **THEN** 工作流以与 push 相同的流程执行

### Requirement: 构建校验先行，且与发布分属不同权限的 job
工作流 SHALL 拆分为 `verify` 与 `release` 两个 job，`release` SHALL 声明 `needs: verify`。工作流顶层 SHALL 声明 `permissions: contents: read`；`release` job SHALL 是唯一提升为 `contents: write` 的 job。`verify` job SHALL 依次执行：版本一致性校验、`ruff` 与 `mypy` 静态检查、`pytest` 测试、`install.sh` 的 shell 静态检查、`uv build` 构建。任一步骤失败时工作流 SHALL 失败且 SHALL NOT 进入 `release` job。

#### Scenario: 测试失败则不发布
- **WHEN** `pytest` 在 `verify` job 中失败
- **THEN** 工作流以失败结束，`release` job 不执行，不创建任何 Release 或 tag

#### Scenario: 执行仓库代码的步骤不持有写权限
- **WHEN** 检查 `verify` job 的有效权限
- **THEN** 其 `contents` 权限为 `read`

#### Scenario: 仅发布 job 持有写权限
- **WHEN** 检查 `release` job 的有效权限
- **THEN** 其 `contents` 权限为 `write`

### Requirement: 版本一致性与格式校验
系统 SHALL 提供单一的版本读取入口脚本，只使用 Python 标准库（`tomllib` 读 `pyproject.toml` 的 `project.version`，`ast` 解析 `src/loopspec/__init__.py` 的 `__version__`），SHALL NOT 为此引入新的运行时或开发依赖，且 SHALL NOT 通过 import 该包来取值。两处版本号一致且格式合法时，脚本 SHALL 把版本号输出到 stdout 并以退出码 0 结束；不一致或格式非法时 SHALL 输出诊断信息到 stderr 并以非零退出码结束。版本号 SHALL 匹配正则 `^[0-9]+\.[0-9]+\.[0-9]+([._-]?(a|b|rc|alpha|beta|dev|post)[0-9]+)?$`。CI 工作流与本地任务入口 SHALL 共用这一个脚本，SHALL NOT 各自另写一份版本提取逻辑。

#### Scenario: 两处版本号一致
- **WHEN** `pyproject.toml` 与 `__init__.py` 的版本号都是 `0.1.0`
- **THEN** 脚本输出 `0.1.0` 并以 0 退出

#### Scenario: 两处版本号漂移
- **WHEN** `pyproject.toml` 是 `0.2.0` 而 `__init__.py` 仍是 `0.1.0`
- **THEN** 脚本以非零退出码结束，stderr 中同时指出两处的值，工作流失败

#### Scenario: 版本号格式非法
- **WHEN** `pyproject.toml` 的版本号是 `0.1.0-my-branch`
- **THEN** 脚本以非零退出码结束，且该值不会被用于构造 tag

#### Scenario: 不导入包即可取值
- **WHEN** 在未安装项目依赖的环境中运行该脚本
- **THEN** 脚本仍能正常读出两处版本号并完成校验

### Requirement: 发布由版本号驱动，已发布的版本跳过且不算失败
`release` job SHALL 以 `v<version>` 这个 Release 是否已存在作为发布判定依据。若已存在，job SHALL 跳过发布、在 job summary 中写明本次为跳过及对应版本号，并以**成功**状态结束。若不存在，job SHALL 执行发布。查询 Release 存在性时若发生查询本身的错误（而非"明确不存在"），job SHALL 失败，SHALL NOT 将其视为"已存在"或"不存在"。

#### Scenario: 版本号未变更的常规提交
- **WHEN** 一个不修改版本号的提交被推送到 `main`，且 `v0.1.0` 已发布
- **THEN** 构建校验照常执行，不创建新 Release，工作流以成功状态结束，job summary 说明跳过原因与版本号

#### Scenario: 版本号被抬升
- **WHEN** 一个把版本号改为 `0.2.0` 的提交被推送到 `main`，且 `v0.2.0` 尚未发布
- **THEN** 工作流创建 `v0.2.0` 的 tag 与 Release

#### Scenario: 查询 Release 时 API 出错
- **WHEN** 查询 `v0.2.0` 是否存在时 GitHub API 返回 5xx
- **THEN** job 失败，不创建 Release，也不报告为"已跳过"

### Requirement: Release 资产的命名与内容契约
创建 Release 时，系统 SHALL 上传且仅上传以下资产，文件名 SHALL 严格遵循以下命名（`<version>` 为不带 `v` 前缀的版本号）：
- `loopspec-<version>-py3-none-any.whl`
- `loopspec-<version>.tar.gz`
- `checksums.txt`

上传时系统 SHALL 按上述命名显式列出这三个文件路径，SHALL NOT 使用通配符（如 `dist/*`）展开待上传文件——通配符会把"发布哪些文件"的决定权交给构建目录的实际内容，无法满足"仅上传"这一约束。上传前系统 SHALL 逐个断言这三个文件存在，任一缺失即 SHALL 失败且 SHALL NOT 创建 Release。

`checksums.txt` SHALL 包含上述 wheel 与 sdist 的 SHA256，格式 SHALL 可被 `sha256sum -c` 与 `shasum -a 256 -c` 直接校验，且每条记录的文件名 SHALL 是不含目录前缀的基名。`checksums.txt` SHALL 由发布 job 对**其自身构建产出的文件**计算，以保证发布的资产与其校验值自洽。Release 的 tag SHALL 为 `v<version>`，SHALL 指向触发本次运行的 commit。

#### Scenario: Release 资产齐全
- **WHEN** `v0.2.0` 发布完成
- **THEN** 该 Release 包含 `loopspec-0.2.0-py3-none-any.whl`、`loopspec-0.2.0.tar.gz`、`checksums.txt` 三个资产

#### Scenario: 构建产物名与预期版本号不符
- **WHEN** 版本号为 `0.2.0` 但 `dist/` 中不存在 `loopspec-0.2.0-py3-none-any.whl`
- **THEN** 发布步骤失败，不创建 Release

#### Scenario: 构建目录中的意外文件不会被发布
- **WHEN** `dist/` 中除契约规定的两个产物外还存在其他文件
- **THEN** 该文件不会出现在 Release 资产中

#### Scenario: checksums 可被标准工具校验
- **WHEN** 下载 wheel 与 `checksums.txt` 到同一目录并运行 `sha256sum -c checksums.txt`（或 `shasum -a 256 -c`）
- **THEN** 校验通过

#### Scenario: tag 指向触发运行的 commit
- **WHEN** commit `abc123` 触发了 `v0.2.0` 的发布
- **THEN** tag `v0.2.0` 指向 `abc123`

### Requirement: 凭据与权限最小化
工作流 SHALL 只使用 GitHub 自动注入的 `GITHUB_TOKEN`，SHALL NOT 声明、读取或依赖任何额外的 repository/organization secret，SHALL NOT 在任何步骤中把凭据写入日志、文件或命令行参数。工作流 SHALL NOT 向除 GitHub 自身 API 之外的外部服务发送仓库内容或凭据。

#### Scenario: 无需配置任何 secret
- **WHEN** 在一个未配置任何 secret 的仓库中启用该工作流
- **THEN** 工作流可以完整运行并成功发布（前提是仓库 Actions 允许 `contents: write`）

#### Scenario: 日志中不出现凭据
- **WHEN** 检查任一 job 的运行日志
- **THEN** 日志中不包含 token 值

### Requirement: 令牌不得暴露给执行仓库代码或第三方代码的步骤
除"权限最小化"之外，工作流 SHALL 把令牌的**可见范围**限制到实际需要它的步骤，具体 SHALL 满足以下全部三条：

- 每一处 `actions/checkout` SHALL 显式声明 `persist-credentials: false`。默认行为会把令牌以 `http.extraheader` 形式写入工作目录的 `.git/config`，使同一 job 内运行的任意代码都能读到它。
- 令牌 SHALL 仅以 step 级 `env` 的形式注入调用 `gh` 的步骤，SHALL NOT 出现在 workflow 级或 job 级 `env`。
- 执行仓库自身代码或第三方代码的步骤（测试、静态检查、依赖同步、构建）SHALL NOT 被注入任何令牌。

由于发布通过 `gh` 完成而非 `git push`，禁用凭据持久化 SHALL NOT 影响任何功能。

#### Scenario: checkout 不持久化凭据
- **WHEN** 检查工作流中每一处 `actions/checkout` 的 `with` 配置
- **THEN** 均包含 `persist-credentials: false`

#### Scenario: 测试步骤看不到令牌
- **WHEN** `verify` job 运行测试与静态检查步骤
- **THEN** 这些步骤的环境变量中不存在任何令牌

#### Scenario: 构建步骤看不到令牌
- **WHEN** `release` job 运行构建步骤（该步骤会执行 `pyproject.toml` 声明的构建后端代码）
- **THEN** 该步骤的环境变量中不存在任何令牌，且工作目录的 `.git/config` 中不含凭据

#### Scenario: 令牌只绑定在发布步骤
- **WHEN** 检查工作流中令牌的所有出现位置
- **THEN** 它只出现在调用 `gh` 的 step 的 `env` 下，不出现在 workflow 级或 job 级 `env`

### Requirement: 构建后端受版本范围约束
项目 SHALL 为 `pyproject.toml` 的 `[build-system] requires` 声明版本下界与上界（上界 SHALL 排除下一个主版本），SHALL NOT 使用无任何约束的裸包名。这限制了每次构建时从包索引解析并执行的第三方构建后端代码的范围。

该约束 SHALL NOT 被表述为哈希级固定：版本范围内仍会解析到最新的补丁版本，因此"构建时解析第三方代码"这一事实仍然存在。抵消它的补充控制是上述"令牌不得暴露给执行第三方代码的步骤"与"按命名契约显式列出待发布文件"两条需求。

#### Scenario: 构建后端有版本上下界
- **WHEN** 检查 `pyproject.toml` 的 `[build-system] requires`
- **THEN** 其中的构建后端声明同时带有版本下界与排除下一主版本的上界

#### Scenario: 加约束后仍可构建
- **WHEN** 在加了版本约束的工作副本上执行构建
- **THEN** 构建成功，产出符合命名契约的 wheel 与 sdist

### Requirement: 第三方 Action 固定到不可变引用
工作流引用的每一个第三方 action SHALL 固定到 40 位 commit SHA，SHALL NOT 使用可变的 tag 或分支引用（如 `@v7`、`@main`）。每个 pin SHALL 在同行注释中保留其对应的人类可读版本号，便于人工核对与升级。

#### Scenario: 所有 action 引用均为 SHA
- **WHEN** 检查工作流文件中所有 `uses:` 行
- **THEN** 每一行的引用都是 40 位 commit SHA，且带有说明对应版本的注释

### Requirement: 发布逻辑不引入额外的第三方 Action
创建 tag、创建 Release、上传资产 SHALL 通过 GitHub-hosted runner 预装的 `gh` CLI 完成，SHALL NOT 为此引入第三方发布类 action。工作流 SHALL NOT 使用 artifact 上传/下载 action 在 job 之间传递构建产物；`release` job SHALL 重新构建以获得待发布产物。

#### Scenario: 发布步骤只用预装工具
- **WHEN** 检查 `release` job 的发布步骤
- **THEN** 它调用 `gh` 命令，工作流中除 checkout 与 uv 安装外没有其他 action

### Requirement: 本地可预演 CI 的可本地验证部分
项目的任务入口（`Makefile`）SHALL 提供一个目标，在本地按 CI 相同的方式执行版本一致性校验、`install.sh` 的语法检查与构建，使贡献者无需推送即可发现这些问题。当本地缺少 `shellcheck` 时，该目标 SHALL 跳过 `shellcheck` 并明确提示其缺失，SHALL NOT 因此失败；但在 CI 中 `shellcheck` SHALL 是硬要求。

#### Scenario: 本地预演通过
- **WHEN** 在版本号一致、脚本语法正确的工作副本上运行该目标
- **THEN** 命令以 0 退出，且已产出构建产物

#### Scenario: 本地预演捕获版本漂移
- **WHEN** 在版本号漂移的工作副本上运行该目标
- **THEN** 命令以非零码退出并指出漂移

#### Scenario: 本地缺少 shellcheck
- **WHEN** 本地未安装 `shellcheck` 时运行该目标
- **THEN** 命令跳过 `shellcheck`、打印提示，其余检查照常执行

### Requirement: 发布前置条件与跳过语义写入项目文档
项目文档 SHALL 说明发布是版本号驱动的（抬升版本号才会产生 Release）、Release 中包含哪些资产，以及启用发布所需的仓库设置前置条件（Actions 的 workflow 权限需允许写入 `contents`，否则发布步骤会因权限不足失败）。

#### Scenario: 文档覆盖发布语义与前置条件
- **WHEN** 读者查阅项目 README 的发布相关章节
- **THEN** 能得知"改版本号才发布"、Release 资产清单，以及需要开启的仓库 Actions 权限设置
