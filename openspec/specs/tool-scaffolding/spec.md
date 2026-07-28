# tool-scaffolding Specification

## Purpose
TBD - created by archiving change ai-tool-scaffolding. Update Purpose after archive.
## Requirements
### Requirement: AI 工具注册表
系统 SHALL 维护一个 AI 工具注册表，为每个已注册工具声明唯一的工具 id 与 `skills_dir`（如 `claude` → `.claude`）；v1 SHALL 内置注册 `claude`（Claude Code）、`codex`（Codex）、`opencode`（OpenCode）、`cursor`（Cursor）、`windsurf`（Windsurf）五个工具。注册表 SHALL 支持后续新增工具而不影响已注册工具的行为。

#### Scenario: 已注册工具可被查询
- **WHEN** 查询工具注册表中的 `claude`
- **THEN** 返回其 `skills_dir` 为 `.claude`

#### Scenario: 未注册的工具 id 不存在于注册表
- **WHEN** 查询一个未注册的工具 id
- **THEN** 系统能明确判定该 id 不在已注册工具集合中，供上层报错使用

### Requirement: 脚手架写入项目根目录，而非 workflow home
工具脚手架目录（`.claude`/`.codex` 等）SHALL 写入**项目根目录**，因为 AI 编程工具只会在项目根查找这些目录；SHALL NOT 写入 workflow home（`loopspec/`）内部，否则生成的 skill/命令对工具不可见。项目根目录 SHALL 默认解析为 workflow home 的父目录；调用方 SHALL 可以通过显式参数覆盖该默认值。

#### Scenario: 默认写入 workflow home 的父目录
- **WHEN** 在项目 `myproject/` 下执行 `loopspec init ./loopspec --tools claude`
- **THEN** skill/命令文件写入 `myproject/.claude/...`，且 `myproject/loopspec/.claude` 不存在

#### Scenario: 显式覆盖项目根目录
- **WHEN** 执行 `loopspec init <home> --tools claude --project-root <other-dir>`
- **THEN** skill/命令文件写入 `<other-dir>/.claude/...`，不写入 workflow home 的父目录

### Requirement: 统一的 skill 文件落盘规则
系统 SHALL 为每个被选中的工具，把每个 skill 模板写入 `<项目根目录>/<skills_dir>/skills/<template-name>/SKILL.md`，路径规则对所有已注册工具一致，不因工具而异。

#### Scenario: 不同工具的 skill 路径规则一致
- **WHEN** 同一个 skill 模板分别为 `claude` 与 `opencode` 生成文件
- **THEN** 生成路径分别为 `<项目根目录>/.claude/skills/<name>/SKILL.md` 与 `<项目根目录>/.opencode/skills/<name>/SKILL.md`，目录结构规则相同，只有 `skills_dir` 前缀不同

### Requirement: 命令适配器接口
系统 SHALL 定义命令适配器接口，包含两个方法：`get_file_path(command_id)` 返回该工具存放此命令文件的路径（可以是项目内路径，也可以是用户主目录下的绝对路径）；`format_file(content)` 接收通用的命令正文（`id`/`name`/`description`/`body`），返回该工具要求格式（Markdown 或其他）的完整文件内容。同一份命令正文 SHALL 被所有已注册命令适配器复用，适配器只负责路径与格式转换，不重新编写正文语义。

#### Scenario: 同一份正文产出不同工具的文件内容
- **WHEN** 对同一个 `CommandContent` 分别调用 Claude Code 与 Codex 的 `format_file`
- **THEN** 两者产出的文件内容 frontmatter 结构不同，但正文核心指令内容一致

### Requirement: 具体工具的命令落盘规则
系统 SHALL 内置以下命令适配器行为：
- Claude Code：命令文件写入 `.claude/commands/lpsx/<verb>.md`，命令名为 `/lpsx:<verb>`（冒号命名空间，项目本地路径）。
- Codex：命令文件写入 `$CODEX_HOME/prompts/lpsx-<verb>.md`（`CODEX_HOME` 未设置时默认 `~/.codex/prompts`），命令名为 `/lpsx-<verb>`（连字符命名，用户主目录绝对路径，不在项目目录内）。
- OpenCode / Cursor / Windsurf：命令文件写入 `.<tool>/commands/lpsx-<verb>.md`，命令名为 `/lpsx-<verb>`（连字符命名，项目本地路径）。

