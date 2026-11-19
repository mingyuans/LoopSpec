## 背景与现状

- 定义读取全部以 workflow home 为根：`WorkflowCatalog(home)` 内部用 `ResourceBundle(home)` 读 `fragments/<name>/fragment.yaml`、`profiles/<name>.yaml`；`catalog.resource()` 返回 `fragments/<name>/<file>` 形式的 home 相对路径并写入 Plan 的 `ResolvedNode.instruction/template/gate.assurance`。
- 运行时：`workflow_runtime.resource_text()` 用 `read_bytes(loaded.home, path)` 现场读 instruction/template；`workflow_assurance.live_rules()` 用 `ResourceBundle(loaded.home)` 读 Gate 与 `config.yaml` `workflow.assurance_rules` 指向的规则文件。
- 同步：`registry_sync.update/apply` 做「lock 基线 / 本地 / 上游」三方分类，`apply` 写 `fragments/`、`profiles/` 与 `registry.lock.yaml`（v1：`definitions`、`held`、`files`）。git 访问在 `registry_git.RegistryRepo`：每次新建私有裸仓库、浅拉取、只读 `ls-tree`/`cat-file`，不 checkout。
- `loopspec init` 在 home 没有定义时复制内置 fragments/profiles。

## 目标 / 非目标

**目标：**
- registry 模式下 registry 定义只存在于用户级全局存储，项目只提交 `config.yaml` 与 `registry.lock.yaml`。
- 新 clone / worktree 读取定义时按 lock 自动拉取并校验，所有读取路径（编译、列表、运行时 instruction、assurance 规则）一致。
- 本地同名定义报错；本地独有定义继续可用。

**非目标：** 见 proposal「非目标」，非 registry 项目行为不变；不做本地 overlay、自动迁移、存储 GC。

## 方案

### 1. 全局存储（新模块 `registry_store.py`）

```
$LOOPSPEC_REGISTRY_STORE  (默认 ~/.loopspec/registry)
└── <source-id>/                      source-id = sha256(url + "\n" + (path or ""))[:32]
    ├── <commit>/                     不可变快照
    │   ├── .snapshot.json            {"url","path","commit","files":{path:sha256}}
    │   ├── fragments/<name>/...
    │   └── profiles/<name>.yaml
    └── .tmp-<uuid>/                  写入中的临时目录（含 repo.git 工作仓库）
```

- 根目录逐级以 0700 创建，所有访问走 `workflow_io.directory()`（O_NOFOLLOW 逐级打开），拒绝符号链接。
- 物化 `materialize(spec, commit, tag, expected_files | None) -> Path`：
  1. 若 `<commit>/.snapshot.json` 存在且 url/path/commit 一致、`files` 与期望一致（期望为 None 时只要求自洽）→ 直接返回。
  2. 否则在 `.tmp-<uuid>/` 中用 `RegistryRepo(tmp, spec)` 执行 `fetch_base(commit, tag)`（先按 tag、再按 commit 拉取）+ `read_tree(commit)`；文件 hash 必须与期望完全一致（路径集合与 hash 都相同），否则 `registry_lock_mismatch`。
  3. 写文件与 `.snapshot.json` 到 `.tmp-<uuid>/snapshot/`，删除工作仓库，`os.rename` 到 `<commit>`；目标已存在（并发写入者先完成）→ 删除自己的临时目录，按第 1 步复核已有快照；已有快照损坏（manifest 缺失或不一致）→ 先移走再 rename。
  4. 任何失败都清理临时目录，不留下可被当作完整快照的目录（完整性以 `.snapshot.json` 最后写入 + rename 原子性保证）。
- 读取校验：`DefinitionBundle` 从快照读出的每个文件都按 lock 的 hash 校验，不一致报 `registry_store_corrupt`（fix：删除提示的快照目录后重试，下次会自动重新拉取）。

### 2. lock v2

```yaml
version: 2
registry: {url, version, path}
commit: <40/64 hex>
tag: v1.2.0 | null
files: {fragments/x/fragment.yaml: <sha256>, profiles/y.yaml: <sha256>, ...}
```

