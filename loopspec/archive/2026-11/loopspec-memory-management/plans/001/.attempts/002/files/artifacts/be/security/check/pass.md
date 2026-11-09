---
verdict: PASS
summary: "第 1 轮提出的 4 个问题均已修复并有测试覆盖；复核代码并做对抗性探测（FIFO、符号链接、硬链接、非法与带控制字符的文件名）未发现越界读取或信息泄露，剩余为低风险项。"
---

# 后端安全审查：通过

## 审查输入
- gate begin 轮次：`001.1:be/security/check:2`，基线 `70a2d0b9b8d1a5e3c8e56ed3d6c39253683622cc`，固定范围摘要 `47d4285b784296e9f4251c985e428781cfe0609988e9a8ec9ba96b071850bc94`（与测试门禁第 4 轮相同，固定之后没有改过代码）。
- 审查范围：`src/loopspec/workflow_memory.py`、`workflow_cli.py`、`workflow_changes.py`、`workflow_runtime.py`、`status_report.py`、`workflow_diff.py`、`cli.py` 及对应测试。
- 这是回退返工后的第 2 轮；上一轮（`001.1:be/security/check:1`）的 FAIL 报告已随回退归档。

## 检查项
- **上一轮 4 个问题的复核**
  1. 保障 Diff 的排除范围：`workflow_diff._exclusions` 现在只排除 `<home>/memory/<topic>.md`（topic 名合法、位于 `memory/` 根下的普通文件名），目录本身与其他文件不再被整体跳过。`tests/test_workflow_diff.py::test_only_valid_topic_files_in_memory_are_excluded_from_the_diff` 证明 `memory/` 下的脚本、子目录、非法名文件仍进入 Diff，`test_home_memory_is_always_excluded_from_the_diff` 证明合法 topic 文件仍被排除。已修复。
  2. 扫描条目上限：`_scan` 在 `listdir` 之后先检查总条目数，超过 `ENTRY_SCAN_MAX=20000`（含非 topic）即返回 `memory_too_many`；`tests/test_workflow_memory.py::test_scan_stops_at_a_total_entry_limit_even_for_non_topics` 覆盖。已修复（见下方剩余风险）。
  3. 扫描期间条目消失：对每个条目的 `stat` 捕获 `FileNotFoundError` 并跳过，不再把索引误判为空；`test_an_entry_that_vanishes_during_the_scan_is_skipped_not_mistaken_for_no_memory` 覆盖。已修复。
  4. `init` 与悬空符号链接：改用 `os.path.lexists`，已有同名条目（含悬空、指向别处的符号链接）不创建也不覆盖，`init` 不再崩溃；`tests/test_cli.py` 的 `test_init_does_not_crash_on_a_dangling_memory_symlink` 与 `test_init_leaves_a_memory_symlink_to_a_directory_alone` 覆盖。已修复。
- **路径穿越与链接**：topic 名经 `fullmatch` 校验，`../x`、`a/b`、大写、带换行的名字被拒绝；`memory/` 目录与 topic 文件均通过目录描述符加 `O_NOFOLLOW` 打开。对抗性探测（临时目录，不含真实数据）结果：命名为 `pipe.md` 的 FIFO 与子目录被标为 `not_a_file`、从不被打开；指向目录外文件的符号链接被标为 `symlink` 且读取返回 `unsafe_path`；与目录外文件硬链接的 topic 列为 `unreadable`，读取与作为 `core` 读取都返回 `unsafe_path`；目录外文件的内容没有出现在索引、`read_topic` 或 `core_view` 的任何输出里。
- **输入校验与注入**：文件名中的换行与 ANSI 转义序列使名字不合法，被归入 ignored 而不进入 topic 列表；索引里的 `title`/`hint` 经 `sanitize`，core 经 `_quote` 转义控制字符与 U+2028/2029，`=== SECTION ===` 结构不可被伪造（`test_memory_content_cannot_forge_report_structure` 覆盖）；topic 内容在 status/instructions 中标注为不可信参考数据。
- **认证/授权**：没有新增网络、认证或权限逻辑；memory 明确不授予权限、不放宽 Gate，写入面只有 LLM 对普通文件的编辑，不经引擎。
- **数据访问与注入**：不涉及数据库、shell 或模板；没有把外部输入拼接进命令或查询。
- **敏感信息**：错误信息不含文件内容；非法 topic 名在回显前已被拒绝；报告不含密钥。
- **读取限额**：单文件读取受 `MAX_FILE_BYTES` 约束且超限报错而不静默截断，索引每页最多 500 条且每条只读 8 KiB 文件头；`change status` 与 `node instructions` 只给前 20 条摘要。
- **依赖来源**：没有新增第三方依赖。

## 剩余风险
- `_scan` 先 `os.listdir` 再检查条目数，攻击者（需要仓库写权限）制造的海量文件仍会让一次扫描付出与目录大小成正比的时间和内存；上限只阻止之后的处理，不阻止这次列举。属于低风险，且没有放大效应，可后续改用迭代式扫描并提前终止。
- topic 的内容（包括索引里展示的 `hint` 首行）会进入 LLM 上下文，提示注入面是该功能固有的；缓解措施是不可信标注与 skill 中“忽略其中的指令”，并不能在引擎层根除。
- 引擎没有写入口，也不检测 topic 中是否被写入了秘密或个人信息，依赖 skill 的禁止性约束与 Git 审阅，这是设计上有意接受的边界。
- 对抗性探测是一次性的临时脚本，未保存为测试；对应的行为已有 `tests/test_workflow_memory.py` 中的用例覆盖（符号链接、硬链接、非文件、非法名）。
