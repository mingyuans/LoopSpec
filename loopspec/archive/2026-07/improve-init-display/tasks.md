> **本轮（round 2）相对 round 1 的变更**：新增第 1 组的 1.2/1.7 两项（呈现层强制转义的实现与回归测试）、第 3 组的 3.8 项（渲染器参数已转义的显式约束），并把第 6.3 项的人工验收改为在隔离的 `CODEX_HOME` 下进行。旧版本存档于 `.attempts/round-001/tasks.md`。
>
> **计数更正（approval round 1 的前置条件）**：本文件共 **29 项**任务（1 组 8 项、2 组 3 项、3 组 8 项、4 组 3 项、5 组 4 项、6 组 3 项）。此前 `state.md` 与 `security/pass.md` 记作「25 项」，是 round 1 的旧计数未随 round 2 新增的 1.2/1.7/3.8 更新。`security/pass.md` 作为已出具的门禁判定记录不做改写，其计数以本条为准。

## 1. 呈现层基础（cli-presentation）

- [x] 1.1 新增 `src/loopspec/presentation.py`：定义字形表（`✔`/`✖`/`⚠`/`•`/`▌`）与其 ASCII 降级映射（`ok`/`x`/`!`/`-`/`|`），按输出编码能否表示 Unicode 自动选择
- [x] 1.2 **实现 D10 的强制转义**：所有公开辅助函数在**内部**对插值内容做 `rich.markup.escape()`（或改为构造 `Text` 并以 `markup=False` 输出），样式一律通过 `Style`/`Text` 对象施加而非内联 markup 字符串；同时剥离/可见化控制字符。在模块 docstring 写明所选方案与该保证
- [x] 1.3 实现语义化辅助：`heading()`（bold 无字形）、`success()`、`failure()`、`warning()`、`dim()`、`bullet()`（2 空格缩进）、`link()`（cyan）
- [x] 1.4 `Console` 必须可注入，且在非 TTY / `NO_COLOR` 下自动输出无色纯文本（依赖 `rich` 原生行为，显式验证而非假定）
- [x] 1.5 实现多阶段进度封装：TTY 下用 `rich` 的 status/spinner，非 TTY 下降级为普通完成行（无光标控制字符）
- [x] 1.6 在模块 docstring 中明确约束「仅人类可读路径可用」，且渲染函数签名不接受 `as_json`，从签名上阻止 JSON 路径误用
- [x] 1.7 **转义回归测试**（对应门禁 round 1 的阻断问题，必须与 1.2 同批落地）：以 `/tmp/[red]out`、`/tmp/[oops]` 为输入断言路径**原样**出现在输出中（覆盖"静默篡改"失效模式）；以 `/tmp/[/]out`、`/tmp/[/bold]out` 为输入断言**不抛** `MarkupError`（覆盖"崩溃"失效模式）；再以含控制字符的路径断言输出无裸控制字符
- [x] 1.8 编写 `tests/test_presentation.py` 的其余用例：字形/配色映射、ASCII 降级、`NO_COLOR` 与非 TTY 下无 ANSI 序列、进度在非 TTY 下无控制字符、辅助函数不含 emoji/框线

## 2. 脚手架上报 Created / Refreshed（tool-scaffolding）

- [x] 2.1 在 `scaffold_tools()` 写入任何文件**之前**探测每个工具的 skill 文件是否已存在，据此分组
- [x] 2.2 `ScaffoldResult` 新增 `created` 与 `refreshed` 两个工具 id 列表（**新增字段，不改动/不删除既有字段**，以保证 `init` 的 JSON 契约不破）
- [x] 2.3 扩展 `tests/test_scaffold.py`：首次生成归 created、再次生成归 refreshed、混合场景两组各一、以及断言未新增任何状态记录文件

## 3. init 专用摘要渲染（loopspec-cli）

- [x] 3.1 在 `presentation.py`（或相邻模块）实现 `render_init_summary(...)`，按 design D4 的固定行序渲染：进度行 → 粗体标题 → `Created:`/`Refreshed:` → 聚合计数 → 无适配器提示（dim）→ `Config:` 状态 → `Getting started:` → `Learn more:`/`Feedback:` → 重启提示
- [x] 3.2 聚合计数行统计写入的 skill 与命令数量及目标目录（如 `4 skills and 4 commands in .claude, .codex`），**不逐条罗列路径**
- [x] 3.3 `Config:` 行区分新建（带 schema 名）与已存在（标注 exists）两种状态
- [x] 3.4 链接使用 `https://github.com/mingyuans/LoopSpec` 与 `.../issues`，标签用手工空格对齐使 URL 起始列一致
- [x] 3.5 `cli.py` 的 `init` 在人类模式调用该渲染器；**保持 `_emit()` 既有行为不变**（其余命令继续用它），JSON 模式仍走 `_emit()`
- [x] 3.6 逐阶段进度接入：workflow home 骨架就绪（`▌` 标记行）、逐工具完成行（`✔ Setup complete for <显示名>`）；`--json` 下全部不输出
- [x] 3.7 为工具 id 补人类可读显示名（`claude` → `Claude Code` 等），供摘要与进度行使用
- [x] 3.8 `render_init_summary` 接收的路径与 schema 名等用户可控参数，其转义由第 1 组的辅助函数在内部完成；本项需在实现中确认渲染器**没有**绕过那些辅助函数直接调用 `console.print(f"...")` 拼接用户可控内容

## 4. 交互式列表状态标签

- [x] 4.1 `prompt_tools_interactively()` 的编号列表为每项补状态标签：`(configured)`（已配置未选中）、`(refresh)`（已配置且选中）、`(detected)`（探测到目录但未配置）
- [x] 4.2 状态探测复用第 2 组的「skill 文件是否存在」逻辑，不新增判定路径
- [x] 4.3 扩展 `tests/test_tools_arg.py`：已配置工具带 `(configured)`/`(refresh)` 标签、未配置工具无标签，且标签不影响编号解析结果

## 5. 契约护栏与回归

- [x] 5.1 新增测试断言 `init --json` 的 stdout 可被 `json.loads()` 整体解析，且不含 ANSI 序列或进度行
- [x] 5.2 新增测试断言 `init` 人类可读输出**不含** JSON 字段名（如 `scaffoldedFiles`）与 Python 容器 repr（如 `{'claude':`）
- [x] 5.3 确认既有 `tests/test_cli.py` 中全部断言 JSON 结构的用例**未经修改**即通过（JSON 契约零变化的证据）
- [x] 5.4 新增测试断言人类模式被聚合掉的路径明细仍可从 `--json` 完整取回

## 6. 收尾

- [x] 6.1 更新 `README.md`：贴一段 `loopspec init` 的实际人类可读输出示例
- [x] 6.2 运行 `make lint` 与 `make test`，确保全绿（既有测试基线为 221 个，含 `approval`/`apply` 两个新节点带来的用例）
- [x] 6.3 人工肉眼验收（**须在隔离环境下进行**：显式设置临时 `CODEX_HOME`，避免污染开发者真实的 `~/.codex/prompts/`）：在 TTY 下真实跑 `init --tools claude,codex` 两遍确认 Created→Refreshed 切换；再各跑一次 `NO_COLOR=1` 与重定向到文件，确认降级正常；最后用一个含 `[red]` 的 `--project-root` 目录名跑一次，肉眼确认路径原样显示
