---
verdict: FAIL
summary: "append_text/read_capped 只防符号链接不防硬链接：state.md 被硬链接到 Change 目录外文件时，事件会写入外部文件，change status 会把外部文件内容输出到 LLM 上下文"
---

# 后端安全审查：失败

## 阻塞问题

- `src/loopspec/workflow_io.py` `append_text()`：以 `O_APPEND` 原地追加，`O_NOFOLLOW` 只拦截符号链接，未检查 `st_nlink`。若 `state.md` 是指向 Change 目录外（同一文件系统）文件的硬链接，`plan create/approve/rollback/archive` 会把事件行写进该外部文件。原有 `atomic_write()` 以临时文件 + `os.replace` 写入，会断开硬链接，因此这是新增的越界写入路径。修复后需补测试：硬链接的 `state.md` 不被写入，命令返回 `warnings`。
- `src/loopspec/workflow_io.py` `read_capped()`：同样未检查 `st_nlink`。`state.md` 为硬链接时，`change status` 会把外部文件（例如同用户的其他敏感文件）内容原样输出到 JSON 与纯文本报告，进入 LLM 上下文。修复后需补测试：硬链接的 `state.md` 在 status 中为 `content: null, error: "unreadable"`，且输出不含外部文件内容。

## 审查输入

- 轮次：`001.1:be/security/check:1`；基线 `ac4ff4fe7213e03f2c1e717c5190ef583f216a15`；scopeDigest `928275bc…`；warnings：无。
- 范围：`src/loopspec/{status_report,workflow_journal,workflow_changes,workflow_cli,workflow_io,workflow_plans}.py` 及对应测试（13 个路径）。

其余检查项结论（不阻塞）：

- 注入：不涉及 SQL / shell / 模板；`--note` 经 `one_line()` 折叠空白（含 U+2028/U+2029/NEL）并去除 Cc 控制字符；纯文本报告插值经 `sanitize()`，`state.md` 原文控制字符改写并逐行缩进，无法伪造分隔行或输出 ANSI 转义。
- 认证 / 授权：本地 CLI，无新增鉴权面；事件追加均在既有 `write_lock` 内、提交点之后。
- 路径穿越：读写路径由 Change 根 + 固定文件名或 `check_plan_id()` 校验的 Plan id 拼出，经 `relative_path()` 与目录描述符访问，符号链接被拒绝（硬链接见上）。
- 敏感信息：事件行只含时间、事件名、revision、digest 前缀、节点 id 与用户 note；不读取环境变量。
- 反序列化：未新增 YAML / pickle 解析；引擎不解析 `state.md`。
- 依赖来源：未新增第三方依赖。

## 建议修复方向

- 在 `append_text()` 与 `read_capped()` 打开文件后、读写前检查 `fstat().st_nlink == 1`，否则抛 `unsafe_path`；调用方已按"写失败返回 warnings / 读失败返回 unreadable"处理，无需改动上层。
