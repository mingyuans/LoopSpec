## 背景

`change archive` 已在归档时删除各 Plan 的 `.attempts/`。归档目录中仍保留 Gate 相关文件，它们只在执行中的 Plan 用于证据绑定与轮次推导：`.gates/`（`begin.yaml`、`evidence.yaml`、`assurance.yaml`）、`.gate-rounds/`（每轮记录与 `prior/` 报告副本），以及 `artifacts/` 下各 Gate 的 `pass`/`fail` 报告。人已确认这三类都在归档时删除，只保留需求、设计、实现等非 Gate 产物（HUMAN 决策见 change 级 state）。

## 用户场景

- 维护者归档完成的 Change 后，归档目录只剩 `state.md`、`.workflow.yaml`、各 Plan 的 `plan.yaml`、`state.md` 与非 Gate 产物（如 `requirements/proposal.md`、`be/code/implementation.md`、QA 附带的脚本）。
- `--dry-run` 预览会删除的全部路径，不改动磁盘。
- `--force`、`--all` 同样处理。

## 范围

- `change archive` 移动成功后，对每个 Plan（含已 `plan archive` 的 Plan）删除：`plans/<NNN>/.attempts/`（已有）、`plans/<NNN>/.gates/`、`plans/<NNN>/.gate-rounds/`，以及该 Plan `plan.yaml` 中所有 Gate 节点声明的 `outputs.pass`/`outputs.fail` 文件；删除后清理因此变空的目录（不超过 `plans/<NNN>/artifacts/`）。
- Gate 报告只按 `plan.yaml` 声明的路径删除，同目录下的其他文件（如 `acceptance.sh`）保留。
- 删除沿用现有方式：经移动时持有的目录 fd、逐级 O_NOFOLLOW、先确认归档位置是同一目录；失败只报告不回滚。
- 结果字段统一为 `dropped`（删除或 dry-run 将删除的路径）与 `notDropped`（删除失败），取代仅含 `.attempts` 的 `droppedAttempts`/`attemptsNotDropped`（该字段只在未发版的 PR #14 中出现）。
- 中英文文档、BDD 与单元测试同步。
- 按同一规则清理 `loopspec/archive/` 下已有的新格式（有 `plans/`）归档。

## 非目标

- 不清理旧格式（1.x schema，无 `plans/`）归档：其 `security/`、`approval/` 等文件不能从现有定义可靠判定为 Gate 产物。
- 不改 `plan archive`、返工流程与 Gate 判定逻辑。

## 验收条件

- [ ] 有代码 Gate、assurance 与 qa Gate 的 complete Change 归档后：`plans/001/.gates`、`.gate-rounds`、`.attempts` 均不存在；`artifacts/` 下不存在任何 Gate 的 pass/fail 文件；`requirements/proposal.md`、`be/code/implementation.md` 等非 Gate 产物仍在；Gate 输出目录中的其他文件仍在。
- [ ] 因删除变空的 Gate 输出目录被移除，非空目录与 `artifacts/` 本身保留。
- [ ] `dropped` 列出全部删除路径；`--dry-run` 返回相同列表且磁盘不变。
- [ ] 多 Plan（含已归档 Plan）与 `--all`、`--force` 都按同一规则删除。
- [ ] 拒绝或失败的归档不删除任何内容；`plan.yaml` 无法读取时仍删除控制目录、跳过报告并不影响归档。
- [ ] 历史清理后，`loopspec/archive/` 中所有新格式归档不含 `.gates`、`.gate-rounds`、`.attempts` 及 Gate 报告；旧格式归档不变。
- [ ] lint、全量测试、docs 一致性通过；LLM E2E 通过。

## 风险

- 删除不可恢复，且 Gate 审查结论随之移除：人已确认；`state.md` 中的决策、偏差与 rework 记录保留。
- 字段改名：`droppedAttempts` 未发版，影响面仅 PR #14 之后的未发布代码。