- 定义集合由 `files` 推出（`definition_key`）。
- 读取兼容 v1：`held` 为空时用 `commit` + `files` 作为 v2 等价物；`held` 非空（v1 曾跳过部分上游变更，文件 hash 不对应单一 commit）→ `registry_lock_outdated`，提示运行 `registry update` + `apply`。`apply` 总是写 v2。
- lock 的 `registry.url/path` 与 `config.yaml` 不一致 → `registry_lock_mismatch`（提示重新 update/apply）；`version` 不同不影响使用（lock 是锁定版本，`version` 只是 update 的目标）。

### 3. 定义解析层

新增 `definition_bundle(home) -> ResourceBundle`（`registry_store.py`）：

- 未配置 registry（含 `config.yaml` 不存在）→ 返回原 `ResourceBundle(home)`，行为完全不变。
- 配置了 registry：读 lock（缺失 → `registry_not_synced`），`materialize` 得到快照根，返回 `DefinitionBundle(home, snapshot, lock)`：
  - `read(path)`：路径属于 lock 中的定义（`fragments/<name>/...` 且 `fragments/<name>` 在定义集合中，或 `profiles/<name>.yaml` 在其中）→ 从快照读并校验 hash；否则从 home 读（本地独有定义、`config.yaml` 等）。
  - `registry_definitions`：定义 key 集合，供 catalog 列表与冲突检查。
  - 构造时检查本地冲突：home 下存在 `fragments/<name>`（任何类型的条目）或 `profiles/<name>.yaml` 且 `<kind>/<name>` 属于 registry 定义 → `registry_local_conflict`，message 列出全部冲突路径（按名称排序，名称已由 KEBAB 校验，安全回显），fix：删除这些项目内副本（registry 定义由 `registry.lock.yaml` 提供）。
- 同一进程内按 home 缓存快照定位结果（不缓存文件内容之外的东西），避免一次命令重复物化。

接入点：
- `WorkflowCatalog.__init__`：`self.bundle = definition_bundle(home)`；`entries()` 返回 registry 定义 ∪ 本地定义（本地 `fragments/`、`profiles/` 目录不存在时视为空）；每个条目附带来源。
- `workflow_runtime.resource_text`：改为 `definition_bundle(loaded.home).read(path)`。
- `workflow_assurance.live_rules` 与 `workflow_planning.compile_request`：使用 `definition_bundle`（compile 已经走 `catalog.bundle`）。
- 现有 Plan 中保存的 `fragments/<name>/...` 路径不变，由解析层路由，兼容已有 change。

### 4. `fragment list` / `profile list`

每项新增 `source: "registry" | "local"`；registry 项保留现有 `registry: {syncedTag, syncedCommit}`（v2 下所有 registry 定义都等于 lock 的 tag/commit）。

### 5. `profile save`

registry 模式下名称属于 registry 定义 → `profile_exists`（沿用现有错误码，message 说明与 registry 同名），不写文件；否则写入项目 `profiles/`。

### 6. `registry update`

1. 读 spec 与 lock（可为空、可为 v1）。
2. 快速路径：lock 同来源、`version` 为固定 tag 且 `lock.tag == version`、无 `--full` → `upToDate`。
3. 否则 `resolve_target`；同来源且 `target.commit == lock.commit` → `upToDate`。
4. `materialize(spec, target.commit, target.tag, None)`（快照内容按 commit 不可变，提前物化无副作用，且供 apply 复用、供人审阅）。
5. 对比 lock.files（不同来源或无 lock 时视为空，并给出 warning）与快照 files：每个文件 `added | modified | deleted`，汇总为定义级变化。
6. 写计划 `<home>/.cache/registry/plan.json`（`.cache/registry/.gitignore` 已有 `*`）：`plan_id = digest(body)`，body 含 spec、`base`（当前 lock 的 commit 与 files 摘要，无 lock 为 null）、target commit/tag、entries。
7. 输出：`registry`、`upToDate`、`baseCommit/baseTag`、`upstreamCommit/upstreamTag`、`planId`、`definitions`（kind/name/change）、`files`（path、status、`upstreamPath` 指向快照文件、`basePath` 指向旧快照文件（旧快照存在时））、`localConflicts`（目标版本将与本地定义同名的路径）、`warnings`、`nextSteps: ["loopspec registry apply --plan <id>"]`。

### 7. `registry apply --plan <id>`

