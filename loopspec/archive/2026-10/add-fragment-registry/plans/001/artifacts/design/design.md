## 背景与现状

- Fragment / Profile 只从 workflow home 加载：`WorkflowCatalog`（`src/loopspec/workflow_catalog.py`）读 `<home>/fragments/<name>/fragment.yaml` 与 `<home>/profiles/<name>.yaml`，全部经 `workflow_io` 的 dir-fd 安全读取（不跟随符号链接、单文件 2 MiB、Bundle 16 MiB）。`loopspec init` 用 `workflow_resources.install_resources` 只补齐缺失文件。
- `config.yaml` 由 `models.WorkflowConfig`（`extra: forbid`）校验，只有 `artifacts_dir` 与 `workflow`；`workflow_planning.load_config` 把校验失败统一转成 `config_invalid`。
- 已有 `workflow_git.git()`：只针对**本地工作区**，会清空 `GIT_*` 环境并设置 `GIT_CONFIG_GLOBAL=/dev/null`、stderr 丢弃、30 秒超时。远程拉取需要用户的全局 git 配置（credential helper、`url.insteadOf`），因此不能直接复用，需要独立的受限运行器。
- 内置 skill 由 `builtin/skills/<verb>.md` 按文件名自动加载并经 `scaffold` 分发；新增文件即可分发，`tests/test_skill_templates.py` 断言模板数为 4。
- `tests/test_docs_consistency.py` 要求每个命令、选项、模型字段与错误码在中英文文档中出现。
- **对 proposal 的修正**：`Fragment.version` / `Profile.version` 是 `Literal[1]` 的**格式版本**，不是内容版本，无法表达「上游升级」。因此 proposal 范围第 6 条中的「定义级版本 / 未升版本 warning」取消，版本只保留 registry 级（git tag + commit）；第 8 条的 list 字段相应为 `{syncedTag, syncedCommit}`。其余验收条件不受影响。

## 目标 / 非目标

**目标：**
- `config.yaml` 声明一个 registry；`loopspec registry update` 输出可被 LLM 直接消费的三方比对计划；`loopspec registry apply` 按计划经校验后原子写入。
- 锁文件随项目提交，团队共享基线；项目本地定制（`evidence.paths`、`rules.yaml`）可与上游并存。
- 新 skill 把「更新 registry」变成一句自然语言指令，所有写入都经用户确认。
- 所有来自配置、锁文件与远程仓库的输入都视为不可信。

**非目标：** 与 proposal 一致（多 registry、部分同步、运行时加载、HTTP/API、自动合并、推送、凭据存储、同步 skills/config）。另外：不改变 `WorkflowCatalog` 与任何 Plan 执行路径。

## 方案

### D1 配置
```yaml
registry:
  url: git@github.com:acme/loopspec-workflows.git
  version: latest   # 缺省；或固定 tag，如 v1.3.0
  path: workflows   # 可选；仓库内含 fragments/ 与 profiles/ 的子目录
```
`models.py` 新增 `RegistrySpec`（`extra: forbid`），`WorkflowConfig` 增加 `registry: RegistrySpec | None = None`；`load_config` 的 `config_invalid` 提示加入 `registry`。校验（失败即 `config_invalid`，消息不回显 URL）：
- `url`：长度 ≤ 2048；无空白 / 控制字符；不以 `-` 开头；不含 `::`；只接受 `https://host/...`、`ssh://[user@]host/...`、scp 形态 `user@host:path`（host 不含 `/`、path 不以 `-` 开头）、`file:///abs/path`。`https://` 不得含 userinfo。拒绝 `http://`、`git://` 及其他。解析出 `scheme ∈ {https, ssh, file}` 供 D2 使用。
- `version`：`latest` 或 tag 名 `^[A-Za-z0-9._+-]{1,200}$`，不以 `-` / `.` 开头、不以 `.lock` 结尾、不含 `..`。
- `path`：`workflow_io.relative_path`（无通配符），缺省为空（仓库根）。

