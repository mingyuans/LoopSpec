## Context

`improve-init-display` 已经把 `init` 的**输出**对齐 OpenSpec（分节摘要、Created/Refreshed、聚合计数、进度行），但**交互**没动：工具选择仍是编号列表 + 读一行输入，且列表里显示的是裸 id。

用户给出的目标形态有两部分（附了 OpenSpec 的实际截图）：

```
Welcome to OpenSpec
A lightweight spec-driven framework

This setup will configure:
  • Agent Skills for AI tools
  • /opsx:* slash commands

Quick start after setup:
  /opsx:new       Create a change
  /opsx:continue  Next artifact
  /opsx:apply     Implement tasks

Press Enter to select tools...
```

```
Detected tool directories: Claude Code (pre-selected for first-time setup)
? Select tools to set up (31 available)
  Selected:  Claude Code
  Search: [type to filter]
  ↑↓ navigate • Space toggle • Backspace remove • Enter confirm
  › ◉ Claude Code (selected)
    ○ Amazon Q Developer
    ...
  (1/3)
```

**本变更显式推翻 `improve-init-display` 的两条冻结决定**（记录在其 `state.md` 的 Non-Goals / Rejected Options）：

| 上一轮的决定 | 当时的理由 | 为什么现在推翻 |
| --- | --- | --- |
| 不实现动画 logo，连静态 banner 也不做 | 投入产出不划算 | 用户把欢迎屏定为目标；本轮只做**静态**一帧，动画仍是 Non-Goal，所以「不划算」的那部分并未被推翻 |
| 不升级为方向键 + 可搜索多选 | 需要裸终端输入处理**或引入新依赖**，与「不为次要交互引入新依赖」冲突 | 交互不再是「次要项」而是本变更的目标本身，前提失效；用户已在本轮选定「引入 `questionary`」 |

调研与实测结论（已在本机验证，不是文档推断）：

- `questionary` **2.1.1** 的 `checkbox()` 签名含 `use_search_filter`、`use_arrow_keys`、`use_jk_keys`、`instruction`、`initial_choice`、`pointer`、`show_description`；预选通过 `Choice(..., checked=True)`。安装带入 3 个包：`questionary`、`prompt_toolkit`、`wcwidth`。
- 无头可测：`prompt_toolkit.input.create_pipe_input()` + `output=DummyOutput()` 传给 `checkbox(..., input=, output=)` 后，用 `" \x1b[B \r"` 这样的字节流驱动按键，`unsafe_ask()` 返回 `['codex']`（初始勾选的 Claude 被空格取消、下移、勾选 Codex、回车）。这条实测决定了整套选择器**不需要真终端也能测**。
- OpenSpec 的工具注册表在 `src/core/config.ts`：32 条，其中 31 条 `available: true`（第 32 条 `agents` 是 `available: false` 的占位）。这解释了截图里的 `(31 available)`。
- 命令适配器在 `src/core/command-generation/adapters/`：**28 个**（不含 `index.ts`），即 31 个工具中 `forgecode`/`kimi`/`vibe` 三个没有适配器 —— 正好对应 loopspec 既有的「无适配器只写 skill」规则。
- 逐个提取 28 个适配器的落盘路径后，形态可归纳为：`commands/`（17）、`prompts/`（6）、`workflows/`（3）、`.clinerules/workflows/`（1）、Codex 用户全局（1）；命名分冒号命名空间（6 个工具）与连字符（其余）；正文格式有 Markdown frontmatter、TOML（`gemini`/`qwen`）、无 frontmatter 的 `# 标题`（`cline`）三种；扩展名有 `.md`、`.toml`、`.prompt`、`.prompt.md` 四种。

## Goals / Non-Goals

**Goals:**
- `init` 在交互式场景下先给欢迎屏（静态文案 + 静态色块 logo），再给可搜索多选器。
- 选择器达到截图的能力：方向键导航、空格勾选、输入过滤、回车确认、显示名 + 状态标注、可用计数与分页、首次 setup 预选探测到的工具。
- 工具注册表扩到 31 个，命令适配器按归纳出的参数化形态批量补齐（含 4 类特例）。
- 非 TTY / `--json` / 显式 `--tools` 三条路径完全不碰交互库，行为与现在一致。
- 选择器与欢迎屏都能在**没有真终端**的测试环境里被断言。

