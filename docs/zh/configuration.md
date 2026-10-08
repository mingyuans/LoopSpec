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

可选的 git 仓库（通常在 GitHub），用于单独维护共享的 fragments 与 profiles。fragments 与 profiles 仍只从 `<home>/fragments/` 与 `<home>/profiles/` 加载；registry 是它们的上游，由 `loopspec registry update` 与 `loopspec registry apply` 同步（见 [CLI 参考](cli-reference.md)）。每个项目只配置一个 registry，并全量同步。

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

`loopspec registry apply` 写出 `<home>/registry.lock.yaml`，与 `config.yaml` 一起提交。它是三方比对的基线，并记录每个定义来自哪个上游版本。`loopspec init` 不会创建它，内置资源也不带版本号。它作为不可信输入严格校验，不合法时返回 `config_invalid`。

<!-- loopspec:example=registry-lock -->
```yaml
version: 1
registry:
  url: git@github.com:acme/loopspec-workflows.git
  version: latest
  path: workflows
commit: 3f2a9c1e5b7d4f60a8e2c3b1d9f7a6e5c4b3a2f1
tag: v1.4.0
definitions:
  fragments/qa-testing: {tag: v1.3.0, commit: 3f2a9c1e5b7d4f60a8e2c3b1d9f7a6e5c4b3a2f1}
  profiles/bugfix: {tag: v1.4.0, commit: 3f2a9c1e5b7d4f60a8e2c3b1d9f7a6e5c4b3a2f1}
files:
  fragments/qa-testing/fragment.yaml: 9c1e5b7d4f60a8e2c3b1d9f7a6e5c4b3a2f1e0d9c8b7a6f5e4d3c2b1a0f9e8d7
  profiles/bugfix.yaml: 51ab7d4f60a8e2c3b1d9f7a6e5c4b3a2f1e0d9c8b7a6f5e4d3c2b1a0f9e8d7c6
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `version` | 整数 | 否 | `1` | 格式版本。 |
| `registry` | registry 映射 | 是 | - | 本次锁对应的 registry。 |
| `commit` | commit id | 是 | - | 上次 apply 的上游 commit。 |
| `tag` | tag 或 null | 否 | - | 该 commit 的 release tag。 |
| `definitions` | 映射 | 否 | `{}` | `fragments/<name>` 或 `profiles/<name>` 到该定义实际所处的版本。有文件被跳过的定义保留旧版本。 |
| `held` | 定义列表 | 否 | `[]` | 有文件被跳过的定义。只要存在这样的定义，即使 registry 没有变化，`registry update` 也会重新比对，被跳过的变更不会被遗忘。 |
| `files` | 映射 | 否 | `{}` | 每个已同步文件到其上游内容的 SHA-256，用于区分本地修改与上游修改。 |

冲突选择 `local` 同样算作基于该上游版本作出了决定：该定义的版本会推进，此后这个文件显示为 `local-modified`。`url` 或 `path` 变化后不再使用旧锁作为基线：所有差异按冲突报告，不会规划任何删除。

`definitions` 的每一项：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `tag` | tag 或 null | 否 | - | 同步该定义时的 release tag。 |
| `commit` | commit id | 是 | - | 同步该定义时的上游 commit。 |

缓存目录 `<home>/.cache/registry/`（私有裸仓库、计划与暂存文件）通过自带的 `.gitignore` 忽略自身，可随时删除。

### 何时读取

创建 Plan 时检查约束，确认或修订时按当时的文件再次检查。执行期间 Diff 排除项与保障规则也实时读取。`<home>/.cache/`（registry 同步缓存）与当前 Change 的 `.workflow.yaml`、`state.md`、`plans/` 始终不计入 Diff，无需配置。因此修改 `config.yaml` 会立即影响正在执行的 Plan（包括放宽规则），应当作需要评审的项目代码对待。

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
