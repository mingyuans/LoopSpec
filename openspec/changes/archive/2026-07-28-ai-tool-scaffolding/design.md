## Context

`loopspec init` 目前只初始化 workflow home 本身（`config.yaml`/`schemas/`/`changes/`）。用户提出的需求参照 OpenSpec 项目（`/Users/xq.yan/otherprojects/OpenSpec`）已经落地的方案：`init` 时询问用户在用哪些 AI 编程工具，然后按工具规则把 skill/slash-command 文件写进 `.claude/`、`.codex/`、`.opencode/` 等目录，预置 `/lpsx:new` 一类命令。

调研 OpenSpec 源码（`src/core/init.ts`、`src/core/config.ts`、`src/core/command-generation/**`）确认了以下关键机制，本设计据此裁剪到 loopspec 实际需要的范围（5 个工具、4 个 skill，而不是 OpenSpec 的 30 个工具、12 个 workflow）：

- 工具选择与工具→路径映射是两个独立的东西：`AI_TOOLS` 注册表只管 `skillsDir`（每个工具统一在 `<skillsDir>/skills/<name>/SKILL.md`），命令文件路径则由每个工具各自的 `ToolCommandAdapter` 决定（因为不同工具的 slash command 文件名/位置规则差异很大：Claude Code 用冒号命名空间且项目本地，Codex 的 slash command 反而是全局的，OpenCode/Cursor 用连字符文件名）。
- 命令正文只写一份（`CommandContent`），每个工具的适配器只负责“文件放哪、包什么 frontmatter”，不重新编写正文。
- 没有命令适配器的工具，只跳过命令文件生成，skill 文件照常写；不报错。
- 重新运行 `init` 时，已选工具的 skill/命令文件永远被整体覆盖重写，没有增量 diff、没有逐文件确认；是否已"配置过"某工具，永远是运行时扫描文件系统里对应 SKILL.md 是否存在来判断，从不写一个"已选工具清单"文件。
- `opsx`（对应 loopspec 是 `lpsx`）前缀是硬编码在每个适配器里的字符串，不做成可配置项。

## Goals / Non-Goals

**Goals:**
- `loopspec init` 支持通过交互式选择或 `--tools` 参数，为 Claude Code、Codex、OpenCode、Cursor、Windsurf 生成对应的 skill 文件（全部工具统一规则）和命令文件（工具各自的规则，无适配器时优雅跳过）。
- 预置 4 个 skill/命令：`loopspec-new`、`loopspec-continue`、`loopspec-archive`、`loopspec-bulk-archive`，与 3.10 节描述的 loopspec 主循环一一对应。
- 保持 `loopspec init` 现有行为的向后兼容：不传 `--tools` 且非交互环境下，等价于当前实现（只初始化 workflow home，不做任何工具脚手架）。
- 工具注册表设计上可扩展（新增工具只需要加一条注册 + 可选适配器），但 v1 只内置这 5 个工具的具体实现。

**Non-Goals:**
- 不做 OpenSpec 那种全量 30 工具注册表、也不做 12 个 workflow 的完整移植——只做 loopspec 自己需要的 4 个 skill。
- 不实现 OpenSpec 里花哨的可搜索多选终端 UI（`searchable-multi-select` 自定义 Inquirer 组件）；用简单的编号列表 + 逗号分隔输入即可，避免引入新的 TUI 依赖。
- 不持久化"用户选了哪些工具"到任何配置文件；工具配置状态永远由文件系统现状推导，与 OpenSpec 一致。
- 不做 legacy 文件清理/版本漂移检测（OpenSpec 的 `handleLegacyCleanup`、`getToolVersionStatus` 等）——loopspec 是全新工具，没有历史包袱需要处理。
- 不生成 AGENTS.md 通用兜底文件（OpenSpec 自己也没真正实现这个兜底，只是注册表里一条不可选的占位项）。

## Decisions

### D1. 工具注册表与命令适配器分离，而不是一张大表
**决策**：`AI_TOOLS`（工具 id → `skills_dir`）与 `COMMAND_ADAPTERS`（工具 id → `ToolCommandAdapter` 实例，缺省即无该工具的适配器）分成两个独立的注册表；skill 文件生成只读前者，命令文件生成只读后者。
**理由**：忠实复刻 OpenSpec 的关键洞察——所有工具的 skill 目录规则是统一的（`<skillsDir>/skills/<name>/SKILL.md`），但 slash command 的落盘规则五花八门（Claude 项目本地冒号命名空间、Codex 用户全局、OpenCode/Cursor 连字符文件名），把两者硬耦合在一张表里会让"新增一个只支持 skill、不支持命令的工具"变得别扭。

