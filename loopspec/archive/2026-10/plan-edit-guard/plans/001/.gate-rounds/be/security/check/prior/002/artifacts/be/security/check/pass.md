---
verdict: PASS
summary: "第 1 轮四项发现均已修复并实测：对抗性长命令、深层通配符在时间预算内被拒绝，超大输入、异常、深度嵌套、FIFO 都 fail closed；只读白名单中能写文件的选项已移除；未发现新的绕过"
---

# 安全审查：通过（第 2 轮）

## 审查输入

- 轮次：`001.1:be/security/check:2`；基线 `ec77d652…`；scopeDigest `9b4e50f4…`。
- 路径：`src/loopspec/cli.py`、`src/loopspec/plan_guard.py`、`src/loopspec/scaffold.py` 及测试。

## 第 1 轮发现的复核

1. **二次复杂度**：路径提取改为 `str.find` 加向左有界扩展。实测（`hook_output` 直接调用）：
   - 10 万个 `plan.yaml` 用 1.86 秒，结果为放行（都不指向受保护文件）；
   - 5 万个含空格的参数用 0.43 秒；
   - 1 MB 对抗性单 token 命令被 10 秒预算截断，结果为拒绝，不再放行。
2. **超大输入**：超过 64 MiB 直接拒绝；未超限的大输入按正常流程判定，有时间预算兜底。
3. **异常放行**：对 Edit、MultiEdit、Write、NotebookEdit、apply_patch、Bash，任何分析异常都拒绝；嵌套超过 8 层抛 `Undecidable` 并拒绝。有用例覆盖。
4. **FIFO**：改为 `O_NONBLOCK` 打开并检查 `fstat` 是否为普通文件，非普通文件视为受保护。有用例覆盖。

## 本轮新增审查

- **只读白名单**：会写文件或执行命令的选项不再算只读：`sed`（`w` 命令）、`less -o`、`yq -i/--inplace`、`git --output`、`rg --pre`。`sed 1wplan.yaml` 这种文件名紧贴在命令字母后的写法，按同目录下的 plan.yaml 判定。
- **通配符**：不含 `plan.yaml` 字样的通配符 token 也会展开检查。深层通配符 `cat /*/*/*/*/*/*/*/zz` 在 2 秒预算处被截断并拒绝。
- **时间预算**：SIGALRM 只在 CLI 主线程设置，退出前恢复原处理器。10 秒低于 Claude Code 默认的 60 秒 hook 超时。
- **settings 合并**：不读取环境变量与密钥；对符号链接、非普通文件、非法 JSON 都不写入；用临时文件加 `os.replace` 原子写入（新文件权限为 0600，不影响功能）。
- **输出**：deny 原因经 `json.dumps` 输出，不执行任何命令，也不拼进 shell。原因中的路径来自真实存在的 Change 目录。
- **依赖**：没有新增依赖。

## 已接受的残余风险（设计已记录）

- Bash 检测是启发式的：变量拼接路径、脚本文件内写入、`$'…'` 转义识别不了。由 `read_plan` 的 digest 校验兜底。
- Windows 没有 SIGALRM，因此没有时间预算保护。
- 正常但极长的命令可能因超出预算被拒，提示拆分即可，属于可接受的误拦。
