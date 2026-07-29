# Security Review: PASS

## Scope Reviewed

- `loopspec/changes/interactive-tool-picker/design.md`（D1–D10）
- `loopspec/changes/interactive-tool-picker/tasks.md`（7 组共 39 项）
- 变更将触及的既有代码，用于判断 tasks 的改动落在什么现状之上：
  - `src/loopspec/tool_registry.py`（`AI_TOOLS`、`COMMAND_ADAPTERS`、`CodexCommandAdapter._codex_home()`）
  - `src/loopspec/tools_cli.py`（`is_interactive()`、`tool_status_label()`、`prompt_tools_interactively()`）
  - `src/loopspec/scaffold.py`（`tool_is_configured()`、`scaffold_tools()` 的写盘路径）
- 外部核验：PyPI 官方注册表（`https://pypi.org/pypi/<pkg>/json`）上 `questionary` / `prompt_toolkit` / `wcwidth` 三项元数据。

## Checks Performed

### 1. 新增第三方依赖的来源与维护状态（design D10 指定的复核项，本次重点）

三个包全部在 PyPI 官方注册表核验，均非臆造名、无 typosquatting 迹象，且都是各自生态里的长期主线包：

| 包 | 注册表版本 | 许可 | 上游仓库 | 维护者 | 角色 |
| --- | --- | --- | --- | --- | --- |
| `questionary` | 2.1.1 | MIT | `github.com/tmbo/questionary` | Tom Bocklisch | 唯一新增的**直接**依赖 |
| `prompt_toolkit` | 3.0.53 | BSD | `github.com/prompt-toolkit/python-prompt-toolkit` | Jonathan Slenders | 传递依赖；IPython/ptpython 的底层交互库 |
| `wcwidth` | 0.8.2 | MIT | `github.com/jquast/wcwidth` | jquast | 传递依赖；宽字符宽度计算，生态内广泛使用 |

判定要点：
- design 声明的 `questionary` 版本（2.1.1）与注册表当前版本一致，`checkbox()` 的 `use_search_filter` / `initial_choice` 等签名结论建立在本机实测之上，不是文档推断。
- 依赖树增量与 design 声明一致（+3 包，无隐藏的重量级传递依赖）；未引入 `InquirerPy` 或其它同类竞品叠加，直接依赖面只扩大 1 项。
- 许可均为宽松许可（MIT/BSD），无 copyleft 传染风险。
- task 1.1 要求 `uv sync` 后确认锁文件带入这三个包 —— 锁文件即为后续供应链固定点，符合「不从非官方源安装」的要求。

结论：依赖引入可接受，D10 的复核项已完成且通过。

### 2. 注入风险（shell / SQL / 模板 / LDAP / XPath）

- 全部 39 项任务中**不存在**任何 `subprocess`、shell 调用、数据库访问、网络请求或模板引擎渲染；变更面是「本地文件生成 + 终端交互」。
- 命令文件正文由 `format_file()` 用固定字符串拼装（三种 `body_format`：`md_frontmatter` / `toml` / `heading`），被插值的 `CommandContent`（name/description/body）来自仓库内的 skill 模板常量，不来自外部输入。
- 无解释型上下文接收不可信输入 → 无注入面。

### 3. 终端转义序列注入（本变更真正新增的呈现面）

这是本轮唯一新增的、值得单独判断的攻击面：`questionary`/`prompt_toolkit` 绕过了 `improve-init-display` D10 建立的 `rich.Text` 转义出口，直接向终端写控制序列。

- design D8 的处置正确：**从数据流上断掉**（候选项文本只允许来自注册表常量的显示名 + 固定状态标注字符串，禁止拼接路径、用户输入或文件内容），而不是为交互组件另造一套转义。这比「再加一层转义」更不易腐化。
- design D8 明确否定了「把 D10 的转义保证顺延到 questionary」的错误推断，并把「将来若要在选择器里展示路径必须先净化」写进了 spec，而非仅停留在设计讨论。
- task 4.8 给出了可执行的护栏：遍历全部 31 个显示名断言不含控制字符。
- task 4.3 的提示行 `Detected tool directories: <显示名列表>` 插值内容同样是注册表常量，落在 D8 的约束内。
- task 5.4 断言 logo 在非 TTY 下不输出 ANSI 序列，task 6.1 断言 `--json` 输出不含 ANSI 序列 —— 控制序列不会泄漏到管道/日志/JSON 消费方。

### 4. 路径处理与遍历防护

