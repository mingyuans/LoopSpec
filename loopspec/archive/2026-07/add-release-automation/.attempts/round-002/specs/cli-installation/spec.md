## ADDED Requirements

### Requirement: 一行命令完成安装
系统 SHALL 在仓库根目录提供一个可执行的 POSIX shell 脚本 `install.sh`，使用户能够通过单条 `curl ... | sh` 命令安装 LoopSpec CLI，无需 clone 仓库、无需预装 Python 构建工具链。脚本 SHALL 以 `#!/bin/sh` 为解释器并只使用 POSIX shell 特性，SHALL NOT 要求 bash/zsh 专有语法。

#### Scenario: 干净环境一行安装
- **WHEN** 用户在已安装 `uv`、未安装 LoopSpec 的机器上执行一行式安装命令
- **THEN** 安装完成后 `loopspec version` 可以输出已安装的版本号

#### Scenario: 脚本可被 dash 执行
- **WHEN** 用 `dash` 执行 `install.sh`
- **THEN** 脚本正常运行，不出现语法错误

### Requirement: 安装与更新是同一条命令（幂等）
脚本 SHALL 以相同的方式处理"首次安装"与"更新到目标版本"两种情形：已安装时 SHALL 覆盖安装到目标版本，未安装时 SHALL 执行安装。重复执行同一条命令 SHALL 得到一致的最终状态，SHALL NOT 因为"已安装"而报错退出。

#### Scenario: 在已安装的机器上重复执行
- **WHEN** 用户在已安装 LoopSpec 的机器上再次执行同一条安装命令
- **THEN** 命令成功结束，已安装版本被更新到目标版本

#### Scenario: 更新无需额外子命令
- **WHEN** 用户想升级到最新版本
- **THEN** 执行与安装完全相同的命令即可，无需传入额外参数或子命令

### Requirement: 目标版本的确定与来源
脚本 SHALL 支持通过环境变量 `LOOPSPEC_VERSION` 指定目标版本；已指定时 SHALL 直接使用该值且 SHALL NOT 调用 GitHub API。未指定时，脚本 SHALL 查询该仓库的 latest Release 并从响应中提取其 `tag_name`，去掉 `v` 前缀后作为目标版本。脚本 SHALL NOT 依赖 `jq` 等非默认预装工具来解析响应。

#### Scenario: 默认安装最新版本
- **WHEN** 用户未设置 `LOOPSPEC_VERSION` 并执行脚本
- **THEN** 脚本查询 latest Release 并安装其对应版本

#### Scenario: 指定版本时不访问 API
- **WHEN** 用户设置 `LOOPSPEC_VERSION=0.1.0` 并执行脚本
- **THEN** 脚本直接安装 `0.1.0`，不发起 latest Release 查询

#### Scenario: 无 jq 的环境
- **WHEN** 在未安装 `jq` 的 macOS 或精简容器中执行脚本
- **THEN** 脚本仍能正确解析出 latest Release 的版本号

#### Scenario: 查询最新版本失败
- **WHEN** latest Release 查询因网络错误或 API 速率限制失败
- **THEN** 脚本以非零码退出，并提示可通过设置 `LOOPSPEC_VERSION` 跳过该查询

### Requirement: 所有外部输入的版本号在使用前必须通过格式校验
脚本 SHALL 对每一个外部来源的版本号在被用于构造 URL、文件名或任何命令参数**之前**校验格式，SHALL 匹配正则 `^[0-9]+\.[0-9]+\.[0-9]+([._-]?(a|b|rc|alpha|beta|dev|post)[0-9]+)?$`。需要校验的来源 SHALL 至少包括：用户提供的 `LOOPSPEC_VERSION`，以及从 GitHub API 响应中提取出的 `tag_name`。校验失败时脚本 SHALL 以非零码退出并说明原因，SHALL NOT 继续拼接。

#### Scenario: 用户提供非法版本号
- **WHEN** 用户设置 `LOOPSPEC_VERSION="0.1.0; rm -rf /"` 并执行脚本
- **THEN** 脚本在发起任何下载前以非零码退出，该值不被拼入任何 URL 或命令

#### Scenario: 用户提供含路径穿越的版本号
- **WHEN** 用户设置 `LOOPSPEC_VERSION="../../etc/passwd"` 并执行脚本
- **THEN** 脚本以非零码退出，不构造任何下载路径

#### Scenario: API 响应中的版本号同样受校验
- **WHEN** 从 API 响应中提取出的 `tag_name` 不符合上述格式
- **THEN** 脚本以非零码退出，不构造下载 URL

### Requirement: 产物完整性校验是安装的前置条件，且无降级路径
脚本 SHALL 先把 wheel 与 `checksums.txt` 下载到本地临时目录，再依次完成以下**三个都必须成功**的步骤，仅在三者全部成功后才执行安装：

