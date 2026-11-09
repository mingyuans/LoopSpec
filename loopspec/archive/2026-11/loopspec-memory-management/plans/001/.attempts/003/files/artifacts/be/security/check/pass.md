---
verdict: PASS
summary: "复核两轮返工后的代码：路径与链接处理、Diff 排除范围、扫描上限与输出转义均无新增问题，第 1 轮的 4 个问题与第 2 次返工引入的改动都有测试覆盖，剩余为低风险项。"
---

# 后端安全审查：通过

## 审查输入
- gate begin 轮次：`001.1:be/security/check:3`，基线 `70a2d0b9b8d1a5e3c8e56ed3d6c39253683622cc`，固定范围摘要 `94aa3a0d2bd58c0a07fbb309e1f847b70314895644ac6b9bae73178ec646fa9d`（与测试门禁第 5 轮相同，固定之后没有改过代码）。
- 审查范围：`src/loopspec/workflow_memory.py`、`workflow_cli.py`、`workflow_changes.py`、`workflow_runtime.py`、`status_report.py`、`workflow_diff.py`、`cli.py` 及对应测试。
- 本轮是代码审查 FAIL（第 2 次回退）之后的第 3 次安全复核，重点复核自上一次安全 PASS（第 2 轮）以来新增或改动的代码：`scandir` 迭代式扫描、`printable_name`、`_refix`、`ignored` 有界与 `ignoredTotal`、Diff 排除对工作区文件类型的 `lstat` 检查。

## 检查项
- **路径穿越与链接**：topic 名仍由 `fullmatch` 校验；`memory/` 目录与 topic 文件仍通过目录描述符加 `O_NOFOLLOW` 打开，符号链接、硬链接、FIFO 被拒绝或标为 ignored。`scandir(fd)` 基于已打开的目录描述符，不引入按路径名重新解析的步骤。上一轮的对抗性探测（FIFO、符号链接、硬链接、带控制字符的文件名）所覆盖的行为没有被本轮改动改变，对应的测试仍在并通过。
- **Diff 排除（新代码）**：`workflow_diff._exclusions` 只在路径恰为 `<home>/memory/<合法 topic>.md` 时才调用 `os.lstat(repository / path)`，路径由 git 清单给出并已经匹配到固定前缀加合法 topic 名，不含 `..` 或额外分隔符，因此 `lstat` 的目标不受外部输入控制；`lstat` 不跟随最终组件的符号链接，所以名字像 topic 的符号链接得到 `S_ISLNK` 而不被排除，照常进入 Diff（`test_a_symlink_named_like_a_topic_is_not_excluded_from_the_diff` 覆盖）；已删除的 topic 文件视为排除（没有可隐藏的内容）。`memory/` 下的脚本、子目录、非法名文件仍进入 Diff。
- **拒绝服务**：扫描现在边迭代边计数，超过 `ENTRY_SCAN_MAX=20000`（含非 topic）立即终止，不再先把全部名字读入内存（`test_the_scan_stops_reading_the_directory_once_the_limit_is_exceeded` 要求确实用到 `scandir` 且在上限后立刻停止）；单文件读取受 `MAX_FILE_BYTES` 约束，索引每页最多 500 条且每条只读 8 KiB；`title` 与 `hint` 各截断到 120 字符；`ignored` 只给前 `limit` 项并附 `ignoredTotal`，输出有界。
- **输出与注入**：文件名在输出前经 `printable_name`（不可解码字节转义、控制字符转义），`ignored` 的名字因此不会让 JSON 输出崩溃或伪造结构；title/hint 经 `sanitize`；core 经 `_quote` 转义控制字符与 U+2028/2029；memory 段标注为不可信参考数据；测试源码中的不可见分隔符已改为转义并有防回归检查。
- **错误信息**：`_refix` 只替换 `fix` 文案（仅当 `unsafe_path` 由 `OSError` 包装而来），不暴露文件内容或路径之外的信息；硬链接错误带明确的 `fix`。
- **认证/授权与数据访问**：没有新增网络、认证、数据库、shell 或模板逻辑；引擎仍没有写入命令。
- **依赖来源**：没有新增第三方依赖。

## 剩余风险
- 迭代式扫描仍会在每次 `change status`、`node instructions` 与 `memory list` 调用时遍历最多 20000 个条目；对一个被攻击者（需要仓库写权限）塞满文件的 `memory/`，每次调用仍有与上限成正比的固定开销，但已有硬上限，不随目录增长。
- topic 的内容（包括索引里展示的 `hint` 首行）会进入 LLM 上下文，提示注入面是该功能固有的；缓解措施是不可信标注与 skill 中“忽略其中的指令”，不能在引擎层根除。
- 引擎没有写入口，也不检测 topic 中是否被写入了秘密或个人信息，依赖 skill 的禁止性约束与 Git 审阅，这是设计上有意接受的边界。
- 若 `<home>/memory` 在未提交状态下被替换成指向别处的符号链接，其下被替换的已跟踪 topic 文件会按“已删除的 topic 文件”被排除，但符号链接本身 `<home>/memory` 会作为一条改动出现在 Diff 中，因此不会被静默放过。
