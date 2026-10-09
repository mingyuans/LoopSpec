## ADDED Requirements

### Requirement: 在 config.yaml 中声明 schema registry

`config.yaml` SHALL 接受可选的顶层字段 `registry`，其值为对象，包含必填的 `url`、可选的 `version`（缺省为 `latest`）与可选的 `path`；出现其他字段 SHALL 以 `config_invalid` 拒绝。每个项目最多声明一个 registry。缺省时所有既有命令的行为 SHALL 与未引入本能力时一致，且 `loopspec schemas update` 与 `loopspec schemas apply` SHALL 以 `registry_not_configured` 失败。

`url` SHALL 满足：长度不超过 2048；不含空白与控制字符；不以 `-` 开头；不含 `::`；形态为 `https://`、`ssh://`、scp 形态 `user@host:path` 或 `file:///` 绝对路径之一；`https://` 形态 SHALL NOT 包含 userinfo。`version` SHALL 为 `latest` 或一个 tag 名；tag 名 SHALL 匹配 `^[A-Za-z0-9._+-]{1,200}$`，且不以 `-` 或 `.` 开头、不以 `.lock` 结尾、不含 `..`、`@{`。`path` SHALL 为安全相对路径。任一不满足 SHALL 以 `config_invalid` 失败，错误消息 SHALL NOT 回显 URL 中的 userinfo。

#### Scenario: 合法的 GitHub SSH registry
- **WHEN** `config.yaml` 含 `registry: {url: git@github.com:acme/schemas.git, version: v1.3.0}`
- **THEN** 配置加载成功

#### Scenario: 拒绝 ext transport
- **WHEN** `registry.url` 为 `ext::sh -c touch% /tmp/pwned`
- **THEN** 以退出码 1 与 `config_invalid` 失败，且不启动任何子进程

#### Scenario: 拒绝以连字符开头的 URL
- **WHEN** `registry.url` 为 `--upload-pack=touch /tmp/pwned`
- **THEN** 以退出码 1 与 `config_invalid` 失败

#### Scenario: 拒绝内嵌凭据
- **WHEN** `registry.url` 为 `https://user:ghp_xxx@github.com/acme/schemas.git`
- **THEN** 以退出码 1 与 `config_invalid` 失败，错误消息中不出现 `ghp_xxx`

#### Scenario: 拒绝不安全协议
- **WHEN** `registry.url` 为 `http://github.com/acme/schemas.git` 或 `git://github.com/acme/schemas.git`
- **THEN** 以退出码 1 与 `config_invalid` 失败

#### Scenario: 拒绝非法 version
- **WHEN** `registry.version` 为 `-oProxyCommand=x`、`a..b`、`v1.lock` 或 `^1.3`
- **THEN** 以退出码 1 与 `config_invalid` 失败

#### Scenario: 未配置 registry
- **WHEN** `config.yaml` 不含 `registry`，执行 `loopspec schemas update --json`
- **THEN** 以退出码 1 与 `registry_not_configured` 失败；其他命令行为不变

### Requirement: 安全地调用 git 拉取 registry

系统 SHALL 仅通过本机 `git` 可执行文件拉取 registry，使用参数列表且不经 shell，URL 与 refname 之前 SHALL 以 `--` 结束选项解析，并 SHALL 只允许 `url` 形态对应的单一协议（其余协议一律禁止）。拉取 SHALL 使用位于 `<home>/.cache/registry/` 下的 loopspec 私有裸仓库，SHALL NOT checkout 工作区。git 调用 SHALL 设置 `GIT_TERMINAL_PROMPT=0` 并有超时。`git` 不可用时 SHALL 以 `registry_unavailable` 失败；git 非零退出或超时 SHALL 以 `registry_fetch_failed` 失败，消息包含退出码与截断后的 stderr。loopspec SHALL NOT 读取、打印或记录任何环境变量的值。

#### Scenario: 从本地 file:// registry 拉取
- **WHEN** `registry.url` 指向 `tmp_path` 下一个含 `team-flow/schema.yaml` 的本地 git 仓库，执行 `loopspec schemas update --json`
- **THEN** 命令成功，`upstreamCommit` 为该仓库最新 release tag 对应的 commit（无 tag 时为默认分支 HEAD）