1. **定位条目**：从 `checksums.txt` 中筛选出文件名字段**恰好等于**目标 wheel 基名的记录。比对 SHALL 是精确相等而非子串匹配——子串匹配会让 `0.1.0` 同时命中 `0.1.0` 与 `0.1.0.post1`。
2. **断言恰好一条**：上一步的结果行数 SHALL 等于 1。为 0（条目缺失、下载到的是错误页面、文件为空）或大于 1（重复或歧义记录）时脚本 SHALL 以非零码中止。**"没有校验到"必须等同于"校验失败"**，SHALL NOT 被当作通过。
3. **执行校验**：把该单条记录交给 `sha256sum -c` 或 `shasum -a 256 -c`（按 `command -v` 探测可用者），依其退出码判定。

上述任一步骤失败时脚本 SHALL 中止并以非零码退出，SHALL NOT 安装该产物。两种校验工具都不可用时，脚本 SHALL 中止并以非零码退出。脚本 SHALL NOT 提供跳过校验的开关、环境变量或任何其他降级路径，SHALL NOT 使用 `--ignore-missing` 一类"缺失即忽略"的选项（该选项在 macOS 的 `shasum` 上不存在，且"零个文件被校验"时各实现行为不一致）。

本项校验保证的是 wheel 与 `checksums.txt` 出自同一次发布、且传输过程中没有一方被单独替换；它 SHALL NOT 被表述为对"发布者可信"或"攻击者能改写整个 Release"的防护——那由 GitHub 的仓库权限模型与 HTTPS 承载。

#### Scenario: 校验通过后安装
- **WHEN** `checksums.txt` 中恰有一条目标 wheel 的记录，且下载的 wheel 的 SHA256 与之一致
- **THEN** 脚本继续执行安装

#### Scenario: 产物被篡改
- **WHEN** 下载的 wheel 的 SHA256 与 `checksums.txt` 中的记录不一致
- **THEN** 脚本以非零码退出并报告校验失败，不执行任何安装动作

#### Scenario: checksums.txt 中缺少 wheel 的条目
- **WHEN** `checksums.txt` 下载成功但其中不存在文件名等于目标 wheel 基名的记录
- **THEN** 脚本以非零码退出，不执行安装，且不将"未找到条目"报告为校验通过

#### Scenario: checksums.txt 内容为空或不是预期格式
- **WHEN** 下载到的 `checksums.txt` 为空文件或是一个 HTML 错误页面
- **THEN** 定位条目的结果为 0 条，脚本以非零码退出，不执行安装

#### Scenario: checksums.txt 中存在重复条目
- **WHEN** `checksums.txt` 中存在两条文件名同为目标 wheel 基名的记录
- **THEN** 脚本以非零码退出，不在歧义情况下继续安装

#### Scenario: 相似版本号不被误匹配
- **WHEN** 目标版本为 `0.1.0`，而 `checksums.txt` 中只有 `loopspec-0.1.0.post1-py3-none-any.whl` 的记录
- **THEN** 定位条目的结果为 0 条，脚本以非零码退出

#### Scenario: 环境中没有 SHA256 校验工具
- **WHEN** 机器上既没有 `sha256sum` 也没有 `shasum`
- **THEN** 脚本以非零码退出并说明原因，不跳过校验继续安装

#### Scenario: 不存在跳过校验的开关
- **WHEN** 检查脚本中所有可识别的环境变量与参数
- **THEN** 其中没有任何能够绕过 SHA256 校验的选项

### Requirement: 安装器只接受本地已校验的产物
脚本 SHALL 把**本地已通过校验的 wheel 文件路径**交给安装器，SHALL NOT 让安装器自行从远端 URL 下载安装——否则被校验的字节与被安装的字节并非同一次下载，校验不成立。

#### Scenario: 安装参数是本地路径
- **WHEN** 检查脚本调用安装器时传入的参数
- **THEN** 该参数是临时目录下的本地 wheel 文件路径，而非 http(s) URL

### Requirement: 安装后端的选择与回退顺序
脚本 SHALL 按以下顺序探测安装后端并使用第一个可用者：`uv tool install`，其次 `pipx install`；两者均以强制覆盖模式调用，以满足幂等要求。两者都不可用时，脚本 SHALL 打印获取 `uv` 的官方安装方式并以非零码退出。脚本 SHALL NOT 回退到 `pip install --user` 或任何会写入用户 default Python 环境的方式，SHALL NOT 自动替用户安装 `uv` 或 `pipx`。

#### Scenario: 优先使用 uv
- **WHEN** 机器上同时存在 `uv` 与 `pipx`
- **THEN** 脚本使用 `uv tool install`

