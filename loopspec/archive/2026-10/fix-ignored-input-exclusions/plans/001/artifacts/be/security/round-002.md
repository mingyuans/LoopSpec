---
verdict: PASS
summary: "返工后复审：告警文本加长度上限，消除了长路径让系统 FAIL 报告不可解析的可用性问题；其余检查项结论不变，无阻塞问题"
---

# 后端安全审查：通过

## 审查输入
- 轮次 `001.1:be/security/check:2`，基线 `7531fb87`，scopeDigest `d13d0a8f2246…`，9 个文件（与 tests 第 2 轮同一输入）
- 相比第 1 轮的变化：`warning_text()` 增加 `MAX_WARNING_CHARS = 8000` 上限；cache 路径写法简化；新增 1 个回归测试
- 本轮 `warnings` 为空

## 检查项
- **注入**：`excluded_paths` 只交给 `fnmatch.fnmatchcase` 做内存匹配，不拼接进 shell、git 参数或 SQL；git 调用参数仍是固定列表，没有新增外部输入。
- **路径穿越 / 输入校验**：每个模式经过 `relative_path(pattern, glob=True)`，拒绝空值、以 `/` 开头、反斜杠、控制字符和 `.`/`..` 分量；最多 128 项。被忽略路径的解码沿用 `_decode_path`（严格 UTF-8 加安全相对路径校验）。`<home>/.cache` 的位置由 `relative_to(repository)` 计算，home 不在仓库内时不排除任何路径。
- **认证 / 授权与门禁完整性**：
  - 当前 Change 的控制路径排除逻辑不变；告警不进入 `diff_digest` 和 `scope_digest`，不会让伪造的文件影响证据绑定。
  - 报告仍由系统写入，`report_hash` 绑定方式不变。
  - `FailureReport` 的严格解析没有放宽：告警只追加到 `summary`。
- **敏感信息**：告警只包含路径名，不读取也不输出文件内容。被忽略的文件名（例如 `.env`）会出现在命令输出和 assurance 报告里，但只有文件名，没有值。
- **资源消耗与可用性**：容器目录判定用祖先路径集合，复杂度与 git 输出条数线性相关，记录数仍受 `_records` 的 4096 上限约束；告警列表上限 20 条。告警文本总长度不超过 8000 字符，所以仓库里出现超长的被忽略路径时，系统 FAIL 报告也不会超过 `FailureReport` 的长度限制，不会让 status、rollback 失效。
- **不安全反序列化 / 依赖来源**：没有新增依赖，也没有新的反序列化入口；配置仍由 pydantic 严格模型校验。

## 剩余风险
- **门禁边界放宽（人已确认）**：`excluded_paths` 不限制取值，可以把 `src/**` 这类业务代码排除在所有 Gate 之外；`ignored_input` 降级为告警后，被忽略的本地文件不再阻断流程。缓解措施是 `config.yaml` 和 `.gitignore` 的修改都在 PR 中，由人工 review 把关，未声明的被忽略路径会写进报告。
- **本仓库配置 `'*.md'`（人已确认）**：会把 `builtin/**` 下发布出去的 skill 与 Fragment 指令排除在门禁之外。
- **文件名外泄**：被忽略的文件名会出现在报告中。如果项目把敏感信息编码进文件名，需要把这些路径加入 `excluded_paths`。
