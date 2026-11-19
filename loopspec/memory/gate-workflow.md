# Gate 与保障的执行顺序

适用时机：推进代码 Gate 与 assurance，或在已有提交之后继续修改代码时；规划 Plan 时也适用。

- 代码改完先 commit 最终内容，再执行 assurance 的 `gate record`。HEAD 中既不是基线、也不是审查过的工作区内容的中间提交会让 assurance 判 FAIL（diverged commits）。来源：registry-global-store 的待解决问题（2026-11-19，实际发生）。
- 规划时给 assurance 配 `on_fail`（例如 `reset: [qa]`）。没有 `on_fail` 的 assurance 一次有效 FAIL 即 exhausted，修订又不能改冻结节点，只能归档 Plan 重新规划或保持现状。来源：registry-global-store（2026-11-19，实际发生）；archive-drop-attempts 起的 Plan 已按此配置。
- 交付 diff 在 Gate 之后又有变化（例如追加历史清理提交）时，只有受影响的 Gate 证据会过期，通常只需重跑 assurance。来源：archive-drop-attempts、registry-global-store（2026-11-19，实际发生）。
