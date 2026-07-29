# Security Review: FAIL

## Blocking Issues
- 用户可控的路径字符串被直接送入 `rich` 渲染，而 design 与 tasks 全文未提及任何转义或禁用标记解析：`rich` 的 `Console.print()` 默认开启 console markup 解析（`markup=True`），会把方括号当格式指令。`--project-root` 与 `path` 均接受任意路径，而目录名在各主流文件系统上都允许包含 `[` 与 `]`。已实测确认两种失效模式：**（a）静默篡改**——`/tmp/[red]out/config.yaml` 被渲染成 `/tmp/out/config.yaml`、`/tmp/[oops]/config.yaml` 被渲染成 `/tmp//config.yaml`，即向用户展示一条并不存在的路径，且无任何报错；**（b）直接崩溃**——路径含 `[/]` 或 `[/bold]` 时抛 `rich.errors.MarkupError`（`closing tag ... has nothing to close`）使命令中断。其中 (a) 比崩溃更危险，因为用户会据此去找一个错误的路径。同理，路径中的裸 ANSI/控制字符会被回显进终端。修复方向：所有插值的用户可控字符串（路径、目录名、以及任何来自 `config.yaml` 的取值如 schema 名）必须经 `rich.markup.escape()` 处理或以 `markup=False` 渲染，并在 `presentation.py` 的接口层面强制这一点（而不是依赖各调用点自觉）；同时需要以含 `[red]`、含 `[/]`、含控制字符的目录名为输入的回归测试，分别覆盖上述 (a)(b) 两种失效模式。

## Scope Reviewed
`design.md`（D1–D9 全部决策与风险清单）与 `tasks.md`（第 1–6 组共 22 项任务）。重点核对：新增依赖来源、用户可控输入进入渲染/执行上下文的路径、凭据与敏感数据暴露、路径遍历、反序列化、以及测试对开发者真实环境的副作用。

## Non-Blocking Observations
（以下不阻断实现，供下一轮参考，不计入必须修复项）

第一，依赖面无新增风险：`rich` 早已是既有声明依赖，来自 Textualize，属广泛使用的可信来源，本变更只是首次真正启用它，未引入任何新第三方包。

第二，凭据与敏感数据方面未发现问题：摘要只呈现路径、工具显示名、数量与 schema 名，不读取也不回显 `config.yaml` 的其余内容，全流程不涉及任何凭据。人类模式改用聚合计数后，绝对路径（可能含用户名）在终端与截图中的暴露面实际是**下降**的，方向正确。

第三，路径遍历风险未被本变更引入或放大：`--project-root` 是上一变更就已存在的显式逃生口，"写到用户指定的位置"即其预期语义；本变更不改动该解析逻辑。

第四，`tasks.md` 第 6.3 项要求人工在 TTY 下真实执行 `init --tools claude,codex` 做肉眼验收——注意 Codex 的命令文件按设计写入用户全局 `$CODEX_HOME/prompts/`，因此该步骤会改动开发者的真实全局配置。建议验收时同样显式设置一个临时 `CODEX_HOME`，与自动化测试已采用的隔离做法保持一致。

## Recommended Fix Direction
在 `presentation.py` 的公开接口上把"用户可控字符串必须被转义"变成结构性保证，而不是调用方纪律：例如所有辅助函数内部统一对插值参数做 `escape()`，或全程以 `markup=False` 输出、需要样式时改用 `Style`/`Text` 对象而非内联标记。design 的 D2/D3 需补充这条约束，tasks 第 1 组需增加对应实现项与回归测试项，第 3 组的 `render_init_summary` 需明确其接收的路径参数已被转义。
