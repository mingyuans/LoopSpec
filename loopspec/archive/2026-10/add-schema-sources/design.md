## Context

- 现状：schema 只从 `<home>/schemas/<name>/` 加载（`paths.schema_dir`），这些目录是各项目自己的副本，`loopspec init` 从 `builtin/schemas` 复制而来。没有任何「上游」的概念，也没有子进程或网络调用。
- 本次方向由 approval 第 1 轮（`approval/changes-requested.md`）与随后的澄清确定：单个 registry（git 仓库，通常在 GitHub）；**全量**同步其中的所有 schema；CLI 只负责拉取、比对、按指令写入；合并决策由新 skill 驱动的 LLM 与用户确认完成；无冲突的变更也要经用户一次确认；拉取使用本机 `git`。
- 运行时查找（从外部目录直接加载 schema）的旧方案已被否决：schema 仍然**只**从 `<home>/schemas/` 加载，本次不改动任何既有 schema 加载路径。
- 约束：不新增 Python 依赖；无 `registry` 配置时所有既有命令行为不变；`.workflow.yaml` 格式不变。
- 安全面（security gate 重点）：本次首次引入 (1) 子进程执行 `git`；(2) 网络拉取；(3) 把来自远程仓库的路径与内容写入本地；(4) 远程内容最终会作为 agent 指令被读取。

## Goals / Non-Goals

**Goals:**
- 在 `config.yaml` 声明一个 registry，`loopspec schemas update` 输出一份可被 LLM 直接消费的三方比对计划，`loopspec schemas apply` 按计划安全写入。
- 让人一眼看懂版本：每个 schema 的本地 / 上次同步 / 上游版本，以及 registry 的 tag（D9）。
- 基线（上次同步状态）随项目提交，团队成员共享同一基线，使「本地改过」与「上游改过」可区分。
- 新 skill 让「更新 schemas」成为一句自然语言指令，所有写入都经过用户确认。
- 所有来自配置、锁文件与远程仓库的输入都视为不可信，并在进入子进程或文件系统之前校验。

**Non-Goals:**
- 多个 registry、部分同步、HTTP 归档下载、向上游推送。
- CLI 自动合并或在无确认时写入。
- 在 `config.yaml` 或锁文件中保存凭据；loopspec 不处理认证，完全依赖用户本机的 git 凭据配置（SSH agent、credential helper）。
- 改变 schema 的加载方式或给既有 schema 加载路径加新的包含性检查（见 Open Questions）。

## Decisions

### D1：配置形态
```yaml
registry:
  url: git@github.com:acme/loopspec-schemas.git
  version: latest  # 可选，缺省 latest；或固定版本，如 v1.3.0（D10）
  path: schemas    # 可选；仓库内存放 <name>/schema.yaml 的子目录，缺省为仓库根
```
`RegistrySpec` 使用 `extra: forbid`。校验（任一失败即 `config_invalid`，消息不回显 URL 中的 userinfo）：
- `url`（**安全：进入子进程前的第一道校验**）：长度 ≤ 2048；不含空白与控制字符；不以 `-` 开头；不含 `::`（拒绝 `ext::` 等 transport 语法）；只接受四种形态——`https://host/...`、`ssh://[user@]host/...`、scp 形态 `user@host:path`、`file:///abs/path`（用于本地 / 单仓场景与测试）。`https://` 形态**不得包含 userinfo**（拒绝 `https://user:token@...` 与 `https://token@...`），消息提示改用 credential helper。`http://`、`git://` 被拒绝（无传输完整性）。
- `version`：`latest`，或一个 release tag 名。tag 名须满足 `^[A-Za-z0-9._+-]{1,200}$`，不以 `-` 或 `.` 开头、不以 `.lock` 结尾、不含 `..`、`@{`（D10）。不支持分支跟踪与 semver 范围（approval 第 2 轮后的澄清）。
- `path`：既有的安全相对路径规则（`paths.is_safe_relative_path`）。
- 备选：只接受 `github.com`。否决：GitHub Enterprise、GitLab 与本地 `file://` 都是合理场景，且主机名限制并不增加安全性——危险的是 transport 与参数注入，已被上述规则挡掉。

