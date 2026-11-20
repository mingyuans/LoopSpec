## 背景

文本报告中的多行引用块（`node instructions` 的指令、模板、Gate 模板，`memory show` 的正文，`change status` 中的 state.md 与 memory core，`state add` 写入的行，`gate begin` 的说明，`change archive` 的审阅指引）只靠每行 4 空格缩进和说明段区分。没有显式结束标记：正文中的空行、原有缩进会让边界不清，模型也无法确认是否读全。用户看过样例后决定（2026-11-20）：加 begin/end 标记与行数，保留缩进。

## 用户场景

- MODEL 读 `node instructions`，看到 `--- begin instruction (9 lines) ---` … `--- end instruction ---`，明确知道指令从哪开始、到哪结束、共几行；写产物时按 TEMPLATE 块去掉 4 空格缩进。
- 正文里出现 `=== NEXT STEPS ===` 或 `--- end instruction ---` 等文字时，仍在缩进内，不会被当成报告结构。

## 范围

1. 所有多行引用块统一为：`--- begin <名称> (<N> lines) ---`、N 行每行缩进 4 空格的原文、`--- end <名称> ---`。N 为块内实际行数；空内容为 `(0 lines)`。
2. 覆盖：`node instructions`（instruction、template、Gate pass/fail 模板）、`memory show`、`state add`、`gate begin`、`change archive` 第一段、`change status`（change/plan state.md、memory core）。
3. 各节说明段、`text_format` 契约、AGENTS.md、cli-reference（zh/en）、skill（如提及缩进）同步。

## 非目标

- 不改 JSON 输出；不去掉缩进；不改单行字段的处理方式。

## 验收条件

- [ ] 上述每个命令的文本输出中，每个引用块都以 begin 行开始、以同名 end 行结束，begin 行中的行数等于两者之间的行数，且这些行全部以 4 空格开头。
- [ ] 正文中包含 `--- end <名称> ---`、`=== X ===` 等文字时，它们只以缩进形式出现，不提前结束块、不产生顶格行（注入测试）。
- [ ] `change status` 的 state 与 memory core 采用同样格式；文件缺失/不可读时仍为单行说明。
- [ ] `--json` 输出不变；全部测试与 `make test-llm` 通过。

## 风险

- `change status` 文本格式变化，依赖旧格式的测试需更新；模型侧由 LLM E2E 验证。