1. 加载计划并校验 digest、`plan_id` 相等、`spec` 与当前 config 一致、当前 lock 摘要与计划 `base` 一致，否则 `registry_plan_stale`。
2. `materialize(spec, target.commit, target.tag, plan.files)`。
3. 预检：以「新快照 + 本地定义」构造临时 `DefinitionBundle`，检查本地冲突（`registry_local_conflict`），并逐个加载所有 registry 定义与本地定义（与现有 `_validate_preview` 一致：registry 定义必须有效；本地定义原本有效而同步后失效时报错）。
4. 原子写 `registry.lock.yaml`（v2），删除 plan.json。
5. 输出 `applied`、`upstreamCommit/Tag`、`added/modified/deleted`（文件路径列表）、`lock`、`nextSteps: []`。
6. CLI 删除 `--resolve`、`--skip` 选项；registry 模式不再写 `fragments/`、`profiles/`。

旧的 `registry_conflict_unresolved`、三方分类、staging/preview 目录逻辑移除（保留的 `.cache/registry/` 只放 plan.json）。

### 8. `loopspec init`

`config.yaml` 已配置 registry 时不复制内置定义（即使 `--update-resources`），输出提示「registry 模式：定义由 registry.lock.yaml 提供」；避免与 registry 同名而触发冲突。

### 9. 错误码

| 错误码 | 场景 |
|---|---|
| `registry_not_synced` | registry 模式但没有 `registry.lock.yaml` |
| `registry_lock_outdated` | v1 lock 含 `held` |
| `registry_lock_mismatch` | lock 来源与 config 不一致；或拉取内容与 lock hash 不一致 |
| `registry_local_conflict` | 本地有与 registry 同名的定义 |
| `registry_store_corrupt` | 快照文件与 lock hash 不一致 |
| `registry_fetch_failed` / `registry_invalid` | 沿用：拉取失败 / 远端内容不合法 |
| `registry_plan_stale` | 沿用 |

新增错误码加入 `errors.py` 的已知集合（若有）并在中英文 CLI 文档中列出。

### 10. 文档与 skill

- `builtin/skills/update-registry.md`（及 `.claude/skills` 副本若由模板生成则一并更新）：去掉冲突 / resolve / skip 流程；overview 改为版本变化 + 定义/文件 added/modified/deleted + `localConflicts`；仍要求展示 instruction/template/fragment.yaml/profile 的内容 diff（`basePath` vs `upstreamPath`）并提示注入风险；确认后 `apply --plan`；结尾提醒只需提交 `registry.lock.yaml`（及 config.yaml），并说明进行中的 Plan 会立即读取新版本。
- `docs/zh|en/configuration.md`、`cli-reference.md`：registry 模式存储位置、`LOOPSPEC_REGISTRY_STORE`、自动拉取、本地冲突与迁移步骤、新错误码；`release-notes.md` 写破坏性变更与迁移。

## 归属与路径

全部为 BE（Python CLI），仓库 `mingyuans/LoopSpec`：

- 新增：`src/loopspec/registry_store.py`
- 修改：`src/loopspec/registry_sync.py`、`registry_git.py`（如需小调整）、`workflow_catalog.py`、`workflow_runtime.py`、`workflow_assurance.py`、`workflow_planning.py`、`workflow_cli.py`、`cli.py`（init）、`errors.py`（如有错误码表）、`skill_templates.py`（如引用 resolve/skip）
- skill：`builtin/skills/update-registry.md`
- 文档：`docs/zh/*.md`、`docs/en/*.md`、`README.md`（如提及）
- 测试：`tests/test_registry_store.py`（新）、`tests/test_registry_sync.py`、`tests/registry_helpers.py`、`tests/features/registry.feature`、`tests/steps/registry_steps.py`、`tests/conftest.py`（全局 fixture 设置 `LOOPSPEC_REGISTRY_STORE` 到临时目录）、相关 catalog/runtime/cli 测试；LLM E2E 场景（`tests/` 下 llm 场景，按 tests/README.md）

路径均在项目 change-assurance 规则覆盖范围内（src/、tests/、builtin/）；docs 与 `*.md` 在 `excluded_paths` 中。

## 安全边界

