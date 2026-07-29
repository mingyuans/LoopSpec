## ADDED Requirements

### Requirement: 发布由 tag 推送触发，构建校验由默认分支 push 触发
系统 SHALL 提供一个 GitHub Actions 工作流，具备两条触发路径：

- 默认分支 `main` 收到 push 时，SHALL 只执行构建校验，SHALL NOT 创建任何 Release 或 tag。
- 推送形如 `v<version>` 的 tag 时，SHALL 先执行构建校验，再执行发布。

工作流 SHALL 同时支持 `workflow_dispatch`。工作流 SHALL NOT 在其他分支的 push 上运行。tag 的 ref 过滤 SHALL 收窄到形如 `v<数字>.<数字>.<数字>` 开头的模式而非宽泛的 `v*`；该过滤 SHALL NOT 被当作 tag 名的格式校验（glob 无法表达"三段数字"，且尾部通配放行任意后缀），真正的校验由「tag 名格式校验」需求承担。

#### Scenario: 默认分支 push 只校验不发布
- **WHEN** 一个提交被推送到 `main`
- **THEN** 工作流执行 lint、测试与构建校验，且不创建任何 Release 或 tag

#### Scenario: 推送版本 tag 触发发布
- **WHEN** tag `v0.2.0` 被推送
- **THEN** 工作流先执行构建校验，通过后创建 `v0.2.0` 的 Release

#### Scenario: push 到特性分支不触发工作流
- **WHEN** 有提交被推送到 `feat/xxx`
- **THEN** 该工作流不被触发

#### Scenario: 无关 tag 不进入发布路径
- **WHEN** tag `vendor-snapshot` 被推送
- **THEN** 工作流不被触发

### Requirement: 发布版本号取自触发发布的 tag 名
发布路径的版本号 SHALL 取自触发本次运行的 tag 名去掉 `v` 前缀后的值，SHALL NOT 从 `pyproject.toml` 或任何其他文件读取后再推断是否发布。Release 的名称 SHALL 使用该 tag。由于 tag 在触发时已经存在，发布步骤 SHALL NOT 再创建 tag。

#### Scenario: 版本号来自 tag
- **WHEN** tag `v0.2.0` 触发发布
- **THEN** 发布使用的版本号为 `0.2.0`，Release 对应 tag 为 `v0.2.0`

#### Scenario: 发布步骤不创建 tag
- **WHEN** 发布步骤执行
- **THEN** 它为既有 tag 创建 Release，不创建新的 tag，也不推送任何 git ref

### Requirement: tag 名格式校验（用途闸门）
tag 名去掉 `v` 前缀后的值，在被用于构造 Release 名、文件路径或任何命令参数**之前**，SHALL 通过格式校验，SHALL 匹配正则 `^[0-9]+\.[0-9]+\.[0-9]+([._-]?(a|b|rc|alpha|beta|dev|post)[0-9]+)?$`。校验失败时工作流 SHALL 失败且 SHALL NOT 创建 Release。

本项校验解决的是"这个值能否安全地拼进路径与参数"，SHALL NOT 被当作针对表达式插值的防护——后者由「外部可影响的值不得插值进入脚本体」这条需求承担，且发生在本项校验之前。两条需求 SHALL 同时满足，SHALL NOT 互相替代。

#### Scenario: 合法 tag 通过校验
- **WHEN** tag 为 `v0.2.0`
- **THEN** 校验通过，值 `0.2.0` 进入后续步骤

#### Scenario: 格式非法的 tag 被拒绝
- **WHEN** tag 为 `v0.2` 或 `v0.2.0-my-branch`
- **THEN** 工作流失败，不创建 Release，该值不被拼入任何路径或命令参数

### Requirement: 外部可影响的值不得以表达式插值进入脚本体
工作流 SHALL 满足以下全部三条，以杜绝表达式插值造成的脚本注入：

- `run:` 脚本体内 SHALL NOT 出现 `${{ github.* }}`、`${{ env.* }}`、`${{ inputs.* }}` 一类表达式插值。需要用到的值 SHALL 通过该 step 的 `env:` 绑定传入，并在脚本中以带引号的变量展开引用。
- step 之间传值 SHALL 走 `$GITHUB_ENV` 或 `$GITHUB_OUTPUT`，读取端 SHALL 以环境变量引用，SHALL NOT 把上游 step 的输出插值进脚本体。
- `if:` 条件、`env:` 的值、`uses:` 的参数等非脚本体位置 MAY 使用表达式——它们不会被拼进 shell 脚本，不构成注入面。

