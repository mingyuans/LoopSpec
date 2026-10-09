## MODIFIED Requirements

### Requirement: config.yaml 的字段级参考与解析优先级
每个语言版本的 `configuration.md` SHALL 逐字段记录 `config.yaml` 的**每一个**字段，字段名 SHALL 使用 YAML 中真实出现的对外名称（存在别名时以别名为准，例如 `schema` 而非内部属性名）。每个字段 SHALL 给出类型、是否必填、默认值、以及适用的校验规则（含 kebab-case 命名约束、安全相对路径约束、`schema` 必须属于 `schemas[*].name`、`schemas[*].name` 唯一、`registry.url` 的形态白名单与禁止内嵌凭据、`registry.version` 的取值（`latest` 或固定 tag）与字符约束）。文档 SHALL 给出 schema 选择的优先级规则，并 SHALL 区分"创建新 change"与"操作既有 change"两条不同路径。文档 SHALL 另外说明 registry 的作用（本地 schema 副本的上游，schema 仍只从 `<home>/schemas/` 加载）、锁文件 `registry.lock.yaml` 应随项目提交而 `.cache/registry/` 不应提交，`latest` 与固定版本的更新语义（固定版本且已同步时完全离线）、registry 维护者应以 semver tag（GitHub Release）发布并在修改 schema 时增加 `schema.yaml` 的 `version`，以及一条安全说明：registry 内容会成为 agent 指令，应开启分支保护与代码评审，且凭据只应通过本机 git 凭据配置提供。

#### Scenario: 每个配置字段都被记录
- **WHEN** 遍历配置模型的全部字段
- **THEN** 每个字段的对外名称都出现在两个语言版本 `configuration.md` 的字段表首列

#### Scenario: 别名字段以对外名称记录
- **WHEN** 某配置字段的内部属性名与 YAML 中的名称不同
- **THEN** 文档记录的是 YAML 中真实使用的名称

#### Scenario: 给出两条路径的优先级规则
- **WHEN** 检视任一语言版本 `configuration.md` 的 schema 解析说明
- **THEN** 其中分别说明创建新 change 与操作既有 change 时的优先级顺序，并指出多候选 schema 未指定时会要求显式选择

#### Scenario: 说明 registry 与安全边界
- **WHEN** 检视任一语言版本 `configuration.md`
- **THEN** 其中包含 `registry` 的字段表、锁文件与缓存目录的提交建议，以及 registry 内容受信任性与凭据提供方式的安全说明

#### Scenario: 提供递进的配置示例
- **WHEN** 检视任一语言版本 `configuration.md` 的示例
- **THEN** 其中至少包含最小配置、多候选 schema、按节点补充规则、自定义目录布局、以及配置 schema registry 五类示例

## ADDED Requirements

### Requirement: 文档覆盖 schema 更新命令与流程
每个语言版本的 `cli-reference.md` SHALL 记录 `loopspec schemas update` 与 `loopspec schemas apply` 的参数（含 `--full`）、JSON 字段（含 `baseTag` / `upstreamTag` / `latestTag` 与各 schema 的三个版本号）、文件分类取值及其含义，`schemas list` 新增的 `registry` 字段，以及新错误码 `registry_not_configured`、`registry_unavailable`、`registry_fetch_failed`、`registry_invalid`、`registry_plan_stale`、`registry_conflict_unresolved`。每个语言版本的 `agent-protocol.md` SHALL 说明由 `loopspec-update-schemas` skill 驱动的更新流程，以及「未经用户确认不得 apply」的约束。

#### Scenario: 记录两个新命令
- **WHEN** 检视任一语言版本 `cli-reference.md`
- **THEN** 其中包含 `schemas update` 与 `schemas apply` 章节，列出全部 JSON 字段与分类取值

#### Scenario: 记录新错误码
- **WHEN** 检视任一语言版本 `cli-reference.md` 的错误码表
- **THEN** 六个 `registry_*` 错误码均出现，并给出触发条件

#### Scenario: agent 协议说明更新流程
- **WHEN** 检视任一语言版本 `agent-protocol.md`
- **THEN** 其中说明 update → 确认 → 逐个解决冲突 → apply 的流程与确认约束
