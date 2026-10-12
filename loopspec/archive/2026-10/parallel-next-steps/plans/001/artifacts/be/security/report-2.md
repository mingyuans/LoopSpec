---
verdict: PASS
summary: "返工后的 node instructions 按需加锁不放宽任何写入保护：无待归档时只读，有待归档时仍在写锁内补完并做完整性校验；其余改动与上一轮一致，未发现安全问题"
---

# 后端安全审查：通过

## 审查输入

- 轮次：`001.1:be/security/check:2`，基线 `1c5ce6ad00450d3639c64501523fd377492fbfc9`，scopeDigest `dcd579f0…`，warnings 为空。
- 路径：`src/loopspec/{status_report,workflow_changes,workflow_cli,workflow_runtime}.py` 及四份测试文件。

## 检查项

- **并发与一致性（本轮重点，`workflow_cli.node_instructions`）**：
  - 无待归档记录时不加锁，只读执行 `instructions()`（已确认 `workflow_runtime.instructions/status` 不写文件）。所有写命令都只有一次生效写入，`status()` 会把待归档的源文件排除在产物之外，所以无锁读取不会看到半成品状态。
  - check-then-act 竞态：检查之后若另一命令提交了 rollback 记录，本次读取最多给出旧的 ready 状态；agent 随后写产物时本来就不持锁（旧实现的锁也在返回前释放），下一条命令仍会补完归档。与旧实现相比没有新增风险。
  - 有待归档记录时仍在写锁内执行 `settled()`，保留“先补完返工归档再写新产物”的保障；篡改归档目标、越界 record 仍报 `history_integrity`（已有用例通过）。
  - 写锁仍为 `LOCK_NB` 快速失败，没有新增阻塞等待，也就不会引入死锁或被长期占用的问题。
- **注入**：`nextSteps` 由已校验的 change 名与编译后的节点 id 拼接，只作为文本返回；报告经 `sanitize` 输出，新增提示为常量。
- **认证 / 授权**：不涉及；没有放宽 ready 校验、Gate 证据、rollback 优先级或人工确认。
- **路径穿越**：没有新增路径拼接；`pending_sources` 复用既有的 record 解析与 `exists` 安全读取。
- **敏感信息 / 反序列化 / 依赖**：无新增。

## 剩余风险

- 并行 sub agent 只做自己节点的约束依赖 skill 文案，不是强制校验（不阻塞）。
