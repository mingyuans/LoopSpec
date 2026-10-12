---
verdict: PASS
summary: "并行 nextSteps 实现与设计一致，rollback / exhausted 优先级与单步行为保持不变，新增用例覆盖扇出、递减、回退、耗尽与非执行状态，未发现阻塞问题"
---

# 后端代码审查：通过

## 审查输入

- 轮次：`001.1:be/review/check:1`，基线 `1c5ce6ad00450d3639c64501523fd377492fbfc9`，scopeDigest `c78496c5…`，warnings 为空。
- 路径：`src/loopspec/{status_report,workflow_changes,workflow_runtime}.py`、`tests/{test_skill_templates,test_status_report,test_workflow_runtime}.py`。

## 审查要点

- **正确性**：`workflow_runtime.status` 只把 `next(...)` 改为列表推导，`entries` 按编译后的依赖顺序插入，输出稳定；同时 ready 的叶子之间不可能存在依赖（否则其一为 blocked），并行安全。`parallel = rollback is None and len(next_steps) > 1`，exhausted 时 `next_steps` 为空自然为 false。
- **边界**：证据过期而回到 ready 的代码 Gate 会和其他 ready 叶子一起列出，符合“重跑该 Gate”的语义；`change status` 在 unplanned / planning 由基础字典给出 `parallel: false`，complete 时显式置 false。
- **兼容性**：`nextSteps` 仍为字符串列表，单步时内容与提示语逐字不变（测试断言）；`change next` 的 `node` 计算未改，`nodes` / `parallel` 为纯增量字段。
- **报告契约**：`parallel` 加入 `TOP_KEYS`，由 NEXT STEPS 提示体现，满足“每个 payload 字段要么渲染要么显式忽略”的约束；新提示保持 80 列内、无 Markdown、为常量。
- **错误处理 / 数据访问**：无新增 I/O、异常路径或锁行为。
- **测试覆盖**：扇出逐步完成、线性单步、rollback 与 exhausted 覆盖并行、`change next` 的 `nodes`、非执行状态、文本报告并行 / 单步提示、skill 文案均有用例；全量 1079 passed，ruff 与 mypy 通过。
- **可维护性**：`next_step` 中 `nodes` 的选取顺序有注释说明与 `nextSteps` 对应。

## 剩余风险

- 存在 exhausted Gate 且其前面还有 ready 叶子时，`change next` 的 `node`（沿用旧逻辑，取第一个 ready/exhausted）可能与 `nodes[0]`（exhausted Gate）不同；这是为保持 `node` 旧语义的取舍，不阻塞。
- `tests/test_status_report.py` 从 `tests/test_workflow_runtime.py` 导入扇出夹具，与仓库已有的跨测试导入方式一致。
