## 背景

LoopSpec 2.0 把工作流定义拆成 Fragment（`<home>/fragments/<name>/`）与 Profile（`<home>/profiles/<name>.yaml`），由 `loopspec init` 从内置资源复制到每个项目。团队在多个仓库共用同一套自定义 Fragment / Profile 时，只能手工复制、同步：副本会漂移，共享定义的一次修复要逐个项目重做；同时每个项目又必须本地定制（例如 Gate 的 `evidence.paths`、`change-assurance/rules.yaml` 的路径映射），手工同步极易覆盖这些定制。

此前的 `add-schema-sources`（2026-10 归档）为 1.x 的 schema 设计过「GitHub registry + 本地副本 + 三方合并」方案，但只停留在设计阶段，未实现，且 2.0 已移除 schema。本次沿用该方案的思路，同步对象改为 fragments 与 profiles。

## 用户场景

- 平台维护者在一个 GitHub 仓库（registry）中单独维护团队共享的 fragments 与 profiles，用 git tag（GitHub Release）发布版本。
- 项目成员在 `<home>/config.yaml` 中声明该 registry，在 LLM 对话里说「更新 registry」，由 skill 驱动 CLI 拉取上游、比对本地副本，列出变更与冲突，经用户确认后写入；项目本地对路径映射等的定制不被静默覆盖。
- 未配置 registry 的项目行为完全不变。

## 范围

人类已确认的决定（AskUserQuestion）：同步模型为本地副本 + 三方合并；registry 仓库结构为 `<path>/fragments/` 与 `<path>/profiles/`；命令为 `loopspec registry update|apply`，新 skill `loopspec-update-registry`；全量同步、只支持一个 registry。

1. **配置**：`config.yaml` 新增可选 `registry`：`url`（必填）、`version`（`latest` 缺省，或固定 tag 如 `v1.3.0`）、`path`（可选，仓库内子目录，缺省为仓库根）。URL / tag / path 严格校验（拒绝 `ext::` 等 transport、`http://`、`git://`、URL 内嵌凭据、以 `-` 开头的参数、路径穿越）。
2. **加载不变**：fragments / profiles 仍只从 `<home>/fragments/` 与 `<home>/profiles/` 加载；Plan、编译、Gate、保障均不感知 registry。
3. **锁文件** `<home>/registry.lock.yaml`（随项目提交）：记录上次同步的上游 commit、tag、每个 Fragment / Profile 的 `version`，以及每个同步文件的内容哈希，作为三方比对基线。严格校验，视为不可信输入。
4. **`loopspec registry update`**：先用 `git ls-remote` 做版本预检，未变化直接返回 `upToDate: true`；固定 tag 且已同步时完全离线；有变化（或 `--full`）时用私有裸仓库 fetch，只通过 `ls-tree` / `cat-file` 读取 git 对象，**全量**比对 registry 中所有 Fragment（目录内全部文件）与 Profile 和本地副本，按 B/L/U 三方哈希分类（unchanged、upstream-modified/added/deleted、local-modified/deleted/only、conflict、unsupported），把 upstream / base 内容暂存在 `<home>/.cache/registry/`，输出 JSON 计划。**不修改** `fragments/`、`profiles/` 与锁文件。
5. **`loopspec registry apply --plan <id> [--resolve <p>=local|upstream]... [--skip <p>]...`**：校验 planId 未过期、冲突全部解决、本地哈希与计划一致；先在预览树中用现有模型校验每个受影响的 Fragment / Profile 可加载；再原子写入并更新锁文件。任一校验失败则不写入任何文件。
6. **版本展示**：registry 级用 git tag；定义级复用 `fragment.yaml` / profile 的 `version`。计划中展示本地 / 上次同步 / 上游版本；上游内容变了但 `version` 未增加时给出 warning。版本只用于展示，不参与分类。
7. **skill**：新增内置 `loopspec-update-registry`（`/lpsx:update-registry`），由 `loopspec init` 分发到各 AI 工具：update → 版本概览与全部变更汇总 → 用户一次确认（可点名跳过）→ 冲突逐个提出合并方案并确认 → apply。未经明确确认不得调用 apply；registry 内容视为待审阅数据。
8. **`fragment list` / `profile list`**：每个条目增加 `registry` 字段（`{syncedVersion, syncedTag, syncedCommit}` 或 `null`），锁文件缺失或不合法时为 `null` 且不让 list 失败。
9. **文档**：中英文 `configuration.md`、`cli-reference.md`、`agent-protocol.md`（或 `workflow-composition.md`）补充 registry 配置、命令、错误码与更新流程。