### D2. `ToolCommandAdapter` 接口：`get_file_path(command_id) -> Path` + `format_file(content) -> str`
**决策**：命令适配器只有两个方法：给定 command id 算出目标文件路径（可以是项目内相对路径解析出的绝对路径，也可以是用户主目录下的绝对路径，如 Codex）；给定通用的 `CommandContent`（`id`/`name`/`description`/`body`）产出该工具specific 格式的完整文件内容（含 frontmatter）。
**备选方案**：让每个适配器自己决定要不要写文件、写到哪、内容是什么（更灵活但更难保证一致性）。
**取舍理由**：两方法接口足够表达 OpenSpec 观察到的全部差异（TOML vs Markdown frontmatter、冒号 vs 连字符命名、项目本地 vs 全局路径），同时保证"一份正文多工具适配"的核心约束不会被绕过。

### D3. Claude Code 冒号命名 + 项目本地；Codex 连字符命名 + 用户全局；OpenCode/Cursor/Windsurf 连字符命名 + 项目本地
**决策**：
- Claude Code：`.claude/commands/lpsx/<verb>.md`，命令名 `/lpsx:<verb>`。
- Codex：`$CODEX_HOME/prompts/lpsx-<verb>.md`（默认 `~/.codex/prompts`，`CODEX_HOME` 环境变量可覆盖），命令名 `/lpsx-<verb>`；这是因为 Codex 的自定义 prompt 机制本身不是仓库范围的。
- OpenCode / Cursor / Windsurf：`.<tool>/commands/lpsx-<verb>.md`，命令名 `/lpsx-<verb>`。
**理由**：直接复用 OpenSpec 已经在生产验证过的各工具约定（对应 `claude.ts`/`codex.ts`/`opencode.ts`/`cursor.ts`/`windsurf.ts` 适配器），不重新发明。

### D4. 连字符命名工具需要把正文里的 `/lpsx:x` 引用改写成 `/lpsx-x`
**决策**：skill/命令正文里如果提到其他 loopspec 命令（例如"回退后重新执行 `/lpsx:continue`"），对 OpenCode/Cursor/Windsurf 这类连字符命名的工具，写入前统一做一次 `/lpsx:(\w[\w-]*)` → `/lpsx-\1` 的正则替换；Claude Code/Codex 不做替换（Codex 本身命令名也是连字符，所以同样需要替换——只有 Claude Code 保留冒号原文）。
**理由**：保证同一份正文在不同工具里引用其他命令时，写出来的引用名和该工具自己解析命令的方式一致，避免用户跟着提示操作却发现命令不存在。

### D5. 无命令适配器的工具只跳过命令生成，不报错、不跳过 skill 生成
**决策**：`COMMAND_ADAPTERS` 里没有登记的工具 id，`init` 会正常写入 4 个 SKILL.md，命令文件生成阶段静默跳过该工具，并在响应的 `nextSteps`/日志里追加一行"已跳过命令文件：<tool>（无命令适配器）"。
**理由**：与 OpenSpec 对 Kimi CLI 的处理保持一致——工具支持是渐进式的，不应该因为某个工具还没适配命令格式就整体报错阻塞用户。当前 v1 的 5 个工具都注册了适配器，这条规则主要是为将来扩展新工具（只想先支持 skill）铺路。

### D6. `--tools` 参数与交互式选择：`all` / `none` / 逗号分隔 id 列表；非交互且未传时默认 `none`
**决策**：`loopspec init [path] [--tools TOOLS] [--no-builtin]`。`--tools` 接受 `all`（全部 5 个工具）、`none`（不做任何工具脚手架）或逗号分隔的工具 id（如 `claude,codex`），大小写不敏感，未知 id 报错并列出合法 id。未传 `--tools`：若当前是交互式终端，打印编号列表（`1) Claude Code  2) Codex  3) OpenCode  4) Cursor  5) Windsurf`）请用户输入逗号分隔的编号或 `all`/`none`；若非交互式终端，直接按 `none` 处理，不报错、不阻塞。
**备选方案**：仿照 OpenSpec，非交互且未传 `--tools` 时报错要求显式传参。
**取舍理由**：loopspec 现有的 18 个 CLI 测试（`tests/test_cli.py`）都是非交互调用 `init` 且不传 `--tools`，仍然期望 `init` 成功初始化 workflow home；选择"默认等价于 `none`"能保持这些既有场景与现有行为完全向后兼容，同时把"必须显式选择工具"这种更严格的 UX 留给真正交互式的场景。

