## ADDED Requirements

### Requirement: 文档集的双语布局与文件清单
仓库 SHALL 在根目录下提供 `docs/` 文档集，且 SHALL 采用**语言并列子目录**布局：`docs/en/` 承载英文版，`docs/zh/` 承载中文版，两个语言目录下的文件名 SHALL 逐一同名。`docs/README.md` SHALL 是唯一位于语言目录之外的文件，且 SHALL 只承担语言选择与一句话导航（本身双语），SHALL NOT 承载任何事实性内容。

每个语言目录 SHALL 包含以下 7 个文件，每个文件 SHALL 只覆盖其声明的范围，不重复其他文件的职责：

| 文件 | 职责范围 |
| --- | --- |
| `<lang>/README.md` | 该语言版本的索引：逐篇列出文件、一句话覆盖范围与适用读者 |
| `<lang>/overview.md` | loopspec 是什么、解决什么问题、核心模型、术语表 |
| `<lang>/cli-reference.md` | 全部 CLI 命令、参数、`--json` 响应字段、退出码与错误码总表 |
| `<lang>/configuration.md` | `config.yaml` 全字段参考与 schema 解析优先级 |
| `<lang>/schema-reference.md` | `schema.yaml` 全字段参考与加载期语义校验清单 |
| `<lang>/agent-protocol.md` | 供 LLM/Agent 驱动 loopspec 的循环契约 |
| `<lang>/workflows/secure-spec-driven.md` | 内置 `secure-spec-driven` schema 的节点图与各节点语义 |

`<lang>/README.md` SHALL 是该语言版本的入口，且 SHALL 链接到同语言目录下其余每一个文档文件。

#### Scenario: 双语目录均包含全部必需文件
- **WHEN** 检视 `docs/en/` 与 `docs/zh/`
- **THEN** 两个目录下上表列出的 7 个文件全部存在

#### Scenario: 顶层只有语言入口文件
- **WHEN** 检视 `docs/` 目录下语言目录之外的文件
- **THEN** 只存在 `docs/README.md`，且其内容只包含语言选择链接与一句话导航

#### Scenario: 语言内索引链接到同语言的每一篇文档
- **WHEN** 检视任一语言目录下的 `README.md`
- **THEN** 其中包含指向该语言目录下其余 6 个文档文件的相对链接，且每一篇都附带一句话说明其覆盖范围与适用读者

#### Scenario: 索引中不存在指向缺失文件的链接
- **WHEN** 解析文档集中的全部仓库内相对链接
- **THEN** 每个链接目标在仓库中都真实存在

### Requirement: 双语版本的等价性
两个语言版本 SHALL 内容等价。等价性 SHALL 落在以下可自动断言的结构化事实上：

- 两个语言目录的相对路径集合 SHALL 相等。
- 两版 `cli-reference.md` 中的命令小节标题集合 SHALL 相等。
- 每一对同名文件中，字段表首列的标识符集合 SHALL 相等。
- 两版记录的错误码集合 SHALL 相等。
- 被标记为可校验的示例块 SHALL 在两版中按出现顺序逐字相等。
- 每篇文档 SHALL 含指向对侧语言同名文件的链接，且链接目标 SHALL 存在。

以下内容 SHALL NOT 被翻译，两版 SHALL 逐字相同：命令名、命令行选项名、配置与 schema 的字段名、错误码、示例块内容、示例标记注释、文件路径、以及命令小节标题。翻译 SHALL 只作用于散文与表格的说明列。

可校验的示例块内 SHALL NOT 包含翻译性注释（对示例的解释 SHALL 写在示例块之外的散文中），否则无法满足两版逐字相等。

散文部分 SHALL NOT 被要求逐句对应——等价性只覆盖上述结构化事实。

#### Scenario: 漏译一篇文档
- **WHEN** 一个语言目录下新增了文档而另一语言目录未同步新增
- **THEN** 双语等价性校验失败

#### Scenario: 只在一版中补了字段
- **WHEN** 某配置字段被补进 `docs/en/configuration.md` 的字段表而 `docs/zh/configuration.md` 未同步
- **THEN** 双语等价性校验失败

#### Scenario: 示例在两版中不一致
- **WHEN** 某个被标记的示例块在两个语言版本中内容不同
- **THEN** 双语等价性校验失败

#### Scenario: 标识符被翻译
- **WHEN** 某命令小节标题或字段名在中文版中被译为中文
- **THEN** 双语等价性校验因集合不相等而失败

