# Human Approval: APPROVED

## Summary Presented to the Human

- **问题**：`loopspec init` 的人类可读输出把喂给 `--json` 的同一个 dict 逐条 `key: value` 转印，嵌套结构以 Python repr 泄漏给用户（`scaffoldedFiles: {'claude': [...]}`）；`rich>=13` 声明为依赖却从未 import。
- **能力变动**：新增 `cli-presentation`（6 条需求：集中化呈现语汇、字形配色表、ASCII 降级、颜色环境降级、JSON 模式抑制装饰、进度仅人类模式）；`loopspec-cli` 2 条 MODIFIED；`tool-scaffolding` 1 条 ADDED（created/refreshed 分组）。
- **关键决策与取舍**：D1 `rich` 确认为强制依赖、仅服务人类路径（代价是引入 markup 解析风险）；D4 摘要用聚合计数替代路径明细（代价是人类模式成为 `--json` 的有损聚合，因此放宽 `loopspec-cli` 原有「两种模式信息内容一致」的要求）；D7 `_emit()` 不动、`init` 走专用渲染器（其余 8 个命令留作后续变更）；D10 用户可控字符串在接口层强制转义。
- **任务规模与顺序**：6 组 29 项，`presentation.py`（含 D10 转义与 1.7 回归测试）→ `scaffold.py` created/refreshed 分组 → `init` 渲染器接入 → 交互式状态标签 → 契约护栏 → 收尾；Migration Plan 要求 1.2/1.7 与呈现模块同批落地。
- **安全结论**：round 2 PASS，round 1 的阻断问题（用户可控路径进 `rich` 无转义）被判定为实质解决——D10 附实测证据、区分静默篡改与 `MarkupError` 崩溃两种失效模式、保证落在接口层。遗留非阻断提醒：选 `escape()` 方案时须约定「转义只做一次」。
- **审查中发现并一并汇报的三处**：(1) `tasks.md` 实际 29 项，但 `state.md` 与 `security/pass.md` 记作 25 项，且 6.2 写着「既有 176 个测试」而当前基线为 221 个；(2) `state.md` 有两个 `[under-review]` 未决问题（3 份 delta spec 如何进 `openspec/specs/`、`loopspec/` 目录仍在版本控制之外）；(3) design.md 记 OpenSpec v1.5.0 而本机为 1.6.0（不影响调研结论）。

## Human's Words

审批结论：**「先修计数再执行」** —— 原文选项描述为「批准方向，但要求先把 tasks.md/state.md 里『25 项』『176 个测试』等过期数字改对，再进 apply」。

delta spec 归宿：**「暂不决定，实现后再说」** —— 原文选项描述为「保持 under-review，本轮只做实现；delta 留在 loopspec/changes/ 里」。

## Non-Blocking Suggestions

无额外建议。人类提出的唯一条件（更正过期计数）属于批准的前置动作，已在写出本判定之前完成：

- `tasks.md` 顶部新增「计数更正」注记，明确本文件共 29 项并按组给出分布。
- `tasks.md` 6.2 的测试基线由「176 个」改为「221 个」。
- `state.md` 的 `Artifact Notes` 中 `tasks.md` 条目由「25 项」改为「29 项」。
- `security/pass.md` 中的「25 项」**未改写**：它是已出具的门禁判定记录，改写会污染审计轨迹；计数以 `tasks.md` 的更正注记为准。

## state.md Write-Back

- Decision Log: round 1 - approved（含前置条件与其满足情况、delta 归宿的暂缓决定）
- Frozen Decisions: 29 项任务清单与 6 组顺序、D1/D4/D7/D10 四项决策、`--json` 契约零变化
- Open Questions: delta spec 归宿改记为「人类决定暂缓至实现之后」
- Artifact Notes: approval/approved.md - approved；tasks.md 计数已更正为 29 项
