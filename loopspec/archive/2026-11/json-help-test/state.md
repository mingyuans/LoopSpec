# 需求记录

跨 Plan 的背景、边界、重要决策与待解决问题；引擎在末尾追加 Plan 记录。
优先用 `loopspec state add` 追加；`loopspec change status` 原样输出全文，引擎不解析内容。

## 背景

<!-- 问题来源、现状与触发原因。用 `loopspec state add --section background` 追加。 -->
- 2026-11-20 main 上 Release 工作流在 #19、#21 合并后失败：tests/test_text_reports.py::test_every_rendered_command_takes_json 通过 --help 文本查找 --json，CI 中 rich 帮助输出带 ANSI 颜色码，把 --json 拆成 '-' 与 '-json'，断言失败；本地终端无颜色故通过。阻塞发布新版本。

## 目标与边界

<!-- 预期结果、范围与明确不做的事。用 `loopspec state add --section goals` 追加。 -->
- 2026-11-20 改为直接检查 click 命令对象的参数（是否有 --json 选项），不依赖帮助文本渲染；让 main 的 CI 通过以便发版。不改产品代码。

## 决策

<!-- 重要取舍与确认：`- YYYY-MM-DD [HUMAN: 用户] 内容` 或 `- YYYY-MM-DD [MODEL: BE] 内容`。主体是实际作出决策的人或 Agent 角色，不是代写者。用 `loopspec state add --section decision` 追加。 -->
- 2026-11-20 [HUMAN: 用户（Desk 卡片）] 确认执行 Plan 001；修复合入后发布 v1.3.0（次版本号，因包含默认文本输出的破坏性变更）。

## 待解决问题

<!-- 跨 Plan 仍需追踪的问题；解决或移交时追加新条目并引用原问题。用 `loopspec state add --section open-question --scope change` 追加。 -->

## 参考

<!-- 相关 issue / PR / 讨论 / 产物入口及用途。用 `loopspec state add --section reference` 追加。 -->
- 2026-11-20 用户 2026-11-20：loopspec 发布新版本。CI 失败日志：Release run on 0b7f9c8，1 failed, 1767 passed。

## Plan 记录

<!-- 引擎自动追加 Plan 沿革，请勿手工编辑，也勿在此段之后新增段落。 -->
- 2026-11-20T17:15:12+00:00 · Change json-help-test 归档前 memory 审阅 · 结论：updated · 变化的 topic：dev-environment · 备注：dev-environment 增加：测试勿在 rich 帮助文本中查找选项，CI 有 ANSI 颜色；本地用 FORCE_COLOR=1 复现。