#### Scenario: git 不可用
- **WHEN** PATH 中没有 `git`，执行 `loopspec schemas update --json`
- **THEN** 以退出码 1 与 `registry_unavailable` 失败

#### Scenario: 固定版本不存在
- **WHEN** `registry.version` 为 registry 中不存在的 tag `v9.9.9`
- **THEN** 以退出码 1 与 `registry_fetch_failed` 失败，`<home>/schemas/` 与锁文件均未被修改

#### Scenario: 不执行仓库中的 hook 与过滤器
- **WHEN** registry 仓库包含 `.gitattributes` 过滤器声明与任意文件
- **THEN** 拉取过程中不会创建工作区，也不会执行任何过滤器或 hook

### Requirement: 远程树的读取与校验

系统 SHALL 从上游 commit 的 git 对象中读取 registry 内容（不经工作区）。registry `path` 下每个满足 kebab-case 且含 `schema.yaml` 的一级目录 SHALL 视为一个 schema，全部 schema SHALL 被同步（全量同步）；registry 根下不属于任何 schema 目录的文件 SHALL 被忽略。符号链接与子模块条目 SHALL 被列入 `unsupported` 且永不写入。每个文件路径的每一段 SHALL 为安全相对路径且不为 `.git`，不满足的条目 SHALL 被列入 `unsupported`。单文件超过 1 MiB 或文件总数超过 2000 时 SHALL 以 `registry_invalid` 失败且不写入任何文件。

#### Scenario: 全量同步所有 schema
- **WHEN** registry 含 `team-flow/` 与 `docs-only/` 两个 schema，本地都没有
- **THEN** 计划中两个 schema 的全部文件均为 `upstream-added`

#### Scenario: 符号链接被拒绝
- **WHEN** registry 中 `team-flow/instructions` 是指向 `/etc` 的符号链接
- **THEN** 该条目出现在 `unsupported` 中，暂存区与 `<home>/schemas/` 中都不会出现该链接或其目标的内容

#### Scenario: 子模块被拒绝
- **WHEN** registry 中 `team-flow/vendor` 是一个子模块
- **THEN** 该条目出现在 `unsupported` 中且不被拉取

#### Scenario: 超大文件
- **WHEN** registry 中某文件大于 1 MiB
- **THEN** 以退出码 1 与 `registry_invalid` 失败，不写入暂存区之外的任何文件

### Requirement: 锁文件与三方分类

`<home>/registry.lock.yaml` SHALL 记录上次同步的 registry 配置、上游 commit、上游 tag（无则为 `null`）、每个 schema 同步时的 `version`，以及每个已同步文件的 `sha256` 内容哈希；它 SHALL 仅由 `loopspec schemas apply` 写入，且读取时 SHALL 被严格校验（未知字段、非法路径键、非法 commit 或哈希格式均以 `config_invalid` 失败）。`loopspec schemas update` SHALL 以锁文件哈希为基线（B）、本地文件哈希（L）、上游文件哈希（U），按下表对 registry 与本地中出现的每个 schema 文件分类：

- L = U：`unchanged`
- B 存在、L = B、U ≠ B：`upstream-modified`（U 缺失时为 `upstream-deleted`）
- B 存在、U = B、L ≠ B：`local-modified`（L 缺失时为 `local-deleted`）
- B 存在、L ≠ B、U ≠ B、L ≠ U：`conflict`
- B 缺失、L 缺失、U 存在：`upstream-added`
- B 缺失、U 缺失、L 存在：`local-only`
- B 缺失、L 与 U 均存在且不同：`conflict`

本地为符号链接的文件 SHALL 列入 `unsupported`，不读取、不覆盖。锁文件中的 registry 与当前配置不一致时 SHALL 产生 warning，并把 base 内容视为不可用。

#### Scenario: 仅上游修改
- **WHEN** 锁文件记录 `team-flow/schema.yaml` 的哈希为 H，本地内容哈希仍为 H，上游已修改
- **THEN** 该文件分类为 `upstream-modified`

#### Scenario: 仅本地修改
- **WHEN** 本地修改了 `team-flow/templates/design.md`，上游该文件与基线相同
- **THEN** 该文件分类为 `local-modified`，计划中不对其提出任何写入

