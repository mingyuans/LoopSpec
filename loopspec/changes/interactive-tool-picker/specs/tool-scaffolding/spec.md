## MODIFIED Requirements

### Requirement: AI 工具注册表
系统 SHALL 维护一个 AI 工具注册表，为每个已注册工具声明唯一的工具 id、`skills_dir`（如 `claude` → `.claude`）与**人类可读显示名**（如 `claude` → `Claude Code`）。显示名 SHALL 用于一切面向人类的呈现（选择器候选项、进度行、摘要的 Created/Refreshed 列表）；工具 id SHALL 仅用于 `--tools` 参数、JSON 输出与内部索引。未声明显示名的工具 SHALL 回退为其 id，使新增工具不因漏填显示名而报错。

注册表 SHALL 内置以下 31 个工具（id → `skills_dir` → 显示名）：

| id | skills_dir | 显示名 | id | skills_dir | 显示名 |
| --- | --- | --- | --- | --- | --- |
| `amazon-q` | `.amazonq` | Amazon Q Developer | `kilocode` | `.kilocode` | Kilo Code |
| `antigravity` | `.agent` | Antigravity | `kimi` | `.kimi` | Kimi CLI |
| `auggie` | `.augment` | Auggie (Augment CLI) | `kiro` | `.kiro` | Kiro |
| `bob` | `.bob` | Bob Shell | `lingma` | `.lingma` | Lingma |
| `claude` | `.claude` | Claude Code | `oh-my-pi` | `.omp` | Oh My Pi |
| `cline` | `.cline` | Cline | `opencode` | `.opencode` | OpenCode |
| `codebuddy` | `.codebuddy` | CodeBuddy Code (CLI) | `pi` | `.pi` | Pi |
| `codex` | `.codex` | Codex | `qoder` | `.qoder` | Qoder |
| `continue` | `.continue` | Continue | `qwen` | `.qwen` | Qwen Code |
| `costrict` | `.cospec` | CoStrict | `roocode` | `.roo` | RooCode |
| `crush` | `.crush` | Crush | `trae` | `.trae` | Trae |
| `cursor` | `.cursor` | Cursor | `vibe` | `.vibe` | Mistral Vibe |
| `factory` | `.factory` | Factory Droid | `windsurf` | `.windsurf` | Windsurf |
| `forgecode` | `.forge` | ForgeCode | `github-copilot` | `.github` | GitHub Copilot |
| `gemini` | `.gemini` | Gemini CLI | `iflow` | `.iflow` | iFlow |
| `junie` | `.junie` | Junie | | | |

注册表 SHALL 支持后续新增工具而不影响已注册工具的行为。

#### Scenario: 已注册工具可被查询
- **WHEN** 查询工具注册表中的 `claude`
- **THEN** 返回其 `skills_dir` 为 `.claude`，显示名为 `Claude Code`

#### Scenario: 未注册的工具 id 不存在于注册表
- **WHEN** 查询一个未注册的工具 id
- **THEN** 系统能明确判定该 id 不在已注册工具集合中，供上层报错使用

#### Scenario: 全部 31 个工具均可查询到 skills_dir 与显示名
- **WHEN** 遍历注册表中的每一个工具 id
- **THEN** 每项都返回非空的 `skills_dir` 与非空显示名，且 `skills_dir` 互不重复（`github-copilot` 的 `.github` 除外无冲突）

#### Scenario: 未声明显示名的工具回退为 id
- **WHEN** 注册一个只声明了 id 与 `skills_dir` 的工具
- **THEN** 其显示名回退为该 id，呈现层不报错

### Requirement: 具体工具的命令落盘规则
命令文件的落盘规则 SHALL 由若干**参数化形态**加少量特例表达，而不是为每个工具手写一份实现。形态由三个维度决定：命令子目录（`commands`/`prompts`/`workflows`）、命名方式（冒号命名空间 `<subdir>/lpsx/<verb>` 与命令名 `/lpsx:<verb>`，或连字符 `<subdir>/lpsx-<verb>` 与命令名 `/lpsx-<verb>`）、文件扩展名与正文格式。

系统 SHALL 内置以下落盘规则（路径相对项目根目录，除 Codex 外）：

| 工具 | 命令文件路径 | 命令名 |
| --- | --- | --- |
| `claude` | `.claude/commands/lpsx/<verb>.md` | `/lpsx:<verb>` |
| `codebuddy` | `.codebuddy/commands/lpsx/<verb>.md` | `/lpsx:<verb>` |
| `crush` | `.crush/commands/lpsx/<verb>.md` | `/lpsx:<verb>` |
| `lingma` | `.lingma/commands/lpsx/<verb>.md` | `/lpsx:<verb>` |
| `qoder` | `.qoder/commands/lpsx/<verb>.md` | `/lpsx:<verb>` |
| `gemini` | `.gemini/commands/lpsx/<verb>.toml`（TOML 正文） | `/lpsx:<verb>` |
| `auggie` / `bob` / `cursor` / `factory` / `iflow` / `junie` / `oh-my-pi` / `opencode` / `roocode` / `trae` | `<skills_dir>/commands/lpsx-<verb>.md` | `/lpsx-<verb>` |
| `qwen` | `.qwen/commands/lpsx-<verb>.toml`（TOML 正文） | `/lpsx-<verb>` |
| `costrict` | `.cospec/loopspec/commands/lpsx-<verb>.md` | `/lpsx-<verb>` |
| `amazon-q` / `pi` | `<skills_dir>/prompts/lpsx-<verb>.md` | `/lpsx-<verb>` |
| `continue` | `.continue/prompts/lpsx-<verb>.prompt` | `/lpsx-<verb>` |
| `github-copilot` | `.github/prompts/lpsx-<verb>.prompt.md` | `/lpsx-<verb>` |
| `kiro` | `.kiro/prompts/lpsx-<verb>.prompt.md` | `/lpsx-<verb>` |
| `antigravity` / `kilocode` / `windsurf` | `<skills_dir>/workflows/lpsx-<verb>.md` | `/lpsx-<verb>` |
| `cline` | `.clinerules/workflows/lpsx-<verb>.md`（正文用 `# <name>` 标题，无 frontmatter） | `/lpsx-<verb>` |
| `codex` | `$CODEX_HOME/prompts/lpsx-<verb>.md`（未设置时 `~/.codex/prompts`，用户全局） | `/lpsx-<verb>` |

