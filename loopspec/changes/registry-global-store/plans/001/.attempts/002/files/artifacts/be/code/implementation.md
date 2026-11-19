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

## 改动文件

- 新增：`src/loopspec/registry_store.py`、`tests/test_registry_store.py`
- 核心：`src/loopspec/registry_sync.py`（重写）、`registry_git.py`、`workflow_catalog.py`、`workflow_runtime.py`、`workflow_assurance.py`、`workflow_cli.py`、`cli.py`
- skill：`builtin/skills/update-registry.md`、`.claude/skills/loopspec-update-registry/SKILL.md`、`.claude/commands/lpsx/update-registry.md`、`.codex/skills/loopspec-update-registry/SKILL.md`
- 文档：`docs/{zh,en}/{configuration,cli-reference,agent-protocol,fragment-profile-plan,release-notes}.md`
- 测试：`tests/conftest.py`、`tests/registry_helpers.py`、`tests/features/registry.feature`、`tests/steps/registry_steps.py`、`tests/test_registry_sync.py`、`tests/test_registry_git.py`、`tests/test_workflow_cli.py`、`tests/test_cli.py`、`tests/test_docs_consistency.py`、`tests/features/llm_skills.feature`、`tests/steps/llm_steps.py`、`tests/llm_launcher.py`、`tests/llm_bin/loopspec`、`tests/test_llm_launcher.py`

## 执行的检查

- `uv run ruff check src tests hatch_version.py`：All checks passed
- `uv run mypy src hatch_version.py`：Success: no issues found
- `uv run pytest -q -n 4 -m "not timing and not llm"`：1649 passed, 1 skipped（基线 1615 passed, 1 skipped）
- `uv run pytest -m "timing and not llm"`：3 passed
- `make test-llm`（返工后）：12 passed，15 次模型启动，$1.628，无重跑，`.llm-e2e-runs/20261119T043103Z/`；返工前一次：12 passed，$1.641，`.llm-e2e-runs/20261119T042134Z/`
- 返工新增用例：存储路径中间符号链接、伪造 lock 的 tag 指向未发布 commit、超深嵌套与重复键 lock、超深嵌套计划 JSON、守卫拒绝非 fixture registry（3 个子命令 × 2 种配置）与未注入 fixture。

说明：本机 `make test` 使用 `-n auto` 时进程被系统以 137 终止（内存），因此改用 `-n 4` 运行同一选择器。

## 与设计的偏差

- 错误码 `registry_breaks_active_plan` 改名为 `registry_breaks_running_plan`：文档一致性测试禁止出现已删除接口名 `active_plan` 子串。
- 定义加载预检对「同步前已失效的本地定义」不阻塞（沿用旧 `_validate_preview` 语义）；判断「同步前」时若当前 lock 无法构造 bundle，则以项目内定义的普通视图为准。
- 本地冲突检查以「存在同名路径」为准（任意文件或目录），而非仅限含 `fragment.yaml` 的目录，避免残留副本被忽略。

## 后续事项

- 本仓库自身 `loopspec/` 仍是 v1 lock + vendored 定义；用本分支 CLI 操作本仓库会报 `registry_local_conflict`，需按迁移步骤删除副本并重新 apply（非目标，待人决定何时迁移）。
- 已使用 registry 的项目（如 aftership-channels、empl-af-desk）升级 CLI 后同样需要按迁移步骤处理。
- 全局存储无 GC 命令（非目标）。
- 剩余风险（安全审查记录）：git 浅拉取在内容限额生效前不限制磁盘写入（改动前已存在）；进程内验证缓存只影响长驻进程，实际读取的字节仍逐文件校验。
