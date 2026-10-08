# 基于本次全量 Diff 的确定性交付保障

执行 `gate record`（不带 `--round` 与 `--report`），由 CLI 按 Change 固定基线核对全量 Diff、必需能力和活动 Plan 中的有效证据，并写出系统 PASS 或 FAIL。不得手写 PASS。诊断提示缺少 Fragment 时，编写修订请求加入对应实例并让本节点依赖它，经人确认后修订；修复后重新经过受影响的 QA 与保障。