### D2：git 子进程调用约束（安全）
全部 git 调用集中在 `registry.py` 的一个函数 `_run_git(args, cwd)` 中：
- `subprocess.run([...], shell=False)`，参数为列表；URL 与 refname 之前一律加 `--` 结束选项解析（`git fetch --no-tags -- <url> <refspec>`）。
- 每次调用前置 `-c protocol.allow=never -c protocol.<scheme>.allow=always`，`<scheme>` 由 D1 解析出的形态决定（`https` / `ssh` / `file`）。这同时禁止了 `ext`、重定向到其他协议与子模块协议滥用。
- 环境：继承用户环境（凭据 helper、SSH agent 需要），额外设置 `GIT_TERMINAL_PROMPT=0`（无凭据时失败而不是挂起等待输入）。loopspec 自身不读取、不打印任何环境变量。
- 超时 300 秒；`git` 不在 PATH 中 → `registry_unavailable`；非零退出或超时 → `registry_fetch_failed`，消息包含退出码与 stderr 的最后 20 行（截断到 2000 字符）。由于 D1 已拒绝带 userinfo 的 https URL，stderr 中不会出现配置里的凭据。
- 仓库为 loopspec 私有的**裸仓库** `<home>/.cache/registry/repo.git`，只执行 `ls-remote`、`init --bare`、`fetch`、`rev-parse`、`ls-tree`、`cat-file`，**从不 checkout 工作区**——因此不会执行仓库中的任何 hook、过滤器或 LFS 配置，远程仓库中的符号链接也不会在磁盘上被创建。
- 备选：`git clone` 出工作区再遍历文件。否决：工作区 checkout 会在磁盘上物化符号链接、触发 smudge/filter 配置，且遍历工作区时难以区分文件类型。

### D3：拉取
- 只有 D10 的预检判定「需要拉取」时才执行 fetch。目标 commit 由预检解析得出（一个 tag 或默认分支 HEAD），执行 `git fetch --no-tags -- <url> +<refname>:refs/loopspec/upstream`，其中 `<refname>` 为 `refs/tags/<tag>` 或 `HEAD`；然后 `rev-parse refs/loopspec/upstream^{commit}`，结果必须等于预检解析出的 commit，否则 `registry_fetch_failed`（远端在两步之间发生了变化）。
- 若锁文件记录的基线 commit 不在本地裸仓库中，额外 `fetch -- <url> <baseCommit>`；失败不报错，计划中 `baseAvailable: false`——分类只需要锁文件里的哈希（D5），base 内容只用于给 LLM 提供三方合并的参照。

### D4：远程树的读取与校验（安全：不可信路径与内容）
- `git ls-tree -r -z --full-tree <commit> -- <path>`（`-z` 避免文件名转义与换行注入）。只接受 mode `100644` / `100755` 的 blob；`120000`（符号链接）与 `160000`（子模块）记入计划的 `unsupported`，**永不写入**。
- 路径相对 registry `path` 后，第一段为 schema 名：必须满足 `KEBAB_RE` 且该目录下存在 `schema.yaml` 才算一个 schema；registry 根下的其他文件（如 `README.md`）忽略。其余每一段必须通过 `is_safe_relative_path`，且不得为 `.git`。
- 限额：单文件 ≤ 1 MiB（先 `cat-file -s` 查大小再读取），总文件数 ≤ 2000；超限 → `registry_invalid`，不写任何东西。
- 内容一律按字节处理，哈希为 `sha256:<hex>`。

### D5：锁文件与三方分类
`<home>/registry.lock.yaml`（随项目提交，由 `apply` 生成）：
```yaml
registry: {url: ..., version: latest, path: schemas}
commit: <上游 commit>
tag: v1.3.0          # 同步时上游 commit 的精确 tag；没有则为 null（D9）
schemas:
  secure-spec-driven: {version: 3}   # 同步时上游 schema.yaml 的 version（D9）
files:
  secure-spec-driven/schema.yaml: sha256:...
```
锁文件是被提交的文件，同样视为不可信输入：用 pydantic 严格校验（`extra: forbid`；键须为 `<kebab>/<安全相对路径>`；commit 为 40 或 64 位十六进制；哈希格式固定），不合法 → `config_invalid`。锁文件中的 registry 与当前配置不一致时，产生 warning 并把 base 内容视为不可用，但哈希仍用于分类。

对每个文件 `p`，令 B = 锁中哈希，L = 本地哈希，U = 上游哈希（缺失记为 ∅）：

