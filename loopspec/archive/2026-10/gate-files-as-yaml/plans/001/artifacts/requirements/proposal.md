## 背景

Plan 目录下的 Gate 控制文件扩展名都是 `.yaml`，但内容是单行 JSON：

| 文件 | 写入位置 |
| --- | --- |
| `.gates/<gate>/begin.yaml` | `workflow_evidence.py:178`、`:270` |
| `.gates/<gate>/evidence.yaml` | `workflow_evidence.py:291`、`workflow_assurance.py:227` |
| `.gates/<gate>/assurance.yaml` | `workflow_assurance.py:226` |
| `.gate-rounds/<gate>/NNN.yaml` | `workflow_evidence.py:174`、`workflow_assurance.py:222` |

它们都用 `write_json()`（`canonical()` 紧凑 JSON）写入，读取则一律走 `parse_yaml()`（`ResourceBundle.model()`）。JSON 是合法 YAML，
所以功能正常，但格式与扩展名不符，人读时也不便。同目录的 `plan.yaml`、`.attempts/*/record.yaml`、`.workflow.yaml`
都用 `write_yaml()` 写真 YAML。用户发现后决定：按 YAML 写，不改扩展名。

## 用户场景

1. 人在 IDE 中打开 `.gates/` 或 `.gate-rounds/` 下的文件，看到与其他控制文件一致的多行 YAML。
2. 升级后继续推进升级前创建的 Change：已有 JSON 内容的 Gate 文件仍被正确读取，证据不失效。

## 范围

- 上表 7 个调用点从 `write_json()` 改为 `write_yaml()`（`exclusive` 等参数保持不变）。
- 测试：新写出的四类文件是 YAML（非 JSON 单行），解析结果与原字段一致；旧的 JSON 内容文件仍可读取、证据仍有效。

## 非目标

- 不把扩展名改为 `.json`，不改文件路径、字段名与模型。
- 不迁移、不改写已有 Change 与 `archive/` 中的文件。
- 不改 registry 缓存的 `plan.json`（它本来就是 `.json`）。
- 不改证据比较逻辑（比较的是解析后的值，不是文件字节）。

## 验收条件

- [ ] `gate begin` 后 `.gates/<gate>/begin.yaml` 与 `.gate-rounds/<gate>/NNN.yaml` 不以 `{` 开头、为多行 YAML，`yaml.safe_load` 结果等于 `Begin` 模型的 `model_dump()`。判定：集成测试。
- [ ] `gate record`（代码证据）后 `.gates/<gate>/evidence.yaml` 为多行 YAML，解析结果字段完整。判定：集成测试。
- [ ] 保障 `gate record` 后 `assurance.yaml`、`evidence.yaml` 与本轮 `NNN.yaml` 均为多行 YAML。判定：集成测试。
- [ ] 把已有的 `begin.yaml` / `evidence.yaml` 改写为旧版紧凑 JSON 后，`change status` 中该 Gate 仍为 done，`gate record` 仍可正常提交。判定：集成测试。
- [ ] 改动前后同一 Gate 的证据判定不变：既有 `tests/test_workflow_evidence.py`、`test_workflow_assurance.py`、`test_workflow_e2e.py` 全部通过。
- [ ] `make lint` 通过，`make test` 全量通过。

## 风险

- **YAML 往返类型**：`write_yaml()` 用 `yaml.safe_dump`，会为形似数字 / 布尔的字符串（如 `001`、全数字摘要）加引号，往返后仍是字符串；读取侧还有 Pydantic 校验兜底。测试中覆盖往返。
- **写入点遗漏**：除上表外如仍有 `write_json()` 写 `.yaml`，用测试遍历 Plan 目录下全部 `.yaml` 文件断言非 JSON 单行来兜底。
- **体积**：多行 YAML 略大于紧凑 JSON，文件很小，可忽略。
