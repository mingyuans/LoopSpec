---
verdict: FAIL
summary: "独立审查并经我逐条核实：有两个测试名不副实、memory list --all 的 ignored 不受分页约束、title 无长度上限、Diff 排除不看文件模式（符号链接会被排除）、测试源码含字面量 U+2028、错误分支缺测试，需要返工；核心的路径安全与 core 条目边界逻辑审查后没有发现缺陷。"
---

# 后端代码审查：需要修改

## 阻塞问题
以下每条都已由我对照代码或文件确认（审查由一个独立的审查 agent 完成，我逐条核实）：

- `tests/test_workflow_memory.py::test_limit_is_clamped_and_bad_ranges_are_rejected`（约第 166–174 行）：只建了 3 个 topic，再断言 `limit=10_000` 返回 3 条，删掉 `workflow_memory.py` 里的 `limit = min(limit, LIST_MAX_LIMIT)` 这个测试照样通过，没有验证“夹紧”。另外 `offset` 恰好等于总数、超过总数的情形没有测试。修复方向：用 `monkeypatch` 把 `LIST_MAX_LIMIT` 调小，建多于上限的 topic，断言只返回上限条且 `nextOffset` 正确；补 `offset == total`、`offset > total`（返回空页、`nextOffset` 为 None）。
- `tests/test_workflow_memory.py::test_every_node_gets_the_same_memory_summary`（约第 546–552 行）：名字说“每个节点相同”，实际只对 `requirements/proposal` 一个节点调用了一次，最后一条 `"fragments" not in ...` 与要验证的行为无关。修复方向：对至少两个不同节点分别调用 `node instructions`，断言它们的 `memory` 字段完全相等；删掉无关断言。
- `src/loopspec/workflow_memory.py::list_topics`（约第 186–187 行）：`--all` 返回的 `ignored` 是 `_scan` 的完整列表，没有套用 `offset/limit`。`memory/` 下有接近 20000 个无关文件时，`memory list --all --limit 1` 仍输出全部 ignored 项，且每翻一页重复一遍，与“分页、有界输出”的需求不一致。修复方向：对 `ignored` 同样分页或截断，并给出 `ignoredTotal`，补测试。
- `src/loopspec/workflow_memory.py::_title_and_hint`（约第 151、161 行）：`hint` 被截断到 120 字符，`title` 没有上限，只受读取的 8 KiB 文件头间接限制；一个首行 8 KiB 的 `# 标题` 会让 JSON 输出膨胀（`memory list --limit 500` 可到数 MiB）。修复方向：给 `title` 加同样的长度上限，补测试。
- `src/loopspec/workflow_diff.py::_exclusions`：排除判断只看路径，不看文件类型。`memory/x.md` 如果是符号链接（git 模式 120000）也会被排除出 Diff，等于允许把一条指向别处的链接放过 Gate 审查，而设计要求只排除合法的 topic 普通文件。修复方向：在排除前对工作区路径做 `lstat`，只有常规文件（或工作区中已不存在的已删除文件）才排除；符号链接照常计入 Diff；补测试。
- `tests/test_workflow_memory.py`（第 95、97、497、498、501 行）：测试源码中含字面量的 U+2028 字符（我用脚本确认了这 5 行），看起来像空格，编辑器或格式化工具一旦规范化就会让测试静默改变含义。修复方向：全部改写成 `" "` 转义形式。
- 错误分支缺少测试：`summary()` 的 `except WorkflowError` 分支和 `status_report` 的 `topic index unavailable` 分支没有测试，“坏掉的 memory 不能拖垮 `change status`”这一承诺没有任何保护；topic 上限只测了超过一个的情形，没有“恰好等于上限仍然通过”的边界。修复方向：补 `memory/` 是符号链接时 `change status`（文本与 JSON）仍可输出并显示 unavailable；对 `TOPIC_SCAN_MAX`（用 `monkeypatch` 调小）补“恰好等于通过、多一个失败”。

## 其他会一并修的审查意见（非阻塞，但改动都很小）
- `src/loopspec/workflow_memory.py::_scan`：topic 按带扩展名的文件名排序，因此 `a-b.md` 排在 `a.md` 之前，与设计里“按 topic 名排序”不符；改为按 topic 名排序并补测试。
- `ENTRY_SCAN_MAX` 的注释与实现不符：`os.listdir` 会先把全部文件名读入内存再检查数量。改用 `os.scandir` 边迭代边计数，超过上限立即终止。
- 非 UTF-8 文件名（Linux 上可能出现）经 `os.listdir` 变成含代理字符的字符串，`memory list --all` 输出 `ignored` 时可能在编码处崩溃；对 ignored 的名字做安全转义（审查对此标为“不确定”，macOS 上无法复现，用单元测试验证转义函数）。
- 部分 memory 错误的 `fix` 文案不贴切（硬链接错误没有 `fix`，`directory()` 包出来的 `unsafe_path` 是“检查配置并重新校验计划”）：对 memory 相关的 `unsafe_path` 补上贴切的 `fix`。
- `continue.md` 与 `archive.md` 中的 “Memory maintenance procedure” 整段逐字重复，容易漂移：加一个测试断言两处文本完全一致。

## 审查输入
- gate begin 轮次 `001.1:be/review/check:1`，基线 `70a2d0b9b8d1a5e3c8e56ed3d6c39253683622cc`，固定范围摘要 `47d4285b784296e9f4251c985e428781cfe0609988e9a8ec9ba96b071850bc94`（与测试门禁第 4 轮、安全审查第 2 轮相同）。
- 审查由一个独立的 `feature-dev:code-reviewer` agent 完成（只读，未运行测试），它只拿到需求描述和代码位置，没有拿到我的结论；它没有 Bash 工具，所以没能运行 `git diff`，只读了最终文件内容。上面每个阻塞项都由我对照文件逐条确认。

## 已审查且未发现问题的方面
- 名字校验（`fullmatch` 拒绝带换行的名字，Diff 排除与引擎共用同一个 `is_topic_name`）、符号链接/硬链接/FIFO/悬空链接的处理、扫描期间条目消失的处理。
- core 内联：按 `## ` 条目边界、围栏内不拆分、空文件/前言超限/无标题大文件/多字节字符均得到完整条目，被截断时有明确的补读提示；上限比较符正确（恰好等于上限仍通过）。
- 输出转义覆盖控制字符与 U+2028/2029，段落结构不可被伪造；既有的 `TOP_KEYS`、段落顺序断言已正确更新，`status()` 的 `**report` 不会覆盖 `memory` 键。
- `init` 的 `lexists` 保护；skill 提示词没有明显的自相矛盾，`new` 的步骤编号与 `continue` 的引用仍对得上。

## 建议修复方向
- 先为每条阻塞项补失败测试并确认为红，再修复。
- 审查指出但我决定不修的两点，记录在此以免被误认为遗漏：core 在报告里既内联又出现在索引中（设计与测试有意如此）；`core` 的 `bytes`（原始字节）与 `shown`（解码重编码后的长度）在含非法 UTF-8 时单位不完全一致（极少见，只影响提示文字）；`pointer()` 为了 `bytes` 字段会读一遍 core（最大 2 MiB，开销可以忽略）。