#### Scenario: 散文措辞不同不算失败
- **WHEN** 两个语言版本的散文段落数量或措辞不同，但标识符、示例与错误码集合一致
- **THEN** 双语等价性校验通过

#### Scenario: 每篇可跳转到对侧语言
- **WHEN** 打开任一文档文件
- **THEN** 其首屏含指向对侧语言同名文件的相对链接，且该文件存在

### Requirement: 人类与 LLM 双读者的可读性约定
文档集的每个文件 SHALL 同时满足人类顺序阅读与 LLM 局部读取两种消费方式，为此 SHALL 遵守以下可检查的约定（两个语言版本同等适用）：

- 每个文件的**首屏** SHALL 给出三样内容：覆盖范围、适用读者、指向对侧语言同名文件的链接。
- 配置字段 SHALL 以表格呈现，列 SHALL 固定为五列且顺序固定：字段、类型、必填、默认值、说明；字段名 SHALL 出现在**首列**并以反引号包裹。表头词 SHALL 按语言固定（英文版为 `Field`/`Type`/`Required`/`Default`/`Description`，中文版为 `字段`/`类型`/`必填`/`默认值`/`说明`），且一致性校验 SHALL 按列位置而非表头文字定位字段名。
- 所有代码块 SHALL 标注语言（如 `yaml`、`bash`、`json`）。
- 示例 SHALL 可直接复制使用，SHALL NOT 用 `...` 之类的省略号占位；确需省略时 SHALL 以注释说明被省略的内容。
- 文档 SHALL NOT 使用图片、emoji、框线表格或 ASCII 图；层级 SHALL 用 Markdown 标题表达，最深不超过三级。
- 术语首次出现 SHALL 给出一句定义或链接到同语言目录 `overview.md` 的术语表锚点。
- 跨文档引用 SHALL 使用**同语言目录内**的相对链接；跨语言目录的链接 SHALL 只允许出现在每篇首屏的语言切换链接与 `docs/README.md` 中。

#### Scenario: 每个文件首屏声明范围、读者与语言切换
- **WHEN** 打开文档集下任意一个文档文件
- **THEN** 在正文首屏可读到覆盖范围、适用读者，以及指向对侧语言同名文件的链接

#### Scenario: 配置字段以固定五列的表格呈现
- **WHEN** 检视任一语言版本 `configuration.md` 或 `schema-reference.md` 中的任一字段表
- **THEN** 表格为五列且顺序为字段、类型、必填、默认值、说明，字段名位于首列并以反引号包裹

#### Scenario: 表头语言不影响字段定位
- **WHEN** 一致性校验在中文版与英文版中提取字段名
- **THEN** 两者均按表格首列位置提取，不依赖表头文字

#### Scenario: 代码块均标注语言
- **WHEN** 提取文档集中的全部围栏代码块
- **THEN** 每个代码块都带有语言标注

#### Scenario: 不使用图片与 emoji
- **WHEN** 检视文档集全部文件
- **THEN** 文档中不含图片引用与 emoji

#### Scenario: 不存在越界的跨语言链接
- **WHEN** 解析某语言目录下文档的全部相对链接
- **THEN** 除首屏的语言切换链接外，不存在指向另一语言目录的链接

### Requirement: CLI 命令与参数的完整覆盖
每个语言版本的 `cli-reference.md` SHALL 记录 CLI 暴露的**每一个**命令（含子命令组下的子命令）与**每一个**命令行选项。每条命令 SHALL 拥有一个标题为 `## loopspec <command>` 的小节（子命令写作 `## loopspec <group> <subcommand>`，两种语言均使用该英文标题），该小节 SHALL 包含：用途说明、语法、参数表（名称/类型/默认值/说明）、`--json` 响应字段表、以及至少一个真实运行产出的 `--json` 响应示例。某命令的每一个选项 SHALL 出现在该命令自己的小节内。

#### Scenario: 每个命令在每个语言版本都有对应小节
- **WHEN** 遍历 CLI 注册的全部命令与子命令
- **THEN** `docs/en/cli-reference.md` 与 `docs/zh/cli-reference.md` 中均存在与之一一对应的 `## loopspec <command>` 小节

#### Scenario: 每个选项出现在其命令的小节内
- **WHEN** 遍历某命令的全部命令行选项
- **THEN** 每个选项名都出现在该语言版本中该命令的小节范围内，而不是仅出现在其他命令的小节里