| 条件 | 分类 | 动作 |
| --- | --- | --- |
| L = U | `unchanged` | 无 |
| B ≠ ∅，L = B，U ≠ B | `upstream-modified` / `upstream-deleted`（U = ∅） | 待确认变更 |
| B ≠ ∅，U = B，L ≠ B | `local-modified` / `local-deleted`（L = ∅） | 无（保留本地） |
| B ≠ ∅，L ≠ B，U ≠ B，L ≠ U | `conflict` | 必须逐个解决 |
| B = ∅，L = ∅，U ≠ ∅ | `upstream-added` | 待确认变更 |
| B = ∅，U = ∅，L ≠ ∅ | `local-only` | 无 |
| B = ∅，L ≠ ∅，U ≠ ∅，L ≠ U | `conflict`（双方新增） | 必须逐个解决 |

首次同步没有锁文件，所有文件都落入 B = ∅ 的几行——与上游一致的文件是 `unchanged`，不一致的是 `conflict`，这正是首次接入时需要人工确认的内容。本地是符号链接的文件记为 `unsupported`，不读取、不覆盖。上游删除了整个 schema 时，计划在 schema 级标记 `deletedUpstream: true`，并在该 schema 仍被 `config.yaml` 或活跃 change 的 `.workflow.yaml` 引用时追加 warning。

### D6：`schemas update` 的输出与暂存区
- 不修改 `<home>/schemas/` 与锁文件。写入范围仅限 `<home>/.cache/registry/`：首次创建时写入内容为 `*` 的 `.gitignore`，使缓存目录自行被 git 忽略，无需改动用户的 `.gitignore`。
- 计划写入 `<home>/.cache/registry/plan.json`，包含 `planId`（计划内容的哈希）、上游与基线 commit，以及每个条目的 B/L/U 哈希。对所有非 `unchanged` 的条目，把上游与（如可用的）base 内容物化到 `staging/<planId>/upstream|base/<p>`，供 LLM 读取。
- JSON 响应：`registry`、`baseCommit`、`upstreamCommit`、`baseTag`、`upstreamTag`、`latestTag`、`baseAvailable`、`upToDate`、`planId`、`schemas[]`（`name`、`deletedUpstream`、`localVersion`、`upstreamVersion`、`baseVersion`）、`files[]`（`path`、`status`、`localPath`、`upstreamPath`、`basePath`，不存在则为 `null`）、`unsupported[]`、`warnings`、`nextSteps`。所有路径为绝对路径，且全部位于 workflow home 内。
- 暂存与缓存路径全部经 `paths.resolve_within(<home>/.cache/registry, ...)` 计算。

### D7：`schemas apply` 的写入规则（安全）
`loopspec schemas apply --plan <planId> [--resolve <path>=local|upstream]... [--skip <path>]... [--json]`：
1. `planId` 必须等于最新 `plan.json` 的 id，否则 `registry_plan_stale`。
2. 每个 `conflict` 必须恰好有一个 `--resolve`；`--resolve` 只能指向 conflict，`--skip` 只能指向待确认变更；违反 → `registry_conflict_unresolved` / `config_invalid`。`local` 表示「采用本地当前内容」——即 LLM 在用户确认后已写入本地文件的合并结果，或原样保留。
3. 重新计算所有条目的本地哈希；除 `--resolve <p>=local` 的条目外，任何与计划记录不一致 → `registry_plan_stale`（防止在计划生成后被改动的本地文件被静默覆盖）。
4. 先在 `<home>/.cache/registry/preview/` 构建每个受影响 schema 的结果树，并对其调用 `load_schema`；任一失败 → `schema_invalid`，不写入任何文件。
5. 写入 `<home>/schemas/`：目标路径经 `resolve_within(<home>/schemas, p)`，并要求目标文件本身及其每个父目录都不是符号链接；先写同目录临时文件再 `os.replace`。删除只删除计划中列出的文件，之后清理空目录。
6. 更新锁文件：`commit` = 上游 commit；`tag` = `upstreamTag`；`schemas` = 每个上游 schema 的 `upstreamVersion`；`files` = 所有上游存在的文件取 U，被 `--skip` 的条目保留原 B（下次仍会出现）。清理本计划的暂存目录。
- 备选：让 LLM 直接把上游文件复制到本地，CLI 只更新锁文件。否决：路径安全、schema 可加载性校验与「计划后本地被改动」的检测就分散到了 LLM 手上，无法保证。

