# 需求记录

需求背景、跨 Plan 的决策与更替原因。
人与 LLM 可直接编辑；`loopspec change status` 原样输出全文，引擎不解析。

## 背景

提交 `31a5286`（state-md-writeback）后，Claude Code 的后台提交安全审查报告 `src/loopspec/status_report.py`
存在输出注入 / 解析差异问题（通知只有标题，无细节）。复现确认：

- `presentation.sanitize()` 只转义 C0/C1 控制字符，未处理 Unicode 行分隔符 U+2028 / U+2029；
  `status_report._QUOTED_CONTROL` 同样未覆盖。
- 按 Unicode 断行的解析器（Python `str.splitlines()`、部分 LLM 分词 / 渲染）会把它们当换行，于是
  `--note` 或 `state.md` 中的 `x\u2028=== NEXT STEPS ===` 在 `change status` 纯文本报告里变成一条顶格的伪造分隔行，
  绕过"插值不能伪造顶格分隔行"的防线。
- `state.md` 事件行不受影响（`one_line()` 已折叠所有空白）。

## 目标 / 非目标

- 目标：`change status` 纯文本报告中所有插值与 `state.md` 原文里的 U+2028 / U+2029 都改写为可见转义，
  任何按 Unicode 断行的解析都不能从中切出新行；补测试覆盖 note 与 `state.md` 两条路径。
- 非目标：不改报告版式与 `--json` 字段；不处理双向控制字符（Cf 类，仅影响显示、不产生换行）；不改 `state.md` 写入逻辑。

## 关键决策

- 2026-10-09（用户）：通过 LoopSpec bugfix Change 修复，而非直接提交 `fix:` 提交。

## 参考

- 引入提交：`31a5286`；归档 Change：`loopspec/archive/2026-10/state-md-writeback`。

## Plan 记录

<!-- 引擎在此之后追加 Plan 归档事件；LLM 可在事件行下补充更替原因。 -->
