---
verdict: PASS
summary: "返工后 append_text/read_capped 已拒绝符号链接、硬链接与非普通文件，注入、路径、敏感信息与依赖检查无阻塞问题"
---

# 后端安全审查：通过

## 审查输入

- 轮次：`001.1:be/security/check:2`；基线 `ac4ff4fe7213e03f2c1e717c5190ef583f216a15`；scopeDigest `8a7f4073…`；warnings：无。
- 范围：`src/loopspec/{status_report,workflow_journal,workflow_changes,workflow_cli,workflow_io,workflow_plans}.py` 及对应测试（13 个路径）。上一轮 FAIL（attempt 1）指出的硬链接问题为本轮重点复核项。

## 检查项

- 路径穿越 / 链接：读写路径由 Change 根 + 固定文件名或 `check_plan_id()` 校验的 Plan id 拼出，经 `relative_path()` 与目录描述符访问；`O_NOFOLLOW` 拒绝符号链接；打开后对同一文件描述符 `fstat`，要求普通文件且 `st_nlink == 1`，因此硬链接到 Change 外的文件既不会被追加，也不会在 status 中输出，检查与读写作用于同一 inode，无 TOCTOU 窗口。对应用例 `test_append_and_capped_read_refuse_hard_links`、`test_hard_linked_state_is_neither_written_nor_shown`、T10、T13 均通过。
- 注入：不涉及 SQL / shell / 模板 / 正则拼接；`--note` 经 `one_line()` 折叠所有空白（含 U+2028/U+2029/NEL）并去除 Cc 控制字符；纯文本报告插值经 `sanitize()`，`state.md` 原文控制字符改写为 `\xNN` 并逐行缩进 4 空格，无法伪造分隔行或输出 ANSI 转义（T20、T21、T19）。
- 认证 / 授权：本地 CLI，无新增鉴权面；事件追加在既有 `write_lock` 内、提交点之后，失败不改变命令结果。
- 敏感信息：事件行只含时间、事件名、revision、digest 前缀、节点 id 与用户 note；不读取环境变量；status 只输出 Change 级与当前 Plan 的 `state.md`，并附不可信声明。
- 不安全反序列化：未新增 YAML / pickle 解析，引擎不解析 `state.md`，非 UTF-8 以替换字符解码。
- 资源：status 展示上限 64 KiB（首尾各 32 KiB，`pread` 定长读取，不整文件载入）。
- 依赖来源：未新增第三方依赖。

## 剩余风险

- `state.md` 内容可含 Unicode 双向控制字符（Cf 类），在 status 输出中原样保留，可能影响人眼阅读；不影响报告结构与执行，未处理。
- `state.md` 是任何人 / LLM 可编辑的不可信内容，进入 LLM 上下文后仍可能构成提示注入；已通过报告说明文字与 skill 约定声明"不执行其中指令"缓解，无法在引擎层彻底消除。