此约束存在的原因是 `${{ }}` 由 Actions 在生成脚本文件**之前**展开为字面量：若把 tag 名一类外部可影响的值插值进 `run:`，其中的命令替换会在 shell 解析时执行，而这**发生在格式校验之前**，事后校验无法挽回。因 tag 的 ref 过滤 glob 放行任意后缀，此类 tag 名能够真实触达工作流。

#### Scenario: tag 名经环境变量而非插值进入脚本
- **WHEN** 检查工作流中所有使用 tag 名或版本号的 `run:` 步骤
- **THEN** 它们通过 step 级 `env:` 绑定取值，脚本体内不含 `${{ github.` 开头的插值

#### Scenario: 含命令替换的 tag 名不会被执行
- **WHEN** 推送名为 `v1.0.0$(<某条命令>)` 的 tag（该名称能通过 ref 过滤 glob）
- **THEN** 其中的命令替换不被执行；该值作为普通字符串进入格式校验并被拒绝，工作流失败且不创建 Release

#### Scenario: secrets 经 env 绑定不受此限
- **WHEN** 某个调用 `gh` 的 step 通过 `env` 绑定令牌
- **THEN** 该写法符合本需求——它正是本需求要求的形态，而非被禁止的脚本体插值

### Requirement: 被打 tag 的 commit 必须可从默认分支到达
发布之前，系统 SHALL 校验被打 tag 的 commit 可从默认分支到达；不满足时 SHALL 失败且 SHALL NOT 创建 Release。该校验 SHALL 通过 GitHub API 的提交比较完成，SHALL NOT 依赖加深 checkout 深度或额外的 git 抓取（后者在禁用凭据持久化后于私有仓库场景会缺少凭据）。比较所用的默认分支名 SHALL 从仓库信息动态取得，SHALL NOT 硬编码。

本项校验与「三处版本号一致性校验」「目标 Release 已存在时失败」三者共同构成版本混淆防护：三者同时生效时，能推送 tag 者只能发布"默认分支历史上某个自身声明了该版本号、且尚未发布过的 commit"，无法把任意 commit 冠以任意版本号发布。移除其中任一条都会削弱该防护。

#### Scenario: tag 指向默认分支的当前 HEAD
- **WHEN** tag 指向 `main` 的最新 commit
- **THEN** 校验通过，继续发布

#### Scenario: tag 指向默认分支历史上的较早 commit
- **WHEN** tag 指向 `main` 历史中的某个较早 commit（补发旧版本）
- **THEN** 校验通过，继续发布

#### Scenario: tag 指向未合入默认分支的 commit
- **WHEN** tag 指向某个特性分支上、尚未合入 `main` 的 commit
- **THEN** 校验失败，不创建 Release

#### Scenario: 默认分支改名后校验仍然正确
- **WHEN** 仓库的默认分支被改名
- **THEN** 校验以新的默认分支名为基准进行比较，无需修改工作流文件

### Requirement: 构建校验先行，且与发布分属不同权限的 job
工作流 SHALL 拆分为 `verify` 与 `release` 两个 job，`release` SHALL 声明 `needs: verify`，并 SHALL 通过 ref 条件把自身限制在 tag 上运行。工作流顶层 SHALL 声明 `permissions: contents: read`；`release` job SHALL 是唯一提升为 `contents: write` 的 job。`verify` job SHALL 依次执行：版本一致性校验、`ruff` 与 `mypy` 静态检查、`pytest` 测试、`install.sh` 的 shell 静态检查（`sh -n` 与 `shellcheck`，二者均为硬要求）、构建。任一步骤失败时工作流 SHALL 失败且 SHALL NOT 进入 `release` job。

#### Scenario: 测试失败则不发布
- **WHEN** tag 推送触发的运行中 `pytest` 失败
- **THEN** 工作流以失败结束，`release` job 不执行，不创建任何 Release

#### Scenario: 分支 push 时发布 job 缺席
- **WHEN** 运行由 `main` 的 push 触发
- **THEN** `release` job 因 ref 条件不满足而不执行

