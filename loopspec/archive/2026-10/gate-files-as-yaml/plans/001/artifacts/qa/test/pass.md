---
verdict: PASS
summary: "6 条验收条件全部满足：真实 CLI 推进代码证据 Gate 后 begin / evidence / round 文件均为多行 YAML、无 JSON 单行，Gate 判定正常；全量 986 passed"
---

# 验收测试：通过

## 验收条件核对

- [x] `gate begin` 后 `begin.yaml` 与 `.gate-rounds/<gate>/001.yaml` 为多行 YAML，字段与 begin 返回一致：E2E 输出 `gate: be/tests/check`、`plan_digest: …`、`round: 1`、`round_id: 001.1:be/tests/check:1` 等多行键值；Y1 通过。
- [x] 代码证据 `gate record` 后 `evidence.yaml` 为多行 YAML：E2E 输出多行键值，`gate record` 返回 `verdict: PASS`；Y2 通过。
- [x] 保障 `gate record` 后 `assurance.yaml`、`evidence.yaml`、round 文件为多行 YAML：Y3+Y4 用例通过（含全目录无 JSON 单行检查）；本 Change 的 `assurance/check` 由新代码记录，同样适用。
- [x] 旧 JSON 内容文件仍可读：Y5 通过（改回紧凑 JSON 后 Gate 仍 done，`gate record` 仍成功）。
- [x] 证据判定不变：E2E `be/tests/check` 记录后为 done；`test_workflow_evidence.py`、`test_workflow_assurance.py`、`test_workflow_e2e.py` 通过。
- [x] `make lint` 通过；`make test` 986 passed。

## 执行的测试

- 端到端：`bash scratchpad/qa3.sh <scratch 目录>`，在全新 git 仓库中用本工作树 `.venv/bin/loopspec` 执行 `init` → `change new` → `plan create/approve` → 写产物并改业务代码 → `gate begin` → 写 PASS 报告 → `gate record`，查看 `begin.yaml`、`evidence.yaml`、`001.yaml` 内容，`grep -rl '^{' --include=*.yaml` 结果为 none，`change status` 显示 `be/tests/check done`。
- 自动化：`make test` 986 passed in 498.63s。

## 剩余风险

- 已有 Change 与归档中的旧 JSON 内容文件按决策不迁移，混合格式会长期存在，但均可读。
