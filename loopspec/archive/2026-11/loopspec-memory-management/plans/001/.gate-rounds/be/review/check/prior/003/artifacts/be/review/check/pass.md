---
verdict: PASS
summary: "经三轮独立审查（前两轮 FAIL 并返工），第三轮复审逐条核实修复属实、没有发现阻塞合并的问题；遗留两个很轻的非阻塞点已如实记录。"
---

# 后端代码审查：通过

## 审查输入
- gate begin 轮次：`001.1:be/review/check:3`，基线 `70a2d0b9b8d1a5e3c8e56ed3d6c39253683622cc`，固定范围摘要 `40cbcf352a454939ed1558d2467b3b793ecfc1dff1008919a96d166b80d7f524`（与测试门禁第 6 轮、安全审查第 4 轮相同，固定之后没有改过代码）。
- 审查由同一个独立的 `feature-dev:code-reviewer` agent 在三轮中完成（只读、没有 Bash 工具、没有运行测试）：我每轮只把需求描述或“声称修了什么”交给它去核实，没有给结论；它的发现由我逐条对照文件或实际运行 Python 复核。前两轮（`001.1:be/review/check:1`、`:2`）为 FAIL 并已回退返工，本轮是第三轮。

## 审查要点
- **正确性与需求一致性**：topic 名校验、符号链接/硬链接/FIFO 的处理、`core.md` 按完整 `## ` 条目边界内联（放不下的条目整条略去、被截断时必须补读）、分页索引（`total/nextOffset`、`limit` 夹紧、`offset` 越界为空页）、`scandir` 迭代式扫描与条目/topic 上限、按 topic 名排序、`title`/`hint` 上限、`ignored` 有界并附 `ignoredTotal`、`change status` 的 `MEMORY` 段与 `node instructions` 的 `memory` 字段、`init` 建目录（`lexists`）、保障 Diff 只排除工作区里的普通 topic 文件——三轮审查未发现与需求不一致的行为。
- **边界与错误处理**：空目录与缺目录按空处理、扫描期间条目消失被跳过、恰好等于上限仍通过、多字节字符不被切断、`memory/` 异常时 `change status` 不被拖垮（`error` 字段）、`memory/` 被换成文件时 Diff 给出结构化 `unsafe_path`、异常重抛不再产生自引用 cause、`fix` 文案只对 `ELOOP`/`ENOTDIR` 给出符号链接提示。
- **既有代码影响**：`TOP_KEYS` 已含 `memory`；既有测试里固定的段落顺序已更新为含 `MEMORY`；`_memory()` 在 payload 没有 `memory` 时返回空列表；`status()` 的 `**report` 不会覆盖 `memory` 键。
- **测试质量**（前两轮 FAIL 的主要原因，已逐项整改并经复审核实）：夹紧测试真的验证夹紧；“每个节点同摘要”测试对两个不同 Fragment 的节点比较，旧的空转测试已删除；`scandir` 提前终止与条目消失测试在实现退回 `listdir` 时会失败（不空转）；测试源码里无字面量 U+2028/2029 且有守卫测试；错误分支、topic 上限边界、`pointer` 出错、status 在 topic 超限时的行为、skill 维护提示词一致性（比较完整文本）都有测试。
- **测试覆盖**：测试门禁第 6 轮全量 1253 passed、1 skipped（既有 skip），lint 与 mypy 通过。

## 剩余风险
以下是第三轮复审指出、我核对属实但判定为不阻塞的点，改动代码会使全部门禁证据作废，因此记录为后续事项：
- `tests/test_workflow_memory.py` 约第 93–97 行：`test_control_characters_in_hint_cannot_forge_report_structure` 对 `hint` 断言 `" " not in entry["hint"]` 恒为真——`_title_and_hint` 先做 `splitlines()`，U+2028 本身就是行分隔符，hint 行在它之前就被切断了；同一测试里对 `\x1b` 的断言是有效的，U+2028 的转义真正被验证的是 core 内容那条用例（走 `_quote`）。影响很小。
- `test_pointer_reports_a_broken_core_without_raising` 中 `"SECRET-OUTSIDE" not in repr(pointer)` 本来就不可能失败（`pointer()` 的 core 不带正文），但它的 `present is False` 与 `error == "unsafe_path"` 断言有效，整个测试不算空。
- `memory/` 没有读权限时，错误的 `fix` 仍是默认的“检查配置并重新校验计划。”，不再误导到符号链接，但也没有给出可用的建议；`message` 里也仍含“包含符号链接”的通用措辞（来自既有的 `directory()`）。
- 继承自前几轮的非阻塞项：core 在报告里既内联又出现在索引中（设计有意如此）；`core` 含非法 UTF-8 时 `bytes` 与 `shown` 单位不完全一致；`pointer()` 为 `bytes` 字段读一遍 core（最大 2 MiB）；`printable_name` 不转义字面反斜杠；`lstat` 会跟随中间路径的符号链接（符号链接本身会作为改动出现在 Diff 中）；`ignored` 超过 `limit` 的部分不可见（文档已写明）。
- 首轮全量运行中，对机器负载敏感的 `test_plan_guard.py::test_long_command_is_decided_quickly` 曾偶发失败一次；此后各轮没有再出现。
- 模型行为（是否漏读、是否重复写入、`core` 被截断时是否补读）没有自动化测试，也没有人工验证。
