## 背景与现状

`text_format.quote(content)` 返回逐行 4 空格缩进的列表；调用方各自在前面加 `--- xxx ---` 标题或字段名。`status_report` 通过别名 `_quote` 复用。

## 目标 / 非目标

目标：统一的有界引用块。非目标：JSON、单行字段、去缩进。

## 方案

- `text_format.quote_block(label, content, detail="") -> list[str]`：
  - `body = quote(content)` if content else `[]`（空内容 0 行）；
  - 返回 `[f"--- begin {sanitize(label)} ({len(body)} lines{', ' + detail if detail else ''}) ---", *body, f"--- end {sanitize(label)} ---"]`。
  - `label` 只用常量或已校验 id/路径；仍经 `sanitize`。
- 替换调用点：
  - `node.py`：`quote_block("instruction", …)`、`quote_block("template", …)`、`quote_block("pass template"/"fail template", …)`。
  - `memory.py`：`quote_block("content", …)`（替换原 `--- content ---` 与 `(empty)`）。
  - `gate.py`：`state add` 的 `quote_block("line", …)`；`gate begin` 的 `quote_block("instruction", …)`。
  - `change.py`：归档指引 `quote_block("instructions", …)`。
  - `status_report.py`：state 块标题改为 `quote_block(f"{title}: {path}", content, detail)`（`detail` 为 truncated 提示）；缺失/不可读仍为单行 `--- {title}: {path} (missing|unreadable) ---`；memory core 为 `quote_block("core: memory/core.md", …)`。为保持 end 行简短，end 行使用 `label` 的冒号前部分（`end change`、`end plan 001 (...)`、`end core`）—— 实现为 `quote_block(label, content, detail, end=短名)`。
- 说明段：`PROMPT_INSTRUCTION`、`PROMPT_TEMPLATE`、`PROMPT_GATE_TEMPLATES`、memory/state 等提到缩进的地方改为「between the begin and end lines, every line indented by four spaces」。`PROMPT_STATE`（status）同步。

## 归属与路径

BE：`src/loopspec/text_format.py`、`src/loopspec/text_reports/{node,memory,gate,change}.py`、`src/loopspec/status_report.py`、`tests/**`、`docs/**`、`AGENTS.md`。

## 安全边界

块内每行仍缩进，伪造的 `--- end … ---` 只能以缩进形式出现；begin/end 行只由 CLI 生成。注入测试扩展：正文中写入 `--- end instruction ---` 后，顶格的 end 行仍只有一个且位于块末。

## 验证方案

- `tests/test_text_reports.py` 新增：对所有样本输出解析 begin/end 对，校验同名配对、行数一致、块内全部缩进；对 poison 后的 payload 同样成立。
- `tests/test_status_report.py` 更新 state/core 断言并加配对校验。
- `make test-llm`。

## 风险与取舍

- 标记行与缩进双保险，输出略长；可读性收益更大。