- **输入不可信**：config.yaml 的 registry spec、lock 内容（commit 正则、文件路径用 `is_definition_file` 校验、hash 正则）、远端树与文件内容、全局存储中的文件都视为不可信。
- **完整性**：只物化 lock 锁定的 commit；物化与每次读取都按 lock hash 校验，存储被篡改不会被静默使用；lock 由项目版本库评审（skill 继续提醒审阅 lock 变化）。
- **文件系统**：存储目录 0700；所有访问用目录 fd + O_NOFOLLOW；拒绝符号链接与特殊文件；source-id 与 commit 均为十六进制，不含用户可控字符；临时目录名用 uuid。
- **git**：沿用 `run_git` 加固（协议白名单、禁用 hooks/模板、fsck、清理 GIT_* 环境变量、凭据脱敏）；工作仓库每次新建，不复用。
- **回显**：错误信息只回显经正则校验的定义名与路径。
- **资源上限**：沿用 `MAX_FILES`、单文件/总量限额。

## 验证方案

- 单元测试（`test_registry_store.py`）：source-id 稳定；物化成功/幂等；hash 不一致 → `registry_lock_mismatch`；读取时篡改 → `registry_store_corrupt`；并发两次物化（模拟目标已存在）；失败不留快照；符号链接存储根拒绝；v1 lock 兼容与 `held` → `registry_lock_outdated`；lock 缺失 → `registry_not_synced`；本地冲突 → `registry_local_conflict`。
- 同步测试（`test_registry_sync.py` 改写）：首次 update/apply 只写 lock；upToDate 两条快速路径；上游新增/修改/删除分类；plan stale（config 变化、lock 变化、plan 篡改）；apply 预检失败不写 lock；apply 引入与本地同名定义时报错。
- 端到端（BDD `registry.feature`）：新 clone 场景（无 fragments/profiles，存储为空）→ fragment list / plan create / node instructions 成功且内容正确；第二个 home 同 commit 在 registry 不可达时仍成功；本地同名报错、删除后成功；本地独有 + registry 混用；`profile save` 同名失败；非 registry 项目回归。
- 回归：现有全部测试（`make test`）。
- skill：更新 `loopspec-update-registry` 的 LLM E2E 场景并运行 `make test-llm`。

## 风险与取舍

- **放弃本地三方合并**：registry 模式不再支持本地定制 registry 定义（已确认）。需要定制时只能用不同名字的本地定义或修改 registry 本身。
- **plan.json 仍放在项目 `.cache/`**：已被 `.cache/registry/.gitignore` 忽略，不进版本库；放到全局存储需要按项目区分，收益不大。
- **update 阶段提前物化目标快照**：会在全局存储留下未被采用的版本，但快照按 commit 不可变、可复用，且无 GC 属于非目标。
- **备选：项目内 gitignore 目录 + 修复恢复逻辑（方案一）**：改动小，但每个 worktree 都要一份副本、仍需修补三方分类，已由用户否决。
- **备选：存储内保留长期 git 镜像以加速**：增加被持久化 git 配置影响的攻击面，现有设计刻意每次新建工作仓库，保持不变。

## 评审修订（Codex 审阅后采纳，优先于上文）

