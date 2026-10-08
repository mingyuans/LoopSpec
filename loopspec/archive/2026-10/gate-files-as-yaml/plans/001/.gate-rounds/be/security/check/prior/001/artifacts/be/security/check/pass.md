---
verdict: PASS
summary: "Gate 控制文件改用 yaml.safe_dump 写入、读取仍经 StrictLoader；实测无锚点 / 别名，证据完整性与路径约束不变，无阻塞问题"
---

# 后端安全审查：通过

## 审查输入

- 轮次：`001.1:be/security/check:1`；基线 `21f17e1789cd2b114e56006000f5c0b7e138a27c`；scopeDigest `d43569a0…`；warnings：无。
- 路径：`src/loopspec/workflow_assurance.py`、`src/loopspec/workflow_evidence.py`、`tests/test_gate_file_format.py`。

## 检查项

- 不安全序列化 / 反序列化：写入为 `write_yaml()` → `yaml.safe_dump`（只输出标准标签，不产生 Python 对象标签）；读取仍为 `parse_yaml()` 的 `StrictLoader`（拒绝别名、重复键、非字符串键，限深度与条目数），未放宽。
- 锚点 / 别名：`safe_dump` 在同一对象被引用两次时会输出 `&id` / `*id`，而 `StrictLoader` 拒绝别名。核对数据来源：`begin` / `evidence` 为 `model_dump()` 新建对象，`assurance` 诊断中每个 `requiredCapabilities` 列表由 `sorted()` 新建；实测推进到保障通过（含两个业务路径）后，Plan 目录下全部 `.yaml` 均无 `&id` / `*id`。
- 证据完整性：证据校验比较解析后的值与 `report_hash`（报告文件字节），不对控制文件字节做哈希；返工归档的 sha256 在归档时现算，格式变化不影响。
- 路径穿越：写入路径与 `atomic_write()`（目录描述符、`O_NOFOLLOW`、临时文件 + 原子替换）不变；`exclusive=True` 的 round 文件仍以 link 方式防覆盖。
- 注入：值来自模型与诊断数据，经 YAML 序列化转义，不进入 shell / 模板。
- 敏感信息、认证 / 授权、依赖来源：未涉及变化。

## 剩余风险

- 若日后让同一 list / dict 在这些载荷中出现两次，`safe_dump` 会写出别名，下次读取时被 `StrictLoader` 拒绝（fail closed，不会被绕过）。这与已用 `write_yaml()` 的 `plan.yaml`、`record.yaml` 是同一既有约束，本次不处理；可后续让 `write_yaml()` 使用忽略别名的 Dumper。