#### Scenario: 执行仓库代码的步骤不持有写权限
- **WHEN** 检查 `verify` job 的有效权限
- **THEN** 其 `contents` 权限为 `read`

#### Scenario: 仅发布 job 持有写权限
- **WHEN** 检查 `release` job 的有效权限
- **THEN** 其 `contents` 权限为 `write`

### Requirement: 手动触发的发布语义由 ref 决定
`workflow_dispatch` SHALL 遵循与 push 相同的 ref 条件：在 tag ref 上手动触发 SHALL 执行校验与发布；在分支 ref 上手动触发 SHALL 只执行校验。系统 SHALL NOT 在缺少 tag 的情况下从任何文件推断一个待发布版本号。

#### Scenario: 在 tag 上手动触发
- **WHEN** 维护者对 tag `v0.2.0` 执行 `Run workflow`
- **THEN** 工作流执行校验并尝试发布 `v0.2.0`

#### Scenario: 在分支上手动触发
- **WHEN** 维护者对 `main` 执行 `Run workflow`
- **THEN** 工作流只执行校验，不发布，也不推断任何版本号

### Requirement: 三处版本号一致性校验
系统 SHALL 提供单一的版本校验脚本，只使用 Python 标准库（`tomllib` 读 `pyproject.toml` 的 `project.version`，`ast` 解析 `src/loopspec/__init__.py` 的 `__version__`），SHALL NOT 为此引入新的运行时或开发依赖，且 SHALL NOT 通过 import 该包来取值。脚本 SHALL 支持两种调用方式：

- **不带期望值**：校验上述两处一致且格式合法，一致时把版本号输出到 stdout 并以 0 退出。
- **带期望值**（发布路径使用，期望值为 tag 名去掉 `v` 前缀后的值）：在上述校验之外，追加断言两处均等于期望值。

任一校验失败时脚本 SHALL 把涉及的各处实际值输出到 stderr 并以非零退出码结束。版本号 SHALL 匹配与 tag 名相同的正则。CI 工作流与本地任务入口 SHALL 共用这一个脚本，SHALL NOT 各自另写一份版本提取逻辑。

发布路径 SHALL 在**构建之前**执行带期望值的校验——因为构建产物的文件名由 `pyproject.toml` 的版本决定，把不一致拦在构建前所给出的诊断信息，比事后报告"资产文件不存在"清晰得多。

#### Scenario: 三处一致
- **WHEN** tag 为 `v0.2.0`，`pyproject.toml` 与 `__init__.py` 均为 `0.2.0`
- **THEN** 校验通过，继续构建与发布

#### Scenario: tag 与文件中的版本号不一致
- **WHEN** tag 为 `v0.2.0` 但 `pyproject.toml` 仍为 `0.1.0`
- **THEN** 工作流在构建之前失败，stderr 中同时给出 tag 值与两处文件中的值，不创建 Release

#### Scenario: 两处文件之间版本号漂移
- **WHEN** `pyproject.toml` 是 `0.2.0` 而 `__init__.py` 仍是 `0.1.0`
- **THEN** 校验以非零退出码结束，工作流失败

#### Scenario: 文件中的版本号格式非法
- **WHEN** `pyproject.toml` 的版本号是 `0.1.0-my-branch`
- **THEN** 校验以非零退出码结束

#### Scenario: 不导入包即可取值
- **WHEN** 在未安装项目依赖的环境中运行该脚本
- **THEN** 脚本仍能正常读出两处版本号并完成校验

### Requirement: 目标 Release 已存在时失败，不静默跳过
发布之前系统 SHALL 检查该 tag 对应的 Release 是否已存在。已存在时 job SHALL **失败**，并 SHALL 在失败信息中给出可操作的出路（删除既有 Release 与 tag 后重推，或改用新版本号）；SHALL NOT 静默跳过，SHALL NOT 把"未能创建 Release"报告为成功。查询若发生查询本身的错误（而非"明确不存在"），job SHALL 失败，SHALL NOT 将其视为"不存在"而进入发布路径。

#### Scenario: 重跑已成功的发布
- **WHEN** 对一个已成功发布的 tag 重新运行工作流
- **THEN** job 失败并提示既有 Release 的处理方式，不报告为成功

