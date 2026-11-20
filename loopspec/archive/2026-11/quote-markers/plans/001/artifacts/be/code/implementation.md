## 完成的任务

- 1.1 `text_format.quote_block(label, content, detail="", end=None)`：输出 `--- begin <label> (N lines[, detail]) ---`、N 行 4 空格缩进的原文、`--- end <end or label> ---`；空内容为 `(0 lines)`；label 经 `sanitize`。
- 1.2 text_reports：`node instructions` 的 instruction、template、pass/fail template；`memory show` 的 content（替代原 `--- content ---` 与 `(empty)`）；`state add` 的 line；`gate begin` 的 instruction；`change archive` 第一段的 instructions。对应说明段改为「between the begin and end lines …；写产物时去掉缩进与 begin/end 行」。
- 1.3 `status_report`：change/plan state.md 改为 `--- begin <title>: <path> (N lines[, truncated…]) ---` … `--- end <title> ---`，缺失/不可读仍为单行标题；memory core 为 `--- begin core: memory/core.md (N lines) ---` … `--- end core ---`；PROMPT_STATE 与模块说明同步。
- 2.1 测试：`tests/test_text_reports.py` 新增 `quoted_blocks()` 校验器与两项测试（所有样本及 poison 后的样本中 begin/end 同名配对、行数一致、块内全部缩进、没有孤立的 end 行；正文中的 `--- end content ---` 不会提前结束块），注入串加入伪造的 end 行；`tests/test_status_report.py` 更新 3 处断言并新增 state/core 块配对测试；BDD `text_output.feature` 步骤改为校验 begin/end 与行数。
- 2.2 文档：AGENTS.md 文本契约、`docs/{zh,en}/cli-reference.md`（约定段与 change status）、`agent-protocol.md`、`release-notes.md`；skill `new.md`、`continue.md` 说明 begin/end 行（副本经 `uv run loopspec` 同步）。

## 改动文件

- 代码：`src/loopspec/text_format.py`、`src/loopspec/status_report.py`、`src/loopspec/text_reports/{common,node,memory,gate,change}.py`
- 测试：`tests/test_text_reports.py`、`tests/test_status_report.py`、`tests/steps/text_output_steps.py`、`tests/features/text_output.feature`
- skill：`builtin/skills/{new,continue}.md` 及同步副本
- 文档：`AGENTS.md`、`docs/{zh,en}/{cli-reference,agent-protocol,release-notes}.md`

## 执行的检查

- `uv run ruff check src tests hatch_version.py`：All checks passed!
- `uv run mypy src hatch_version.py`：Success: no issues found in 51 source files
- `uv run pytest -q -n 2 -m "not timing and not llm"`：首轮 1 failed（BDD 步骤仍按旧格式解析），修正后在测试关卡重跑。

## 与设计的偏差

- 无实质偏差。end 行对 status 的 state 块使用标题（不含路径），与设计一致。

## 后续事项

- PR #20（fragment-dir）基于本分支旧提交，本次合入后需要把新提交合进 #20 并解决 `node.py` 中 PROMPT_INSTRUCTION 的冲突。