**Non-Goals:**
- 不做逐帧动画 logo（这一条继续沿用 `improve-init-display` 的判断）。
- 不改 `--tools` 的参数语法与解析规则。
- 不把这套交互推广到其余命令（`status`/`instructions`/... 仍是既有输出）。
- 不为 31 个工具做逐一人工验收 —— 改为表驱动自动断言 + 抽样人工验收。
- 不移植 OpenSpec 的 `available: false` 占位项（`AGENTS.md` 那条），loopspec 注册表只放真正能生成文件的工具。

## Decisions

### D1. 引入 `questionary`，而不是手写 raw-mode 输入
**决策**：新增依赖 `questionary>=2.1`，用其 `checkbox()` 实现选择器。
**备选方案**：`termios`/`msvcrt` + `rich.live` 手写；或 `InquirerPy`/`prompt_toolkit` 直接用。
**取舍理由**：手写方案要自己处理 raw mode、方向键转义序列、搜索过滤、分页、窄终端与宽字符对齐、Windows 分支——这些恰恰是「看起来简单、实际全是边界情况」的一类代码，而 `questionary` 的 `use_search_filter` + `Choice(checked=)` + `instruction` 已经一一对上截图里的每个元素（已实测）。直接用 `prompt_toolkit` 等于自己重写 questionary 的那层封装。代价是依赖树多 3 个包；`questionary` 本身是 prompt_toolkit 生态里长期维护的成熟库，安装体积与 `rich` 同量级。
**约束**：`questionary` 的 import 与调用 SHALL 只出现在交互路径。`--json` 与非交互路径不得走到它需要终端的代码。

### D2. 选择器的输入/输出可注入，测试不依赖真终端
**决策**：封装一层 `pick_tools(project_path, *, input=None, output=None)`，把 `input`/`output` 透传给 `questionary.checkbox()`；测试用 `create_pipe_input()` + `DummyOutput()` 驱动按键序列。
**理由**：这是 `improve-init-display` 里「`Console` 必须可注入」那条决策的同构延伸——交互组件如果不能注入输入，就只能靠人工验收，而 31 个工具 × 多种预选状态的组合根本不适合人工覆盖。实测已确认该注入方式可行（见 Context）。
**代价**：按键序列断言可读性一般（`" \x1b[B \r"` 需要注释说明），因此测试里 SHALL 为每个按键序列写明其语义。

### D3. 欢迎屏与选择器的触发条件收敛为一个判定
**决策**：只有「未显式传 `--tools`」且「`is_interactive()` 为真」且「非 `--json`」三者同时成立时，才渲染欢迎屏并启动选择器；三者任一不成立即走既有路径。这个判定 SHALL 计算一次并同时决定两者，不允许出现「渲染了欢迎屏却没有选择器」的中间态。
**理由**：欢迎屏的收尾是 `Press Enter to select tools...`，如果它出现了而选择器没出现，就是在骗用户按回车。把两者绑成同一个条件从结构上排除这种不一致。

### D4. 注册表增加显示名与探测路径两个维度
**决策**：`ToolSpec` 已有 `display_name`（`improve-init-display` 落地）；本轮新增可选的 `detection_paths: tuple[str, ...] | None`。判定分两层：**已配置** = 该工具的 skill 文件存在（既有 `tool_is_configured()`，唯一权威）；**已探测** = 有 `detection_paths` 时任一路径存在，否则 `skills_dir` 目录存在。
**理由**：`github-copilot` 的 `skills_dir` 是 `.github`，而 `.github/` 几乎每个仓库都有（CI 配置），仅凭目录存在会把所有仓库都误判为「在用 Copilot」并在首次 setup 时**默认勾选**它——这会让用户莫名其妙多出一堆 `.github/prompts/lpsx-*.prompt.md`。OpenSpec 用 `detectionPaths` 精确到 `.github/copilot-instructions.md` 等具体文件，本设计照搬这一点。
**边界**：探测只影响呈现与预选，不参与 created/refreshed 分组（那个只看 skill 文件）。

