---
verdict: PASS
summary: "“能检测到就禁，检测不了就放行”在代码、测试、中英文文档、实现报告与 state.md 中表述一致；判定逻辑仍集中在纯函数中，验收条件均有用例覆盖"
---

# 后端代码审查：通过（第 2 轮）

## 审查输入

- 轮次：`001.1:be/review/check:2`；基线 `ec77d652…`；scopeDigest `a905a048…`。
- 路径：`src/loopspec/cli.py`、`src/loopspec/plan_guard.py`、`src/loopspec/scaffold.py`、`tests/test_hook_settings.py`、`tests/test_plan_guard.py`、`tests/test_workflow_cli.py`；另人工核对 `docs/{zh,en}/cli-reference.md`、实现报告与 Change 级 `state.md`。

## 结论

自第 1 轮 review 以来的改动只涉及失败处理，本轮重点审查这部分。

**`plan_guard.py`**
- 模块说明写明了新原则。
- `_current_status` 遇到 `Undecidable` 返回 `None`，按未确认处理。
- `hook_output` 在以下情况都返回空输出：超大输入、非 JSON、非受保护工具、分析异常、超时。
- `bash -c` 嵌套超过 `MAX_NESTING` 时只跳过更深的展开，命令其余部分照常检查，不会整条放行。
- 已无残留的拒绝原因常量。`Undecidable` 只在内部表示"检测不了"。

**测试**
- 原来的 fail closed 用例都已改为放行断言。
- 新增"超时放行且在 3 秒内返回"与"深层嵌套有界且仍能识别"。
- 能检测的写入用例保持不变，全部通过。

**文档一致性**
- zh/en `cli-reference.md` 已删除"无法读取或解析时视为受保护"。
- 新原则的表述与代码行为一致：64 MiB、10 秒、8 层、读取失败。
- `test_docs_consistency.py` 通过。

**记录**
- `state.md` 新增一条决策，并注明它取代 security 返工中的 fail closed 做法。
- 实现报告的"与设计的偏差"已同步。

**测试结果**：`make test` 1072 passed，`make lint` 通过（tests Gate 第 5 轮）。

## 非阻塞建议

- `design.md` 仍写着"无法读取 / 解析时 fail closed"，这是已完成节点的历史产物，偏差已记录在实现报告与 `state.md`，不再修改。
- 第 1 轮 review 的非阻塞建议仍然适用：`init` 写配置时遇到 OSError 会直接抛出；新建 settings 文件的权限为 0600。
