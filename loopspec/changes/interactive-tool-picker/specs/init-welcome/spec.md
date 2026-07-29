## ADDED Requirements

### Requirement: init 欢迎屏的内容契约
`loopspec init` 在进入交互式工具选择之前 SHALL 渲染一屏欢迎信息，按固定顺序包含以下分节（各节之间以空行分隔）：

1. 标题行（粗体）与一行副标题，说明 loopspec 是什么；
2. `This setup will configure:` 标题 + 列表项，逐条说明本次 setup 会写入什么（AI 工具的 Agent Skills、`/lpsx:*` slash 命令）；
3. `Quick start after setup:` 标题 + 命令表，每行一个 `/lpsx:<verb>` 命令与其一句话用途，且 SHALL 覆盖 `new`/`continue`/`apply` 三条主循环入口；
4. 一行提示，告知用户按回车进入工具选择。

命令名 SHALL 与实际生成的 slash 命令一致，包括为连字符命名工具做的命名转换规则（见 `lpsx-skills`）——欢迎屏 SHALL NOT 展示一个用户实际敲不出来的命令名。

#### Scenario: 交互式 init 渲染欢迎屏
- **WHEN** 在可交互终端执行 `loopspec init`（不带 `--tools`）
- **THEN** 在工具选择器出现之前，输出依次包含标题与副标题、`This setup will configure:` 清单、`Quick start after setup:` 命令表（含 `new`/`continue`/`apply`）、以及按回车继续的提示

#### Scenario: quick start 展示的命令名与实际生成的一致
- **WHEN** 查看欢迎屏的 quick start 命令表
- **THEN** 其中每个命令名都能在本次 setup 实际写入的命令文件中找到对应项

### Requirement: 静态色块 logo
欢迎屏 SHALL 包含一个由色块字符构成的静态 logo 标识。该 logo SHALL NOT 使用逐帧动画、光标回退或定时器——任何环境下都只渲染同一帧。当输出编码无法表示所用色块字符时，SHALL 按 `cli-presentation` 的 ASCII 降级规则降级，且 SHALL NOT 报错。

#### Scenario: logo 只渲染一帧
- **WHEN** 在可交互终端渲染欢迎屏
- **THEN** logo 被输出一次，输出中不含用于重绘的光标控制序列，命令不因此产生任何等待

#### Scenario: 编码不支持色块字符时降级
- **WHEN** 输出编码无法表示 logo 所用的色块字符
- **THEN** logo 以 ASCII 等价物呈现，命令正常完成而不抛出编码错误

### Requirement: 欢迎屏的渲染条件与降级
欢迎屏 SHALL 只在「本次执行将进入交互式工具选择」时渲染。以下任一情况 SHALL NOT 渲染欢迎屏（也 SHALL NOT 输出其任何分节）：

- `--json` 模式；
- `--tools` 已显式给定（包括 `all`/`none`），因为不需要用户再做选择；
- 当前不处于可交互终端（重定向、CI、管道）。

欢迎屏 SHALL 经由 `cli-presentation` 的呈现出口产出，因此其中的插值内容（如路径）沿用该能力的转义保证。

#### Scenario: --json 模式不渲染欢迎屏
- **WHEN** 执行 `loopspec init --json`
- **THEN** stdout 只含一份可整体解析的 JSON，不含标题、`This setup will configure:`、quick start 或 logo 的任何字符

#### Scenario: 显式传入 --tools 时不渲染欢迎屏
- **WHEN** 执行 `loopspec init --tools claude`（人类可读模式）
- **THEN** 输出中不含欢迎屏的任何分节，直接进入进度与摘要

#### Scenario: 非交互环境不渲染欢迎屏
- **WHEN** 在非交互环境下执行 `loopspec init`（不带 `--tools`、不带 `--json`）
- **THEN** 不渲染欢迎屏，行为退回该环境既有的默认路径（等价于 `--tools none`）
