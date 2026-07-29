## MODIFIED Requirements

### Requirement: 全命令支持结构化 JSON 输出
`loopspec` 的每个子命令 SHALL 支持 `--json` 标志，输出机器可解析的结构化结果；`--json` 是 LLM/Agent 消费的主协议，人类可读输出（无 `--json`）为次要形式。二者 SHALL 呈现同一组事实，但人类可读模式 SHALL 允许对事实做聚合与取舍（例如用计数替代逐条明细），以换取可读性；被聚合掉的明细 SHALL 仍完整保留在 `--json` 输出中。人类可读模式 SHALL NOT 直接转印 `--json` 载荷的字段名与原始数据结构。

#### Scenario: 任意命令附加 --json
- **WHEN** 对任意 `loopspec` 子命令附加 `--json`
- **THEN** 命令以合法 JSON 格式输出结果到 stdout

#### Scenario: 人类可读模式不泄漏内部数据结构
- **WHEN** 不带 `--json` 执行任意命令
- **THEN** 输出中不出现 JSON 载荷的原始字段名或语言层面的容器字面量（如 dict/list 的 repr）

#### Scenario: 人类可读模式聚合后明细仍可从 JSON 获取
- **WHEN** 某命令的人类可读输出用计数替代了逐条明细
- **THEN** 同一命令加 `--json` 后仍可取到被聚合掉的完整明细

### Requirement: loopspec init 初始化 workflow home
`loopspec init [path] [--tools TOOLS] [--project-root DIR]` SHALL 在指定路径（缺省为 `./loopspec`）创建 workflow home，包含 `config.yaml`（含默认 `artifacts_dir: changes` 与默认 `schema`）、空的 `schemas/` 目录与空的 `changes/` 目录；默认 SHALL 同时把内置 schema 复制到 `schemas/` 下；传入 `--no-builtin` SHALL 跳过复制，只生成空骨架。

`--tools` 参数 SHALL 接受 `all`（选中全部已注册工具）、`none`（不做任何工具脚手架）或逗号分隔的工具 id 列表（如 `claude,codex`），大小写不敏感；传入未注册的工具 id SHALL 报错并在 `fix` 中列出全部合法 id。未传 `--tools` 时：若当前处于可交互终端，SHALL 打印已注册工具的编号列表，读取一行逗号分隔的编号或 `all`/`none` 作为选择；若处于非交互环境，SHALL 直接按 `none` 处理（不做任何工具脚手架、不报错、不阻塞），以保持与本参数引入前完全一致的默认行为。交互式列表 SHALL 为每个工具标注其当前状态：已配置且未被选中标注 `(configured)`、已配置且被选中标注 `(refresh)`、探测到对应目录但未配置标注 `(detected)`。

对每个被选中的工具，`init` SHALL 按 `tool-scaffolding` 能力描述的规则写入其 skill 文件与（如有命令适配器）命令文件；这些文件 SHALL 写入项目根目录（默认为 workflow home 的父目录，可用 `--project-root` 覆盖），而非 workflow home 内部。未选择任何工具或全部工具都不支持时，`init` 的其余行为（`config.yaml`/`schemas/`/`changes/` 初始化）SHALL 不受影响。`init` 的响应 SHALL 包含 `projectRoot` 字段，说明脚手架实际写入的根目录。

人类可读模式下，`init` SHALL 按固定顺序渲染分节摘要（各节以空行分隔）：多阶段进度行 → 粗体标题 → `Created:` 与 `Refreshed:` 工具显示名列表（各自非空时才出现）→ 一行聚合计数（写入的 skill 与命令数量及其所在目录）→ 无命令适配器工具的暗色提示 → 配置文件状态行（新建时含 schema 名，已存在时标注为已存在）→ 粗体的 `Getting started:` 段落及首条建议命令 → 项目与反馈链接 → 确有工具被配置时的重启提示。该摘要 SHALL NOT 逐条罗列写入的文件路径。`--json` 模式下 SHALL 不输出上述任何摘要或进度内容，且 JSON 载荷的既有字段名与结构 SHALL 保持不变。

