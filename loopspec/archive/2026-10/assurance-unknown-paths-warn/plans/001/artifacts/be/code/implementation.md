## 完成的任务

本 Plan 没有 design/tasks 节点，按 proposal 的范围 1–6 实现：

1. **模型**：`AssuranceRules.unknown_paths` 改为 `Literal["fail", "warn"]`，默认 `fail`。
2. **合并**：`assurance_rules()` 逐个读取规则文件，任一文件为 `fail` 就取 `fail`，全部为 `warn` 才取 `warn`；合并结果带上 `unknown_paths`，修复了字段丢失。
3. **判定**：`diagnose()` 在 `warn` 模式下不把 `unknown_paths` 计入失败条件，并在 `warnings` 中加入 `unknownPaths`（最多 20 条，复用 `MAX_IGNORED_WARNINGS`）和 `unknownTotal`，与已有的 `ignoredPaths` 合并在同一个对象里。`fail` 模式行为不变。
4. **报告**：`warning_text()` 改为按 `WARNING_KINDS` 依次输出"被忽略路径"和"未匹配规则路径"两类告警，共用 `MAX_WARNING_CHARS = 8000` 的预算，被忽略路径优先；系统报告改用 `diagnostics["warnings"]` 生成摘要。
5. **文档**：中英文 `configuration.md` 的 `unknown_paths` 行写明两种取值、告警位置与合并规则；`cli-reference.md` 的 `gate record` 段落补充未匹配路径的告警。
6. **测试**：新增 9 个用例（合并参数化 4 个、非法取值、warn 通过、warn 下其他缺口仍失败、fail 无告警、上限 20 条、两类长告警的长度上限）。

## 改动文件

- 引擎：
  - `src/loopspec/workflow_models.py`：`unknown_paths` 的取值范围
  - `src/loopspec/workflow_planning.py`：合并时保留 `unknown_paths`，任一 `fail` 即 `fail`
  - `src/loopspec/workflow_assurance.py`：warn 判定、`unknownPaths` 告警，以及两类告警共用预算的 `warning_text()`
- 测试：`tests/test_workflow_assurance.py`：fixture 增加 `unknown`、`project_unknown` 参数，新增用例
- 文档：`docs/{zh,en}/configuration.md`、`docs/{zh,en}/cli-reference.md`

## 执行的检查

- `uv run pytest tests/test_workflow_assurance.py tests/test_workflow_planning.py -q`：先红（8 failed），实现后 24 + 33 个全部通过
- `make test`：933 passed（6 分 10 秒）
- `make lint`：ruff 与 mypy 通过

## 与设计的偏差

- `warn` 模式下其他缺口仍判失败的用例，改用 `missing_fragments` 构造缺口：若用缺证据构造，assurance 节点会因为上游 Gate 未完成而处于 blocked，不会记录结论。
- 未匹配路径的告警只出现在 assurance 的诊断与报告里，与 proposal 的非目标一致：`gate begin/record` 和 `change status` 不做规则判定。

## 后续事项

- 本仓库与内置模板的 `rules.yaml` 仍为 `fail`；如需启用 `warn`，改上游 loopspec-fragments 仓库。
- 规则级 `severity`（控制 `missing_fragments` 的严重级别）未做。
