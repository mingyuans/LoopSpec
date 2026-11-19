## 背景

`loopspec change archive` 把整个 Change 目录移到 `archive/<YYYY-MM>/<change>`，其中包括每个 Plan 下的 `.attempts/`：rollback 与修订时被归档的旧产物、报告、证据与 `record.yaml`。`.attempts` 只在活动 Plan 的返工流程中有用（Gate 的 rollback 计数、`priorAttempts`、`state add --section rework` 的轮次推导）。Change 归档后不再执行，这些文件只增加仓库体积与文件数（例如 registry-global-store 有 4 轮返工、几十个文件），返工的经验已记录在 `state.md` 的 rework 段落中。

## 用户场景

- 维护者完成一个 Change 后执行 `loopspec change archive <change>`，归档目录里只保留 `state.md`、各 Plan 的 `plan.yaml`、`artifacts/`、`.gates/`、`.gate-rounds/` 等，不再有 `.attempts/`。
- 维护者先用 `--dry-run` 预览，结果中能看到哪些 `.attempts/` 将被删除，但磁盘上什么都不变。
- 人明确放弃一个未完成的 Change，用 `--force` 归档，同样不保留 `.attempts/`。
- `--all` 批量归档时，每个被归档的 Change 都同样处理。

## 范围

- `change archive`（单个、`--force`、`--all`）实际归档时，删除归档后 Change 目录中每个 Plan（含已归档的 Plan）的 `plans/<NNN>/.attempts/`。
- 先完成目录移动再删除；删除不跟随符号链接，`.attempts` 为符号链接或非目录时不删除其目标。
- 结果 JSON 增加列出被删除（或 dry-run 时将被删除）的 `.attempts` 路径的字段。
- 更新中英文 CLI 文档与相关说明；补充 BDD 场景与单元测试。

## 非目标

- 不改变 `plan archive`（Plan 级归档）与返工流程（rollback、修订、`priorAttempts`）。
- 不清理 `archive/` 中已有的历史 `.attempts/`。
- 不删除 `.gate-rounds/` 或其他工作流文件。

## 验收条件

- [ ] 有返工记录的 complete Change 执行 `change archive` 后：目标目录存在，`plans/<NNN>/.attempts/` 不存在，`state.md`、`plan.yaml`、`artifacts/`、`.gates/` 仍在；原 Change 目录不存在。
- [ ] 结果 JSON 列出被删除的 `.attempts` 路径（相对归档目录）；没有返工记录时为空列表。
- [ ] `--dry-run`：返回将删除的路径，Change 目录与 `.attempts` 均保持不变。
- [ ] `--force` 归档未完成且有返工记录的 Change：`.attempts` 同样被删除，`forced: true`。
- [ ] `--all`：每个归档项都不含 `.attempts`。
- [ ] 一个 Change 有多个 Plan（含已 `plan archive` 的 Plan）时，所有 Plan 的 `.attempts` 都被删除。
- [ ] `.attempts` 是指向 Change 外部目录的符号链接时：归档成功，外部目录及其内容不被删除。
- [ ] 归档失败（如 `archive_unsafe`、`archive_conflict`）时不删除任何 `.attempts`。
- [ ] 中英文文档与一致性测试通过；`make lint`、全量测试通过。

## 风险

- 删除不可恢复：只在移动成功后、且只删除归档目录内的 `.attempts`；dry-run 可预览。
- 移动成功后删除失败（崩溃、权限）：Change 已归档，残留 `.attempts` 不影响正确性，结果中报告失败项；不回滚移动。
- 符号链接/竞态：用基于目录 fd、不跟随符号链接的删除。