#### Scenario: 双方都修改
- **WHEN** 本地与上游都修改了 `team-flow/instructions/design.md` 且内容不同
- **THEN** 该文件分类为 `conflict`

#### Scenario: 首次同步
- **WHEN** 没有锁文件，本地 `team-flow/schema.yaml` 与上游不同，本地另有私有 schema `my-flow`
- **THEN** `team-flow/schema.yaml` 为 `conflict`，`my-flow` 下的文件全部为 `local-only`

#### Scenario: 上游删除仍在使用的 schema
- **WHEN** 上游删除了整个 `team-flow`，而 `config.yaml` 的 `schema` 为 `team-flow`
- **THEN** `team-flow` 的文件均为 `upstream-deleted`，`schemas[]` 中该 schema 的 `deletedUpstream` 为 `true`，且 `warnings` 指出它仍被引用

#### Scenario: 锁文件被篡改
- **WHEN** 锁文件 `files` 中出现键 `../../etc/passwd`
- **THEN** 以退出码 1 与 `config_invalid` 失败

### Requirement: loopspec schemas update 输出比对计划

`loopspec schemas update [--home <dir>] [--json]` SHALL 拉取 registry、生成比对计划，并 SHALL NOT 修改 `<home>/schemas/` 与锁文件；其写入范围 SHALL 仅限 `<home>/.cache/registry/`，且该目录首次创建时 SHALL 写入内容为 `*` 的 `.gitignore`。对每个非 `unchanged` 的文件，系统 SHALL 把上游内容与（可用时的）base 内容物化到暂存区。`--json` 响应 SHALL 至少包含 `registry`、`baseCommit`、`upstreamCommit`、`baseTag`、`upstreamTag`、`latestTag`、`baseAvailable`、`upToDate`、`planId`（`upToDate` 且未生成计划时为 `null`）、`schemas`（每项含 `name`、`deletedUpstream`、`localVersion`、`upstreamVersion`、`baseVersion`）、`files`（每项含 `path`、`status`、`localPath`、`upstreamPath`、`basePath`，不存在时为 `null`）、`unsupported`、`warnings`、`nextSteps`。全部路径 SHALL 为 workflow home 内的绝对路径。

#### Scenario: 已是最新
- **WHEN** 锁文件 commit 与上游 commit 相同，且本地无改动
- **THEN** `upToDate` 为 `true`，`files` 中没有待确认变更与冲突

#### Scenario: update 不修改本地 schema
- **WHEN** 存在 `upstream-modified` 与 `conflict` 文件时执行 `loopspec schemas update --json`
- **THEN** 执行前后 `<home>/schemas/` 与 `registry.lock.yaml` 的文件集合与内容完全一致

#### Scenario: 提供三方合并素材
- **WHEN** 某文件为 `conflict` 且 base 可用
- **THEN** 其 `localPath`、`upstreamPath`、`basePath` 均指向存在的文件，内容分别为本地、上游与基线版本

### Requirement: loopspec schemas apply 按计划写入

`loopspec schemas apply --plan <planId> [--resolve <path>=local|upstream]... [--skip <path>]... [--home <dir>] [--json]` SHALL 按最新计划写入 `<home>/schemas/` 并更新锁文件。系统 SHALL 在写入任何文件之前完成以下全部校验，任一失败即不写入：

1. `planId` 等于最新计划的 id，否则 `registry_plan_stale`。
2. 每个 `conflict` 恰好有一个 `--resolve`；`--resolve` 只能指向 `conflict`，`--skip` 只能指向待确认变更（`upstream-modified`、`upstream-added`、`upstream-deleted`）；缺少解决方案时 `registry_conflict_unresolved`，参数指向不匹配的条目时 `config_invalid`。
3. 除 `--resolve <path>=local` 的条目外，每个条目的本地哈希与计划记录一致，否则 `registry_plan_stale`。
4. 每个受影响 schema 的结果树通过 `load_schema` 校验，否则 `schema_invalid`。