`cline` 的命令目录 SHALL 是 `.clinerules/`，与其 `skills_dir`（`.cline`）不同——两者 SHALL NOT 相互推导。`costrict` 的命令路径 SHALL 在 `.cospec/` 下嵌一层 `loopspec/`（即工具方要求的「按来源工具分目录」约定）。`forgecode`、`kimi`、`vibe` 三个工具 SHALL NOT 注册命令适配器，按「无命令适配器的工具优雅跳过命令生成」处理。

#### Scenario: 冒号命名空间工具的路径与命名
- **WHEN** 为 Claude Code 生成 `new` 命令
- **THEN** 文件写入 `.claude/commands/lpsx/new.md`，对应命令名为 `/lpsx:new`

#### Scenario: 连字符命名工具的路径与命名
- **WHEN** 为 OpenCode 生成 `archive` 命令
- **THEN** 文件写入 `.opencode/commands/lpsx-archive.md`，对应命令名为 `/lpsx-archive`

#### Scenario: Codex 命令写入用户全局目录
- **WHEN** 为 Codex 生成 `new` 命令，且未设置 `CODEX_HOME` 环境变量
- **THEN** 文件写入 `~/.codex/prompts/lpsx-new.md`（用户主目录下的绝对路径，不在项目目录内），对应命令名为 `/lpsx-new`

#### Scenario: CODEX_HOME 环境变量覆盖 Codex 命令目录
- **WHEN** 设置了 `CODEX_HOME` 环境变量后为 Codex 生成命令
- **THEN** 命令文件写入 `$CODEX_HOME/prompts/` 下，而不是默认的 `~/.codex/prompts/`

#### Scenario: TOML 正文格式的工具
- **WHEN** 为 Gemini CLI 生成 `new` 命令
- **THEN** 文件写入 `.gemini/commands/lpsx/new.toml`，其正文为 TOML 而非 Markdown frontmatter

#### Scenario: 双扩展名的工具
- **WHEN** 为 GitHub Copilot 生成 `new` 命令
- **THEN** 文件写入 `.github/prompts/lpsx-new.prompt.md`

#### Scenario: 命令目录与 skills_dir 不一致的工具
- **WHEN** 为 Cline 生成 skill 与命令文件
- **THEN** skill 写入 `.cline/skills/<name>/SKILL.md`，命令写入 `.clinerules/workflows/lpsx-<verb>.md`，且命令正文以 `# <命令名>` 标题开头、不含 frontmatter

#### Scenario: 命令路径需嵌套来源目录的工具
- **WHEN** 为 CoStrict 生成 `new` 命令
- **THEN** 文件写入 `.cospec/loopspec/commands/lpsx-new.md`

#### Scenario: 未注册适配器的工具只写 skill
- **WHEN** 为 ForgeCode、Kimi CLI 或 Mistral Vibe 生成脚手架
- **THEN** 其 skill 文件正常写入，命令文件生成被跳过并在响应中说明，整体调用不报错

## ADDED Requirements

### Requirement: 工具目录的多路径探测
工具的「是否探测到」判定 SHALL 默认检查其 `skills_dir` 目录是否存在；对该判定不适用的工具，注册表 SHALL 支持声明一组**探测路径**，其中任一路径存在即视为探测到该工具。`github-copilot` SHALL 使用探测路径而非目录存在性，因为 `.github/` 目录在几乎所有仓库中都存在（CI 配置等），仅凭它存在会把每个仓库都误判为「使用 GitHub Copilot」。

探测 SHALL 只影响呈现与预选，SHALL NOT 影响「是否已配置」的判定（后者始终只看 skill 文件是否存在）。

#### Scenario: 默认按 skills_dir 目录探测
- **WHEN** 项目根目录下存在 `.cursor/` 目录
- **THEN** Cursor 被判定为已探测到

#### Scenario: GitHub Copilot 不因 .github 目录存在而被探测到
- **WHEN** 项目根目录下存在 `.github/` 但其中没有任何 Copilot 相关文件
- **THEN** GitHub Copilot **不**被判定为已探测到

#### Scenario: GitHub Copilot 的探测路径命中
- **WHEN** 项目中存在 `.github/copilot-instructions.md`（或其声明的其他探测路径之一）
- **THEN** GitHub Copilot 被判定为已探测到

#### Scenario: 探测不改变已配置判定
- **WHEN** 某工具被探测到但其 skill 文件不存在
- **THEN** 该工具仍被判定为**未配置**，脚手架结果把它归入 created 而非 refreshed
