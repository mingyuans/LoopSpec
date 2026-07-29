## Context

> **本轮（round 2）相对 round 1 的变更**：round 1 被 `security` 门禁判定为 FAIL，阻断问题是「用户可控的路径字符串直接进入 `rich` 渲染，全文未提转义」。本轮新增决策 **D10（呈现层强制转义）**，并相应加固 D2/D3、补充风险条目。旧版本存档于 `.attempts/round-001/design.md`。

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
- **呈现层对用户可控字符串的转义必须是结构性保证**，不依赖调用点自觉（见 D10）。
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
**代价**：`rich` 默认解析 console markup，这引入了一类新的输出完整性风险，必须由 D10 兜住。

### D2. 呈现语汇集中在单一模块，而不是各命令内联重复
**决策**：新增 `src/loopspec/presentation.py`，导出语义化辅助（`heading()`/`success()`/`warn()`/`error()`/`dim()`/`bullet()`/`link()`）与固定的字形表，所有人类可读输出只能经由它产出。这些辅助 SHALL 在内部完成转义（见 D10），因此调用方传入原始字符串即安全。
**备选方案**：照抄 OpenSpec 的做法——不建共享模块，在每个命令里内联 `chalk.xxx`。
**取舍理由**：OpenSpec 自己就吃了这个亏——调研确认它**没有**中心化的 output 模块，同一套字形/配色在各命令里重复，导致漂移（例如手写成功项用 `✓` U+2713、而 ora 的成功符号是 `✔` U+2714，两个字形并存；`failWithError` 带 `✖` 前缀而 `emitFailure` 不带）。loopspec 从一开始集中化，避免同类漂移；集中化同时是 D10 能够生效的前提——只有单一出口才能强制转义。

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

统一只用 `✔`（不再引入 `✓`）；分节一律用空行，不用横线/框线；不使用 emoji。字形与配色由呈现模块以 `Style`/`Text` 对象施加，而非内联 markup 字符串（见 D10）。
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

### D10. 用户可控字符串在呈现层被强制转义（round 2 新增，回应门禁阻断问题）
**决策**：呈现模块的公开接口**在内部**对所有插值内容做转义，调用方传入原始字符串即安全；样式一律通过 `rich` 的 `Style`/`Text` 对象施加，**不**通过内联 markup 字符串拼接。具体做法二选一（实现时择其一并在模块 docstring 写明）：其一，所有辅助函数内部对参数调用 `rich.markup.escape()`；其二，构造 `Text` 对象并以 `markup=False` 输出。同时对控制字符做剥离/可见化处理。

**实测依据**（`rich` 默认 `markup=True`，方括号被当作格式指令）：

| 输入 | 未转义时的实际渲染 |
|---|---|
| `/tmp/[red]out/config.yaml` | `/tmp/out/config.yaml` ← **静默篡改，无报错** |
| `/tmp/[oops]/config.yaml` | `/tmp//config.yaml` ← **静默篡改** |
| `/tmp/[/]out` | 抛 `rich.errors.MarkupError`，命令中断 |
| `/tmp/[/bold]out` | 抛 `rich.errors.MarkupError`，命令中断 |

**为什么这是阻断级**：受影响的插值内容全部是用户可控的——`--project-root` 与 `path` 参数接受任意路径，目录名在各主流文件系统上都允许含 `[`/`]`；`config.yaml` 的 schema 名也来自用户文件。其中"静默篡改"比崩溃更危险：摘要会向用户展示一条**并不存在**的路径，用户据此去找文件必然失败，且没有任何错误提示。

**为什么放在接口层而非调用点**：调用点纪律会随时间腐化，尤其后续要把其余 8 个命令逐步迁移到这套语汇上时；把保证放进单一出口（D2 的集中化）才能一次到位。

## Risks / Trade-offs

- **[Risk] 用户可控字符串（路径、schema 名）进入 `rich` 渲染时被当作 console markup，导致静默篡改或崩溃。**
  → Mitigation：D10 在呈现层接口内部强制转义 + 用 `Style`/`Text` 而非内联 markup；回归测试必须以含 `[red]`、含 `[/]`、含控制字符的目录名为输入，分别覆盖"静默篡改"与"抛异常"两种失效模式。
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

纯呈现层改动，无数据迁移。实现顺序：`presentation.py`（语汇 + D10 转义 + 降级）→ `scaffold.py` 增 created/refreshed 分组 → `init` 专用渲染器接入 → `tools_cli.py` 状态标签。每步都必须保持既有 CLI JSON 测试全绿作为契约护栏；D10 的转义测试必须与呈现模块同批落地，不得延后。

## Open Questions

- 无（「链接指向哪里」由 D8 关闭；「是否要静态 banner」已在 Non-Goals 中明确不做；round 1 的门禁阻断问题由 D10 关闭）。
