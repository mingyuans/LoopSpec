## 背景

项目在 `config.yaml` 配置 `registry` 后，`loopspec registry update` / `apply` 会把 registry 的全部 fragments/profiles 写进项目的 workflow home（`loopspec/fragments/`、`loopspec/profiles/`），并用 `registry.lock.yaml` 记录基线。这样导致：

- 项目里多出大量与业务无关、但必须提交的文件，每次同步都产生大 diff。
- 如果项目把 `fragments/`、`profiles/` gitignore 而只提交 lock，新 clone / 新 worktree 无法恢复定义：
  - `registry update` 的快速路径在 lock 的 tag/commit 与目标一致时直接返回 `upToDate`，不检查本地文件；
  - `--full` 时三方分类把「lock 有、本地无、上游未变」判成 `local-deleted`，`apply` 不写入；
  - 运行时 `node instructions` 通过 `resource_text` 现场读取 fragment 文件，进行中的 change 直接失败。

已确认的方向（见 change 级 state 的 HUMAN 决策）：registry 模式下定义存放在用户级全局目录，项目只保留 lock；缺失时自动按 lock 拉取；本地同名定义直接报错；不考虑本地修改 registry 定义。

## 用户场景

1. 团队成员 clone 一个 registry 模式的项目（或用 fleet 新建 worktree），直接运行 `loopspec fragment list` / `loopspec change new` + `plan create` / `node instructions`，无需额外步骤就能用上 lock 锁定版本的定义。
2. 项目维护者运行 `loopspec registry update` 查看 registry 新版本相对当前 lock 的定义变化，确认后 `registry apply` 只更新 `registry.lock.yaml`，项目 diff 只有 lock 一个文件。
3. 同一台机器上多个项目 / 多个 worktree 锁定同一个 registry commit 时，共用一份全局存储，不重复拉取。
4. 已经把定义 vendor 在项目内的存量项目升级 CLI 后，CLI 明确报错指出哪些本地定义与 registry 同名，用户删除这些副本后即可继续使用。
5. 项目除 registry 定义外还有自己独有名字的本地 fragment/profile（含 `profile save` 新存的），这些继续在项目内维护并可正常使用。

## 范围

- **全局存储**：registry 定义按「registry 来源 + commit」存放在用户级目录（默认 `~/.loopspec/` 下，可用环境变量覆盖，便于测试与隔离）；同一来源同一 commit 的内容只写一次、写入后不可变，写入过程原子化，并发写入安全。
- **lock**：`registry.lock.yaml` 成为项目唯一的 registry 状态：记录来源、commit、tag 及每个文件的内容 hash；全局存储的内容按 lock 校验。旧格式（v1）lock 可被读取并在下一次 `apply` 时升级。
- **定义解析**：registry 模式下，fragment/profile 的查找、列表、校验，Plan 编译，运行时读取 instruction/template，Gate 的 assurance 规则（包括 `config.yaml` 中 `workflow.assurance_rules` 指向 `fragments/...` 的路径）统一从「全局存储中 lock 对应的快照 + 项目本地独有定义」中解析；已存在 Plan 中记录的 `fragments/<name>/...` 相对路径保持可用。
- **自动拉取**：需要读取定义时，若全局存储缺少 lock 指定的 commit，自动从 registry 拉取该 commit、按 lock hash 校验后写入存储，再继续执行。
- **同名冲突**：registry 模式下，项目本地 `fragments/<name>` 或 `profiles/<name>.yaml` 与 lock 快照中的定义同名时，相关命令报错并列出冲突项和修复方式；`profile save` 不得保存与 registry 同名的 Profile。
- **registry update / apply**：`update` 对比 registry 目标版本与当前 lock，输出定义级和文件级的新增 / 修改 / 删除及计划 ID，不写项目文件；`apply --plan` 校验通过后写入全局存储并只更新 `registry.lock.yaml`。registry 模式下不再有本地三方合并（`--resolve` / `--skip`、`conflict`、`local-*` 状态）。
- **列表输出**：`fragment list` / `profile list` 标明每个定义来自 registry 还是本地。
- **配套**：更新内置 skill `loopspec-update-registry`（及 `skill_templates.py` 中相关内容）、中英文文档（configuration / cli-reference 等）、release notes；按 AGENTS.md 测试规范补齐 BDD、单元测试与涉及 skill 的 LLM E2E 场景。

## 非目标