## 非目标

- 多个 registry；按名称部分同步；按单个定义固定版本；semver 范围与分支跟踪。
- 运行时直接从 registry 加载定义（不改变任何既有加载路径）。
- GitHub API / `gh` / HTTP 归档下载；只使用本机 `git`。
- CLI 自动合并或在无用户确认时写入；向 registry 推送本地改动；定时 / 后台同步。
- 在 `config.yaml` 或锁文件中保存凭据；loopspec 不处理认证。
- 同步 `skills`、`config.yaml` 或任何 Change 内容。

## 验收条件

- [ ] 未配置 `registry` 时，现有全部测试保持通过，`fragment list`、`profile list`、`plan` 等命令输出除新增的 `registry: null` 字段外不变。
- [ ] `registry.url` 为 `ext::sh -c x`、`http://...`、`git://...`、`https://user:token@host/x`、`-oProxyCommand=x` 等时返回 `config_invalid`，且错误消息不回显凭据。
- [ ] 使用 `tmp_path` 中的本地 git 仓库（`file://`）作为 registry，首次 `registry update` 输出的计划中：与上游一致的文件为 `unchanged`，不一致的为 `conflict`，上游独有的为 `upstream-added`；`fragments/`、`profiles/` 与锁文件未被修改。
- [ ] 同步后上游修改某文件、本地未改 → `upstream-modified`；本地修改、上游未改 → `local-modified`；双方都改且不同 → `conflict`；上游删除 → `upstream-deleted`（不静默删除）。
- [ ] 上游 commit 与锁文件一致时，`registry update` 只执行 `ls-remote`、不执行 fetch，返回 `upToDate: true`；固定 tag 且已同步时不执行任何 git 命令。
- [ ] `latest` 模式选择最高的 release tag（`v1.10.0` 高于 `v1.9.0`，忽略 `v2.0.0-rc1`）；无 tag 时跟踪默认分支 HEAD。
- [ ] 上游含符号链接、子模块、路径穿越名、超限文件时：链接 / 子模块列入 `unsupported` 永不写入；超限返回 `registry_invalid` 且不写入。
- [ ] `registry apply`：planId 过期 → `registry_plan_stale`；存在未解决冲突 → `registry_conflict_unresolved`；计划后本地文件被改动 → `registry_plan_stale`；结果中某 Fragment / Profile 无法通过模型校验 → 返回校验错误且不写入任何文件；成功时写入目标文件并更新锁文件，`--skip` 的条目保留原基线。
- [ ] `git` 不在 PATH 时 `registry update` 返回 `registry_unavailable`；fetch 失败返回 `registry_fetch_failed`，消息仅包含截断后的 stderr。
- [ ] `loopspec init` 为每个已配置的 AI 工具生成 `loopspec-update-registry` skill / 命令；skill 正文要求未经用户确认不得调用 `apply`。
- [ ] 中英文文档包含 `registry` 配置、`registry update` / `registry apply`、新错误码；`tests/test_docs_consistency.py`（如存在）通过。
- [ ] 不新增 Python 依赖；`make test` 全部通过。

## 风险

- **安全：子进程与远程输入**——首次在 2.0 中引入 `git` 子进程与网络拉取。缓解：`shell=False`、参数列表、`--` 结束选项解析、`-c protocol.allow=never` 加按 scheme 白名单、`GIT_TERMINAL_PROMPT=0`、超时；裸仓库不 checkout，杜绝 hook / filter / 符号链接落盘；`ls-remote` 输出与 tag 名逐行校验。
- **安全：路径与内容**——上游路径逐段校验、只接受普通 blob、单文件与总量限额；写入复用 `workflow_io` 的 dir-fd 安全写入与原子替换。
- **安全：供应链与 agent 指令**——registry 内容最终成为 agent 指令（instruction 文件）。缓解：所有写入经用户确认，skill 把上游内容当作待审阅数据；文档建议 registry 开启分支保护，对敏感项目使用固定 tag。
- **凭据泄露**——拒绝 URL 内嵌凭据；loopspec 不读取、不打印环境变量；stderr 截断。
- **兼容性**——`registry` 可选，缺省即现状；`config.yaml` 仍拒绝未知字段，新字段需加入模型。
- **执行中 Plan 受影响**——Fragment 的 instruction / template / rules 在执行时实时读取，apply 会立即影响进行中的 Plan；与直接编辑本地文件的风险相同，在文档与 skill 中提示。
- **首次接入冲突多**——本地已定制的文件首次同步都会是 conflict，符合预期，由 skill 汇总降低成本。
