# 归档行为与归档前取证

适用时机：归档 Change、修改 `change archive`，或事后需要查找某个已归档 Change 的审查结论时。

- 归档只保留 `state.md`、各 Plan 的 `plan.yaml`/`state.md` 与非 Gate 产物（需求、设计、实现报告、QA 附带脚本等）；`.attempts/`、`.gates/`、`.gate-rounds/` 与 Gate 的 PASS/FAIL 报告会被删除。需要长期保留的结论应写进 `state.md`（决策、偏差、rework）或 memory，并在第二段 `--confirm` 之前完成 memory 审阅。原因：这些文件只服务执行中的 Plan。来源：archive-drop-attempts、archive-drop-gate-outputs 的 HUMAN 决策（2026-11-19，用户决定，非测试结论）。
- 已归档 Change 的 Gate 报告与返工记录只能从 git 历史找回：看归档提交之前那个提交里的 `loopspec/changes/<change>/`。来源：archive-drop-gate-outputs 历史清理（2026-11-19，实际执行并抽查验证）。
- 1.x schema 时代的旧格式归档（没有 `plans/`）未清理，其 `security/`、`approval/`、`apply/` 无法按现有定义判定为 Gate 产物，处理需要人另行决定。来源：archive-drop-gate-outputs 的 assumption（2026-11-19）。
- 归档分两段：`loopspec change archive <change>`（或 `--all`）只复核并返回 `archiveId`、审阅指引与素材；读完素材、维护 memory 后用 `loopspec change archive --confirm <archiveId> --memory updated|none --note <说明>` 完成。`--dry-run` 已删除。两段之间改动 Change（包括 `state add`）会使凭据失效（`archive_ticket_stale`），需重新执行第一段；所以先整理 `state.md`，再执行第一段。来源：archive-memory-review（2026-11-19），单测、BDD、端到端脚本与 LLM E2E 均已通过。
