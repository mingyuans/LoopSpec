## 1. 全局存储与 lock v2

- [x] 1.1 `registry_git.RegistryRepo`：新增严格的 `fetch_commit(commit, tag)`；64 位 commit 时裸仓库用 `--object-format=sha256` 初始化。验证：`tests/test_registry_git.py` 新增按 tag / 按 commit 拉取成功、不存在的 commit 报 `registry_fetch_failed`。
- [x] 1.2 新模块 `registry_store.py`：存储根解析（`LOOPSPEC_REGISTRY_STORE`，默认 `~/.loopspec/registry`）与权限检查、`source_id`、`materialize`（临时目录 + 原子 rename，已存在则完整校验，损坏报 `registry_store_corrupt`）、`.snapshot.json`。验证：`tests/test_registry_store.py` 覆盖物化、幂等、hash 不符、损坏、宽权限根、符号链接根、并发多进程首次发布、中断残留。
- [x] 1.3 lock v2 模型与 v1 兼容读取（`held` 非空报 `registry_lock_outdated`），lock 来源不一致报 `registry_lock_mismatch`，缺失报 `registry_not_synced`；大小上限。验证：单元测试。

## 2. 定义解析层

- [x] 2.1 `definition_bundle(home)` / `DefinitionBundle`：非 registry 模式返回原 `ResourceBundle`；registry 模式路由读取、逐文件校验 hash、本地同名冲突报 `registry_local_conflict`；进程内按（home，lock 字节 hash）缓存。验证：单元测试。
- [x] 2.2 接入 `WorkflowCatalog`（列表合并 registry 与本地、本地目录可不存在、带来源）、`workflow_runtime.resource_text`、`workflow_assurance.live_rules`、`workflow_planning`。验证：catalog / runtime / planning 相关测试与新 BDD。
- [x] 2.3 `fragment list` / `profile list` 输出 `source` 与 registry 版本（同一 bundle）；`profile save` 在 registry 模式下拒绝同名并在写锁内执行。验证：BDD。
- [x] 2.4 `loopspec init`：registry 模式不复制内置定义（含 `--update-resources`）。验证：BDD / `test_cli.py`。

## 3. registry update / apply

- [x] 3.1 重写 `registry_sync.update`：v2 快速路径；总是从 git 读目标树并物化；与 lock 对比生成 added/modified/deleted；尽力物化旧快照给出 `basePath`；v1 迁移计划；`localConflicts`、`brokenReferences`；计划 schema 2 写入 `.cache/registry/plan.json`（写锁内）。验证：`tests/test_registry_sync.py`。
- [x] 3.2 重写 `registry_sync.apply`：锁内校验计划与 lock `base`、物化、预检（冲突、定义加载、项目约束与 assurance、活动 Plan 引用）、只写 lock v2；删除 `--resolve` / `--skip`。验证：`tests/test_registry_sync.py`。
- [x] 3.3 清理三方合并遗留代码与 `synced_versions` 旧逻辑；更新 `errors.py`（如需）。验证：`make lint`、`make test`。

## 4. skill 与文档

- [x] 4.1 更新 `builtin/skills/update-registry.md`（及 `skill_templates.py` 相关内容）。验证：`tests/test_skill_templates.py`、`tests/test_docs_consistency.py`。
- [x] 4.2 更新 `docs/zh|en` 的 configuration、cli-reference、release-notes 等。验证：`tests/test_docs_consistency.py`。

## 5. BDD 与 LLM E2E

- [x] 5.1 改写 `tests/features/registry.feature` 与 `tests/steps/registry_steps.py`：新 clone 读取、plan create + node instructions + assurance Gate、同 commit 第二个 home 离线可用、本地同名报错与修复、本地独有混用、`profile save` 同名失败、v1 迁移、registry 模式 init、`graph --profile`、lock 缺失、update/apply 正常与 stale。conftest 全局把 `LOOPSPEC_REGISTRY_STORE` 指到临时目录。验证：`make test`。
- [x] 5.2 LLM E2E：更新 `features/llm_skills.feature` 中 update-registry 场景。验证：`make test-llm`（无法运行时如实记录）。

## 6. 全量验证

- [x] 6.1 `make lint`、`make test` 全部通过，记录真实结果。