#### Scenario: 查询 Release 时 API 出错
- **WHEN** 查询 Release 是否存在时 GitHub API 返回 5xx
- **THEN** job 失败，不创建 Release，也不将其当作"不存在"继续发布

### Requirement: Release 资产的命名与内容契约
创建 Release 时，系统 SHALL 上传且仅上传以下资产，文件名 SHALL 严格遵循以下命名（`<version>` 为不带 `v` 前缀的版本号）：
- `loopspec-<version>-py3-none-any.whl`
- `loopspec-<version>.tar.gz`
- `checksums.txt`

上传时系统 SHALL 按上述命名显式列出这三个文件路径，SHALL NOT 使用通配符（如 `dist/*`）展开待上传文件——通配符会把"发布哪些文件"的决定权交给构建目录的实际内容，无法满足"仅上传"这一约束。上传前系统 SHALL 逐个断言这三个文件存在，任一缺失即 SHALL 失败且 SHALL NOT 创建 Release。

`checksums.txt` SHALL 包含上述 wheel 与 sdist 的 SHA256，格式 SHALL 可被 `sha256sum -c` 与 `shasum -a 256 -c` 直接校验，且每条记录的文件名 SHALL 是不含目录前缀的基名。`checksums.txt` SHALL 由发布 job 对**其自身构建产出的文件**计算，以保证发布的资产与其校验值自洽。

#### Scenario: Release 资产齐全
- **WHEN** `v0.2.0` 发布完成
- **THEN** 该 Release 包含 `loopspec-0.2.0-py3-none-any.whl`、`loopspec-0.2.0.tar.gz`、`checksums.txt` 三个资产

#### Scenario: checksums 可被标准工具校验
- **WHEN** 下载 wheel 与 `checksums.txt` 到同一目录并运行 `sha256sum -c`（或 `shasum -a 256 -c`）校验其中 wheel 对应的那条记录
- **THEN** 校验通过

#### Scenario: 构建产物名与 tag 版本号不符
- **WHEN** tag 版本号为 `0.2.0` 但 `dist/` 中不存在 `loopspec-0.2.0-py3-none-any.whl`
- **THEN** 发布步骤失败，不创建 Release

#### Scenario: 构建目录中的意外文件不会被发布
- **WHEN** `dist/` 中除契约规定的两个产物外还存在其他文件
- **THEN** 该文件不会出现在 Release 资产中

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

由于发布通过 `gh` 完成而非 `git push`、且默认分支可达性校验通过 GitHub API 完成而非 `git fetch`，禁用凭据持久化 SHALL NOT 影响任何功能。

#### Scenario: checkout 不持久化凭据
- **WHEN** 检查工作流中每一处 `actions/checkout` 的 `with` 配置
- **THEN** 均包含 `persist-credentials: false`

#### Scenario: 测试步骤看不到令牌
- **WHEN** `verify` job 运行测试与静态检查步骤
- **THEN** 这些步骤的环境变量中不存在任何令牌

#### Scenario: 构建步骤看不到令牌
- **WHEN** `release` job 运行构建步骤（该步骤会执行 `pyproject.toml` 声明的构建后端代码）
- **THEN** 该步骤的环境变量中不存在任何令牌，且工作目录的 `.git/config` 中不含凭据

#### Scenario: 令牌只绑定在需要它的步骤
- **WHEN** 检查工作流中令牌的所有出现位置
- **THEN** 它只出现在调用 `gh` 的 step 的 `env` 下，不出现在 workflow 级或 job 级 `env`

### Requirement: 第三方 Action 固定到不可变引用
工作流引用的每一个第三方 action SHALL 固定到 40 位 commit SHA，SHALL NOT 使用可变的 tag 或分支引用（如 `@v7`、`@main`）。每个 pin SHALL 在同行注释中保留其对应的人类可读版本号，便于人工核对与升级。

#### Scenario: 所有 action 引用均为 SHA
- **WHEN** 检查工作流文件中所有 `uses:` 行
- **THEN** 每一行的引用都是 40 位 commit SHA，且带有说明对应版本的注释