写入时，每个目标路径 SHALL 位于 `<home>/schemas/` 内，目标文件及其每个父目录 SHALL NOT 为符号链接；文件 SHALL 先写入同目录临时文件再原子替换。`upstream-deleted` 只删除计划中列出的文件，之后清理空目录。`--resolve <path>=local` SHALL 采用本地当前内容；`--resolve <path>=upstream` SHALL 采用上游内容。写入成功后，锁文件的 `commit` SHALL 更新为上游 commit，`tag` SHALL 更新为 `upstreamTag`，`schemas.<name>.version` SHALL 更新为各 schema 的 `upstreamVersion`，`files` SHALL 记录每个上游存在文件的上游哈希，被 `--skip` 的条目 SHALL 保留原基线哈希。`local-modified`、`local-deleted`、`local-only`、`unsupported` 条目 SHALL NOT 被修改。

#### Scenario: 应用无冲突的变更
- **WHEN** 计划只含 `upstream-modified` 与 `upstream-added`，执行 `loopspec schemas apply --plan <id> --json`
- **THEN** 本地文件内容变为上游内容，锁文件 `commit` 为上游 commit

#### Scenario: 冲突未解决
- **WHEN** 计划含一个 `conflict`，执行 apply 时未传 `--resolve`
- **THEN** 以退出码 1 与 `registry_conflict_unresolved` 失败，不写入任何文件

#### Scenario: 采用 LLM 写入的合并结果
- **WHEN** 计划生成后，冲突文件的本地内容被改写为合并结果，执行 apply 时传入 `--resolve <path>=local`
- **THEN** 该文件保留合并后的内容，锁文件记录的是上游哈希，下次 update 时该文件分类为 `local-modified`

#### Scenario: 计划生成后本地被改动
- **WHEN** 计划生成后，一个 `upstream-modified` 文件的本地内容被修改，然后执行 apply
- **THEN** 以退出码 1 与 `registry_plan_stale` 失败，不写入任何文件

#### Scenario: 旧计划被新计划取代
- **WHEN** 运行两次 `schemas update`，然后用第一次的 `planId` 执行 apply
- **THEN** 以退出码 1 与 `registry_plan_stale` 失败

#### Scenario: 结果 schema 不可加载
- **WHEN** 应用上游变更后 `team-flow/schema.yaml` 会引用不存在的模板
- **THEN** 以退出码 1 与 `schema_invalid` 失败，`<home>/schemas/` 与锁文件未被修改

#### Scenario: 本地父目录是符号链接
- **WHEN** `<home>/schemas/team-flow` 是指向 workflow home 之外目录的符号链接，计划中有该 schema 的待写入文件
- **THEN** apply 失败且不向链接目标写入任何内容

#### Scenario: 跳过某个变更
- **WHEN** 执行 apply 时对一个 `upstream-modified` 文件传入 `--skip`
- **THEN** 该文件本地内容不变，锁文件保留其原基线哈希，下次 update 时它仍为 `upstream-modified`

### Requirement: 版本选择与 ls-remote 预检

`registry.version` 为 `latest` 时，系统 SHALL 通过 `git ls-remote` 获取远端 tag，从中选出 release tag（匹配 `^v?\d+(\.\d+){0,2}$`，且通过 tag 名校验），按数字大小取最高者作为目标版本；附注 tag SHALL 取其剥离后的 commit；没有任何 release tag 时 SHALL 以默认分支 `HEAD` 的 commit 为目标。`registry.version` 为固定 tag 时，若锁文件的 `tag` 已等于该值，且锁文件的 `registry.url` 与 `registry.path` 与配置一致，系统 SHALL NOT 执行任何 git 命令，并 SHALL 直接返回 `upToDate: true`、`latestTag: null`；否则 SHALL 通过 `git ls-remote` 解析该 tag。

预检解析出的目标 commit 等于锁文件 `commit`，且锁文件的 registry 与配置一致时，`schemas update` SHALL 返回 `upToDate: true`，SHALL NOT 执行 fetch、SHALL NOT 读取远程树、SHALL NOT 生成新计划。`--full` 参数 SHALL 跳过预检，总是执行拉取与全量比对。`ls-remote` 输出中格式不符（`<十六进制 commit>\t<refname>`）、refname 既不以 `refs/tags/` 开头也不等于 `HEAD`、或 tag 名未通过校验的行 SHALL 被丢弃；因 tag 名不合法而丢弃时 SHALL 产生 warning，且 warning 中不回显该 tag 名。

