# Change State

## Current Focus
- `security` 门禁已 **PASS**（`security/pass.md`），design D10 指定的依赖来源复核已完成、无阻塞问题。
- `approval` 门禁第 1 轮已 **APPROVED**（`approval/approved.md`），人类无限定条件、无调整要求。
- `apply` 已完成：tasks.md 39/39 全部勾选，`make test` 505 passed（基线 268），`make lint` 全绿，报告在 `apply/report.md`。
- 本 change 的全部节点已 done，`isComplete` 为 true，下一步是 `loopspec archive interactive-tool-picker`。归档前需注意 Open Questions 里的 delta 叠加顺序问题仍未解决。

## Frozen Decisions
- [approved] **本变更显式推翻 `improve-init-display` 的两条冻结决定**：其一「不做 banner」→ 本轮做静态欢迎屏与静态 logo（动画仍不做，所以「动画不划算」的判断未被推翻）；其二「不为次要交互引入新依赖」→ 交互已成为本变更的目标本身，前提失效。推翻依据是用户在本轮开工前的三项定案。
- [approved] 用户定案三项：交互库用 **`questionary`**；工具注册表**扩到 OpenSpec 量级（31 个）**；欢迎屏为**静态文案 + 静态色块 logo**。
- [approved] `questionary` 只允许出现在交互路径；`--json` 与非交互路径不得走到需要终端的代码（design D1/D3）。
- [approved] 「已配置」判定始终只看 skill 文件是否存在（既有 `tool_is_configured()`，唯一权威）；新增的「已探测」判定只影响呈现与预选，不参与 created/refreshed 分组（design D4）。
- [approved] 首次 setup 预选**探测到**的工具，已有配置时改为预选**已配置**的工具，使重复运行 `init` 的默认动作是刷新而非扩大范围（design D5）。
- [approved] 命令适配器用参数化形态 + 4 类特例表达，而不是 28 份手写实现；`cline` 的命令目录（`.clinerules`）与 `skills_dir`（`.cline`）解耦、不得相互推导（design D6/D7）。
- [approved] 交互组件的文本安全靠「只喂注册表常量」，不得把 `improve-init-display` 的 D10 转义保证顺延到 `questionary`——它不经过呈现模块的出口（design D8）。
- [approved] **以下 5 条经 `approval` 第 1 轮人类签核（`approval/approved.md`），后续节点不得静默改动；要改需另起一轮 approval：**
- [approved] （签核点 1）tasks.md 的 7 组 39 项实施顺序：第 1 组「依赖与测试地基」（`questionary>=2.1` 入 `pyproject.toml` + `tests/test_tool_picker.py` 的 pipe-input 最小用例 + 按键序列辅助函数）必须先落地并验证可行，再进入第 2 组注册表扩容。
- [approved] （签核点 2）design D3 的单一判定不得拆成两个独立判断：「未显式传 `--tools`」+「`is_interactive()`」+「非 `--json`」三者的合取只计算一次，并同时决定「是否渲染欢迎屏」与「是否启动选择器」，不允许出现渲染了欢迎屏却没有选择器的中间态。
- [approved] （签核点 3）`tests/test_cli.py` 的 JSON 断言与 `tests/test_tools_arg.py` 的 `--tools` 解析断言必须**未经修改**即通过（tasks 6.4），作为「`--tools` 语义、`--json` 输出结构、脚手架落盘规则契约零变化」的证据。
- [approved] （签核点 4）注册表 31 项与命令适配器 28 项的落盘路径以 `specs/tool-scaffolding/spec.md` 的两张表格为准，测试须逐项断言**完整路径字符串**而非抽查（tasks 3.6）；`cline`/`costrict`/`github-copilot`/`gemini`/`qwen`/`continue` 各单列断言。
- [approved] （签核点 5）接受 `security/pass.md` 记录的 4 条非阻塞残余风险：`CODEX_HOME` 未做校验（既有行为、本轮不改）、适配器路径常量约束靠 tasks 3.6 的完整路径断言事实覆盖、非中断类异常下的终端状态恢复、依赖版本下界靠 `uv.lock` 固定。同时接受两项现状：`improve-init-display` → `interactive-tool-picker` 的 delta 叠加顺序由人工保证；`--tools all` 的写入范围由 5 个工具扩到 31 个（含用户全局 `~/.codex/prompts/`）。

