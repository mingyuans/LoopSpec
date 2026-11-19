## 背景与现状

- `workflow_archive.archive(home, name, force, dry_run, today)`：在 Change 写锁内 settle 活动 Plan、复核状态；dry-run 返回预览；否则 `move()` 后经已移动目录 fd 删除 `archive_drops()`（`.attempts`、`.gates`、`.gate-rounds`、Gate 报告）。`archive_all()` 循环调用。
- memory：`workflow_memory.MEMORY_DIR = "memory"`，`list_topics(home)` 给索引。维护流程原文在 `builtin/skills/archive.md` 与 `continue.md` 的同一段落（"Memory maintenance procedure."，由测试保证一致）。
- 事件：`workflow_journal.event_line()` 与 `append_text()` 向 `state.md` 末尾追加单行事件。

## 目标 / 非目标

**目标：** 归档拆为两段，memory 审阅结论成为第二段的必填输入，并由 CLI 核对与留痕；去掉 `--dry-run`。

**非目标：** 判断 memory 内容质量；改变删除范围、Gate 或 `plan archive`。

## 方案

### CLI

```
loopspec change archive <change> [--force]                 # 第一段（单个）
loopspec change archive --all [--older-than <days>]          # 第一段（批量）
loopspec change archive --confirm <archiveId> --memory updated|none --note <text>   # 第二段
```

- `--confirm` 不能与 Change 名、`--all`、`--force`、`--older-than` 同用（`option_conflict`）；没有 `--confirm` 时不能用 `--memory`/`--note`。
- `--memory` 取值 `updated|none`；`--note` 按 `state add` 的文本规则折叠为单行，非空，≤1000 字符，拒绝 `<!--`/`-->`（`workflow_invalid`）。

### 第一段：`prepare(home, names|all, force, older_than, today)`

1. 对每个候选 Change（单个或 `--all` 的筛选结果）在其写锁内：settle 活动 Plan → 复核状态（与现有逻辑相同：未完成且非 force 报 `archive_unsafe`；`--all` 中跳过并记原因）→ 计算 `drops = archive_drops(root)` 与 `content = content_digest(root)`。
2. `content_digest(root)`：按相对路径排序遍历 Change 目录（不跟随符号链接；跳过 `plans/.write.lock`），对普通文件取 `path + sha256`，其他条目取 `path + 类型`；总条目受 `MAX_FILES` 限制。
3. `memory_snapshot(home)`：`memory/` 下每个直接子项 → sha256（普通文件）或类型标记；目录不存在为空映射。
4. 凭据 `.cache/archive/<archiveId>.json`：`{version:1, created, entries:[{change, forced, status, content}], memory:{name:hash}, all: bool}`；`archiveId = digest(凭据主体)`（64 hex）。`.cache/archive/.gitignore` 不存在时写 `*`。
5. 返回：`archiveId`、`changes`（每项 `changeName/status/complete/forced/source/destination/dropped`(将删除)）、`skipped`（仅 `--all`）、`memoryReview`：
   - `instructions`：固定引导语 + 从 `builtin/skills/archive.md` 截取的 "Memory maintenance procedure." 段落（读取失败时退回内置短文）。
   - `inputs`：每个 Change 的 `state.md`、各 Plan `state.md`、`artifacts/` 下全部文件、Gate 报告、`.attempts/*/record.yaml` 的绝对路径（有上限，超出标注 `truncated`）。
   - `memoryIndex`：`list_topics(home)` 结果。
   - `nextSteps`：`loopspec change archive --confirm <id> --memory updated|none --note "<...>"`。
   - 没有可归档的 Change（`--all` 全部跳过）时不发凭据，`archiveId: null`。

### 第二段：`confirm(home, archive_id, memory, note, today)`

1. 读凭据（`archive_id` 仅与文件名做 64 hex 校验后使用；不存在 → `archive_ticket_not_found`；解析失败或摘要不符 → `archive_ticket_invalid`）。
2. memory 核对：当前快照与凭据比较得到 `changedTopics`（新增/修改/删除）。`updated` 且无变化 → `memory_review_missing`；`none` 且有变化 → `memory_review_mismatch`。均不移动。
3. 逐个 Change 在写锁内：settle → 复核状态（与第一段相同规则，forced 取自凭据）→ `content_digest` 与凭据比对，不同 → `archive_ticket_stale`（提示重新执行第一段）。全部通过后才进入写入阶段（`--all` 中任一失败则整体不移动）。
4. 对每个 Change：向 Change 级 `state.md` 追加事件 `归档前 memory 审阅 · 结论：updated|none · 变化：<topics或无> · 备注：<note>`（追加失败即报错，不移动）→ `move()`（含删除运行期文件）。
5. 全部成功后删除凭据；返回 `{archiveId, memoryReview:{memory, note, changedTopics}, archived:[原单个结果字段 moved/dropped/notDropped/destination…]}`。

### 删除 `--dry-run`

- 移除选项与 `dry_run` 参数；`archive()` 拆为 `prepare()` / `confirm()`，`archive_all()` 合入 `prepare(all=True)`。

### 错误码

