## 1. 呈现层基础（cli-presentation）

- [ ] 1.1 新增 `src/loopspec/presentation.py`：定义字形表（`✔`/`✖`/`⚠`/`•`/`▌`）与其 ASCII 降级映射（`ok`/`x`/`!`/`-`/`|`），按输出编码能否表示 Unicode 自动选择
- [ ] 1.2 实现语义化辅助：`heading()`（bold 无字形）、`success()`、`failure()`、`warning()`、`dim()`、`bullet()`（2 空格缩进）、`link()`（cyan）；全部返回渲染后的字符串或直接写入注入的 `Console`
- [ ] 1.3 `Console` 必须可注入，且在非 TTY / `NO_COLOR` 下自动输出无色纯文本（依赖 `rich` 原生行为，显式验证而非假定）
- [ ] 1.4 实现多阶段进度封装：TTY 下用 `rich` 的 status/spinner，非 TTY 下降级为普通完成行（无光标控制字符）
- [ ] 1.5 在模块 docstring 中明确约束「仅人类可读路径可用」，且渲染函数签名不接受 `as_json`，从签名上阻止 JSON 路径误用
- [ ] 1.6 编写 `tests/test_presentation.py`：字形/配色映射、ASCII 降级、`NO_COLOR` 与非 TTY 下无 ANSI 序列、进度在非 TTY 下无控制字符、辅助函数不含 emoji/框线

## 2. 脚手架上报 Created / Refreshed（tool-scaffolding）

- [ ] 2.1 在 `scaffold_tools()` 写入任何文件**之前**探测每个工具的 skill 文件是否已存在，据此分组
- [ ] 2.2 `ScaffoldResult` 新增 `created` 与 `refreshed` 两个工具 id 列表（**新增字段，不改动/不删除既有字段**，以保证 `init` 的 JSON 契约不破）
- [ ] 2.3 扩展 `tests/test_scaffold.py`：首次生成归 created、再次生成归 refreshed、混合场景两组各一、以及断言未新增任何状态记录文件

## 3. init 专用摘要渲染（loopspec-cli）

- [ ] 3.1 在 `presentation.py`（或相邻模块）实现 `render_init_summary(...)`，按 design D4 的固定行序渲染：进度行 → 粗体标题 → `Created:`/`Refreshed:` → 聚合计数 → 无适配器提示（dim）→ `Config:` 状态 → `Getting started:` → `Learn more:`/`Feedback:` → 重启提示
- [ ] 3.2 聚合计数行统计写入的 skill 与命令数量及目标目录（如 `4 skills and 4 commands in .claude, .codex`），**不逐条罗列路径**
- [ ] 3.3 `Config:` 行区分新建（带 schema 名）与已存在（标注 exists）两种状态
- [ ] 3.4 链接使用 `https://github.com/mingyuans/LoopSpec` 与 `.../issues`，标签用手工空格对齐使 URL 起始列一致
- [ ] 3.5 `cli.py` 的 `init` 在人类模式调用该渲染器；**保持 `_emit()` 既有行为不变**（其余命令继续用它），JSON 模式仍走 `_emit()`
- [ ] 3.6 逐阶段进度接入：workflow home 骨架就绪（`▌` 标记行）、逐工具完成行（`✔ Setup complete for <显示名>`）；`--json` 下全部不输出
- [ ] 3.7 为工具 id 补人类可读显示名（`claude` → `Claude Code` 等），供摘要与进度行使用

## 4. 交互式列表状态标签

- [ ] 4.1 `prompt_tools_interactively()` 的编号列表为每项补状态标签：`(configured)`（已配置未选中）、`(refresh)`（已配置且选中）、`(detected)`（探测到目录但未配置）
- [ ] 4.2 状态探测复用第 2 组的「skill 文件是否存在」逻辑，不新增判定路径
- [ ] 4.3 扩展 `tests/test_tools_arg.py`：已配置工具带 `(configured)`/`(refresh)` 标签、未配置工具无标签，且标签不影响编号解析结果

## 5. 契约护栏与回归

- [ ] 5.1 新增测试断言 `init --json` 的 stdout 可被 `json.loads()` 整体解析，且不含 ANSI 序列或进度行
- [ ] 5.2 新增测试断言 `init` 人类可读输出**不含** JSON 字段名（如 `scaffoldedFiles`）与 Python 容器 repr（如 `{'claude':`）
- [ ] 5.3 确认既有 `tests/test_cli.py` 中全部断言 JSON 结构的用例**未经修改**即通过（JSON 契约零变化的证据）
- [ ] 5.4 新增测试断言人类模式被聚合掉的路径明细仍可从 `--json` 完整取回

## 6. 收尾

- [ ] 6.1 更新 `README.md`：贴一段 `loopspec init` 的实际人类可读输出示例
- [ ] 6.2 运行 `make lint` 与 `make test`，确保全绿（含既有 176 个测试）
- [ ] 6.3 人工肉眼验收：在 TTY 下真实跑一次 `init --tools claude,codex`（首次与二次各一遍，确认 Created/Refreshed 切换），再跑一次 `NO_COLOR=1` 与一次重定向到文件，确认降级正常