## Decision Log
- 2026-07-29: 用户对照 OpenSpec 截图提出两项目标：`init` 欢迎屏（configure 清单 + quick start + Press Enter 收口 + 色块 logo）、可搜索多选工具选择器（方向键/空格/搜索/预选/显示名/分页）。当前实现只有编号列表 + 读一行输入，且列表显示裸 id。
- 2026-07-29: 指出这两项正是 `improve-init-display` 冻结的 Non-Goal，按 approval 门禁的规矩不能在已签核的 change 上改，故新建本 change。
- 2026-07-29: 实测 `questionary` 2.1.1 的 `checkbox()` 具备 `use_search_filter`/`use_arrow_keys`/`instruction`/`initial_choice`，`Choice(checked=True)` 可预选；安装带入 3 个包。
- 2026-07-29: 实测无头可测路径 —— `create_pipe_input()` + `DummyOutput()` 传入 `checkbox()` 后，按键序列 `" \x1b[B \r"` 返回 `['codex']`（取消预选的 Claude、下移、勾选 Codex、回车）。这条决定了选择器不需要真终端也能测（design D2）。
- 2026-07-29: 逐个提取 OpenSpec 28 个适配器的落盘路径，归纳出 `commands`/`prompts`/`workflows` 三种子目录、冒号 vs 连字符两种命名、`.md`/`.toml`/`.prompt`/`.prompt.md` 四种扩展名、三种正文格式；31 个工具中 `forgecode`/`kimi`/`vibe` 无适配器。
- 2026-07-29: 发现 `github-copilot` 的 `skills_dir` 是 `.github`，而该目录几乎每个仓库都有，仅凭目录存在会在首次 setup 时默认勾选 Copilot 并写出一堆文件；故引入 `detection_paths` 精确探测（design D4）。
- 2026-07-29: `apply` 完成，39/39 项落地，`apply/report.md` 记录全部细节。三处与 spec 字面文本的偏离已在报告中列明：(1) `tool_is_detected()` 落在 `tools_cli.py` 而非 `scaffold.py`（tasks 2.3 括号内已授权两者之一；选后者使 D4「探测不参与 created/refreshed 分组」从结构上成立）；(2) 欢迎屏 quick start 列 `/lpsx:archive` 而非 spec 与 tasks 5.2 写的 `/lpsx:apply` —— loopspec 不生成 `/lpsx:apply`（`apply` 是 schema 节点名，由 `/lpsx:continue` 驱动），该命令名系从 OpenSpec 截图照搬之误，按 `init-welcome` 中更强的「SHALL NOT 展示用户敲不出来的命令名」实施并加测试永久绑定；(3) `windsurf` 命令目录由 `.windsurf/commands/` 改为 `.windsurf/workflows/`，依 `tool-scaffolding` spec 表格，但这改变了 `improve-init-display` 时期的既有行为，旧路径遗留文件无清理机制（已记入 Follow-Ups）。
- 2026-07-29: 签核点 3 的护栏证据落实：`tests/test_tools_arg.py` **零改动**通过；`tests/test_cli.py` 全文仅删 1 行——把硬编码 5 个工具 id 的 `toolsConfigured` 断言改为 `set(AI_TOOLS)`，因其断言的是注册表内容（本变更批准的目标）而非 `--tools` 语义/`--json` 结构/落盘规则。
- 2026-07-29: `approval` 门禁第 1 轮 **APPROVED**（`approval/approved.md`，含人类原话）。人类对完整方案摘要（问题陈述、5 份 delta 的能力增改、D1–D10 的决策与取舍、39 项任务的规模与顺序、安全结论与残余风险、以及两项显式交给人类判断的事项）答复「按此方案实施」，无限定条件、无例外、未要求任何调整。据此冻结 5 条签核点（见 Frozen Decisions），并视为接受 `improve-init-display` → `interactive-tool-picker` 的 delta 叠加顺序由人工保证、以及 `--tools all` 写入范围扩到 31 个工具（含用户全局 `~/.codex/prompts/`）这两项现状。
- 2026-07-29: `security` 门禁 PASS。D10 要求的依赖核验在 PyPI 官方注册表逐项完成：`questionary` 2.1.1（MIT，tmbo/questionary）、`prompt_toolkit` 3.0.53（BSD，prompt-toolkit 组织，IPython 底层库）、`wcwidth` 0.8.2（MIT，jquast）—— 三者均为生态主线包、无 typosquatting 迹象、许可宽松，直接依赖面只扩大 1 项。同时确认本变更全程无 shell/subprocess/网络/数据库/不安全反序列化，路径分量全为注册表常量（`--tools` 走白名单校验），故无注入与遍历面；唯一新增的实质攻击面是交互组件绕过 `rich.Text` 转义出口直写终端控制序列，已由 D8「只喂常量」+ task 4.8 的控制字符断言从数据流上断掉。

