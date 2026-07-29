# Change State

## Current Focus
- 规划产物已齐（proposal / specs ×5 / design / tasks）。下一个节点是 `security` 门禁，其复核项之一由 design D10 显式指定：新增依赖 `questionary` 及其传递依赖 `prompt_toolkit`/`wcwidth` 的来源与维护状态。
- 门禁通过后是 `approval`（人类签核），再进 `apply` 按 tasks.md 7 组 39 项实现。

## Frozen Decisions
- [approved] **本变更显式推翻 `improve-init-display` 的两条冻结决定**：其一「不做 banner」→ 本轮做静态欢迎屏与静态 logo（动画仍不做，所以「动画不划算」的判断未被推翻）；其二「不为次要交互引入新依赖」→ 交互已成为本变更的目标本身，前提失效。推翻依据是用户在本轮开工前的三项定案。
- [approved] 用户定案三项：交互库用 **`questionary`**；工具注册表**扩到 OpenSpec 量级（31 个）**；欢迎屏为**静态文案 + 静态色块 logo**。
- [approved] `questionary` 只允许出现在交互路径；`--json` 与非交互路径不得走到需要终端的代码（design D1/D3）。
- [approved] 「已配置」判定始终只看 skill 文件是否存在（既有 `tool_is_configured()`，唯一权威）；新增的「已探测」判定只影响呈现与预选，不参与 created/refreshed 分组（design D4）。
- [approved] 首次 setup 预选**探测到**的工具，已有配置时改为预选**已配置**的工具，使重复运行 `init` 的默认动作是刷新而非扩大范围（design D5）。
- [approved] 命令适配器用参数化形态 + 4 类特例表达，而不是 28 份手写实现；`cline` 的命令目录（`.clinerules`）与 `skills_dir`（`.cline`）解耦、不得相互推导（design D6/D7）。
- [approved] 交互组件的文本安全靠「只喂注册表常量」，不得把 `improve-init-display` 的 D10 转义保证顺延到 `questionary`——它不经过呈现模块的出口（design D8）。

## Decision Log
- 2026-07-29: 用户对照 OpenSpec 截图提出两项目标：`init` 欢迎屏（configure 清单 + quick start + Press Enter 收口 + 色块 logo）、可搜索多选工具选择器（方向键/空格/搜索/预选/显示名/分页）。当前实现只有编号列表 + 读一行输入，且列表显示裸 id。
- 2026-07-29: 指出这两项正是 `improve-init-display` 冻结的 Non-Goal，按 approval 门禁的规矩不能在已签核的 change 上改，故新建本 change。
- 2026-07-29: 实测 `questionary` 2.1.1 的 `checkbox()` 具备 `use_search_filter`/`use_arrow_keys`/`instruction`/`initial_choice`，`Choice(checked=True)` 可预选；安装带入 3 个包。
- 2026-07-29: 实测无头可测路径 —— `create_pipe_input()` + `DummyOutput()` 传入 `checkbox()` 后，按键序列 `" \x1b[B \r"` 返回 `['codex']`（取消预选的 Claude、下移、勾选 Codex、回车）。这条决定了选择器不需要真终端也能测（design D2）。
- 2026-07-29: 逐个提取 OpenSpec 28 个适配器的落盘路径，归纳出 `commands`/`prompts`/`workflows` 三种子目录、冒号 vs 连字符两种命名、`.md`/`.toml`/`.prompt`/`.prompt.md` 四种扩展名、三种正文格式；31 个工具中 `forgecode`/`kimi`/`vibe` 无适配器。
- 2026-07-29: 发现 `github-copilot` 的 `skills_dir` 是 `.github`，而该目录几乎每个仓库都有，仅凭目录存在会在首次 setup 时默认勾选 Copilot 并写出一堆文件；故引入 `detection_paths` 精确探测（design D4）。

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

## Artifact Notes
- proposal.md: approved（含对 `improve-init-display` 两条冻结决定的显式推翻及其理由）
- specs/: approved（5 份：新增 `init-welcome` 3 需求、新增 `tool-picker` 5 需求；`tool-scaffolding` 2 条 MODIFIED + 1 条 ADDED、`loopspec-cli` 1 条 MODIFIED、`cli-presentation` 3 条 ADDED）
- design.md: approved（D1–D10，含依赖选型论证、无头测试方案、预选分流、适配器参数化、叠加顺序说明）
- tasks.md: approved（7 组共 39 项，第 1 组要求先落地无头测试地基再往下做）
- security（gate）: 待执行，复核项含新增依赖来源（design D10 指定）
- approval（gate）: 待执行
- apply（gate）: 待执行，进度由 tasks.md 的 39 个 checkbox 追踪
