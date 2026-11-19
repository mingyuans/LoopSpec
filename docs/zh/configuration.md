# 配置

> 覆盖范围：`config.yaml` 与保障规则文件的全部字段，以及各自何时检查。
> 适用读者：配置与维护项目的人。
> 语言：**中文** · [English](../en/configuration.md)

## config.yaml

`loopspec init` 写出 `<home>/config.yaml`，记录 Change 存放位置与项目的最低工作流约束。未知字段一律拒绝，因此 LoopSpec 1.x 的字段（`schema`、`schemas`、`schema_selection`、`context`、`rules`）与 `workflow.default_profile` 会返回 `config_invalid`，需要删除。`workflow.generated_dirs` 已删除，把其中的名称原样移到 `workflow.excluded_paths` 即可，含义不变。

<!-- loopspec:example=config -->
```yaml
artifacts_dir: changes
workflow:
  required_fragments: [qa-testing, change-assurance]
  assurance_rules: fragments/change-assurance/rules.yaml
  excluded_paths: [node_modules, .venv, .DS_Store, docs/**]
```

### 顶层字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `artifacts_dir` | 相对路径 | 否 | `changes` | 工作区内存放 Change 的目录。 |
| `workflow` | 映射 | 否 | - | 项目约束，见下。 |
| `registry` | 映射 | 否 | - | fragments 与 profiles 的上游 git registry，见下。 |

### workflow 字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `required_fragments` | Fragment 名称列表 | 否 | `[]` | 每份 Plan 的 flow 中都必须实例化这些 Fragment。 |
| `assurance_rules` | 工作区路径 | 否 | - | 项目保障规则。设置后每份 Plan 都需要保障节点，且这些规则与保障节点自带规则合并。 |
| `excluded_paths` | 模式列表 | 否 | `[]` | 不计入 Git Diff 的路径，最多 128 项。不含 `/` 的模式匹配路径中任意一级名字（包括文件名），例如 `.DS_Store`、`__pycache__`、`*.log`；含 `/` 的模式用 fnmatch 匹配仓库相对完整路径，`*` 可跨目录，例如 `docs/**`、`loopspec/config.yaml`。命中的路径不需要任何审查，被忽略时也不产生告警。模式必须是安全相对路径：不能为空、不能以 `/` 开头、不能含 `.` 或 `..` 分量。 |

### registry 字段

可选的 git 仓库（通常在 GitHub），用于单独维护共享的 fragments 与 profiles。配置 registry 后项目进入 **registry 模式**：registry 的 fragments 与 profiles 不再写进项目，而是存放在用户级全局存储中，项目只提交 `config.yaml` 与 `registry.lock.yaml`。版本由 `loopspec registry update` 与 `loopspec registry apply` 更新（见 [CLI 参考](cli-reference.md)）。每个项目只配置一个 registry。

<!-- loopspec:example=config -->
```yaml
artifacts_dir: changes
workflow: {}
registry:
  url: git@github.com:acme/loopspec-workflows.git
  version: latest
  path: workflows
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `url` | git URL | 是 | - | `https://host/...`、`ssh://[user@]host/...`、`user@host:path` 或 `file:///abs/path`。拒绝 `http://`、`git://`、`ext::` 等传输语法以及 URL 内嵌的凭据；认证使用本机 git 配置（SSH agent 或 credential helper）。 |
| `version` | `latest` 或 tag | 否 | `latest` | `latest` 跟踪最高的 release tag（`v1.2.3`，忽略预发布），没有 tag 时跟踪默认分支。固定 tag（如 `v1.3.0`）不会更新，同步后无需联网。 |
| `path` | 相对路径 | 否 | - | registry 中存放 `fragments/` 与 `profiles/` 的目录；缺省为仓库根。 |

`latest` 会跟随 registry 发布的更高 tag；对供应链更敏感的项目应固定 tag，并为 registry 的分支与 tag 开启保护。

### registry.lock.yaml

`loopspec registry apply` 写出 `<home>/registry.lock.yaml`，与 `config.yaml` 一起提交。它锁定项目使用的 registry commit，并记录该 commit 中每个定义文件的 SHA-256。`loopspec init` 不会创建它。它作为不可信输入严格校验，不合法时返回 `config_invalid`。

