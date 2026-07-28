## MODIFIED Requirements

### Requirement: loopspec init 初始化 workflow home
`loopspec init [path] [--tools TOOLS] [--project-root DIR]` SHALL 在指定路径（缺省为 `./loopspec`）创建 workflow home，包含 `config.yaml`（含默认 `artifacts_dir: changes` 与默认 `schema`）、空的 `schemas/` 目录与空的 `changes/` 目录；默认 SHALL 同时把内置 schema 复制到 `schemas/` 下；传入 `--no-builtin` SHALL 跳过复制，只生成空骨架。

`--tools` 参数 SHALL 接受 `all`（选中全部已注册工具）、`none`（不做任何工具脚手架）或逗号分隔的工具 id 列表（如 `claude,codex`），大小写不敏感；传入未注册的工具 id SHALL 报错并在 `fix` 中列出全部合法 id。未传 `--tools` 时：若当前处于可交互终端，SHALL 打印已注册工具的编号列表，读取一行逗号分隔的编号或 `all`/`none` 作为选择；若处于非交互环境，SHALL 直接按 `none` 处理（不做任何工具脚手架、不报错、不阻塞），以保持与本参数引入前完全一致的默认行为。

对每个被选中的工具，`init` SHALL 按 `tool-scaffolding` 能力描述的规则写入其 skill 文件与（如有命令适配器）命令文件；这些文件 SHALL 写入项目根目录（默认为 workflow home 的父目录，可用 `--project-root` 覆盖），而非 workflow home 内部。未选择任何工具或全部工具都不支持时，`init` 的其余行为（`config.yaml`/`schemas/`/`changes/` 初始化）SHALL 不受影响。`init` 的响应 SHALL 包含 `projectRoot` 字段，说明脚手架实际写入的根目录。

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
