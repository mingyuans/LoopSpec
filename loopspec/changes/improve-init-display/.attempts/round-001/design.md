## Context

`loopspec` 目前所有命令的人类可读输出都走同一个 `_emit()` 分支：

```python
def _emit(data: dict[str, Any], as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(data, indent=2, default=str))
    else:
        for key, value in data.items():
            typer.echo(f"{key}: {value}")
```

也就是把喂给 JSON 的同一个 dict 逐条 `key: value` 转印，所以嵌套的 dict/list 会以 Python repr 直接泄漏给用户。`init` 受影响最重，因为它的载荷里有 `scaffoldedFiles`（按工具分组的完整路径列表）。

对照实现来自 OpenSpec（`/Users/xq.yan/otherprojects/OpenSpec`，v1.5.0），已调研清楚其呈现栈与具体格式：

- 呈现依赖只有 `chalk`（全部着色）+ `ora`（全部 spinner），**没有** boxen / cli-table3 / ink；框线和对齐全靠手写字符串。
- `InitCommand.displaySuccessMessage()`（`src/core/init.ts:652-752`）是唯一的摘要函数：纯 `console.log` 扁平行、空行分节、2 空格缩进、**无 emoji、无框线、无表格**；摘要正文里一个字形都没有（字形只出现在上方的 spinner 行）。
- 摘要**从不枚举文件**，只给一行聚合计数：`` `${skillCount} skills and ${commandCount} commands in ${toolDirs}/` ``。
- Created / Refreshed 的区分不靠对勾也不靠颜色，就是两行标签 `Created:` / `Refreshed:`，各跟一个逗号分隔的工具显示名列表；分组依据是写入**之前**捕获的 `tool.wasConfigured`。
- 无适配器工具走 `chalk.dim`：`` `Commands skipped for: ${ids.join(', ')} (no adapter)` ``。
- 收尾固定三段：bold `Getting started:` + 一行 2 空格缩进的首命令；`Learn more:` / `Feedback:` 两条 cyan URL（标签用手工空格对齐）；`Restart your IDE for slash commands to take effect.`
- 关键差异：**OpenSpec 的 `init` 没有 `--json` 模式**（`src/cli/index.ts:140-146` 只注册了 `--tools`/`--force`/`--profile`）。但它别的命令有，且模式统一是 `const spinner = options.json ? undefined : ora(...).start()` —— JSON 模式下 spinner 整体不启动。

## Goals / Non-Goals

**Goals:**
- 建立一套可复用的人类可读呈现语汇（字形、配色、章节结构、缩进），并集中在单一模块，避免像 OpenSpec 那样在各命令里重复。
- 把 `loopspec init` 的人类可读输出改写成对齐 OpenSpec 的分节摘要，用聚合计数替代路径明细。
- 逐阶段进度反馈（骨架创建、逐工具写入），且 `--json` 模式下完全静默。
- 脚手架层上报 Created / Refreshed 分组，判定依据沿用「写入前 skill 文件是否存在」。
- 交互式工具列表补 `(configured)` / `(refresh)` / `(detected)` 状态标签。
- `--json` 的结构与字段**零变化**，既有断言 JSON 的测试原样通过，作为契约护栏。

**Non-Goals:**
- 不实现 OpenSpec 的逐帧动画 ASCII logo（8 帧 / 120ms / 裸 ANSI 光标回退）；连静态 banner 也不做。
- 不把交互式选择升级为方向键 + 可搜索多选，沿用编号列表，只吸收其状态标签信息。
- 不改造 `status`/`instructions`/`rollback`/`history`/`archive` 等其余命令的人类可读输出（本次只建语汇，迁移留作后续变更）。
- 不移植 OpenSpec 的 legacy 清理提示与 telemetry 提示（loopspec 无历史包袱、无遥测）。

## Decisions

