# Change State

## Current Focus
- 全部 7 个节点已 done：`security`（round 2 PASS）、`approval`（round 1 人类批准）、`apply`（29/29 任务勾选完成，报告见 `apply/report.md`）。`isComplete=true`，可归档。
- 归档前仍待人类决定的一件事：3 份 delta spec 如何进入 `openspec/specs/` 主 spec 库（人类已决定推迟到实现之后，见 Open Questions）。

## Frozen Decisions
- [approved] **D10：用户可控字符串的转义必须是呈现层接口的结构性保证**（内部 `escape()` 或 `Text`+`markup=False`），不得依赖调用点自觉 —— 由 round 1 门禁失败换来的结论，实测证据见 design D10 表格。
- [approved] 对齐范围限定为 **人类可读输出的呈现**；`--json` 的结构与字段完全不变（loopspec 的 `--json` 是主协议，而 OpenSpec 的 init 根本没有 JSON 模式，这一点故意不对齐）。
- [approved] 用已声明但从未使用的 `rich` 实现呈现层，确认为**强制依赖**、仅服务人类可读路径 —— 这同时结束了 `gated-artifact-workflow` design 里遗留的开放问题。
- [approved] 人类可读摘要**不再罗列文件路径**，改用聚合计数（`N skills and M commands in .claude, .codex`），路径明细只留在 `--json`。
- [approved] Created / Refreshed 的判定依据是"写入前该工具的 skill 文件是否已存在"，沿用既有「配置状态由文件系统判定、不持久化工具选择」规则，不新增清单文件。
- [approved] 呈现风格照搬 OpenSpec：纯扁平行 + 空行分节，**不用框线、表格、emoji**；2 空格缩进；字形只用 `✔ ✖ ⚠ • ▌`。
- [approved] **人类于 approval round 1 签核的计划基线**：tasks.md 的 6 组 29 项任务清单与其执行顺序（1 呈现层基础 → 2 scaffold created/refreshed → 3 init 摘要渲染 → 4 交互式状态标签 → 5 契约护栏 → 6 收尾），以及 design 的 D1（rich 为强制依赖、仅人类路径）、D4（聚合计数替代路径明细）、D7（`_emit()` 不动、init 走专用渲染器）、D10（呈现层接口内部强制转义）四项决策。后续节点不得擅自变更这些要点；确需变更须重新走一轮 `approval`。

## Decision Log
- 2026-07-28: 定位问题根因 —— `_emit()` 的人类分支就是把 JSON 同一个 dict 逐条 `key: value` 打印，所以 dict/list 会以 Python repr 泄漏给用户。
- 2026-07-28: 调研 OpenSpec 呈现栈为 chalk + ora（无 boxen/cli-table3/ink）；Python 侧 `rich` 一个库即可同时覆盖颜色与 spinner。
- 2026-07-28: 确认 OpenSpec 的成功摘要**不枚举文件**，只给聚合计数 + Created/Refreshed 分组 —— 这直接决定了本变更要放宽 `loopspec-cli` 里「两种模式信息内容一致」的既有要求。
- 2026-07-28 (round 1 → 2): `security` 门禁 FAIL，阻断问题为「用户可控路径进 `rich` 渲染无转义」。实测两种失效：`[red]`/`[oops]` 被当作样式标记导致**静默篡改路径**（渲染出不存在的路径且无报错，比崩溃更危险）、`[/]`/`[/bold]` 抛 `MarkupError` 中断命令。已回退 design/tasks（归档于 `.attempts/round-001/`）并新增 D10 关闭该问题。
- 2026-07-28 (round 2): `security` 门禁 PASS。同时采纳了 round 1 的非阻断建议——人工验收改在隔离 `CODEX_HOME` 下进行，避免污染开发者真实的 `~/.codex/prompts/`。
- 2026-07-29 (approval round 1): 人类批准按 tasks.md 的 6 组 29 项计划进入实现，但附一个前置条件——先更正过期计数。条件已在写出判定前满足：`tasks.md` 顶部新增「计数更正」注记（明确 29 项及按组分布）、6.2 的测试基线由「176 个」改为「221 个」、本文件 `Artifact Notes` 的 `tasks.md` 条目由「25 项」改为「29 项」。`security/pass.md` 里的「25 项」保持原样不改写，因为它是已出具的门禁判定记录，改写会污染审计轨迹。判定原话见 `approval/approved.md`。
- 2026-07-29 (approval round 1): 人类就「3 份 delta spec 如何进入 `openspec/specs/` 主 spec 库」决定**暂缓**——本轮只做实现，delta 暂留在 `loopspec/changes/improve-init-display/specs/` 下，实现完成后再定归宿。
- 2026-07-29 (apply): 29 项任务全部实现并勾选完成。`make test` 268 通过（基线 221，新增 47 条）、`make lint` 全绿、隔离环境人工验收 6 项全过。D10 的两个可选实现选了「构造 `Text` 对象」而非 `rich.markup.escape()`，因为 `Text` 不会被二次解析，天然避开 `security/pass.md` Notes 提醒的「转义只能做一次」陷阱。
- 2026-07-29 (apply): `init` 的 JSON 载荷新增 `createdTools`/`refreshedTools` 两个键（纯新增，不改既有字段名与结构），让 Agent 能拿到与人类摘要同一组事实；既有 JSON 断言用例一行未改即全绿，作为契约未破的证据。

