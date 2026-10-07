# 配置

> 覆盖范围：`config.yaml` 与保障规则文件的全部字段，以及各自何时检查。
> 适用读者：配置与维护项目的人。
> 语言：**中文** · [English](../en/configuration.md)

## config.yaml

`loopspec init` 写出 `<home>/config.yaml`，记录 Change 存放位置与项目的最低工作流约束。未知字段一律拒绝，因此 LoopSpec 1.x 的字段（`schema`、`schemas`、`schema_selection`、`context`、`rules`）与 `workflow.default_profile` 会返回 `config_invalid`，需要删除。

<!-- loopspec:example=config -->
```yaml
artifacts_dir: changes
workflow:
  required_fragments: [qa-testing, change-assurance]
  assurance_rules: fragments/change-assurance/rules.yaml
  generated_dirs: [node_modules, .venv]
```

### 顶层字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `artifacts_dir` | 相对路径 | 否 | `changes` | 工作区内存放 Change 的目录。 |
| `workflow` | 映射 | 否 | - | 项目约束，见下。 |

### workflow 字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `required_fragments` | Fragment 名称列表 | 否 | `[]` | 每份 Plan 的 flow 中都必须实例化这些 Fragment。 |
| `assurance_rules` | 工作区路径 | 否 | - | 项目保障规则。设置后每份 Plan 都需要保障节点，且这些规则与保障节点自带规则合并。 |
| `generated_dirs` | 名称列表 | 否 | `[]` | 不计入 Git Diff 的工具生成目录。只接受 `.venv`、`node_modules`、`.pytest_cache`、`.mypy_cache`、`.ruff_cache` 与 `__pycache__`，其他值返回 `unsafe_exclusion`。 |

### 何时读取

创建 Plan 时检查约束，确认或修订时按当时的文件再次检查。执行期间 Diff 排除项与保障规则也实时读取。因此修改 `config.yaml` 会立即影响正在执行的 Plan（包括放宽规则），应当作需要评审的项目代码对待。

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
| `unknown_paths` | `fail` | 否 | `fail` | 不匹配任何规则的改动路径使保障失败。 |
| `rules` | 规则列表 | 是 | - | 1 到 256 条规则。 |

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | kebab-case 字符串 | 是 | - | 规则名；两个文件中同名规则内容必须相同。 |
| `paths` | 通配列表 | 是 | - | 规则覆盖的改动路径。多条规则命中时要求取并集。 |
| `requires` | 能力列表 | 是 | - | 每个命中路径都必须由带有效证据的代码 Gate 提供的能力。 |
| `repair_fragment` | Fragment 名称 | 是 | - | Plan 中没有 Gate 能提供某项能力时建议补充的 Fragment。 |

Fragment 中 Gate 的 `evidence.paths` 与规则的 `paths` 必须描述同一批目录。没人审查的路径会出现在 `unknown_paths` 或 `missing_fragments` 中；不要用扩大 `generated_dirs` 的方式隐藏业务代码。
