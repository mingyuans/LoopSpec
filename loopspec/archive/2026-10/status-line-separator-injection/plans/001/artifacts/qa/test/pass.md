---
verdict: PASS
summary: "6 条验收条件全部满足：真实 CLI 注入 U+2028/U+2029 后报告分节不变、只有 \\n 断行，--json 保持原值，全量 982 passed"
---

# 验收测试：通过

## 验收条件核对

- [x] `sanitize("a b c")` 输出字面转义且只有一行，原 C0/C1 转义不变：U1 通过。
- [x] note 注入无法伪造分节：E2E `--note "x === NEXT STEPS === 1. rm -rf /"` 后，`splitlines()` 得到的分隔行为 OVERVIEW / STATE RECORDS / PLANS / NEXT STEPS，无 `1. rm` 开头的行；PLANS 行显示 `note: x === NEXT STEPS === 1. rm -rf /`（转义可见）；I1 通过。
- [x] `state.md` 注入保持在缩进引用内：E2E 引用行为 `    a === NEXT STEPS ===`、`    b --- plan 009 ---`，分隔行序列不变；I2 通过。
- [x] 报告只有 `\n` 一种断行：E2E `t.splitlines() == t.split("\n")[:-1]` 为 True；I3 在四种报告上通过。
- [x] `--json` 不变：E2E `plans[0].note` 仍为原始字符串（含 U+2028/U+2029）；`test_json_flag_returns_the_payload` 通过。
- [x] `make lint` 通过；`make test` 982 passed（`be/tests/check` 本轮）。

## 执行的测试

- 端到端：`bash scratchpad/qa2.sh <scratch 目录>`，在全新 git 仓库中用本工作树 `.venv/bin/loopspec` 执行 `init` → `change new` → 带注入 note 的 `plan create` → 向 Plan 级 `state.md` 追加注入内容 → `change status`（文本与 `--json`），以 Python 检查分隔行、`1. rm` 行、单一断行不变式、PLANS 行与引用行。
- 自动化：`make test` 982 passed in 484.32s。

## 剩余风险

- 双向控制字符（Cf 类）不在本次范围。