#### Scenario: 回退到 pipx
- **WHEN** 机器上没有 `uv` 但有 `pipx`
- **THEN** 脚本使用 `pipx install` 完成安装

#### Scenario: 两种后端都缺失
- **WHEN** 机器上既没有 `uv` 也没有 `pipx`
- **THEN** 脚本以非零码退出，输出安装 `uv` 的官方命令，且不自行安装任何工具、不修改用户的 Python 环境

### Requirement: 脚本的执行安全形态
脚本 SHALL 满足以下全部约束：

- SHALL 以 `set -eu` 开头，使未定义变量与失败命令立即中止执行。
- 全部逻辑 SHALL 封装在函数中，并在文件**末尾**才调用入口函数，使传输中断导致的部分脚本不会被执行。
- SHALL 使用 `mktemp -d` 创建临时目录，SHALL NOT 使用可预测的固定路径；SHALL 通过 `trap` 在 `EXIT`/`INT`/`TERM` 时删除该目录。
- 所有下载 SHALL 仅通过 HTTPS，SHALL 显式禁止协议降级（如 `--proto '=https'`），失败时 SHALL 返回非零（如 `curl -f`）。
- SHALL NOT 使用 `eval`，SHALL NOT 使用 `sudo` 或任何提权手段，SHALL NOT 写入系统级目录。
- SHALL NOT 下载并执行除目标 wheel 之外的任何内容。

#### Scenario: 传输中断不产生半个安装
- **WHEN** `curl | sh` 过程中连接在脚本传输一半时中断
- **THEN** 入口函数从未被调用，机器上没有发生任何安装或写入动作

#### Scenario: 临时目录被清理
- **WHEN** 脚本因任意原因（成功、失败、被 Ctrl-C 中断）结束
- **THEN** 其创建的临时目录已被删除

#### Scenario: 脚本不含提权与 eval
- **WHEN** 静态检查脚本内容
- **THEN** 其中不出现 `sudo`、`eval`，也不写入系统级目录

#### Scenario: 拒绝非 HTTPS 下载
- **WHEN** 下载请求被重定向到 http
- **THEN** 下载失败，脚本以非零码退出

### Requirement: 安装后自检与 PATH 提示
安装成功后，脚本 SHALL 尝试执行 `loopspec version` 进行自检。若可执行文件不在当前 `PATH` 中，脚本 SHALL 输出如何将其加入 `PATH` 的提示，并 SHALL 仍以退出码 0 结束——包已成功安装，未就绪的只是当前 shell 的 `PATH`。

#### Scenario: 自检成功
- **WHEN** 安装完成且可执行文件在 `PATH` 中
- **THEN** 脚本输出已安装版本号并以 0 退出

#### Scenario: 可执行文件不在 PATH 中
- **WHEN** 安装完成但 `loopspec` 不在当前 `PATH` 中
- **THEN** 脚本打印将其目录加入 `PATH` 的提示，并以 0 退出

### Requirement: 脚本纳入静态检查
`install.sh` SHALL 在 CI 中接受 shell 语法检查（`sh -n`）与 `shellcheck` 静态检查，二者 SHALL 均为 CI 的硬性要求；`shellcheck` 报出的问题 SHALL 被修复或以显式的行内 `disable` 指令连同理由标注，SHALL NOT 被静默忽略。

#### Scenario: 语法错误被 CI 拦截
- **WHEN** `install.sh` 中存在 shell 语法错误
- **THEN** CI 失败

#### Scenario: shellcheck 告警被 CI 拦截
- **WHEN** `install.sh` 触发 `shellcheck` 告警且未附带带理由的 disable 指令
- **THEN** CI 失败

### Requirement: 安装文档面向用户，且给出可审阅的替代路径
项目 README SHALL 把面向用户的安装说明与面向贡献者的开发环境搭建分开呈现。安装章节 SHALL 至少包含：一行式安装命令；"先下载、审阅、再执行"的两步替代命令；不使用脚本的手动安装方式（`uv tool install` / `pipx install`）；更新方式（与安装同一条命令）；卸载方式；以及 Windows 用户的说明。文档 SHALL NOT 把开发环境搭建命令呈现为用户的安装方式。

#### Scenario: 用户能找到不执行远端脚本的安装方式
- **WHEN** 一位不愿意直接执行 `curl | sh` 的用户查阅 README 安装章节
- **THEN** 能找到先下载审阅再执行的两步命令，以及完全手动的 `uv tool install` 方式

#### Scenario: 开发环境搭建不再冒充安装方式
- **WHEN** 读者查阅 README 的安装章节
- **THEN** 其中不把 `make install`（开发环境同步）作为用户安装 CLI 的方式，该命令出现在开发章节

#### Scenario: 覆盖更新与卸载
- **WHEN** 读者想更新或卸载已安装的 CLI
- **THEN** README 安装章节给出了对应命令
