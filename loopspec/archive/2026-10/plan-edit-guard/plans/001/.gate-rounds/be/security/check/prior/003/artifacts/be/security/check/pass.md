---
verdict: PASS
summary: "按用户确认的“能检测到就禁，检测不了就放行”原则复审：可检测的写入均被拒绝，扫描线性、10 秒预算内必有结果；超时/异常/超长放行属用户接受的残余风险，由 digest 校验兜底；未发现其他问题"
---

# 安全审查：通过（第 3 轮）

## 审查输入

- 轮次：`001.1:be/security/check:3`；基线 `ec77d652…`；scopeDigest `a905a048…`。
- 路径：`src/loopspec/cli.py`、`src/loopspec/plan_guard.py`、`src/loopspec/scaffold.py` 及测试。

## 背景

第 1 轮 FAIL 指出：hook 超时或崩溃时调用会被放行，可以借此绕过保护。第 2 轮改成 fail closed 后通过。之后用户明确决定（2026-10-11，记录在 Change 级 `state.md`）：**能检测到就禁，检测不了（超长、超时、异常等）就放行，不影响正常 tool 调用**。本轮按这个原则复审。

## 复核

- **能检测的写入都拒绝**：
  - 编辑类工具、`apply_patch`、Bash 的拒绝用例全部通过；
  - 30 万字符命令中的写入在 2 秒内被拒；
  - 深层 `bash -c` 嵌套在较浅层级就被识别出来；
  - 通配符写入、`p'l'an.yaml` 拆开引号、`sed 1wplan.yaml`、`yq -i`、`git --output`、`rg --pre` 都被拒。
- **检测不了就放行，且有上限**：
  - 路径扫描是线性的；
  - SIGALRM 10 秒预算低于 Claude Code 默认的 60 秒 hook 超时，hook 不会拖到宿主超时；
  - 实测深层通配符 `cat /*/*/*/*/*/*/*/zz` 在 2 秒预算处放行；
  - 非法 JSON、`tool_input` 类型不对时静默放行；
  - FIFO 改为非阻塞读取后放行。
- **没有引入新的风险面**：
  - 不执行任何命令，不把输入拼进 shell；
  - `parse_yaml` 有深度、条目与别名限制；
  - settings 只合并、不覆盖，不写符号链接与非法 JSON，原子写入；
  - 不读取环境变量或密钥，没有新增依赖。

## 用户接受的残余风险

- LLM 可以构造超长、超时或触发异常的输入来绕过检测。这类写入发生后，`read_plan` 的 digest 校验会在读取时发现 spec 被篡改并报 `plan_integrity`。但同时改写 digest 或 status 的篡改，只能靠 hook 拦截。
- Bash 检测仍是启发式：变量拼接路径、脚本文件内写入、`$'…'` 转义都识别不了。
- Windows 上没有 SIGALRM 预算，极端输入可能拖到宿主超时，结果同样是放行。
