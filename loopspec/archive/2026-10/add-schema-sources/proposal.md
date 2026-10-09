## Why

今天每个 schema 都以副本形式放在各项目的 `<workflow home>/schemas/<name>/` 下（`loopspec init` 从内置 schema 复制而来）。团队在多个仓库共用同一份自定义 schema 时，只能手工在每个仓库复制、同步：副本会漂移，共享 schema 的一次修复要逐个项目重做，而且各项目通常还会对自己的副本做少量本地改动，手工同步时很容易把这些改动覆盖掉。

引入 **schema registry（schema 源）**：一个存放共享 schema 的 git 仓库（通常在 GitHub 上），作为各项目本地 schema 副本的**上游**。CLI 负责拉取上游并做三方比对；由于本地副本大概率被改过、冲突是常态，合并决策交给一个新的 skill——用户在 LLM 对话里说「更新 schemas」，LLM 通过 CLI 拉取更新、尝试合并，整理变更与冲突并经用户确认后再写入。

## What Changes

- `config.yaml` 新增可选的 `registry` 字段：一个 git 仓库（`url`，可选的 `version` 与仓库内子目录 `path`）。每个项目最多一个 registry。`version` 类似依赖版本：`latest`（默认，跟踪最高的 semver release tag，也就是 GitHub Release 的 tag；没有 tag 时跟踪默认分支）或固定 tag（如 `v1.3.0`，已同步后不再更新，且完全离线）。
- **版本号**：registry 级用 git tag 标识；schema 级复用 `schema.yaml` 已有的 `version`。更新计划会展示 registry 的「当前 tag → 上游 tag」，以及每个 schema 的本地 / 上次同步 / 上游版本；上游改了 schema 却没升 `version` 时给出提醒。版本号只用于展示，不参与合并判断。
- 新增 **锁文件** `<home>/registry.lock.yaml`（随项目提交）：记录上次同步的上游 commit、tag、每个 schema 的版本，以及每个同步文件的内容哈希，作为三方比对的基线（base），用于区分「本地改过」与「上游改过」。
- 新增 CLI 命令 `loopspec schemas update`：先用 `git ls-remote` 做轻量的版本预检（只列出远端 ref，不下载内容），与锁文件一致时直接报告已是最新；有变化时才通过本机 `git` 拉取 registry，**全量**比对 registry 中的所有 schema 与本地 `<home>/schemas/`，把每个文件分类（未变、仅上游变、仅本地变、冲突、新增、删除……），并把 base / upstream 副本放入 `<home>/.cache/registry/` 下的暂存区，输出供 LLM 消费的 JSON 计划。该命令**不修改** `<home>/schemas/`。
- 新增 CLI 命令 `loopspec schemas apply`：按上一步的计划写入 `<home>/schemas/`——应用上游变更、接受 LLM 已写好的冲突合并结果（需逐个声明为已解决），写入前校验结果 schema 可加载，写入后更新锁文件。计划过期或仍有未解决冲突时拒绝写入。
- 新增内置 skill `loopspec-update-schemas`（命令 `/lpsx:update-schemas`），由 `loopspec init` 分发：驱动「update → 列出全部变更并请用户一次确认 → 对冲突逐个提出合并方案并确认 → apply」的流程。未经用户明确确认，skill SHALL NOT 调用 `apply`。
- registry 中仅作为本项目私有的 schema（本地有、上游没有）不受影响；上游删除的 schema 或文件不会被静默删除，而是作为需要确认的变更列出。
- 完全向后兼容：没有 `registry` 时，所有既有命令行为不变；schema 仍只从 `<home>/schemas/` 加载，`.workflow.yaml` 格式不变。

不在范围内（非目标）：多个 registry；只同步部分 schema；按单个 schema 固定版本；semver 范围（如 `^1.3`）与按分支跟踪；通过 GitHub API / `gh` 查询 release 或通过 HTTP 下载归档（仅使用本机 `git`）；固定版本时查询是否有更新的版本；CLI 自动合并或自动应用任何变更；在 `config.yaml` 中保存凭据；定时 / 后台自动同步；向 registry 推送本地改动。

## Capabilities

### New Capabilities
- `schema-registry`：`registry` 配置与校验、锁文件与基线、拉取与三方分类、暂存区、`schemas update` 计划的 JSON 契约、`schemas apply` 的写入规则与安全边界。

### Modified Capabilities
- `lpsx-skills`：内置 skill/命令模板从 4 个增加到 5 个，新增 `loopspec-update-schemas`。
- `usage-docs`：配置参考（`registry`）、CLI 参考（`schemas update`、`schemas apply`、新错误码）、agent 协议中的 schema 更新流程（中英文）。

## Impact

- 代码：`src/loopspec/models.py`（`RegistrySpec`、锁文件模型）、`src/loopspec/config.py`（registry 校验）、新模块 `src/loopspec/registry.py`（git 调用、分类、暂存、应用）、`src/loopspec/cli.py`（两个新子命令）、`src/loopspec/errors.py`（新错误码）、`builtin/skills/update-schemas.md`（新 skill）。
- 外部集成与安全面：首次引入**子进程调用 `git`** 与**网络拉取**；registry URL 与 ref 来自配置、文件路径与内容来自远程仓库，均为不可信输入——命令注入、协议滥用（如 `ext::`）、路径穿越、符号链接 / 子模块、凭据泄露（URL 中嵌入的 token）、以及上游内容作为 agent 指令的信任边界，都需要在 design 中逐项处理。
- 运行时依赖：需要本机安装 `git`（仅 `schemas update` 需要；未安装时给出明确错误）。不新增 Python 依赖。
- 文件：`<home>/registry.lock.yaml`（提交）、`<home>/.cache/registry/`（不提交，自带 `.gitignore`）。
- 文档：`docs/en|zh/configuration.md`、`cli-reference.md`、`agent-protocol.md`、`schema-reference.md`。
- 测试：新增 `tests/test_registry.py`（使用 `tmp_path` 中的本地 git 仓库作为 registry，不访问网络），并修改 `tests/test_config.py`、`tests/test_cli.py`、`tests/test_skill_templates.py`、`tests/test_scaffold.py`、`tests/test_docs_consistency.py`。