- 新增的 `detection_paths`（task 2.1/2.2）只做**存在性只读检查**，不读取内容、不解析；其值是 spec 表格给定的常量。
- 参数化适配器（task 3.1/3.3）的路径分量 `tool_dir` / `subdir` / `extension` / `nested` 全部是注册表常量；`command_id` 来自内部命令清单。既有 `scaffold_tools()` 的写盘方式为 `mkdir(parents=True, exist_ok=True)` + `write_text()`，路径无用户可控分量 → 无遍历面。
- `--tools` 解析（`resolve_tools_arg()`）对工具 id 采用**注册表白名单校验**，未知 id 直接报错，不会把任意字符串带进路径拼接；本变更明确不改这套解析规则（design Non-Goals、task 6.4）。
- `CodexCommandAdapter._codex_home()` 读 `CODEX_HOME` 环境变量且不校验，但该变量属操作者自身的控制面（非不可信输入），且为既有行为、本变更不改动（task 3.4 保留独立实现）。见 Notes。

### 5. 认证 / 授权

本变更不涉及任何认证或授权判定（无服务端、无凭据、无权限模型）。唯一近似「授权」语义的是「哪些工具目录可以被写入」，由 D3 的单一交互判定 + 白名单注册表共同界定，无绕过路径。

### 6. 凭据与敏感数据

- 无硬编码凭据、无 token/密钥读写、无 `.env` 类文件访问。
- 无日志/缓存写入 PII；生成物内容为 skill/command 模板，全部为仓库内常量。
- 交互组件不回显任何机密（选择器只显示工具显示名与状态标注）。

### 7. 反序列化 / 解析不可信输入

- YAML frontmatter 与 TOML 在本变更中只被**生成**，不被解析（task 3.2）；不存在 `yaml.load` 类不安全反序列化。
- 探测逻辑不读取任何被探测文件的内容。

### 8. 数据暴露与副作用范围

- `--tools all` 的写入范围由 5 个工具扩到 31 个（task 6.5 已识别），生成的文件名统一带 `lpsx-` / `lpsx/` 命名空间前缀，与其它工具的既有文件不冲突，覆盖风险限定在 loopspec 自己的产物上。
- 最实质的副作用风险是「首次 setup 误预选导致回车即产生一堆文件」，design D4/D5 已针对性缓解：`github-copilot` 用 `detection_paths` 精确到具体文件（避免 `.github/` 这一近乎万仓皆有的目录触发误探测），重复运行 `init` 改为只预选**已配置**项，使默认动作是「刷新」而非「悄悄扩大范围」。task 2.6 有对应断言（只有 `.github/` 时 Copilot **未**探测到）。
- task 6.5 / 7.4 要求测试与人工验收均隔离 `CODEX_HOME`，避免写入开发者真实 `~/.codex/prompts/`。
- D9 规定用户中断按「不配置任何工具」收尾且**不写脚手架**，不会留下半写状态的产物。

## Notes

以下均为**非阻塞**观察，不影响本门禁的 PASS 判定：

- **`CODEX_HOME` 未做校验属既有行为。** `_codex_home()` 直接 `Path(os.environ["CODEX_HOME"])`，未规范化也未限制。因该变量由操作者自身设置（威胁模型下不属不可信输入），且本变更不触碰该实现，不作为本轮阻塞项。若将来 loopspec 需要在 CI 或多用户环境里由外部配置驱动这个变量，届时应补一条「解析为绝对路径并拒绝写入非预期位置」的校验。
- **建议把「适配器路径分量必须是编译期常量」写成一条断言。** 参数化适配器（task 3.1）把路径构造从 28 份手写实现收敛成一张数据表，安全性依赖于「表里的值都是常量」这一隐含前提。task 3.6 的表驱动完整路径断言事实上已经守住了这一点（任何越界或含 `..` 的分量都会让完整字符串断言失败），故无需额外任务；此处仅作为后续维护者的提示记录。
- **交互异常路径下的终端状态恢复。** D9 覆盖了 `KeyboardInterrupt` / `ask() -> None`；`prompt_toolkit` 自身以上下文管理器恢复终端 raw mode，其它异常类型下终端状态一般可自愈。这属于可用性而非安全问题，但若 task 4.5 实现时顺手确认非中断类异常也能正常退出交互态，会更稳。
- **依赖版本约束为下界（`questionary>=2.1`）。** 供应链的实际固定点是 `uv.lock`（task 1.1 会确认），这与项目既有依赖（`rich>=13` 等）的写法一致，无需在本轮改变策略。
