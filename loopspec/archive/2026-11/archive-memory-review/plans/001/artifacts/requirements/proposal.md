## 背景

`loopspec change archive` 一条命令即可归档。memory 审阅（把可复用结论沉淀到 `loopspec/memory/`）只写在 `loopspec-archive` skill 里，模型直接调用 CLI 就能跳过；archive-drop-attempts、archive-drop-gate-outputs 两次归档都被跳过，项目 memory 至今为空。归档还会删除 Gate 报告与 `.attempts`，跳过后这些素材在工作区中不可再得。

## 用户场景

- Agent 归档一个完成的 Change：第一段命令得到 `archiveId`、审阅指引与要读的素材路径；读完素材、维护 memory 后，用第二段命令带上 `archiveId` 与审阅结论完成归档。
- Agent 认为没有新知识：第二段用 `--memory none` 并在 `--note` 写明理由，这个结论被写入 Change 的 `state.md`，评审可见。
- Agent 谎称已更新：`--memory updated` 但 `memory/` 没有任何变化时，CLI 拒绝。
- 人放弃 Change：`--force` 归档同样走两段。
- 批量归档：`--all` 第一段为全部符合条件的 Change 发一个批次 `archiveId`，第二段一次确认。

## 范围

- 第一段 `loopspec change archive <change> [--force]` / `--all [--older-than <days>]`：照常复核状态与证据，不移动、不删除；在 `<home>/.cache/archive/` 写凭据（绑定每个 Change 目录的内容摘要与 `memory/` 快照）；返回 `archiveId`、`memoryReview`（维护流程原文、素材路径、当前 memory 索引）、每个 Change 的状态与将删除的路径、下一步命令。
- 第二段 `loopspec change archive --confirm <archiveId> --memory updated|none --note <text>`：三项必填；重新复核状态；凭据不存在、Change 内容在两段之间变化时拒绝；`updated` 要求 `memory/` 相对快照确有变化，`none` 要求没有变化；在移动前把审阅结论（选择、说明、变化的 topic）作为事件写入每个 Change 的 `state.md`；然后移动、删除运行期文件；成功后删除凭据。
- 删除 `--dry-run`（第一段即预览）。
- 更新 `loopspec-archive`、`loopspec-bulk-archive` skill 与本仓库生成副本、中英文文档、BDD、单元测试与 LLM E2E 场景。
- 补做 archive-drop-attempts、archive-drop-gate-outputs 两次被跳过的 memory 审阅（素材：两者 `state.md` 与 git 历史中的 Gate 报告）。

## 非目标

- 不判断 memory 内容质量；`none` 加理由仍可跳过，但必须显式并留痕。
- 不改 `plan archive`、Gate 判定与删除范围。

## 验收条件

- [ ] 第一段不移动、不删除任何文件，返回 `archiveId`、`memoryReview.instructions`（含 "Memory maintenance procedure"）、素材路径（state.md、产物、Gate 报告、`.attempts` 记录）与 `nextSteps`；凭据写入自带 `.gitignore` 的 `.cache/archive/`。
- [ ] 第二段缺少 `--memory` 或 `--note`、`--note` 为空、`archiveId` 不存在时以明确错误码失败，不移动。
- [ ] 两段之间 Change 目录内容变化时报凭据过期，不移动。
- [ ] `--memory updated` 而 `memory/` 无变化、或 `--memory none` 而 `memory/` 有变化时拒绝，不移动。
- [ ] 成功时 Change 的 `state.md` 末尾有审阅事件（含选择、说明与变化的 topic），归档目录中可见；凭据被删除；结果返回 `memoryReview` 记录。
- [ ] `--force` 与 `--all` 两段流程同样生效；`--confirm` 与 Change 名、`--all`、`--force`、`--older-than` 同时使用时报 `option_conflict`。
- [ ] `--dry-run` 不再被接受。
- [ ] 本仓库 `loopspec/memory/` 有来自两次被跳过归档的条目，注明来源。
- [ ] lint、全量测试、docs 一致性、LLM E2E 通过。

## 风险

- 破坏性改动：单命令归档与 `--dry-run` 不再可用，依赖旧用法的脚本与旧 skill 需要更新（skill 随 `loopspec init` 刷新）。
- 模型仍可用 `none` 加敷衍理由跳过：通过留痕在评审中暴露，不由 CLI 判断。
- 凭据残留：未确认的凭据留在 `.cache/archive/`，已忽略且可随时删除。
