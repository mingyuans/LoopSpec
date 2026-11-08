---
verdict: PASS
summary: "复核自上次安全 PASS 以来的改动（Diff 排除对 OSError 的处理、异常重抛与 fix 文案收窄）：都朝更安全的方向（排除失败时不排除、权限错误不被误导），无新增问题。"
---

# 后端安全审查：通过

## 审查输入
- gate begin 轮次：`001.1:be/security/check:4`，基线 `70a2d0b9b8d1a5e3c8e56ed3d6c39253683622cc`，固定范围摘要 `40cbcf352a454939ed1558d2467b3b793ecfc1dff1008919a96d166b80d7f524`（与测试门禁第 6 轮相同，固定之后没有改过代码）。
- 审查范围：`src/loopspec/workflow_memory.py`、`workflow_cli.py`、`workflow_changes.py`、`workflow_runtime.py`、`status_report.py`、`workflow_diff.py`、`cli.py` 及对应测试。
- 这是第 3 次返工后的第 4 次安全复核。上一次安全 PASS（第 3 轮）之后只有两处代码改动：`workflow_diff` 的 `memory_topic` 对 `OSError` 的处理，以及 `workflow_memory` 的 `_reraise` 与 `_refix` 收窄；其余为测试。

## 检查项
- **Diff 排除（本轮改动）**：`os.lstat` 失败时的处理现在是：`FileNotFoundError`（已删除）视为排除，其他 `OSError`（例如 `memory/` 被换成文件、无权限）返回“不排除”，把路径交回 Diff 的正常处理。这一改动是 fail-safe 方向：无法确认是普通 topic 文件时不排除，该路径会被审查而不是被静默放过；同时不再抛出裸 `NotADirectoryError`。`lstat` 的路径仍只在 `<home>/memory/<合法 topic>.md` 时才构造，不含 `..` 或额外分隔符，目标不受外部输入控制。
- **异常处理（本轮改动）**：`_reraise` 在不需要改写时原样 `raise`，替换 `fix` 时才 `raise new from exc`；不再出现 `__cause__` 指向自己的情况，也不会改变 `_is_missing` 等依赖 `__cause__` 的判断（有测试覆盖 `memory_too_many`、`memory_too_large`、硬链接错误的 `__cause__` 为 None）。`_refix` 只在 `ELOOP`、`ENOTDIR` 时给出符号链接相关的提示，权限错误保持通用提示，不再误导排查方向；`fix` 文案只含固定文字，不包含文件内容或路径之外的信息。
- **路径穿越与链接、拒绝服务、输出与注入、认证/授权、依赖来源**：本轮没有改动这些代码路径；上一次安全 PASS（`001.1:be/security/check:3`）的结论仍然成立，相关测试在本轮全量运行中全部通过（符号链接、硬链接、FIFO、非法与带控制字符的文件名、`scandir` 提前终止、条目与 topic 上限、`ignored` 有界、title/hint 上限、输出转义）。
- **敏感信息**：错误信息不含文件内容；报告不含密钥。

## 剩余风险
- 迭代式扫描仍会在每次 `change status`、`node instructions` 与 `memory list` 调用时遍历最多 20000 个条目；有硬上限，不随目录增长。
- topic 的内容（包括索引里展示的 `hint` 首行）会进入 LLM 上下文，提示注入面是该功能固有的；缓解措施是不可信标注与 skill 中“忽略其中的指令”，不能在引擎层根除。
- 引擎没有写入口，也不检测 topic 中是否被写入了秘密或个人信息，依赖 skill 的禁止性约束与 Git 审阅，这是设计上有意接受的边界。
- `lstat` 会跟随中间路径的符号链接：`<home>/memory` 在未提交状态下被换成符号链接时，其下已跟踪的 topic 路径会按链接目标判断，符号链接本身会作为一条改动出现在 Diff 中，不会被静默放过。
