---
verdict: PASS
summary: "代码审查返工引入的 held 字段、来源变化时清空基线与全量预览校验未引入新的安全问题；第 1 轮的三项阻塞修复保持有效"
---

# 后端安全审查：通过

## 审查输入
- 轮次 `001.1:be/security/check:3`，基线 `9b90c66c11bab432176d640cfc6caad760706fcc`，固定路径 16 个。
- 上一轮（`security/check:2`）由独立子代理复审并 PASS。本轮相对那一版的代码差异只在 `src/loopspec/registry_sync.py`（`RegistryLock.held`、`update` 中的 behind 判断、`_build_plan` 在来源变化时令 `base = {}`、`_definition_error` / `_definitions_in` / `_validate_preview` 重写）和 `tests/test_registry_sync.py`。本轮由主代理逐行审查这部分差异，其余代码沿用上一轮的结论。

## 检查项
- **注入**：没有新增子进程调用，也没有新的外部值进入参数。
- **路径穿越 / 符号链接**：
  - `_definitions_in` 只接受 kebab 名称；`is_file()` 只用来决定是否校验，实际读取都经 `WorkflowCatalog` 的 dir-fd 与 O_NOFOLLOW 安全读取，并有限额。
  - 预览树的复制与写入都在缓存目录内（`_remove` 会拒绝符号链接），并且现在出错时也会清理。
  - 写入范围不变：只有 apply 中经确认的条目。
- **敏感信息与回显**：新增的错误消息只包含经正则过滤的定义键与既有错误消息，不回显文件内容或不合法的名称。
- **锁篡改**：`held` 的键经 `DEFINITION_RE` 校验，只作为「需要重新比对」的条件，不会触发写入；来源变化时不再使用旧锁的哈希，消除了「伪造或过期的基线导致确认后批量删除」的路径，比之前更安全。
- **资源耗尽**：每个定义各用一个 `WorkflowCatalog`，受单文件与累计限额约束；本地定义数量由用户自己控制，最多造成拒绝服务。
- **反序列化与依赖**：没有变化。

## 剩余风险
沿用 `security/check:2` 中的非阻塞建议，至今未处理：
- skill 的内容 diff 应覆盖全部待确认文件，包括 `fragment.yaml` 引用的任意文件名。
- `redact` 应过滤 Unicode 格式字符（Cf 类别）。
- `run_git` 应显式关闭管道并 join 写线程。
- 本地预览校验会逐个加载全部定义，定义很多时 apply 会变慢。