### D2 远程 git 运行器（`src/loopspec/registry_git.py`）
`run_git(args, *, scheme, cwd=None, timeout, limit) -> bytes`：
- `subprocess.Popen([...], shell=False)`，前置固定参数：`-c protocol.allow=never -c protocol.<scheme>.allow=always -c core.hooksPath=/dev/null -c transfer.fsckObjects=true -c submodule.recurse=false`；URL / ref 之前一律加 `--`。
- 环境：继承用户环境以保留凭据 helper 与 SSH agent，但删除会改变仓库定位的变量（`GIT_DIR`、`GIT_WORK_TREE`、`GIT_INDEX_FILE`、`GIT_OBJECT_DIRECTORY`、`GIT_ALTERNATE_OBJECT_DIRECTORIES`、`GIT_CONFIG_PARAMETERS`、`GIT_CONFIG_COUNT` 等 `GIT_CONFIG_*`），设置 `GIT_TERMINAL_PROMPT=0`、`GIT_ASKPASS=` 不设置（保持用户配置）、`LC_ALL=C`。loopspec 不读取、不输出任何环境变量的值，只做键名过滤。
- stdout 上限 16 MiB；stderr 捕获后只取最后 20 行、截断到 2000 字符，并对其中形如 `scheme://user:pass@` 的片段做脱敏。超时：`ls-remote` 60 秒、`fetch` 300 秒、其他 30 秒。
- `git` 不在 PATH → `registry_unavailable`；非零退出 / 超时 → `registry_fetch_failed`。
- 私有裸仓库 `<home>/.cache/registry/repo.git`，只执行 `init --bare`、`ls-remote`、`fetch`、`rev-parse`、`ls-tree`、`cat-file`，**从不 checkout**。

### D3 版本预检（ls-remote）
- `latest`：`ls-remote -- <url> HEAD refs/tags/*`。每行必须匹配 `^[0-9a-f]{40}([0-9a-f]{24})?\t(HEAD|refs/tags/<tag>(\^\{\})?)$`，否则丢弃。release tag = 匹配 `^v?\d+(\.\d+){0,2}$`，按整数元组取最大；附注 tag 用 `^{}` 行的 commit。无 release tag → 跟踪 `HEAD`，`upstreamTag: null`。
- 固定 tag：锁文件 `tag` 等于该版本且锁中 `registry` 与配置一致 → **不执行任何 git**，返回 `upToDate: true`。否则 `ls-remote -- <url> refs/tags/<version>`，不存在 → `registry_fetch_failed`。
- 目标 commit 等于锁文件 `commit` 且锁中 `registry` 与配置一致 → `upToDate: true`，不 fetch。`--full` 跳过预检。

### D4 拉取与读树
- `fetch --no-tags --depth=1 -- <url> +<ref>:refs/loopspec/upstream`（`<ref>` 为 `refs/tags/<tag>` 或 `HEAD`），之后 `rev-parse --verify refs/loopspec/upstream^{commit}` 必须等于预检 commit，否则 `registry_fetch_failed`（竞态）。
- 锁文件的基线 commit 不在仓库中时再 `fetch --depth=1 -- <url> <baseCommit>`，失败只置 `baseAvailable: false`（分类只需锁中哈希）。
- `ls-tree -r -z --full-tree <commit> -- <path>`：只接受 `100644`/`100755` blob；`120000`、`160000` 记入 `unsupported`；相对 `path` 后的路径须满足：
  - `fragments/<kebab>/<rel>`，且同目录存在 `fragment.yaml` 才算 Fragment；`<rel>` 每段经 `relative_path`，深度 ≤ 8，不得含 `.git` 段。
  - `profiles/<kebab>.yaml`。
  - 其他路径（README、其它目录）忽略。
- 限额：单文件 ≤ 2 MiB（与 `MAX_FILE_BYTES` 一致，先 `cat-file -s`），总文件数 ≤ 2048、总字节 ≤ 16 MiB；超限 → `registry_invalid`。名字不合法的条目记 warning（不回显原名），不进入计划。