1. **可信文件表**：快照只在有可信期望文件表（来自 lock 或 apply 计划）时才允许命中缓存。`registry update` 总是从 git 读取目标 commit 的树得到文件表，再以它为期望物化；不再存在 `expected_files=None` 的物化。审阅用的 `upstreamPath/basePath` 指向已按 hash 校验过的快照文件。
2. **不自动修复损坏快照**：发布只用「临时目录写完 → `os.rename` 到不存在的目标」；目标已存在则按期望完整校验，通过即复用，不通过报 `registry_store_corrupt`（message 给出快照目录，fix 为删除该目录后重试），不做「移走再替换」。
3. **项目级并发**：`registry update` 写计划、`registry apply` 的最终校验与写 lock、registry 模式下的 `profile save` 名称校验与写入，都在 `write_lock(<home>/.cache/registry)` 内执行；锁内重读 config、lock 与计划，只删除本次消费的计划。
4. **存储根权限**：存储根及 `<source-id>` 目录必须是当前用户所有、非符号链接、不可被组/其他用户写（`mode & 0o022 == 0`），否则 `unsafe_path`；新建目录一律 0700。git 只在 `<source-id>/.tmp-<uuid>/` 这个刚由本进程创建的 0700 目录中运行。
5. **v1 迁移**：快速路径（两条 `upToDate`）只对 v2 lock 生效。v1 lock（无论是否同 commit、是否有 `held`）一律生成计划；同 commit 时计划标记 `migration: true`、文件变化为空，`apply` 按 git 树重建 v2 文件表写入。读取路径对 `held` 非空的 v1 报 `registry_lock_outdated`，此时 `update` 不会走快速路径，因此修复提示可执行。
6. **apply 预检扩展**：在候选「新快照 + 本地定义」上执行：本地同名冲突检查；全部 registry 与本地定义加载（同现有 `_validate_preview` 规则）；项目 `workflow.assurance_rules` 与 `required_fragments` 能解析；未完成 change 的活动 Plan 引用的资源路径（instruction、template、Gate 模板、assurance）在候选中仍存在。`update` 输出 `localConflicts` 与 `brokenReferences` 供确认前展示；`apply` 对二者任一非空分别报 `registry_local_conflict` / `registry_breaks_running_plan` 且不写 lock。
7. **计划结构**：`plan.json` 带 `schema: 2`、spec、完整目标文件表 `files`、`base`（当前 lock 文件原始字节的 sha256，无 lock 为 null）、目标 commit/tag、`migration` 标志与展示用 entries。`apply` 用 `base` 判断 lock 是否被改动，用完整 `files` 生成 v2 lock。
8. **基线审阅**：`update` 尽力按旧 lock（同来源）物化旧 commit 快照（期望为旧 lock 文件表），成功则给出 `basePath`，失败时 `baseAvailable: false` 并在 warnings 中说明哪些修改无法给出基线内容。来源切换时旧 lock 的定义全部列为 `deleted`，并加 warning 要求单独确认来源切换。
9. **update 的项目落盘**：只允许写 `<home>/.cache/registry/`（不存在时创建并写入 `.gitignore`=`*`），proposal 验收已同步修改。
10. **快照完整性**：每个进程首次使用某快照时按期望文件表做完整校验（文件集合与全部 hash），之后按需读取仍逐文件校验；缺失与 hash 不符都报 `registry_store_corrupt`。`fragment list` / `profile list` 的来源与版本信息从同一个解析上下文（bundle）取得，不再单独读 lock。
11. **严格拉取**：`RegistryRepo` 新增 `fetch_commit(commit, tag)`：先按 tag（若 lock 有 tag 且 tag 指向该 commit）再按 commit 拉取，失败抛 `registry_fetch_failed`（fix 说明需要远端仍保留该 commit/tag 及凭据）；64 位 commit 时裸仓库以 `--object-format=sha256` 初始化。
12. **命令级一致性**：`definition_bundle(home)` 在进程内按（home 绝对路径，lock 原始字节 hash）缓存，同一命令内所有读取者共用同一个 bundle。`plan --file` 请求文件仍只从 home 读取（不经 registry 路由）。补测 `graph --profile` 与 Gate 多资源读取。
13. **历史 Plan 重新绑定**：由第 6 点在 apply 前阻止删除活动 Plan 引用的 registry 资源；运行时若路径既不在 registry 也不在本地则报资源缺失。文档说明「从 registry 删除的定义改为本地同名定义」会让旧 Plan 读到本地版本。
14. **大小上限**：lock、manifest、plan 的文件表条目数不超过 `registry_git.MAX_FILES`，路径由 `is_definition_file` 约束；写入前序列化并确认不超过 `MAX_FILE_BYTES`，否则 `resource_limit`。
15. **测试补充**：BDD 增加 assurance Gate 同时读取 registry 规则与 `config.yaml` 规则、registry 模式 `init --update-resources` 不复制定义、同 commit v1 迁移成 v2、`graph --profile`；`test_registry_store.py` 用真实多进程覆盖并发首次发布与中断（临时目录残留不被当作快照）；LLM E2E 断言模型展示实际内容 diff、不执行未经确认的 `apply`、确认后只有 lock 变化。

不采纳：为活动 Plan 持久化资源来源（改 Plan 格式代价大，第 6、13 点已覆盖主要风险）。
