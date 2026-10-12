# 需求记录

需求背景、跨 Plan 的决策与更替原因。
人与 LLM 可直接编辑；`loopspec change status` 原样输出全文，引擎不解析。

## 背景

<!-- 用户原始诉求、要解决的问题、现状与触发原因。由 new skill 在创建 Plan 前填写。 -->

用户反馈 loopspec CLI 没有 update 功能。现状：升级 CLI 只能重新执行 `curl … install.sh | sh`，CLI 本身没有升级入口；`loopspec registry update` 管的是外部 Fragment registry，与升级 CLI 无关。

## 目标 / 非目标

<!-- 本需求的范围边界，明确不做的事。 -->

目标：
- 新增 `loopspec update` 命令，完成 CLI 自升级：从 GitHub Release 解析最新版本（或 `--version` 指定），下载 wheel，按 `checksums.txt` 精确匹配并校验 SHA256 后，用 `uv tool install --force`（无 uv 时用 `pipx install --force`）安装。
- `--check` 只检查不安装；`--json` 输出机器可读结果；已是最新版本时不重装。
- 安全：版本号经与 install.sh 相同的正则校验后才进入 URL/文件名；只允许 https（含重定向）；下载有大小与超时限制；子进程以参数列表调用，不经 shell；不提供跳过校验的开关。
- 新增错误码并同步中英文 cli-reference、README。

非目标：
- 不做项目内 Skill/命令/hook/内置资源的刷新（仍用 `loopspec init --tools ...`）。
- 不做 `self-update` 等别名命令。
- 不改 install.sh 行为。

## 关键决策

<!-- 每条一行：- YYYY-MM-DD（确认人）：决策内容；理由。
只追加；推翻旧决策时新增一条并注明取代哪条。 -->

- 2026-10-12（用户）：命令名只用 `loopspec update`，语义为 CLI 自升级，不做项目刷新；理由：用户明确要求。
- 2026-10-12（用户）：通过 LoopSpec 流程（loopspec new）推进本需求。

## 参考

<!-- 相关 issue / PR / 已归档 Change。 -->

- install.sh（版本解析与校验逻辑的参照）
- archive/2026-07/add-release-automation

## Plan 记录

<!-- 引擎在此之后追加 Plan 归档事件；LLM 可在事件行下补充更替原因。 -->
