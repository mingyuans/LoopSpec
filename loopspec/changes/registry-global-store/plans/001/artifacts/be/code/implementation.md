## 完成的任务

- 1.1 `RegistryRepo.fetch_commit(commit, tag)`：严格拉取锁定版本（先 tag 后 commit，失败报 `registry_fetch_failed`），64 位 commit 用 `--object-format=sha256` 初始化裸仓库。
- 1.2 新模块 `registry_store.py`：存储根（`LOOPSPEC_REGISTRY_STORE`，默认 `~/.loopspec/registry`）及所有者/权限/符号链接检查、`source_id`、`materialize`（临时目录写入 → 原子 rename 发布；已存在则按可信文件表完整校验；损坏报 `registry_store_corrupt`，不自动替换）、`.snapshot.json` manifest。
- 1.3 lock v2 模型（`commit`、`tag`、`files`）与 v1 兼容读取；`registry_not_synced`、`registry_lock_outdated`、`registry_lock_mismatch`；lock 写入前大小检查。
- 2.1 `definition_bundle(home)` / `DefinitionBundle`：非 registry 模式返回原 `ResourceBundle`；registry 模式下 registry 定义从快照读取并逐文件按 lock hash 校验，其余路径从 home 读；本地同名冲突报 `registry_local_conflict`；进程内按（home，lock 字节 hash）缓存快照位置。
- 2.2 `WorkflowCatalog` 支持注入 bundle，列表合并 registry 与本地定义（registry 模式下本地目录可不存在），提供 `source()`、`registry_version()`；`workflow_runtime.resource_text` 与 `workflow_assurance.live_rules` 改走 `definition_bundle`。
- 2.3 `fragment list` / `profile list` 输出 `source` 与 `registry`（来自同一 bundle）；registry 模式 `profile save` 在项目写锁内执行并拒绝 registry 同名。
- 2.4 `loopspec init`：registry 模式不复制内置定义（含 `--update-resources`），`resourcesUpdate` 为 `registry`。
- 3.1 / 3.2 重写 `registry_sync`：`update` 在写锁内 → v2 快速路径 → 从 git 读目标树并物化 → 与 lock 对比 added/modified/deleted → 尽力物化旧快照给出 `basePath` → `localConflicts`、`brokenReferences`、v1 `migration` → 计划 schema 2（完整目标文件表 + lock 原始字节 hash 作为 `base`）。`apply` 在写锁内校验计划/配置/lock → 本地冲突 → 定义加载（同步前已失效的本地定义不阻塞）→ 项目约束与 assurance 规则 → 活动 Plan 引用（`registry_breaks_running_plan`）→ 只写 lock v2。删除 `--resolve` / `--skip`。
- 3.3 删除三方合并、staging/preview、`synced_versions` 等旧逻辑。
- 4.1 重写 `builtin/skills/update-registry.md`，同步本仓库 `.claude/skills`、`.claude/commands/lpsx`、`.codex/skills` 中的生成副本。
- 4.2 更新 `docs/zh|en` 的 configuration（lock v2、全局存储、迁移）、cli-reference（list/save/update/apply、7 个新错误码）、agent-protocol、fragment-profile-plan、release-notes。
- 5.1 改写 registry BDD（7 个场景）；conftest 加 autouse fixture 把存储隔离到临时目录；新增 `test_registry_store.py`，重写 `test_registry_sync.py`，更新 `test_workflow_cli.py`、`test_cli.py`、`test_registry_git.py`、`test_docs_consistency.py`。
- 5.2 LLM E2E：守卫与启动器放行 `registry`；新增 2 个 update-registry 场景（未确认不 apply；确认后只有 lock 变化）。
- 返工（安全审查 FAIL 后，rollback 001）：
  - `_private_dir()` 用 `workflow_io.directory()` 逐级 O_NOFOLLOW 打开，存储路径任意位置有符号链接都报 `unsafe_path`。
  - `RegistryRepo.fetch_commit()` 在 lock 带 tag 时先 `ls-remote` 校验 tag 解引用后的 commit 等于 lock 的 commit，不一致报 `registry_lock_mismatch`，tag 已不存在报 `registry_fetch_failed`。
  - lock 改用有界的 `parse_yaml()`（拒绝别名、重复键、超深嵌套）；计划 JSON 解析捕获 `RecursionError`，按 `registry_plan_stale` 处理。
  - LLM 守卫：所有子命令（`hook` 除外）若 config.yaml 配置了 registry，其 url 必须等于测试注入的 `LOOPSPEC_LLM_REGISTRY_URL`，且 `LOOPSPEC_REGISTRY_STORE` 必须在项目内；`registry` 子命令在未注入 fixture 时一律拒绝。
  - 文档补充 tag 绑定校验与「路径中不能有符号链接」。
- 第 2 次返工（安全审查第 2 轮 FAIL 后，rollback 002）：
  - `_private_dir()` 从最深的已存在祖先起用 `directory(..., create=True)` 逐级 O_NOFOLLOW 打开并创建：先检查后创建，符号链接后面不会留下目录。
  - 快照 manifest 增加 `tags`（发布时已验证指向该 commit 的 tag）；缓存命中但 lock 的 tag 不在其中时，经 `RegistryRepo.verify_tag()` 在线校验，结果在进程内缓存。`fetch_commit` 复用 `verify_tag`。
  - LLM 守卫改为用被测 CLI 的 `registry_spec()`（`python -I` 子进程）解析配置，与 CLI 一致；解析失败即拒绝。
  - 文档写明已接受风险：读取定义的命令在缓存缺失时会按项目配置联网并使用本机 git 凭据。