### D5. 预选规则按「是否首次 setup」分流
**决策**：目标项目根目录下若**没有任何**工具已配置（首次 setup）→ 预选所有**探测到**的工具，并在选择器上方打一行 `Detected tool directories: <显示名列表> (pre-selected for first-time setup)`；若已有工具配置过 → 预选**已配置**的工具。
**备选方案**：永远预选探测到的工具。
**取舍理由**：重复运行 `init` 的意图通常是「刷新我已经配好的那几个」，而不是「把新装的编辑器也一起配上」。永远按探测预选会让第二次运行悄悄扩大配置范围（用户装了别的编辑器 → 目录存在 → 被预选 → 回车 → 多出一堆文件）。按已配置预选让重复运行的默认动作等于「刷新」，与摘要里 Created/Refreshed 的语义保持一致。

### D6. 命令适配器用参数化形态 + 特例，而不是 28 份手写实现
**决策**：定义一个参数化适配器，字段为：`tool_dir`（命令根目录，默认取 `skills_dir`，`cline` 覆盖为 `.clinerules`）、`subdir`（`commands`/`prompts`/`workflows`）、`namespaced`（True → `<subdir>/lpsx/<verb><ext>` + `/lpsx:<verb>`；False → `<subdir>/lpsx-<verb><ext>` + `/lpsx-<verb>`）、`extension`（`.md`/`.toml`/`.prompt`/`.prompt.md`）、`body_format`（`md_frontmatter`/`toml`/`heading`）、`nested`（`costrict` 需要在 `.cospec/` 下嵌 `loopspec/`）。Codex 保留独立实现（用户全局路径 + `CODEX_HOME`）。
**理由**：28 份手写实现里真正不同的只有这几个维度（已逐个提取验证），参数化后新增工具是加一行数据而不是加一个类；同时把「命名方式」与既有的 `hyphenated` 标志统一到 `namespaced` 一个来源，避免两处各自判断导致 skill 正文里的 `/lpsx:x` 转换与命令文件名不一致。
**代价**：参数组合可能产出「理论上合法但没有工具真的这么用」的形态；用表驱动测试逐个工具断言实际路径来兜住。

### D7. `cline` 的命令目录与 `skills_dir` 解耦
**决策**：`cline` 的 `skills_dir` 是 `.cline`，命令目录是 `.clinerules/workflows/`；适配器的 `tool_dir` 与注册表的 `skills_dir` SHALL 是两个独立字段，不得相互推导。
**理由**：这是调研中唯一一个两者不同的工具，如果按「命令目录 = skills_dir」的惯例推导，会把命令写进 `.cline/workflows/` —— 一个 Cline 根本不读的位置，且没有任何报错，属于静默失效。

### D8. 交互组件的文本安全靠「只喂常量」，而不是靠转义
**决策**：传入选择器的候选项文本只允许来自注册表常量（显示名）与固定的状态标注字符串；不允许拼接路径、用户输入或文件内容。
**理由**：`improve-init-display` 的 D10 保证「呈现模块的插值内容一律安全」，但那个保证的实现是「构造 `rich.Text` 对象」——`questionary`/`prompt_toolkit` 完全不经过这个出口，把 D10 的结论顺延到交互组件上是错的。与其为交互组件再造一套转义，不如从数据流上断掉风险：候选项文本全是编译期常量，就没有注入面。将来若确实要在选择器里展示路径，必须先净化再传入（已写进 spec）。

### D9. 用户中断按「放弃工具配置」处理，而不是让异常冒到栈顶
**决策**：`questionary` 在 Ctrl+C 时（`unsafe_ask()` 抛 `KeyboardInterrupt`；`ask()` 返回 `None`）SHALL 被翻译为「本次不配置任何工具」：不写脚手架，正常收尾并给一行说明。
**理由**：`init` 已经在选择器之前创建了 workflow home 骨架，此时抛栈会留下一个「已建目录但没有任何提示」的现场。按 `none` 收尾语义清晰，且用户重跑 `init` 即可继续（脚手架本来就是覆盖重写的）。

### D10. 依赖新增需过 `security` 门禁复核
**决策**：把「新增 `questionary` 及其传递依赖 `prompt_toolkit`/`wcwidth` 的来源与维护状态」显式列为本轮 `security` 门禁的复核项之一。
**理由**：项目策略要求「添加依赖前必须核验包的真实性与维护状况」，而本变更是 loopspec 第二次真正引入运行时依赖（第一次是启用既有的 `rich`）。这条决策的作用是让门禁**必须**看这件事，而不是默认它没问题。