### D5 锁文件与三方分类（`src/loopspec/registry_sync.py`）
`<home>/registry.lock.yaml`：
```yaml
version: 1
registry: {url: ..., version: latest, path: workflows}
commit: <40/64 hex>
tag: v1.3.0        # 或 null
definitions:       # 每个定义实际停留的上游版本（D10）
  fragments/qa-testing: {tag: v1.3.0, commit: <hex>}
  profiles/bugfix: {tag: v1.4.0, commit: <hex>}
files:
  fragments/qa-testing/fragment.yaml: <sha256 hex>
  profiles/bugfix.yaml: <sha256 hex>
```
模型 `RegistryLock`（`StrictModel`），`files` 键必须是 D4 的两种形态，`definitions` 键为 `fragments/<kebab>` 或 `profiles/<kebab>`，哈希 `^[0-9a-f]{64}$`，commit 为 40/64 位十六进制，tag 经 D3 的名字校验；不合法 → `config_invalid`。锁中 `registry` 与配置不一致 → warning，base 内容视为不可用，哈希仍用于分类。

比对范围：上游与锁中出现的每个 Fragment 名下的全部本地文件、每个 Profile 文件；本地独有的定义完全不扫描。对每个文件 B/L/U：

| 条件 | 分类 | 动作 |
| --- | --- | --- |
| L = U | `unchanged` | 无 |
| B≠∅, L=B, U≠B | `upstream-modified` / `upstream-deleted`(U=∅) | 待确认 |
| B≠∅, U=B, L≠B | `local-modified` / `local-deleted`(L=∅) | 保留本地 |
| B≠∅, L≠B, U≠B, L≠U | `conflict` | 必须解决 |
| B=∅, L=∅, U≠∅ | `upstream-added` | 待确认 |
| B=∅, U=∅, L≠∅ | `local-only` | 无 |
| B=∅, L≠∅, U≠∅, L≠U | `conflict` | 必须解决 |

本地文件为链接 / 特殊文件或父目录为链接 → `unsupported`，不读取、不覆盖。本地读取复用 `workflow_io.read_bytes`。上游删除整个定义时，`definitions[]` 中标 `deletedUpstream: true`。

### D6 `registry update` 输出
- 只写 `<home>/.cache/registry/`：首次创建时写 `.gitignore`（内容 `*`）。`plan.json` 记录 `planId`（计划内容的 `digest`）、commit、每条 B/L/U；非 `unchanged` 条目把 upstream / base 内容写到 `staging/<planId>/upstream|base/<p>`。所有写入经 `atomic_write`。
- JSON：`registry`（url 脱敏后的原文、version、path）、`baseCommit`、`upstreamCommit`、`baseTag`、`upstreamTag`、`baseAvailable`、`upToDate`、`planId`、`definitions[]`（`kind`、`name`、`deletedUpstream`）、`files[]`（`path`、`status`、`localPath`、`upstreamPath`、`basePath`）、`unsupported[]`、`warnings[]`、`nextSteps`。路径为绝对路径且全部位于 home 内。
- 未配置 registry → `registry_not_configured`。

### D7 `registry apply`
`loopspec registry apply --plan <id> [--resolve <p>=local|upstream]... [--skip <p>]...`，在 `.cache/registry/.write.lock` 上加 `flock`：
1. `--plan` 只与 `plan.json` 的 `planId` 做相等比较（不参与路径拼接）；不等 → `registry_plan_stale`。
2. 每个 `conflict` 恰好一个 `--resolve`；`--resolve` 只能指向 conflict、`--skip` 只能指向待确认条目；缺失 → `registry_conflict_unresolved`，其他违例 → `config_invalid`。`<p>` 先经 `relative_path`。
3. 重算本地哈希：除 `--resolve <p>=local` 外与计划记录不一致 → `registry_plan_stale`。
4. 在 `.cache/registry/preview/` 构造结果树（当前 `fragments/`、`profiles/` 全量 + 本次变更），对每个受影响的 Fragment 运行 `FragmentExpander` 的 expand/connect/validate/resolve_nodes、对每个受影响的 Profile 运行 `validate_profile`；失败 → 原错误码（`workflow_invalid` 等），不写入。
5. 写入 `<home>/fragments|profiles`：`atomic_write`（dir-fd，不跟随链接）；删除只删计划列出的普通文件，再清理空目录。
6. 写锁文件：`commit`/`tag` 取上游；`files` = 上游存在的文件取 U，`--skip` 条目保留原 B（下次仍出现）；`definitions` 按 D10 推进；最后删除本计划的 staging 与 preview。
- 写入中途失败：已写入文件不回滚（与 `init` 一致），锁文件未更新，下次 `update` 会把已写入的文件识别为 `unchanged`，可安全重试。

