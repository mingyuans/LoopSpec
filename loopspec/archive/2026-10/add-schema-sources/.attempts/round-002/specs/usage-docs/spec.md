## MODIFIED Requirements

### Requirement: config.yaml 的字段级参考与解析优先级
每个语言版本的 `configuration.md` SHALL 逐字段记录 `config.yaml` 的**每一个**字段，字段名 SHALL 使用 YAML 中真实出现的对外名称（存在别名时以别名为准，例如 `schema` 而非内部属性名）。每个字段 SHALL 给出类型、是否必填、默认值、以及适用的校验规则（含 kebab-case 命名约束、安全相对路径约束、`schema` 必须属于 `schemas[*].name`、`schemas[*].name` 唯一、`schema_sources[*].name` 唯一且不得为 `local`、`schema_sources[*].path` 必须解析为已存在的目录）。文档 SHALL 给出 schema 选择的优先级规则，并 SHALL 区分"创建新 change"与"操作既有 change"两条不同路径。文档 SHALL 另外说明 schema 名称到 schema 目录的**源查找顺序**（`local` 优先，其后按 `schema_sources` 声明顺序，先命中者胜出、同名遮蔽），源 `path` 的三种写法与「不展开环境变量」的规则，以及一条安全说明：外部源中的内容会作为指令交给 agent，只应配置自己信任、写权限受控的目录。

#### Scenario: 每个配置字段都被记录
- **WHEN** 遍历配置模型的全部字段
- **THEN** 每个字段的对外名称都出现在两个语言版本 `configuration.md` 的字段表首列

#### Scenario: 别名字段以对外名称记录
- **WHEN** 某配置字段的内部属性名与 YAML 中的名称不同
- **THEN** 文档记录的是 YAML 中真实使用的名称

#### Scenario: 给出两条路径的优先级规则
- **WHEN** 检视任一语言版本 `configuration.md` 的 schema 解析说明
- **THEN** 其中分别说明创建新 change 与操作既有 change 时的优先级顺序，并指出多候选 schema 未指定时会要求显式选择

#### Scenario: 说明源查找顺序与安全边界
- **WHEN** 检视任一语言版本 `configuration.md`
- **THEN** 其中包含 `schema_sources` 的字段表、源查找顺序与遮蔽规则、`path` 的解析规则（含不展开环境变量），以及外部源内容受信任性的安全说明

#### Scenario: 提供递进的配置示例
- **WHEN** 检视任一语言版本 `configuration.md` 的示例
- **THEN** 其中至少包含最小配置、多候选 schema、按节点补充规则、自定义目录布局、以及跨项目共享 schema 源五类示例

## ADDED Requirements

### Requirement: CLI 参考记录 schema 来源字段
每个语言版本的 `cli-reference.md` SHALL 记录 `schemas list` 条目中 `source` 的取值含义（`local` 或 `schema_sources[*].name`，不再恒为 `local`）与新增的 `shadowed` 字段，`schemas show` / `schemas validate` 响应中的 `source` 字段，以及 `new` / `status` 响应中的 `schemaSource` 字段。

#### Scenario: 记录 shadowed 字段
- **WHEN** 检视任一语言版本 `cli-reference.md` 的 `schemas list` 章节
- **THEN** 字段表中包含 `shadowed`，且 `source` 的说明不再写作「恒为 `local`」

#### Scenario: 记录 schemaSource 字段
- **WHEN** 检视任一语言版本 `cli-reference.md` 的 `new` 与 `status` 章节
- **THEN** 两者的字段表都包含 `schemaSource`