## Rejected Options
- [superseded] 用 stdlib `termios`/`msvcrt` + `rich.live` 手写可搜索多选器：零新依赖，但要自己处理 raw mode、方向键转义序列、搜索过滤、分页、窄终端与宽字符对齐、Windows 分支；这些边界情况的成本高于一个成熟依赖。
- [superseded] 只做欢迎屏、选择器保留编号列表：用户明确要的是截图里那套交互，只做一半不解决问题。
- [superseded] 保持 5 个工具不扩容：搜索过滤与分页在 5 项上没有意义，扩容是这套 UI 成立的前提。
- [superseded] 逐帧动画 logo：沿用 `improve-init-display` 的判断，OpenSpec 自己在不可动画环境下也只渲染静态帧。
- [superseded] 永远按「探测到」预选：会让重复运行 `init` 悄悄扩大配置范围（用户新装编辑器 → 目录存在 → 被预选 → 回车 → 多出一堆文件）。
- [superseded] 为 31 个工具逐一做人工验收：改为表驱动自动断言全部路径 + 抽样人工验收 5 个特例工具。

## Open Questions
- [under-review] **delta 叠加顺序需要人工保证**：`improve-init-display` 已完成但未归档，其 3 份 delta 尚未应用到 `openspec/specs/`。本轮 `loopspec-cli` 的 MODIFIED 全文以那一版为基线，两者必须按 `improve-init-display` → `interactive-tool-picker` 的顺序应用，反序会丢掉摘要相关段落。`cli-presentation`（两轮都是 ADDED）与 `tool-scaffolding`（上轮 ADDED、本轮 MODIFIED 不同需求）无顺序要求。
- [under-review] loopspec 管理的 change 其 delta 如何进入 `openspec/specs/` 主 spec 库 —— 与 `improve-init-display` 同一个悬而未决的问题（loopspec 没有 delta→主 spec 同步能力），现在多了一份 change 等待同一个决定。
- [under-review] `loopspec/` 目录仍未纳入版本控制，本 change 的规划产物同样落在版本控制之外。
- [under-review] **`windsurf` 旧命令路径的遗留文件无清理机制**：命令目录由 `.windsurf/commands/` 改为 `.windsurf/workflows/` 后，此前配置过 Windsurf 的项目会同时留有两套 `lpsx-*.md`。脚手架的既定语义是「无条件覆盖」而非「同步删除」，需要一个后续 change 决定是否加清理。
- [under-review] **`prompt_tools_interactively()` 已无生产调用方**，仅被测试使用（tasks 4.6 明确要求保留为降级实现）。它与 `pick_tools()` 的长期共存关系需日后重新评估。

## Artifact Notes
- proposal.md: approved（含对 `improve-init-display` 两条冻结决定的显式推翻及其理由）
- specs/: approved（5 份：新增 `init-welcome` 3 需求、新增 `tool-picker` 5 需求；`tool-scaffolding` 2 条 MODIFIED + 1 条 ADDED、`loopspec-cli` 1 条 MODIFIED、`cli-presentation` 3 条 ADDED）
- design.md: approved（D1–D10，含依赖选型论证、无头测试方案、预选分流、适配器参数化、叠加顺序说明）
- tasks.md: approved（7 组共 39 项，第 1 组要求先落地无头测试地基再往下做）
- security（gate）: **PASS** → `security/pass.md`（8 类检查；D10 依赖核验含 PyPI 注册表逐项证据；4 条非阻塞观察：`CODEX_HOME` 未校验属既有行为、适配器常量约束已由 task 3.6 的完整路径断言事实覆盖、非中断类异常下的终端状态恢复、依赖版本下界靠 `uv.lock` 固定）
- approval（gate）: **APPROVED** → `approval/approved.md`（第 1 轮；人类原话「按此方案实施」，无限定条件；冻结 5 条签核点）
- apply（gate）: **完成** → `apply/report.md`（39/39；`make test` 505 passed、`make lint` 全绿；含真 pty 交互验收与 5 个特例工具落盘验收；3 处 spec 偏离与 4 项 Follow-Ups 已列明）