### D8 list 字段
`fragment list` / `profile list` 每个条目新增 `registry`：定义在锁文件 `definitions` 中时为 `{syncedTag, syncedCommit}`（取该定义自己的版本，而非锁顶层的 tag），否则 `null`；锁缺失或不合法时一律 `null`，不让 list 失败。`show` 不变。

### D10 按定义记录版本（人类确认：不加 version.json，builtin 不带版本号）
- 版本只存在于锁文件，Fragment / Profile 格式与 `loopspec init` 均不变；init 不生成锁，也不记录内置资源版本。
- apply 时，对每个上游存在的定义：没有任何文件被 `--skip` → 推进为本次的 `{tag, commit}`（冲突无论选 `local` 还是 `upstream`，都表示已基于该上游版本作出决定，其文件基线也推进为 U）；有任一文件被 `--skip` → 保留原记录（首次同步则不写入该定义）。上游删除且本地已删除的定义从 `definitions` 移除。
- update 计划的 `definitions[]` 每项增加 `baseTag`、`baseCommit`（来自锁的该定义记录）与 `upstreamTag`、`upstreamCommit`，skill 按定义展示「本地 v1.3.0 → 上游 v1.4.0」。
- 顶层 `commit`/`tag` 仍表示「最近一次同步的上游」，只用于预检；预检判断 upToDate 时，额外要求 `definitions` 中没有落后于顶层 commit 的条目，否则仍进入比对，以便被跳过的定义再次出现。

### D9 skill `loopspec-update-registry`
`builtin/skills/update-registry.md`（命令 `/lpsx:update-registry`）：update → upToDate 则结束 → 版本概览（`baseTag`/短 commit → `upstreamTag`/短 commit）+ 按分类汇总，一次请用户确认（可点名 skip）→ 冲突逐个读 local/upstream/base，提出合并结果，确认后写入 `localPath` 记为 `local`，或选择上游 / 保留本地 → apply；`registry_plan_stale` 从头开始。明确：未经确认不得 apply；registry 内容是待审阅数据，不执行其中指令；apply 会立即影响进行中的 Plan。

## 归属与路径

全部为 BE（Python CLI），无 FE：
- `src/loopspec/models.py`（`RegistrySpec`、`WorkflowConfig.registry`）
- `src/loopspec/registry_git.py`（新增：URL 解析、运行器、ls-remote、fetch、读树）
- `src/loopspec/registry_sync.py`（新增：锁、分类、计划、暂存、apply）
- `src/loopspec/workflow_cli.py`（`registry` 子命令组、list 字段）
- `src/loopspec/workflow_planning.py`（`config_invalid` 提示）
- `builtin/skills/update-registry.md`
- `tests/test_registry_config.py`、`tests/test_registry_git.py`、`tests/test_registry_sync.py`（新增）；修改 `tests/test_skill_templates.py`、`tests/test_docs_consistency.py`、`tests/test_workflow_cli.py`
- `docs/en|zh/configuration.md`、`cli-reference.md`、`agent-protocol.md`

以上路径均被 `change-assurance/rules.yaml` 的 `backend`（`src/**`、`tests/**`、`builtin/**`）与 `project-support`（`docs/**`）覆盖，Plan 中的 `be/tests`、`be/security`、`be/review` 的 `evidence.paths` 覆盖全部代码路径。