| 错误码 | 场景 |
|---|---|
| `archive_ticket_not_found` | `--confirm` 的凭据不存在 |
| `archive_ticket_invalid` | 凭据文件损坏或摘要不符 |
| `archive_ticket_stale` | 第一段之后 Change 内容变化 |
| `memory_review_missing` | `--memory updated` 但 memory 无变化 |
| `memory_review_mismatch` | `--memory none` 但 memory 有变化 |

### skill

- `archive.md`：整理 state → 第一段 → 按 `memoryReview` 读素材、执行维护流程（维护流程段落保留，与 continue.md 一致）→ 第二段（如实选择 `updated`/`none` 并写 `--note`）；凭据过期时重新第一段；不得为通过校验而伪造 memory 改动。
- `bulk-archive.md`：同样两段，`--all`。
- 同步本仓库 `.claude`、`.codex` 生成副本；`tests/test_skill_templates.py` 与 `init_steps` 断言更新。

### 补做 memory

按维护流程，在本仓库 `loopspec/memory/` 写入来自 archive-drop-attempts、archive-drop-gate-outputs（及 registry-global-store 已记录的教训）的可复用条目，注明来源与日期。

## 归属与路径

BE：`src/loopspec/workflow_archive.py`、`src/loopspec/workflow_cli.py`、`src/loopspec/workflow_journal.py`；skill `builtin/skills/{archive,bulk-archive}.md` 与生成副本；`docs/{zh,en}/{cli-reference,agent-protocol}.md`；测试 `tests/test_workflow_archive.py`、`tests/test_workflow_cli.py`、`tests/test_workflow_e2e.py`、`tests/test_workflow_assurance.py`、`tests/test_skill_templates.py`、`tests/features/change.feature`、`tests/steps/{change,init}_steps.py`、LLM 场景；`loopspec/memory/`。

## 安全边界

- `archiveId` 只作为 64 hex 校验后的文件名使用；凭据内容是不可信输入，模型校验并比对摘要。
- 凭据只存于 `<home>/.cache/archive/`（O_NOFOLLOW 写入，自带忽略）；不含文件内容，只含摘要与路径。
- `--note` 经单行折叠与长度、注释标记校验后写入 `state.md`，不注入 Markdown 结构。
- 内容摘要遍历不跟随符号链接，受条目与单文件大小限制。

## 验证方案

- 单元：第一段不改文件且返回字段齐全；`--confirm` 各类缺参/冲突；凭据不存在/损坏/过期；updated 无变化、none 有变化；成功时 state 事件与凭据删除；force、all；与现有删除用例合并改写。
- BDD：`change.feature` 两段流程与拒绝场景。
- LLM E2E：现有两个归档场景改为两段式；新增断言：模型在归档前执行了第一段且第二段带 `--memory`，以及「没有新知识」场景使用 `none`。
- 回归：全量测试、docs 一致性。

## 风险与取舍

- 去掉单命令归档是破坏性的，换来协议级的审阅环节；旧 skill 需 `loopspec init --update-resources`/刷新。
- 只核对 memory「是否变化」与选择一致，不评估内容；`none` 的理由公开留痕作为补充约束。
- 备选：在 `state.md` 中要求 `memory-review` 段落而非事件——需改模板与段落注册，收益相同，未采用。

## 评审修订（Codex 只读审阅后，优先于上文）

1. **边界说明（不改）**：`--memory none` 加理由仍可跳过实际审阅；凭据在模型拥有相同文件权限的环境中不是安全边界，伪造凭据得到的能力不超过如实选择 `none`。约束来自「显式选择 + 必填理由 + 写入 state 留痕」，LLM E2E 断言模型在第二段之前执行了第一段并读取了素材。
2. **memory 快照只计有效 topic**：复用 `workflow_memory` 的规则（`is_topic_name`、普通文件、非符号链接、大小上限），只对 `memory/<topic>.md` 计算摘要；无关文件、目录、链接不计入，不能用来让 `updated` 通过。
3. **并发**：第二段按 Change 名排序，用 `ExitStack` 同时持有全部 Change 写锁直到提交结束；在锁内、写入前再取一次 memory 快照做核对。
4. **批量与重试**：写入前先预检全部条目（状态、内容摘要、归档目标不存在）；之后逐项「追加事件 → 移动」，每完成一项把进度（已归档、已写事件后的新内容摘要）写回凭据；中途失败时返回部分结果与错误，凭据保留，用同一 `archiveId` 重试会跳过已完成项。
5. **settle**：第一段与第二段都在锁内 settle 活动 Plan。这只是完成之前已提交命令留下的返工搬运（现有约定：下一条命令负责收尾），不属于归档动作；第一段因此「不归档、不删除」，验收条件按此理解。第二段的内容摘要在 settle 之后计算，与第一段一致。
6. **素材清单**：`inputs` 列出 `state.md`（Change 与各 Plan）、`artifacts/` 下全部文件，以及 `archive_drops()` 中每个将被删除的目录/文件路径（目录给路径，由模型自行浏览），不再逐个列 `.attempts` 记录；不做分页。
7. **严格事件写入**：审阅事件用 `append_text` 直接写入并在失败时抛错（不用尽力而为的 `record()`），写入成功后才 `move()`；事件中的 topic 名已经过 `is_topic_name` 校验，`--note` 经单行折叠。