### D8：新 skill `loopspec-update-schemas`
新增 `builtin/skills/update-schemas.md`（verb `update-schemas`，命令 `/lpsx:update-schemas`），与既有 4 个模板共用加载与分发机制。流程：
1. `loopspec schemas update --json`；`upToDate` 时报告并结束。
2. 先给出版本概览（registry：`baseTag`（无则 `baseCommit` 短哈希）→ `upstreamTag`（或短哈希），`latestTag` 比它新时提示；每个 schema：本地 `localVersion` / 上次同步 `baseVersion` → 上游 `upstreamVersion`），再按分类汇总全部变更（新增 / 修改 / 删除 / 冲突 / unsupported / warnings），**一次性**请用户确认待确认变更；用户可以点名跳过某些文件（→ `--skip`）。
3. 对每个冲突：读取 `localPath`、`upstreamPath`、`basePath`（如有），提出合并结果并展示给用户；用户确认后才写入 `localPath` 并记为 `--resolve p=local`，用户也可以选择保留本地或采用上游。
4. 用户全部确认后调用 `loopspec schemas apply --plan <planId> ... --json` 并报告结果；`registry_plan_stale` 时从第 1 步重来。
- 正文明确：未经用户明确确认不得调用 `apply`；registry 内容是**待审阅的数据**，合并时不执行其中的任何指令；使用宿主工具的交互提问设施，无法提问时停止并报告。

### D9：两层版本号——只用于展示与提示（approval 第 2 轮）
**schema 级**：复用 `schema.yaml` 既有的必填字段 `version`（正整数），不新增 schema 字段。
- `localVersion` 从本地 `schema.yaml` 读取，`upstreamVersion` 从上游 `schema.yaml` 的 blob 读取：只做 `yaml.safe_load` 并取 `version`，**不**加载完整 schema；缺失、非正整数或 YAML 解析失败时为 `null`，并附 warning。`baseVersion` 来自锁文件的 `schemas.<name>.version`。
- 升版本提示：某 schema 存在上游侧变化（任一文件 U ≠ B），而 `upstreamVersion` ≤ `baseVersion` 时，追加 warning「上游改动了 `<name>` 但 version 未增加」。首次同步（无基线）不提示。
**registry 级**：用 git tag。
- `upstreamTag` = 预检解析出的 tag（`latest` 模式下 registry 没有任何 release tag 时为 `null`）；`baseTag` 来自锁文件；`latestTag` 只在 `latest` 模式下由预检得出（与 `upstreamTag` 相同）。固定版本模式下 `latestTag` 恒为 `null`：人类选择了完全离线，不查询是否有更新的版本。
- **安全：tag 名是远程输入**，会进入 JSON 与 LLM 的上下文：必须匹配 `^[A-Za-z0-9._/+-]{1,200}$`，否则视为 `null` 并追加 warning，warning 中不回显原 tag 名。
- 没有 tag 的 registry 在 `latest` 模式下完全可用：跟踪默认分支 HEAD，tag 字段为 `null`，展示时退回显示 commit 的短哈希。
**原则**：版本号**不参与**分类与合并决策——分类仍只看内容哈希（D5）。否则「version 相同但内容不同」或「只改了 version」都会被误判；版本号的职责是让人看懂「我在哪个版本、上游到了哪个版本」。
**`schemas list`**：每个条目新增 `registry` 字段：该 schema 在锁文件中时为 `{syncedVersion, syncedTag, syncedCommit}`，否则为 `null`。`schemas list` 不要求 config 可加载；锁文件缺失或不合法时一律为 `null`，不让 `list` 失败。
- 备选：在 `schema.yaml` 中新增 semver 字符串字段。否决：已有整数 `version`，新增字段需要改 schema 模型与全部既有 schema，而 registry 级的 semver 已经由 git tag 承担。

### D10：版本选择与 ls-remote 预检——没有变化就不拉取（approval 第 2 轮后的澄清）
动机：每次都 fetch 再全树比对太慢。GitHub Release 以 git tag 为载体，因此「版本」以 tag 为准，用 `git ls-remote`（只列出远端 ref，不下载对象，复用本机 git 凭据）完成版本比对；不引入 GitHub API、`gh` 或 token。

`registry.version` 的两种写法：
- **`latest`（默认）**：执行 `git ls-remote --tags -- <url>`（外加 `HEAD`）。从 tag 中选出 **release tag**：匹配 `^v?\d+(\.\d+){0,2}$`（不含 `-rc` 之类的预发布后缀）且通过 D9 的 tag 名校验；按数字元组取最大者。附注 tag 取剥离后（`^{}` 行）的 commit，因为锁文件记录的是 commit。没有任何 release tag 时，退回跟踪默认分支 `HEAD` 的 commit。
- **固定版本（如 `v1.3.0`）**：锁文件的 `tag` 已等于该版本、且锁文件的 `registry.url` / `path` 与配置一致时，**完全离线**：不执行任何 git 命令，直接返回 `upToDate: true`（不查询是否有更新的版本）。否则（首次同步，或配置改了版本）执行 `git ls-remote --tags -- <url> refs/tags/<version>` 解析该 tag；tag 不存在 → `registry_fetch_failed`。

