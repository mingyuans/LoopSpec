---
verdict: FAIL
summary: "复审核实：上轮 4 条修复里 3 条属实，但我的去重重构留下了一个仍然空转的旧测试，Diff 排除新增的 lstat 在目录被换成文件时会抛出未处理的 NotADirectoryError，另有 3 个小问题；需要再返工一次。"
---

# 后端代码审查：需要修改

## 阻塞问题
以下每条都已由我对照文件或实际运行 Python 确认（复审由同一个独立审查 agent 完成，我逐条核实）：

- `tests/test_workflow_memory.py` 中仍保留旧测试 `test_every_node_gets_the_same_memory_summary`（约第 760–774 行）：这是我上一轮用“按函数名去重”修复文件重复时留下的——新测试改名为 `..._whatever_its_fragment`，旧测试因名字不同被保留。它只对 `requirements/proposal` 有效，`design/design` 在未写 `proposal.md` 时不就绪，循环 `continue`，最后 `all(item == memories[0])` 是自己和自己比；其中 `invoke_args` 加 `assert node not in invoke_args` 是无意义断言。同一区域的 `test_the_memory_summary_does_not_depend_on_the_node_fragment` 与新测试几乎重复。修复方向：删除这两个旧测试，只保留对两个不同 Fragment 的节点做比较的那个。
- `src/loopspec/workflow_diff.py::_exclusions` 的 `memory_topic`（约第 143–149 行）：`os.lstat` 只捕获 `FileNotFoundError`。我用 Python 验证了对“某个路径组件是普通文件”会抛出 `NotADirectoryError`，它不是 `FileNotFoundError` 的子类。触发场景：基线里有 `<home>/memory/core.md`，工作区把 `<home>/memory` 目录换成一个普通文件，排除判断被基线路径调用时以裸异常崩出，而不是结构化错误。修复方向：捕获 `OSError`，此时不排除（返回 False），让后续逻辑照常处理；补测试（基线有 topic 文件、工作区把目录换成文件，`collect_diff` 不抛裸异常，且 `memory` 与被删除的 topic 路径按预期出现）。
- `src/loopspec/workflow_memory.py` 中多处 `raise _refix(exc) from exc`（约第 134、203、252 行）：不需要改写时 `_refix` 返回同一个对象，变成 `raise exc from exc`，`__cause__` 指向自己，本来没有 cause 的 `memory_too_many`、`memory_too_large`、硬链接错误也被加上无意义的自引用，之后任何检查 `__cause__`（如 `_is_missing`）的人都会拿到自己。修复方向：不需要改写时直接 `raise`，只有真正替换时才 `raise new from exc`；补测试断言这些错误的 `__cause__` 为 None。
- `src/loopspec/workflow_memory.py::_refix`（约第 67–71 行）：触发条件是“`unsafe_path` 且 cause 是 `OSError`”，对 `EACCES`（没有读权限）也会提示“不能是符号链接”，方向不对。修复方向：只在 `ELOOP`、`ENOTDIR` 时使用这条文案，其余保留通用提示；补测试（目录权限为 0 时的 fix 文案；测试需在 root 下跳过）。
- 测试缺口（复审指出，我核对属实）：`pointer()` 在 core 出错时的 `error` 字段没有测试；topic 数超过上限时 `change status` 的行为没有测试（承诺是“坏掉的 memory 不能拖垮 change status”）；skill 提示词一致性测试只比较到第一个空行，将来段落中间插入空行会悄悄放过后半段漂移。修复方向：补 `pointer` 出错与 status 在 `memory_too_many` 时仍可输出的测试；把一致性测试改为比较从 “Memory maintenance procedure.” 到固定结束句 “without inventing writes or test results.” 的完整文本。

## 审查输入
- gate begin 轮次 `001.1:be/review/check:2`，基线 `70a2d0b9b8d1a5e3c8e56ed3d6c39253683622cc`，固定范围摘要 `94aa3a0d2bd58c0a07fbb309e1f847b70314895644ac6b9bae73178ec646fa9d`（与测试门禁第 5 轮、安全审查第 3 轮相同）。
- 复审由同一个 `feature-dev:code-reviewer` agent 完成（只读、没有 Bash，未运行测试），我只把“声称修了什么”交给它核实，没有给结论；以下“已核实”的结论来自它读最终文件。

## 复审已核实属实的修复
- `limit` 夹紧测试确实把 `LIST_MAX_LIMIT` 调小并验证了夹紧；`offset` 等于、超过总数有测试；`memory/` 为符号链接时 `change status`（文本与 JSON）的错误分支有测试；topic 上限“恰好等于通过、多一个失败”有测试（在 monkeypatch 下）；测试文件里没有字面量 U+2028/U+2029，并有守卫测试。
- `_scan` 用 `os.scandir` 迭代并在超限时立即终止；topic 按 topic 名排序且测试能区分 stem 排序与文件名排序；title 与 hint 同样截断；`--all` 的 `ignored` 只给前 `limit` 项并附 `ignoredTotal`；ignored 名字经 `printable_name` 转义。
- Diff 排除只认普通 topic 文件，符号链接不被排除，已删除的被排除。
- `scandir` 相关两个测试不是空测试：把实现退回 `os.listdir`，`"ghost.md" in consumed` 与 `1 <= len(consumed) <= 6` 都会失败。
- 新的 scandir 循环对幻影条目、空名字这两个边界没有问题；`scandir` 与 `directory()` 的退出顺序正确。

## 记录但不修复的点
- `--all` 的 `ignored` 超过 `limit` 的部分无法再看到（`ignored[:limit]` 不受 `offset` 影响）：这是有意的“诊断用、有界输出”取舍，文档已写明“只给前 `--limit` 项并附 `ignoredTotal`”，不再单独分页。
- `printable_name` 不转义字面反斜杠，一个真实叫 `\udcff` 的文件名与一个非 UTF-8 文件名显示相同；影响可忽略。
- `lstat` 会跟随中间路径的符号链接（`memory` 目录被换成符号链接时按链接目标判断）：这类路径是已跟踪的 topic 文件，符号链接本身会作为一条改动出现在 Diff 中，影响面很小。
- `test_status_report.py:279、308` 与 `test_presentation.py:401-402` 中的字面量 U+2028 是既有代码，不在本次范围。

## 建议修复方向
- 先为每条阻塞项补失败测试并确认为红，再修复；删除旧的空测试要在同一提交里完成，不再用“按名字去重”的方式整理测试文件。