## Risks / Trade-offs

- **[Risk] 依赖树扩大（+3 包）带来安装体积与供应链面。** → Mitigation：只引入 `questionary` 一个直接依赖，不引入 `InquirerPy`/自研 TUI；由 `security` 门禁复核来源（D10）；交互路径与 `--json` 路径分层，JSON 协议不依赖它。
- **[Risk] `questionary`/`prompt_toolkit` 在非 TTY 下抛错，污染 CI 与脚本场景。** → Mitigation：D3 的单一判定确保非交互环境根本不会调到它；新增测试断言非 TTY 下 `init` 不启动选择器且正常完成。
- **[Risk] 31 个工具的落盘路径写错一处就是静默失效（文件写到工具不读的位置，无任何报错）。** → Mitigation：表驱动测试逐个工具断言 skill 路径与命令路径的**完整字符串**，而不是抽查；`cline`（D7）、`costrict`、`github-copilot`、`gemini`/`qwen` 这些特例各自单列一条断言。
- **[Risk] 首次 setup 的预选把用户不想配的工具默认勾上，回车即产生一堆文件。** → Mitigation：D4 的 `detection_paths` 让 `.github` 这类共有目录不触发探测；D5 让重复运行只预选已配置项；界面明确写出「哪些是被预选的、为什么」。
- **[Risk] 交互组件绕过了 D10 的转义出口，可能重新引入静默篡改/崩溃。** → Mitigation：D8 从数据流上断掉（只喂常量）；新增测试遍历全部显示名断言不含控制字符。
- **[Risk] 按键序列测试可读性差，后人改不动。** → Mitigation：测试中每个按键序列必须带注释说明其语义；提供一个把「人类可读动作列表」翻译成字节序列的小工具函数。
- **[Risk] 与 `improve-init-display` 的 delta 叠加冲突。** → 见下节。

## Migration Plan

**叠加依赖（必须先说清）**：`improve-init-display` 已完成但**尚未归档**，其 3 份 delta spec（`cli-presentation` 新增、`loopspec-cli` 修改、`tool-scaffolding` 新增）**尚未应用**到 `openspec/specs/`。本变更的 delta 以那 3 份为基线：

- 本轮 `loopspec-cli` 的 MODIFIED 全文是在 `improve-init-display` 的版本上继续修改的，两者 SHALL 按 `improve-init-display` → `interactive-tool-picker` 的顺序应用；反序会丢掉摘要相关的段落。
- 本轮 `cli-presentation` 只用 ADDED，与上一轮的 ADDED 可交换顺序，无冲突。
- 本轮 `tool-scaffolding` 的 MODIFIED 针对的是主 spec 库里已有的两条需求（`AI 工具注册表`、`具体工具的命令落盘规则`），与上一轮该能力的 ADDED（created/refreshed 上报）互不重叠。

实现顺序：

1. `pyproject.toml` 加 `questionary>=2.1`，`uv sync`；先写一条最小的「注入 pipe input 能跑通 checkbox」的测试，确认环境可用再往下做（避免在 31 个工具都写完后才发现测试方式不可行）。
2. 注册表扩容到 31 项（含显示名、`detection_paths`），同步扩探测逻辑；此时 `--tools all` 会一次写 31 个工具的文件，测试需用 tmp 目录并隔离 `CODEX_HOME`。
3. 参数化命令适配器 + 4 类特例，补齐 28 个适配器；表驱动测试逐个断言路径。
4. `pick_tools()` 选择器 + 预选规则 + 降级路径。
5. 欢迎屏（含静态 logo）接入 `presentation.py`，`init` 按 D3 的单一判定调用。
6. README 更新，全量 `make lint`/`make test`，抽样人工验收（TTY 下真实跑一次交互、非 TTY 与 `--json` 各一次）。

每一步都必须保持既有 `--json` 断言与 `--tools` 解析测试全绿作为契约护栏。

## Open Questions

- 无（依赖选型、注册表规模、logo 形态三项已由用户在本轮开工前定案：`questionary`、扩到 31 个、静态文案 + 静态色块 logo）。