预检结果：
- 解析出的目标 commit 等于锁文件的 `commit`，且锁文件的 `registry` 与配置一致 → 返回 `upToDate: true`，**不 fetch、不读树、不生成新计划**。本地文件的改动（`local-modified` 等）本来就不需要任何动作，因此不必为它扫描本地。
- 否则进入 D3 的拉取与 D5 的全量比对。
- `schemas update --full` 跳过预检，总是执行拉取与比对（用于排查，或在本地误删文件之后复原）。

安全：`ls-remote` 同样只经 `_run_git`，参数之前有 `--`；它的输出是远程输入——每行必须是 `<40 或 64 位十六进制>\t<refname>`，refname 必须以 `refs/tags/` 开头或等于 `HEAD`，否则丢弃该行；tag 名同样经过 D9 的校验。
- 备选：GitHub Releases API（通过 `gh` 或 HTTP）。否决（人类选择）：只适用于 GitHub，还需要 loopspec 处理 token；`ls-remote` 同样快，且沿用本机 git 凭据。
- 备选：semver 范围（`^1.3`）与分支跟踪（`branch: main`）。否决（人类选择）：保持只支持 `latest` 与固定版本。

## Risks / Trade-offs

- [registry 内容最终成为 agent 指令，能写 registry 的人可以影响所有项目的 agent 行为] → 所有写入都经用户逐项确认（D8），skill 明确把上游内容当作待审阅的数据；文档建议 registry 开启分支保护与代码评审。这是共享 schema 的内在风险，已接受。
- [调用 `git` 引入命令 / 参数注入与协议滥用面] → D1 的 URL / version 白名单 + D2 的 `shell=False`、`--`、`protocol.allow=never` 白名单协议、不 checkout 工作区。
- [恶意 registry 通过路径、符号链接、子模块或超大文件攻击本地] → D4 只读 blob、拒绝链接与子模块、逐段校验路径、限额；D7 写入时再做包含性与符号链接检查。
- [凭据泄露] → 拒绝 URL 内嵌凭据；不读取、不打印环境变量；stderr 截断输出。loopspec 不接触 token。
- [计划生成后本地文件被改动或 LLM 写错文件] → D7 第 3 步哈希复核；预览树中先做 `load_schema` 校验。
- [首次接入时所有有差异的文件都是冲突，工作量大] → 符合预期：首次同步本来就需要人工逐个判断；skill 汇总展示可降低成本。
- [需要本机安装 git，且拉取需要网络] → 只有 `schemas update` 需要；其他命令完全离线。缺失 git 时给出明确的 `registry_unavailable`。
- [registry 维护者忘记升 `version` 或打 tag，版本号与实际内容脱节] → 分类只看哈希，版本号脱节不会导致错误写入；D9 的升版本 warning 会在每次 update 时提示。
- [固定版本完全离线，不会提示有更新的版本] → 人类的明确选择；想了解新版本时，可以临时把 `version` 改为 `latest` 再执行 update。
- [预检只看上游 commit，若有人在本地误删了已同步的文件，默认 update 不会发现] → 误删在 `local-deleted` 分类下本来也不会被恢复；需要时用 `--full` 触发全量比对。
- [并发执行两次 `update`] → 后一次覆盖 `plan.json`，前一次的 `apply` 因 planId 不匹配被拒绝（`registry_plan_stale`），不会写入过期计划。

## Migration Plan

- 无需迁移：`registry` 可选，缺省即现状。首次配置后运行一次「更新 schemas」生成锁文件并提交。
- 回滚：删除 `config.yaml` 中的 `registry` 与 `registry.lock.yaml`，本地 schema 副本保持最后一次同步后的状态；删除 `<home>/.cache/registry/` 无副作用。

## Open Questions

- 第 1 轮 security 指出的既有缺口（schema 内 `instructions/`、`templates/` 子目录自身为符号链接时，包含性检查失效）在新模型下不再有外部写入路径：registry 永远不会写入符号链接（D4/D7）。本次不修复该缺口，建议作为独立的加固变更处理。