### Requirement: 发布逻辑不引入额外的第三方 Action
创建 Release、上传资产、以及默认分支可达性校验 SHALL 通过 GitHub-hosted runner 预装的 `gh` CLI 完成，SHALL NOT 为此引入第三方 action。工作流 SHALL NOT 使用 artifact 上传/下载 action 在 job 之间传递构建产物；`release` job SHALL 重新构建以获得待发布产物。

#### Scenario: 发布步骤只用预装工具
- **WHEN** 检查 `release` job 的各步骤
- **THEN** 它们调用 `gh` 命令，工作流中除 checkout 与 uv 安装外没有其他 action

### Requirement: 构建后端受版本范围约束
项目 SHALL 为 `pyproject.toml` 的 `[build-system] requires` 声明版本下界与上界（上界 SHALL 排除下一个主版本），SHALL NOT 使用无任何约束的裸包名。这限制了每次构建时从包索引解析并执行的第三方构建后端代码的范围。

该约束 SHALL NOT 被表述为哈希级固定：版本范围内仍会解析到最新的补丁版本，因此"构建时解析第三方代码"这一事实仍然存在。抵消它的补充控制是"令牌不得暴露给执行第三方代码的步骤"与"按命名契约显式列出待发布文件"两条需求。

#### Scenario: 构建后端有版本上下界
- **WHEN** 检查 `pyproject.toml` 的 `[build-system] requires`
- **THEN** 其中的构建后端声明同时带有版本下界与排除下一主版本的上界

#### Scenario: 加约束后仍可构建
- **WHEN** 在加了版本约束的工作副本上执行构建
- **THEN** 构建成功，产出符合命名契约的 wheel 与 sdist

### Requirement: 本地可预演 CI 的可本地验证部分
项目的任务入口（`Makefile`）SHALL 提供一个目标，在本地按 CI 相同的方式执行版本一致性校验、`install.sh` 的语法检查与构建。该目标 SHALL 支持可选地传入一个 tag 名，以在本地预演发布路径的三方一致性校验。当本地缺少 `shellcheck` 时，该目标 SHALL 跳过 `shellcheck` 并明确提示其缺失，SHALL NOT 因此失败；但在 CI 中 `shellcheck` SHALL 是硬要求。

#### Scenario: 本地预演通过
- **WHEN** 在版本号一致、脚本语法正确的工作副本上运行该目标
- **THEN** 命令以 0 退出，且已产出构建产物

#### Scenario: 本地预演捕获版本漂移
- **WHEN** 在两处版本号漂移的工作副本上运行该目标
- **THEN** 命令以非零码退出并指出漂移

#### Scenario: 本地预演 tag 一致性
- **WHEN** 传入一个与两处版本号不一致的 tag 名运行该目标
- **THEN** 命令以非零码退出，使人在推 tag 之前就发现不一致

#### Scenario: 本地缺少 shellcheck
- **WHEN** 本地未安装 `shellcheck` 时运行该目标
- **THEN** 命令跳过 `shellcheck`、打印提示，其余检查照常执行

### Requirement: 发布流程与前置条件写入项目文档
项目文档 SHALL 说明发布流程为显式的三步且必须按序执行：把 `pyproject.toml` 与 `src/loopspec/__init__.py` 的版本号同时改为目标版本并合入默认分支；对默认分支上的 commit 打 `v<version>` tag；推送该 tag。文档 SHALL 说明只有推送 tag 会触发发布、tag 名与两处版本号不一致会失败、Release 中包含哪些资产，以及启用发布所需的仓库设置前置条件（Actions 的 workflow 权限需允许写入 `contents`，否则发布步骤会因权限不足失败）。

文档 SHALL 同时提示："能推送 `v*` tag 的人即能发布"，并建议用仓库的 tag 保护规则收紧该权限。该提示 SHALL 被表述为仓库配置层面的建议，SHALL NOT 被表述为本变更已强制实施的控制。

#### Scenario: 文档覆盖发布流程
- **WHEN** 读者查阅项目 README 的发布相关章节
- **THEN** 能得知改版本号 → 打 tag → 推 tag 这三步的顺序、只有推 tag 才发布、以及需要开启的仓库 Actions 权限设置

#### Scenario: 文档如实呈现 tag 推送权限的含义
- **WHEN** 读者查阅发布章节
- **THEN** 能得知推送 `v*` tag 的权限等价于发布权限，且该收紧建议属于仓库配置而非已实施的代码控制