### D1. 用 `rich` 作为呈现层，确认为强制依赖
**决策**：人类可读路径全部经由 `rich`（着色 + spinner/status），不引入任何新依赖。
**理由**：`rich>=13` 早在 `gated-artifact-workflow` 就写进了 `pyproject.toml` 却从未 import，等于白背依赖；`rich` 一个库即可同时覆盖 OpenSpec 那边 chalk + ora 两个库的职责，且原生处理 `NO_COLOR`、非 TTY、Windows legacy 终端。
**副产品**：这条决策同时**关闭了 `gated-artifact-workflow` design 里遗留的开放问题**「rich 是否作为强制依赖，还是保持可选」——结论：强制依赖，但只允许出现在人类可读路径，`--json` 路径不得依赖它。

### D2. 呈现语汇集中在单一模块，而不是各命令内联重复
**决策**：新增 `src/loopspec/presentation.py`，导出语义化辅助（`heading()`/`success()`/`warn()`/`error()`/`dim()`/`bullet()`/`link()`）与固定的字形表，所有人类可读输出只能经由它产出。
**备选方案**：照抄 OpenSpec 的做法——不建共享模块，在每个命令里内联 `chalk.xxx`。
**取舍理由**：OpenSpec 自己就吃了这个亏——调研确认它**没有**中心化的 output 模块，同一套字形/配色在各命令里重复，导致漂移（例如手写成功项用 `✓` U+2713、而 ora 的成功符号是 `✔` U+2714，两个字形并存；`failWithError` 带 `✖` 前缀而 `emitFailure` 不带）。loopspec 从一开始集中化，避免同类漂移。

### D3. 字形与配色语汇表（照搬 OpenSpec 的观感，去掉其内部不一致）
**决策**：

| 用途 | 字形 | 配色 |
|---|---|---|
| 成功 | `✔` (U+2714) | 绿 |
| 失败 | `✖` (U+2716) | 红 |
| 警告 | `⚠` (U+26A0) | 黄 |
| 列表项 | `•` (U+2022)，2 空格缩进 | 无 |
| 骨架就绪标记 | `▌` (U+258C) | 亮白 |
| 章节标题 | 无字形 | bold |
| 次要/跳过信息 | 无字形 | dim |
| URL | 无字形 | cyan |

统一只用 `✔`（不再引入 `✓`）；分节一律用空行，不用横线/框线；不使用 emoji。
**理由**：与 OpenSpec 的视觉词汇一致，同时消除它 `✓`/`✔` 并存那类内部不一致。

### D4. 成功摘要的行序固定，且用聚合计数替代路径明细
**决策**：`init` 人类可读输出按固定顺序渲染（空行分节）：
1. 进度行（骨架 `▌`、逐工具 `✔ Setup complete for <Tool>`）
2. bold 标题 `LoopSpec Setup Complete`
3. `Created: <显示名列表>` / `Refreshed: <显示名列表>`（各自非空才出现）
4. 聚合计数 `N skills and M commands in <目录列表>`
5. `Commands skipped for: <ids> (no adapter)`（dim，仅当存在）
6. `Config: <相对路径> (schema: <name>)` 或 `... (exists)`
7. bold `Getting started:` + 2 空格缩进的 `loopspec new <change-name>` 建议
8. `Learn more:` / `Feedback:` 两条 cyan URL
9. `Restart your IDE for slash commands to take effect.`（仅当确有工具被配置）

**代价**：人类模式因此成为 JSON 载荷的**有损聚合**（路径明细只在 JSON 里），这与 `loopspec-cli` 既有要求「二者返回的信息内容 SHALL 保持一致」冲突，故本变更要显式放宽该要求为「呈现同一组事实，人类模式允许聚合与取舍」。这是有意的：一次 `--tools all` 会产生 40 个文件路径，逐条列出对人毫无价值。

### D5. Created / Refreshed 需要在写入前探测状态
**决策**：`scaffold_tools()` 在写任何文件**之前**，先检查该工具的 4 个 skill 文件是否已存在，把结果记入 `ScaffoldResult`（新增 created / refreshed 两个工具 id 列表）。
**理由**：写入是无条件覆盖的（既有决策），一旦写完就无法区分本次是新建还是刷新，所以状态必须前置捕获——OpenSpec 同样是在 `generateSkillsAndCommands` 之前从 `getToolStates()` 拿 `wasConfigured`。判定依据正好是既有 `tool-scaffolding` 需求已经规定的「配置状态由 skill 文件是否存在判定」，因此不需要引入任何清单文件，与「不持久化工具选择」规则一致。