#### Scenario: 新增命令但未补文档
- **WHEN** CLI 新增一个命令而某个语言版本的 `cli-reference.md` 未增加对应小节
- **THEN** 文档一致性校验失败

#### Scenario: 命令小节含 JSON 响应字段表
- **WHEN** 检视任意命令的小节
- **THEN** 其中包含该命令 `--json` 输出的字段表与至少一个 JSON 响应示例

### Requirement: 错误码与退出码的完整覆盖
每个语言版本的 `cli-reference.md` SHALL 包含一张错误码总表，逐条给出错误码、触发条件与修复建议方向，且 SHALL 覆盖系统定义的**每一个**错误码。文档 SHALL 说明失败时的统一契约：退出码为 `1`，结构化输出含 `error`、`message`、`fix` 三个字段。

#### Scenario: 每个错误码在每个语言版本都在总表中
- **WHEN** 遍历系统定义的全部错误码
- **THEN** 每个错误码字面值都出现在两个语言版本 `cli-reference.md` 的错误码总表中

#### Scenario: 新增错误码但未补文档
- **WHEN** 代码新增一个错误码而某个语言版本的错误码总表未更新
- **THEN** 文档一致性校验失败

#### Scenario: 说明统一失败契约
- **WHEN** 检视任一语言版本的 `cli-reference.md`
- **THEN** 其中说明命令失败时退出码为 1，且结构化输出包含 `error`、`message`、`fix` 三个字段

### Requirement: config.yaml 的字段级参考与解析优先级
每个语言版本的 `configuration.md` SHALL 逐字段记录 `config.yaml` 的**每一个**字段，字段名 SHALL 使用 YAML 中真实出现的对外名称（存在别名时以别名为准，例如 `schema` 而非内部属性名）。每个字段 SHALL 给出类型、是否必填、默认值、以及适用的校验规则（含 kebab-case 命名约束、安全相对路径约束、`schema` 必须属于 `schemas[*].name`、`schemas[*].name` 唯一）。文档 SHALL 给出 schema 选择的优先级规则，并 SHALL 区分"创建新 change"与"操作既有 change"两条不同路径。

#### Scenario: 每个配置字段都被记录
- **WHEN** 遍历配置模型的全部字段
- **THEN** 每个字段的对外名称都出现在两个语言版本 `configuration.md` 的字段表首列

#### Scenario: 别名字段以对外名称记录
- **WHEN** 某配置字段的内部属性名与 YAML 中的名称不同
- **THEN** 文档记录的是 YAML 中真实使用的名称

#### Scenario: 给出两条路径的优先级规则
- **WHEN** 检视任一语言版本 `configuration.md` 的 schema 解析说明
- **THEN** 其中分别说明创建新 change 与操作既有 change 时的优先级顺序，并指出多候选 schema 未指定时会要求显式选择

#### Scenario: 提供递进的配置示例
- **WHEN** 检视任一语言版本 `configuration.md` 的示例
- **THEN** 其中至少包含最小配置、多候选 schema、按节点补充规则、以及自定义目录布局四类示例

### Requirement: schema.yaml 的字段级参考与语义校验清单
每个语言版本的 `schema-reference.md` SHALL 逐字段记录 `schema.yaml` 的**每一个**字段（顶层字段、节点字段、门禁字段及其嵌套字段），字段名 SHALL 使用 YAML 中真实出现的对外名称。文档 SHALL 说明：`instruction` 的内联字符串与文件引用两种写法、`generates` 对 glob 的支持、`tracks` 的语义与约束、`templates/` 与 `instructions/` 的目录约定、以及被保留而不可用作产物路径的文件名。文档 SHALL 列出加载期执行的全部语义校验，并为每条校验注明失败时返回的错误码。文档 SHALL 提供一个从零手写的最小可用 schema 完整示例。

#### Scenario: 每个 schema 字段都被记录
- **WHEN** 遍历 schema 相关模型的全部字段
- **THEN** 每个字段的对外名称都出现在两个语言版本 `schema-reference.md` 的字段表首列

#### Scenario: 语义校验清单注明错误码
- **WHEN** 检视任一语言版本 `schema-reference.md` 的语义校验清单
- **THEN** 每条校验都注明其失败时返回的错误码

#### Scenario: 记录保留产物路径
- **WHEN** 检视任一语言版本的 `schema-reference.md`
- **THEN** 其中说明 change 级保留文件不可被声明为节点产物路径

