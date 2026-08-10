## 1. 渲染模块骨架

- [ ] 1.1 新建 `src/loopspec/status_report.py`，导出 `render_status_report(payload: dict) -> str`，模块文档字符串写明其契约：纯文本、不着色、不经 rich `Console`、输出字节与终端环境无关（D1）
- [ ] 1.2 在 `status_report.py` 中从 `presentation` 导入并复用 `sanitize()` 做控制字符消毒，不另写第二份实现（D1）
- [ ] 1.3 实现表格单元格转义辅助：在 `sanitize()` 之上再把 `|` 转义为 `\|`（**外部输入处理**：`outputPath` 来自 schema 作者、`existingOutputPaths` 来自文件系统，均不受 change 名的 kebab-case 约束）（D5）
- [ ] 1.4 定义渲染器已知的顶层字段名集合与节点字段名集合常量，并显式标注"有意省略"的字段（如 `schemaPath`、`artifactsDir` 视 Overview 设计而定）（D2）

## 2. 各节渲染

- [ ] 2.1 渲染 `# LoopSpec Status: <change>` 标题与 `## Overview` 节：schema 名、change 根绝对路径、`state.md` 是否存在、`isComplete`；artifact 根与 change 根不同时额外输出 artifact 根
- [ ] 2.2 渲染 `## Nodes` 四列表格（`Node`/`Status`/`Output`/`Notes`），行序沿用 payload 的 `nodes` 顺序；gate 节点的 `Output` 列输出 pass/fail 双相对路径
- [ ] 2.3 实现 `Notes` 列的互斥取值：`blocked` → 缺失依赖；有 `taskProgress` → `complete/total`；`failed`/`exhausted` → 指向 `## Gate Failures`；glob 节点 → 已匹配文件计数；否则留空（D4、D5）
- [ ] 2.4 渲染条件节 `## Gate Failures`：每个失败 gate 一个 `### <gate-id>` 子节，含 verdict、summary、`blockingIssues` 无序列表、`rollbacksUsed`/`maxRetries`、`resetClosure`（D6）
- [ ] 2.5 渲染条件节 `## Pending Rollback`：gate、closure、可原样执行的 `command`
- [ ] 2.6 渲染恒在节 `## Next Steps`：`nextSteps` 逐条有序列表；为空时输出占位行
- [ ] 2.7 校验节序恒定为 Overview → Nodes → Gate Failures → Pending Rollback → Next Steps，且三个恒在节在任何状态下都出现

## 3. CLI 接线

- [ ] 3.1 修改 `cli.status`：`as_json` 为真时维持 `json.dumps` 原路径，为假时改为 `typer.echo(render_status_report(result))`，不再走 `_emit` 的 `key: value` 分支；确认 `result` 的构造过程一字未改
- [ ] 3.2 修改 `cli._fail` 的非 JSON 分支，渲染 `# Error` + `error`/`message`/`fix` 三项 Markdown；`--json` 分支不动（D7，**此项对全部子命令生效**，需在提交说明中点明）
- [ ] 3.3 去掉 `policy.build_next_steps` 与 `cli` 中指向 `loopspec status` 的 `nextSteps` 文案里的 `--json`；确认指向 `loopspec instructions` 的文案仍保留 `--json`（D8）

## 4. Skill 模板同步

- [ ] 4.1 修改 `src/loopspec/skill_templates.py` 中三处 `loopspec status <change-name> --json`，去掉 `--json`（D9）
- [ ] 4.2 更新 `tests/test_skill_templates.py` 中相关断言，并新增一条断言：全部模板正文中不存在 `loopspec status ... --json`

## 5. 测试

- [ ] 5.1 `tests/test_status_report.py`：默认输出以 `# LoopSpec Status:` 开头、含三个恒在节、不含 Python 字面量文本
- [ ] 5.2 条件节测试：无失败 gate 时不出现 `## Gate Failures`/`## Pending Rollback`；有 `failed` gate 时两节均出现且顺序正确
- [ ] 5.3 表格测试：数据行数与节点数一致、行序与 `--json` 的 `nodes[*].id` 一致、`blocked` 行列出缺失依赖、`tracks` 行呈现 `3/12`、glob 行以计数呈现且不出现逐条路径、gate 行含双路径
- [ ] 5.4 **安全测试**：产物路径含 `|` 时单元格转义为 `\|` 且表格仍为四列；路径含控制字符（换行、`\x1b`）时被改写为 `\xNN` 且报告行结构完整
- [ ] 5.5 纯文本测试：输出不含 ANSI 转义；两种终端宽度下逐字节相同；设置与不设置 `NO_COLOR` 时逐字节相同
- [ ] 5.6 字段覆盖一致性测试：断言渲染器声明的字段集合与 `status` 实际 payload 的字段集合相等（顶层与节点各一），新增未处理字段时失败（D2）
- [ ] 5.7 **安全测试**：在 change 目录放入正文含自然语言指令的产物文件，断言报告中不出现该正文，只出现路径或计数（限制 prompt injection 面）
- [ ] 5.8 错误路径测试：`loopspec status nonexistent`（不带 `--json`）退出码为 1，输出为含 `error`/`message`/`fix` 三项的 Markdown；同一场景带 `--json` 时仍返回原 JSON 三字段
- [ ] 5.9 `nextSteps` 文案测试：`new` 与 `rollback` 的 `nextSteps` 中 `loopspec status` 不带 `--json`；`status` 指向 `instructions` 的文案仍带 `--json`
- [ ] 5.10 回归确认：`tests/test_cli.py` 现有全部 `--json` 断言无需修改即通过（JSON 契约未变）

## 6. 文档

- [ ] 6.1 更新 `docs/en/cli-reference.md` 与 `docs/zh/cli-reference.md` 的 `loopspec status` 章节：说明默认输出为 Markdown 报告并给出示例，`--json` 字段表保持不变
- [ ] 6.2 更新 `docs/en/agent-protocol.md` 与 `docs/zh/agent-protocol.md`：主循环表格中的 `loopspec status <change> --json` 改为默认形式，并说明报告各节与原字段的对应关系
- [ ] 6.3 更新 `README.md`、`docs/en/README.md`、`docs/zh/README.md`、`docs/*/overview.md`、`docs/*/schema-reference.md`、`docs/*/workflows/secure-spec-driven.md` 中的 `loopspec status` 示例
- [ ] 6.4 运行 `tests/test_docs_consistency.py`，确认 en/zh 双语的集合相等与示例块逐字节比对全部通过

## 7. 收尾

- [ ] 7.1 运行 `make lint` 与 `make test`，全部通过
- [ ] 7.2 人工执行 `loopspec status cli-status-markdown-output`，肉眼确认报告版式符合 `status-report` 规格