### D6. `--json` 模式下抑制一切装饰，且 JSON 只走 stdout
**决策**：`as_json=True` 时不创建 spinner/status、不输出任何进度行、不着色；stdout 只有那一份 JSON 文档。
**备选方案**：进度一律写 stderr，JSON 写 stdout，两者共存。
**取舍理由**：与 OpenSpec 各命令一致（`options.json ? undefined : ora(...)`），实现更简单，且避免 Agent 在合并 stdout/stderr 的环境下拿到污染输出。

### D7. `_emit()` 保留为通用兜底，`init` 走专用渲染器
**决策**：不动 `_emit()` 的既有行为（其余命令继续用它），另加 `render_init_summary(result)` 专用渲染函数；`init` 在人类模式调用它，JSON 模式仍走 `_emit()`。
**理由**：`_emit()` 被全部 9 个命令共用，改它的通用分支会一次性影响所有命令的人类输出，超出本次范围且难以回归；专用渲染器把风险限制在 `init` 一条路径上，同时为后续逐命令迁移留出模式。

### D8. `Learn more` / `Feedback` 链接取自 git origin
**决策**：使用 `https://github.com/mingyuans/LoopSpec` 与 `.../issues`（由仓库 `origin` 远端推导），标签用手工空格对齐（`Learn more: ` / `Feedback:   `）使 URL 起始列对齐。
**理由**：这是本仓库实际的远端地址，无需新增配置项；`state.md` 里原先「链接指向哪里」的开放问题据此关闭。

### D9. 字形的 ASCII 降级
**决策**：当输出编码无法表示上述 Unicode 字形时（`sys.stdout.encoding` 不支持），降级为 ASCII：`✔→ok`、`✖→x`、`⚠→!`、`•→-`、`▌→|`。
**理由**：OpenSpec 侧有等价机制（`log-symbols` 的 fallback 表、ASCII logo 的 `supportsUnicode` 判定），且 CI/重定向场景常见。

## Risks / Trade-offs

- **[Risk] 人类输出改成有损聚合后，用户想看具体写了哪些文件就没法看了。**
  → Mitigation：`--json` 保留完整 `scaffoldedFiles` 明细；摘要里的聚合计数带上目录名（`in .claude, .codex`），用户可自行 `ls`。
- **[Risk] `rich` 输出 ANSI 转义序列会污染 CliRunner 捕获的文本，导致既有/新增测试断言失败。**
  → Mitigation：呈现模块的 `Console` 必须可注入且在测试中强制 `no_color=True`/`force_terminal=False`；断言只针对纯文本。JSON 路径完全不经 `rich`，所以既有 20+ 条 JSON 断言天然不受影响。
- **[Risk] 改 `ScaffoldResult` 的形状会波及 `init` 的 JSON 载荷，破坏已声明"零变化"的契约。**
  → Mitigation：新增字段而非改名/删字段（`scaffoldedFiles` 等既有键保持原样）；把既有 CLI JSON 测试当作护栏，任何键名变动都会立刻失败。
- **[Risk] 进度行在 JSON 模式下漏出会破坏机器可解析性。**
  → Mitigation：单测显式断言 `--json` 输出可被 `json.loads()` 整体解析（现有 `run()` 辅助已经在做这件事，等于自带回归）。
- **[Risk] 集中化呈现模块可能被后续命令误用于 JSON 路径，重新引入污染。**
  → Mitigation：模块 docstring 明确约束「仅人类可读路径可用」；渲染函数不接受 `as_json` 参数，从签名上让 JSON 路径无法顺手调用。

## Migration Plan

纯呈现层改动，无数据迁移。实现顺序：`presentation.py`（语汇 + 降级）→ `scaffold.py` 增 created/refreshed 分组 → `init` 专用渲染器接入 → `tools_cli.py` 状态标签。每步都必须保持既有 CLI JSON 测试全绿作为契约护栏。

## Open Questions

- 无（原「链接指向哪里」已由 D8 关闭，「是否要静态 banner」已在 Non-Goals 中明确不做）。