- 不改变未配置 `registry` 的项目的任何行为（定义仍在项目内，`loopspec init` 的内置定义复制不变）。
- 不支持在本地修改或覆盖 registry 定义（无本地 overlay、无三方合并）。
- 不自动删除或迁移存量项目内 vendor 的定义文件，只报错提示。
- 不提供全局存储的清理 / GC 命令。
- 不改变 registry 仓库自身的目录约定（`fragments/<name>/...`、`profiles/<name>.yaml`、`registry.path`）。
- 不修改本仓库自身 `loopspec/` 目录的 registry 使用方式（是否迁移本仓库 dogfooding 另行决定）。

## 验收条件

- [ ] 新 clone 场景：registry 模式项目只含 `config.yaml` + `registry.lock.yaml`（无 `fragments/`、`profiles/`），全局存储为空时运行 `loopspec fragment list` 成功，列出 lock 快照中的全部定义；全局存储目录下出现该 commit 的快照。判定：命令退出码 0 且定义名称与 registry 该 commit 一致。
- [ ] 同一场景下完成 `change new` → `plan create`（使用 registry 的 profile/fragment）→ `plan approve` → `node instructions`，返回的 `instruction` 内容与 registry 中对应文件一致；`assurance` Gate 能读取 registry 中的 assurance 规则。
- [ ] 第二个项目 / worktree 锁定同一 commit 时不再访问 registry（可通过把 registry URL 指向已删除的本地仓库来判定：命令仍成功）。
- [ ] 全局存储中快照文件被篡改或缺失时，读取命令不会静默使用错误内容：重新拉取修复或以明确错误码失败。
- [ ] `registry update` 在 lock 与 registry 同版本时返回 `upToDate: true`；registry 有新提交时返回新增 / 修改 / 删除的定义与文件以及 `planId`；项目目录内除自带 `.gitignore`（内容 `*`）的 `.cache/registry/` 外无任何文件变化，`git status` 不出现新增或修改。
- [ ] `registry apply --plan <id>` 成功后，项目目录内只有 `registry.lock.yaml` 被创建或修改，lock 的 commit 等于目标 commit；计划过期（registry 配置变化、lock 被改动）时返回 `registry_plan_stale`。
- [ ] 项目本地存在与 registry 同名的 fragment 或 profile 时，`fragment list`、`plan validate/create`、`node instructions` 等读取定义的命令以明确错误码失败，错误信息列出冲突的路径；删除这些本地副本后命令成功。
- [ ] 项目本地独有名字的 fragment/profile 与 registry 定义可在同一 Plan 中共同使用；`fragment list` / `profile list` 中各自标注来源。
- [ ] `profile save` 使用 registry 中已有的名称时失败且不写文件。
- [ ] 旧格式（v1）lock 的存量项目：删除冲突的本地副本后，命令按 v1 lock 的 commit 使用全局存储；随后 `registry apply` 把 lock 写成新格式。
- [ ] registry 模式下 lock 缺失时，读取定义的命令以明确错误码失败并提示运行 `registry update` / `apply`。
- [ ] registry 不可达且全局存储缺少所需 commit 时，以 `registry_fetch_failed`（或同类）错误码失败，不产生半成品快照（存储中不存在不完整目录被当作完整快照使用）。
- [ ] 未配置 registry 的项目：现有测试全部通过，行为不变。
- [ ] `make test`（BDD + 单测）通过；`loopspec-update-registry` skill 修改后对应 LLM E2E 场景通过 `make test-llm`。

## 风险

- **破坏性升级**：存量 vendor 项目升级后命令会报同名冲突，需要用户手动删除副本。应对：错误信息给出精确路径和一步修复说明；release notes 写明迁移步骤。
- **读命令隐式联网**：首次读取会访问 registry，离线或缺少 git 凭据时失败。应对：只在全局存储缺少 lock commit 时联网，错误信息说明原因与修复（检查网络 / 凭据或在有网环境预热）。
- **供应链与完整性**：自动拉取的内容会成为 agent 指令。应对：只拉取 lock 中锁定的 commit，逐文件按 lock hash 校验；lock 本身由项目版本库评审；沿用现有 git 子进程加固（禁用 hooks、协议白名单、不 checkout、fsck）。
- **全局目录安全**：存储目录可能被其他进程或用户篡改、或被符号链接替换。应对：目录权限 0700，拒绝跟随符号链接，快照写入走临时目录 + 原子 rename，读取时校验完整性标记。
- **并发**：多个 worktree 同时拉取同一 commit。应对：原子 rename，后完成者发现已存在则丢弃自己的结果。
- **进行中的 change**：`apply` 更新 lock 后，进行中 Plan 读取的 instruction 会随之变化（与现状一致）。应对：skill 中继续提示。
- **测试隔离**：测试不能写真实的 `~/.loopspec`。应对：通过环境变量把存储根目录指到临时目录，并在测试 fixture 中强制设置。