#### Scenario: 默认初始化包含内置 schema
- **WHEN** 执行 `loopspec init ./loopspec`
- **THEN** 生成 `config.yaml`/`schemas/`/`changes/`，且 `schemas/` 下包含内置 schema 的完整拷贝

#### Scenario: --no-builtin 跳过内置 schema
- **WHEN** 执行 `loopspec init ./loopspec --no-builtin`
- **THEN** 生成空的 `schemas/` 目录，不包含任何内置 schema 文件

#### Scenario: 非交互且未传 --tools 时行为不变
- **WHEN** 在非交互环境下执行 `loopspec init ./loopspec`（不传 `--tools`）
- **THEN** 只初始化 `config.yaml`/`schemas/`/`changes/`，不写入任何 `.claude/`/`.codex/` 等工具目录，行为与引入 `--tools` 之前完全一致

#### Scenario: --tools all 选中全部注册工具
- **WHEN** 执行 `loopspec init ./loopspec --tools all`
- **THEN** 为全部已注册工具（`claude`/`codex`/`opencode`/`cursor`/`windsurf`）在项目根目录写入其 skill 文件（及有适配器时的命令文件）

#### Scenario: 脚手架写入项目根而非 workflow home
- **WHEN** 在项目 `myproject/` 下执行 `loopspec init ./loopspec --tools claude`
- **THEN** 文件写入 `myproject/.claude/`，`myproject/loopspec/.claude` 不存在，且响应的 `projectRoot` 为 `myproject` 的绝对路径

#### Scenario: --tools 指定子集
- **WHEN** 执行 `loopspec init ./loopspec --tools claude,codex`
- **THEN** 只为 `claude` 与 `codex` 写入脚手架文件，其余已注册工具不受影响

#### Scenario: --tools 传入未注册的工具 id
- **WHEN** 执行 `loopspec init ./loopspec --tools not-a-real-tool`
- **THEN** 命令报错，`fix` 中列出全部合法工具 id，且不产生任何文件系统变更

#### Scenario: 交互式环境下未传 --tools 时提示选择
- **WHEN** 在可交互终端执行 `loopspec init ./loopspec`（不传 `--tools`）
- **THEN** 打印已注册工具的编号列表，等待用户输入逗号分隔的编号或 `all`/`none`，再按用户选择写入对应脚手架文件

#### Scenario: 交互式列表标注工具当前状态
- **WHEN** 在已为 `claude` 生成过脚手架的项目中，交互式执行 `loopspec init`
- **THEN** 列表中 `claude` 带有状态标注，用于区分本次是新建还是刷新

#### Scenario: 人类可读摘要区分 Created 与 Refreshed
- **WHEN** 首次为 `claude` 生成脚手架后，再次执行同一条 `init --tools claude`
- **THEN** 第一次的摘要把 `claude` 列在 `Created:` 下，第二次列在 `Refreshed:` 下

#### Scenario: 人类可读摘要用聚合计数替代路径明细
- **WHEN** 执行 `loopspec init ./loopspec --tools claude,codex`（不带 `--json`）
- **THEN** 摘要中包含一行写入数量与目标目录的聚合计数，且不出现任何逐条文件路径

#### Scenario: 摘要包含 Getting started 与链接收尾
- **WHEN** 一次成功的人类可读 `init` 完成
- **THEN** 输出末尾依次包含 `Getting started:` 段落、项目与反馈链接，以及（确有工具被配置时的）重启提示

#### Scenario: JSON 模式不输出摘要且字段结构不变
- **WHEN** 执行 `loopspec init ./loopspec --tools claude --json`
- **THEN** stdout 只含一份可整体解析的 JSON，不含摘要或进度行，且既有字段（`workflowHome`/`projectRoot`/`toolsConfigured`/`scaffoldedFiles`/`skippedCommandGeneration` 等）名称与结构均未改变