#### Scenario: 提供最小 schema 示例
- **WHEN** 检视任一语言版本的 `schema-reference.md`
- **THEN** 其中包含一个含普通节点与门禁节点的最小完整 schema 示例，以及其配套的目录结构说明

### Requirement: 文档示例必须可被真实校验
文档集中标记为可校验的 YAML 示例 SHALL 能通过项目自身的配置/schema 加载逻辑校验而不报错。可校验示例 SHALL 通过在围栏代码块**前一行**放置约定的 HTML 注释标记来声明其类型（配置示例、schema 示例、或需要物化目录的完整 schema 示例）。未加标记的 YAML 代码块 SHALL 被视为片段而不参与校验。标记本身 SHALL NOT 被翻译，两个语言版本 SHALL 使用同一套标记。

#### Scenario: 标记为配置示例的块通过校验
- **WHEN** 提取任一语言版本中被标记为配置示例的 YAML 块并交给配置模型校验
- **THEN** 校验通过且不抛出异常

#### Scenario: 标记为 schema 示例的块通过校验
- **WHEN** 提取任一语言版本中被标记为 schema 示例的 YAML 块并交给 schema 模型校验
- **THEN** 校验通过且不抛出异常

#### Scenario: 未标记的片段不参与校验
- **WHEN** 文档中存在一个未加标记的 YAML 片段
- **THEN** 该片段不被送入校验，且不导致校验失败

#### Scenario: 示例写错时校验失败
- **WHEN** 某个被标记的示例含有非法字段或缺少必填字段
- **THEN** 文档一致性校验失败并指出该示例

### Requirement: 文档一致性校验的执行方式与安全边界
仓库 SHALL 提供自动化的文档一致性校验，纳入项目默认测试范围，并 SHALL 可通过一个独立的构建目标单独执行。该校验 SHALL 包含两类断言：

1. **代码 → 文档的单向覆盖**：只断言代码中存在的命令、选项、模型字段与错误码都已被文档记录，SHALL NOT 断言文档中不得出现代码里没有的名称（文档需要额外解释环境变量、目录约定与术语）。该类断言 SHALL 对**每个语言版本分别执行**。
2. **语言版本之间的双向等价**：比对对象限定为标识符与示例这类闭集，SHALL 断言集合相等。

该校验 SHALL NOT 执行文档中出现的任何 shell 命令，只 SHALL 对文档做文本解析与 YAML/模型校验；需要物化目录的 schema 示例 SHALL 只在测试临时目录中创建文件，SHALL NOT 写入仓库工作区，且物化前 SHALL 先校验示例中声明的文件名为安全相对路径。

字段与选项的存在性判定 SHALL 基于结构化位置匹配（如字段表首列、命令小节范围内），SHALL NOT 使用全文裸子串包含判定，以避免名称恰好出现在无关叙述中即被判定为"已记录"。

#### Scenario: 默认测试范围内包含文档校验
- **WHEN** 运行项目默认测试
- **THEN** 文档一致性校验被执行

#### Scenario: 可单独执行文档校验
- **WHEN** 执行专用的文档校验构建目标
- **THEN** 只运行文档一致性校验并报告结果

#### Scenario: 单向覆盖对每个语言版本分别执行
- **WHEN** 某命令的小节只存在于英文版
- **THEN** 中文版的覆盖断言失败

#### Scenario: 校验不执行文档中的命令
- **WHEN** 文档中包含 shell 代码块
- **THEN** 校验过程中这些命令不被执行，仅作为文本处理

#### Scenario: 示例文件名不安全时拒绝物化
- **WHEN** 某个需要物化目录的示例声明的文件名为绝对路径或含 `..`
- **THEN** 校验在写入任何文件之前失败

#### Scenario: 文档额外解释非命令行事实不算失败
- **WHEN** 文档中记录了环境变量、目录约定等代码命令行表面之外的事实
- **THEN** 一致性校验不因此失败

#### Scenario: 名称出现在叙述文本中不算已记录
- **WHEN** 某配置字段名只在正文叙述中被提及，而未出现在字段表首列
- **THEN** 一致性校验判定该字段未被记录并失败

### Requirement: 文档中的默认值与代码保持一致
文档中出现的默认值（如工作流主目录的默认路径、默认 schema 名称、以及各配置/schema 字段的默认值）SHALL 与代码中的定义一致，并 SHALL 由文档一致性校验对齐代码中的常量与模型默认值，而不是人工维护。该要求对两个语言版本同等适用。

