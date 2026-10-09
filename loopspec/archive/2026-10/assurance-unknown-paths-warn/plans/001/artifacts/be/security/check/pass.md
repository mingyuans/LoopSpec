---
verdict: PASS
summary: "未发现阻塞问题；warn 只能由规则文件显式开启，多份规则任一 fail 即 fail，报告长度有上限"
---

# 后端安全审查：通过

## 审查输入
- 轮次 `001.1:be/security/check:1`，基线 `cd74011`，scopeDigest `8c65eff49a9b…`，4 个文件（与 tests 轮次同一输入）
- 本轮 `warnings` 为空

## 检查项
- **注入 / 输入校验**：`unknown_paths` 由 pydantic 严格模型限定为 `fail` 或 `warn`，其他值读取失败；没有新增外部输入，也没有 shell、git 或 SQL 拼接。
- **门禁完整性 / 授权**：
  - 默认值仍为 `fail`；
  - 合并时任一规则文件为 `fail` 即取 `fail`，所以 Fragment 自带的规则不能放宽项目规则；
  - `missing_evidence`、`stale_evidence`、`missing_fragments` 仍计入失败；
  - 报告仍由系统写入，证据绑定（plan digest、diff digest、report hash）没有变化。
- **可用性**：两类告警共用 8000 字符预算，FAIL 报告不会超过 `FailureReport` 的 16384 字符限制而导致 status 和 rollback 不可用，已有测试覆盖。
- **敏感信息**：告警只包含路径名，不含文件内容。
- **依赖来源 / 反序列化**：没有新增依赖或反序列化入口。

## 剩余风险
- 规则文件设为 `warn` 后，不匹配任何规则的业务代码不再阻断 assurance，只靠报告中的告警和人工 review。这是人已确认的能力；默认值与内置模板均为 `fail`。