<!-- loopspec:example=registry-lock -->
```yaml
version: 2
registry:
  url: git@github.com:acme/loopspec-workflows.git
  version: latest
  path: workflows
commit: 3f2a9c1e5b7d4f60a8e2c3b1d9f7a6e5c4b3a2f1
tag: v1.4.0
files:
  fragments/qa-testing/fragment.yaml: 9c1e5b7d4f60a8e2c3b1d9f7a6e5c4b3a2f1e0d9c8b7a6f5e4d3c2b1a0f9e8d7
  profiles/bugfix.yaml: 51ab7d4f60a8e2c3b1d9f7a6e5c4b3a2f1e0d9c8b7a6f5e4d3c2b1a0f9e8d7c6
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `version` | 整数 | 否 | `2` | 格式版本。旧格式 `1`（定义写在项目内时的锁）仍可读取，下一次 `registry apply` 改写为 `2`。 |
| `registry` | registry 映射 | 是 | - | 本次锁对应的 registry。`url` 或 `path` 与 `config.yaml` 不一致，或 `config.yaml` 固定了 tag 而 lock 的 `tag` 与之不同，读取定义返回 `registry_lock_mismatch`；修改 `version` 后先 `registry update` 与 `registry apply`。 |
| `commit` | commit id | 是 | - | 项目使用的 registry commit。 |
| `tag` | tag 或 null | 否 | - | 该 commit 的 release tag。 |
| `files` | 映射 | 否 | `{}` | 该 commit 中每个定义文件到其内容 SHA-256。定义集合由它推出，全局存储中的快照逐文件按它校验。 |

### 全局存储

registry 定义按「来源 + commit」存放在 `$LOOPSPEC_REGISTRY_STORE`（默认 `~/.loopspec/registry`）下：`<store>/<source-id>/<commit>/`，`source-id` 由 `url` 与 `path` 推出。快照写完临时目录后原子发布，此后不再改变，同一台机器上的多个项目与 worktree 共用。目录必须属于当前用户、路径中没有符号链接且组与其他用户不可写，否则返回 `unsafe_path`；新建目录权限为 `0700`。

- **自动拉取。**读取定义（`fragment list`、`plan create`、`node instructions`、保障规则等）时，如果存储中还没有 lock 锁定的 commit，CLI 会从 registry 拉取该 commit，按 lock 的 hash 完整校验后发布，再继续执行；lock 带 `tag` 时，先确认该 tag 在 registry 中仍指向 lock 的 commit，否则返回 `registry_lock_mismatch`，伪造的 lock 无法借已发布的 tag 掩盖其他 commit。注意：这意味着在不信任的项目里执行读取定义的命令，也可能按该项目配置的 `registry.url` 发起 git 连接并使用本机的 SSH 或凭据助手认证；对不熟悉的项目，先检查 `config.yaml` 与 `registry.lock.yaml`。新 clone 或新 worktree 因此不需要额外步骤；只有首次拉取需要网络与 git 凭据，失败返回 `registry_fetch_failed`，不会留下半成品快照。
- **完整性。**每次读取都按 lock 校验文件内容；快照被改动或缺文件时返回 `registry_store_corrupt`，按提示删除该快照目录后重试即可重新拉取。CLI 不会自动替换已存在的快照。
- **本地定义。**项目内仍可在 `<home>/fragments/`、`<home>/profiles/` 放置名称不同于 registry 定义的本地定义，二者可在同一 Plan 中使用，`fragment list`/`profile list` 用 `source` 区分。与 registry 同名的本地文件或目录会让读取定义的命令返回 `registry_local_conflict`，删除这些项目内副本即可。
- **缺少锁。**registry 模式下没有 `registry.lock.yaml` 时返回 `registry_not_synced`；旧格式锁中有被跳过的定义（`held`）时返回 `registry_lock_outdated`。两者都通过 `registry update` 与 `registry apply` 修复。

缓存目录 `<home>/.cache/registry/`（同步计划与写锁）通过自带的 `.gitignore` 忽略自身，可随时删除。

### 从项目内定义迁移

之前由 `registry apply` 写入项目的 `fragments/`、`profiles/` 副本在升级后会与 registry 同名而报 `registry_local_conflict`：

1. 删除项目内与 registry 同名的定义（只保留你自己的本地定义）。
2. 运行 `loopspec registry update`，确认后 `loopspec registry apply --plan <planId>`，锁改写为新格式。
3. 提交删除与新的 `registry.lock.yaml`。

### 何时读取

创建 Plan 时检查约束，确认或修订时按当时的文件再次检查。执行期间 Diff 排除项与保障规则也实时读取。`<home>/.cache/`（registry 同步缓存）、memory topic 文件 `<home>/memory/{topic}.md`（跨 Change 的 memory）与当前 Change 的 `.workflow.yaml`、`state.md`、`plans/` 始终不计入 Diff，无需配置。因此修改 `config.yaml` 会立即影响正在执行的 Plan（包括放宽规则），应当作需要评审的项目代码对待。

## 保障规则

保障规则文件把改动路径映射到必须由代码 Gate 证明的能力。内置 `change-assurance` Fragment 附带的 `rules.yaml` 只是示例路径，使用前按项目实际目录调整。

<!-- loopspec:example=assurance-rules -->
```yaml
version: 1
unknown_paths: fail
rules:
- id: backend
  paths: [src/backend/**, backend/**, tests/backend/**]
  requires: [backend-tests, security-review, pr-review]
  repair_fragment: backend-implementation
- id: frontend
  paths: [src/frontend/**, frontend/**, tests/frontend/**]
  requires: [frontend-tests, pr-review]
  repair_fragment: frontend-implementation
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `version` | 整数 | 否 | `1` | 格式版本。 |
| `unknown_paths` | `fail` 或 `warn` | 否 | `fail` | 改动路径不匹配任何规则时的处理。`fail` 使保障失败；`warn` 不影响结论，这些路径仍列在诊断的 `unknown_paths` 中，并作为告警（`warnings.unknownPaths`，最多 20 条，附 `unknownTotal`）写进诊断与系统报告的 `summary`。合并多份规则文件时，任一文件为 `fail` 即按 `fail`，Fragment 自带的规则不能放宽项目规则。 |
| `rules` | 规则列表 | 是 | - | 1 到 256 条规则。 |

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | kebab-case 字符串 | 是 | - | 规则名；两个文件中同名规则内容必须相同。 |
| `paths` | 通配列表 | 是 | - | 规则覆盖的改动路径。多条规则命中时要求取并集。 |
| `requires` | 能力列表 | 是 | - | 每个命中路径都必须由带有效证据的代码 Gate 提供的能力。 |
| `repair_fragment` | Fragment 名称 | 是 | - | Plan 中没有 Gate 能提供某项能力时建议补充的 Fragment。 |

Fragment 中 Gate 的 `evidence.paths` 与规则的 `paths` 必须描述同一批目录。没人审查的路径会出现在 `unknown_paths` 或 `missing_fragments` 中；`excluded_paths` 不限制取值，写进去的路径就不再经过任何 Gate；不要用它隐藏业务代码，修改它应当作需要评审的项目代码对待。