## Rejected Options
- [superseded] 移植 OpenSpec 的逐帧动画 ASCII logo（8 帧 / 120ms / 裸 ANSI 光标控制）：投入产出不划算，且 OpenSpec 自己在非 TTY / `NO_COLOR` / 窄终端下也只渲染静态帧。
- [superseded] 把交互式工具选择升级为方向键 + 可搜索多选（OpenSpec 用 @inquirer/core 自研组件）：需要裸终端输入处理或引入新依赖，与既有决策 D7（不为次要交互引入新依赖）冲突；只吸收其**信息**部分，即 `(configured)`/`(refresh)`/`(detected)` 状态标签。
- [superseded] 顺手把 `status`/`instructions`/`rollback` 等命令的人类输出一起改造：范围过大，本次只建立可复用呈现语汇，其余命令留作后续变更。

## Open Questions
- [approved] ~~`Learn more:` / `Feedback:` 链接指向哪里~~ —— 已由 design D8 关闭：取自仓库 origin，即 `https://github.com/mingyuans/LoopSpec`。
- [approved] ~~是否需要静态 banner~~ —— 已在 design Non-Goals 中明确不做。
- [under-review] **本变更的 delta spec 如何进入主 spec 库？** 这份 change 由 loopspec 管理（`loopspec/changes/`），但项目的主 spec 库在 `openspec/specs/`，而 loopspec **没有实现 delta→主 spec 的同步机制**（那是 OpenSpec 独有的能力）。因此 3 份 delta 需要人工应用，或借 OpenSpec 工具链应用。人类已于 approval round 1 决定**暂缓到实现之后再定**，本轮不处理；届时的候选路径是「在 `openspec/` 建一个承载这 3 份 delta 的 change 并走 `openspec archive` 合并」或「手工写进 `openspec/specs/` 对应文件」。
- [under-review] `loopspec/` 目录当前未纳入版本控制（用户明确要求本轮不动、不提交），因此这份规划产物目前也在版本控制之外 —— 若要保留需重新决定。

## Artifact Notes
- proposal.md: approved（round 1 写就，未被回退，含明确的非目标清单）
- specs/: approved（3 份，未被回退：新增 `cli-presentation` 6 需求、`loopspec-cli` 2 条 MODIFIED、`tool-scaffolding` 1 条 ADDED）
- design.md: approved（round 2；round 1 版本存档于 `.attempts/round-001/design.md`）
- tasks.md: approved（round 2，6 组共 **29** 项；round 1 版本存档于 `.attempts/round-001/tasks.md`）
- security（gate）: PASS（round 2；round 1 的 fail.md 存档于 `.attempts/round-001/security/fail.md`）。判定正文里的「25 项」是 round 1 旧计数，未改写以保留审计轨迹。
- approval（gate）: PASS（round 1，人类批准并附「先更正过期计数」的前置条件，条件已满足；判定与原话见 `approval/approved.md`）
- apply（gate）: PASS（29/29 任务勾选完成；改动文件清单、真实测试结果、与设计的 4 处偏离及后续项见 `apply/report.md`）
