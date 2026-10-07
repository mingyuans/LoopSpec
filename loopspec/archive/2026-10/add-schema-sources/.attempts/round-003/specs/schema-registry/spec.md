## ADDED Requirements

### Requirement: 在 config.yaml 中声明 schema registry

`config.yaml` SHALL 接受可选的顶层字段 `registry`，其值为对象，包含必填的 `url`、可选的 `ref` 与可选的 `path`；出现其他字段 SHALL 以 `config_invalid` 拒绝。每个项目最多声明一个 registry。缺省时所有既有命令的行为 SHALL 与未引入本能力时一致，且 `loopspec schemas update` 与 `loopspec schemas apply` SHALL 以 `registry_not_configured` 失败。

`url` SHALL 满足：长度不超过 2048；不含空白与控制字符；不以 `-` 开头；不含 `::`；形态为 `https://`、`ssh://`、scp 形态 `user@host:path` 或 `file:///` 绝对路径之一；`https://` 形态 SHALL NOT 包含 userinfo。`ref` SHALL 匹配 `^[A-Za-z0-9._/-]{1,200}$`，且不以 `-` 或 `/` 开头、不以 `/` 或 `.lock` 结尾、不含 `..`、`//`、`@{`。`path` SHALL 为安全相对路径。任一不满足 SHALL 以 `config_invalid` 失败，错误消息 SHALL NOT 回显 URL 中的 userinfo。

#### Scenario: 合法的 GitHub SSH registry
- **WHEN** `config.yaml` 含 `registry: {url: git@github.com:acme/schemas.git, ref: main}`
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

#### Scenario: 拒绝非法 ref
- **WHEN** `registry.ref` 为 `-oProxyCommand=x`、`a..b` 或 `main.lock`
- **THEN** 以退出码 1 与 `config_invalid` 失败

#### Scenario: 未配置 registry
- **WHEN** `config.yaml` 不含 `registry`，执行 `loopspec schemas update --json`
- **THEN** 以退出码 1 与 `registry_not_configured` 失败；其他命令行为不变

### Requirement: 安全地调用 git 拉取 registry

系统 SHALL 仅通过本机 `git` 可执行文件拉取 registry，使用参数列表且不经 shell，URL 与 ref 之前 SHALL 以 `--` 结束选项解析，并 SHALL 只允许 `url` 形态对应的单一协议（其余协议一律禁止）。拉取 SHALL 使用位于 `<home>/.cache/registry/` 下的 loopspec 私有裸仓库，SHALL NOT checkout 工作区。git 调用 SHALL 设置 `GIT_TERMINAL_PROMPT=0` 并有超时。`git` 不可用时 SHALL 以 `registry_unavailable` 失败；git 非零退出或超时 SHALL 以 `registry_fetch_failed` 失败，消息包含退出码与截断后的 stderr。loopspec SHALL NOT 读取、打印或记录任何环境变量的值。

#### Scenario: 从本地 file:// registry 拉取
- **WHEN** `registry.url` 指向 `tmp_path` 下一个含 `team-flow/schema.yaml` 的本地 git 仓库，执行 `loopspec schemas update --json`
- **THEN** 命令成功，`upstreamCommit` 为该仓库 `ref` 对应的 commit

#### Scenario: git 不可用
- **WHEN** PATH 中没有 `git`，执行 `loopspec schemas update --json`
- **THEN** 以退出码 1 与 `registry_unavailable` 失败

#### Scenario: ref 不存在
- **WHEN** `registry.ref` 为 registry 中不存在的分支
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

`<home>/registry.lock.yaml` SHALL 记录上次同步的 registry 配置、上游 commit，以及每个已同步文件的 `sha256` 内容哈希；它 SHALL 仅由 `loopspec schemas apply` 写入，且读取时 SHALL 被严格校验（未知字段、非法路径键、非法 commit 或哈希格式均以 `config_invalid` 失败）。`loopspec schemas update` SHALL 以锁文件哈希为基线（B）、本地文件哈希（L）、上游文件哈希（U），按下表对 registry 与本地中出现的每个 schema 文件分类：

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

`loopspec schemas update [--home <dir>] [--json]` SHALL 拉取 registry、生成比对计划，并 SHALL NOT 修改 `<home>/schemas/` 与锁文件；其写入范围 SHALL 仅限 `<home>/.cache/registry/`，且该目录首次创建时 SHALL 写入内容为 `*` 的 `.gitignore`。对每个非 `unchanged` 的文件，系统 SHALL 把上游内容与（可用时的）base 内容物化到暂存区。`--json` 响应 SHALL 至少包含 `registry`、`baseCommit`、`upstreamCommit`、`baseAvailable`、`upToDate`、`planId`、`schemas`（每项含 `name`、`deletedUpstream`）、`files`（每项含 `path`、`status`、`localPath`、`upstreamPath`、`basePath`，不存在时为 `null`）、`unsupported`、`warnings`、`nextSteps`。全部路径 SHALL 为 workflow home 内的绝对路径。

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

写入时，每个目标路径 SHALL 位于 `<home>/schemas/` 内，目标文件及其每个父目录 SHALL NOT 为符号链接；文件 SHALL 先写入同目录临时文件再原子替换。`upstream-deleted` 只删除计划中列出的文件，之后清理空目录。`--resolve <path>=local` SHALL 采用本地当前内容；`--resolve <path>=upstream` SHALL 采用上游内容。写入成功后，锁文件的 `commit` SHALL 更新为上游 commit，`files` SHALL 记录每个上游存在文件的上游哈希，被 `--skip` 的条目 SHALL 保留原基线哈希。`local-modified`、`local-deleted`、`local-only`、`unsupported` 条目 SHALL NOT 被修改。

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