### D7. 简单编号列表交互，而不是可搜索多选组件
**决策**：交互式工具选择用最简单的"打印编号列表 + 读一行逗号分隔输入"实现，不引入 `questionary`/`InquirerPy` 等新依赖，不做类型即时过滤、方向键勾选之类的高级交互。
**备选方案**：引入 `questionary`（成熟、维护活跃的库）实现真正的复选框交互，更接近 OpenSpec 的观感。
**取舍理由**：项目现有依赖策略是"能不加就不加"（D7/pydantic+typer+pyyaml+rich 已经是全部依赖），且 `--json`/脚本化调用才是本工具的主协议，人类交互式的这一步本来就是次要路径；用标准输入/输出就能实现，没必要为了一个次要交互引入新依赖。如果后续用户反馈体验不够好，可以作为独立的后续增强单独提出。

### D8. 覆盖重写、不做持久化工具清单
**决策**：每次 `init` 选中某工具时，无条件重写它的全部 skill/命令文件（`Path.write_text` 直接覆盖），不做"文件已存在就跳过"或逐文件确认；不新增任何记录"用户选过哪些工具"的配置文件（`config.yaml` 保持不变，仍然只有 `artifacts_dir`/`schema` 等字段）。
**理由**：与 D 决策保持一致——`loopspec` 的状态哲学是"文件系统是唯一真相"，工具是否已配置由 SKILL.md 是否存在这件事本身来回答，不需要额外的清单去追踪它，也避免清单与实际文件不同步的经典问题（正是本项目 D1 决策反复强调要避免的模式）。

## Risks / Trade-offs

- **[Risk] 覆盖重写会抹掉用户对已生成 skill/命令文件的手工修改。**
  → Mitigation：这是与 OpenSpec 一致的既有取舍，非本变更引入的新风险；在 `init` 的响应/文档里明确提示"重新运行会覆盖这些文件，如果手工改过请自行备份"。
- **[Risk] Codex 命令写到用户全局目录（`$CODEX_HOME/prompts/`），跨项目共享，多个项目都装 loopspec 可能互相覆盖。**
  → Mitigation：文件内容与 loopspec 命令本身无项目特定信息（都是调用 `loopspec ... --change <change-name>` 这种通用套路，`<change-name>` 由用户在对话里提供），多项目共享同名 prompt 文件本身没有语义冲突；这也是 Codex 自身机制的固有限制，不是 loopspec 引入的问题。
- **[Risk] 简单的编号列表交互在极端窄的终端或非 UTF-8 环境下可能显示不佳。**
  → Mitigation：只用 ASCII 输出（编号、英文工具名），不依赖任何终端特性；非交互环境完全跳过这段代码。
- **[Risk] 正则替换 `/lpsx:x` → `/lpsx-x` 可能误伤正文里恰好长得像命令引用但其实不是的文本。**
  → Mitigation：只在生成阶段对固定的、由我们自己撰写的 4 份模板正文做替换，不对用户输入或运行时数据做替换，误伤面可控；替换规则用专门的单元测试锁定输入输出。

## Migration Plan

全新能力，不影响任何既有数据。实现顺序：先落地 `tool-scaffolding` 的注册表与适配器接口（含无适配器工具的跳过路径），再写 `lpsx-skills` 的 4 份模板正文与命名转换规则，最后把两者接入 `loopspec init` 的 `--tools`/交互分支。每步都要保证 `tests/test_cli.py` 里已有的、非交互零参数调用 `init` 的用例继续通过（回归护栏）。

## Open Questions

- 是否需要一个独立的 `loopspec tools list` 子命令列出当前注册表支持哪些工具（本变更暂不做，可以作为后续增强）。