#### Scenario: 默认值与代码常量一致
- **WHEN** 一致性校验读取代码中的默认常量与模型字段默认值
- **THEN** 两个语言版本中记录的对应默认值与之相同

#### Scenario: 代码默认值变更但文档未更新
- **WHEN** 代码中某默认值被修改而任一语言版本仍写旧值
- **THEN** 文档一致性校验失败

### Requirement: Agent 驱动契约文档
每个语言版本的 `agent-protocol.md` SHALL 描述 LLM/Agent 驱动 loopspec 的完整契约，并 SHALL 明确以下容易误判的行为：

- 主循环：读取状态、按状态给出的下一步提示执行命令、按节点指令产出产物、回到读取状态。
- 门禁失败支线：先执行回退，再重做被重置的节点；重做时可从节点指令中读到上一轮失败的原因。
- 声明了任务追踪的节点：即使已写出通过态产物，只要被追踪文件中仍有未完成条目，该节点仍未完成，归档 SHALL 被拒绝。
- 人类审批节点：Agent SHALL NOT 代替人类作出批准决定；无法联系到人类时该节点保持等待状态。
- `state.md` 的读写约定。

文档 SHALL 对每一步指明应读取响应中的哪个字段。

#### Scenario: 描述主循环与所依赖的字段
- **WHEN** 检视任一语言版本的 `agent-protocol.md`
- **THEN** 其中给出主循环的步骤序列，并逐步指明该步应读取的响应字段

#### Scenario: 说明任务追踪节点的完成判定
- **WHEN** 检视任一语言版本的 `agent-protocol.md`
- **THEN** 其中说明声明了任务追踪的节点在被追踪文件仍有未完成条目时不算完成，且归档会被拒绝

#### Scenario: 说明禁止代替人类批准
- **WHEN** 检视任一语言版本的 `agent-protocol.md`
- **THEN** 其中明确 Agent 不得代替人类批准，且无人可问时节点保持等待

### Requirement: 内置工作流文档
每个语言版本的 `workflows/secure-spec-driven.md` SHALL 记录内置 `secure-spec-driven` schema 的完整节点图（节点、类型、依赖、产物路径），逐节点说明其语义与产出要求，并 SHALL 给出每个门禁的重置目标、最大重试次数与耗尽策略及其取值理由。

#### Scenario: 记录完整节点图
- **WHEN** 检视任一语言版本的 `workflows/secure-spec-driven.md`
- **THEN** 其中以表格给出内置 schema 每个节点的类型、依赖与产物路径，与 schema 定义一致

#### Scenario: 记录门禁的回退配置与理由
- **WHEN** 检视文档中任一门禁的说明
- **THEN** 其中给出该门禁失败时的重置目标、最大重试次数、耗尽策略，以及为何如此取值

### Requirement: README 收敛为文档集入口
`README.md` SHALL 保留项目定位、安装与快速上手，SHALL 链接到 `docs/README.md` 作为完整手册入口，且 SHALL NOT 重复维护 CLI 参数明细、`config.yaml` 字段明细或 `schema.yaml` 字段明细——这些内容 SHALL 只存在于 `docs/` 中。

#### Scenario: README 链接到文档集
- **WHEN** 检视 `README.md`
- **THEN** 其中包含指向 `docs/README.md` 的链接，并说明完整手册位于 `docs/` 且提供中英两个语言版本

#### Scenario: README 不重复字段明细
- **WHEN** 检视 `README.md`
- **THEN** 其中不包含 `config.yaml` 或 `schema.yaml` 的逐字段参考表，也不包含命令参数明细表

### Requirement: 文档示例不得包含真实凭据
文档集中的全部示例 SHALL 只使用占位名称与仓库内相对路径，SHALL NOT 包含任何真实凭据、密钥、令牌、内网地址或真实用户标识。该检查 SHALL 对两个语言版本同等执行，且校验失败时 SHALL 只报告文件与行号及命中的规则名，SHALL NOT 回显命中的内容。

#### Scenario: 示例使用占位名称
- **WHEN** 检视文档集中的全部示例
- **THEN** 其中的变更名、schema 名与路径均为占位或仓库内相对路径，不含任何凭据类信息

#### Scenario: 命中疑似凭据时不回显内容
- **WHEN** 凭据检查在某文档中命中疑似凭据
- **THEN** 失败信息只包含文件路径、行号与命中的规则名，不包含命中的原始字符串