#### Scenario: Claude Code 命令路径与命名
- **WHEN** 为 Claude Code 生成 `new` 命令
- **THEN** 文件写入 `.claude/commands/lpsx/new.md`，对应命令名为 `/lpsx:new`

#### Scenario: Codex 命令写入用户全局目录
- **WHEN** 为 Codex 生成 `new` 命令，且未设置 `CODEX_HOME` 环境变量
- **THEN** 文件写入 `~/.codex/prompts/lpsx-new.md`（用户主目录下的绝对路径，不在项目目录内），对应命令名为 `/lpsx-new`

#### Scenario: CODEX_HOME 环境变量覆盖 Codex 命令目录
- **WHEN** 设置了 `CODEX_HOME` 环境变量后为 Codex 生成命令
- **THEN** 命令文件写入 `$CODEX_HOME/prompts/` 下，而不是默认的 `~/.codex/prompts/`

#### Scenario: OpenCode/Cursor/Windsurf 命令路径与命名
- **WHEN** 为 OpenCode 生成 `archive` 命令
- **THEN** 文件写入 `.opencode/commands/lpsx-archive.md`，对应命令名为 `/lpsx-archive`

### Requirement: 无命令适配器的工具优雅跳过命令生成
若某个已注册工具没有对应的命令适配器，系统 SHALL 仍正常为其写入全部 skill 文件；命令文件生成阶段 SHALL 跳过该工具，不报错、不中断其余工具的处理，并在响应中说明该工具已跳过命令文件生成及原因。

#### Scenario: 只注册了 skills_dir 没有命令适配器的工具
- **WHEN** 某工具在注册表中只声明了 `skills_dir`，未注册命令适配器
- **THEN** 该工具的 4 个 skill 文件正常写入，命令文件生成被跳过，且整体 `init` 调用不报错

### Requirement: 覆盖重写、不持久化工具选择
系统 SHALL 在每次为某工具生成脚手架文件时，无条件覆盖重写该工具的全部 skill 与命令文件（不做增量 diff、不逐文件确认、不检测文件是否已存在再决定是否跳过）。系统 SHALL NOT 引入任何独立的配置文件记录"用户选择过哪些工具"；某工具是否已配置 SHALL 始终通过检查其 skill 文件在磁盘上是否存在来判定。

#### Scenario: 重复运行 init 覆盖已有脚手架文件
- **WHEN** 对已经生成过脚手架文件的工具再次运行 `init` 并选中该工具
- **THEN** 该工具的 skill/命令文件被整体重新写入，即使磁盘上已存在同名文件也不报错、不跳过

#### Scenario: 不产生工具选择清单文件
- **WHEN** 完成一次带工具选择的 `init` 调用
- **THEN** `config.yaml` 内容不包含任何"已选工具"字段，也不产生额外的工具选择记录文件

### Requirement: --tools 参数解析
系统 SHALL 解析 `--tools` 参数为工具 id 集合：`all` 展开为全部已注册工具 id；`none` 展开为空集合；逗号分隔的显式 id 列表 SHALL 大小写不敏感地匹配注册表，并对未知 id 报错，错误信息 SHALL 列出全部合法工具 id 作为修复建议。

#### Scenario: --tools all 展开为全部工具
- **WHEN** 解析 `--tools all`
- **THEN** 得到当前注册表中全部工具 id 的集合

#### Scenario: --tools none 展开为空集合
- **WHEN** 解析 `--tools none`
- **THEN** 得到空集合，不触发任何脚手架写入

#### Scenario: 未知工具 id 报错并列出合法选项
- **WHEN** 解析 `--tools foo,claude`，其中 `foo` 不是已注册工具
- **THEN** 系统报错，且错误的 `fix` 字段中列出全部合法工具 id

