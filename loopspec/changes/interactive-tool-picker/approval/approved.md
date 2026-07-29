# Human Approval: APPROVED

## Summary Presented to the Human

向人类呈现的审阅摘要（第 1 轮）覆盖以下内容：

### 1. 要解决的问题
`improve-init-display` 已把 `init` 的**输出**对齐 OpenSpec（分节摘要、Created/Refreshed、聚合计数、进度行），但**交互本身**未动：工具选择仍是「打印编号列表 + 读一行逗号分隔输入」，列表显示裸 id（`claude` 而非 `Claude Code`），且 5 个工具的注册表撑不起搜索与分页。

明确告知人类：**本变更显式推翻 `improve-init-display` 的两条冻结决定**——
- 「不做动画 logo，连静态 banner 也不做」→ 本轮只做**静态**一帧，动画仍是 Non-Goal，故「动画不划算」的判断未被推翻；
- 「不为次要交互引入新依赖」→ 交互不再是次要项而是本变更的目标本身，前提失效。

推翻依据是人类在本轮开工前的三项定案：交互库用 `questionary`、注册表扩到 31 个、欢迎屏为静态文案 + 静态色块 logo。

### 2. 新增与修改的能力（5 份 delta spec）
- **新增 `init-welcome`**（3 需求）：欢迎屏内容契约（标题/副标题 → `This setup will configure:` → `Quick start after setup:` 三条 `/lpsx:*` → `Press Enter to select tools...`）、静态色块 logo、渲染条件与降级。
- **新增 `tool-picker`**（5 需求）：方向键/空格/搜索/回车键位、显示名 + 状态标注、首次 setup 预选、分页与可用计数、非 TTY 降级与中断处理。
- **修改 `tool-scaffolding`**（2 MODIFIED + 1 ADDED）：注册表 5 → 31 项（含显示名表格）、28 个命令适配器的完整落盘规则表、新增「多路径探测」。
- **修改 `loopspec-cli`**（1 MODIFIED）：`init` 需求补充欢迎屏与选择器的交互要求。
- **修改 `cli-presentation`**（3 ADDED）：静态 logo 进呈现语汇表、交互组件的独立转义约束、第三方交互库只服务交互路径。

### 3. 关键技术决策与各自的取舍（design D1–D10）
- **D1** 引入 `questionary>=2.1`，换掉手写 `termios`/`msvcrt` raw-mode 方案。代价是依赖树 +3 包；换来的是不必自行处理方向键转义序列、搜索过滤、分页、宽字符对齐与 Windows 分支。
- **D2** 输入/输出可注入：`create_pipe_input()` + `DummyOutput()` 已实机验证可驱动 `checkbox()`，整套选择器无需真终端即可测试。代价是按键序列可读性差，故要求每处带注释并提供人类可读动作 → 字节序列的辅助函数。
- **D3** 单一判定：「未显式传 `--tools`」+「`is_interactive()`」+「非 `--json`」三者同时成立才渲染欢迎屏并启动选择器，判定计算一次并同时决定两者，从结构上排除「渲染了欢迎屏却没有选择器」这一会骗用户按回车的中间态。
- **D4/D5** 探测与预选分流：`github-copilot` 的 `skills_dir` 是 `.github`（几乎每个仓库都有），故引入 `detection_paths` 精确到具体文件；重复运行 `init` 改为只预选**已配置**项，使默认动作是「刷新」而非悄悄扩大配置范围。
- **D6/D7** 适配器参数化：28 份手写实现收敛为一张数据表 + 4 类特例；`cline` 的命令目录 `.clinerules` 与 `skills_dir` `.cline` 解耦、不得相互推导（推导错误会导致**静默失效**——文件写到 Cline 不读的位置且无任何报错）。
- **D8** 交互文本只喂注册表常量，明确否定「把上一轮 `rich.Text` 的转义保证顺延到 `questionary`」。
- **D9** Ctrl+C 按「本次不配置任何工具」收尾，不抛栈、不留半写现场。

### 4. 任务清单规模与顺序
7 组共 39 项，第 1 组（3 项）明确要求**先落地无头测试地基再往下做**，避免 31 个工具全部写完后才发现测试方式不可行。其后依次为：注册表扩容（6 项）→ 参数化适配器（8 项）→ 选择器（8 项）→ 欢迎屏与 init 接入（4 项）→ 契约护栏与回归（5 项）→ 收尾（5 项，含抽样人工验收 5 个特例工具）。

契约护栏：`tests/test_cli.py` 的 JSON 断言与 `tests/test_tools_arg.py` 的 `--tools` 解析断言须**未经修改即通过**（task 6.4），作为契约零变化的证据。

### 5. 安全评审结论与接受的残余风险
`security` 门禁 PASS（`security/pass.md`）。design D10 要求的依赖核验已在 PyPI 官方注册表逐项完成：`questionary` 2.1.1（MIT / tmbo）、`prompt_toolkit` 3.0.53（BSD / prompt-toolkit 组织，IPython 底层库）、`wcwidth` 0.8.2（MIT / jquast），均为生态主线包、无 typosquatting 迹象、许可宽松。全程无 shell/subprocess/网络/数据库/不安全反序列化，路径分量全为注册表常量。

接受的 4 条非阻塞残余风险：`CODEX_HOME` 未做校验（既有行为、本轮不改）、适配器路径常量约束靠 task 3.6 的完整路径断言事实覆盖、非中断类异常下的终端状态恢复、依赖版本下界靠 `uv.lock` 固定。

### 6. 明确交给人类判断的两点
- **delta 叠加顺序只能人工保证**：`improve-init-display` 已完成但未归档，其 3 份 delta 尚未应用到 `openspec/specs/`；本轮 `loopspec-cli` 的 MODIFIED 全文以那一版为基线，两者必须按 `improve-init-display` → `interactive-tool-picker` 的顺序应用，反序会丢掉摘要相关段落。
- **`--tools all` 的副作用范围扩大**：从写 5 个工具变为写 31 个，其中 `codex` 写入用户全局 `~/.codex/prompts/`；tasks 6.5/7.4 已要求测试与人工验收隔离 `CODEX_HOME`。

## Human's Words

> 按此方案实施

（无限定条件、无例外、未要求任何调整。）

## Non-Blocking Suggestions

无。人类未提出任何非阻塞意见，也未对摘要中「交给人类判断的两点」附加额外要求——即视为接受 `security/pass.md` 记录的 4 条非阻塞残余风险，以及 delta 叠加顺序由人工保证、`--tools all` 写入范围扩大到 31 个工具（含用户全局 `~/.codex/prompts/`）这两项现状。

## state.md Write-Back

- Decision Log: round 1 - approved
- Frozen Decisions: 追加 5 条签核点——(1) 39 项任务的实施顺序，第 1 组无头测试地基必须先落地；(2) D3 的单一判定不得拆成两个独立判断；(3) `tests/test_cli.py` 与 `tests/test_tools_arg.py` 的既有断言必须未经修改即通过；(4) 注册表 31 项与 28 个适配器的落盘路径以 spec 表格为准，逐项完整字符串断言而非抽查；(5) 接受 `security/pass.md` 的 4 条非阻塞残余风险。并注明后续节点不得静默改动这些点，改动需要另一轮 approval。
- Artifact Notes: approval/approved.md - approved