#### Scenario: latest 跟踪最新 release
- **WHEN** registry 有 tag `v1.2.0`、`v1.10.0`、`v2.0.0-rc1`，`version` 为 `latest`
- **THEN** 目标版本为 `v1.10.0`（按数字比较，而不是按字符串；预发布版本被排除）

#### Scenario: 无 release tag 时跟踪默认分支
- **WHEN** registry 没有任何 tag，`version` 为 `latest`
- **THEN** 目标为默认分支 HEAD 的 commit，`upstreamTag` 为 `null`

#### Scenario: 上游无变化时不拉取
- **WHEN** 锁文件 `commit` 等于 `ls-remote` 解析出的目标 commit
- **THEN** 返回 `upToDate: true`，本次只执行了 `ls-remote`，没有执行 `fetch`、`ls-tree` 或 `cat-file`

#### Scenario: 固定版本且已同步时完全离线
- **WHEN** `version` 为 `v1.3.0`，锁文件 `tag` 为 `v1.3.0` 且 registry 配置一致
- **THEN** 返回 `upToDate: true`、`latestTag: null`，且没有启动任何 git 子进程

#### Scenario: 修改固定版本后更新
- **WHEN** `version` 从 `v1.3.0` 改为 `v1.4.0`，执行 `schemas update`
- **THEN** 解析 `v1.4.0` 并拉取，生成从 `v1.3.0` 到 `v1.4.0` 的比对计划

#### Scenario: --full 跳过预检
- **WHEN** 上游无变化，执行 `loopspec schemas update --full --json`
- **THEN** 执行拉取与全量比对，本地被误删的已同步文件以 `local-deleted` 出现在计划中

#### Scenario: 丢弃恶意 ls-remote 行
- **WHEN** 远端存在名为 `v1.0.0$(touch x)` 的 tag
- **THEN** 该 tag 不参与版本选择，`warnings` 中记录一条不含该 tag 名的警告

### Requirement: schema 级与 registry 级版本号的展示

系统 SHALL 复用 `schema.yaml` 既有的 `version` 字段作为 schema 级版本号：`localVersion` 与 `upstreamVersion` SHALL 分别由本地与上游的 `schema.yaml` 经 `yaml.safe_load` 读取 `version` 得到（不加载完整 schema），缺失、非正整数或 YAML 解析失败时 SHALL 为 `null` 并产生 warning；`baseVersion` SHALL 来自锁文件。某 schema 存在上游侧变化（任一文件的上游哈希与基线哈希不同），而 `upstreamVersion` 不大于 `baseVersion` 时，SHALL 产生 warning，提示上游修改了该 schema 但没有增加 `version`。版本号 SHALL NOT 参与文件分类与合并决策。`loopspec schemas list` 的每个条目 SHALL 新增 `registry` 字段：该 schema 出现在锁文件中时为 `{syncedVersion, syncedTag, syncedCommit}`，否则、或锁文件缺失 / 不合法时为 `null`，且 SHALL NOT 因此让 `list` 失败。

#### Scenario: 报告三个版本
- **WHEN** 本地 `team-flow` 的 `version` 为 3，锁文件记录 3，上游为 5
- **THEN** 计划中 `team-flow` 的 `localVersion` 为 3、`baseVersion` 为 3、`upstreamVersion` 为 5

#### Scenario: 上游改动但未升版本
- **WHEN** 上游修改了 `team-flow/templates/design.md`，但 `team-flow/schema.yaml` 的 `version` 仍为 3，而基线也为 3
- **THEN** `warnings` 中包含该 schema 未升版本的提示，文件仍按哈希分类为 `upstream-modified`

#### Scenario: 版本号不影响分类
- **WHEN** 上游只把 `schema.yaml` 的 `version` 从 3 改为 4，其余文件不变
- **THEN** 只有 `team-flow/schema.yaml` 被分类为变更，其余文件为 `unchanged`

#### Scenario: schemas list 显示同步版本
- **WHEN** 锁文件记录 `team-flow` 同步于 tag `v1.3.0`、version 3，执行 `loopspec schemas list --json`
- **THEN** `team-flow` 条目的 `registry` 为 `{syncedVersion: 3, syncedTag: v1.3.0, syncedCommit: <commit>}`，本地私有 schema 的 `registry` 为 `null`
