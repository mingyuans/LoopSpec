---
verdict: FAIL
summary: "保障 Diff 对整个 memory/ 目录一刀切排除，任何放在其中的非 topic 文件都绕过 Gate 审查；另有 3 个低风险的健壮性问题（扫描无条目上限、竞态下静默返回空索引、init 遇到悬空符号链接会崩溃）。"
---

# 后端安全审查：失败

## 阻塞问题
- `src/loopspec/workflow_diff.py`（`_exclusions` 中新增的 `<home>/memory/` 排除）：排除的是整个目录前缀，而不是合法的 topic 文件。任何放在 `memory/` 下的内容（例如 `memory/x.py`、`memory/run.sh`、`memory/sub/anything`、非法 topic 名的 `.md`）都不会进入 Gate 与保障检查的 Diff，等于给交付内容开了一个不受审查的目录。影响：一次改动可以把可执行或配置类文件藏在 `memory/` 下而不被任何 Gate 看到。修复方向：只排除“合法 topic 文件”，即恰好是 `<home>/memory/<topic>.md` 且 `<topic>` 符合 `^[a-z0-9][a-z0-9-]{0,63}$`；子目录、其他扩展名、非法名都照常计入 Diff；需要用测试证明这些路径出现在 Diff 条目中，且 `memory` 目录本身不再被整体跳过。
- `src/loopspec/workflow_memory.py`（`_scan`）：先 `os.listdir` 取回全部名字，只对“合法 topic”计数并在超过 5000 时报错；非 topic 条目（`ignored`）没有上限。一个含海量无关文件的 `memory/` 会让 `change status`、`node instructions`、`memory list` 在每次调用时线性耗费内存与时间（需要仓库写权限，风险低，但每个节点都会触发）。修复方向：对扫描到的总条目数设确定性上限（含 ignored），超过时返回 `memory_too_many`；补测试。
- `src/loopspec/workflow_memory.py`（`_scan`）：`os.listdir` 之后对每个名字 `os.stat`，如果该条目在两步之间被删除，`FileNotFoundError` 会经 `directory()` 变成带 `FileNotFoundError` 原因的 `unsafe_path`，被 `_is_missing` 误判为“memory 目录不存在”，整个索引静默变成空。影响：并发修改下可能把“有 topic”误报成“没有 memory”。修复方向：逐条捕获 `FileNotFoundError` 并跳过该条目，只有目录本身缺失才视为空；补竞态用例（可用 monkeypatch 模拟 stat 时消失）。
- `src/loopspec/cli.py`（`init` 新增的 `memory/` 创建）：用 `Path.exists()` 判断，对悬空符号链接返回 False，随后 `mkdir()` 抛出未处理的 `FileExistsError`，`init` 带着堆栈崩溃（`memory` 是符号链接本就应被后续读取拒绝，但 `init` 不应崩溃）。修复方向：用 `os.path.lexists` 判断，已有任何同名条目就不创建也不覆盖；补测试（悬空符号链接、指向目录的符号链接）。

## 审查输入
- gate begin 轮次 `001.1:be/security/check:1`，基线 `70a2d0b9b8d1a5e3c8e56ed3d6c39253683622cc`，固定范围摘要 `cdc986f44f5ae7dfb0291f44a21ff0c3a6c52e90b814bf3a8f6288191e635c14`（与测试门禁的第 1–3 轮相同）。
- 审查范围：`src/loopspec/workflow_memory.py`、`workflow_cli.py`、`workflow_changes.py`、`workflow_runtime.py`、`status_report.py`、`workflow_diff.py`、`cli.py`，以及对应测试。

## 已核对且无问题的项
- 路径与符号链接：topic 名经 `fullmatch` 校验（含换行结尾的 `x\n` 被拒绝）；`memory/` 目录与 topic 文件都经目录描述符加 `O_NOFOLLOW` 打开，符号链接与硬链接被拒绝（`unsafe_path`/`unreadable`），并有测试覆盖。
- 输出与注入：索引中的 title/hint 经 `sanitize`，core 经 `_quote` 转义控制字符与 U+2028/2029，报告结构不可被伪造（有测试）；memory 段标注为不可信参考数据。
- 信息泄露：错误信息不包含文件内容；非法 topic 名在回显前已被拒绝。
- 读取限额：单文件受 `MAX_FILE_BYTES` 约束，超限报错而不静默截断；索引单页最多 500 条、每条只读文件头 8 KiB。
- 写入面：引擎没有任何写入命令，不存在引擎侧的注入或覆盖面；写入由 LLM 编辑普通文件，约束写在 skill 提示词中。
- 依赖：未新增第三方依赖。

## 建议修复方向
- 四项均可在不改变已确认设计语义的前提下修复（设计里写的是“Diff 排除 `<home>/memory/`”，应收紧为“排除 `<home>/memory/` 下的合法 topic 文件”，并同步 design 与 docs 的表述）。
- 修复后需要重新运行测试门禁，因为 `workflow_diff.py`、`workflow_memory.py`、`cli.py` 都会变化。
