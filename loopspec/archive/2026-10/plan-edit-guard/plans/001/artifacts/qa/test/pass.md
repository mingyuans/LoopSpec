---
verdict: PASS
summary: "（按“能检测到就禁，检测不了就放行”复测）在临时 Git 项目中用真实 CLI 端到端验证：init 写入并幂等合并 Claude/Codex hook 配置，approved Plan 的 Write/Bash/apply_patch 被拒，读取与其他文件放行，伪造确认被拒，CLI 归档不受影响，非法配置被跳过；超大输入与深层通配符放行且不阻塞"
---

# 集成验收测试：通过

## 环境

- 临时目录：会话 scratchpad 下的 `qa/`，其中新建 Git 仓库，`CODEX_HOME` 指向该目录内，不触碰用户的 `~/.codex`。
- 用 `uv run --project <本仓库> loopspec` 执行真实 CLI；`hook pre-tool-use` 通过管道输入模拟 Claude Code / Codex 的 hook JSON。
- 脚本：`scratchpad/qa.sh`（bash）。

## 用例与结果

| # | 步骤 | 预期 | 实际 |
| --- | --- | --- | --- |
| 1 | `loopspec init loopspec --tools claude,codex --json` | `hooks.claude`、`hooks.codex` 均为 created | 两者都是 created；matcher 分别为 `Edit\|MultiEdit\|Write\|NotebookEdit\|Bash` 和 `^apply_patch$\|^Bash$`，command 为 `loopspec hook pre-tool-use` |
| 2 | 再次 init | 两者均为 unchanged | 均为 unchanged，配置里没有重复条目 |
| 3 | draft Plan：Edit plan.yaml | 放行 | 无输出，exit 0 |
| 4 | draft Plan：Edit 把 `status: draft` 改为 `status: approved` | 拒绝（伪造确认） | deny，原因为 "writing an approved plan.yaml by hand…" |
| 5 | `plan approve` 之后 Write plan.yaml（绝对路径） | 拒绝 | deny，原因包含路径与修订、归档的指引 |
| 6 | approved：Bash `sed -i "" s/a/b/ <plan.yaml>` | 拒绝 | deny |
| 7 | approved：Bash `cat <plan.yaml>` | 放行 | 无输出，exit 0 |
| 8 | approved：Codex `apply_patch` 的 Update File 指向 plan.yaml | 拒绝 | deny |
| 9 | approved：Edit `plans/request.yaml` | 放行 | 无输出，exit 0 |
| 10 | Read 工具 | 放行 | 无输出，exit 0 |
| 11 | stdin 为 `not json` | 放行 | 无输出，exit 0 |
| 12 | CLI `plan archive -c qa-demo -p 001` | 不受 hook 影响 | 返回 archived |
| 13 | archived Plan：Edit plan.yaml | 放行 | 无输出，exit 0 |
| 14 | `.claude/settings.json` 写成非法 JSON 后再 init | skipped，文件不变 | `skipped`（not valid JSON），内容仍为 `{bad` |

| 15 | 新建并确认 Plan 002 后，Bash `echo x > <002 plan.yaml>` | 拒绝 | deny |
| 16 | hook stdin 超过 64 MiB（65 MiB 的 Bash 命令） | 放行 | 无输出，exit 0 |
| 17 | Bash `cat /*/*/*/*/*/*/zz`（深层通配符） | 放行，且在 10 秒预算内返回 | 无输出，exit 0，含 uv 启动共耗时 7 秒 |

用例 15–17 在“能检测到就禁，检测不了就放行”改动后复测时加入；用例 1–14 在同一轮复测中重新执行，结果与上一轮相同。

以上所有用例的退出码都是 0，拒绝通过 stdout 的 `permissionDecision: deny` 表达，符合 Claude Code 与 Codex 的 hook 协议。

## 未覆盖

- 没有在真实的 Claude Code / Codex 会话中触发 hook，本次用管道模拟输入。协议字段依据官方文档，单元与集成用例已覆盖。
- Codex 需要用户在 `/hooks` 中信任 hook 后才会运行，这一步无法自动化验证。
