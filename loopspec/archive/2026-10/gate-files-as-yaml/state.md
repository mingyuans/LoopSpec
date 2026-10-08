# 需求记录

需求背景、跨 Plan 的决策与更替原因。
人与 LLM 可直接编辑；`loopspec change status` 原样输出全文，引擎不解析。

## 背景

用户发现 `.gate-rounds/<gate>/NNN.yaml` 等 Gate 控制文件内容是 JSON，扩展名却是 `.yaml`。核实：
`workflow_evidence.py`（begin.yaml、NNN.yaml、evidence.yaml）与 `workflow_assurance.py`（NNN.yaml、assurance.yaml、
evidence.yaml）共 7 处用 `write_json()` 写入；读取一律走 `parse_yaml()`，JSON 恰是合法 YAML，所以功能正常但格式与扩展名不符。
同目录的 `plan.yaml`、`.attempts/*/record.yaml`、`.workflow.yaml` 均为 `write_yaml()` 写的真 YAML。

## 目标 / 非目标

- 目标：上述 Gate 控制文件改为真正的 YAML（`write_yaml()`），读取逻辑不变；旧的 JSON 内容文件继续可读。
- 非目标：不改扩展名为 `.json`；不改文件路径与字段；不迁移或改写已有 Change / 归档中的文件；不改 registry 的 `plan.json`。

## 关键决策

- 2026-10-09（用户）：Gate 控制文件按 YAML 写，不改成 `.json`；理由：读取端与旧文件无需变更，和同目录其他控制文件一致。
- 2026-10-09（用户）：通过 LoopSpec bugfix Change 修复。

## 参考

- 写入点：`src/loopspec/workflow_evidence.py:174`、`:178`、`:270`、`:291`；`src/loopspec/workflow_assurance.py:222`、`:226`、`:227`。

## Plan 记录

<!-- 引擎在此之后追加 Plan 归档事件；LLM 可在事件行下补充更替原因。 -->