- 第 3 次返工（安全审查第 3 轮 FAIL 后，rollback 003）：
  - `pinned()`：`config.yaml` 固定 tag 时，lock 的 `tag` 必须与之相同，否则 `registry_lock_mismatch`（防止省略 tag 跳过 tag→commit 校验）。
  - LLM 守卫：对默认 home 与所有可能的 `--home` 值都解析 registry，任一不是「未配置或 fixture URL」即拒绝（防止 `--note --home=…` 误导）。
  - 文档补充固定 tag 时 lock 必须一致、修改 `version` 后需先 update/apply。
- 第 4 次返工（代码审查 FAIL 后，rollback 004）：
  - `update()` 快速路径同时比较 commit 与 tag（同 commit 改绑 tag、首次给已锁定的 HEAD 打 tag 都会生成计划）。
  - `registry_spec()` 只在 `config.yaml` 声明了 `registry`（无法解析时原文含 `registry`）才严格加载；非 registry 项目不再因无关配置错误失败。
  - update 输出 `sourceChanged`、`previousRegistry`，警告文字与预览一致；skill 要求并列展示新旧来源并单独确认。
  - `instructions()` 一次响应只解析一次 lock，instruction、template、Gate 模板共用同一个 bundle。
  - `_build_plan()` 发布计划前用 `lock_bytes()` 检查目标 lock 可读；`read_lock()` 把超过读取上限的 lock 映射为 `config_invalid`。
  - 在线验证过的 tag→commit 绑定持久化到 `<store>/<source-id>/tags/<tag>`，之后离线可信；v1 lock 文件表上限沿用旧版 8192。

## 改动文件

- 新增：`src/loopspec/registry_store.py`、`tests/test_registry_store.py`
- 核心：`src/loopspec/registry_sync.py`（重写）、`registry_git.py`、`workflow_catalog.py`、`workflow_runtime.py`、`workflow_assurance.py`、`workflow_cli.py`、`cli.py`
- skill：`builtin/skills/update-registry.md`、`.claude/skills/loopspec-update-registry/SKILL.md`、`.claude/commands/lpsx/update-registry.md`、`.codex/skills/loopspec-update-registry/SKILL.md`
- 文档：`docs/{zh,en}/{configuration,cli-reference,agent-protocol,fragment-profile-plan,release-notes}.md`
- 测试：`tests/conftest.py`、`tests/registry_helpers.py`、`tests/features/registry.feature`、`tests/steps/registry_steps.py`、`tests/test_registry_sync.py`、`tests/test_registry_git.py`、`tests/test_workflow_cli.py`、`tests/test_cli.py`、`tests/test_docs_consistency.py`、`tests/features/llm_skills.feature`、`tests/steps/llm_steps.py`、`tests/llm_launcher.py`、`tests/llm_bin/loopspec`、`tests/test_llm_launcher.py`

## 执行的检查

- `uv run ruff check src tests hatch_version.py`：All checks passed
- `uv run mypy src hatch_version.py`：Success: no issues found
- `uv run pytest -q -n 2 -m "not timing and not llm"`：1670 passed, 1 skipped（基线 1615 passed, 1 skipped）
- `make test-llm`（第 4 次返工后）：12 passed，15 次模型启动，$1.666，无重跑，`.llm-e2e-runs/20261119T054402Z/`；此前四次均 12 passed（$1.641、$1.628、$1.699、$1.698）。
- 独立复核：第 3、4 次返工前各用 Codex 只读复核一次；最后一次复核两次超时未完成，最后三处修复（tag 绑定持久化、v1 上限、坏 YAML 探测）为人工复核。
- 第 4 次返工新增用例：同 commit 改绑 tag、首次给锁定 HEAD 打 tag、无文件变化的来源切换、目标 lock 超限时不发布计划、超大 lock 报 `config_invalid`、非 registry 项目带旧字段或坏 YAML 的 config 仍可读定义、一次 `node instructions` 只解析一次 lock、改绑 tag 后离线可用、v1 lock 超过 2048 条目。

说明：本机 `make test` 使用 `-n auto`/`-n 4` 时进程被系统以 137 终止（内存），因此改用 `-n 2` 运行同一选择器。

## 与设计的偏差

- 错误码 `registry_breaks_active_plan` 改名为 `registry_breaks_running_plan`：文档一致性测试禁止出现已删除接口名 `active_plan` 子串。
- 定义加载预检对「同步前已失效的本地定义」不阻塞（沿用旧 `_validate_preview` 语义）；判断「同步前」时若当前 lock 无法构造 bundle，则以项目内定义的普通视图为准。
- 本地冲突检查以「存在同名路径」为准（任意文件或目录），而非仅限含 `fragment.yaml` 的目录，避免残留副本被忽略。

## 后续事项

- 本仓库自身 `loopspec/` 仍是 v1 lock + vendored 定义；用本分支 CLI 操作本仓库会报 `registry_local_conflict`，需按迁移步骤删除副本并重新 apply（非目标，待人决定何时迁移）。
- 已使用 registry 的项目（如 aftership-channels、empl-af-desk）升级 CLI 后同样需要按迁移步骤处理。
- 全局存储无 GC 命令（非目标）。
- 剩余风险（代码审查记录）：`plan approve` 与 `registry apply` 并发交错可能让新批准的 Plan 引用被删除的资源，运行时会明确报资源缺失。
- 剩余风险（安全审查记录）：git 浅拉取在内容限额生效前不限制磁盘写入（改动前已存在）；进程内验证缓存只影响长驻进程，实际读取的字节仍逐文件校验。
