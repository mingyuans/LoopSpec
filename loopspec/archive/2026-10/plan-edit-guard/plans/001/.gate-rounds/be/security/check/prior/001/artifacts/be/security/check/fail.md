---
verdict: FAIL
summary: "hook 在超时、超大输入或异常时一律放行，LLM 可构造命令让判定超时/崩溃从而绕过保护；路径提取正则为二次复杂度，已实测 10 万字符命令 20 秒内无法完成"
---

# 安全审查：不通过

## 审查输入

- 轮次：`001.1:be/security/check:1`；基线 `ec77d652…`；scopeDigest `5a181e21…`；warnings：无。
- 路径：`src/loopspec/cli.py`、`src/loopspec/plan_guard.py`、`src/loopspec/scaffold.py` 及测试。

## 发现

威胁模型：被保护的对象正是调用工具的 LLM，它能完全控制 `tool_input`。hook 一旦超时（Claude Code 默认 60 秒）或非 2 退出码，工具调用照常执行，所以判定程序的任何失效都等于放行。

1. **[高] 二次复杂度导致超时放行**：`_PATH_IN_TOKEN = [^\s'"=(),;]*plan\.yaml` 在 `findall` 中对每个起点向右贪婪扫描再回溯，长度 n 的长 token 代价 O(n²)。实测：4000 字符 0.032 秒；`"a"*100000 + " plan.yaml"` 的 Bash 命令 20 秒未完成（faulthandler 栈停在 `_candidates`）。在真正的写命令前拼接长参数即可让 hook 超时，写操作被放行。
2. **[高] 超大输入直接放行**：`hook_output` 对超过 1 MiB 的 stdin 返回空（放行）。把 Bash 命令或 Write 内容填充到 1 MiB 以上即可绕过所有检查。
3. **[中] 异常一律放行**：CLI 入口捕获所有异常后放行。可由输入触发的异常包括：路径含 NUL 时 `glob`/`realpath` 抛 `ValueError`；`bash -c` 嵌套递归没有深度上限，可能触发 `RecursionError`。
4. **[低] FIFO 阻塞**：`_current_status` 用阻塞 `open()` 读取。受保护位置若是 FIFO，hook 会挂起直到超时，然后放行。

未发现问题的部分：deny 原因只含文件系统路径与 Change 名，不执行命令、不拼接 shell；`parse_yaml` 有深度、条目与别名限制；settings 合并不覆盖用户配置，拒绝符号链接；不读取环境变量或密钥。

## 修复方向

- 路径片段提取改为线性：先用 `str.find` 定位 `plan.yaml`，再从每个出现位置向左扩展到分隔字符，扩展不越过上一个匹配。
- 改为 fail closed：输入超限、JSON 之外的分析异常、嵌套超过深度上限时，只要原始输入包含 `plan.yaml` 就拒绝（给出通用原因）；与 `plan.yaml` 无关的调用仍然放行。
- `bash -c` 嵌套设深度上限（例如 8），超过时按上一条处理。
- 读取 plan.yaml 改为 `O_NONBLOCK` 打开，`fstat` 要求普通文件；非普通文件视为受保护。
- 补充回归测试：长命令在 1 秒内完成判定；超过 1 MiB 且含 `plan.yaml` 的输入被拒绝；NUL、深度嵌套、FIFO 被拒绝。