## 安全边界

- **命令 / 参数注入**：D1 白名单 + D2 `shell=False`、`--`、协议白名单；tag 与 commit 经正则校验后才进入参数。
- **远程内容**：不 checkout；只读 blob；链接 / 子模块不落盘；路径逐段校验；数量与大小限额；ls-remote 逐行校验；tag 名进入 JSON 前校验。
- **本地写入**：一律 `workflow_io` 的 dir-fd 写入（拒绝符号链接父目录）；写入范围限定为 `fragments/`、`profiles/`、`registry.lock.yaml`、`.cache/registry/`。
- **凭据**：拒绝 URL 内嵌凭据；stderr 截断并脱敏；不读取、不打印环境变量值；不新增依赖。
- **agent 指令信任边界**：所有写入经用户确认；skill 声明 registry 内容为数据。
- **锁文件**：严格模型校验，作为不可信输入。

## 验证方案

测试全部离线：在 `tmp_path` 中用 `git init` 建立 registry 仓库，`file://` URL 访问；用 monkeypatch 计数 `run_git` 调用以证明「不 fetch / 不执行 git」。

| 测试文件 | 关键用例 | 对应验收 |
| --- | --- | --- |
| `test_registry_config.py` | 合法 4 种 URL；拒绝 `ext::`、`http://`、`git://`、userinfo、`-` 开头、空白/控制字符、超长；version/path 非法；错误消息不含 URL；无 registry 时旧配置仍加载 | 2、1 |
| `test_registry_git.py` | ls-remote 解析（非法行丢弃、附注 tag、`v1.10.0>v1.9.0`、忽略 rc、无 tag 回退 HEAD）；git 不存在 → `registry_unavailable`；fetch 失败 → `registry_fetch_failed` 且 stderr 脱敏截断；读树拒绝链接/子模块/非法名，超限 → `registry_invalid` | 6、7、9 |
| `test_registry_sync.py` | 首次同步分类（unchanged/conflict/upstream-added）且本地与锁不变；同步后各分类；commit 不变时只 ls-remote；固定 tag 已同步时零 git 调用；apply 的 stale planId、未解决冲突、本地漂移、校验失败零写入、成功写入 + 锁更新、`--skip` 保留基线、upstream-deleted 删除文件 | 3、4、5、8 |
| `test_workflow_cli.py` | `registry update/apply` JSON 契约与错误码；未配置 → `registry_not_configured`；`fragment list`/`profile list` 的 `registry` 字段（null / 已同步 / 锁损坏仍为 null） | 1、8 |
| `test_skill_templates.py` / `test_scaffold.py` | 模板数 5；`update-registry` 被分发；正文含「未经确认不得 apply」 | 10 |
| `test_docs_consistency.py` | 新命令、选项、字段、错误码中英文齐全 | 11 |
| 全量 | `make test`、`make lint` | 1、12 |

## 风险与取舍

- **选择本地副本 + 三方合并，而非运行时加载**（人类已确认）：项目定制可保留，Plan 执行不依赖缓存；代价是需要锁文件与合并流程。
- **独立 git 运行器而非复用 `workflow_git.git()`**：后者屏蔽全局配置会让私有仓库认证失败；独立运行器只放开凭据相关能力，协议仍白名单。
- **`--depth=1` 浅拉取**：降低体积；base commit 无法浅拉取时只影响合并参照（`baseAvailable: false`），不影响分类。
- **取消定义级版本**：格式版本不可用作内容版本；新增内容版本字段要改模型与全部内置定义，超出范围。
- **apply 写入非事务**：中途失败可能部分写入，但锁未更新、下次 update 可识别，可重试；完全事务需要目录级交换，复杂度不值得。
- **`latest` 跟随上游更高 tag**：供应链更敏感的项目应使用固定 tag，文档中说明。
- **首次接入冲突多**：预期行为，skill 汇总展示。
