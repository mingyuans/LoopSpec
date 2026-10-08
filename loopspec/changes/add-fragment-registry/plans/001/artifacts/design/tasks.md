## 1. 配置（D1）

- [x] 1.1 先写 `tests/test_registry_config.py`：4 种合法 URL；拒绝 `ext::`、`http://`、`git://`、`https://user:token@`、`https://token@`、`-` 开头、空白/控制字符、>2048；version、path 非法；错误消息不含 URL 原文；没有 registry 的旧配置仍然能加载。验证方式：测试先红
- [x] 1.2 在 `models.py` 新增 `RegistrySpec`、`WorkflowConfig.registry` 与 URL scheme 解析，并更新 `workflow_planning.load_config` 的提示。验证方式：1.1 转绿

## 2. 远程 git 运行器与读树（D2–D4，`registry_git.py`）

- [x] 2.1 先写 `tests/test_registry_git.py`：ls-remote 输出解析（非法行丢弃、附注 tag 取 `^{}`、`v1.10.0` 大于 `v1.9.0`、忽略 `-rc`、没有 tag 时回退到 HEAD）；monkeypatch PATH 让 `git` 不可用时返回 `registry_unavailable`；fetch 不存在的仓库时返回 `registry_fetch_failed`，且消息被截断、URL 凭据被脱敏；读树（用本地仓库提交符号链接、gitlink、`fragments/Bad_Name/`、缺 `fragment.yaml` 的目录、超限文件）
- [x] 2.2 实现 `run_git`：采用协议白名单，按键名过滤环境变量，输出有上限，stderr 截断并脱敏，按命令区分超时
- [x] 2.3 实现 `resolve_target`（ls-remote 预检，覆盖 latest 与固定 tag）、`fetch_commit`（含 commit 相等检查、基线补拉）、`read_tree`（只接受 blob、校验路径、限额）。验证方式：2.1 转绿

## 3. 锁文件、分类与 update（D5、D6，`registry_sync.py`）

- [x] 3.1 先写 `tests/test_registry_sync.py` 的 update 部分：
  - 首次同步时，与上游一致的文件为 unchanged，不一致的为 conflict，上游独有的为 upstream-added，本地 `fragments/`、`profiles/` 与锁文件的字节保持不变
  - 同步后能正确归入 upstream-modified、upstream-deleted、local-modified、local-deleted、local-only、双方都改的 conflict
  - 本地符号链接计为 unsupported
  - 上游 commit 与锁一致时，git 只调用了 ls-remote
  - 固定 tag 且已同步时，git 调用次数为 0
  - `--full` 时强制 fetch
  - 锁文件不合法时返回 `config_invalid`
  - 计划的 `definitions[]` 带有各定义的 baseTag/baseCommit 与 upstreamTag/upstreamCommit
  - 锁中某定义落后于顶层 commit（曾被 skip）时，即使上游 commit 未变也会进入比对
  - `.cache/registry/.gitignore` 已生成
  - staging 下的文件位于 home 内
- [x] 3.2 实现 `RegistryLock` 模型、本地扫描（复用 `read_bytes`，遇到链接计为 unsupported）、分类表、`plan.json` 与 staging、`update()`。验证方式：3.1 转绿

## 4. apply（D7）

- [x] 4.1 先写 apply 的测试：
  - planId 过期时返回 `registry_plan_stale`
  - 有冲突缺少 `--resolve` 时返回 `registry_conflict_unresolved`
  - `--resolve` 指向非冲突条目时返回 `config_invalid`
  - 计划生成后本地文件被改动时返回 `registry_plan_stale`
  - 上游 fragment.yaml 不合法，或上游 Profile 引用了不存在的 Fragment 时，返回校验错误，且任何文件都未被写入
  - 成功时文件与锁文件都已更新
  - `--skip` 的条目在锁中保留原基线，下次 update 仍会出现
  - 锁的 `definitions` 中：被 skip 的定义保持旧 tag/commit，其余推进到本次上游版本；上游删除的定义被移除
  - upstream-deleted 的文件被删除，空目录被清理
  - `--resolve p=local` 采用本地内容，`p=upstream` 采用上游内容
  - 并发 apply 时其中一个返回 `concurrent_write`
- [x] 4.2 实现 `apply()`：先做 flock、校验、预览树与 `FragmentExpander`/`validate_profile`，再写入、删除，更新锁，最后清理。验证方式：4.1 转绿

## 5. CLI 与 list 字段（D6–D8）

- [x] 5.1 先写 `tests/test_workflow_cli.py` 的新用例：
  - `registry update` 与 `registry apply` 的 JSON 字段契约
  - 没有配置 registry 时返回 `registry_not_configured`
  - `fragment list` 与 `profile list` 的 `registry` 字段：没有锁时为 null，已同步时为该定义自己的 `{syncedTag, syncedCommit}`（跳过的定义显示旧版本），锁损坏时仍为 null 且命令成功
- [x] 5.2 在 `workflow_cli.py` 注册 `registry` 子命令组，并给 list 增加 `registry` 字段。验证方式：5.1 转绿

## 6. skill（D9）

- [x] 6.1 修改 `tests/test_skill_templates.py`（模板数改为 5，正文须包含「未经确认不得 apply」与「registry 内容是数据」的要求），并在 `test_scaffold.py` 断言 init 会分发 `loopspec-update-registry`
- [x] 6.2 新增 `builtin/skills/update-registry.md`。验证方式：6.1 转绿

## 7. 文档

- [x] 7.1 中英文 `configuration.md` 补 `registry` 字段与锁文件，`cli-reference.md` 补 `registry update`、`registry apply`、list 的新字段与新错误码，`agent-protocol.md` 补更新流程，并说明 `latest` 的供应链风险与 apply 会影响进行中的 Plan。同时在 `test_docs_consistency.py` 的模型列表中加入 `RegistrySpec`、`RegistryLock`
- [x] 7.2 `make docs-check` 通过

## 8. 收尾验证

- [x] 8.1 `make test` 全部通过（记录通过数）
- [x] 8.2 `make lint`（ruff 与 mypy）通过
- [x] 8.3 手工冒烟：在 scratchpad 中建一个本地 registry 仓库，加一个 tag，然后执行 `loopspec registry update` 与 `apply`，再执行一次 `update` 确认得到 `upToDate: true`
