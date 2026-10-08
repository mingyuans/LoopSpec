# Plan 001

本计划执行中的决策与备注（人读，引擎不读取）。

- 2026-10-08：基线落后 HEAD 5 个提交，经用户同意删除原草稿并重建 Change，基线改为 `ac4ff4f`。
- 2026-10-08：用户确认并批准 Plan 001，revision 1，digest `321f50cd`。
- 2026-10-08：requirements/proposal 完成后，用户要求 `change status` 输出两级 `state.md` 全文，已并入提案范围 C。
- 2026-10-08：design/design 完成，采用提案中待确认的 5 处取舍作为默认方案（追加失败不报错、缺失重建、note 单行化、gate record/change archive 不追加、status 含已归档 Plan 且单文件 64 KiB 截断），待用户评审。
- 2026-10-08 [design/design] 用户要求 status 默认输出 Markdown、--json 输出 JSON；设计第 5 节已改为 5.1 数据/JSON、5.2 Markdown 报告、5.3 渲染安全、5.4 CLI。
- 2026-10-08 [design/design] 用户要求恢复 1.x 的 `=== SECTION ===` 纯文本版式，取代 Markdown 报告；设计 5.2/5.3 已重写，state.md 原文改为逐行缩进 4 空格引用。
- 2026-10-08 [design/design] 用户要求 status 列出各 Plan 现有 artifacts 及简单说明；新增 plans[].artifacts 字段与 === ARTIFACTS === 节。
- 2026-10-08 [design/design] 产物清单收窄为只列活动 Plan，字段改为顶层 artifacts / artifactsTruncated。
- 2026-10-08 [design/design] 撤销 === ARTIFACTS === 与 artifacts 字段，产物信息由 === NODES === 承载；T24–T26 删除。
- 2026-10-08 [design/design] 去掉 === INSTANCES === 节，instances 仅保留在 --json，字段覆盖测试中列为有意省略。
- 2026-10-08 [design/design] status 的 Plan 级 state 只输出当前 Plan，JSON 字段改为顶层 planState。
- 2026-10-08 [design/design] 确认 === PLANS === 保留已归档 Plan 的摘要行。
- 2026-10-08 [design/design] 用户批准设计；planning 时 planState 输出草稿 Plan 的 state.md 按默认保留。
- 2026-10-08 [design/tasks] 用户确认测试计划 T1–T23 与任务拆分，开始 be/code/implement。
- 2026-10-08 [be/code/implement] 实现完成：tasks 1.1–6.3 全部勾选，make lint 通过，make test 974 passed；偏差见 implementation.md。
- 2026-10-08 [be/tests/check] PASS：make test 974 passed（轮次 001.1:be/tests/check:1）。
- 2026-10-08T14:36:49+00:00 · rollback · gate be/security/check · attempt 1 · reset: assurance/check, be/code/implement, be/review/check, be/security/check, be/tests/check, qa/test
- 2026-10-08 [be/security/check] attempt 1：append_text/read_capped 未拒绝硬链接，state.md 硬链接到 Change 外文件时会越界写入并在 status 泄露外部内容；修复方向：打开后检查 st_nlink == 1，补硬链接测试。
- 2026-10-08 [be/code/implement] 返工 attempt 1 完成：拒绝硬链接，补 2 个用例；make test 976 passed。
- 2026-10-08 [be/tests/check] 第 2 轮 PASS：make test 976 passed。
- 2026-10-08 [be/security/check] 第 2 轮 PASS：硬链接问题已修复。
- 2026-10-08T15:02:57+00:00 · rollback · gate be/review/check · attempt 2 · reset: assurance/check, be/code/implement, be/review/check, be/security/check, be/tests/check, qa/test
- 2026-10-08 [be/review/check] attempt 2：new.md 插入第 3 步后 continue.md 仍引用 steps 3-8，重新规划会漏掉 approve；修复方向：改为 steps 3-9、同步已安装副本、补区间一致性测试与 glob 续行渲染用例。
- 2026-10-08 [be/code/implement] 返工 attempt 2 完成：steps 3-9，补区间一致性与 glob 续行用例。
- 2026-10-08 [be/tests/check] 第 3 轮 PASS：make test 978 passed。
- 2026-10-08 [be/security/check] 第 3 轮 PASS。
- 2026-10-08 [be/review/check] 第 2 轮 PASS。
- 2026-10-08 [qa/test] PASS：26 条验收条件全部满足（E2E + 978 个用例）。
- 2026-10-08 [assurance/check] 系统保障 PASS：14 个路径均有 backend-tests / security-review / pr-review 有效证据，无 unknown/missing/stale/diverged。
